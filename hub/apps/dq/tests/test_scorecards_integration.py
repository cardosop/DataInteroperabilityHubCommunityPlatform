"""
Integration tests for DQ Scorecards

Tests for scorecards in the context of DQ workflows.
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


class DQScorecardsIntegrationTest(TestCase):
    """Integration tests for DQ scorecards"""
    
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
    
    def test_scorecard_workflow(self):
        """Test complete scorecard workflow"""
        # Create DQ runs
        for i in range(10):
            job = Job.objects.create(
                tenant=self.tenant,
                job_type=JobType.DQ_CHECK,
                status=JobStatus.COMPLETED,
                created_by=self.user
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
                quality_score=85.0 + (i * 1.0),
                completed_at=timezone.now() - timedelta(days=10-i)
            )
        
        # Create trends
        for i in range(5):
            DQTrend.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                metric_type="quality_score",
                period_start=timezone.now() - timedelta(days=5-i),
                period_end=timezone.now() - timedelta(days=4-i),
                period_type="DAILY",
                current_value=85.0 + (i * 1.0),
                previous_value=84.0 + (i * 1.0),
                change_amount=1.0,
                change_percent=1.2,
                direction=DQTrendDirection.IMPROVING
            )
        
        # Get executive dashboard
        dashboard = DQScorecardService.get_executive_dashboard(
            str(self.tenant.id),
            days=30
        )
        
        # Verify dashboard structure
        self.assertIn("summary", dashboard)
        self.assertIn("score_distribution", dashboard)
        self.assertIn("trend_summary", dashboard)
        self.assertEqual(dashboard["summary"]["total_runs"], 10)
        
        # Get asset scorecard
        scorecard = DQScorecardService.get_asset_scorecard(
            str(self.asset.id),
            str(self.tenant.id),
            days=30
        )
        
        # Verify scorecard structure
        self.assertIn("metrics", scorecard)
        self.assertIn("recent_runs", scorecard)
        self.assertIn("trends", scorecard)
        self.assertEqual(scorecard["metrics"]["total_runs"], 10)
        
        # Test drill-down
        drill_down = DQScorecardService.drill_down(
            str(self.tenant.id),
            asset_id=str(self.asset.id),
            days=30
        )
        
        self.assertIn("metrics", drill_down)
        self.assertIn("run_history", drill_down)

