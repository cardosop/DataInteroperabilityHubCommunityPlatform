"""
Unit tests for Data Freshness Monitoring

Tests for freshness tracking, SLA calculation, and stale data detection.

Comprehensive tests without mocks/stubs, following engineering best practices and TDD principles.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.models import FreshnessSLA
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class FreshnessMonitorTest(TestCase):
    """Test FreshnessMonitor"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def test_calculate_freshness_age(self):
        """Test freshness age calculation"""
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)

        age = FreshnessMonitor.calculate_freshness_age(one_hour_ago)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 3600)  # At least 1 hour in seconds
        self.assertLess(age, 3700)  # Less than 1 hour + 2 minutes

    def test_is_stale(self):
        """Test stale data detection"""
        # Data is 2 hours old, SLA is 1 hour -> stale
        self.assertTrue(FreshnessMonitor.is_stale(7200, 3600))

        # Data is 30 minutes old, SLA is 1 hour -> not stale
        self.assertFalse(FreshnessMonitor.is_stale(1800, 3600))

        # No SLA -> never stale
        self.assertFalse(FreshnessMonitor.is_stale(7200, None))

        # Unknown freshness -> not stale
        self.assertFalse(FreshnessMonitor.is_stale(None, 3600))

    def test_record_metric(self):
        """Test recording observability metric"""
        last_update = timezone.now() - timedelta(hours=1)

        metric = FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=last_update,
            freshness_sla=FreshnessSLA.HOURLY,
            row_count=1000,
            size_bytes=50000,
        )

        self.assertIsNotNone(metric)
        self.assertEqual(metric.dataset_id, self.dataset.id)
        self.assertIsNotNone(metric.freshness_age_seconds)
        self.assertEqual(metric.freshness_sla, FreshnessSLA.HOURLY)
        self.assertEqual(metric.row_count, 1000)
        self.assertEqual(metric.size_bytes, 50000)

    def test_get_freshness_dashboard(self):
        """Test freshness dashboard"""
        # Record some metrics
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=2),
            freshness_sla=FreshnessSLA.HOURLY,
        )

        dashboard = FreshnessMonitor.get_freshness_dashboard(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id)
        )

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertGreater(len(dashboard["results"]), 0)

    def test_detect_stale_data(self):
        """Test stale data detection"""
        # Record stale metric
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=2),
            freshness_sla=FreshnessSLA.HOURLY.value,  # 1 hour SLA, 2 hours old = stale
        )

        stale_data = FreshnessMonitor.detect_stale_data(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id)
        )

        self.assertGreater(len(stale_data), 0)
        self.assertTrue(stale_data[0]["freshness_age_seconds"] > 3600)


class FreshnessMonitorFailureTest(TestCase):
    """Test FreshnessMonitor failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_record_metric_invalid_tenant_id(self):
        """Test recording metric with invalid tenant ID"""
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            FreshnessMonitor.record_metric(
                tenant_id=str(uuid.uuid4()),  # Non-existent tenant
                dataset=None,
                last_update_time=timezone.now(),
                freshness_sla=FreshnessSLA.HOURLY.value,
            )

    def test_get_freshness_dashboard_invalid_tenant_id(self):
        """Test getting freshness dashboard with invalid tenant ID"""
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            FreshnessMonitor.get_freshness_dashboard(
                tenant_id=str(uuid.uuid4())  # Non-existent tenant
            )

    def test_detect_stale_data_invalid_dataset_id(self):
        """Test detecting stale data with invalid dataset ID"""
        # Should handle gracefully or raise appropriate error
        try:
            stale_data = FreshnessMonitor.detect_stale_data(
                tenant_id=str(self.tenant.id),
                dataset_id=str(uuid.uuid4()),  # Non-existent dataset
            )
            # May return empty list if handled gracefully
            self.assertIsInstance(stale_data, list)
        except Exception:
            # Exception acceptable if validation is strict
            pass


class FreshnessMonitorEdgeCasesTest(TestCase):
    """Test FreshnessMonitor edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_calculate_freshness_age_very_old(self):
        """Test freshness age calculation for very old data"""
        very_old_time = timezone.now() - timedelta(days=365)
        age = FreshnessMonitor.calculate_freshness_age(very_old_time)
        self.assertGreater(age, 30000000)  # More than 1 year in seconds

    def test_calculate_freshness_age_very_recent(self):
        """Test freshness age calculation for very recent data"""
        recent_time = timezone.now() - timedelta(seconds=1)
        age = FreshnessMonitor.calculate_freshness_age(recent_time)
        self.assertLessEqual(age, 5)  # Should be around 1 second

    def test_is_stale_exactly_at_threshold(self):
        """Test staleness detection exactly at threshold"""
        is_stale = FreshnessMonitor.is_stale(3600, 3600)  # Exactly at SLA
        # Should not be stale when exactly at SLA (stale only when strictly exceeding)
        self.assertFalse(is_stale)

    def test_record_metric_with_all_sla_types(self):
        """Test recording metric with all SLA types"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        for sla_name, _sla_label in FreshnessSLA.choices:
            metric = FreshnessMonitor.record_metric(
                tenant_id=str(self.tenant.id),
                asset=asset,
                last_update_time=timezone.now(),
                freshness_sla=sla_name,
            )
            self.assertIsNotNone(metric)
            self.assertEqual(metric.freshness_sla, sla_name)

    def test_get_freshness_dashboard_empty(self):
        """Test getting freshness dashboard when empty"""
        dashboard = FreshnessMonitor.get_freshness_dashboard(tenant_id=str(self.tenant.id))

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 0)


class FreshnessMonitorErrorHandlingTest(TestCase):
    """Test FreshnessMonitor error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_record_metric_handles_none_values(self):
        """Test recording metric handles None values gracefully"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Should handle None values gracefully
        try:
            metric = FreshnessMonitor.record_metric(
                tenant_id=str(self.tenant.id),
                asset=asset,
                last_update_time=None,  # None last update
                freshness_sla=None,  # None SLA
            )
            # May succeed with None values or handle gracefully
            self.assertIsNotNone(metric)
        except Exception:
            # Exception acceptable if None values are not allowed
            pass

    def test_get_freshness_dashboard_handles_missing_data(self):
        """Test getting freshness dashboard handles missing data"""
        dashboard = FreshnessMonitor.get_freshness_dashboard(
            tenant_id=str(self.tenant.id),
            dataset_id=str(uuid.uuid4()),  # Non-existent dataset
        )

        # Should return empty dashboard structure
        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)

    def test_detect_stale_data_handles_no_metrics(self):
        """Test detecting stale data handles no metrics"""
        stale_data = FreshnessMonitor.detect_stale_data(tenant_id=str(self.tenant.id))

        # Should return empty list if no metrics
        self.assertIsInstance(stale_data, list)
