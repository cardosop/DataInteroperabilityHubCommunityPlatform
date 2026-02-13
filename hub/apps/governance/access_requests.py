"""
Access Request Workflows

Handles access request creation, approval workflows, and access grant management.
"""
from typing import List, Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
import structlog

from .models import (
    AccessRequest,
    AccessRequestStatus
)

logger = structlog.get_logger(__name__)


class AccessRequestWorkflow:
    """
    Manages access request workflows.
    
    This class now delegates to the workflow engine-based implementation
    for orchestrated access request processing.
    
    Supports:
    - Single-step approval
    - Multi-step approval workflows
    - Access grant management
    - Access expiration
    - Auto-classification
    - Approval routing
    - Timeout handling
    - Escalation logic
    """
    
    @staticmethod
    @transaction.atomic
    def create_access_request(
        tenant_id: str,
        requested_by_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        reason: str = None,
        requested_access_type: str = "READ",
        requires_approval: bool = True,
        approvers: Optional[List[str]] = None,
        approval_workflow: Optional[List[Dict[str, Any]]] = None,
        expires_at: Optional[timezone.datetime] = None
    ) -> AccessRequest:
        """
        Create an access request using the workflow engine.
        
        Args:
            tenant_id: Tenant UUID
            requested_by_id: User UUID requesting access
            asset_id: Asset UUID (optional)
            dataset_id: Dataset UUID (optional)
            file_id: File UUID (optional)
            reason: Reason for access request
            requested_access_type: Type of access (READ, WRITE, DOWNLOAD)
            requires_approval: Whether approval is required (workflow will determine based on classification)
            approvers: List of approver user IDs (for manual override, workflow will route automatically)
            approval_workflow: Multi-step approval workflow (for manual override, workflow will determine)
            expires_at: When access expires (optional)
        
        Returns:
            AccessRequest instance
        """
        from hub.apps.orchestration.workflows.access_request import AccessRequestWorkflow as WorkflowAccessRequestWorkflow
        
        # Convert expires_at to ISO string if provided
        expires_at_str = None
        if expires_at:
            expires_at_str = expires_at.isoformat()
        
        # Execute workflow
        try:
            workflow_result = WorkflowAccessRequestWorkflow.execute(
                tenant_id=tenant_id,
                requested_by_id=requested_by_id,
                asset_id=asset_id,
                dataset_id=dataset_id,
                file_id=file_id,
                reason=reason or "",
                requested_access_type=requested_access_type,
                expires_at=expires_at_str,
                requires_approval=requires_approval,
            )
            
            # Get access request ID from workflow output
            output_data = workflow_result.get("output_data", {})
            access_request_id = output_data.get("access_request_id")
            
            if access_request_id:
                access_request = AccessRequest.objects.get(id=access_request_id)
                
                # Override with manual approvers/workflow if provided (for backward compatibility)
                if approvers or approval_workflow:
                    if approval_workflow:
                        access_request.approval_workflow = approval_workflow
                    if approvers:
                        access_request.approvers = approvers
                    access_request.requires_approval = requires_approval
                    access_request.save()
                
                return access_request
            else:
                raise ValueError("Workflow did not return access_request_id")
                
        except Exception as e:
            logger.error(
                "Failed to create access request via workflow",
                tenant_id=tenant_id,
                requested_by_id=requested_by_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    @staticmethod
    @transaction.atomic
    def approve_access_request(
        access_request_id: str,
        approved_by_id: str,
        step_index: Optional[int] = None
    ) -> AccessRequest:
        """
        Approve an access request (single-step or multi-step).
        
        Delegates to workflow-based implementation.
        
        Args:
            access_request_id: AccessRequest UUID
            approved_by_id: User UUID approving
            step_index: Step index for multi-step approval (optional)
        
        Returns:
            Updated AccessRequest instance
        """
        from hub.apps.orchestration.workflows.access_request import AccessRequestWorkflow as WorkflowAccessRequestWorkflow
        
        return WorkflowAccessRequestWorkflow.approve_access_request(
            access_request_id=access_request_id,
            approved_by_id=approved_by_id,
            step_index=step_index
        )
    
    @staticmethod
    @transaction.atomic
    def reject_access_request(
        access_request_id: str,
        rejected_by_id: str,
        rejection_reason: str
    ) -> AccessRequest:
        """
        Reject an access request.
        
        Delegates to workflow-based implementation.
        
        Args:
            access_request_id: AccessRequest UUID
            rejected_by_id: User UUID rejecting
            rejection_reason: Reason for rejection
        
        Returns:
            Updated AccessRequest instance
        """
        from hub.apps.orchestration.workflows.access_request import AccessRequestWorkflow as WorkflowAccessRequestWorkflow
        
        return WorkflowAccessRequestWorkflow.reject_access_request(
            access_request_id=access_request_id,
            rejected_by_id=rejected_by_id,
            rejection_reason=rejection_reason
        )
    
    @staticmethod
    @transaction.atomic
    def revoke_access(
        access_request_id: str,
        revoked_by_id: str
    ) -> AccessRequest:
        """
        Revoke granted access.
        
        Args:
            access_request_id: AccessRequest UUID
            revoked_by_id: User UUID revoking
        
        Returns:
            Updated AccessRequest instance
        """
        access_request = AccessRequest.objects.get(id=access_request_id)
        
        if access_request.status != AccessRequestStatus.APPROVED.value:
            raise ValueError(f"Access request is not approved (status: {access_request.status})")
        
        access_request.status = AccessRequestStatus.REVOKED.value
        access_request.save()
        
        return access_request
    
    @staticmethod
    def check_access_expiration():
        """
        Check and expire access requests that have passed their expiration date.
        
        Returns:
            Number of expired requests
        """
        now = timezone.now()
        
        expired_requests = AccessRequest.objects.filter(
            status=AccessRequestStatus.APPROVED.value,
            expires_at__lte=now
        )
        
        count = expired_requests.update(
            status=AccessRequestStatus.EXPIRED.value
        )
        
        return count
    
    @staticmethod
    def get_user_access_requests(
        user_id: str,
        tenant_id: Optional[str] = None,
        status: Optional[AccessRequestStatus] = None
    ) -> List[AccessRequest]:
        """
        Get access requests for a user.
        
        Args:
            user_id: User UUID
            tenant_id: Optional tenant ID to filter by
            status: Optional status to filter by
        
        Returns:
            List of AccessRequest instances
        """
        queryset = AccessRequest.objects.filter(requested_by_id=user_id)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if status:
            queryset = queryset.filter(status=status.value)
        
        return list(queryset.order_by('-created_at'))
    
    @staticmethod
    def get_pending_approvals(
        approver_id: str,
        tenant_id: Optional[str] = None
    ) -> List[AccessRequest]:
        """
        Get pending access requests requiring approval from a user.
        
        Args:
            approver_id: Approver user UUID
            tenant_id: Optional tenant ID to filter by
        
        Returns:
            List of AccessRequest instances
        """
        queryset = AccessRequest.objects.filter(
            status=AccessRequestStatus.PENDING.value,
            requires_approval=True
        )
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Filter by approver
        # Check if user is in approvers list or in current step approvers
        from django.db.models import Q
        
        queryset = queryset.filter(
            Q(approvers__contains=[approver_id]) |
            Q(approval_workflow__contains=[{'approvers': [approver_id]}])
        )
        
        return list(queryset.order_by('-created_at'))

