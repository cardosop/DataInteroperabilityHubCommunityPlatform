"""
283.3.1.3 — G3 E2E consent grant/revoke flow.

Covers:
- Grant consent via API
- Revoke consent via API
- Verify audit events emitted
- Verify consent dashboard accessible to TENANT_ADMIN/DPO
"""

import pytest
from django.test import override_settings
from rest_framework import status

from hub.apps.audit.models import AuditEvent
from hub.apps.consent.models import ConsentPurpose, ConsentRecord, ConsentRecordStatus
from tests.e2e.conftest import E2ETestBase


def _hex_key(seed: int) -> str:
    return ("%.64x" % (seed * (1 << 128) + 1))[:64]


@pytest.mark.e2e
class ConsentGrantRevokeE2ETests(E2ETestBase):
    """E2E tests for consent grant/revoke flow (283.3.1.3)."""

    def setUp(self):
        super().setUp()
        # Enable consent feature flag on the E2E tenant
        self.tenant.compliance_consent_enabled = True
        self.tenant.save(update_fields=["compliance_consent_enabled"])

        # Configure consent signing keys so grant/revoke operations succeed
        cfg = {str(self.tenant.id): [_hex_key(88)]}
        self._keys = override_settings(CONSENT_SIGNING_KEYS_JSON=cfg)
        self._keys.enable()
        self.addCleanup(self._keys.disable)

        # Create a consent purpose
        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="e2e.consent.test",
            name="E2E Consent Test Purpose",
            description="Purpose for E2E consent flow testing",
            retention_days=365,
            is_active=True,
        )

    def test_full_consent_grant_revoke_lifecycle(self):
        """End-to-end: grant consent → verify record + audit → revoke → verify."""
        # ── Grant consent ──────────────────────────────────────────
        grant_resp = self.client.post(
            "/api/v1/governance/consent-records/",
            {"purpose_id": str(self.purpose.id), "payload": {"channel": "email", "version": 1}},
            format="json",
        )
        self.assertEqual(grant_resp.status_code, status.HTTP_201_CREATED)
        record_id = grant_resp.data["id"]
        self.assertEqual(grant_resp.data["status"], ConsentRecordStatus.GRANTED)
        self.assertIn("proof_hmac", grant_resp.data)

        # Verify record persisted
        record = ConsentRecord.objects.get(id=record_id)
        self.assertEqual(record.status, ConsentRecordStatus.GRANTED)
        self.assertEqual(record.purpose, self.purpose)
        self.assertEqual(record.user, self.user)

        # Verify CONSENT_GRANTED audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_GRANTED",
                resource_id=str(record_id),
            ).exists(),
            "CONSENT_GRANTED audit event must exist after grant",
        )

        # ── Revoke consent ─────────────────────────────────────────
        revoke_resp = self.client.post(
            f"/api/v1/governance/consent-records/{record_id}/revoke/",
            {},
            format="json",
        )
        self.assertEqual(revoke_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(revoke_resp.data["status"], ConsentRecordStatus.REVOKED)

        # Verify CONSENT_REVOKED audit event
        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_REVOKED",
                resource_id=str(record_id),
            ).exists(),
            "CONSENT_REVOKED audit event must exist after revoke",
        )

    def test_consent_dashboard_accessible(self):
        """Verify consent dashboard returns 200 for TENANT_ADMIN."""
        dash_resp = self.client.get("/api/v1/governance/consent-dashboard/")
        self.assertEqual(dash_resp.status_code, status.HTTP_200_OK)
        self.assertIn("purposes", dash_resp.data)

    def test_consent_purpose_create_and_update_audit(self):
        """Verify CONSENT_PURPOSE_CHANGED emits on both create and update."""
        # Create
        create_resp = self.client.post(
            "/api/v1/governance/consent-purposes/",
            {
                "key": "e2e.create.test",
                "name": "E2E Created Purpose",
                "description": "Testing create audit",
                "retention_days": 60,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        pid = create_resp.data["id"]

        self.assertTrue(
            AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_PURPOSE_CHANGED",
                resource_id=str(pid),
            ).exists(),
            "CONSENT_PURPOSE_CHANGED must emit on purpose create",
        )

        # Update
        update_resp = self.client.put(
            f"/api/v1/governance/consent-purposes/{pid}/",
            {
                "key": "e2e.create.test",
                "name": "E2E Updated Purpose",
                "description": "Testing update audit",
                "retention_days": 90,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(update_resp.status_code, status.HTTP_200_OK)

        # Two audit events for this purpose: create + update
        count = AuditEvent.objects.filter(
            tenant=self.tenant,
            action="CONSENT_PURPOSE_CHANGED",
            resource_id=str(pid),
        ).count()
        self.assertGreaterEqual(count, 2)
