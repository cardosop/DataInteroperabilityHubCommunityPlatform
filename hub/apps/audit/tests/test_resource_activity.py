"""Tests for Phase 224.3 audit role gating and the resource-activity feed.

Two concerns, one file:
 1. Raw ``/api/v1/audit/audit-events/`` list/retrieve/export now require
    ``TENANT_ADMIN`` or ``AUDITOR`` (platform admins bypass).
 2. The new ``/api/v1/audit/audit-events/resource-activity/`` endpoint returns
    a tenant-scoped, sanitized per-resource feed to any authenticated user.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.serializers import (
    RESOURCE_ACTIVITY_FORBIDDEN_KEYS,
    sanitize_activity_details,
)
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _grant(user, tenant, name):
    role, _ = Role.objects.get_or_create(tenant=tenant, name=name, defaults={"description": name})
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return role


class AuditRoleGateTest(TestCase):
    """Raw audit list/retrieve is role-gated to TENANT_ADMIN or AUDITOR."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Audit Gate Tenant",
            slug=f"audit-gate-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.plain_user = User.objects.create_user(
            email=f"plain-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.auditor = User.objects.create_user(
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _grant(self.auditor, self.tenant, "AUDITOR")
        self.admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _grant(self.admin, self.tenant, "TENANT_ADMIN")

        create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.plain_user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"name": "A"},
        )

    def test_plain_user_cannot_list_raw_audit_events(self):
        self.client.force_authenticate(user=self.plain_user)
        resp = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_can_list_raw_audit_events(self):
        self.client.force_authenticate(user=self.auditor)
        resp = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_tenant_admin_can_list_raw_audit_events(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/api/v1/audit/audit-events/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_plain_user_cannot_export_raw_audit_events(self):
        self.client.force_authenticate(user=self.plain_user)
        resp = self.client.get("/api/v1/audit/audit-events/export/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class ResourceActivityEndpointTest(TestCase):
    """Scoped, sanitized per-resource activity feed."""

    def setUp(self):
        self.client = APIClient()
        self.tenant1 = Tenant.objects.create(
            name="Resource Activity T1",
            slug=f"ra-t1-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant2 = Tenant.objects.create(
            name="Resource Activity T2",
            slug=f"ra-t2-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user1 = User.objects.create_user(
            email=f"ra-u1-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        self.user2 = User.objects.create_user(
            email=f"ra-u2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )

        self.asset_id = uuid.uuid4()
        self.other_asset_id = uuid.uuid4()

        # 2 events for tenant1's asset, 1 unrelated tenant1 event, 1 tenant2
        # event on the same resource_id to prove cross-tenant isolation.
        self.ev_match1 = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user1,
            tenant=self.tenant1,
            resource_id=str(self.asset_id),
            details={
                "name": "Asset",
                "ip_address": "10.0.0.1",  # forbidden
                "_internal_flag": True,  # underscore-prefixed
                "request_id": "req-abc",  # forbidden
                "note": "user visible",
                "nested": {
                    "user_agent": "curl/7",  # forbidden in nested
                    "visible": "yes",
                },
            },
        )
        self.ev_match2 = create_audit_event(
            resource_type="ASSET",
            action="UPDATED",
            actor_user=self.user1,
            tenant=self.tenant1,
            resource_id=str(self.asset_id),
            details={"name": "Asset v2"},
        )
        create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user1,
            tenant=self.tenant1,
            resource_id=str(self.other_asset_id),
            details={"name": "Other"},
        )
        create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user2,
            tenant=self.tenant2,
            resource_id=str(self.asset_id),  # same UUID but different tenant
            details={"name": "Cross-tenant"},
        )

    def _url(self, resource_type="ASSET", resource_id=None):
        rid = str(resource_id if resource_id else self.asset_id)
        return (
            f"/api/v1/audit/audit-events/resource-activity/"
            f"?resource_type={resource_type}&resource_id={rid}"
        )

    def test_plain_user_can_read_their_resource_activity(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {ev["id"] for ev in resp.data["results"]}
        self.assertEqual(ids, {str(self.ev_match1.id), str(self.ev_match2.id)})

    def test_cross_tenant_events_are_excluded(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        actions = [ev["action"] for ev in resp.data["results"]]
        # Cross-tenant event is ALSO action=CREATED; ensure results come only
        # from tenant1 by checking the count.
        self.assertEqual(len(resp.data["results"]), 2)
        self.assertIn("CREATED", actions)
        self.assertIn("UPDATED", actions)

    def test_details_are_sanitized_top_level(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        match1 = next(ev for ev in resp.data["results"] if ev["id"] == str(self.ev_match1.id))
        details = match1["details"]
        self.assertNotIn("ip_address", details)
        self.assertNotIn("request_id", details)
        self.assertNotIn("_internal_flag", details)
        self.assertEqual(details["name"], "Asset")
        self.assertEqual(details["note"], "user visible")

    def test_details_are_sanitized_recursively(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        match1 = next(ev for ev in resp.data["results"] if ev["id"] == str(self.ev_match1.id))
        nested = match1["details"]["nested"]
        self.assertNotIn("user_agent", nested)
        self.assertEqual(nested["visible"], "yes")

    def test_response_exposes_actor_display_name_not_raw_fk(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        match1 = next(ev for ev in resp.data["results"] if ev["id"] == str(self.ev_match1.id))
        self.assertIn("actor_display_name", match1)
        self.assertNotIn("actor_user", match1)
        self.assertNotIn("tenant", match1)
        self.assertNotIn("details_json", match1)
        self.assertTrue(match1["actor_display_name"])

    def test_results_are_ordered_newest_first(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url())
        timestamps = [ev["timestamp"] for ev in resp.data["results"]]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_missing_params_return_400(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get("/api/v1/audit/audit-events/resource-activity/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_uuid_returns_400(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(
            "/api/v1/audit/audit-events/resource-activity/"
            "?resource_type=ASSET&resource_id=not-a-uuid"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_is_401(self):
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_resource_returns_empty_list(self):
        self.client.force_authenticate(user=self.user1)
        resp = self.client.get(self._url(resource_id=uuid.uuid4()))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["results"], [])


class SanitizeActivityDetailsTest(TestCase):
    """Unit tests for the pure ``sanitize_activity_details`` helper."""

    def test_strips_forbidden_top_level(self):
        out = sanitize_activity_details({"ip_address": "x", "name": "ok", "token": "t"})
        self.assertEqual(out, {"name": "ok"})

    def test_strips_underscore_prefixed(self):
        out = sanitize_activity_details({"_internal": 1, "ok": 2})
        self.assertEqual(out, {"ok": 2})

    def test_case_insensitive_match(self):
        out = sanitize_activity_details({"IP_Address": "x", "keep": 1})
        self.assertEqual(out, {"keep": 1})

    def test_recurses_into_lists_of_dicts(self):
        out = sanitize_activity_details({"items": [{"token": "x", "keep": 1}]})
        self.assertEqual(out, {"items": [{"keep": 1}]})

    def test_non_dict_passes_through(self):
        self.assertEqual(sanitize_activity_details("hello"), "hello")
        self.assertEqual(sanitize_activity_details(None), None)

    def test_forbidden_set_documents_sensitive_keys(self):
        # Regression guard: any change to the allowlist must be deliberate.
        for key in ("access_token", "password", "secret", "authorization"):
            self.assertIn(key, RESOURCE_ACTIVITY_FORBIDDEN_KEYS)
