"""
Compliance Reporting Workflow

Orchestrates compliance report generation, including:
- Trigger report generation (scheduled/manual)
- Collect compliance data (classifications, access logs, etc.)
- Generate report (GDPR/HIPAA/SOX/etc.)
- Validate report completeness
- Send report (email/API)
- Store report for audit
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.compliance.business_rules import ComplianceBusinessRules
from hub.apps.compliance.models import ComplianceRun
from hub.apps.governance.compliance_reports import ComplianceReportGenerator
from hub.apps.governance.models import AccessRequest, ComplianceReport, DataClassification
from hub.apps.governance.report_scheduler import ReportScheduler
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine

logger = structlog.get_logger(__name__)


class ComplianceReportingWorkflow:
    """
    Compliance reporting workflow orchestrator.

    Orchestrates the complete compliance reporting process:
    1. Trigger report generation (scheduled/manual)
    2. Collect compliance data (classifications, access logs, etc.)
    3. Generate report (GDPR/HIPAA/SOX/etc.)
    4. Validate report completeness
    5. Send report (email/API)
    6. Store report for audit
    """

    WORKFLOW_NAME = "compliance_reporting"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the compliance reporting workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "trigger_report_generation",
                    "type": "task",
                    "task": "compliance_reporting.trigger_report_generation",
                },
                {
                    "name": "collect_compliance_data",
                    "type": "task",
                    "task": "compliance_reporting.collect_compliance_data",
                },
                {
                    "name": "generate_report",
                    "type": "task",
                    "task": "compliance_reporting.generate_report",
                },
                {
                    "name": "validate_report",
                    "type": "task",
                    "task": "compliance_reporting.validate_report",
                },
                {"name": "send_report", "type": "task", "task": "compliance_reporting.send_report"},
                {
                    "name": "store_report",
                    "type": "task",
                    "task": "compliance_reporting.store_report",
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "compliance_reporting.audit_logging",
                },
            ],
            "compensation": {"enabled": True},
        }
        registry.register_workflow(cls.WORKFLOW_NAME, workflow_dsl)

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "compliance_reporting.trigger_report_generation", cls._trigger_report_generation_task
        )
        engine.register_task(
            "compliance_reporting.collect_compliance_data", cls._collect_compliance_data_task
        )
        engine.register_task("compliance_reporting.generate_report", cls._generate_report_task)
        engine.register_task("compliance_reporting.validate_report", cls._validate_report_task)
        engine.register_task("compliance_reporting.send_report", cls._send_report_task)
        engine.register_task("compliance_reporting.store_report", cls._store_report_task)
        engine.register_task("compliance_reporting.audit_logging", cls._audit_logging_task)

    @staticmethod
    def _trigger_report_generation_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Trigger report generation (scheduled/manual).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with trigger details
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        regulation = input_data.get("regulation")
        report_type = input_data.get("report_type", "STANDARD")
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")
        triggered_by_id = input_data.get("triggered_by_id") or instance.created_by_id
        is_scheduled = input_data.get("is_scheduled", False)
        schedule_frequency = input_data.get("schedule_frequency")
        email_recipients = input_data.get("email_recipients", [])

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not regulation:
            raise ValueError("regulation is required")
        if regulation not in ["GDPR", "HIPAA", "SOX", "LGPD", "CCPA"]:
            raise ValueError(
                f"Invalid regulation: {regulation}. Must be one of: GDPR, HIPAA, SOX, LGPD, CCPA"
            )

        # Set default dates if not provided
        if not end_date:
            end_date = timezone.now()
        else:
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        logger.info(
            "Report generation triggered",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            regulation=regulation,
            report_type=report_type,
            is_scheduled=is_scheduled,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        return {
            "tenant_id": tenant_id,
            "regulation": regulation,
            "report_type": report_type,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "triggered_by_id": triggered_by_id,
            "is_scheduled": is_scheduled,
            "schedule_frequency": schedule_frequency,
            "email_recipients": email_recipients,
            "state": {
                "tenant_id": tenant_id,
                "regulation": regulation,
                "report_type": report_type,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "triggered_by_id": triggered_by_id,
                "is_scheduled": is_scheduled,
                "schedule_frequency": schedule_frequency,
                "email_recipients": email_recipients,
            },
        }

    @staticmethod
    def _collect_compliance_data_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Collect compliance data (classifications, access logs, etc.).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with collected data summary
        """
        tenant_id = instance.state_data.get("tenant_id")
        regulation = instance.state_data.get("regulation")
        start_date_str = instance.state_data.get("start_date")
        end_date_str = instance.state_data.get("end_date")

        if not tenant_id or not regulation:
            raise ValueError("tenant_id and regulation are required")

        # Parse dates
        start_date = (
            datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            if start_date_str
            else None
        )
        end_date = (
            datetime.fromisoformat(end_date_str.replace("Z", "+00:00")) if end_date_str else None
        )

        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")

        # Collect compliance runs
        compliance_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            regulations__contains=[regulation],
            completed_at__gte=start_date,
            completed_at__lte=end_date,
        )

        # Collect data classifications
        classifications = DataClassification.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Collect access requests
        access_requests = AccessRequest.objects.filter(
            tenant_id=tenant_id, created_at__gte=start_date, created_at__lte=end_date
        )

        # Collect summary statistics
        compliance_runs_count = compliance_runs.count()
        classifications_count = classifications.count()
        access_requests_count = access_requests.count()

        logger.info(
            "Compliance data collected",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            regulation=regulation,
            compliance_runs_count=compliance_runs_count,
            classifications_count=classifications_count,
            access_requests_count=access_requests_count,
        )

        return {
            "compliance_runs_count": compliance_runs_count,
            "classifications_count": classifications_count,
            "access_requests_count": access_requests_count,
            "data_collected": True,
            "state": {
                "compliance_runs_count": compliance_runs_count,
                "classifications_count": classifications_count,
                "access_requests_count": access_requests_count,
                "data_collected": True,
            },
        }

    @staticmethod
    def _generate_report_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Generate report (GDPR/HIPAA/SOX/etc.).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with generated report data
        """
        tenant_id = instance.state_data.get("tenant_id")
        regulation = instance.state_data.get("regulation")
        report_type = instance.state_data.get("report_type", "STANDARD")
        start_date_str = instance.state_data.get("start_date")
        end_date_str = instance.state_data.get("end_date")

        if not tenant_id or not regulation:
            raise ValueError("tenant_id and regulation are required")

        # Parse dates
        start_date = (
            datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            if start_date_str
            else None
        )
        end_date = (
            datetime.fromisoformat(end_date_str.replace("Z", "+00:00")) if end_date_str else None
        )

        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")

        # Generate report based on regulation
        if regulation == "GDPR":
            report_data = ComplianceReportGenerator.generate_gdpr_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "HIPAA":
            report_data = ComplianceReportGenerator.generate_hipaa_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "SOX":
            report_data = ComplianceReportGenerator.generate_sox_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "LGPD":
            report_data = ComplianceReportGenerator.generate_lgpd_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "CCPA":
            report_data = ComplianceReportGenerator.generate_ccpa_report(
                tenant_id, start_date, end_date
            )
        else:
            raise ValueError(f"Unknown regulation: {regulation}")

        logger.info(
            "Report generated",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            regulation=regulation,
            report_type=report_type,
            report_size=len(str(report_data)),
        )

        return {
            "report_data": report_data,
            "regulation": regulation,
            "report_type": report_type,
            "generated_at": timezone.now().isoformat(),
            "state": {
                "report_data": report_data,
                "regulation": regulation,
                "report_type": report_type,
                "generated_at": timezone.now().isoformat(),
            },
        }

    @staticmethod
    def _validate_report_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Validate report completeness.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        report_data = instance.state_data.get("report_data")
        regulation = instance.state_data.get("regulation")

        if not report_data:
            raise ValueError("report_data is required")
        if not regulation:
            raise ValueError("regulation is required")

        # Validate report using ComplianceBusinessRules
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        tenant_id = instance.state_data.get("tenant_id")
        triggered_by_id = instance.state_data.get("triggered_by_id") or instance.created_by_id

        tenant = Tenant.objects.get(id=tenant_id) if tenant_id else None
        user = User.objects.get(id=triggered_by_id) if triggered_by_id else None

        compliance_rules = ComplianceBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(triggered_by_id) if triggered_by_id else None,
        )

        # Validate report structure using business rules
        # Note: ComplianceBusinessRules validates compliance runs, but we can use it for report validation context
        # For report validation, we'll do manual validation but use business rules for tenant context validation
        tenant_context_result = compliance_rules.validate(
            tenant=tenant, user=user, validation_type="tenant_context"
        )

        validation_errors = []
        validation_warnings = []

        # Add business rules validation errors/warnings
        if not tenant_context_result.is_valid:
            validation_errors.extend(tenant_context_result.errors)
        validation_warnings.extend(tenant_context_result.warnings)

        # Check required fields
        required_fields = ["regulation", "report_period", "generated_at"]
        for field in required_fields:
            if field not in report_data:
                validation_errors.append(f"Missing required field: {field}")

        # Check report period structure
        if "report_period" in report_data:
            period = report_data["report_period"]
            if "start_date" not in period or "end_date" not in period:
                validation_errors.append("report_period missing start_date or end_date")

        # Check compliance_runs section
        if "compliance_runs" not in report_data:
            validation_warnings.append("compliance_runs section missing")
        elif "total" not in report_data["compliance_runs"]:
            validation_warnings.append("compliance_runs.total missing")

        # Regulation-specific validation
        if regulation == "GDPR":
            if "pii_detection" not in report_data:
                validation_warnings.append("GDPR report missing pii_detection section")
            if "data_subject_rights" not in report_data:
                validation_warnings.append("GDPR report missing data_subject_rights section")
        elif regulation == "HIPAA":
            if "phi_detection" not in report_data:
                validation_warnings.append("HIPAA report missing phi_detection section")
        elif regulation == "SOX":
            if "financial_data" not in report_data:
                validation_warnings.append("SOX report missing financial_data section")

        is_valid = len(validation_errors) == 0

        if not is_valid:
            raise ValueError(f"Report validation failed: {', '.join(validation_errors)}")

        logger.info(
            "Report validated",
            workflow_instance_id=str(instance.id),
            regulation=regulation,
            is_valid=is_valid,
            validation_errors_count=len(validation_errors),
            validation_warnings_count=len(validation_warnings),
        )

        return {
            "is_valid": is_valid,
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
            "state": {
                "is_valid": is_valid,
                "validation_errors": validation_errors,
                "validation_warnings": validation_warnings,
            },
        }

    @staticmethod
    def _send_report_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Send report (email/API).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with send results
        """
        report_data = instance.state_data.get("report_data")
        regulation = instance.state_data.get("regulation")
        email_recipients = instance.state_data.get("email_recipients", [])
        tenant_id = instance.state_data.get("tenant_id")

        if not report_data:
            raise ValueError("report_data is required")
        if not regulation:
            raise ValueError("regulation is required")

        email_sent = False
        email_sent_at = None

        # Send email if recipients provided
        if email_recipients and len(email_recipients) > 0:
            try:
                from hub.apps.tenants.models import Tenant

                tenant = Tenant.objects.get(id=tenant_id)

                # Create a temporary ComplianceReport for email sending
                # We'll use ReportScheduler.send_report_email which expects a ComplianceReport instance
                # We need to save it temporarily so tenant relationship works
                start_date_dt = datetime.fromisoformat(
                    report_data["report_period"]["start_date"].replace("Z", "+00:00")
                )
                end_date_dt = datetime.fromisoformat(
                    report_data["report_period"]["end_date"].replace("Z", "+00:00")
                )

                temp_report = ComplianceReport(
                    tenant=tenant,
                    regulation=regulation,
                    report_data=report_data,
                    start_date=start_date_dt,
                    end_date=end_date_dt,
                    email_recipients=email_recipients,
                )
                temp_report.save()

                try:
                    email_sent = ReportScheduler.send_report_email(temp_report)
                finally:
                    # Clean up temporary report (we'll create the real one in store_report task)
                    temp_report.delete()
                if email_sent:
                    email_sent_at = timezone.now().isoformat()

                logger.info(
                    "Report email sent",
                    workflow_instance_id=str(instance.id),
                    regulation=regulation,
                    recipients_count=len(email_recipients),
                    email_sent=email_sent,
                )
            except Exception as e:
                logger.error(
                    "Failed to send report email",
                    workflow_instance_id=str(instance.id),
                    regulation=regulation,
                    error=str(e),
                    exc_info=True,
                )
                # Don't fail workflow on email errors - log and continue
                email_sent = False

        return {
            "email_sent": email_sent,
            "email_sent_at": email_sent_at,
            "email_recipients": email_recipients,
            "state": {
                "email_sent": email_sent,
                "email_sent_at": email_sent_at,
                "email_recipients": email_recipients,
            },
        }

    @staticmethod
    @transaction.atomic
    def _store_report_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Store report for audit.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with stored report ID
        """
        tenant_id = instance.state_data.get("tenant_id")
        regulation = instance.state_data.get("regulation")
        report_type = instance.state_data.get("report_type", "STANDARD")
        report_data = instance.state_data.get("report_data")
        start_date_str = instance.state_data.get("start_date")
        end_date_str = instance.state_data.get("end_date")
        triggered_by_id = instance.state_data.get("triggered_by_id")
        is_scheduled = instance.state_data.get("is_scheduled", False)
        schedule_frequency = instance.state_data.get("schedule_frequency")
        email_recipients = instance.state_data.get("email_recipients", [])
        send_email = instance.state_data.get("send_email", False)

        if not tenant_id or not regulation or not report_data:
            raise ValueError("tenant_id, regulation, and report_data are required")

        # Parse dates
        start_date = (
            datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            if start_date_str
            else None
        )
        end_date = (
            datetime.fromisoformat(end_date_str.replace("Z", "+00:00")) if end_date_str else None
        )

        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")

        # Create ComplianceReport record
        report = ComplianceReport.objects.create(
            tenant_id=tenant_id,
            regulation=regulation,
            report_type=report_type,
            report_data=report_data,
            start_date=start_date,
            end_date=end_date,
            scheduled=is_scheduled,
            schedule_frequency=schedule_frequency,
            email_recipients=email_recipients,
            created_by_id=triggered_by_id,
        )

        # Send email if recipients provided (after report is stored)
        email_sent = False
        email_sent_at = None
        send_email = instance.state_data.get("send_email", False)

        if send_email and email_recipients and len(email_recipients) > 0:
            try:
                email_sent = ReportScheduler.send_report_email(report)
                if email_sent:
                    email_sent_at = timezone.now()
                    # Update report with email status
                    report.email_sent = True
                    report.email_sent_at = email_sent_at
                    report.save(update_fields=["email_sent", "email_sent_at"])

                logger.info(
                    "Report email sent",
                    workflow_instance_id=str(instance.id),
                    report_id=str(report.id),
                    regulation=regulation,
                    recipients_count=len(email_recipients),
                    email_sent=email_sent,
                )
            except Exception as e:
                logger.error(
                    "Failed to send report email",
                    workflow_instance_id=str(instance.id),
                    report_id=str(report.id),
                    regulation=regulation,
                    error=str(e),
                    exc_info=True,
                )
                # Don't fail workflow on email errors - log and continue
                email_sent = False

        logger.info(
            "Report stored",
            workflow_instance_id=str(instance.id),
            report_id=str(report.id),
            regulation=regulation,
            tenant_id=tenant_id,
            email_sent=email_sent,
        )

        return {
            "report_id": str(report.id),
            "email_sent": email_sent,
            "email_sent_at": email_sent_at.isoformat() if email_sent_at else None,
            "state": {
                "report_id": str(report.id),
                "email_sent": email_sent,
                "email_sent_at": email_sent_at.isoformat() if email_sent_at else None,
            },
        }

    @staticmethod
    def _audit_logging_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create audit log entry for compliance report generation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit event ID
        """
        tenant_id = instance.state_data.get("tenant_id")
        regulation = instance.state_data.get("regulation")
        report_id = instance.state_data.get("report_id")
        triggered_by_id = instance.state_data.get("triggered_by_id")

        if not tenant_id or not regulation:
            raise ValueError("tenant_id and regulation are required")

        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=triggered_by_id) if triggered_by_id else None

        # Create audit event
        audit_event = create_audit_event(
            resource_type="COMPLIANCE_REPORT",
            action="COMPLIANCE_REPORT_GENERATED",
            actor_user=user,
            tenant=tenant,
            resource_id=report_id or str(instance.id),
            details={
                "regulation": regulation,
                "report_id": report_id,
                "workflow_instance_id": str(instance.id),
            },
        )

        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            report_id=report_id,
            regulation=regulation,
            audit_event_id=str(audit_event.id) if audit_event else None,
        )

        return {
            "audit_event_id": str(audit_event.id) if audit_event else None,
            "state": {"audit_event_id": str(audit_event.id) if audit_event else None},
        }

    @classmethod
    @transaction.atomic
    def execute(
        cls,
        tenant_id: str,
        regulation: str,
        report_type: str = "STANDARD",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        triggered_by_id: Optional[str] = None,
        is_scheduled: bool = False,
        schedule_frequency: Optional[str] = None,
        email_recipients: Optional[List[str]] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None,
    ) -> Dict[str, Any]:
        """
        Execute compliance reporting workflow.

        Args:
            tenant_id: Tenant ID
            regulation: Regulation (GDPR, HIPAA, SOX, LGPD, CCPA)
            report_type: Report type (STANDARD, SUMMARY, DETAILED)
            start_date: Start date for report period (optional)
            end_date: End date for report period (optional)
            triggered_by_id: User ID who triggered the report (optional)
            is_scheduled: Whether this is a scheduled report (default: False)
            schedule_frequency: Schedule frequency if scheduled (DAILY, WEEKLY, MONTHLY, QUARTERLY)
            email_recipients: List of email addresses to send report to (optional)
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "regulation": regulation,
            "report_type": report_type,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "triggered_by_id": triggered_by_id,
            "is_scheduled": is_scheduled,
            "schedule_frequency": schedule_frequency,
            "email_recipients": email_recipients or [],
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=triggered_by_id,
        )

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Compliance reporting workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                regulation=regulation,
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "report_id": workflow_instance.state_data.get("report_id"),
                "output_data": workflow_instance.output_data,
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Compliance reporting workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                regulation=regulation,
                error=error_message,
            )
            raise ValueError(f"Compliance reporting workflow failed: {error_message}")
