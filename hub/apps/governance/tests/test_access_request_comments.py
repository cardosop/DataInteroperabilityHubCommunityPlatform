"""
Phase 272.1 — AccessRequestComment tests.

Covers:
* Comment persists with approve
* Comment persists with reject
* Standalone comment without status change
* Empty comment body rejected (400)
* Tenant isolation (tenant A cannot see tenant B's comments)
* Comment list renders chronologically
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _create_tenant(name_prefix="AC", slug_prefix=None):
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    slug = slug_prefix or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{name_prefix}-{slug}",
        slug=f"{slug}-{slug}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _create_user(tenant, email_prefix="user"):
    sfx = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{email_prefix}-{sfx}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _create_asset(tenant, created_by, key_prefix="asset"):
    sfx = uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"{key_prefix}-{sfx}",
        name=f"Test Asset {sfx}",
        status=AssetStatus.ACTIVE,
        created_by=created_by,
    )


def _create_access_request(tenant, requested_by, asset, status_val=AccessRequestStatus.PENDING):
    return AccessRequest.objects.create(
        tenant=tenant,
        requested_by=requested_by,
        asset=asset,
        reason="Test access request",
        requested_access_type="READ",
        status=status_val,
    )


def _make_admin(tenant, user):
    """Grant TENANT_ADMIN role to a user."""
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant Administrator"},
    )
    UserRole.objects.get_or_create(user=user, role=role, tenant=tenant)


# ===========================================================================
# 1. Comment persistence with approve / reject
# ===========================================================================


class TestCommentPersistsWithApprove(TestCase):
    """When approve is called with a non-empty comments body, an
    AccessRequestComment row is created in the same transaction."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _create_tenant()
        self.requester = _create_user(self.tenant, "req")
        self.approver = _create_user(self.tenant, "approver")
        # Give approver TENANT_ADMIN role so they can approve.
        self.asset = _create_asset(self.tenant, self.requester)
        self.access_request = _create_access_request(
            self.tenant, self.requester, self.asset,
        )
        _make_admin(self.tenant, self.approver)
        self.client.force_authenticate(user=self.approver)

    def test_approve_with_comments_creates_comment_row(self):
        from hub.apps.governance.models import AccessRequestComment

        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/approve/",
            data={"comments": "LGTM, approved."},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        comments = AccessRequestComment.objects.filter(
            access_request=self.access_request,
        ).order_by("created_at")
        assert len(comments) == 1
        assert comments[0].body == "LGTM, approved."
        assert comments[0].author == self.approver
        assert comments[0].tenant == self.tenant

    def test_approve_without_comments_does_not_create_comment(self):
        from hub.apps.governance.models import AccessRequestComment

        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/approve/",
            data={},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        assert not AccessRequestComment.objects.filter(
            access_request=self.access_request,
        ).exists()


