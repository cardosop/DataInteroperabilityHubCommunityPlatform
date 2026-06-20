"""Phase 232.1 consent subsystem integration tests (real DB + crypto, no mocks)."""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.consent.gates import WEBHOOK_PURPOSE_KEY
from hub.apps.consent.models import ConsentPurpose, ConsentRecord, ConsentRecordStatus
from hub.apps.consent.services import ConsentService
from hub.apps.consent.signing import compute_proof_hmac, verify_proof_hmac
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.webhook_service import WebhookService


def _hex_key(seed: int) -> str:
    return ("%.64x" % (seed * (1 << 128) + 1))[:64]


class ConsentSigningWindowTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="c1", slug="c1-" + uuid.uuid4().hex[:8])

    @pytest.mark.integration
    def test_three_key_window_verifies_with_rotated_key(self):
        tenant_id = str(self.tenant.id)
        user_id = str(uuid.uuid4())
        purpose_id = str(uuid.uuid4())
        payload = {"a": 1}
        ring = [bytes.fromhex(_hex_key(1)), bytes.fromhex(_hex_key(2)), bytes.fromhex(_hex_key(3))]
        proof_old = compute_proof_hmac(
            key=ring[2],
            tenant_id=tenant_id,
            user_id=user_id,
            purpose_id=purpose_id,
            payload=payload,
        )
        ok, idx = verify_proof_hmac(
            proof_hex=proof_old,
            tenant_id=tenant_id,
            user_id=user_id,
            purpose_id=purpose_id,
            payload=payload,
            key_ring=ring,
        )
        self.assertTrue(ok)
        self.assertEqual(idx, 2)

    @pytest.mark.integration
    def test_tampered_payload_rejected(self):
        tenant_id = str(self.tenant.id)
        user_id = str(uuid.uuid4())
        purpose_id = str(uuid.uuid4())
        ring = [bytes.fromhex(_hex_key(9))]
        proof = compute_proof_hmac(
            key=ring[0],
            tenant_id=tenant_id,
            user_id=user_id,
            purpose_id=purpose_id,
            payload={"x": 1},
        )
        ok, _ = verify_proof_hmac(
            proof_hex=proof,
            tenant_id=tenant_id,
            user_id=user_id,
            purpose_id=purpose_id,
            payload={"x": 2},
            key_ring=ring,
        )
        self.assertFalse(ok)


class ConsentApiIntegrationTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="c2",
            slug="c2-" + uuid.uuid4().hex[:8],
            compliance_consent_enabled=True,
        )
        # Phase 25.2.4 TenantSuspensionMiddleware refuses writes
        # (POST/PUT/PATCH/DELETE) when the tenant has no active
        # Subscription — every consent test below issues writes, so
        # seed an ACTIVE subscription up front.
        ensure_tenant_has_active_subscription(self.tenant)
        cfg = {str(self.tenant.id): [_hex_key(11)]}
        self._keys = override_settings(CONSENT_SIGNING_KEYS_JSON=cfg)
        self._keys.enable()
        self.addCleanup(self._keys.disable)

        self.user = User.objects.create_user(
            email=f"u-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026",
            tenant=self.tenant,
            display_name="Subject",
            status=UserStatus.ACTIVE,
        )
        admin_role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=admin_role)

        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="test.purpose",
            name="Test",
            description="",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.integration
    def test_grant_creates_audit_and_record(self):
        url = "/api/v1/consent/consent-records/"
        resp = self.client.post(
            url,
            {"purpose_id": str(self.purpose.id), "payload": {"k": "v"}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        rec = ConsentRecord.objects.get(user=self.user, purpose=self.purpose)
        self.assertEqual(rec.status, ConsentRecordStatus.GRANTED)
        self.assertTrue(ConsentService().verify_record_integrity(rec))
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant, action="CONSENT_GRANTED", resource_id=str(rec.id)
            ).exists()
        )

    @pytest.mark.integration
    def test_duplicate_grant_same_payload_single_audit_event(self):
        url = "/api/v1/consent/consent-records/"
        body = {"purpose_id": str(self.purpose.id), "payload": {"k": "same"}}
        r1 = self.client.post(url, body, format="json", HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post(url, body, format="json", HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        rec_id = str(ConsentRecord.objects.get(user=self.user, purpose=self.purpose).id)
        self.assertEqual(rec_id, str(r1.data["id"]))
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=self.tenant, action="CONSENT_GRANTED", resource_id=rec_id
            ).count(),
            1,
        )

    @pytest.mark.integration
    def test_grant_inactive_purpose_returns_400(self):
        inactive = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"off-{uuid.uuid4().hex[:8]}",
            name="Inactive",
            description="",
            is_active=False,
        )
        resp = self.client.post(
            "/api/v1/consent/consent-records/",
            {"purpose_id": str(inactive.id), "payload": {}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_create_purpose_via_api_emits_consent_purpose_changed(self):
        slug = uuid.uuid4().hex[:8]
        resp = self.client.post(
            "/api/v1/consent/consent-purposes/",
            {
                "key": f"api-created-{slug}",
                "name": "API Purpose",
                "description": "from test",
                "retention_days": 30,
                "is_active": True,
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pid = resp.data["id"]
        ev = AuditEvent.objects.filter(
            tenant=self.tenant, action="CONSENT_PURPOSE_CHANGED", resource_id=str(pid)
        ).first()
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.details_json.get("operation"), "created")
        self.assertEqual(ev.details_json.get("purpose_key"), f"api-created-{slug}")

    @pytest.mark.integration
    def test_patch_consent_record_regrants_with_new_proof(self):
        create_url = "/api/v1/consent/consent-records/"
        r = self.client.post(
            create_url,
            {"purpose_id": str(self.purpose.id), "payload": {"v": 1}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        rec_id = r.data["id"]
        proof1 = r.data["proof_hmac"]
        r2 = self.client.patch(
            f"/api/v1/consent/consent-records/{rec_id}/",
            {"payload": {"v": 2}},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertNotEqual(r2.data["proof_hmac"], proof1)
        self.assertEqual(
            AuditEvent.objects.filter(
                tenant=self.tenant, action="CONSENT_GRANTED", resource_id=str(rec_id)
            ).count(),
            2,
        )

    @pytest.mark.integration
    def test_consent_dashboard_allowed_for_tenant_admin(self):
        resp = self.client.get(
            "/api/v1/consent/consent-dashboard/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("purposes", resp.data)

    @pytest.mark.integration
    def test_revoke_after_rotation_still_verifies_with_prior_key(self):
        # The previous version of this test manually called
        # ``self._keys.disable()`` (the override registered in
        # ``setUp`` and tracked via ``addCleanup``) and then rebound
        # ``self._keys`` to a new override. The ``addCleanup``
        # callback still held a reference to the ORIGINAL override's
        # ``.disable``, so cleanup re-disabled an already-disabled
        # object — Django's ``override_settings.disable`` then raises
        # ``'override_settings' object has no attribute 'wrapped'``
        # because the first ``disable`` consumed the attribute.
        # Use nested ``override_settings`` context managers and leave
        # the setUp-registered key set untouched.
        key_a = _hex_key(21)
        key_b = _hex_key(22)
        cfg1 = {str(self.tenant.id): [key_a]}
        with override_settings(CONSENT_SIGNING_KEYS_JSON=cfg1):
            rec = ConsentService().grant(
                tenant=self.tenant,
                user=self.user,
                purpose=self.purpose,
                payload={"phase": "1"},
                actor_user=self.user,
            )
        cfg2 = {str(self.tenant.id): [key_b, key_a]}  # rotated; prior key still verifiable
        with override_settings(CONSENT_SIGNING_KEYS_JSON=cfg2):
            ConsentService().revoke(
                tenant=self.tenant, record=rec, actor_user=self.user, request=None
            )
        rec.refresh_from_db()
        self.assertEqual(rec.status, ConsentRecordStatus.REVOKED)


class ConsentWebhookGateTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="c3",
            slug="c3-" + uuid.uuid4().hex[:8],
            compliance_consent_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self._keys = override_settings(
            CONSENT_SIGNING_KEYS_JSON={str(self.tenant.id): [_hex_key(31)]}
        )
        self._keys.enable()
        self.addCleanup(self._keys.disable)
        self.user = User.objects.create_user(
            email=f"w-{uuid.uuid4().hex[:8]}@example.com",
            password="M3sh@nt!Hub#2026",
            tenant=self.tenant,
            display_name="W",
            status=UserStatus.ACTIVE,
        )
        ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=WEBHOOK_PURPOSE_KEY,
            name="Webhook",
            description="",
        )
        purpose = ConsentPurpose.objects.get(tenant=self.tenant, key=WEBHOOK_PURPOSE_KEY)
        ConsentService().grant(
            tenant=self.tenant,
            user=self.user,
            purpose=purpose,
            payload={},
            actor_user=self.user,
        )

    @pytest.mark.integration
    def test_create_webhook_allowed_with_consent(self):
        wh = WebhookService().create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="t",
            url="http://example.com/hook",
            secret="s" * 32,
            event_types=[str(WebhookEventType.ASSET_CREATED)],
        )
        self.assertIsNotNone(wh.id)
