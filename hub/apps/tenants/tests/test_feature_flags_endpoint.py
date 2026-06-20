"""
Phase 250.6.E TDD pin for the tenant feature-flags admin endpoints.

The new admin page at ``/admin/tenant-settings/`` (frontend) needs
two backend surfaces:

1. ``GET  /api/v1/tenants/me/feature-flags/`` — return the per-tenant
   capability flags + their human-readable descriptions + their
   default values. Lets the SPA render a self-describing settings
   page without a separate "schema" round-trip.

2. ``PATCH /api/v1/tenants/me/feature-flags/`` — let TENANT_ADMIN
   flip flags on / off. Each PATCH writes a
   ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the
   before/after values so the audit-log panel below the settings
   form can render the change history.

3. ``GET  /api/v1/tenants/me/feature-flag-history/`` — return the
   audit-event rows for the calling tenant, scoped to
   ``action=TENANT_FEATURE_FLAG_UPDATED`` so the SPA can render
   "who changed what when" without scanning the full audit log.

Per Phase 250.6.E.2, all three endpoints are TENANT_ADMIN-only —
non-admin users see HTTP 403 with ``code="PERMISSION_DENIED"``. The
gate runs BEFORE the body parse so a non-admin POST can't influence
the audit emission either.

Tests use real Django ORM rows + real DRF APIClient — no mocks.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_data_provider_role,
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant(*, slug_prefix: str = "t"):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


class FeatureFlagsGetTest(TestCase):
    """``GET`` returns the per-tenant flag values + descriptions."""

    def test_admin_can_read_flags(self):
        _tenant, user = _seed_tenant()
        ensure_user_has_tenant_admin_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/tenants/me/feature-flags/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        body = resp.json()
        # Each flag entry carries its current value + a description
        # so the SPA can render a self-describing settings page.
        self.assertIn("flags", body)
        flags = {f["name"]: f for f in body["flags"]}
        # Anchor on a few flags from prior phases — these are the
        # canonical per-tenant capability flags the admin surface
        # exposes:
        self.assertIn("asset_creation_enabled", flags)
        self.assertIn("federated_import_enabled", flags)
        self.assertIn("asset_auto_activate_on_gate_pass", flags)
        # Each flag has the contract shape we render against.
        for f in body["flags"]:
            assert "name" in f
            assert "value" in f
            assert "description" in f
            assert isinstance(f["value"], bool)

    def test_non_admin_gets_403(self):
        _tenant, user = _seed_tenant()
        # DATA_PROVIDER (non-admin) — must NOT see the admin endpoint.
        ensure_user_has_data_provider_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/tenants/me/feature-flags/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)


class FeatureFlagsPatchTest(TestCase):
    """``PATCH`` lets TENANT_ADMIN flip flags + emits the audit row."""

    def test_admin_can_flip_flag_emits_audit(self):
        tenant, user = _seed_tenant()
        ensure_user_has_tenant_admin_role(user)
        # Pre-condition: federated_import_enabled defaults to False
        # (per Phase 250.5.A.2) — flipping to True is the canonical
        # flow that exercises the audit emission.
        self.assertFalse(tenant.federated_import_enabled)

        client = APIClient()
        client.force_authenticate(user=user)
        before = AuditEvent.objects.filter(
            action=audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
            tenant=tenant,
        ).count()
        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"federated_import_enabled": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        # Tenant row updated.
        tenant.refresh_from_db()
        self.assertTrue(tenant.federated_import_enabled)
        # Audit row emitted with before/after values for forensic
        # replay (the audit-log panel renders these as "User X
        # changed federated_import_enabled from False to True").
        after = AuditEvent.objects.filter(
            action=audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
            tenant=tenant,
        ).order_by("-timestamp")
        self.assertEqual(after.count() - before, 1)
        ev = after.first()
        self.assertEqual(ev.details_json["flag_name"], "federated_import_enabled")
        self.assertFalse(ev.details_json["previous_value"])
        self.assertTrue(ev.details_json["new_value"])

    def test_non_admin_patch_gets_403_no_side_effects(self):
        tenant, user = _seed_tenant()
        ensure_user_has_data_provider_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        before_audit = AuditEvent.objects.filter(
            action=audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
            tenant=tenant,
        ).count()
        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"federated_import_enabled": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)
        # No side-effects on the tenant row (refusal is structurally
        # side-effect-free — gate runs BEFORE the model write).
        tenant.refresh_from_db()
        self.assertFalse(tenant.federated_import_enabled)
        # No audit row emitted (the gate refused before the audit
        # emission would have fired).
        after_audit = AuditEvent.objects.filter(
            action=audit_event_types.TENANT_FEATURE_FLAG_UPDATED,
            tenant=tenant,
        ).count()
        self.assertEqual(after_audit, before_audit)

    def test_unknown_flag_returns_400(self):
        _tenant, user = _seed_tenant()
        ensure_user_has_tenant_admin_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"never_heard_of_this_flag": True},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.content)
        body = resp.json()
        self.assertEqual(body.get("code"), "UNKNOWN_FLAG")


class FeatureFlagHistoryTest(TestCase):
    """``GET /me/feature-flag-history/`` returns audit rows scoped to
    ``TENANT_FEATURE_FLAG_UPDATED``. Cross-tenant rows are excluded
    (existence-leak protection per the IDOR pattern)."""

    def test_admin_sees_own_tenant_history(self):
        _tenant, user = _seed_tenant()
        ensure_user_has_tenant_admin_role(user)

        client = APIClient()
        client.force_authenticate(user=user)

        # Flip a flag to seed an audit row.
        client.patch(
            "/api/v1/tenants/me/feature-flags/",
            data={"federated_import_enabled": True},
            format="json",
        )

        resp = client.get("/api/v1/tenants/me/feature-flag-history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        body = resp.json()
        self.assertIn("events", body)
        self.assertGreaterEqual(len(body["events"]), 1)
        ev = body["events"][0]
        self.assertEqual(ev["action"], "TENANT_FEATURE_FLAG_UPDATED")
        self.assertEqual(ev["details_json"]["flag_name"], "federated_import_enabled")

    def test_non_admin_history_gets_403(self):
        _tenant, user = _seed_tenant()
        ensure_user_has_data_provider_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/tenants/me/feature-flag-history/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, resp.content)
