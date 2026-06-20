"""
Comprehensive unit tests for AccessRequestViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create, update, destroy)
- Custom actions (approve, reject)
- Filtering (status, asset_id, dataset_id)
- Tenant isolation
- Permission checks (IsAuthenticated, platform admin)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling

All tests use real implementations (no mocks/stubs).
Workflow operations gracefully handle when workflow engine unavailable.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AccessRequestViewSetTest(TestCase):
    """Comprehensive tests for AccessRequestViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create approver
        self.approver = User.objects.create_user(
            email=f"approver-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Grant TENANT_ADMIN role so approver can approve/reject
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.approver, role=admin_role)

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Create another tenant and user for isolation tests
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create assets
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.other_user,
        )

        # Create file
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": []},
            format="CSV",
            version=1,
            created_by=self.user,
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_access_requests_success(self):
        """Test listing access requests successfully"""
        # Create access requests
        request1 = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason 1",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        request2 = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason 2",
            requested_access_type="WRITE",
            status=AccessRequestStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

        # Verify requests are returned
        request_ids = [req["id"] for req in response.data["results"]]
        self.assertIn(str(request1.id), request_ids)
        self.assertIn(str(request2.id), request_ids)

    def test_list_access_requests_tenant_isolation(self):
        """Test that users can only see access requests in their tenant"""
        # Create request for first tenant
        request1 = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        # Create request for other tenant
        request2 = AccessRequest.objects.create(
            tenant=self.other_tenant,
            requested_by=self.other_user,
            asset=self.other_asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(request1.id))
        self.assertNotEqual(response.data["results"][0]["id"], str(request2.id))

    def test_list_access_requests_platform_admin_sees_all(self):
        """Test platform admin can see all access requests"""
        # Create requests for both tenants
        request1 = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        request2 = AccessRequest.objects.create(
            tenant=self.other_tenant,
            requested_by=self.other_user,
            asset=self.other_asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        request_ids = [req["id"] for req in response.data["results"]]
        self.assertIn(str(request1.id), request_ids)
        self.assertIn(str(request2.id), request_ids)

    def test_list_access_requests_filter_by_status(self):
        """Test filtering access requests by status"""
        # Create requests with different statuses
        pending_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Pending reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Approved reason",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.user)

        # Filter by PENDING
        response = self.client.get(
            "/api/v1/governance/access-requests/", {"status": AccessRequestStatus.PENDING}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(pending_request.id))

    def test_list_access_requests_filter_by_asset_id(self):
        """Test filtering access requests by asset_id"""
        # Create requests for different assets
        asset2 = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-2",
            name="Test Asset 2",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        request1 = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Reason 1",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=asset2,
            reason="Reason 2",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        # Filter by asset_id
        response = self.client.get(
            "/api/v1/governance/access-requests/", {"asset_id": str(self.asset.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(request1.id))

    def test_list_access_requests_filter_by_dataset_id(self):
        """Test filtering access requests by dataset_id"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            dataset=self.dataset,
            reason="Dataset reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        # Filter by dataset_id
        response = self.client.get(
            "/api/v1/governance/access-requests/", {"dataset_id": str(self.dataset.id)}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], str(request.id))

    def test_list_access_requests_requires_authentication(self):
        """Test that listing access requests requires authentication"""
        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_access_requests_empty_when_no_requests(self):
        """Test that listing returns empty list when no requests exist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_access_request_success(self):
        """Test retrieving access request successfully"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/governance/access-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(request.id))
        self.assertEqual(response.data["reason"], "Test reason")
        self.assertEqual(response.data["status"], AccessRequestStatus.PENDING)

    def test_retrieve_access_request_tenant_isolation(self):
        """Test that users can only retrieve access requests in their tenant"""
        # Create request for other tenant
        request = AccessRequest.objects.create(
            tenant=self.other_tenant,
            requested_by=self.other_user,
            asset=self.other_asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/governance/access-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_access_request_nonexistent(self):
        """Test retrieving nonexistent access request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/governance/access-requests/{fake_request_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_access_request_requires_authentication(self):
        """Test that retrieving access request requires authentication"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        response = self.client.get(f"/api/v1/governance/access-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== CREATE ENDPOINT TESTS ==========

    def test_create_access_request_success_with_asset(self):
        """Test creating access request successfully with asset"""
        self.client.force_authenticate(user=self.user)

        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,  # noqa: F401
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": str(self.asset.id),
                "reason": "Need access for analysis",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 CREATED, got {response.status_code}: {response.content}",
        )

        self.assertIn("id", response.data)
        self.assertEqual(response.data["reason"], "Need access for analysis")

        # Verify request was created
        request_id = response.data["id"]
        request = AccessRequest.objects.get(id=request_id)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.requested_by, self.user)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ACCESS_REQUEST",
            action="ACCESS_REQUEST_CREATED",
            resource_id=request_id,
        )
        self.assertGreater(audit_events.count(), 0)

    def test_create_access_request_success_with_dataset(self):
        """Test creating access request successfully with dataset"""
        self.client.force_authenticate(user=self.user)

        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,  # noqa: F401
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "dataset_id": str(self.dataset.id),
                "reason": "Need access for analysis",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 CREATED, got {response.status_code}: {response.content}",
        )

    def test_create_access_request_success_with_file(self):
        """Test creating access request successfully with file"""
        self.client.force_authenticate(user=self.user)

        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,  # noqa: F401
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "file_id": str(self.file.id),
                "reason": "Need access for analysis",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 CREATED, got {response.status_code}: {response.content}",
        )

    def test_create_access_request_missing_reason(self):
        """Test creating access request without reason returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": str(self.asset.id),
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format (detail/code or error for backward compatibility)
        if "detail" in response.data:
            self.assertIn("code", response.data)
            self.assertIn("reason", str(response.data.get("detail", "")).lower())
        else:
            # Backward compatibility check
            self.assertIn("reason", str(response.data.get("error", "")).lower())

    def test_create_access_request_missing_resource(self):
        """Test creating access request without asset/dataset/file returns error"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "reason": "Test reason",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format (detail/code or error for backward compatibility)
        error_text = str(response.data.get("detail", response.data.get("error", ""))).lower()
        self.assertIn("asset_id, dataset_id, or file_id", error_text)

    def test_create_access_request_user_without_tenant(self):
        """Test creating access request by user without tenant returns error"""
        # Create user without tenant
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=user_no_tenant)

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": str(self.asset.id),
                "reason": "Test reason",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format (detail/code or error for backward compatibility)
        error_text = str(response.data.get("detail", response.data.get("error", ""))).lower()
        self.assertIn("tenant", error_text)

    def test_create_access_request_requires_authentication(self):
        """Test that creating access request requires authentication"""
        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": str(self.asset.id),
                "reason": "Test reason",
                "requested_access_type": "READ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== APPROVE ACTION TESTS ==========

    def test_approve_access_request_success(self):
        """Test approving access request successfully"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/approve/",
            {"comments": "Approved"},
            format="json",
        )

        # Approve does NOT use workflow — it should always succeed with proper setup
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code}: {response.content}",
        )

        request.refresh_from_db()
        self.assertEqual(request.status, AccessRequestStatus.APPROVED)
        self.assertEqual(request.approved_by, self.approver)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ACCESS_REQUEST",
            action="ACCESS_REQUEST_APPROVED",
            resource_id=str(request.id),
        )
        self.assertGreater(audit_events.count(), 0)

    def test_approve_access_request_not_pending(self):
        """Test approving non-pending access request returns error"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/approve/",
            {"comments": "Approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format (detail/code or error for backward compatibility)
        error_text = str(response.data.get("detail", response.data.get("error", ""))).lower()
        self.assertIn("not pending", error_text)

    def test_approve_access_request_requires_authentication(self):
        """Test that approving access request requires authentication"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/approve/",
            {"comments": "Approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== REJECT ACTION TESTS ==========

    def test_reject_access_request_success(self):
        """Test rejecting access request successfully"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/reject/",
            {"reason": "Not approved"},
            format="json",
        )

        # Reject does NOT use workflow — it should always succeed with proper setup
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code}: {response.content}",
        )

        request.refresh_from_db()
        self.assertEqual(request.status, AccessRequestStatus.REJECTED)
        self.assertEqual(request.rejected_by, self.approver)
        self.assertEqual(request.rejection_reason, "Not approved")

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ACCESS_REQUEST",
            action="ACCESS_REQUEST_REJECTED",
            resource_id=str(request.id),
        )
        self.assertGreater(audit_events.count(), 0)

    def test_reject_access_request_missing_reason(self):
        """Test rejecting access request without reason returns error"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/reject/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format
        self.assertIn("detail", response.data or {})
        self.assertIn("code", response.data or {})
        error_message = str(response.data.get("detail", "")).lower()
        self.assertIn("reason", error_message)

    def test_reject_access_request_not_pending(self):
        """Test rejecting non-pending access request returns error"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/reject/",
            {"reason": "Not approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check standardized error format (detail/code or error for backward compatibility)
        error_text = str(response.data.get("detail", response.data.get("error", ""))).lower()
        self.assertIn("not pending", error_text)

    def test_reject_access_request_requires_authentication(self):
        """Test that rejecting access request requires authentication"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        response = self.client.post(
            f"/api/v1/governance/access-requests/{request.id}/reject/",
            {"reason": "Not approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== EDGE CASES TESTS ==========

    def test_list_access_requests_pagination(self):
        """Test that list endpoint supports pagination"""
        # Create multiple requests
        for i in range(25):
            AccessRequest.objects.create(
                tenant=self.tenant,
                requested_by=self.user,
                asset=self.asset,
                reason=f"Reason {i}",
                requested_access_type="READ",
                status=AccessRequestStatus.PENDING,
            )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/governance/access-requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return paginated results
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_create_access_request_with_expires_at(self):
        """Test creating access request with expiration date"""
        self.client.force_authenticate(user=self.user)

        expires_at = (timezone.now() + timezone.timedelta(days=30)).isoformat()

        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,  # noqa: F401
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": str(self.asset.id),
                "reason": "Test reason",
                "requested_access_type": "READ",
                "expires_at": expires_at,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201 CREATED, got {response.status_code}: {response.content}",
        )

    # ========== ERROR HANDLING TESTS ==========

    def test_create_access_request_nonexistent_asset(self):
        """Test creating access request with nonexistent asset returns error"""
        self.client.force_authenticate(user=self.user)

        fake_asset_id = str(uuid.uuid4())

        response = self.client.post(
            "/api/v1/governance/access-requests/",
            {
                "asset_id": fake_asset_id,
                "reason": "Test reason",
                "requested_access_type": "READ",
            },
            format="json",
        )

        # Service raises ValidationError for nonexistent asset, view returns 400
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f"Expected 400 BAD_REQUEST, got {response.status_code}: {response.content}",
        )

    def test_approve_access_request_nonexistent(self):
        """Test approving nonexistent access request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{fake_request_id}/approve/",
            {"comments": "Approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reject_access_request_nonexistent(self):
        """Test rejecting nonexistent access request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.approver)

        response = self.client.post(
            f"/api/v1/governance/access-requests/{fake_request_id}/reject/",
            {"reason": "Not approved"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== UPDATE ENDPOINT TESTS ==========

    def test_update_access_request_success(self):
        """Test updating access request successfully (PUT)"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Original reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/governance/access-requests/{request.id}/",
            {
                "reason": "Updated reason",
                "requested_access_type": "WRITE",
            },
            format="json",
        )

        # PUT with valid writable fields (reason, requested_access_type) — all
        # required fields are provided; optional fields retain current values.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code}: {response.content}",
        )
        request.refresh_from_db()
        self.assertEqual(response.data["reason"], "Updated reason")
        self.assertEqual(response.data["requested_access_type"], "WRITE")

    def test_partial_update_access_request_success(self):
        """Test partial updating access request successfully (PATCH)"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Original reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/api/v1/governance/access-requests/{request.id}/",
            {
                "reason": "Partially updated reason",
            },
            format="json",
        )

        # PATCH is partial — no fields are required; sending just "reason" is always valid.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 OK, got {response.status_code}: {response.content}",
        )
        request.refresh_from_db()
        self.assertEqual(response.data["reason"], "Partially updated reason")

    def test_update_access_request_tenant_isolation(self):
        """Test that users can only update access requests in their tenant"""
        request = AccessRequest.objects.create(
            tenant=self.other_tenant,
            requested_by=self.other_user,
            asset=self.other_asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/governance/access-requests/{request.id}/",
            {
                "reason": "Updated reason",
                "requested_access_type": "WRITE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_access_request_nonexistent(self):
        """Test updating nonexistent access request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            f"/api/v1/governance/access-requests/{fake_request_id}/",
            {
                "reason": "Updated reason",
                "requested_access_type": "WRITE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_access_request_requires_authentication(self):
        """Test that updating access request requires authentication"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        response = self.client.put(
            f"/api/v1/governance/access-requests/{request.id}/",
            {
                "reason": "Updated reason",
                "requested_access_type": "WRITE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== DESTROY ENDPOINT TESTS ==========

    def test_destroy_access_request_success(self):
        """Test deleting access request successfully"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/governance/access-requests/{request.id}/")

        # ModelViewSet supports destroy
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify request was deleted
        self.assertFalse(AccessRequest.objects.filter(id=request.id).exists())

    def test_destroy_access_request_tenant_isolation(self):
        """Test that users can only delete access requests in their tenant"""
        request = AccessRequest.objects.create(
            tenant=self.other_tenant,
            requested_by=self.other_user,
            asset=self.other_asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/governance/access-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify request still exists
        self.assertTrue(AccessRequest.objects.filter(id=request.id).exists())

    def test_destroy_access_request_nonexistent(self):
        """Test deleting nonexistent access request returns 404"""
        fake_request_id = str(uuid.uuid4())

        self.client.force_authenticate(user=self.user)

        response = self.client.delete(f"/api/v1/governance/access-requests/{fake_request_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_access_request_requires_authentication(self):
        """Test that deleting access request requires authentication"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        response = self.client.delete(f"/api/v1/governance/access-requests/{request.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccessRequestPendingCountTest(TestCase):
    """Tests for the AccessRequestViewSet.pending_count action.

    Admin-only endpoint that surfaces the number of PENDING access requests in
    the caller's tenant (or across all tenants for platform admins) so the UI
    can render a Governance badge without polling the paginated list.
    """

    PENDING_COUNT_URL = "/api/v1/governance/access-requests/pending-count/"

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other {other_uid}",
            slug=f"other-{other_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.regular_user = User.objects.create_user(
            email=f"regular-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.tenant_admin = User.objects.create_user(
            email=f"admin-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_admin, tenant=self.tenant, role=admin_role)

        self.other_admin = User.objects.create_user(
            email=f"otheradmin-{other_uid}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        other_admin_role, _ = Role.objects.get_or_create(
            tenant=self.other_tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(
            user=self.other_admin, tenant=self.other_tenant, role=other_admin_role
        )

        self.platform_admin = User.objects.create_user(
            email=f"platform-{uid}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.regular_user,
        )
        self.other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key=f"asset-{other_uid}",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.other_admin,
        )

    def _make_request(self, tenant, asset, requested_by, status_value):
        return AccessRequest.objects.create(
            tenant=tenant,
            requested_by=requested_by,
            asset=asset,
            reason="r",
            requested_access_type="READ",
            status=status_value,
        )

    def test_pending_count_requires_authentication(self):
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pending_count_forbidden_for_regular_user(self):
        self._make_request(self.tenant, self.asset, self.regular_user, AccessRequestStatus.PENDING)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_count_zero_when_no_requests(self):
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"count": 0})

    def test_pending_count_tenant_admin_sees_only_own_tenant(self):
        self._make_request(self.tenant, self.asset, self.regular_user, AccessRequestStatus.PENDING)
        self._make_request(self.tenant, self.asset, self.regular_user, AccessRequestStatus.PENDING)
        self._make_request(self.tenant, self.asset, self.regular_user, AccessRequestStatus.APPROVED)
        self._make_request(
            self.other_tenant,
            self.other_asset,
            self.other_admin,
            AccessRequestStatus.PENDING,
        )

        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"count": 2})

    def test_pending_count_ignores_non_pending_statuses(self):
        for non_pending in (
            AccessRequestStatus.APPROVED,
            AccessRequestStatus.REJECTED,
            AccessRequestStatus.REVOKED,
        ):
            self._make_request(self.tenant, self.asset, self.regular_user, non_pending)
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"count": 0})

    def test_pending_count_platform_admin_sees_all_tenants(self):
        # Capture baseline to account for stale data from --keepdb runs.
        self.client.force_authenticate(user=self.platform_admin)
        baseline = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(baseline.status_code, status.HTTP_200_OK)
        baseline_count = baseline.data["count"]

        self._make_request(self.tenant, self.asset, self.regular_user, AccessRequestStatus.PENDING)
        self._make_request(
            self.other_tenant,
            self.other_asset,
            self.other_admin,
            AccessRequestStatus.PENDING,
        )
        response = self.client.get(self.PENDING_COUNT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], baseline_count + 2)


