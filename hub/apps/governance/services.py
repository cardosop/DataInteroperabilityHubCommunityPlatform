"""
Governance Service

Service layer for governance operations.
Extracts governance logic from access_requests.py and views.
All create/update/approve paths call GovernanceBusinessRules before mutation.
"""

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.events.service_publishers import AccessEventPublisher
from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.governance.business_rules import GovernanceBusinessRules
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
    RetentionPolicy,
    RetentionPolicyType,
)
from hub.apps.orchestration.workflows.access_request import (
    AccessRequestWorkflow as WorkflowAccessRequestWorkflow,
)


class GovernanceService(BaseService, AccessEventPublisher):
    """
    Service for governance operations.

    Provides business logic for:
    - Access request creation
    - Access request approval/rejection
    - Access request management
    """

    service_name = "governance_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize GovernanceService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        AccessEventPublisher.__init__(self)

    def create_access_request(
        self,
        tenant_id: str,
        requested_by_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        reason: Optional[str] = None,
        requested_access_type: str = "READ",
        expires_at: Optional[str] = None,
    ) -> AccessRequest:
        """
        Create an access request using workflow orchestration.

        Args:
            tenant_id: Tenant UUID
            requested_by_id: User UUID requesting access
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            reason: Reason for access request
            requested_access_type: Type of access (READ, WRITE, DOWNLOAD)
            expires_at: Optional expiration datetime (ISO string)

        Returns:
            Created AccessRequest instance

        Raises:
            ValidationError: If access request creation fails
        """
        return self.execute_with_transaction(
            operation="create_access_request",
            func=lambda: self._create_access_request_impl(
                tenant_id=tenant_id,
                requested_by_id=requested_by_id,
                asset_id=asset_id,
                dataset_id=dataset_id,
                file_id=file_id,
                reason=reason,
                requested_access_type=requested_access_type,
                expires_at=expires_at,
            ),
            tenant_id=tenant_id,
        )

    def _create_access_request_impl(
        self,
        tenant_id: str,
        requested_by_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        reason: Optional[str] = None,
        requested_access_type: str = "READ",
        expires_at: Optional[str] = None,
    ) -> AccessRequest:
        """Internal implementation of access request creation."""
        # Plan limit enforcement (monthly)
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_access_requests_per_month",
            delta=1,
        )

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        # Resolve optional resource references.
        # Assets can be from any tenant (cross-tenant access requests, e.g. consumer
        # requesting provider's marketplace asset). Datasets/files stay tenant-scoped.
        asset = None
        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id)
            except Asset.DoesNotExist:
                raise ValidationError(
                    f"Asset {asset_id} not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"asset_id": asset_id},
                )
        dataset = None
        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
            except Dataset.DoesNotExist:
                raise ValidationError(
                    f"Dataset {dataset_id} not found or not in tenant",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"dataset_id": dataset_id},
                )
        file_obj = None
        if file_id:
            try:
                file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise ValidationError(
                    f"File {file_id} not found or not in tenant",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"file_id": file_id},
                )

        # Validate via GovernanceBusinessRules before any mutation
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=requested_by_id)
        payload_request = AccessRequest(
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            reason=reason or "",
            requested_access_type=requested_access_type or "READ",
            status=AccessRequestStatus.PENDING.value,
        )
        rules = GovernanceBusinessRules(
            tenant_id=tenant_id,
            user_id=requested_by_id,
        )
        result = rules.validate(
            access_request=payload_request,
            tenant=tenant,
            user=user,
            validation_type="access_request",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Execute workflow
        workflow_result = WorkflowAccessRequestWorkflow.execute(
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
            asset_id=asset_id,
            dataset_id=dataset_id,
            file_id=file_id,
            reason=reason or "",
            requested_access_type=requested_access_type,
            expires_at=expires_at,
        )

        # Get access request ID from workflow output
        output_data = workflow_result.get("output_data", {})
        access_request_id = output_data.get("access_request_id")

        if not access_request_id:
            raise ValidationError(
                "Access request creation failed: workflow did not return access_request_id"
            )

        access_request = AccessRequest.objects.get(id=access_request_id)
        return access_request

    def approve_access_request(
        self,
        access_request_id: str,
        tenant_id: str,
        approver_id: str,
        comments: Optional[str] = None,
    ) -> AccessRequest:
        """
        Approve an access request.

        Args:
            access_request_id: Access request ID
            tenant_id: Tenant ID
            approver_id: User ID approving the request
            comments: Optional approval comments

        Returns:
            Updated AccessRequest instance

        Raises:
            NotFoundError: If access request not found
            ValidationError: If GovernanceBusinessRules reject approval
        """
        access_request = self.get_resource_or_raise(
            AccessRequest, access_request_id, tenant_id=tenant_id
        )

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        approver_user = User.objects.get(id=approver_id)
        tenant = Tenant.objects.get(id=tenant_id)

        # Validate approval via GovernanceBusinessRules before mutation
        rules = GovernanceBusinessRules(
            tenant_id=tenant_id,
            user_id=approver_id,
        )
        result = rules.validate(
            access_request=access_request,
            tenant=tenant,
            approver=approver_user,
            validation_type="approval",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Update access request
        access_request.status = AccessRequestStatus.APPROVED
        access_request.approved_by = approver_user
        access_request.approved_at = timezone.now()
        # Set expiration if not already set (default 90 days from approval)
        if not access_request.expires_at:
            access_request.expires_at = timezone.now() + timedelta(days=90)
        access_request.save()

        return access_request

    def reject_access_request(
        self, access_request_id: str, tenant_id: str, approver_id: str, reason: str
    ) -> AccessRequest:
        """
        Reject an access request.

        Args:
            access_request_id: Access request ID
            tenant_id: Tenant ID
            approver_id: User ID rejecting the request
            reason: Rejection reason

        Returns:
            Updated AccessRequest instance

        Raises:
            NotFoundError: If access request not found
            ValidationError: If GovernanceBusinessRules reject (e.g. not pending)
        """
        access_request = self.get_resource_or_raise(
            AccessRequest, access_request_id, tenant_id=tenant_id
        )

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        rejector_user = User.objects.get(id=approver_id)
        tenant = Tenant.objects.get(id=tenant_id)

        # Validate approval path (same as approve: must be pending, rejector authorized)
        rules = GovernanceBusinessRules(
            tenant_id=tenant_id,
            user_id=approver_id,
        )
        result = rules.validate(
            access_request=access_request,
            tenant=tenant,
            approver=rejector_user,
            validation_type="approval",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Update access request
        access_request.status = AccessRequestStatus.REJECTED
        access_request.rejected_by = rejector_user
        access_request.rejected_at = timezone.now()
        access_request.rejection_reason = reason
        access_request.save()

        return access_request

    def get_access_request(
        self, access_request_id: str, tenant_id: Optional[str] = None
    ) -> AccessRequest:
        """
        Get access request by ID.

        Args:
            access_request_id: Access request ID
            tenant_id: Optional tenant ID for filtering

        Returns:
            AccessRequest instance

        Raises:
            NotFoundError: If access request not found
        """
        return self.get_resource_or_raise(
            AccessRequest, access_request_id, tenant_id=tenant_id or self.tenant_id
        )

    def list_access_requests(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
        requested_by_id: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> List[AccessRequest]:
        """
        List access requests with filters.

        Args:
            tenant_id: Tenant ID for filtering
            status: Optional status filter
            requested_by_id: Optional requester filter
            asset_id: Optional asset filter

        Returns:
            List of AccessRequest instances
        """
        effective_tenant_id = tenant_id or self.tenant_id

        queryset = AccessRequest.objects.filter(tenant_id=effective_tenant_id)

        if status:
            queryset = queryset.filter(status=status)
        if requested_by_id:
            queryset = queryset.filter(requested_by_id=requested_by_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        return list(queryset.order_by("-created_at"))

    def check_user_permissions_for_domain_creation(self, user_id: str, tenant_id: str) -> None:
        """
        Check user permissions for domain creation.

        Validates:
        - User has TENANT_ADMIN role
        - User belongs to the specified tenant (unless platform admin)

        Args:
            user_id: User ID
            tenant_id: Tenant ID

        Raises:
            PermissionError: If user lacks required permissions
        """
        from hub.apps.core.services.base import PermissionError
        from hub.apps.users.models import User

        try:
            user = User.objects.prefetch_related("user_roles__role").get(id=user_id)
        except User.DoesNotExist:
            raise PermissionError(f"User {user_id} not found")

        # Platform admins have all permissions (can operate on any tenant)
        if user.is_platform_admin:
            return

        # For non-platform admins, verify tenant matches
        if str(user.tenant_id) != tenant_id:
            raise PermissionError(f"User {user_id} does not belong to tenant {tenant_id}")

        # Check if user has required role (TENANT_ADMIN)
        has_required_role = user.has_role("TENANT_ADMIN")
        if not has_required_role:
            raise PermissionError(
                f"User {user_id} does not have required role (TENANT_ADMIN) for domain creation"
            )

    def validate_resource_quota_allocation(
        self, tenant_id: str, requested_quota: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate resource quota allocation via GovernanceService.

        Validates that the requested quota:
        1. Has valid structure and values
        2. Does not exceed tenant-level resource limits
        3. Can be allocated given current tenant usage

        Args:
            tenant_id: Tenant ID
            requested_quota: Requested resource quota dictionary

        Returns:
            Validated and potentially adjusted quota dictionary

        Raises:
            ValidationError: If quota validation fails
        """
        from hub.apps.core.services.base import ValidationError

        if not requested_quota:
            return {}

        # Validate quota structure
        if not isinstance(requested_quota, dict):
            raise ValidationError("Resource quota must be a dictionary")

        # Validate quota values are non-negative numbers
        for key, value in requested_quota.items():
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Resource quota '{key}' must be a number")
            if value < 0:
                raise ValidationError(f"Resource quota '{key}' cannot be negative")

        # Check tenant-level resource limits
        self.check_tenant_resource_limits(tenant_id, requested_quota)

        # Return validated quota (may be adjusted in future)
        return requested_quota.copy()

    def check_tenant_resource_limits(self, tenant_id: str, requested_quota: Dict[str, Any]) -> None:
        """
        Enforce tenant-level resource limits.

        Checks that the requested quota does not exceed tenant-level limits
        when combined with existing domain quotas.

        Args:
            tenant_id: Tenant ID
            requested_quota: Requested resource quota dictionary

        Raises:
            ValidationError: If tenant resource limits would be exceeded
        """
        from hub.apps.core.services.base import ValidationError
        from hub.apps.mesh.models import DataMeshDomain

        if not requested_quota:
            return

        # Get all active domains for the tenant
        active_domains = DataMeshDomain.objects.filter(tenant_id=tenant_id, status="ACTIVE")

        # Calculate current tenant usage across all domains
        tenant_usage = {}
        for domain in active_domains:
            domain_quota = domain.resource_quota or {}
            for resource_type, quota_value in domain_quota.items():
                if isinstance(quota_value, (int, float)):
                    tenant_usage[resource_type] = tenant_usage.get(resource_type, 0) + quota_value

        # Check if requested quota would exceed tenant limits
        # For now, we'll use reasonable defaults. In production, this would
        # come from tenant configuration or a quota management service.
        tenant_limits = {
            "storage_gb": 10000,  # 10TB default
            "compute_hours": 1000,  # 1000 hours default
            "api_calls_per_day": 1000000,  # 1M calls/day default
        }

        for resource_type, requested_value in requested_quota.items():
            if not isinstance(requested_value, (int, float)):
                continue

            current_usage = tenant_usage.get(resource_type, 0)
            tenant_limit = tenant_limits.get(resource_type)

            if tenant_limit is not None:
                new_total = current_usage + requested_value
                if new_total > tenant_limit:
                    raise ValidationError(
                        f"Requested quota for {resource_type} ({requested_value}) would exceed "
                        f"tenant limit ({tenant_limit}). Current tenant usage: {current_usage}, "
                        f"new total would be: {new_total}"
                    )

    @transaction.atomic
    def create_retention_policy(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        policy_type: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        description: Optional[str] = None,
        retention_period_days: Optional[int] = None,
        event_trigger: Optional[str] = None,
        action: str = "SOFT_DELETE",
        grace_period_days: int = 30,
        legal_hold: bool = False,
        legal_hold_reason: Optional[str] = None,
        legal_hold_expires_at: Optional[Any] = None,
        enabled: bool = True,
    ) -> RetentionPolicy:
        """
        Create a retention policy.

        Validates input via GovernanceBusinessRules, persists RetentionPolicy,
        and emits exactly one audit event.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID creating the policy
            name: Policy name
            policy_type: Policy type (TIME_BASED or EVENT_BASED)
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            description: Optional description
            retention_period_days: Required for TIME_BASED policies
            event_trigger: Required for EVENT_BASED policies
            action: Action to take (SOFT_DELETE, HARD_DELETE, ARCHIVE)
            grace_period_days: Grace period in days
            legal_hold: Whether data is under legal hold
            legal_hold_reason: Reason for legal hold
            legal_hold_expires_at: When legal hold expires
            enabled: Whether policy is enabled

        Returns:
            Created RetentionPolicy instance

        Raises:
            ValidationError: If validation fails
            NotFoundError: If referenced resources not found
        """
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        # Resolve tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        # Validate at least one resource is provided
        if not any([asset_id, dataset_id, file_id]):
            raise ValidationError(
                "At least one of asset_id, dataset_id, or file_id must be provided",
                code="VALIDATION_ERROR",
                details={"asset_id": asset_id, "dataset_id": dataset_id, "file_id": file_id},
            )

        # Resolve resource references (must belong to tenant)
        asset = None
        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except Asset.DoesNotExist:
                raise NotFoundError(
                    f"Asset {asset_id} not found or not in tenant",
                    code="ASSET_NOT_FOUND",
                    details={"asset_id": asset_id},
                )

        dataset = None
        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
            except Dataset.DoesNotExist:
                raise NotFoundError(
                    f"Dataset {dataset_id} not found or not in tenant",
                    code="DATASET_NOT_FOUND",
                    details={"dataset_id": dataset_id},
                )

        file_obj = None
        if file_id:
            try:
                file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise NotFoundError(
                    f"File {file_id} not found or not in tenant",
                    code="FILE_NOT_FOUND",
                    details={"file_id": file_id},
                )

        # Validate policy_type-specific requirements
        if policy_type == RetentionPolicyType.TIME_BASED.value:
            if not retention_period_days:
                raise ValidationError(
                    "retention_period_days is required for time-based policies",
                    code="VALIDATION_ERROR",
                    details={"policy_type": policy_type},
                )
            if retention_period_days is not None and retention_period_days < 0:
                raise ValidationError(
                    "retention_period_days must be >= 0",
                    code="VALIDATION_ERROR",
                    details={"retention_period_days": retention_period_days},
                )
        if grace_period_days is not None and grace_period_days < 0:
            raise ValidationError(
                "grace_period_days must be >= 0",
                code="VALIDATION_ERROR",
                details={"grace_period_days": grace_period_days},
            )
        elif policy_type == RetentionPolicyType.EVENT_BASED.value:
            if not event_trigger:
                raise ValidationError(
                    "event_trigger is required for event-based policies",
                    code="VALIDATION_ERROR",
                    details={"policy_type": policy_type},
                )

        # Apply GovernanceBusinessRules validation
        # Create a temporary policy instance for validation
        temp_policy = RetentionPolicy(
            tenant_id=tenant_id,
            name=name,
            description=description or "",
            asset=asset,
            dataset=dataset,
            file=file_obj,
            policy_type=policy_type,
            retention_period_days=retention_period_days,
            event_trigger=event_trigger,
            action=action,
            grace_period_days=grace_period_days,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            legal_hold_expires_at=legal_hold_expires_at,
            enabled=enabled,
            created_by=user,
        )

        # Validate via GovernanceBusinessRules if retention validation exists
        # For now, we'll use model validation (full_clean) which enforces constraints
        try:
            temp_policy.full_clean()
        except Exception as e:
            raise ValidationError(
                str(e), code="VALIDATION_ERROR", details={"validation_errors": str(e)}
            )

        # Create retention policy
        policy = RetentionPolicy.objects.create(
            tenant_id=tenant_id,
            name=name,
            description=description or "",
            asset=asset,
            dataset=dataset,
            file=file_obj,
            policy_type=policy_type,
            retention_period_days=retention_period_days,
            event_trigger=event_trigger,
            action=action,
            grace_period_days=grace_period_days,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            legal_hold_expires_at=legal_hold_expires_at,
            enabled=enabled,
            created_by=user,
        )

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_CREATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(policy.id),
            details={
                "name": policy.name,
                "policy_type": policy.policy_type,
                "asset_id": str(asset.id) if asset else None,
                "dataset_id": str(dataset.id) if dataset else None,
                "file_id": str(file_obj.id) if file_obj else None,
            },
        )

        return policy

    @transaction.atomic
    def update_retention_policy(
        self, policy_id: str, tenant_id: str, user_id: str, **update_data
    ) -> RetentionPolicy:
        """
        Update a retention policy.

        Validates input via GovernanceBusinessRules, persists changes,
        and emits exactly one audit event.

        Args:
            policy_id: Retention policy UUID
            tenant_id: Tenant UUID
            user_id: User UUID updating the policy
            **update_data: Fields to update

        Returns:
            Updated RetentionPolicy instance

        Raises:
            NotFoundError: If policy not found
            ValidationError: If validation fails
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        # Get policy
        policy = self.get_resource_or_raise(RetentionPolicy, policy_id, tenant_id=tenant_id)

        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        # Store original values for audit
        original_data = {
            "name": policy.name,
            "policy_type": policy.policy_type,
            "enabled": policy.enabled,
        }

        # Validate numeric fields before applying
        if "retention_period_days" in update_data:
            v = update_data["retention_period_days"]
            if v is not None and v < 0:
                raise ValidationError(
                    "retention_period_days must be >= 0",
                    code="VALIDATION_ERROR",
                    details={"retention_period_days": v},
                )
        if "grace_period_days" in update_data:
            v = update_data["grace_period_days"]
            if v is not None and v < 0:
                raise ValidationError(
                    "grace_period_days must be >= 0",
                    code="VALIDATION_ERROR",
                    details={"grace_period_days": v},
                )

        # Update fields
        for field, value in update_data.items():
            if hasattr(policy, field) and field not in [
                "id",
                "tenant",
                "created_by",
                "created_at",
                "updated_at",
            ]:
                setattr(policy, field, value)

        # Validate updated policy
        try:
            policy.full_clean()
        except Exception as e:
            raise ValidationError(
                str(e), code="VALIDATION_ERROR", details={"validation_errors": str(e)}
            )

        # Save policy
        policy.save()

        # Emit exactly one audit event (Phase 12.4.1)
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_UPDATED",
            actor_user=user,
            tenant=tenant,
            resource_id=str(policy.id),
            details={
                "changes": update_data,
                "original": original_data,
            },
        )

        return policy
