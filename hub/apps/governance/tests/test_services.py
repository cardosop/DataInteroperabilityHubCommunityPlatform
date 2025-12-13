"""
Unit tests for GovernanceService.

Tests cover all service methods with 100% coverage target.
"""
import pytest
from django.test import TestCase
from unittest.mock import patch, Mock

from hub.apps.governance.services import GovernanceService
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus


pytestmark = pytest.mark.django_db(transaction=True)


class GovernanceServiceTest(TestCase):
    """Test GovernanceService operations"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.approver = User.objects.create_user(
            email="approver@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.service = GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        
        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )
    
    def test_create_access_request_success(self):
        """Test successful access request creation"""
        with patch('hub.apps.governance.services.WorkflowAccessRequestWorkflow') as mock_workflow:
            mock_workflow.execute.return_value = {
                "output_data": {
                    "access_request_id": "test-id"
                }
            }
            
            # Mock AccessRequest.objects.get
            mock_request = Mock()
            mock_request.id = "test-id"
            with patch('hub.apps.governance.services.AccessRequest.objects.get', return_value=mock_request):
                request = self.service.create_access_request(
                    tenant_id=str(self.tenant.id),
                    requested_by_id=str(self.user.id),
                    asset_id=str(self.asset.id),
                    reason="Test reason"
                )
                
                self.assertIsNotNone(request)
    
    def test_approve_access_request_success(self):
        """Test successful access request approval"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING
        )
        
        approved = self.service.approve_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.approver.id),
            comments="Approved"
        )
        
        approved.refresh_from_db()
        self.assertEqual(approved.status, AccessRequestStatus.APPROVED)
        self.assertEqual(approved.approved_by_id, self.approver.id)
    
    def test_reject_access_request_success(self):
        """Test successful access request rejection"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING
        )
        
        rejected = self.service.reject_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.approver.id),
            reason="Not approved"
        )
        
        rejected.refresh_from_db()
        self.assertEqual(rejected.status, AccessRequestStatus.REJECTED)
        self.assertEqual(rejected.rejection_reason, "Not approved")
    
    def test_get_access_request_success(self):
        """Test successful access request retrieval"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING
        )
        
        retrieved = self.service.get_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(retrieved.id, request.id)
    
    def test_list_access_requests_success(self):
        """Test successful access request listing"""
        # Create multiple requests
        for i in range(3):
            AccessRequest.objects.create(
                tenant=self.tenant,
                requested_by=self.user,
                asset=self.asset,
                reason=f"Test reason {i}",
                requested_access_type="READ",
                status=AccessRequestStatus.PENDING
            )
        
        requests = self.service.list_access_requests(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertEqual(len(requests), 3)

