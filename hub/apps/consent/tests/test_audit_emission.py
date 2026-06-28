"""283.3.1.1 — G7 Audit: verify CONSENT_GRANTED / CONSENT_REVOKED / CONSENT_PURPOSE_CHANGED
emit from all mutation paths. Real DB, real audit rows — no mocks."""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.consent.models import ConsentPurpose
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus


def _hex_key(seed: int) -> str:
    return ("%.64x" % (seed * (1 << 128) + 1))[:64]


class ConsentAuditEmissionTests(TestCase):
    """Targeted pytest for 283.3.1.1 — every mutation path emits the correct audit event."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="audit-t",
            slug="audit-t-" + uuid.uuid4().hex[:8],
            compliance_consent_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        cfg = {str(self.tenant.id): [_hex_key(99)]}
        self._keys = override_settings(CONSENT_SIGNING_KEYS_JSON=cfg)
        self._keys.enable()
        self.addCleanup(self._keys.disable)

        self.user = User.objects.create_user(
            email=f"audit-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026",
            tenant=self.tenant,
            display_name="AuditSubject",
            status=UserStatus.ACTIVE,
        )
        admin_role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=admin_role)

        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="audit-purpose",
            name="AuditPurpose",
            description="",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    # ── CONSENT_GRANTED paths ──────────────────────────────────────────

    @pytest.mark.integration
    def test_grant_via_create_emits_consent_granted(self):
        """POST /consent-records/ → CONSENT_GRANTED."""
        before = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_GRANTED").count()
        resp = self.client.post(
            "/api/v1/consent/consent-records/",
            {"purpose_id": str(self.purpose.id), "payload": {"k": "v"}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        after = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_GRANTED").count()
        self.assertEqual(after, before + 1)

    @pytest.mark.integration
    def test_grant_via_patch_emits_consent_granted(self):
        """PATCH /consent-records/{id}/ (re-grant with new payload) → CONSENT_GRANTED."""
        # initial grant
        r = self.client.post(
            "/api/v1/consent/consent-records/",
            {"purpose_id": str(self.purpose.id), "payload": {"v": 1}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rec_id = r.data["id"]
        before = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_GRANTED").count()
        # re-grant with new payload
        r2 = self.client.patch(
            f"/api/v1/consent/consent-records/{rec_id}/",
            {"payload": {"v": 2}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_GRANTED").count()
        self.assertEqual(after, before + 1)

    # ── CONSENT_REVOKED path ───────────────────────────────────────────

    @pytest.mark.integration
    def test_revoke_via_action_emits_consent_revoked(self):
        """POST /consent-records/{id}/revoke/ → CONSENT_REVOKED."""
        r = self.client.post(
            "/api/v1/consent/consent-records/",
            {"purpose_id": str(self.purpose.id), "payload": {}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rec_id = r.data["id"]
        before = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_REVOKED").count()
        r2 = self.client.post(
            f"/api/v1/consent/consent-records/{rec_id}/revoke/",
            {},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(tenant=self.tenant, action="CONSENT_REVOKED").count()
        self.assertEqual(after, before + 1)

    # ── CONSENT_PURPOSE_CHANGED paths ──────────────────────────────────

    @pytest.mark.integration
    def test_create_purpose_emits_consent_purpose_changed(self):
        """POST /consent-purposes/ → CONSENT_PURPOSE_CHANGED with operation=created."""
        slug = uuid.uuid4().hex[:8]
        before = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED"
        ).count()
        resp = self.client.post(
            "/api/v1/consent/consent-purposes/",
            {
                "key": f"api-{slug}",
                "name": "CreatedPurpose",
                "description": "audit test",
                "retention_days": 30,
                "is_active": True,
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pid = resp.data["id"]
        after = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED"
        ).count()
        self.assertEqual(after, before + 1)
        ev = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED", resource_id=str(pid)
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.details_json.get("operation"), "created")

    @pytest.mark.integration
    def test_update_purpose_emits_consent_purpose_changed(self):
        """PUT /consent-purposes/{id}/ → CONSENT_PURPOSE_CHANGED with version_bumped info."""
        before = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED"
        ).count()
        resp = self.client.put(
            f"/api/v1/consent/consent-purposes/{self.purpose.id}/",
            {
                "key": self.purpose.key,
                "name": "UpdatedPurpose",
                "description": "changed",
                "retention_days": 90,
                "is_active": True,
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        after = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED"
        ).count()
        self.assertEqual(after, before + 1)
        ev = (
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_PURPOSE_CHANGED",
                resource_id=str(self.purpose.id),
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(ev)
        self.assertTrue(ev.details_json.get("version_bumped"))
        self.assertEqual(ev.details_json["after"]["name"], "UpdatedPurpose")
