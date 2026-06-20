"""
Jobs Business Rules

Comprehensive business rules validation for job operations, including:
- Job creation validation
- Job execution validation
- Job status transition validation
- Tenant and user context validation
- Resource validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import logging
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.jobs.models import Job, JobPriority, JobStatus, JobType
from hub.apps.users.models import User

logger = logging.getLogger(__name__)


@dataclass
class JobsRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for jobs business rules.

    Adds job-specific context:
    - job: The job being validated
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """

    job: Job | None = None
    tenant: Any | None = None  # Using Any to avoid circular import
    user: User | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "job_id": str(self.job.id) if self.job else None,
                "job_type": self.job.type if self.job else None,
                "job_status": self.job.status if self.job else None,
                "tenant_id": str(self.tenant.id) if self.tenant else None,
                "user_id": str(self.user.id) if self.user else None,
            }
        )
        return base_dict


@register_rule(
    rule_name="jobs_validation",
    description="Validates job creation, execution, status transitions, tenant context, and resource relationships",
    tags=["jobs", "validation"],
    priority=10,
    openspec_ref="specs/jobs-business-rules/spec.md",
)
class JobsBusinessRules(BusinessRules):
    """
    Business rules validator for job operations.

    Extends BusinessRules base class with job-specific validation:
    - Job creation validation
    - Job execution validation
    - Job status transition validation
    - Tenant context consistency
    - User permissions and access validation
    - Resource validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "JobsBusinessRules"

    def validate(
        self, context: RuleExecutionContext | None = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all job validation checks.
        It can be called with a JobsRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        job, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - job: Job instance (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('job_creation', 'job_execution', 'status_transition', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract job, tenant, and user from context or kwargs
        if isinstance(context, JobsRuleExecutionContext):
            job = context.job
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            job = kwargs.get("job")
            tenant = kwargs.get("tenant")
            user = kwargs.get("user")

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, "metadata") and isinstance(context.metadata, dict):
                job = job or context.metadata.get("job")
                tenant = tenant or context.metadata.get("tenant")
                user = user or context.metadata.get("user")

            # Also check context.resource
            if not job and context and hasattr(context, "resource"):
                if isinstance(context.resource, Job):
                    job = context.resource

        # Determine what to validate based on what's provided
        validation_type = kwargs.get("validation_type", "all")

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate job if provided
        if job and validation_type in ("job_creation", "job_execution", "status_transition", "all"):
            # For job_creation, use comprehensive creation validation
            if validation_type == "job_creation":
                job_result = self.validate_job_creation(job, tenant, user)
            else:
                # Basic job validation for other types
                job_result = self._validate_job_basic(job, tenant, user)
            result = result.combine(job_result)
            validated_items.append(
                "job_basic" if validation_type != "job_creation" else "job_creation"
            )

        # Validate tenant context if tenant provided
        if tenant and validation_type in ("tenant_context", "all"):
            tenant_context_result = self._validate_tenant_context(tenant)
            result = result.combine(tenant_context_result)
            validated_items.append("tenant_context")

        # Validate permissions if user provided
        if user and validation_type in ("permissions", "all"):
            permissions_result = self._validate_permissions(user, tenant)
            result = result.combine(permissions_result)
            validated_items.append("permissions")

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=["At least one of job, tenant, or user must be provided"],
                details={"validation_type": validation_type},
            )

        # Add validation summary to details
        result.details["validated_items"] = validated_items
        result.details["validation_type"] = validation_type

        return result

    def _validate_job_basic(
        self, job: Job, tenant: Any | None = None, user: User | None = None
    ) -> ValidationResult:
        """
        Validate basic job structure and context.

        Validates:
        - Job has required fields (type, status, resource_type, resource_id)
        - Job type is valid
        - Job status is valid
        - Tenant context consistency
        - User context consistency

        Args:
            job: Job instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            "job_id": str(job.id),
            "job_type": job.type,
            "job_status": job.status,
        }

        # Validate tenant context consistency
        if self.tenant_id and job.tenant_id:
            if str(job.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Job tenant ({job.tenant_id}) does not match context tenant ({self.tenant_id})"
                )
                details["tenant_match"] = False
            else:
                details["tenant_match"] = True

        # Validate tenant context if provided
        if tenant and job.tenant_id:
            if str(tenant.id) != str(job.tenant_id):
                errors.append(
                    f"Job tenant ({job.tenant_id}) does not match provided tenant ({tenant.id})"
                )
                details["provided_tenant_match"] = False
            else:
                details["provided_tenant_match"] = True

        # Validate job type
        valid_job_types = [choice[0] for choice in JobType.choices]
        if job.type not in valid_job_types:
            errors.append(
                f"Job has invalid type: {job.type}. "
                f"Valid job types are: {', '.join(valid_job_types)}"
            )
            details["job_type_valid"] = False
        else:
            details["job_type_valid"] = True

        # Validate job status
        valid_statuses = [choice[0] for choice in JobStatus.choices]
        if job.status not in valid_statuses:
            errors.append(
                f"Job has invalid status: {job.status}. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details["job_status_valid"] = False
        else:
            details["job_status_valid"] = True

        # Validate resource_type and resource_id are provided
        if not job.resource_type or not job.resource_type.strip():
            errors.append("Job must have a resource_type")
            details["has_resource_type"] = False
        else:
            details["has_resource_type"] = True
            details["resource_type"] = job.resource_type

        if not job.resource_id:
            errors.append("Job must have a resource_id")
            details["has_resource_id"] = False
        else:
            details["has_resource_id"] = True
            details["resource_id"] = str(job.resource_id)

        # Validate date consistency
        if job.started_at and job.completed_at:
            if job.completed_at < job.started_at:
                errors.append(
                    f"Job completed_at ({job.completed_at}) is before started_at ({job.started_at})"
                )
                details["date_consistency"] = False
            else:
                details["date_consistency"] = True

        # Validate user context if user provided
        if user and job.created_by:
            if str(user.id) != str(job.created_by.id):
                warnings.append(
                    f"Provided user ({user.id}) does not match job creator ({job.created_by.id})"
                )
                details["user_match"] = False
            else:
                details["user_match"] = True

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_tenant_context(self, tenant: Any) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            tenant: Tenant instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        details = {
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name if hasattr(tenant, "name") else None,
        }

        # Validate tenant context consistency
        if self.tenant_id:
            if str(tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Provided tenant ({tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details["tenant_match"] = False
            else:
                details["tenant_match"] = True

        details["is_valid"] = len(errors) == 0

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, details=details)

    def _validate_permissions(self, user: User, tenant: Any | None = None) -> ValidationResult:
        """
        Validate user permissions.

        Args:
            user: User instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {"user_id": str(user.id), "user_email": user.email}

        # Validate user context consistency
        if self.user_id:
            if str(user.id) != str(self.user_id):
                warnings.append(
                    f"Provided user ({user.id}) does not match context user ({self.user_id})"
                )
                details["user_match"] = False
            else:
                details["user_match"] = True

        # Validate user has tenant if tenant provided
        if tenant and hasattr(user, "tenant_id") and user.tenant_id:
            if str(user.tenant_id) != str(tenant.id):
                errors.append(
                    f"User tenant ({user.tenant_id}) does not match provided tenant ({tenant.id})"
                )
                details["user_tenant_match"] = False
            else:
                details["user_tenant_match"] = True

        # Validate user tenant matches context tenant if both provided
        if self.tenant_id and hasattr(user, "tenant_id") and user.tenant_id:
            if str(user.tenant_id) != str(self.tenant_id):
                warnings.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details["user_context_tenant_match"] = False
            else:
                details["user_context_tenant_match"] = True

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_job_creation(
        self, job: Job, tenant: Any | None = None, user: User | None = None
    ) -> ValidationResult:
        """
        Comprehensive job creation validation.

        Orchestrates all job creation validation checks:
        - Job type validation (valid job types)
        - Job configuration validation (valid parameters, required fields)
        - Job resource validation (resources exist and accessible)
        - Job quota validation (tenant job quota not exceeded)

        Args:
            job: Job instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            "validation_type": "job_creation",
            "job_id": str(job.id) if job.id else None,
            "job_type": job.type if job else None,
        }

        # Determine effective tenant
        effective_tenant = tenant or (job.tenant if job and job.tenant else None)

        # Comprehensive validation: job type validation
        job_type_result = self._validate_job_type(job)
        result = result.combine(job_type_result)
        details["job_type_validated"] = True

        # Comprehensive validation: job configuration validation
        job_config_result = self._validate_job_configuration(job)
        result = result.combine(job_config_result)
        details["job_configuration_validated"] = True

        # Comprehensive validation: job resource validation
        if effective_tenant:
            resource_result = self._validate_job_resource(job, effective_tenant, user)
            result = result.combine(resource_result)
            details["job_resource_validated"] = True
        else:
            details["job_resource_validated"] = False
            details["resource_validation_skipped"] = "No tenant provided"

        # Comprehensive validation: job quota validation
        if effective_tenant:
            quota_result = self._validate_job_quota(job, effective_tenant)
            result = result.combine(quota_result)
            details["job_quota_validated"] = True
        else:
            details["job_quota_validated"] = False
            details["quota_validation_skipped"] = "No tenant provided"

        # Update result details
        result.details.update(details)
        result.details["job_creation_valid"] = result.is_valid
        result.details["is_valid"] = result.is_valid
        result.details["has_warnings"] = len(result.warnings) > 0

        return result

    def _validate_job_type(self, job: Job) -> ValidationResult:
        """
        Validate job type (valid job types: CONTRACT_NORMALIZATION, DQ_RUN, COMPLIANCE_SCAN, TRANSFORMATION, etc.).

        Validates:
        - Job has a type field
        - Job type is one of the valid job types

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with job type validation status
        """
        errors = []
        warnings = []
        details = {
            "job_type_validation": "job_type_validation",
        }

        # Validate job has type
        if not job.type or not job.type.strip():
            errors.append("Job must have a type")
            details["has_type"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["has_type"] = True
        details["job_type"] = job.type

        # Validate job type is valid
        valid_job_types = [choice[0] for choice in JobType.choices]
        if job.type not in valid_job_types:
            errors.append(
                f"Job has invalid type: {job.type}. "
                f"Valid job types are: {', '.join(valid_job_types)}"
            )
            details["job_type_valid"] = False
        else:
            details["job_type_valid"] = True

        details["job_type_validation_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_configuration(self, job: Job) -> ValidationResult:
        """
        Validate job configuration (valid parameters, required fields).

        Validates:
        - Required fields are present (resource_type, resource_id)
        - details_json is valid JSON structure (if provided)
        - timeout_seconds is valid (if provided)
        - Configuration parameters are appropriate for job type

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with job configuration validation status
        """
        errors = []
        warnings = []
        details = {
            "job_configuration_validation": "job_configuration_validation",
        }

        # Validate resource_type is provided
        if not job.resource_type or not job.resource_type.strip():
            errors.append("Job must have a resource_type")
            details["has_resource_type"] = False
        else:
            details["has_resource_type"] = True
            details["resource_type"] = job.resource_type

        # Validate resource_id is provided
        if not job.resource_id:
            errors.append("Job must have a resource_id")
            details["has_resource_id"] = False
        else:
            details["has_resource_id"] = True
            details["resource_id"] = str(job.resource_id)

        # Validate details_json is valid (if provided)
        if job.details_json is not None:
            if not isinstance(job.details_json, dict):
                errors.append("Job details_json must be a dictionary")
                details["details_json_valid"] = False
            else:
                details["details_json_valid"] = True
                details["has_details_json"] = True
        else:
            details["has_details_json"] = False
            details["details_json_valid"] = True  # None is valid

        # Validate timeout_seconds is valid (if provided)
        if job.timeout_seconds is not None:
            if not isinstance(job.timeout_seconds, int):
                errors.append("Job timeout_seconds must be an integer")
                details["timeout_seconds_valid"] = False
            elif job.timeout_seconds <= 0:
                errors.append("Job timeout_seconds must be greater than 0")
                details["timeout_seconds_valid"] = False
            else:
                details["timeout_seconds_valid"] = True
                details["timeout_seconds"] = job.timeout_seconds

                # Warn if timeout seems too long (> 24 hours)
                if job.timeout_seconds > 86400:
                    warnings.append(
                        f"Job timeout_seconds ({job.timeout_seconds}) is very long (> 24 hours). "
                        f"Consider if this is intentional."
                    )
                    details["timeout_reasonable"] = False
                else:
                    details["timeout_reasonable"] = True
        else:
            details["has_timeout_seconds"] = False
            details["timeout_seconds_valid"] = True  # None is valid (will use default)

        # Validate job type-specific configuration requirements
        if job.type and job.details_json is not None and isinstance(job.details_json, dict):
            # Get job type as string for comparison (Django TextChoices stores as string)
            job_type_str = job.type if isinstance(job.type, str) else str(job.type)

            # For CONTRACT_VALIDATION jobs, check if contract_id is in details
            if (
                job_type_str == JobType.CONTRACT_VALIDATION[0]
                or job_type_str == JobType.CONTRACT_VALIDATION
            ):
                if "contract_id" not in job.details_json:
                    warnings.append(
                        "CONTRACT_VALIDATION job should have 'contract_id' in details_json"
                    )
                    details["contract_id_in_details"] = False
                else:
                    details["contract_id_in_details"] = True

            # For DQ_RUN jobs, check if profile_key or checks are in details
            if job_type_str == JobType.DQ_RUN[0] or job_type_str == JobType.DQ_RUN:
                if "profile_key" not in job.details_json and "checks" not in job.details_json:
                    warnings.append(
                        "DQ_RUN job should have 'profile_key' or 'checks' in details_json"
                    )
                    details["dq_config_in_details"] = False
                else:
                    details["dq_config_in_details"] = True

            # For COMPLIANCE_RUN jobs, check if scan_type is in details
            if job_type_str == JobType.COMPLIANCE_RUN[0] or job_type_str == JobType.COMPLIANCE_RUN:
                if "scan_type" not in job.details_json:
                    warnings.append("COMPLIANCE_RUN job should have 'scan_type' in details_json")
                    details["scan_type_in_details"] = False
                else:
                    details["scan_type_in_details"] = True

        details["job_configuration_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_resource(
        self, job: Job, tenant: Any, user: User | None = None
    ) -> ValidationResult:
        """
        Validate job resource (resources exist and accessible).

        Validates:
        - Resource exists (based on resource_type and resource_id)
        - Resource belongs to tenant (or cross-tenant access is allowed)
        - Resource is accessible (not deleted, not archived)

        Args:
            job: Job instance to validate
            tenant: Tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with resource validation status
        """
        errors = []
        warnings = []
        details = {
            "resource_validation": "job_resource_validation",
            "resource_type": job.resource_type,
            "resource_id": str(job.resource_id) if job.resource_id else None,
        }

        if not job.resource_type or not job.resource_id:
            errors.append("Job must have resource_type and resource_id for resource validation")
            details["resource_provided"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["resource_provided"] = True

        # Map resource_type to model class
        resource_model_map = {
            "CONTRACT": ("hub.apps.contracts.models", "Contract"),
            "DATASET": ("hub.apps.datasets.models", "Dataset"),
            "FILE": ("hub.apps.files.models", "File"),
            "ASSET": ("hub.apps.assets.models", "Asset"),
        }

        resource_type_upper = job.resource_type.upper()
        if resource_type_upper not in resource_model_map:
            warnings.append(
                f"Unknown resource_type '{job.resource_type}'. "
                f"Cannot validate resource existence. Known types: {', '.join(resource_model_map.keys())}"
            )
            details["resource_type_known"] = False
            details["resource_exists"] = None  # Cannot determine
            details["resource_accessible"] = None  # Cannot determine
            return ValidationResult(
                is_valid=True,  # Not an error, just can't validate
                errors=errors,
                warnings=warnings,
                details=details,
            )

        details["resource_type_known"] = True

        # Import and get resource model
        try:
            module_path, model_name = resource_model_map[resource_type_upper]
            module = __import__(module_path, fromlist=[model_name])
            ResourceModel = getattr(module, model_name)
        except (ImportError, AttributeError) as e:
            warnings.append(f"Could not import resource model for '{job.resource_type}': {e!s}")
            details["resource_model_imported"] = False
            details["resource_exists"] = None
            details["resource_accessible"] = None
            return ValidationResult(
                is_valid=True,  # Not an error, just can't validate
                errors=errors,
                warnings=warnings,
                details=details,
            )

        details["resource_model_imported"] = True

        # Check if resource exists
        try:
            resource = ResourceModel.objects.get(id=job.resource_id)
            details["resource_exists"] = True
        except ResourceModel.DoesNotExist:
            errors.append(f"Resource {job.resource_type}:{job.resource_id} does not exist")
            details["resource_exists"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        # Validate resource belongs to tenant
        if hasattr(resource, "tenant") and resource.tenant:
            resource_tenant_id = str(resource.tenant.id)
            tenant_id = str(tenant.id)

            if resource_tenant_id != tenant_id:
                errors.append(
                    f"Resource {job.resource_type}:{job.resource_id} belongs to tenant {resource_tenant_id} "
                    f"but job is for tenant {tenant_id}"
                )
                details["resource_tenant_match"] = False
            else:
                details["resource_tenant_match"] = True
        else:
            warnings.append(
                f"Resource {job.resource_type}:{job.resource_id} has no tenant association"
            )
            details["resource_has_tenant"] = False

        # Validate resource is accessible (not deleted/archived)
        if hasattr(resource, "status"):
            resource_status = resource.status
            details["resource_status"] = resource_status

            # Check for deleted/archived statuses (common patterns)
            inaccessible_statuses = ["DELETED", "ARCHIVED", "RETIRED", "INACTIVE"]
            if resource_status in inaccessible_statuses:
                errors.append(
                    f"Resource {job.resource_type}:{job.resource_id} has status {resource_status} "
                    f"and is not accessible for job execution"
                )
                details["resource_accessible"] = False
            else:
                details["resource_accessible"] = True
        else:
            # No status field - assume accessible
            details["resource_accessible"] = True
            details["resource_status"] = None

        # Validate user has access to resource (if user provided)
        if user:
            if hasattr(user, "tenant") and user.tenant:
                user_tenant_id = str(user.tenant.id)
                if hasattr(resource, "tenant") and resource.tenant:
                    resource_tenant_id = str(resource.tenant.id)
                    if user_tenant_id != resource_tenant_id:
                        warnings.append(
                            f"User belongs to tenant {user_tenant_id} but resource belongs to tenant {resource_tenant_id} "
                            f"(cross-tenant access)"
                        )
                        details["user_resource_tenant_match"] = False
                    else:
                        details["user_resource_tenant_match"] = True
                else:
                    details["user_resource_tenant_match"] = None
            else:
                warnings.append("User has no tenant association")
                details["user_has_tenant"] = False

        details["resource_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_quota(self, job: Job, tenant: Any) -> ValidationResult:
        """
        Validate job quota (tenant job quota not exceeded).

        Validates:
        - Tenant has not exceeded concurrent job limit
        - Tenant has not exceeded queued job limit
        - Uses real quota checking from jobs.utils

        Args:
            job: Job instance to validate
            tenant: Tenant instance

        Returns:
            ValidationResult with quota validation status
        """
        errors = []
        warnings = []
        details = {
            "quota_validation": "job_quota_validation",
            "tenant_id": str(tenant.id),
        }

        tenant_id = str(tenant.id)

        # Use real quota checking from jobs.utils
        try:
            from django.core.cache import cache

            from hub.apps.jobs.utils import check_tenant_job_limits
            from hub.apps.tenants.services import get_tenant_job_limits

            # Get tenant job limits
            limits = get_tenant_job_limits(tenant_id)
            max_concurrency = limits.get("max_job_concurrency", 5)
            max_queued = limits.get("max_queued_jobs", 50)

            details["max_job_concurrency"] = max_concurrency
            details["max_queued_jobs"] = max_queued

            # Check tenant job limits
            can_create_job, error_message = check_tenant_job_limits(tenant_id)

            if not can_create_job:
                # Get current counts for detailed error message
                running_key = f"job:tenant:{tenant_id}:running"
                queued_key = f"job:tenant:{tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["running_jobs"] = running_count
                details["queued_jobs"] = queued_count

                if running_count >= max_concurrency:
                    errors.append(
                        f"Tenant has reached maximum concurrent job limit ({max_concurrency}). "
                        f"Current running jobs: {running_count}. Please wait for jobs to complete."
                    )
                    details["concurrency_limit_exceeded"] = True
                else:
                    details["concurrency_limit_exceeded"] = False

                if queued_count >= max_queued:
                    errors.append(
                        f"Tenant has reached maximum queued job limit ({max_queued}). "
                        f"Current queued jobs: {queued_count}. Please wait for queue to process."
                    )
                    details["queued_limit_exceeded"] = True
                else:
                    details["queued_limit_exceeded"] = False

                # Add the error message from check_tenant_job_limits if provided
                if error_message:
                    errors.append(error_message)
            else:
                # Get current counts for details even if quota is OK
                running_key = f"job:tenant:{tenant_id}:running"
                queued_key = f"job:tenant:{tenant_id}:queued"
                running_count = cache.get(running_key, 0)
                queued_count = cache.get(queued_key, 0)

                details["running_jobs"] = running_count
                details["queued_jobs"] = queued_count
                details["concurrency_limit_exceeded"] = False
                details["queued_limit_exceeded"] = False

                # Warn if approaching limits
                concurrency_usage_pct = (
                    (running_count / max_concurrency * 100) if max_concurrency > 0 else 0
                )
                queued_usage_pct = (queued_count / max_queued * 100) if max_queued > 0 else 0

                if concurrency_usage_pct >= 80:
                    warnings.append(
                        f"Tenant is using {concurrency_usage_pct:.1f}% of concurrent job limit "
                        f"({running_count}/{max_concurrency})"
                    )
                    details["concurrency_usage_high"] = True
                else:
                    details["concurrency_usage_high"] = False

                if queued_usage_pct >= 80:
                    warnings.append(
                        f"Tenant is using {queued_usage_pct:.1f}% of queued job limit "
                        f"({queued_count}/{max_queued})"
                    )
                    details["queued_usage_high"] = True
                else:
                    details["queued_usage_high"] = False

            details["quota_valid"] = len(errors) == 0
            details["quota_validated"] = True

        except Exception as e:
            logger.warning(
                f"Job quota validation failed: {e!s}", extra={"tenant_id": tenant_id}, exc_info=True
            )
            warnings.append(f"Could not validate job quota: {e!s}. Job creation may proceed.")
            details["quota_check_error"] = str(e)
            details["quota_valid"] = True  # Allow on error (graceful degradation)
            details["quota_validated"] = True  # Still considered validated (with error)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_job_execution(
        self,
        job: Job,
        current_status: str | None = None,
        new_status: str | None = None,
        tenant: Any | None = None,
        user: User | None = None,
    ) -> ValidationResult:
        """
        Comprehensive job execution validation.

        Orchestrates all job execution validation checks:
        - Job status transition validation
        - Job cancellation validation
        - Job retry validation
        - Job timeout validation

        Args:
            job: Job instance to validate
            current_status: Optional current status (if None, uses job.status)
            new_status: Optional new status to transition to
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with execution validation status
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            "validation_type": "job_execution",
            "job_id": str(job.id) if job.id else None,
            "job_type": job.type if job else None,
        }

        # Status transition validation
        status_result = self._validate_job_status_transition(
            job, current_status=current_status, new_status=new_status
        )
        result = result.combine(status_result)
        details["status_transition_validated"] = True

        # Cancellation validation (if attempting to cancel)
        # Get status values from choices to ensure consistency
        status_values = {choice[0]: choice[0] for choice in JobStatus.choices}
        cancelled_val = status_values.get("CANCELLED", "CANCELLED")
        if new_status == cancelled_val or (new_status is None and current_status == cancelled_val):
            cancellation_result = self._validate_job_cancellation(job)
            result = result.combine(cancellation_result)
            details["cancellation_validated"] = True
        else:
            details["cancellation_validated"] = False
            details["cancellation_validation_skipped"] = "Not cancelling job"

        # Retry validation
        retry_result = self._validate_job_retry(job)
        result = result.combine(retry_result)
        details["retry_validated"] = True

        # Timeout validation
        timeout_result = self._validate_job_timeout(job)
        result = result.combine(timeout_result)
        details["timeout_validated"] = True

        # Update result details
        result.details.update(details)
        result.details["job_execution_valid"] = result.is_valid
        result.details["is_valid"] = result.is_valid
        result.details["has_warnings"] = len(result.warnings) > 0

        return result

    def _validate_job_status_transition(
        self, job: Job, current_status: str | None = None, new_status: str | None = None
    ) -> ValidationResult:
        """
        Validate job status transition.

        Validates:
        - Current status is valid
        - New status is valid (if provided)
        - Transition is allowed (PENDING → RUNNING → COMPLETED/FAILED/CANCELLED)
        - Timestamps are correctly set for transitions

        Args:
            job: Job instance
            current_status: Current status (if None, uses job.status)
            new_status: New status to transition to (if None, just validates current state)

        Returns:
            ValidationResult with status transition validation status
        """
        errors = []
        warnings = []
        details = {
            "validation_type": "status_transition",
        }

        # Get current status
        if current_status is None:
            current_status = job.status

        details["current_status"] = current_status

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in JobStatus.choices]
        if current_status not in valid_statuses:
            errors.append(
                f"Invalid current status: {current_status}. Valid statuses are: {', '.join(valid_statuses)}"
            )
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["current_status_valid"] = True

        # Get status values from choices to ensure consistency
        status_values = {choice[0]: choice[0] for choice in JobStatus.choices}
        pending_val = status_values.get("PENDING", "PENDING")
        running_val = status_values.get("RUNNING", "RUNNING")
        completed_val = status_values.get("COMPLETED", "COMPLETED")
        failed_val = status_values.get("FAILED", "FAILED")
        cancelled_val = status_values.get("CANCELLED", "CANCELLED")

        # If new_status is provided, validate transition
        if new_status:
            details["new_status"] = new_status

            # Validate new status is valid
            if new_status not in valid_statuses:
                errors.append(
                    f"Invalid new status: {new_status}. Valid statuses are: {', '.join(valid_statuses)}"
                )
                return ValidationResult(
                    is_valid=False, errors=errors, warnings=warnings, details=details
                )

            details["new_status_valid"] = True

            # Define allowed transitions
            allowed_transitions = {
                pending_val: [running_val, cancelled_val],  # PENDING can go to RUNNING or CANCELLED
                running_val: [
                    completed_val,
                    failed_val,
                    cancelled_val,
                ],  # RUNNING can go to COMPLETED, FAILED, or CANCELLED
                completed_val: [],  # Terminal state - cannot transition
                failed_val: [],  # Terminal state - cannot transition
                cancelled_val: [],  # Terminal state - cannot transition
            }

            # Check if transition is allowed
            allowed_next_statuses = allowed_transitions.get(current_status, [])
            if new_status not in allowed_next_statuses:
                errors.append(
                    f"Cannot transition from {current_status} to {new_status}. "
                    f"Allowed transitions from {current_status}: {allowed_next_statuses}"
                )
                details["transition_allowed"] = False
            else:
                details["transition_allowed"] = True

            # Validate transition timing
            if current_status == pending_val and new_status == running_val:
                # PENDING → RUNNING: should have started_at set
                if not job.started_at:
                    warnings.append("Transitioning to RUNNING status - started_at should be set")
                    details["started_at_set"] = False
                else:
                    details["started_at_set"] = True

            elif current_status == running_val and new_status in [
                completed_val,
                failed_val,
                cancelled_val,
            ]:
                # RUNNING → COMPLETED/FAILED/CANCELLED: should have started_at and completed_at set
                if not job.started_at:
                    errors.append(
                        "Cannot transition to terminal state without started_at being set"
                    )
                    details["started_at_set"] = False
                else:
                    details["started_at_set"] = True

                if not job.completed_at:
                    warnings.append("Transitioning to terminal state - completed_at should be set")
                    details["completed_at_set"] = False
                else:
                    details["completed_at_set"] = True

                    # Validate completed_at is after started_at
                    if job.started_at and job.completed_at < job.started_at:
                        errors.append(
                            f"completed_at ({job.completed_at}) cannot be before started_at ({job.started_at})"
                        )
                        details["date_order_valid"] = False
                    else:
                        details["date_order_valid"] = True

            elif current_status == pending_val and new_status == cancelled_val:
                # PENDING → CANCELLED: completed_at should be set
                if not job.completed_at:
                    warnings.append("Cancelling job - completed_at should be set")
                    details["completed_at_set"] = False
                else:
                    details["completed_at_set"] = True
        # Just validating current state - check if it's in a valid state for operations
        elif current_status == pending_val:
            details["can_start"] = True
            details["can_cancel"] = True
        elif current_status == running_val:
            details["can_start"] = False
            details["can_cancel"] = True
            details["can_complete"] = True
        else:
            # Terminal state
            details["can_start"] = False
            details["can_cancel"] = False
            details["can_complete"] = False

        details["status_transition_valid"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_cancellation(self, job: Job) -> ValidationResult:
        """
        Validate job cancellation.

        Validates:
        - Job can be cancelled (only PENDING or RUNNING jobs can be cancelled)
        - Job is not already in a terminal state

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with cancellation validation status
        """
        errors = []
        warnings = []
        details = {
            "validation_type": "cancellation",
            "job_id": str(job.id),
            "job_status": job.status,
        }

        # Get status values
        status_values = {choice[0]: choice[0] for choice in JobStatus.choices}
        pending_val = status_values.get("PENDING", "PENDING")
        running_val = status_values.get("RUNNING", "RUNNING")
        completed_val = status_values.get("COMPLETED", "COMPLETED")
        failed_val = status_values.get("FAILED", "FAILED")
        cancelled_val = status_values.get("CANCELLED", "CANCELLED")

        # Check if job can be cancelled
        cancellable_statuses = [pending_val, running_val]
        if job.status not in cancellable_statuses:
            errors.append(
                f"Job cannot be cancelled. Only jobs with status PENDING or RUNNING can be cancelled. "
                f"Current status: {job.status}"
            )
            details["can_cancel"] = False
        else:
            details["can_cancel"] = True

        # Check if job is already cancelled
        if job.status == cancelled_val:
            warnings.append("Job is already cancelled")
            details["already_cancelled"] = True
        else:
            details["already_cancelled"] = False

        # Check if job is in terminal state
        terminal_statuses = [completed_val, failed_val, cancelled_val]
        if job.status in terminal_statuses:
            errors.append(f"Job is in terminal state ({job.status}) and cannot be cancelled")
            details["is_terminal"] = True
        else:
            details["is_terminal"] = False

        details["cancellation_valid"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_retry(self, job: Job) -> ValidationResult:
        """
        Validate job retry logic.

        Validates:
        - Retry count is within limits (if retry information is in details_json)
        - Max retries is reasonable
        - Retry logic is valid

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with retry validation status
        """
        errors = []
        warnings = []
        details = {
            "validation_type": "retry",
            "job_id": str(job.id),
        }

        # Default max retries if not specified
        DEFAULT_MAX_RETRIES = 3
        MAX_ALLOWED_RETRIES = 10

        # Check if retry information is in details_json
        if job.details_json and isinstance(job.details_json, dict):
            retry_count = job.details_json.get("retry_count", 0)
            max_retries = job.details_json.get("max_retries", DEFAULT_MAX_RETRIES)
        else:
            retry_count = 0
            max_retries = DEFAULT_MAX_RETRIES

        details["retry_count"] = retry_count
        details["max_retries"] = max_retries

        # Validate max_retries is reasonable
        if max_retries < 0:
            errors.append(f"max_retries ({max_retries}) cannot be negative")
            details["max_retries_valid"] = False
        elif max_retries > MAX_ALLOWED_RETRIES:
            errors.append(
                f"max_retries ({max_retries}) exceeds maximum allowed ({MAX_ALLOWED_RETRIES})"
            )
            details["max_retries_valid"] = False
        else:
            details["max_retries_valid"] = True

        # Validate retry_count is not negative
        if retry_count < 0:
            errors.append(f"retry_count ({retry_count}) cannot be negative")
            details["retry_count_valid"] = False
        else:
            details["retry_count_valid"] = True

        # Check if retry count exceeds max retries
        if retry_count > max_retries:
            errors.append(f"retry_count ({retry_count}) exceeds max_retries ({max_retries})")
            details["retry_limit_exceeded"] = True
        else:
            details["retry_limit_exceeded"] = False

        # Warn if approaching retry limit
        if max_retries > 0:
            retry_usage_pct = (retry_count / max_retries * 100) if max_retries > 0 else 0
            if retry_usage_pct >= 80:
                warnings.append(
                    f"Job has used {retry_usage_pct:.1f}% of retry limit ({retry_count}/{max_retries})"
                )
                details["retry_usage_high"] = True
            else:
                details["retry_usage_high"] = False

        details["retry_valid"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_job_timeout(self, job: Job) -> ValidationResult:
        """
        Validate job timeout limits.

        Validates:
        - Timeout is set (if required for job type)
        - Timeout is within reasonable limits
        - Timeout hasn't been exceeded (if job is running)

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with timeout validation status
        """
        errors = []
        warnings = []
        details = {
            "validation_type": "timeout",
            "job_id": str(job.id),
        }

        # Default timeout limits (in seconds)
        MIN_TIMEOUT_SECONDS = 1
        MAX_TIMEOUT_SECONDS = 86400 * 7  # 7 days
        DEFAULT_TIMEOUT_SECONDS = 3600  # 1 hour

        # Get timeout from job
        timeout_seconds = job.timeout_seconds

        details["timeout_seconds"] = timeout_seconds

        # If timeout is not set, use default
        if timeout_seconds is None:
            timeout_seconds = DEFAULT_TIMEOUT_SECONDS
            warnings.append(
                f"Job timeout not set, using default ({DEFAULT_TIMEOUT_SECONDS} seconds)"
            )
            details["timeout_set"] = False
            details["timeout_seconds_effective"] = timeout_seconds
        else:
            details["timeout_set"] = True
            details["timeout_seconds_effective"] = timeout_seconds

        # Validate timeout is within limits
        if timeout_seconds < MIN_TIMEOUT_SECONDS:
            errors.append(
                f"Job timeout ({timeout_seconds} seconds) is below minimum ({MIN_TIMEOUT_SECONDS} seconds)"
            )
            details["timeout_valid"] = False
        elif timeout_seconds > MAX_TIMEOUT_SECONDS:
            errors.append(
                f"Job timeout ({timeout_seconds} seconds) exceeds maximum ({MAX_TIMEOUT_SECONDS} seconds / 7 days)"
            )
            details["timeout_valid"] = False
        else:
            details["timeout_valid"] = True

        # Check if timeout has been exceeded (if job is running)
        # Get status value from choices to ensure consistency
        status_values = {choice[0]: choice[0] for choice in JobStatus.choices}
        running_val = status_values.get("RUNNING", "RUNNING")
        if job.status == running_val and job.started_at:
            elapsed_seconds = (timezone.now() - job.started_at).total_seconds()
            details["elapsed_seconds"] = elapsed_seconds

            if elapsed_seconds > timeout_seconds:
                errors.append(
                    f"Job has exceeded timeout ({timeout_seconds} seconds). "
                    f"Elapsed time: {elapsed_seconds:.1f} seconds"
                )
                details["timeout_exceeded"] = True
            else:
                details["timeout_exceeded"] = False

                # Warn if approaching timeout
                timeout_usage_pct = (
                    (elapsed_seconds / timeout_seconds * 100) if timeout_seconds > 0 else 0
                )
                if timeout_usage_pct >= 80:
                    warnings.append(
                        f"Job has used {timeout_usage_pct:.1f}% of timeout ({elapsed_seconds:.1f}/{timeout_seconds} seconds)"
                    )
                    details["timeout_usage_high"] = True
                else:
                    details["timeout_usage_high"] = False
        else:
            details["elapsed_seconds"] = None
            details["timeout_exceeded"] = False
            details["timeout_usage_high"] = False

        details["timeout_validation_valid"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def validate_job_priority(
        self, job: Job, tenant: Any | None = None, user: User | None = None
    ) -> ValidationResult:
        """
        Comprehensive job priority validation.

        Orchestrates all priority validation checks:
        - Priority level validation (valid priority levels)
        - Priority assignment validation (user has permission for high priority)
        - Priority queue validation (priority-based queue ordering)

        Args:
            job: Job instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with priority validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            "validation_type": "job_priority",
            "job_id": str(job.id) if job.id else None,
            "job_type": job.type if job else None,
        }

        # Determine effective tenant and user
        effective_tenant = tenant or (job.tenant if job and job.tenant else None)
        effective_user = user or (job.created_by if job and job.created_by else None)

        # Priority level validation
        priority_level_result = self._validate_priority_level(job)
        result = result.combine(priority_level_result)
        details["priority_level_validated"] = True

        # Priority assignment validation (user permissions)
        if effective_user:
            priority_assignment_result = self._validate_priority_assignment(
                job, effective_user, effective_tenant
            )
            result = result.combine(priority_assignment_result)
            details["priority_assignment_validated"] = True
        else:
            details["priority_assignment_validated"] = False
            details["priority_assignment_skipped"] = "No user provided"

        # Priority queue validation
        priority_queue_result = self._validate_priority_queue(job)
        result = result.combine(priority_queue_result)
        details["priority_queue_validated"] = True

        # Update result details
        result.details.update(details)
        result.details["job_priority_valid"] = result.is_valid
        result.details["is_valid"] = result.is_valid
        result.details["has_warnings"] = len(result.warnings) > 0

        return result

    def _validate_priority_level(self, job: Job) -> ValidationResult:
        """
        Validate priority level (valid priority levels: LOW, NORMAL, HIGH, CRITICAL).

        Priority can be:
        - Explicitly set in details_json['priority']
        - Inferred from job type (via queue mapping)
        - Defaults to NORMAL if not specified

        Validates:
        - Priority is one of the valid priority levels
        - Priority format is correct

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with priority level validation status
        """
        errors = []
        warnings = []
        details = {
            "priority_validation": "priority_level_validation",
        }

        # Get priority from details_json or infer from job type
        priority = None
        priority_source = None

        if job.details_json and isinstance(job.details_json, dict):
            priority = job.details_json.get("priority")
            if priority:
                priority_source = "details_json"
                details["priority_source"] = "details_json"
                details["priority_from_details"] = priority

        # If not in details_json, infer from job type
        if not priority and job.type:
            from hub.apps.jobs.utils import get_queue_for_job_type

            queue_name = get_queue_for_job_type(job.type)

            # Map queue to priority - extract values from choices to ensure consistency
            priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
            queue_to_priority = {
                "job_critical": priority_values.get("HIGH", "HIGH"),  # HIGH priority
                "job_default": priority_values.get("NORMAL", "NORMAL"),  # NORMAL priority
                "job_low": priority_values.get("LOW", "LOW"),  # LOW priority
            }

            priority = queue_to_priority.get(queue_name, priority_values.get("NORMAL", "NORMAL"))
            priority_source = "inferred_from_job_type"
            details["priority_source"] = "inferred_from_job_type"
            details["priority_from_queue"] = priority
            details["queue_name"] = queue_name

        # Default to NORMAL if still not determined
        if not priority:
            priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
            priority = priority_values.get("NORMAL", "NORMAL")
            priority_source = "default"
            details["priority_source"] = "default"
            warnings.append("Priority not specified, defaulting to NORMAL")

        details["priority"] = priority
        details["priority_source"] = priority_source

        # Validate priority is valid - extract values from choices
        valid_priorities = [choice[0] for choice in JobPriority.choices]
        if priority not in valid_priorities:
            valid_priority_names = [str(p) for p in valid_priorities]
            errors.append(
                f"Job has invalid priority: {priority}. "
                f"Valid priorities are: {', '.join(valid_priority_names)}"
            )
            details["priority_valid"] = False
        else:
            details["priority_valid"] = True

        # Store priority level for other validations
        details["priority_level"] = priority

        details["priority_level_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_priority_assignment(
        self, job: Job, user: User, tenant: Any | None = None
    ) -> ValidationResult:
        """
        Validate priority assignment (user has permission for high priority).

        Validates:
        - User has permission to create HIGH priority jobs (TENANT_ADMIN or platform admin)
        - User has permission to create CRITICAL priority jobs (TENANT_ADMIN or platform admin)
        - Regular users can create LOW and NORMAL priority jobs

        Args:
            job: Job instance to validate
            user: User instance
            tenant: Optional tenant instance

        Returns:
            ValidationResult with priority assignment validation status
        """
        errors = []
        warnings = []
        details = {
            "priority_assignment_validation": "priority_assignment_validation",
            "user_id": str(user.id),
            "user_email": user.email,
        }

        # Get priority level (from previous validation or infer)
        priority = None
        if job.details_json and isinstance(job.details_json, dict):
            priority = job.details_json.get("priority")

        # If not in details_json, infer from job type
        if not priority and job.type:
            from hub.apps.jobs.utils import get_queue_for_job_type

            queue_name = get_queue_for_job_type(job.type)
            # Get priority values from choices to ensure consistency
            priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
            high_val = priority_values.get("HIGH", "HIGH")
            normal_val = priority_values.get("NORMAL", "NORMAL")
            low_val = priority_values.get("LOW", "LOW")
            queue_to_priority = {
                "job_critical": high_val,
                "job_default": normal_val,
                "job_low": low_val,
            }
            priority = queue_to_priority.get(queue_name, normal_val)

        # Default to NORMAL
        if not priority:
            priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
            normal_val = priority_values.get("NORMAL", "NORMAL")
            priority = normal_val

        details["priority"] = priority

        # Check if user is platform admin (has all permissions)
        is_platform_admin = hasattr(user, "is_platform_admin") and user.is_platform_admin
        details["is_platform_admin"] = is_platform_admin

        if is_platform_admin:
            details["priority_assignment_valid"] = True
            details["permission_check"] = "platform_admin"
            return ValidationResult(
                is_valid=True, errors=errors, warnings=warnings, details=details
            )

        # Check user permissions for HIGH and CRITICAL priority jobs
        # Extract values from choices to ensure consistency
        priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
        high_val = priority_values.get("HIGH", "HIGH")
        critical_val = priority_values.get("CRITICAL", "CRITICAL")
        if priority in [high_val, critical_val]:
            # HIGH and CRITICAL priority jobs require TENANT_ADMIN role or platform admin
            has_required_role = False
            if hasattr(user, "has_role"):
                has_required_role = user.has_role("TENANT_ADMIN")
            # Fallback: check user_roles relationship
            elif hasattr(user, "user_roles"):
                role_names = [ur.role.name for ur in user.user_roles.all()]
                has_required_role = "TENANT_ADMIN" in role_names

            details["has_required_role"] = has_required_role
            details["required_role"] = "TENANT_ADMIN"

            if not has_required_role:
                errors.append(
                    f"User {user.email} does not have permission to create {priority} priority jobs. "
                    f"Required role: TENANT_ADMIN"
                )
                details["priority_assignment_valid"] = False
            else:
                details["priority_assignment_valid"] = True
                details["permission_check"] = "tenant_admin"
        else:
            # LOW and NORMAL priority jobs can be created by any user
            details["priority_assignment_valid"] = True
            details["permission_check"] = "any_user"
            details["required_role"] = None

        # Validate tenant context if tenant provided
        if tenant:
            if hasattr(user, "tenant") and user.tenant:
                user_tenant_id = str(user.tenant.id)
                tenant_id = str(tenant.id)
                if user_tenant_id != tenant_id:
                    warnings.append(
                        f"User belongs to tenant {user_tenant_id} but job is for tenant {tenant_id}"
                    )
                    details["tenant_match"] = False
                else:
                    details["tenant_match"] = True
            else:
                warnings.append("User has no tenant association")
                details["tenant_match"] = None

        details["priority_assignment_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_priority_queue(self, job: Job) -> ValidationResult:
        """
        Validate priority queue (priority-based queue ordering).

        Validates:
        - Queue name matches the priority level
        - Priority and queue are consistent
        - Queue assignment is correct for the priority

        Queue mapping:
        - CRITICAL/HIGH priority → job_critical
        - NORMAL priority → job_default
        - LOW priority → job_low

        Args:
            job: Job instance to validate

        Returns:
            ValidationResult with priority queue validation status
        """
        errors = []
        warnings = []
        details = {
            "priority_queue_validation": "priority_queue_validation",
        }

        if not job.type:
            errors.append("Job must have a type for queue validation")
            details["has_job_type"] = False
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, details=details
            )

        details["has_job_type"] = True
        details["job_type"] = job.type

        # Get queue name from job type
        from hub.apps.jobs.utils import get_queue_for_job_type

        queue_name = get_queue_for_job_type(job.type)
        details["queue_name"] = queue_name

        # Get priority (from details_json or inferred)
        priority = None
        if job.details_json and isinstance(job.details_json, dict):
            priority = job.details_json.get("priority")

        # If not in details_json, infer from queue
        if not priority:
            priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
            queue_to_priority = {
                "job_critical": priority_values.get("HIGH", "HIGH"),
                "job_default": priority_values.get("NORMAL", "NORMAL"),
                "job_low": priority_values.get("LOW", "LOW"),
            }
            priority = queue_to_priority.get(queue_name, priority_values.get("NORMAL", "NORMAL"))
            details["priority_inferred"] = True
        else:
            details["priority_inferred"] = False

        details["priority"] = priority

        # Validate queue matches priority
        # Extract values from choices to ensure consistency
        priority_values = {choice[0]: choice[0] for choice in JobPriority.choices}
        critical_val = priority_values.get("CRITICAL", "CRITICAL")
        high_val = priority_values.get("HIGH", "HIGH")
        normal_val = priority_values.get("NORMAL", "NORMAL")
        low_val = priority_values.get("LOW", "LOW")

        priority_to_queue = {
            critical_val: "job_critical",
            high_val: "job_critical",
            normal_val: "job_default",
            low_val: "job_low",
        }

        expected_queue = priority_to_queue.get(priority)
        details["expected_queue"] = expected_queue
        details["actual_queue"] = queue_name

        if expected_queue and expected_queue != queue_name:
            # Check if it's a valid alternative (CRITICAL can use job_critical even if inferred as HIGH)
            if priority == critical_val and queue_name == "job_critical":
                # CRITICAL priority can use job_critical queue (same as HIGH)
                details["queue_match"] = True
                details["queue_match_reason"] = "critical_uses_high_queue"
            elif priority == high_val and queue_name == "job_critical":
                # HIGH priority correctly uses job_critical
                details["queue_match"] = True
                details["queue_match_reason"] = "high_uses_critical_queue"
            else:
                warnings.append(
                    f"Priority {priority} expects queue {expected_queue} but job is in queue {queue_name}. "
                    f"This may indicate a mismatch between priority and queue assignment."
                )
                details["queue_match"] = False
                details["queue_match_reason"] = "mismatch"
        else:
            details["queue_match"] = True
            details["queue_match_reason"] = "matches"

        # Validate queue is valid
        valid_queues = ["job_critical", "job_default", "job_low"]
        if queue_name not in valid_queues:
            errors.append(
                f"Job has invalid queue name: {queue_name}. "
                f"Valid queues are: {', '.join(valid_queues)}"
            )
            details["queue_valid"] = False
        else:
            details["queue_valid"] = True

        details["priority_queue_valid"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )
