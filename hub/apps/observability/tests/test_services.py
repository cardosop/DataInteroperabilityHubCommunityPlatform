"""
Unit tests for ObservabilityService.

Tests cover all service methods with real seeded data for meaningful content verification.

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
from hub.apps.observability.models import (
    DataObservabilityMetric,
    FreshnessSLA,
)
from hub.apps.observability.services import ObservabilityService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ObservabilityServiceTest(TestCase):
    """Test ObservabilityService operations with seeded data"""

    def setUp(self):
        """Set up test data with actual observability metrics"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = ObservabilityService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Seed test data: asset, file, dataset, and freshness metrics
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"svc-asset-{uid}",
            name="Service Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path=f"test/svc-{uid}.csv",
            content_sha256="abc123",
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "id", "type": "int"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

        # Create 3 freshness metrics with known values:
        # 2 stale (HOURLY SLA with 7200s age), 1 fresh (DAILY SLA with 3600s age)
        for i in range(2):
            DataObservabilityMetric.objects.create(
                tenant=self.tenant,
                dataset=self.dataset,
                last_update_time=timezone.now() - timedelta(hours=2),
                freshness_age_seconds=7200,
                freshness_sla=FreshnessSLA.HOURLY,
                freshness_sla_seconds=3600,
                is_stale=True,
                row_count=1000 + i * 100,
                size_bytes=50000 + i * 1000,
            )

        DataObservabilityMetric.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=1),
            freshness_age_seconds=3600,
            freshness_sla=FreshnessSLA.DAILY,
            freshness_sla_seconds=86400,
            is_stale=False,
            row_count=500,
            size_bytes=25000,
        )

    def test_get_freshness_dashboard_returns_seeded_data(self):
        """Test freshness dashboard returns actual seeded metrics."""
        result = self.service.get_freshness_dashboard(tenant_id=str(self.tenant.id))

        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIn("summary", result)

        results = result["results"]
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 3, "Expected 3 seeded metrics")

        # Verify first metric's content shape
        first = results[0]
        self.assertIn("id", first)
        self.assertIn("dataset_id", first)
        self.assertIn("freshness_age_seconds", first)
        self.assertIn("freshness_sla", first)
        self.assertIn("is_stale", first)
        self.assertIn("recorded_at", first)

        # Verify summary statistics match seeded data
        summary = result["summary"]
        self.assertEqual(summary["total_metrics"], 3)
        self.assertEqual(summary["stale_count"], 2)
        self.assertEqual(summary["fresh_count"], 1)
        self.assertIn("HOURLY", summary["sla_distribution"])
        self.assertIn("DAILY", summary["sla_distribution"])
        self.assertEqual(summary["sla_distribution"]["HOURLY"], 2)
        self.assertEqual(summary["sla_distribution"]["DAILY"], 1)
        self.assertGreater(summary["stale_percentage"], 0)

    def test_get_freshness_dashboard_with_dataset_filter(self):
        """Test freshness dashboard filter narrows results to specific dataset."""
        result = self.service.get_freshness_dashboard(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            limit=10,
        )

        results = result["results"]
        self.assertGreater(len(results), 0)
        # All results should belong to the filtered dataset
        for item in results:
            self.assertEqual(item["dataset_id"], str(self.dataset.id))

    def test_get_freshness_dashboard_empty_when_no_data(self):
        """Test freshness dashboard returns empty structure when no metrics exist."""
        empty_tenant = Tenant.objects.create(
            name=f"Empty {uuid.uuid4().hex[:8]}",
            slug=f"empty-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        result = self.service.get_freshness_dashboard(tenant_id=str(empty_tenant.id))

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["results"]), 0)
        self.assertEqual(result["summary"]["total_metrics"], 0)
        self.assertEqual(result["summary"]["stale_count"], 0)

    def test_get_volume_dashboard_returns_expected_structure(self):
        """Test volume dashboard returns expected dict structure."""
        result = self.service.get_volume_dashboard(tenant_id=str(self.tenant.id))
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["results"], list)

    def test_get_schema_drift_dashboard_returns_expected_structure(self):
        """Test schema drift dashboard returns expected dict structure."""
        result = self.service.get_schema_drift_dashboard(tenant_id=str(self.tenant.id))
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIn("summary", result)
        self.assertIsInstance(result["results"], list)


class ObservabilityServiceFailureTest(TestCase):
    """Test ObservabilityService failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = ObservabilityService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_get_freshness_dashboard_invalid_tenant_id(self):
        """Test getting freshness dashboard with invalid tenant ID raises NotFoundError"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.get_freshness_dashboard(tenant_id=str(uuid.uuid4()))

    def test_get_volume_dashboard_invalid_tenant_id(self):
        """Test getting volume dashboard with invalid tenant ID raises NotFoundError"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.get_volume_dashboard(tenant_id=str(uuid.uuid4()))

    def test_get_schema_drift_dashboard_invalid_tenant_id(self):
        """Test getting schema drift dashboard with invalid tenant ID raises NotFoundError"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.get_schema_drift_dashboard(tenant_id=str(uuid.uuid4()))


class ObservabilityServiceErrorHandlingTest(TestCase):
    """Test ObservabilityService error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = ObservabilityService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_service_initialization_without_tenant(self):
        """Test service initialization without tenant"""
        service = ObservabilityService()
        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)

    def test_get_dashboards_handle_missing_data(self):
        """Test getting dashboards handles empty state gracefully"""
        empty_tenant = Tenant.objects.create(
            name=f"Empty {uuid.uuid4().hex[:8]}",
            slug=f"empty-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        freshness = self.service.get_freshness_dashboard(tenant_id=str(empty_tenant.id))
        volume = self.service.get_volume_dashboard(tenant_id=str(empty_tenant.id))
        schema_drift = self.service.get_schema_drift_dashboard(tenant_id=str(empty_tenant.id))

        for dashboard in [freshness, volume, schema_drift]:
            self.assertIn("results", dashboard)
            self.assertIn("summary", dashboard)
            self.assertIsInstance(dashboard["results"], list)
