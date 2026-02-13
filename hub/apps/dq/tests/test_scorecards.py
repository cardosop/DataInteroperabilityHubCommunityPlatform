"""
Unit tests for DQ Scorecards

Tests for executive dashboards and drill-down capabilities.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine, DQTrend, DQTrendDirection
from hub.apps.dq.scorecards import DQScorecardService
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class DQScorecardServiceTest(TestCase):
    """Test DQScorecardService"""
    
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
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_by=self.user
        )
    
    def _create_dq_run(self, quality_score: float, overall_status: str = "PASS", completed_at=None) -> DQRun:
        """Helper to create DQ run"""
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=self.dataset.id,
            created_by=self.user
        )
        
        return DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status=overall_status,
            quality_score=quality_score,
            completed_at=completed_at or timezone.now()
        )
    
    def test_get_executive_dashboard(self):
        """Test executive dashboard generation"""
        # Create DQ runs with various scores
        self._create_dq_run(95.0, "PASS")
        self._create_dq_run(85.0, "PASS")
        self._create_dq_run(75.0, "WARN")
        self._create_dq_run(65.0, "FAIL")
        
        # Get dashboard
        dashboard = DQScorecardService.get_executive_dashboard(
            str(self.tenant.id),
            days=30
        )
        
        self.assertIn("summary", dashboard)
        self.assertIn("score_distribution", dashboard)
        self.assertIn("top_issues", dashboard)
        self.assertIn("trend_summary", dashboard)
        self.assertEqual(dashboard["summary"]["total_runs"], 4)
    
    def test_get_executive_dashboard_score_distribution(self):
        """Test score distribution calculation"""
        # Create runs in different score ranges
        self._create_dq_run(95.0)  # Excellent
        self._create_dq_run(85.0)  # Good
        self._create_dq_run(75.0)  # Fair
        self._create_dq_run(65.0)  # Poor
        self._create_dq_run(50.0)  # Critical
        
        dashboard = DQScorecardService.get_executive_dashboard(
            str(self.tenant.id),
            days=30
        )
        
        distribution = dashboard["score_distribution"]
        self.assertEqual(distribution["excellent"], 1)
        self.assertEqual(distribution["good"], 1)
        self.assertEqual(distribution["fair"], 1)
        self.assertEqual(distribution["poor"], 1)
        self.assertEqual(distribution["critical"], 1)
    
    def test_get_executive_dashboard_pass_fail_rates(self):
        """Test pass/fail rate calculation"""
        # Create runs with different statuses
        for _ in range(5):
            self._create_dq_run(90.0, "PASS")
        for _ in range(2):
            self._create_dq_run(60.0, "FAIL")
        for _ in range(1):
            self._create_dq_run(75.0, "WARN")
        
        dashboard = DQScorecardService.get_executive_dashboard(
            str(self.tenant.id),
            days=30
        )
        
        summary = dashboard["summary"]
        self.assertEqual(summary["total_runs"], 8)
        self.assertAlmostEqual(summary["pass_rate"], 62.5, places=1)
        self.assertAlmostEqual(summary["fail_rate"], 25.0, places=1)
    
    def test_get_asset_scorecard(self):
        """Test asset scorecard generation"""
        # Create DQ runs for asset
        self._create_dq_run(90.0, "PASS")
        self._create_dq_run(85.0, "PASS")
        self._create_dq_run(70.0, "FAIL")
        
        # Get scorecard
        scorecard = DQScorecardService.get_asset_scorecard(
            str(self.asset.id),
            str(self.tenant.id),
            days=30
        )
        
        self.assertIn("asset_id", scorecard)
        self.assertIn("metrics", scorecard)
        self.assertIn("recent_runs", scorecard)
        self.assertIn("trends", scorecard)
        self.assertEqual(scorecard["metrics"]["total_runs"], 3)
    
    def test_get_asset_scorecard_recent_runs(self):
        """Test recent runs in asset scorecard"""
        # Create runs at different times
        now = timezone.now()
        self._create_dq_run(90.0, completed_at=now - timedelta(days=1))
        self._create_dq_run(85.0, completed_at=now - timedelta(days=2))
        self._create_dq_run(80.0, completed_at=now - timedelta(days=3))
        
        scorecard = DQScorecardService.get_asset_scorecard(
            str(self.asset.id),
            str(self.tenant.id),
            days=30
        )
        
        recent_runs = scorecard["recent_runs"]
        self.assertLessEqual(len(recent_runs), 10)
        # Should be ordered by completed_at descending
        if len(recent_runs) > 1:
            self.assertGreaterEqual(
                recent_runs[0]["completed_at"],
                recent_runs[1]["completed_at"]
            )
    
    def test_drill_down_asset(self):
        """Test drill-down by asset"""
        # Create DQ runs
        self._create_dq_run(90.0)
        self._create_dq_run(85.0)
        
        # Drill down
        drill_down = DQScorecardService.drill_down(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        self.assertIn("filters", drill_down)
        self.assertIn("metrics", drill_down)
        self.assertIn("run_history", drill_down)
        self.assertEqual(drill_down["filters"]["asset_id"], str(self.asset.id))
        self.assertEqual(drill_down["metrics"]["total_runs"], 2)
    
    def test_drill_down_dataset(self):
        """Test drill-down by dataset"""
        # Create DQ runs
        self._create_dq_run(90.0)
        
        # Drill down
        drill_down = DQScorecardService.drill_down(
            str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            days=30
        )
        
        self.assertEqual(drill_down["filters"]["dataset_id"], str(self.dataset.id))
        self.assertEqual(drill_down["metrics"]["total_runs"], 1)
    
    def test_drill_down_metrics(self):
        """Test drill-down metrics calculation"""
        # Create runs with various scores
        self._create_dq_run(95.0)
        self._create_dq_run(85.0)
        self._create_dq_run(75.0)
        
        drill_down = DQScorecardService.drill_down(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        metrics = drill_down["metrics"]
        self.assertEqual(metrics["total_runs"], 3)
        self.assertAlmostEqual(metrics["avg_quality_score"], 85.0, places=1)
        self.assertEqual(metrics["min_quality_score"], 75.0)
        self.assertEqual(metrics["max_quality_score"], 95.0)

