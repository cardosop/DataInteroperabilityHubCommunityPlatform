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

