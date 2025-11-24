"""
Unit tests for ComplianceRun model.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import Job, JobType, JobStatus

User = get_user_model()


class ComplianceRunModelTest(TestCase):
    """Test ComplianceRun model"""
    
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
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.PENDING,
            resource_type="ASSET",
            resource_id=self.asset.id,
        )
    
    def test_create_compliance_run(self):
        """Test compliance run creation"""
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            status=ComplianceRunStatus.PENDING,
        )
        
        self.assertEqual(compliance_run.tenant, self.tenant)
        self.assertEqual(compliance_run.asset, self.asset)
        self.assertEqual(compliance_run.job, self.job)
        self.assertEqual(compliance_run.status, ComplianceRunStatus.PENDING)

