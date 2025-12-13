"""
Unit tests for Data Freshness Monitoring

Tests for freshness tracking, SLA calculation, and stale data detection.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.observability.models import DataObservabilityMetric, FreshnessSLA
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class FreshnessMonitorTest(TestCase):
    """Test FreshnessMonitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            name="Test Dataset",
            schema_json={"fields": [{"name": "email", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
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
            freshness_sla=FreshnessSLA.HOURLY.value,
            row_count=1000,
            size_bytes=50000
        )
        
        self.assertIsNotNone(metric)
        self.assertEqual(metric.dataset_id, self.dataset.id)
        self.assertIsNotNone(metric.freshness_age_seconds)
        self.assertEqual(metric.freshness_sla, FreshnessSLA.HOURLY.value)
        self.assertEqual(metric.row_count, 1000)
        self.assertEqual(metric.size_bytes, 50000)
    
    def test_get_freshness_dashboard(self):
        """Test freshness dashboard"""
        # Record some metrics
        FreshnessMonitor.record_metric(
            tenant_id=str(self.tenant.id),
            dataset=self.dataset,
            last_update_time=timezone.now() - timedelta(hours=2),
            freshness_sla=FreshnessSLA.HOURLY.value
        )
        
        dashboard = FreshnessMonitor.get_freshness_dashboard(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id)
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
            freshness_sla=FreshnessSLA.HOURLY.value  # 1 hour SLA, 2 hours old = stale
        )
        
        stale_data = FreshnessMonitor.detect_stale_data(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id)
        )
        
        self.assertGreater(len(stale_data), 0)
        self.assertTrue(stale_data[0]["freshness_age_seconds"] > 3600)

