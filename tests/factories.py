"""
Test Factories for All Models

Real factories (not mocks) for creating test data for all models.
These factories create actual model instances with realistic test data.
"""

import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig, TenantStatus

User = get_user_model()

# Import app-specific factories


class UserFactory:
    """Factory for creating User instances"""

    @staticmethod
    def create_user(email: str | None = None, tenant: Tenant | None = None, **kwargs) -> User:
        """
        Create a User instance.

        Args:
            email: User email (default: auto-generated)
            tenant: Tenant instance (required)
            **kwargs: Additional fields (display_name, status, etc.)

        Returns:
            User instance
        """
        if email is None:
            email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        if tenant is None:
            tenant = TenantFactory()

        return User.objects.create(email=email, tenant=tenant, **kwargs)

    def __call__(self, **kwargs) -> User:
        """Allow factory to be called directly: UserFactory(**kwargs)"""
        return self.create_user(**kwargs)


# Make UserFactory callable
UserFactory = UserFactory()


class TenantFactory:
    """Factory for creating Tenant instances"""

    @staticmethod
    def create_tenant(
        name: str | None = None,
        slug: str | None = None,
        status: TenantStatus = TenantStatus.ACTIVE,
        kyc_status: KYCStatus = KYCStatus.UNVERIFIED,
        region: str | None = None,
        **kwargs,
    ) -> Tenant:
        """
        Create a Tenant instance.

        Args:
            name: Tenant name (default: auto-generated)
            slug: Tenant slug (default: auto-generated from name)
            status: Tenant status (default: ACTIVE)
            kyc_status: KYC status (default: UNVERIFIED)
            region: Cloud region (default: None)
            **kwargs: Additional fields

        Returns:
            Tenant instance
        """
        if name is None:
            name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        if slug is None:
            slug = name.lower().replace(" ", "-")[:50]

        return Tenant.objects.create(
            name=name, slug=slug, status=status, kyc_status=kyc_status, region=region, **kwargs
        )

    def __call__(self, **kwargs) -> Tenant:
        """Allow factory to be called directly: TenantFactory(**kwargs)"""
        return self.create_tenant(**kwargs)


# Make TenantFactory callable
TenantFactory = TenantFactory()


class TenantConfigFactory:
    """Factory for creating TenantConfig instances"""

    @staticmethod
    def create_tenant_config(
        tenant: Tenant | None = None,
        default_dq_profile: str | None = None,
        allowed_compliance_regimes: list[str] | None = None,
        default_compliance_regimes: list[str] | None = None,
        data_retention_days: int | None = None,
        rate_limits: dict[str, Any] | None = None,
        max_file_size_bytes: int | None = None,
        max_job_concurrency: int | None = None,
        max_queued_jobs: int | None = None,
        **kwargs,
    ) -> TenantConfig:
        """
        Create a TenantConfig instance.

        Args:
            tenant: Tenant instance (required if not provided)
            default_dq_profile: Default DQ profile key
            allowed_compliance_regimes: List of allowed compliance regimes
            default_compliance_regimes: List of default compliance regimes
            data_retention_days: Data retention period in days (90-3650)
            rate_limits: Rate limits JSON structure
            max_file_size_bytes: Maximum file size in bytes
            max_job_concurrency: Maximum concurrent jobs
            max_queued_jobs: Maximum queued jobs
            **kwargs: Additional fields

        Returns:
            TenantConfig instance
        """
        if tenant is None:
            tenant = TenantFactory.create_tenant()

        if default_dq_profile is None:
            default_dq_profile = "intake_basic_gx"

        if allowed_compliance_regimes is None:
            allowed_compliance_regimes = ["GDPR", "LGPD", "CCPA"]

        if default_compliance_regimes is None:
            default_compliance_regimes = ["GDPR"]

        if data_retention_days is None:
            data_retention_days = 2555  # 7 years

        if rate_limits is None:
            rate_limits = {
                "read": {"requests_per_minute": 100, "requests_per_hour": 1000},
                "write": {"requests_per_minute": 50, "requests_per_hour": 500},
                "admin": {"requests_per_minute": 20, "requests_per_hour": 200},
            }

        if max_file_size_bytes is None:
            max_file_size_bytes = 10737418240  # 10 GB

        if max_job_concurrency is None:
            max_job_concurrency = 5

        if max_queued_jobs is None:
            max_queued_jobs = 50

        return TenantConfig.objects.create(
            tenant=tenant,
            default_dq_profile=default_dq_profile,
            allowed_compliance_regimes=allowed_compliance_regimes,
            default_compliance_regimes=default_compliance_regimes,
            data_retention_days=data_retention_days,
            rate_limits=rate_limits,
            max_file_size_bytes=max_file_size_bytes,
            max_job_concurrency=max_job_concurrency,
            max_queued_jobs=max_queued_jobs,
            **kwargs,
        )

    @staticmethod
    def create_tenant_config_with_all_fields(tenant: Tenant | None = None) -> TenantConfig:
        """
        Create a TenantConfig with all fields populated.

        This is a convenience method that creates a config with comprehensive test data.
        """
        return TenantConfigFactory.create_tenant_config(tenant=tenant)