class TestCommentPersistsWithReject(TestCase):
    """When reject is called with comments, a comment row is created."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _create_tenant()
        self.requester = _create_user(self.tenant, "req")
        self.rejecter = _create_user(self.tenant, "rejecter")
        self.asset = _create_asset(self.tenant, self.requester)
        self.access_request = _create_access_request(
            self.tenant, self.requester, self.asset,
        )
        _make_admin(self.tenant, self.rejecter)
        self.client.force_authenticate(user=self.rejecter)

    def test_reject_with_comments_creates_comment_row(self):
        from hub.apps.governance.models import AccessRequestComment

        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/reject/",
            data={"reason": "Insufficient justification", "comments": "Please provide more detail."},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        comments = AccessRequestComment.objects.filter(
            access_request=self.access_request,
        ).order_by("created_at")
        assert len(comments) == 1
        assert comments[0].body == "Please provide more detail."


# ===========================================================================
# 2. Standalone comment (no status change)
# ===========================================================================


class TestStandaloneComment(TestCase):
    """POST /api/v1/governance/access-requests/{id}/comments/ creates a comment
    without changing the access request status."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = _create_tenant()
        self.user = _create_user(self.tenant, "commenter")
        self.asset = _create_asset(self.tenant, self.user)
        self.access_request = _create_access_request(
            self.tenant, self.user, self.asset,
        )
        self.client.force_authenticate(user=self.user)

    def test_standalone_comment_created(self):
        from hub.apps.governance.models import AccessRequestComment

        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
            data={"body": "Checking on this request."},
            format="json",
        )
        assert resp.status_code == 201, resp.content

        # Verify comment saved.
        comments = AccessRequestComment.objects.filter(
            access_request=self.access_request,
        )
        assert comments.count() == 1
        assert comments.first().body == "Checking on this request."
        assert comments.first().author == self.user

        # Status must NOT have changed.
        self.access_request.refresh_from_db()
        assert self.access_request.status == AccessRequestStatus.PENDING

    def test_standalone_comment_empty_body_rejected(self):
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
            data={"body": ""},
            format="json",
        )
        assert resp.status_code == 400, resp.content

    def test_standalone_comment_list_chronological(self):
        from hub.apps.governance.models import AccessRequestComment

        # Create two comments.
        AccessRequestComment.objects.create(
            tenant=self.tenant,
            access_request=self.access_request,
            author=self.user,
            body="First comment.",
        )
        AccessRequestComment.objects.create(
            tenant=self.tenant,
            access_request=self.access_request,
            author=self.user,
            body="Second comment.",
        )

        resp = self.client.get(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
        )
        assert resp.status_code == 200, resp.content
        data = resp.data
        assert len(data) == 2
        # Chronological = oldest first.
        assert data[0]["body"] == "First comment."
        assert data[1]["body"] == "Second comment."

    def test_standalone_comment_requires_authentication(self):
        """POST to comments endpoint without auth returns 401."""
        # Force client to be unauthenticated
        self.client.logout()
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
            data={"body": "test"},
            format="json",
        )
        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated comment POST, got {resp.status_code}: {resp.content}"
        )

    def test_standalone_comment_missing_body_field(self):
        """POST to comments endpoint without 'body' key returns 400."""
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
            data={},  # No 'body' key at all
            format="json",
        )
        assert resp.status_code == 400, (
            f"Expected 400 for missing body field, got {resp.status_code}: {resp.content}"
        )
        error_text = str(resp.data).lower()
        assert "body" in error_text, (
            f"Error response should mention 'body', got: {resp.content}"
        )

    def test_standalone_comment_malformed_json(self):
        """POST to comments endpoint with malformed JSON returns 400."""
        resp = self.client.post(
            f"/api/v1/governance/access-requests/{self.access_request.id}/comments/",
            data="not valid json {{{",
            content_type="application/json",
        )
        assert resp.status_code == 400, (
            f"Expected 400 for malformed JSON, got {resp.status_code}: {resp.content}"
        )


# ===========================================================================
# 3. Tenant isolation
# ===========================================================================


class TestCommentTenantIsolation(TestCase):
    """Tenant A's comments are not visible to tenant B."""

    def setUp(self):
        self.client = APIClient()
        self.tenant_a = _create_tenant(name_prefix="TA")
        self.tenant_b = _create_tenant(name_prefix="TB")
        self.user_a = _create_user(self.tenant_a, "usera")
        self.user_b = _create_user(self.tenant_b, "userb")
        self.asset_a = _create_asset(self.tenant_a, self.user_a)
        self.asset_b = _create_asset(self.tenant_b, self.user_b)
        self.ar_a = _create_access_request(self.tenant_a, self.user_a, self.asset_a)
        self.ar_b = _create_access_request(self.tenant_b, self.user_b, self.asset_b)

    def test_tenant_a_comment_not_visible_to_tenant_b(self):
        from hub.apps.governance.models import AccessRequestComment

        # Create comment in tenant A.
        AccessRequestComment.objects.create(
            tenant=self.tenant_a,
            access_request=self.ar_a,
            author=self.user_a,
            body="Tenant A internal comment.",
        )

        # Tenant B user reads comments on their own request (should see none).
        self.client.force_authenticate(user=self.user_b)
        resp = self.client.get(
            f"/api/v1/governance/access-requests/{self.ar_b.id}/comments/",
        )
        assert resp.status_code == 200, resp.content
        assert len(resp.data) == 0

    def test_tenant_a_cannot_access_tenant_b_comment_endpoint(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(
            f"/api/v1/governance/access-requests/{self.ar_b.id}/comments/",
        )
        # Cross-tenant access should 404 (not 403 to avoid leaking existence).
        assert resp.status_code in (404, 403), resp.content
