"""
Unit tests for DQRun model.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.jobs.models import Job, JobType, JobStatus

User = get_user_model()


class DQRunModelTest(TestCase):
    """Test DQRun model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
        )
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
        )
    
    def test_create_dq_run(self):
        """Test DQ run creation"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic",
            status=DQRunStatus.PENDING,
        )
        
        self.assertEqual(dq_run.tenant, self.tenant)
        self.assertEqual(dq_run.asset, self.asset)
        self.assertEqual(dq_run.job, self.job)
        self.assertEqual(dq_run.engine, DQEngine.GREAT_EXPECTATIONS)
        self.assertEqual(dq_run.profile_key, "intake_basic")
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