class EmailDeliveryFactory:
    """Factory for creating EmailDelivery instances"""

    @staticmethod
    def create_email_delivery(
        email_type: EmailType = EmailType.USER_INVITATION,
        to_email: str | None = None,
        subject: str | None = None,
        status: EmailDeliveryStatus = EmailDeliveryStatus.PENDING,
        message_id: str | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
        sent_at: timezone.datetime | None = None,
        delivered_at: timezone.datetime | None = None,
        failed_at: timezone.datetime | None = None,
        metadata_json: dict[str, Any] | None = None,
        **kwargs,
    ) -> EmailDelivery:
        """
        Create an EmailDelivery instance.

        Args:
            email_type: Type of email
            to_email: Recipient email address
            subject: Email subject
            status: Delivery status
            message_id: Message ID from email service
            error_message: Error message if failed
            retry_count: Number of retry attempts
            max_retries: Maximum retry attempts
            sent_at: When email was sent
            delivered_at: When email was delivered
            failed_at: When email failed
            metadata_json: Additional metadata
            **kwargs: Additional fields

        Returns:
            EmailDelivery instance
        """
        if to_email is None:
            to_email = f"test-{uuid.uuid4().hex[:8]}@example.com"

        if subject is None:
            subject = f"Test {email_type.label} Email"

        if metadata_json is None:
            metadata_json = {}

        return EmailDelivery.objects.create(
            email_type=email_type,
            to_email=to_email,
            subject=subject,
            status=status,
            message_id=message_id,
            error_message=error_message,
            retry_count=retry_count,
            max_retries=max_retries,
            sent_at=sent_at,
            delivered_at=delivered_at,
            failed_at=failed_at,
            metadata_json=metadata_json,
            **kwargs,
        )

    @staticmethod
    def create_email_delivery_with_all_statuses() -> list[EmailDelivery]:
        """
        Create EmailDelivery instances with all possible statuses.

        Returns:
            List of EmailDelivery instances
        """
        emails = []
        for status in EmailDeliveryStatus:
            emails.append(
                EmailDeliveryFactory.create_email_delivery(
                    status=status, to_email=f"test-{status.value}@example.com"
                )
            )
        return emails

    @staticmethod
    def create_email_delivery_with_all_types() -> list[EmailDelivery]:
        """
        Create EmailDelivery instances with all possible email types.

        Returns:
            List of EmailDelivery instances
        """
        emails = []
        for email_type in EmailType:
            emails.append(
                EmailDeliveryFactory.create_email_delivery(
                    email_type=email_type, to_email=f"test-{email_type.value}@example.com"
                )
            )
        return emails


