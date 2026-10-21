"""W11.7 (oss-release-remediation) — AccessRequest transition-matrix
adversarial pins (ASVS V11, register rows 10/16).

The AR lifecycle is the multi-step approval machine
(``governance/state_machine.py``) guarded by the chain + row lock on
the service path.  These pins close the two gaps the W11.7 audit
found:

* the SERIALIZER accepted ``{"status": "APPROVED"}`` on PATCH/PUT and
  wrote it straight through — any→any transition, no chain, no audit
  (the lifecycle fields are now read-only: DRF ignores them);
* the business-rules transition table was a LOCAL copy that diverged
  from the machine (omitted PENDING_NEXT_APPROVER as a source and
  APPROVED→EXPIRED as a hop) — it now imports the machine's table;
* the machine now covers the real-surface hops the writers perform
  (order-cancel PENDING→REVOKED, SLA sweep PENDING→EXPIRED).

Real DRF stack + real DB — no mocks.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.business_rules import GovernanceBusinessRules
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
)
from hub.apps.governance.state_machine import ALLOWED_TRANSITIONS
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ARSerializerTransitionMatrixTest(TestCase):
    """The lifecycle fields are read-only — PATCH/PUT cannot smuggle a
    status change past the service actions."""

    def setUp(self):
        sfx = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W117 {sfx}", slug=f"w117-{sfx}", status="ACTIVE"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w117-{sfx}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"w117-{sfx}",
            name="W117 Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.access_request = AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=self.asset,
            reason="matrix cell",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _patch(self, payload):
        return self.client.patch(
            f"/api/v1/governance/access-requests/{self.access_request.id}/",
            payload,
            format="json",
        )

    def test_patch_status_approved_is_ignored(self):
        """The pre-fix serializer wrote ``{"status": "APPROVED"}``
        straight through — an unguarded, unaudited, chain-free
        approval.  Now the field is read-only: the write is ignored
        and the request stays PENDING."""
        response = self._patch({"status": "APPROVED"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.access_request.refresh_from_db()
        self.assertEqual(
            self.access_request.status, AccessRequestStatus.PENDING
        )
        self.assertEqual(response.data["status"], AccessRequestStatus.PENDING.value)

    def test_patch_approval_workflow_and_approvers_ignored(self):
        """The multi-step chain state cannot be rewritten through the
        serializer (the workflow snapshot + step ledger are service-
        owned)."""
        response = self._patch(
            {
                "approval_workflow": [{"step": 0, "role": "TENANT_ADMIN"}],
                "approvers": [str(self.user.id)],
                "current_approval_step": 5,
            }
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.access_request.refresh_from_db()
        self.assertEqual(self.access_request.approval_workflow, [])
        self.assertEqual(self.access_request.current_approval_step, 0)

    def test_patch_rejection_reason_ignored(self):
        """rejection_reason is set only by the reject service action."""
        response = self._patch({"rejection_reason": "smuggled"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.access_request.refresh_from_db()
        self.assertIsNone(self.access_request.rejection_reason)

    def test_patch_reason_still_writable(self):
        """The client-facing fields stay writable (the legit PATCH
        surface is reason + requested_access_type)."""
        response = self._patch({"reason": "updated matrix reason"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.access_request.refresh_from_db()
        self.assertEqual(self.access_request.reason, "updated matrix reason")


class ARMatrixCoverageTest(TestCase):
    """The machine covers every hop a real writer performs."""

    def test_matrix_covers_the_real_surface_hops(self):
        self.assertIn("REVOKED", ALLOWED_TRANSITIONS["PENDING"])
        self.assertIn("EXPIRED", ALLOWED_TRANSITIONS["PENDING"])
        self.assertIn("REVOKED", ALLOWED_TRANSITIONS["APPROVED"])
        self.assertIn("EXPIRED", ALLOWED_TRANSITIONS["APPROVED"])
        # Terminal states have no outgoing hops.
        for terminal in ("REJECTED", "REVOKED", "EXPIRED"):
            self.assertEqual(ALLOWED_TRANSITIONS[terminal], set())

    def test_business_rules_table_matches_the_machine(self):
        """The business-rules transition validator uses the MACHINE's
        table (pre-fix: a divergent local copy that rejected
        PENDING_NEXT_APPROVER→APPROVED)."""
        rules = GovernanceBusinessRules()
        ar = AccessRequest(
            tenant_id=uuid.uuid4(),
            requested_by_id=uuid.uuid4(),
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING_NEXT_APPROVER,
        )
        result = rules._validate_access_request_status_transition(
            ar,
            current_status=AccessRequestStatus.PENDING_NEXT_APPROVER.value,
            new_status=AccessRequestStatus.APPROVED.value,
        )
        self.assertTrue(result.is_valid, f"PNA→APPROVED must be legal: {result.errors}")

        result = rules._validate_access_request_status_transition(
            ar,
            current_status=AccessRequestStatus.REJECTED.value,
            new_status=AccessRequestStatus.APPROVED.value,
        )
        self.assertFalse(result.is_valid, "REJECTED→APPROVED must stay illegal")
