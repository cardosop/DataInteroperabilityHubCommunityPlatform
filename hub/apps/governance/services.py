"""
Governance Service

Service layer for governance operations.
Extracts governance logic from access_requests.py and views.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone

from hub.apps.core.services.base import BaseService, NotFoundError
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.orchestration.workflows.access_request import AccessRequestWorkflow as WorkflowAccessRequestWorkflow
from hub.apps.core.events.service_publishers import AccessEventPublisher


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
        expires_at: Optional[str] = None
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
                expires_at=expires_at
            ),
            tenant_id=tenant_id
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
        expires_at: Optional[str] = None
    ) -> AccessRequest:
        """Internal implementation of access request creation."""
        # Execute workflow
        workflow_result = WorkflowAccessRequestWorkflow.execute(
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
            asset_id=asset_id,
            dataset_id=dataset_id,
            file_id=file_id,
            reason=reason or "",
            requested_access_type=requested_access_type,
            expires_at=expires_at
        )

        # Get access request ID from workflow output
        output_data = workflow_result.get("output_data", {})
        access_request_id = output_data.get("access_request_id")

        if not access_request_id:
            from hub.apps.core.services.base import ValidationError
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
        comments: Optional[str] = None
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
        """
        access_request = self.get_resource_or_raise(
            AccessRequest,
            access_request_id,
            tenant_id=tenant_id
        )

        # Update access request
        from hub.apps.users.models import User
        approver_user = User.objects.get(id=approver_id)
        access_request.status = AccessRequestStatus.APPROVED
        access_request.approved_by = approver_user
        access_request.approved_at = timezone.now()
        # Note: approval_comments field doesn't exist in AccessRequest model
        # Comments would need to be stored in metadata_json if needed
        access_request.save()

        return access_request

    def reject_access_request(
        self,
        access_request_id: str,
        tenant_id: str,
        approver_id: str,
        reason: str
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
        """
        access_request = self.get_resource_or_raise(
            AccessRequest,
            access_request_id,
            tenant_id=tenant_id
        )

        # Update access request
        from hub.apps.users.models import User
        rejector_user = User.objects.get(id=approver_id)
        access_request.status = AccessRequestStatus.REJECTED
        access_request.rejected_by = rejector_user
        access_request.rejected_at = timezone.now()
        access_request.rejection_reason = reason
        access_request.save()

        return access_request

    def get_access_request(
        self,
        access_request_id: str,
        tenant_id: Optional[str] = None
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
            AccessRequest,
            access_request_id,
            tenant_id=tenant_id or self.tenant_id
        )

    def list_access_requests(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
        requested_by_id: Optional[str] = None,
        asset_id: Optional[str] = None
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

        return list(queryset.order_by('-created_at'))

    def check_user_permissions_for_domain_creation(
        self,
        user_id: str,
        tenant_id: str
    ) -> None:
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
        from hub.apps.users.models import User
        from hub.apps.core.services.base import PermissionError

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise PermissionError(
                f"User {user_id} not found"
            )

        # Platform admins have all permissions (can operate on any tenant)
        if user.is_platform_admin:
            return

        # For non-platform admins, verify tenant matches
        if str(user.tenant_id) != tenant_id:
            raise PermissionError(
                f"User {user_id} does not belong to tenant {tenant_id}"
            )

        # Check if user has required role (TENANT_ADMIN)
        has_required_role = user.has_role("TENANT_ADMIN")
        if not has_required_role:
            raise PermissionError(
                f"User {user_id} does not have required role (TENANT_ADMIN) for domain creation"
            )

    def validate_resource_quota_allocation(
        self,
        tenant_id: str,
        requested_quota: Dict[str, Any]
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

    def check_tenant_resource_limits(
        self,
        tenant_id: str,
        requested_quota: Dict[str, Any]
    ) -> None:
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
        active_domains = DataMeshDomain.objects.filter(
            tenant_id=tenant_id,
            status="ACTIVE"
        )

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