class JobFactory:
    """Factory for creating Job instances"""

    @staticmethod
    def create_job(
        tenant: Tenant | None = None,
        type: JobType = JobType.DQ_RUN,
        status: JobStatus = JobStatus.PENDING,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        created_by: User | None = None,
        started_at: timezone.datetime | None = None,
        completed_at: timezone.datetime | None = None,
        error_message: str | None = None,
        result_json: dict[str, Any] | None = None,
        details_json: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
        **kwargs,
    ) -> Job:
        """
        Create a Job instance.

        Args:
            tenant: Tenant instance (nullable for system jobs)
            type: Job type
            status: Job status
            resource_type: Resource type (e.g., "CONTRACT", "DATASET", "FILE", "ASSET")
            resource_id: Resource ID
            created_by: User who created the job
            started_at: When job started
            completed_at: When job completed
            error_message: Error message if failed
            result_json: Job result data
            details_json: Job details
            timeout_seconds: Job timeout in seconds
            **kwargs: Additional fields

        Returns:
            Job instance
        """
        if resource_type is None:
            resource_type = "CONTRACT"

        # Generate UUID if resource_id is None, unless explicitly disabled via kwargs
        # This allows tests to pass resource_id=None via kwargs to test missing ID scenarios
        if resource_id is None and not kwargs.get("_allow_none_resource_id", False):
            resource_id = uuid.uuid4()
        # Remove the flag from kwargs before creating the job
        kwargs.pop("_allow_none_resource_id", None)

        if result_json is None:
            result_json = {}

        if details_json is None:
            details_json = {}

        if timeout_seconds is None:
            timeout_seconds = 3600  # 1 hour

        return Job.objects.create(
            tenant=tenant,
            type=type,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            created_by=created_by,
            started_at=started_at,
            completed_at=completed_at,
            error_message=error_message,
            result_json=result_json,
            details_json=details_json,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    @staticmethod
    def create_job_with_all_types(
        tenant: Tenant | None = None, created_by: User | None = None
    ) -> list[Job]:
        """
        Create Job instances with all possible job types.

        Args:
            tenant: Tenant instance
            created_by: User who created the jobs

        Returns:
            List of Job instances
        """
        jobs = []
        for job_type in JobType:
            jobs.append(
                JobFactory.create_job(
                    tenant=tenant,
                    type=job_type,
                    created_by=created_by,
                    resource_type="CONTRACT",
                    resource_id=uuid.uuid4(),
                )
            )
        return jobs

    @staticmethod
    def create_job_with_all_statuses(
        tenant: Tenant | None = None, created_by: User | None = None
    ) -> list[Job]:
        """
        Create Job instances with all possible job statuses.

        Args:
            tenant: Tenant instance
            created_by: User who created the jobs

        Returns:
            List of Job instances
        """
        jobs = []
        for status in JobStatus:
            jobs.append(
                JobFactory.create_job(
                    tenant=tenant,
                    status=status,
                    created_by=created_by,
                    resource_type="CONTRACT",
                    resource_id=uuid.uuid4(),
                )
            )
        return jobs


# --- Workflow and business rules factories (Phase 6.1.2, 6.1.3) ---

try:
    from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult
    from hub.apps.orchestration.business_rules import OrchestrationRuleExecutionContext
    from hub.apps.orchestration.models import (
        StepStatus,
        WorkflowDefinition,
        WorkflowInstance,
        WorkflowStatus,
        WorkflowStep,
    )

    _ORCHESTRATION_AVAILABLE = True
except ImportError:
    _ORCHESTRATION_AVAILABLE = False
    WorkflowDefinition = None
    WorkflowInstance = None
    WorkflowStep = None
    WorkflowStatus = None
    StepStatus = None
    ValidationResult = None
    RuleExecutionContext = None
    OrchestrationRuleExecutionContext = None


if _ORCHESTRATION_AVAILABLE:

    class WorkflowDefinitionFactory:
        """Factory for creating WorkflowDefinition instances (Phase 6.1.2)."""

        @staticmethod
        def create_workflow_definition(
            name: str = "test_workflow",
            version: str = "1.0.0",
            dsl_json: dict[str, Any] | None = None,
            description: str | None = None,
            is_active: bool = True,
            created_by=None,
            **kwargs,
        ):
            if dsl_json is None:
                dsl_json = {
                    "version": "1.0.0",
                    "steps": [
                        {"name": "step1", "type": "task", "task": "test.step1"},
                    ],
                }
            return WorkflowDefinition.objects.create(
                name=name,
                version=version,
                dsl_json=dsl_json,
                description=description or f"Test workflow {name}",
                is_active=is_active,
                created_by=created_by,
                **kwargs,
            )

    class WorkflowInstanceFactory:
        """Factory for creating WorkflowInstance instances in various states (Phase 6.1.2)."""

        @staticmethod
        def create_workflow_instance(
            workflow_definition,
            tenant=None,
            status: str = WorkflowStatus.DRAFT,
            workflow_name: str | None = None,
            workflow_version: str | None = None,
            input_data: dict[str, Any] | None = None,
            state_data: dict[str, Any] | None = None,
            created_by=None,
            **kwargs,
        ):
            workflow_name = workflow_name or workflow_definition.name
            workflow_version = workflow_version or workflow_definition.version
            input_data = input_data or {}
            state_data = state_data or {}
            return WorkflowInstance.objects.create(
                workflow_definition=workflow_definition,
                tenant=tenant,
                workflow_name=workflow_name,
                workflow_version=workflow_version,
                status=status if isinstance(status, str) else getattr(status, "value", status),
                input_data=input_data,
                state_data=state_data,
                created_by=created_by,
                **kwargs,
            )

    class WorkflowStepFactory:
        """Factory for creating WorkflowStep instances (Phase 6.1.2)."""

        @staticmethod
        def create_workflow_step(
            workflow_instance,
            step_index: int = 0,
            step_name: str = "step1",
            step_type: str = "task",
            status: str = StepStatus.PENDING,
            input_data: dict[str, Any] | None = None,
            output_data: dict[str, Any] | None = None,
            **kwargs,
        ):
            input_data = input_data or {}
            output_data = output_data or {}
            return WorkflowStep.objects.create(
                workflow_instance=workflow_instance,
                step_index=step_index,
                step_name=step_name,
                step_type=step_type,
                status=status if isinstance(status, str) else getattr(status, "value", status),
                input_data=input_data,
                output_data=output_data,
                **kwargs,
            )

    class ValidationResultFactory:
        """Factory for ValidationResult (business rules; Phase 6.1.3)."""

        @staticmethod
        def create_valid_result(
            warnings: list[str] | None = None, details: dict[str, Any] | None = None
        ):
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings or [],
                details=details or {},
            )

        @staticmethod
        def create_invalid_result(
            errors: list[str],
            warnings: list[str] | None = None,
            details: dict[str, Any] | None = None,
        ):
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings or [],
                details=details or {},
            )

    class RuleExecutionContextFactory:
        """Factory for RuleExecutionContext (Phase 6.1.3)."""

        @staticmethod
        def create_context(
            tenant_id: str | None = None,
            user_id: str | None = None,
            resource=None,
            metadata: dict[str, Any] | None = None,
        ):
            return RuleExecutionContext(
                tenant_id=tenant_id,
                user_id=user_id,
                resource=resource,
                metadata=metadata or {},
            )

    class OrchestrationRuleExecutionContextFactory:
        """Factory for OrchestrationRuleExecutionContext (Phase 6.1.3)."""

        @staticmethod
        def create_context(
            workflow=None,
            step=None,
            workflow_definition=None,
            tenant=None,
            user=None,
            tenant_id: str | None = None,
            user_id: str | None = None,
            metadata: dict[str, Any] | None = None,
        ):
            return OrchestrationRuleExecutionContext(
                workflow=workflow,
                step=step,
                workflow_definition=workflow_definition,
                tenant=tenant,
                user=user,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata=metadata or {},
            )


class AssetFactory:
    """Factory for creating Asset instances."""

    @staticmethod
    def create(
        tenant: Any,
        key: str | None = None,
        name: str | None = None,
        status: str = "DRAFT",
        **kwargs,
    ) -> Any:
        """Create an Asset instance with minimal required fields."""
        import uuid

        from hub.apps.assets.models import Asset

        return Asset.objects.create(
            tenant=tenant,
            key=key or f"test-asset-{uuid.uuid4().hex[:8]}",
            name=name or "Test Asset",
            status=status,
            **kwargs,
        )

    def __new__(cls, tenant=None, **kwargs):
        """Convenience: ``AssetFactory(tenant=t)`` calls ``create``."""
        return cls.create(tenant=tenant, **kwargs)
