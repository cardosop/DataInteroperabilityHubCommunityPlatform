"""
Unit tests for Compliance Reporting

Tests for GDPR, HIPAA, SOX, LGPD, CCPA report generation,
scheduled reports, and email delivery.
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
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobType, JobStatus


pytestmark = pytest.mark.django_db(transaction=True)


class ComplianceReportGeneratorTest(TestCase):
    """Test ComplianceReportGenerator"""
    
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
            schema_json={"fields": [{"name": "email", "type": "string"}]},
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
    
    def test_generate_gdpr_report(self):
        """Test GDPR report generation"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["GDPR"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            risk_level=RiskLevel.LOW.value,
            detected_categories_json={"EMAIL": 1},
            completed_at=timezone.now()
        )
        
        # Create classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="email",
            category=ClassificationCategory.PII.value,
            confidence_score=0.95,
            created_by=self.user
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_gdpr_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'GDPR')
        self.assertIn('compliance_runs', report)
        self.assertIn('pii_detection', report)
        self.assertIn('data_subject_rights', report)
        self.assertGreater(report['compliance_runs']['total'], 0)
    
    def test_generate_hipaa_report(self):
        """Test HIPAA report generation"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["HIPAA"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            completed_at=timezone.now()
        )
        
        # Create PHI classification
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            field_name="patient_id",
            category=ClassificationCategory.PHI.value,
            confidence_score=0.90,
            created_by=self.user
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_hipaa_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'HIPAA')
        self.assertIn('compliance_runs', report)
        self.assertIn('phi_detection', report)
        self.assertIn('access_controls', report)
    
    def test_generate_sox_report(self):
        """Test SOX report generation"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["SOX"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            completed_at=timezone.now()
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_sox_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'SOX')
        self.assertIn('compliance_runs', report)
        self.assertIn('financial_data', report)
    
    def test_generate_lgpd_report(self):
        """Test LGPD report generation"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["LGPD"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            completed_at=timezone.now()
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_lgpd_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'LGPD')
        self.assertIn('compliance_runs', report)
        self.assertIn('pii_detection', report)
        self.assertIn('data_subject_rights', report)
    
    def test_generate_ccpa_report(self):
        """Test CCPA report generation"""
        # Create compliance run
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["CCPA"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            completed_at=timezone.now()
        )
        
        # Generate report
        report = ComplianceReportGenerator.generate_ccpa_report(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(report['regulation'], 'CCPA')
        self.assertIn('compliance_runs', report)
        self.assertIn('pii_detection', report)
        self.assertIn('consumer_rights', report)
    
    def test_generate_and_save_report(self):
        """Test generating and saving a report"""
        report = ReportScheduler.generate_and_save_report(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            report_type="STANDARD",
            user_id=str(self.user.id)
        )
        
        self.assertIsNotNone(report)
        self.assertEqual(report.regulation, "GDPR")
        self.assertEqual(report.report_type, "STANDARD")
        self.assertIn('compliance_runs', report.report_data)
    
    def test_schedule_report(self):
        """Test scheduling a report"""
        report = ReportScheduler.schedule_report(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            schedule_frequency="WEEKLY",
            email_recipients=["admin@example.com"],
            user_id=str(self.user.id)
        )
        
        self.assertTrue(report.scheduled)
        self.assertEqual(report.schedule_frequency, "WEEKLY")
        self.assertIn("admin@example.com", report.email_recipients)

