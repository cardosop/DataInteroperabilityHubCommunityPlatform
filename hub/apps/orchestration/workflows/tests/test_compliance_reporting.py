"""
Unit tests for Compliance Reporting Workflow
"""
import uuid
import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, StepStatus
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.compliance_reporting import ComplianceReportingWorkflow
from hub.apps.governance.models import ComplianceReport, DataClassification, AccessRequest, AccessRequestStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class ComplianceReportingWorkflowUnitTest(TestCase):
    """Unit tests for compliance reporting workflow tasks"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant, _ = Tenant.objects.get_or_create(name=f"Test Tenant {uid}")
        self.user, _ = User.objects.get_or_create(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            defaults={"display_name": "Test User"}
        )
        
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        ComplianceReportingWorkflow.register_workflow(self.registry)
        ComplianceReportingWorkflow.register_tasks(self.engine)
        
        # Set up dates
        self.end_date = timezone.now()
        self.start_date = self.end_date - timedelta(days=30)

    def test_trigger_report_generation_task(self):
        """Test triggering report generation"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "report_type": "STANDARD",
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "triggered_by_id": str(self.user.id),
            "is_scheduled": False
        }
        
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="trigger_report_generation",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._trigger_report_generation_task(
            input_data, instance, step
        )
        
        self.assertIn("tenant_id", result)
        self.assertIn("regulation", result)
        self.assertEqual(result["regulation"], "GDPR")
        self.assertEqual(result["report_type"], "STANDARD")
        self.assertIn("start_date", result)
        self.assertIn("end_date", result)
        self.assertIn("state", result)

    def test_trigger_report_generation_task_invalid_regulation(self):
        """Test triggering report generation with invalid regulation"""
        input_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "INVALID",
            "report_type": "STANDARD"
        }
        
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id)
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="trigger_report_generation",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        with self.assertRaises(ValueError) as cm:
            ComplianceReportingWorkflow._trigger_report_generation_task(
                input_data, instance, step
            )
        self.assertIn("Invalid regulation", str(cm.exception))

    def test_trigger_report_generation_task_missing_tenant_id(self):
        """Test triggering report generation without tenant_id"""
        input_data = {
            "regulation": "GDPR"
        }
        
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data=input_data
        )
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=0,
            step_name="trigger_report_generation",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        with self.assertRaises(ValueError) as cm:
            ComplianceReportingWorkflow._trigger_report_generation_task(
                input_data, instance, step
            )
        self.assertIn("tenant_id is required", str(cm.exception))

    def test_collect_compliance_data_task(self):
        """Test collecting compliance data"""
        # Create test data BEFORE setting up workflow dates to ensure they're within range
        from hub.apps.jobs.models import Job, JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.assets.models import Asset
        
        test_asset, _ = Asset.objects.get_or_create(
            tenant=self.tenant,
            name="Test Asset",
            defaults={"description": "A test asset", "created_by": self.user}
        )
        
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(test_asset.id)
        )
        
        # Create compliance run with completed_at in the past relative to end_date
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=test_asset,
            job=job,
            regulations=["GDPR"],
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            completed_at=self.end_date - timedelta(days=1)
        )
        
        # Create classification - it will have created_at = now(), which should be within range
        # But to be safe, let's ensure it's created before end_date
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            asset=test_asset,
            field_name="test_field",
            category="PII",
            confidence_score=0.95
        )
        # Update created_at to be within the date range
        classification.created_at = self.end_date - timedelta(days=1)
        classification.save(update_fields=['created_at'])
        
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=test_asset,
            reason="Test access request",
            requested_access_type="READ"
        )
        # Update created_at to be within the date range
        access_request.created_at = self.end_date - timedelta(days=1)
        access_request.save(update_fields=['created_at'])
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={
                "tenant_id": str(self.tenant.id),
                "regulation": "GDPR",
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            },
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat()
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=1,
            step_name="collect_compliance_data",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._collect_compliance_data_task(
            input_data, instance, step
        )
        
        self.assertIn("compliance_runs_count", result)
        self.assertIn("classifications_count", result)
        self.assertIn("access_requests_count", result)
        self.assertEqual(result["data_collected"], True)
        self.assertGreaterEqual(result["compliance_runs_count"], 1)
        self.assertGreaterEqual(result["classifications_count"], 1)
        self.assertGreaterEqual(result["access_requests_count"], 1)

    def test_generate_report_task_gdpr(self):
        """Test generating GDPR report"""
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={
                "tenant_id": str(self.tenant.id),
                "regulation": "GDPR"
            },
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "report_type": "STANDARD",
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat()
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="generate_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._generate_report_task(
            input_data, instance, step
        )
        
        self.assertIn("report_data", result)
        self.assertIn("regulation", result)
        self.assertEqual(result["regulation"], "GDPR")
        self.assertIn("generated_at", result)
        
        report_data = result["report_data"]
        self.assertEqual(report_data["regulation"], "GDPR")
        self.assertIn("report_period", report_data)
        self.assertIn("compliance_runs", report_data)

    def test_generate_report_task_hipaa(self):
        """Test generating HIPAA report"""
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={
                "tenant_id": str(self.tenant.id),
                "regulation": "HIPAA"
            },
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "HIPAA",
            "report_type": "STANDARD",
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat()
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=2,
            step_name="generate_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._generate_report_task(
            input_data, instance, step
        )
        
        self.assertIn("report_data", result)
        self.assertEqual(result["regulation"], "HIPAA")
        report_data = result["report_data"]
        self.assertEqual(report_data["regulation"], "HIPAA")

    def test_validate_report_task_valid(self):
        """Test validating a valid report"""
        report_data = {
            "regulation": "GDPR",
            "report_period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            },
            "compliance_runs": {
                "total": 10,
                "passed": 8,
                "failed": 2
            },
            "pii_detection": {
                "total_classifications": 5
            },
            "data_subject_rights": {
                "access_requests": 3
            },
            "generated_at": timezone.now().isoformat()
        }
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "report_data": report_data,
            "regulation": "GDPR",
            "tenant_id": str(self.tenant.id),
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="validate_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._validate_report_task(
            input_data, instance, step
        )
        
        self.assertEqual(result["is_valid"], True)
        self.assertEqual(len(result["validation_errors"]), 0)

    def test_validate_report_task_invalid_missing_fields(self):
        """Test validating a report with missing required fields"""
        report_data = {
            "regulation": "GDPR"
            # Missing report_period and generated_at
        }
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "report_data": report_data,
            "regulation": "GDPR",
            "tenant_id": str(self.tenant.id),
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=3,
            step_name="validate_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        with self.assertRaises(ValueError) as cm:
            ComplianceReportingWorkflow._validate_report_task(
                input_data, instance, step
            )
        self.assertIn("Report validation failed", str(cm.exception))

    @patch('hub.apps.governance.report_scheduler.ReportScheduler.send_report_email')
    def test_send_report_task_with_recipients(self, mock_send_email):
        """Test sending report with email recipients"""
        mock_send_email.return_value = True
        
        report_data = {
            "regulation": "GDPR",
            "report_period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            }
        }
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "report_data": report_data,
            "regulation": "GDPR",
            "email_recipients": ["test@example.com"],
            "tenant_id": str(self.tenant.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="send_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._send_report_task(
            input_data, instance, step
        )
        
        self.assertIn("email_sent", result)
        self.assertEqual(result["email_sent"], True)
        self.assertIn("email_recipients", result)

    def test_send_report_task_no_recipients(self):
        """Test sending report without email recipients"""
        report_data = {
            "regulation": "GDPR",
            "report_period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            }
        }
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "report_data": report_data,
            "regulation": "GDPR",
            "email_recipients": []
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=4,
            step_name="send_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._send_report_task(
            input_data, instance, step
        )
        
        self.assertEqual(result["email_sent"], False)

    def test_store_report_task(self):
        """Test storing report"""
        report_data = {
            "regulation": "GDPR",
            "report_period": {
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat()
            }
        }
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        instance.state_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "report_type": "STANDARD",
            "report_data": report_data,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "triggered_by_id": str(self.user.id),
            "is_scheduled": False,
            "email_recipients": [],
            "email_sent": False
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=5,
            step_name="store_report",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._store_report_task(
            input_data, instance, step
        )
        
        self.assertIn("report_id", result)
        
        # Verify report was created
        report = ComplianceReport.objects.get(id=result["report_id"])
        self.assertEqual(report.tenant, self.tenant)
        self.assertEqual(report.regulation, "GDPR")
        self.assertEqual(report.report_type, "STANDARD")

    @patch('hub.apps.orchestration.workflows.compliance_reporting.create_audit_event')
    def test_audit_logging_task(self, mock_create_audit):
        """Test audit logging"""
        import uuid
        mock_audit_event = MagicMock(id=uuid.uuid4())
        mock_create_audit.return_value = mock_audit_event
        
        input_data = {}
        instance = self.engine.create_instance(
            workflow_name=ComplianceReportingWorkflow.WORKFLOW_NAME,
            input_data={},
            tenant_id=str(self.tenant.id)
        )
        import uuid
        report_id = str(uuid.uuid4())
        instance.state_data = {
            "tenant_id": str(self.tenant.id),
            "regulation": "GDPR",
            "report_id": report_id,
            "triggered_by_id": str(self.user.id)
        }
        instance.save()
        
        from hub.apps.orchestration.models import WorkflowStep
        step = WorkflowStep(
            workflow_instance=instance,
            step_index=6,
            step_name="audit_logging",
            step_type="task",
            status=StepStatus.PENDING
        )
        
        result = ComplianceReportingWorkflow._audit_logging_task(
            input_data, instance, step
        )
        
        self.assertIn("audit_event_id", result)
        mock_create_audit.assert_called_once()


