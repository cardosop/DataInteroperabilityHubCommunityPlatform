"""
Unit tests for Asset Health Score

Tests for health score calculation combining DQ, compliance, freshness, and usage.
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


class AssetHealthScoreServiceTest(TestCase):
    """Test AssetHealthScoreService"""
    
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
    
    def test_calculate_health_score(self):
        """Test health score calculation"""
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.health_score, score)
    
    def test_calculate_health_score_dq_component(self):
        """Test DQ component of health score"""
        # Test PASS status
        self.asset.dq_status = DQStatus.PASS
        self.asset.save()
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreater(score, 50.0)  # Should be high with PASS
        
        # Test FAIL status
        self.asset.dq_status = DQStatus.FAIL
        self.asset.save()
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertLess(score, 80.0)  # Should be lower with FAIL
    
    def test_calculate_health_score_compliance_component(self):
        """Test compliance component of health score"""
        # Test PASS status
        self.asset.compliance_status = ComplianceStatus.PASS
        self.asset.save()
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertGreater(score, 50.0)
        
        # Test FAIL status
        self.asset.compliance_status = ComplianceStatus.FAIL
        self.asset.save()
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        self.assertLess(score, 80.0)
    
    def test_calculate_health_score_with_dq_run(self):
        """Test health score with DQ run quality score"""
        # Create DQ run with quality score
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
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        
        # Should incorporate quality score
        self.assertGreater(score, 50.0)
    
    def test_calculate_health_score_freshness_component(self):
        """Test freshness component of health score"""
        # Create recent dataset
        recent_dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            format="CSV",
            version=2,
            created_at=timezone.now() - timedelta(hours=12),  # Recent
            created_by=self.user
        )
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        
        # Should have good freshness score
        self.assertGreater(score, 50.0)
    
    def test_calculate_health_score_usage_component(self):
        """Test usage component of health score"""
        # Set high usage
        self.asset.view_count = 200
        self.asset.download_count = 100
        self.asset.popularity_score = 90.0
        self.asset.save()
        
        score = AssetHealthScoreService.calculate_health_score(self.asset)
        
        # Should incorporate usage score
        self.assertGreater(score, 50.0)
    
    def test_get_health_score_breakdown(self):
        """Test health score breakdown"""
        breakdown = AssetHealthScoreService.get_health_score_breakdown(self.asset)
        
        self.assertIn("total_score", breakdown)
        self.assertIn("components", breakdown)
        self.assertIn("dq", breakdown["components"])
        self.assertIn("compliance", breakdown["components"])
        self.assertIn("freshness", breakdown["components"])
        self.assertIn("usage", breakdown["components"])
        
        # Verify component structure
        dq_component = breakdown["components"]["dq"]
        self.assertIn("score", dq_component)
        self.assertIn("weight", dq_component)
        self.assertIn("weighted_score", dq_component)
    
    def test_recalculate_all_health_scores(self):
        """Test recalculating all health scores"""
        # Create multiple assets
        for i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"asset-{i}",
                name=f"Asset {i}",
                status=AssetStatus.ACTIVE,
                dq_status=DQStatus.PASS,
                compliance_status=ComplianceStatus.PASS,
                created_by=self.user
            )
        
        count = AssetHealthScoreService.recalculate_all_health_scores(str(self.tenant.id))
        
        self.assertEqual(count, 6)  # 5 new + 1 existing
        
        # Verify scores were calculated
        assets = Asset.objects.filter(tenant=self.tenant)
        for asset in assets:
            self.assertIsNotNone(asset.health_score)

