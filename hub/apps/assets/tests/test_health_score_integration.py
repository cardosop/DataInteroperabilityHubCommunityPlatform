"""
Integration tests for Asset Health Score

Tests for health score calculation in the context of asset workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.assets.health_score import AssetHealthScoreService
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AssetHealthScoreIntegrationTest(TestCase):
    """Integration tests for asset health score"""
    
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
        
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            view_count=100,
            download_count=50,
            popularity_score=80.0,
            created_by=self.user
        )
        
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=1,
            created_at=timezone.now() - timedelta(hours=12),  # Recent
            created_by=self.user
        )
    
    def test_health_score_workflow(self):
        """Test complete health score workflow"""
        # Create DQ run
        job = Job.objects.create(
            tenant=self.tenant,
            job_type=JobType.DQ_CHECK,
            status=JobStatus.COMPLETED,
            created_by=self.user
        )
        
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            job=job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=95.0,
            completed_at=timezone.now()
        )
        
        # Calculate health score
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        # Get breakdown
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        
        self.assertIn("total_score", breakdown)
        self.assertIn("components", breakdown)
        self.assertEqual(breakdown["total_score"], score)