class ComplianceReportingWorkflowIntegrationTest(TestCase):
    """Integration tests for compliance reporting workflow execution"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant, _ = Tenant.objects.get_or_create(name=f"Test Tenant {uid}")
        self.user, _ = User.objects.get_or_create(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            defaults={"display_name": "Test User"}
        )
        
        self.end_date = timezone.now()
        self.start_date = self.end_date - timedelta(days=30)

    @patch('hub.apps.governance.report_scheduler.ReportScheduler.send_report_email')
    @patch('hub.apps.audit.utils.create_audit_event')
    def test_execute_workflow_gdpr(self, mock_audit, mock_send_email):
        """Test executing complete GDPR workflow"""
        mock_send_email.return_value = True
        mock_audit.return_value = MagicMock(id="audit-123")
        
        # Create test data
        from hub.apps.jobs.models import Job, JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.assets.models import Asset
        
        test_asset, _ = Asset.objects.get_or_create(
            tenant=self.tenant,
            name="Test Asset",
            defaults={"description": "A test asset", "created_by": self.user}
        )
        
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(test_asset.id)
        )
        
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=test_asset,
            job=job,
            regulations=["GDPR"],
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            completed_at=self.end_date - timedelta(days=1)
        )
        
        result = ComplianceReportingWorkflow.execute(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            report_type="STANDARD",
            start_date=self.start_date,
            end_date=self.end_date,
            triggered_by_id=str(self.user.id),
            email_recipients=["test@example.com"]
        )
        
        self.assertTrue(result["success"])
        self.assertIn("workflow_instance_id", result)
        self.assertIn("report_id", result)
        
        # Verify report was created
        report = ComplianceReport.objects.get(id=result["report_id"])
        self.assertEqual(report.regulation, "GDPR")
        self.assertEqual(report.tenant, self.tenant)

    @patch('hub.apps.governance.report_scheduler.ReportScheduler.send_report_email')
    @patch('hub.apps.audit.utils.create_audit_event')
    def test_execute_workflow_hipaa(self, mock_audit, mock_send_email):
        """Test executing complete HIPAA workflow"""
        mock_send_email.return_value = True
        mock_audit.return_value = MagicMock(id="audit-123")
        
        result = ComplianceReportingWorkflow.execute(
            tenant_id=str(self.tenant.id),
            regulation="HIPAA",
            report_type="STANDARD",
            start_date=self.start_date,
            end_date=self.end_date,
            triggered_by_id=str(self.user.id)
        )
        
        self.assertTrue(result["success"])
        self.assertIn("report_id", result)
        
        report = ComplianceReport.objects.get(id=result["report_id"])
        self.assertEqual(report.regulation, "HIPAA")

    def test_execute_workflow_invalid_regulation(self):
        """Test executing workflow with invalid regulation"""
        with self.assertRaises(ValueError) as cm:
            ComplianceReportingWorkflow.execute(
                tenant_id=str(self.tenant.id),
                regulation="INVALID",
                report_type="STANDARD"
            )
        self.assertIn("Invalid regulation", str(cm.exception))


class ComplianceReportingWorkflowE2ETest(TestCase):
    """End-to-end tests for compliance reporting journey"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant, _ = Tenant.objects.get_or_create(name=f"Test Tenant {uid}")
        self.user, _ = User.objects.get_or_create(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            defaults={"display_name": "Test User"}
        )
        
        self.end_date = timezone.now()
        self.start_date = self.end_date - timedelta(days=30)

    def test_e2e_gdpr_reporting_journey(self):
        """Test complete GDPR reporting journey"""
        # Create comprehensive test data
        from hub.apps.jobs.models import Job, JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.assets.models import Asset
        
        test_asset, _ = Asset.objects.get_or_create(
            tenant=self.tenant,
            name="Test Asset",
            defaults={"description": "A test asset", "created_by": self.user}
        )
        
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(test_asset.id)
        )
        
        compliance_run = ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=test_asset,
            job=job,
            regulations=["GDPR"],
            status=ComplianceRunStatus.SUCCEEDED,
            overall_status="PASS",
            risk_level=RiskLevel.LOW,
            completed_at=self.end_date - timedelta(days=1)
        )
        
        classification = DataClassification.objects.create(
            tenant=self.tenant,
            asset=test_asset,
            field_name="email",
            category="PII",
            confidence_score=0.95
        )
        
        from hub.apps.assets.models import Asset
        test_asset, _ = Asset.objects.get_or_create(
            tenant=self.tenant,
            name="Test Asset",
            defaults={"description": "A test asset", "created_by": self.user}
        )
        
        access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=test_asset,
            reason="Test access request",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED
        )
        
        # Execute workflow
        result = ComplianceReportingWorkflow.execute(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            report_type="STANDARD",
            start_date=self.start_date,
            end_date=self.end_date,
            triggered_by_id=str(self.user.id),
            email_recipients=["test@example.com"]
        )
        
        # Verify workflow completed successfully
        self.assertTrue(result["success"])
        self.assertIn("report_id", result)
        
        # Verify report exists and contains expected data
        report = ComplianceReport.objects.get(id=result["report_id"])
        self.assertEqual(report.regulation, "GDPR")
        self.assertIn("compliance_runs", report.report_data)
        self.assertIn("pii_detection", report.report_data)
        self.assertIn("data_subject_rights", report.report_data)
        
        # Verify report data quality
        compliance_runs_data = report.report_data["compliance_runs"]
        self.assertGreaterEqual(compliance_runs_data["total"], 1)
        
        # Verify audit trail
        from hub.apps.audit.models import AuditEvent
        audit_events = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="COMPLIANCE_REPORT",
            resource_id=str(report.id)
        )
        self.assertGreaterEqual(audit_events.count(), 1)

    def test_e2e_scheduled_report_generation(self):
        """Test scheduled report generation journey"""
        # Execute workflow with scheduling
        result = ComplianceReportingWorkflow.execute(
            tenant_id=str(self.tenant.id),
            regulation="SOX",
            report_type="STANDARD",
            start_date=self.start_date,
            end_date=self.end_date,
            triggered_by_id=str(self.user.id),
            is_scheduled=True,
            schedule_frequency="MONTHLY",
            email_recipients=["admin@example.com"]
        )
        
        # Verify workflow completed
        self.assertTrue(result["success"])
        
        # Verify report is marked as scheduled
        report = ComplianceReport.objects.get(id=result["report_id"])
        self.assertTrue(report.scheduled)
        self.assertEqual(report.schedule_frequency, "MONTHLY")
        self.assertIn("admin@example.com", report.email_recipients)

