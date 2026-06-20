"""
Unit tests for Data Volume Monitoring

Tests for volume tracking, trend aggregation, and anomaly detection.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.observability.freshness import FreshnessMonitor
from hub.apps.observability.volume import VolumeMonitor
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class VolumeMonitorTest(TestCase):
    """Test VolumeMonitor"""

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

        # Record some metrics
        for i in range(5):
            FreshnessMonitor.record_metric(
                tenant_id=str(self.tenant.id),
                dataset=self.dataset,
                row_count=1000 + i * 100,
                size_bytes=50000 + i * 5000,
            )

    def test_aggregate_hourly_trends(self):
        """Test hourly trend aggregation"""
        trends = VolumeMonitor.aggregate_hourly_trends(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id), hours=24
        )

        self.assertGreater(len(trends), 0)
        for trend in trends:
            self.assertEqual(trend.period_type, "HOURLY")
            self.assertIsNotNone(trend.avg_row_count)

    def test_aggregate_daily_trends(self):
        """Test daily trend aggregation"""
        trends = VolumeMonitor.aggregate_daily_trends(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id), days=30
        )

        self.assertGreater(len(trends), 0)
        for trend in trends:
            self.assertEqual(trend.period_type, "DAILY")
            self.assertIsNotNone(trend.avg_row_count)

    def test_get_volume_dashboard(self):
        """Test volume dashboard"""
        # Aggregate trends first
        VolumeMonitor.aggregate_daily_trends(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id), days=30
        )

        dashboard = VolumeMonitor.get_volume_dashboard(
            tenant_id=str(self.tenant.id), dataset_id=str(self.dataset.id), period_type="DAILY"
        )

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertGreater(len(dashboard["results"]), 0)
