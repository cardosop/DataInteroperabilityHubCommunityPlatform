"""
Tests for Phase 225.3 — separate ``ResourceActivityViewSet`` with
user-involvement scoping, plus explicit ``PLATFORM_ADMIN`` on the raw
audit gate.

225.3.1 — raw audit gate should accept the role name ``PLATFORM_ADMIN``
         (not just the ``is_platform_admin`` boolean bypass).
225.3.2 — ``/api/v1/audit/resource-activity/`` returns only events for
         resources the caller is directly involved in:
             actor_user_id == user.id
             OR resource_owner_id == user.id (via resource-type registry)
         Admins (TENANT_ADMIN / AUDITOR / platform admin) bypass the
         involvement filter and see the full tenant-scoped feed.
225.3.3 — responses are scrubbed by ``ResourceActivityEventSerializer``.

Everything here runs against real DB rows; no mocks.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _grant(user, tenant, name):
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name=name, defaults={"description": name}
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


RESOURCE_ACTIVITY_URL = "/api/v1/audit/resource-activity/"


class ResourceActivityScopingTest(TestCase):
    """User-involvement scoping: only events the caller is tied to."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Involvement T",
            slug=f"inv-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.creator = User.objects.create_user(
            email=f"creator-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.bystander = User.objects.create_user(
            email=f"bystander-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset_id = uuid.uuid4()

        # creator performed an action on this resource; bystander did not.
        self.ev_create = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.creator,
            tenant=self.tenant,
            resource_id=str(self.asset_id),
            details={"name": "Asset", "ip_address": "10.0.0.1", "_private": 1},
        )
        self.ev_update = create_audit_event(
            resource_type="ASSET",
            action="UPDATED",
            actor_user=self.creator,
            tenant=self.tenant,
            resource_id=str(self.asset_id),
            details={"name": "Asset v2"},
        )

    def _url(self, resource_type="ASSET", resource_id=None):
        rid = str(resource_id if resource_id else self.asset_id)
        return f"{RESOURCE_ACTIVITY_URL}?resource_type={resource_type}&resource_id={rid}"

    def test_creator_sees_full_activity_for_their_resource(self):
        self.client.force_authenticate(user=self.creator)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {ev["id"] for ev in resp.data["results"]}
        self.assertEqual(ids, {str(self.ev_create.id), str(self.ev_update.id)})

    def test_bystander_in_same_tenant_gets_403(self):
        """A tenant peer who never touched the resource gets an explicit 403.

        This is the core hardening vs 224.3: previously any tenant member
        could read any resource's activity.
        """
        self.client.force_authenticate(user=self.bystander)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_admin_bypasses_involvement_filter(self):
        self.client.force_authenticate(user=self.bystander)
        _grant(self.bystander, self.tenant, "TENANT_ADMIN")
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 2)

    def test_auditor_bypasses_involvement_filter(self):
        self.client.force_authenticate(user=self.bystander)
        _grant(self.bystander, self.tenant, "AUDITOR")
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_platform_admin_flag_bypasses_involvement_filter(self):
        self.bystander.is_platform_admin = True
        self.bystander.save(update_fields=["is_platform_admin"])
        self.client.force_authenticate(user=self.bystander)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cross_tenant_user_gets_empty_not_403(self):
        """A user from a different tenant must not know whether a resource in
        another tenant exists — return an empty feed rather than a 403 that
        leaks existence."""
        other_tenant = Tenant.objects.create(
            name="Other", slug=f"other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=other_tenant, status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=other_user)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])

    def test_unauthenticated_is_401(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_params_400(self):
        self.client.force_authenticate(user=self.creator)
        resp = self.client.get(RESOURCE_ACTIVITY_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_resource_uuid_400(self):
        self.client.force_authenticate(user=self.creator)
        resp = self.client.get(
            f"{RESOURCE_ACTIVITY_URL}?resource_type=ASSET&resource_id=not-a-uuid"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_is_sanitized(self):
        self.client.force_authenticate(user=self.creator)
        resp = self.client.get(self._url())
        match = next(
            ev for ev in resp.data["results"] if ev["id"] == str(self.ev_create.id)
        )
        details = match["details"]
        self.assertNotIn("ip_address", details)
        self.assertNotIn("_private", details)
        self.assertEqual(details["name"], "Asset")
        # Raw FKs / tenant leakage absent.
        self.assertNotIn("actor_user", match)
        self.assertNotIn("tenant", match)
        self.assertNotIn("details_json", match)


class ResourceOwnershipInvolvementTest(TestCase):
    """The ownership branch of the involvement predicate.

    A user who *owns* a resource (via model-level ``created_by``) but was
    not the actor on any audit event must still be granted access.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Owner T", slug=f"own-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.owner = User.objects.create_user(
            email=f"own-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant, status=UserStatus.ACTIVE,
        )
        self.stranger = User.objects.create_user(
            email=f"str-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant, status=UserStatus.ACTIVE,
        )

        # Real Asset row with created_by=owner but an event actor=stranger.
        from hub.apps.assets.models import Asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Owned Asset",
            status="DRAFT",
            created_by=self.owner,
        )
        # A system/admin stranger performed an audit-worthy action.
        self.ev = create_audit_event(
            resource_type="ASSET",
            action="PUBLISHED",
            actor_user=self.stranger,
            tenant=self.tenant,
            resource_id=str(self.asset.id),
            details={"note": "admin published"},
        )

    def _url(self):
        return (
            f"{RESOURCE_ACTIVITY_URL}"
            f"?resource_type=ASSET&resource_id={self.asset.id}"
        )

    def test_owner_sees_activity_even_without_being_actor(self):
        self.client.force_authenticate(user=self.owner)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {ev["id"] for ev in resp.data["results"]}
        self.assertIn(str(self.ev.id), ids)

    def test_stranger_actor_sees_activity_via_actor_branch(self):
        """stranger never owned the resource but was the actor of an event —
        the actor branch of the involvement predicate grants access."""
        self.client.force_authenticate(user=self.stranger)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_owner_of_resource_with_no_events_yet_gets_empty_list(self):
        """An owner hitting their freshly-created resource (no audit trail
        yet) must get 200 with an empty feed, not 403 — otherwise the
        timeline UI would flash a permission error on new resources."""
        from hub.apps.assets.models import Asset

        empty_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"empty-{uuid.uuid4().hex[:8]}",
            name="Empty Asset",
            status="DRAFT",
            created_by=self.owner,
        )
        self.client.force_authenticate(user=self.owner)
        url = (
            f"{RESOURCE_ACTIVITY_URL}"
            f"?resource_type=ASSET&resource_id={empty_asset.id}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])


class OwnershipRegistryCoverageTest(TestCase):
    """Regression guard: ORDER and ACCESS_REQUEST resource types resolve
    ownership via the registry, not just the actor branch."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Reg T", slug=f"reg-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.buyer = User.objects.create_user(
            email=f"buyer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_ownership_resolvers_cover_core_resource_types(self):
        """The registry must declare resolvers for every resource type the
        frontend's activity timeline queries so the 403 path never fires on
        a legitimate owner."""
        from hub.apps.audit.involvement import OWNERSHIP_RESOLVERS

        expected = {"ASSET", "CONTRACT", "ORDER", "ACCESS_REQUEST"}
        missing = expected - set(OWNERSHIP_RESOLVERS)
        self.assertFalse(
            missing,
            f"OWNERSHIP_RESOLVERS missing resolvers for: {sorted(missing)}",
        )


class PlatformAdminRoleGateTest(TestCase):
    """A user granted the named ``PLATFORM_ADMIN`` role (without the
    ``is_platform_admin`` boolean flag) must be able to list raw audit events.
    """

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="PA Gate", slug=f"pa-{uuid.uuid4().hex[:8]}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.pa_named = User.objects.create_user(
            email=f"pa-named-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123", tenant=self.tenant, status=UserStatus.ACTIVE,
        )
        _grant(self.pa_named, self.tenant, "PLATFORM_ADMIN")
        create_audit_event(
            resource_type="ASSET", action="CREATED",
            actor_user=self.pa_named, tenant=self.tenant,
            resource_id=str(uuid.uuid4()), details={},
        )

    def test_named_platform_admin_role_can_list_raw_audit(self):
        self.client.force_authenticate(user=self.pa_named)
        resp = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