class AccessRequestBulkActionsTest(TestCase):
    """223.3.3 — bulk-approve / bulk-reject.

    Per-id atomicity: a single failing row must not abort the others.
    The response must surface both successes and per-id failures.
    """

    URL_BULK_APPROVE = "/api/v1/governance/access-requests/bulk-approve/"
    URL_BULK_REJECT = "/api/v1/governance/access-requests/bulk-reject/"

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.requester = User.objects.create_user(
            email=f"req-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.admin = User.objects.create_user(
            email=f"adm-{uid}@example.com",
            password="x",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )
        UserRole.objects.create(user=self.admin, tenant=self.tenant, role=admin_role)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="A",
            status=AssetStatus.ACTIVE,
            created_by=self.requester,
        )

    def _make(self, status_value=AccessRequestStatus.PENDING):
        return AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.requester,
            asset=self.asset,
            reason="r",
            requested_access_type="READ",
            status=status_value,
        )

    def test_bulk_approve_rejects_empty_ids(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.URL_BULK_APPROVE, {"ids": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_approve_requires_ids_list(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.URL_BULK_APPROVE, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_approve_all_pending(self):
        a = self._make()
        b = self._make()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.URL_BULK_APPROVE,
            {"ids": [str(a.id), str(b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            sorted(response.data["succeeded"]),
            sorted([str(a.id), str(b.id)]),
        )
        self.assertEqual(response.data["failed"], [])
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, AccessRequestStatus.APPROVED)
        self.assertEqual(b.status, AccessRequestStatus.APPROVED)

    def test_bulk_approve_partial_failure_reports_per_id_error(self):
        # ``b`` is already APPROVED and should fail; ``a`` must still succeed.
        a = self._make()
        b = self._make(status_value=AccessRequestStatus.APPROVED)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.URL_BULK_APPROVE,
            {"ids": [str(a.id), str(b.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(str(a.id), response.data["succeeded"])
        failed_ids = [row["id"] for row in response.data["failed"]]
        self.assertIn(str(b.id), failed_ids)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, AccessRequestStatus.APPROVED)
        # `b` was already APPROVED and stays that way.
        self.assertEqual(b.status, AccessRequestStatus.APPROVED)

    def test_bulk_approve_unknown_id_returns_failed_entry(self):
        unknown = str(uuid.uuid4())
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.URL_BULK_APPROVE, {"ids": [unknown]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["succeeded"], [])
        self.assertEqual(len(response.data["failed"]), 1)
        self.assertEqual(response.data["failed"][0]["id"], unknown)

    def test_bulk_reject_requires_reason(self):
        a = self._make()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(self.URL_BULK_REJECT, {"ids": [str(a.id)]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_reject_all_pending(self):
        a = self._make()
        b = self._make()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.URL_BULK_REJECT,
            {"ids": [str(a.id), str(b.id)], "reason": "nope"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            sorted(response.data["succeeded"]),
            sorted([str(a.id), str(b.id)]),
        )
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, AccessRequestStatus.REJECTED)
        self.assertEqual(b.status, AccessRequestStatus.REJECTED)
        self.assertEqual(a.rejection_reason, "nope")

    def test_bulk_endpoints_require_authentication(self):
        response = self.client.post(self.URL_BULK_APPROVE, {"ids": ["x"]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
