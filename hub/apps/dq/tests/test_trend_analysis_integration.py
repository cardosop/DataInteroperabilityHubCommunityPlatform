"""
Integration tests for DQ Trend Analysis

Tests for trend analysis in the context of DQ run workflows.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus, DQTrend
from hub.apps.dq.trend_analysis import TrendAnalyzer
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TrendAnalysisIntegrationTest(TestCase):
    """Integration tests for trend analysis"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
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
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    def test_trend_analysis_workflow(self):
        """Test complete trend analysis workflow"""
        # Create DQ runs over time with improving trend
        for i in range(20):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=self.dataset.id,
                created_by=self.user,
            )

            DQRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                dataset=self.dataset,
                job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=70.0 + (i * 1.5),  # Improving trend
                completed_at=timezone.now() - timedelta(days=20 - i),
            )

        # Calculate trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            period_type="DAILY",
            periods=20,
        )

        # Save trends
        for trend in trends:
            trend.save()

        # Verify trends were created
        saved_trends = DQTrend.objects.filter(tenant=self.tenant, asset=self.asset)
        self.assertGreater(saved_trends.count(), 0)

        # Verify trend details
        trend = saved_trends.first()
        self.assertEqual(trend.metric_type, "quality_score")
        self.assertIsNotNone(trend.current_value)
        self.assertIsNotNone(trend.direction)
        self.assertIsNotNone(trend.period_start)
        self.assertIsNotNone(trend.period_end)

    def test_trend_visualization_workflow(self):
        """Test trend visualization workflow"""
        # Create DQ runs
        for i in range(10):
            job = Job.objects.create(
                tenant=self.tenant,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=self.dataset.id,
                created_by=self.user,
            )

            DQRun.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                dataset=self.dataset,
                job=job,
                profile_key="intake_basic_gx",
                engine=DQEngine.GREAT_EXPECTATIONS,
                status=DQRunStatus.SUCCEEDED,
                overall_status="PASS",
                quality_score=90.0,
                completed_at=timezone.now() - timedelta(days=10 - i),
            )

        # Calculate and save trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        for trend in trends:
            trend.save()

        # Generate visualizations
        json_viz = TrendAnalyzer.get_trend_visualization(trends, format="json")
        chart_viz = TrendAnalyzer.get_trend_visualization(trends, format="chart_data")

        # Verify visualizations
        self.assertIsInstance(json_viz, list)
        self.assertGreaterEqual(len(json_viz), 1)

        self.assertIsInstance(chart_viz, dict)
        self.assertIn("labels", chart_viz)
        self.assertIn("datasets", chart_viz)
