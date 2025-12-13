"""
Unit tests for Access Request Workflows

Tests for access request creation, single-step and multi-step approval,
access grant management, and expiration.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus
)
from hub.apps.governance.access_requests import AccessRequestWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AccessRequestWorkflowTest(TestCase):
    """Test AccessRequestWorkflow"""
    
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
        
        self.approver = User.objects.create_user(
            email="approver@example.com",
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
    
    def test_create_access_request_no_approval(self):
        """Test creating access request without approval"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=False
        )
        
        self.assertIsNotNone(request)
        self.assertEqual(request.status, AccessRequestStatus.APPROVED.value)
        self.assertIsNotNone(request.access_granted_at)
        self.assertEqual(request.approved_by, self.user)
    
    def test_create_access_request_with_approval(self):
        """Test creating access request requiring approval"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=True,
            approvers=[str(self.approver.id)]
        )
        
        self.assertIsNotNone(request)
        self.assertEqual(request.status, AccessRequestStatus.PENDING.value)
        self.assertIn(str(self.approver.id), request.approvers)
        self.assertTrue(request.requires_approval)
    
    def test_single_step_approval(self):
        """Test single-step approval workflow"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=True,
            approvers=[str(self.approver.id)]
        )
        
        # Approve request
        approved = AccessRequestWorkflow.approve_access_request(
            access_request_id=str(request.id),
            approved_by_id=str(self.approver.id)
        )
        
        self.assertEqual(approved.status, AccessRequestStatus.APPROVED.value)
        self.assertEqual(approved.approved_by, self.approver)
        self.assertIsNotNone(approved.approved_at)
        self.assertIsNotNone(approved.access_granted_at)
    
    def test_multi_step_approval(self):
        """Test multi-step approval workflow"""
        approver2 = User.objects.create_user(
            email="approver2@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        workflow = [
            {'approvers': [str(self.approver.id)], 'step': 0},
            {'approvers': [str(approver2.id)], 'step': 1}
        ]
        
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=True,
            approval_workflow=workflow
        )
        
        # Approve first step
        approved_step1 = AccessRequestWorkflow.approve_access_request(
            access_request_id=str(request.id),
            approved_by_id=str(self.approver.id),
            step_index=0
        )
        
        self.assertEqual(approved_step1.status, AccessRequestStatus.PENDING.value)
        self.assertEqual(approved_step1.current_approval_step, 1)
        
        # Approve second step (final)
        approved_step2 = AccessRequestWorkflow.approve_access_request(
            access_request_id=str(request.id),
            approved_by_id=str(approver2.id),
            step_index=1
        )
        
        self.assertEqual(approved_step2.status, AccessRequestStatus.APPROVED.value)
        self.assertEqual(approved_step2.approved_by, approver2)
        self.assertIsNotNone(approved_step2.access_granted_at)
    
    def test_reject_access_request(self):
        """Test rejecting access request"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=True,
            approvers=[str(self.approver.id)]
        )
        
        # Reject request
        rejected = AccessRequestWorkflow.reject_access_request(
            access_request_id=str(request.id),
            rejected_by_id=str(self.approver.id),
            rejection_reason="Access not authorized"
        )
        
        self.assertEqual(rejected.status, AccessRequestStatus.REJECTED.value)
        self.assertEqual(rejected.rejected_by, self.approver)
        self.assertIsNotNone(rejected.rejected_at)
        self.assertEqual(rejected.rejection_reason, "Access not authorized")
    
    def test_revoke_access(self):
        """Test revoking granted access"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=False
        )
        
        # Revoke access
        revoked = AccessRequestWorkflow.revoke_access(
            access_request_id=str(request.id),
            revoked_by_id=str(self.approver.id)
        )
        
        self.assertEqual(revoked.status, AccessRequestStatus.REVOKED.value)
    
    def test_check_access_expiration(self):
        """Test access expiration"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=False,
            expires_at=timezone.now() - timedelta(days=1)  # Already expired
        )
        
        # Check expiration
        expired_count = AccessRequestWorkflow.check_access_expiration()
        
        self.assertGreater(expired_count, 0)
        
        # Refresh request
        request.refresh_from_db()
        self.assertEqual(request.status, AccessRequestStatus.EXPIRED.value)
    
    def test_get_user_access_requests(self):
        """Test getting user's access requests"""
        request1 = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Request 1",
            requested_access_type="READ",
            requires_approval=False
        )
        
        request2 = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            dataset_id=str(self.asset.id),  # Different resource
            reason="Request 2",
            requested_access_type="WRITE",
            requires_approval=False
        )
        
        requests = AccessRequestWorkflow.get_user_access_requests(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(requests), 2)
        self.assertIn(request1, requests)
        self.assertIn(request2, requests)
    
    def test_get_pending_approvals(self):
        """Test getting pending approvals for approver"""
        request = AccessRequestWorkflow.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Need access for analysis",
            requested_access_type="READ",
            requires_approval=True,
            approvers=[str(self.approver.id)]
        )
        
        pending = AccessRequestWorkflow.get_pending_approvals(
            approver_id=str(self.approver.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(pending), 1)
        self.assertIn(request, pending)

