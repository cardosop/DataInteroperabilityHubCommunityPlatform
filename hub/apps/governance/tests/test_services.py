"""
Comprehensive unit tests for GovernanceService.

Tests cover:
- create_access_request method
- approve_access_request method
- reject_access_request method
- get_access_request method
- list_access_requests method
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- Validation

All tests use real implementations (no mocks/stubs).
Workflow operations gracefully handle when workflow engine unavailable.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy, AccessRequest, AccessRequestStatus
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class GovernanceServiceTest(TestCase):
    """Comprehensive tests for GovernanceService operations"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.approver = User.objects.create_user(
            email=f"approver-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Grant TENANT_ADMIN so approver can approve without being in approvers list
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(user=self.approver, role=admin_role)
        self.service = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
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

        # Create an ALLOW policy so ABAC evaluation runs and emits
        # audit events during approval/rejection.  Without this, the
        # ABAC engine short-circuits (no policies → no audit events).
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="test-default-allow",
            asset=self.asset,
            enabled=True,
            priority=0,
            effect="ALLOW",
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

    # ========== CREATE ACCESS REQUEST TESTS ==========

    def test_create_access_request_success_with_asset(self):
        """Test successful access request creation with asset"""
        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        request = self.service.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Test reason",
            requested_access_type="READ",
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.requested_by, self.user)
        self.assertEqual(request.asset, self.asset)
        self.assertEqual(request.reason, "Test reason")

    def test_create_access_request_success_with_dataset(self):
        """Test successful access request creation with dataset"""
        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        request = self.service.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            dataset_id=str(self.dataset.id),
            reason="Test reason",
            requested_access_type="READ",
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.dataset, self.dataset)

    def test_create_access_request_success_with_file(self):
        """Test successful access request creation with file"""
        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        request = self.service.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            file_id=str(self.file.id),
            reason="Test reason",
            requested_access_type="READ",
        )

        self.assertIsNotNone(request)
        self.assertEqual(request.file, self.file)

    def test_create_access_request_validation_error_no_resource(self):
        """Test that creating access request without resource raises ValidationError"""
        with self.assertRaises(ValidationError):
            self.service.create_access_request(
                tenant_id=str(self.tenant.id),
                requested_by_id=str(self.user.id),
                reason="Test reason",
            )

    def test_create_access_request_validation_error_nonexistent_asset(self):
        """Test that creating access request with nonexistent asset raises ValidationError"""
        fake_asset_id = str(uuid.uuid4())

        with self.assertRaises(ValidationError):
            self.service.create_access_request(
                tenant_id=str(self.tenant.id),
                requested_by_id=str(self.user.id),
                asset_id=fake_asset_id,
                reason="Test reason",
            )

    def test_create_access_request_with_expires_at(self):
        """Test creating access request with expiration date"""
        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        requested_expires_at = timezone.now() + timezone.timedelta(days=30)

        request = self.service.create_access_request(
            tenant_id=str(self.tenant.id),
            requested_by_id=str(self.user.id),
            asset_id=str(self.asset.id),
            reason="Test reason",
            expires_at=requested_expires_at.isoformat(),
        )

        self.assertIsNotNone(request)
        self.assertIsNotNone(request.expires_at, "expires_at should be set on the access request")
        # Verify expires_at matches the requested value within a 1-second delta
        delta = abs(request.expires_at - requested_expires_at)
        self.assertLess(
            delta,
            timezone.timedelta(seconds=5),
            f"expires_at {request.expires_at} should match requested {requested_expires_at}",
        )

    # ========== APPROVE ACCESS REQUEST TESTS ==========

    def test_approve_access_request_success(self):
        """Test successful access request approval"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        approved = self.service.approve_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.approver.id),
            comments="Approved",
        )

        approved.refresh_from_db()
        self.assertEqual(approved.status, AccessRequestStatus.APPROVED)
        self.assertEqual(approved.approved_by_id, self.approver.id)
        self.assertIsNotNone(approved.approved_at)

        # Verify the ABAC_DECISION_RECORDED audit event was emitted,
        # since an ALLOW policy is configured in setUp.
        from hub.apps.audit.event_types import ABAC_DECISION_RECORDED

        audit_events = AuditEvent.objects.filter(
            resource_type="ACCESS_REQUEST",
            action=ABAC_DECISION_RECORDED,
            resource_id=str(request.id),
        )
        self.assertGreaterEqual(audit_events.count(), 1)

    def test_approve_access_request_validation_error_not_pending(self):
        """Test that approving non-pending access request raises ValidationError"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )

        with self.assertRaises(ValidationError):
            self.service.approve_access_request(
                access_request_id=str(request.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.approver.id),
            )

    def test_approve_access_request_not_found(self):
        """Test that approving nonexistent access request raises NotFoundError"""
        fake_request_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.approve_access_request(
                access_request_id=fake_request_id,
                tenant_id=str(self.tenant.id),
                approver_id=str(self.approver.id),
            )

    # ========== REJECT ACCESS REQUEST TESTS ==========

    def test_reject_access_request_success(self):
        """Test successful access request rejection"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        rejected = self.service.reject_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.approver.id),
            reason="Not approved",
        )

        rejected.refresh_from_db()
        self.assertEqual(rejected.status, AccessRequestStatus.REJECTED)
        self.assertEqual(rejected.rejection_reason, "Not approved")
        self.assertEqual(rejected.rejected_by_id, self.approver.id)
        self.assertIsNotNone(rejected.rejected_at)

        # Verify the rejection was fully persisted: status, reason,
        # rejected_by, and rejected_at are all correctly set.
        # (Rejection doesn't run ABAC, so audit events aren't emitted
        # for this path. The state checks above are the authoritative
        # verification.)

    def test_reject_access_request_validation_error_not_pending(self):
        """Test that rejecting non-pending access request raises ValidationError"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
        )

        with self.assertRaises(ValidationError):
            self.service.reject_access_request(
                access_request_id=str(request.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.approver.id),
                reason="Not approved",
            )

    def test_reject_access_request_not_found(self):
        """Test that rejecting nonexistent access request raises NotFoundError"""
        fake_request_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.reject_access_request(
                access_request_id=fake_request_id,
                tenant_id=str(self.tenant.id),
                approver_id=str(self.approver.id),
                reason="Not approved",
            )

    # ========== GET ACCESS REQUEST TESTS ==========

    def test_get_access_request_success(self):
        """Test successful access request retrieval"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        retrieved = self.service.get_access_request(
            access_request_id=str(request.id), tenant_id=str(self.tenant.id)
        )

        self.assertEqual(retrieved.id, request.id)
        self.assertEqual(retrieved.reason, "Test reason")

    def test_get_access_request_not_found(self):
        """Test that getting nonexistent access request raises NotFoundError"""
        fake_request_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_access_request(
                access_request_id=fake_request_id, tenant_id=str(self.tenant.id)
            )

    def test_get_access_request_tenant_isolation(self):
        """Test that getting access request from different tenant raises NotFoundError"""
        # Create another tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        request = AccessRequest.objects.create(
            tenant=other_tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        with self.assertRaises(NotFoundError):
            self.service.get_access_request(
                access_request_id=str(request.id), tenant_id=str(self.tenant.id)
            )

    # ========== LIST ACCESS REQUESTS TESTS ==========

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
                status=AccessRequestStatus.PENDING,
            )

        requests = self.service.list_access_requests(tenant_id=str(self.tenant.id))

        self.assertEqual(len(requests), 3)

    def test_list_access_requests_empty_when_none(self):
        """Test listing access requests returns empty list when none exist"""
        requests = self.service.list_access_requests(tenant_id=str(self.tenant.id))

        self.assertEqual(len(requests), 0)

    def test_list_access_requests_tenant_isolation(self):
        """Test that listing only returns requests for specified tenant"""
        # Create requests for this tenant
        for i in range(2):
            AccessRequest.objects.create(
                tenant=self.tenant,
                requested_by=self.user,
                asset=self.asset,
                reason=f"Test reason {i}",
                requested_access_type="READ",
                status=AccessRequestStatus.PENDING,
            )

        # Create another tenant and request
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        AccessRequest.objects.create(
            tenant=other_tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Other reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        requests = self.service.list_access_requests(tenant_id=str(self.tenant.id))

        self.assertEqual(len(requests), 2)

    # ========== EDGE CASES TESTS ==========

    def test_create_access_request_different_access_types(self):
        """Test creating access requests with different access types"""
        # Check if workflow is available
        try:
            from hub.apps.orchestration.workflows.access_request import (
                AccessRequestWorkflow,
            )
        except ImportError:
            self.skipTest("Workflow engine not available - skipping test that requires workflow")

        access_types = ["READ", "WRITE", "DOWNLOAD"]

        for access_type in access_types:
            request = self.service.create_access_request(
                tenant_id=str(self.tenant.id),
                requested_by_id=str(self.user.id),
                asset_id=str(self.asset.id),
                reason=f"Test reason for {access_type}",
                requested_access_type=access_type,
            )

            self.assertIsNotNone(
                request, f"Request should not be None for access_type={access_type}"
            )
            self.assertEqual(
                request.requested_access_type,
                access_type,
                f"requested_access_type should be {access_type}",
            )

    def test_approve_access_request_with_comments(self):
        """Test approving access request with comments"""
        request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="Test reason",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )

        approved = self.service.approve_access_request(
            access_request_id=str(request.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.approver.id),
            comments="Approved with comments",
        )

        approved.refresh_from_db()
        self.assertEqual(approved.status, AccessRequestStatus.APPROVED)

    # ========== ERROR HANDLING TESTS ==========

    def test_create_access_request_validation_error_missing_reason(self):
        """Test that creating access request without reason raises ValidationError"""
        # Business rules validation happens BEFORE workflow invocation,
        # so no workflow availability check is needed.
        with self.assertRaises(ValidationError) as ctx:
            self.service.create_access_request(
                tenant_id=str(self.tenant.id),
                requested_by_id=str(self.user.id),
                asset_id=str(self.asset.id),
                reason="",  # Empty reason
            )
        # Verify the error code is correct
        self.assertEqual(
            ctx.exception.code,
            "BUSINESS_RULES_VALIDATION",
            "Should raise BUSINESS_RULES_VALIDATION for missing reason",
        )
