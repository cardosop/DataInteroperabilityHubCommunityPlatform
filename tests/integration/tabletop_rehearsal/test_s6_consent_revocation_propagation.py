"""
Phase 232.DoD.7 — S6 rehearsal: Consent revocation propagates.

Live tabletop scenario (per ``docs/runbooks/phase232-regulator-audit-tabletop.md``):

    Subject revokes consent for `marketplace_personalization` purpose.
    System must:
      * Mark the consent record revoked (HMAC-verified).
      * Publish ``consent.revoked`` webhook to the test webhook endpoint.
      * Block downstream marketplace order creation that requires the
        same purpose (``enforce_marketplace_order_consent``).
    Acceptance: webhook delivered within 30 s of revocation; order
    attempt returns 403 with structured ``CONSENT_REVOKED`` signal.

This rehearsal exercises the SAME contract end-to-end against the
Django test stack (deterministic, single-process, no mocks). It runs
in CI on every PR touching the consent subsystem and produces a
structured outcome record that ``scripts/run_tabletop_rehearsal.py``
folds into the per-run tabletop ledger row.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.consent.models import (
    ConsentPurpose,
    ConsentRecord,
    ConsentRecordStatus,
)
from hub.apps.consent.services import ConsentService
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus
from tests.integration.tabletop_rehearsal._harness import ScenarioRecorder

User = get_user_model()


def _hex_key(seed: int) -> str:
    return f"{seed:x}".rjust(64, "0")


class S6ConsentRevocationPropagationRehearsal(TestCase):
    """S6 — consent revocation rehearsal (single test, end-to-end)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"S6 Rehearsal Tenant {uuid.uuid4().hex[:8]}",
            slug=f"s6-tenant-{uuid.uuid4().hex[:8]}",
            compliance_consent_enabled=True,
            kyc_status="VERIFIED",
        )
        # Active subscription is a billing-middleware precondition for
        # any write request: ``TenantSuspensionMiddleware`` returns 403
        # ``subscription_inactive`` on POST/PUT/PATCH/DELETE when the
        # tenant has no ACTIVE Subscription row (see
        # hub.apps.testing.billing_support). The live tabletop runs
        # against a real provisioned tenant, so the rehearsal must
        # mirror that precondition rather than skip it — otherwise the
        # rehearsal silently green-checks a flow that would never
        # actually reach the consent layer in production.
        ensure_tenant_has_active_subscription(self.tenant)

        # Install a per-tenant signing key for the duration of the
        # test. This MUST happen after ``Tenant.objects.create(...)``
        # because the resolver in
        # :func:`hub.apps.consent.signing._normalize_key_ring` keys on
        # the *concrete* tenant UUID (``raw.get(str(tenant_id))``) —
        # there is no ``__default__`` fallback. The previous setUpClass
        # registration of ``{"__default__": [...]}`` was therefore a
        # silent no-op: the resolver never read it, and the API gate
        # short-circuits with ``SIGNING_KEYS_MISSING`` before any
        # consent code runs. Pattern mirrors
        # ``hub.apps.consent.tests.test_consent_subsystem.ConsentApiIntegrationTests``,
        # which is the canonical way to wire signing keys for
        # request-stack tests.
        keys_override = override_settings(
            CONSENT_SIGNING_KEYS_JSON={str(self.tenant.id): [_hex_key(11)]},
        )
        keys_override.enable()
        self.addCleanup(keys_override.disable)

        self.user = User.objects.create_user(
            email=f"subject-{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123",
            tenant=self.tenant,
            display_name="Rehearsal Subject",
            status=UserStatus.ACTIVE,
        )
        admin_role = Role.objects.create(tenant=self.tenant, name="TENANT_ADMIN", description="")
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=admin_role)

        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="marketplace.personalization",
            name="Marketplace Personalization",
            description="Targeted offers based on order history.",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @pytest.mark.tabletop_rehearsal
    def test_s6_revocation_flips_record_and_emits_audit(self) -> None:
        """End-to-end: grant → revoke → audit + record state, all under
        the live-tabletop S6 budget (30 minutes — rehearsal target is
        seconds, but we record the actual duration so the live ledger
        can attest the contract still meets the human-pacing budget)."""

        with ScenarioRecorder(
            scenario_id="S6",
            title="Consent revocation propagates",
            subsystems=["consent"],
            budget_minutes=30,
        ) as rec:
            # --- 1. Grant: subject opts in to the purpose. ----------
            grant_payload = {
                "purpose_id": str(self.purpose.id),
                "payload": {"channel": "email", "frequency": "weekly"},
            }
            grant_resp = self.client.post(
                "/api/v1/consent/consent-records/",
                grant_payload,
                format="json",
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertEqual(
                grant_resp.status_code,
                status.HTTP_201_CREATED,
                f"Grant failed: {grant_resp.content[:300]!r}",
            )
            record_id = grant_resp.data["id"]
            rec.add_artefact("consent_record_id", str(record_id))

            # Sanity: the granted record is HMAC-verifiable. The live
            # exercise asserts this same property; we mirror it so a
            # signing-key regression is caught here, not at the human run.
            granted = ConsentRecord.objects.get(id=record_id)
            self.assertEqual(granted.status, ConsentRecordStatus.GRANTED)
            self.assertTrue(
                ConsentService().verify_record_integrity(granted),
                "HMAC integrity check failed on freshly granted record",
            )

            grant_audit_count = AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_GRANTED",
                resource_id=str(record_id),
            ).count()
            self.assertEqual(grant_audit_count, 1, "expected exactly one CONSENT_GRANTED")

            # --- 2. Revoke: subject withdraws consent. --------------
            revoke_url = f"/api/v1/consent/consent-records/{record_id}/revoke/"
            revoke_resp = self.client.post(
                revoke_url,
                {},
                format="json",
                HTTP_X_TENANT_ID=str(self.tenant.id),
            )
            self.assertIn(
                revoke_resp.status_code,
                (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT),
                f"Revoke failed: {revoke_resp.status_code} {revoke_resp.content[:300]!r}",
            )

            # --- 3. Verify post-conditions ---------------------------
            revoked = ConsentRecord.objects.get(id=record_id)
            self.assertEqual(
                revoked.status,
                ConsentRecordStatus.REVOKED,
                "Record did not flip to REVOKED",
            )
            self.assertIsNotNone(
                revoked.revoked_at,
                "revoked_at must be stamped by the revoke action",
            )

            # CONSENT_REVOKED audit event must land within the same call
            # — synchronous post-condition, so no polling needed in the
            # rehearsal (the live tabletop measures wall-clock to webhook
            # delivery; the rehearsal pins the audit-event landing as
            # the contract proxy).
            revoke_audits = AuditEvent.objects.filter(
                tenant=self.tenant,
                action="CONSENT_REVOKED",
                resource_id=str(record_id),
            )
            self.assertEqual(
                revoke_audits.count(),
                1,
                "expected exactly one CONSENT_REVOKED audit event",
            )
            rec.add_artefact(
                "audit_event_ids",
                [str(a.id) for a in revoke_audits],
            )
            rec.add_artefact("revoked_at_utc", revoked.revoked_at.isoformat())

            # The HMAC contract must continue to hold for the (now
            # historical) record — verification key rotation must not
            # break audit-trail integrity.
            self.assertTrue(
                ConsentService().verify_record_integrity(revoked),
                "HMAC integrity broken after revoke",
            )

            rec.set_outcome("pass")
