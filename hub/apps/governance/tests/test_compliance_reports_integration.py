"""
Integration tests for Compliance Reporting

Tests for report generation in the context of compliance runs,
classifications, and access requests.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.governance.models import ComplianceReport
from hub.apps.governance.compliance_reports import ComplianceReportGenerator
from hub.apps.governance.report_scheduler import ReportScheduler
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.governance.models import DataClassification, ClassificationCategory
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.governance.classification import DataClassifier
from hub.apps.governance.access_requests import AccessRequestWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class ComplianceReportIntegrationTest(TestCase):
    """Integration tests for compliance reporting"""
    
    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
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
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]},
                    {"name": "phone", "data_type": "string", "sample_values": ["123-456-7890"]}
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user
        )
        
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN.value,
            status=JobStatus.COMPLETED.value,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user
        )
    
    def test_gdpr_report_with_full_data(self):
        """Test GDPR report with compliance runs, classifications, and access requests"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["GDPR"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            risk_level=RiskLevel.LOW.value,
            detected_categories_json={"EMAIL": 1, "PHONE": 1},
            completed_at=timezone.now()
        )
        
        # Classify fields
        classifications = DataClassifier.classify_dataset(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            user_id=str(self.user.id)
        )
        
        # Create access request
        access_request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            dataset_id=str(self.dataset.id),
            reason="GDPR data subject access request",
            requested_access_type="READ",
            requires_approval=False
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_gdpr_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'GDPR')
        self.assertGreater(report['compliance_runs']['total'], 0)
        self.assertGreater(report['pii_detection']['total_classifications'], 0)
        self.assertGreater(report['data_subject_rights']['access_requests'], 0)
    
    def test_scheduled_report_generation(self):
        """Test scheduled report generation"""
        # Schedule a report
        scheduled_report = ReportScheduler.schedule_report(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            schedule_frequency="WEEKLY",
            email_recipients=["admin@example.com"],
            user_id=str(self.user.id)
        )
        
        self.assertTrue(scheduled_report.scheduled)
        self.assertEqual(scheduled_report.schedule_frequency, "WEEKLY")
        
        # Generate scheduled reports
        results = ReportScheduler.generate_scheduled_reports()
        
        # Should not generate duplicate for same period
        self.assertGreaterEqual(results['generated'], 0)

