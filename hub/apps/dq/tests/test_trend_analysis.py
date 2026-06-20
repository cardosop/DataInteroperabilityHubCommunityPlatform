"""
Unit tests for DQ Trend Analysis

Tests for quality trend tracking over time.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus, DQTrendDirection
from hub.apps.dq.trend_analysis import TrendAnalyzer
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TrendAnalyzerTest(TestCase):
    """Test TrendAnalyzer"""

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

    def _create_dq_run(self, quality_score: float, completed_at: timezone.datetime) -> DQRun:
        """Helper to create DQ run"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=quality_score,
            completed_at=completed_at,
        )

    def test_calculate_trend_improving(self):
        """Test trend calculation for improving quality"""
        # Create runs with improving scores
        for i in range(10):
            self._create_dq_run(
                quality_score=70.0 + (i * 2.0),  # Improving trend
                completed_at=timezone.now() - timedelta(days=10 - i),
            )

        # Calculate trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        self.assertGreaterEqual(len(trends), 1)
        # Should have improving trends AND ZERO degrading trends
        improving_trends = [t for t in trends if t.direction == DQTrendDirection.IMPROVING]
        self.assertGreaterEqual(len(improving_trends), 1)
        degrading_trends = [t for t in trends if t.direction == DQTrendDirection.DEGRADING]
        self.assertEqual(
            len(degrading_trends), 0, "Improving data must produce ZERO degrading trends"
        )

    def test_calculate_trend_degrading(self):
        """Test trend calculation for degrading quality"""
        # Create runs with degrading scores
        for i in range(10):
            self._create_dq_run(
                quality_score=95.0 - (i * 2.0),  # Degrading trend
                completed_at=timezone.now() - timedelta(days=10 - i),
            )

        # Calculate trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        self.assertGreaterEqual(len(trends), 1)
        # Should have degrading trends AND ZERO improving trends
        degrading_trends = [t for t in trends if t.direction == DQTrendDirection.DEGRADING]
        self.assertGreaterEqual(len(degrading_trends), 1)
        improving_trends = [t for t in trends if t.direction == DQTrendDirection.IMPROVING]
        self.assertEqual(
            len(improving_trends), 0, "Degrading data must produce ZERO improving trends"
        )

    def test_calculate_trend_stable(self):
        """Test trend calculation for stable quality"""
        # Create runs with stable scores
        for i in range(10):
            self._create_dq_run(
                quality_score=90.0,  # Stable
                completed_at=timezone.now() - timedelta(days=10 - i),
            )

        # Calculate trends
        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        self.assertGreaterEqual(len(trends), 1)
        # Should have stable trends AND ZERO directional trends
        stable_trends = [t for t in trends if t.direction == DQTrendDirection.STABLE]
        self.assertGreaterEqual(len(stable_trends), 1)
        directional_trends = [
            t
            for t in trends
            if t.direction in (DQTrendDirection.IMPROVING, DQTrendDirection.DEGRADING)
        ]
        self.assertEqual(
            len(directional_trends),
            0,
            "Stable data must produce ZERO improving or degrading trends",
        )

    def test_trend_change_calculation(self):
        """Test trend change amount and percent calculation"""
        # Create runs with changing scores
        for i in range(5):
            self._create_dq_run(
                quality_score=80.0 + (i * 5.0), completed_at=timezone.now() - timedelta(days=5 - i)
            )

        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        # Check that changes are calculated
        for trend in trends:
            if trend.previous_value is not None:
                self.assertIsNotNone(trend.change_amount)
                self.assertIsNotNone(trend.change_percent)

    def test_trend_forecast(self):
        """Test trend forecasting"""
        # Create runs with consistent trend
        for i in range(10):
            self._create_dq_run(
                quality_score=80.0 + (i * 2.0), completed_at=timezone.now() - timedelta(days=10 - i)
            )

        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        # Check that forecasts are calculated
        forecasts = [t for t in trends if t.forecast_value is not None]
        self.assertGreaterEqual(len(forecasts), 1)

    def test_trend_visualization_json(self):
        """Test trend visualization in JSON format"""
        # Create runs
        for i in range(5):
            self._create_dq_run(
                quality_score=90.0, completed_at=timezone.now() - timedelta(days=5 - i)
            )

        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        visualization = TrendAnalyzer.get_trend_visualization(trends, format="json")

        self.assertIsInstance(visualization, list)
        self.assertGreaterEqual(len(visualization), 1)
        self.assertIn("current_value", visualization[0])
        self.assertIn("direction", visualization[0])

    def test_trend_visualization_chart_data(self):
        """Test trend visualization in chart data format"""
        # Create runs
        for i in range(5):
            self._create_dq_run(
                quality_score=90.0, completed_at=timezone.now() - timedelta(days=5 - i)
            )

        trends = TrendAnalyzer.calculate_trend(
            asset_id=str(self.asset.id), tenant_id=str(self.tenant.id), period_type="DAILY"
        )

        visualization = TrendAnalyzer.get_trend_visualization(trends, format="chart_data")

        self.assertIsInstance(visualization, dict)
        self.assertIn("labels", visualization)
        self.assertIn("datasets", visualization)
        self.assertGreaterEqual(len(visualization["labels"]), 1)
