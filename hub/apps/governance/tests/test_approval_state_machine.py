"""
Phase 274.5.4 — approval state machine tests (8 cases).

Covers PENDING_NEXT_APPROVER transitions from the state_machine module.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.governance.business_rules import (
    ApprovalQuorumRule,
    ApprovalStageRule,
    ApproverIdentityRule,
)
from hub.apps.governance.state_machine import (
    ALLOWED_TRANSITIONS,
    APPROVED,
    PENDING,
    PENDING_NEXT_APPROVER,
    REJECTED,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.journey("JOURNEY-CPO-011")]


class TestApprovalStateMachine(TestCase):
    """Phase 274.5 — state machine constants and transitions."""

    def test_pending_allows_next_approver(self):
        assert PENDING_NEXT_APPROVER in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_allows_approved(self):
        assert APPROVED in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_allows_rejected(self):
        assert REJECTED in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_next_allows_approved(self):
        assert APPROVED in ALLOWED_TRANSITIONS[PENDING_NEXT_APPROVER]

    def test_pending_next_allows_rejected(self):
        assert REJECTED in ALLOWED_TRANSITIONS[PENDING_NEXT_APPROVER]

    def test_approved_allows_revoked(self):
        assert "REVOKED" in ALLOWED_TRANSITIONS[APPROVED]

    def test_rejected_is_terminal(self):
        assert ALLOWED_TRANSITIONS[REJECTED] == set()

    def test_constants_are_strings(self):
        assert isinstance(PENDING, str)
        assert isinstance(PENDING_NEXT_APPROVER, str)
        assert isinstance(APPROVED, str)
        assert isinstance(REJECTED, str)


class TestApprovalRules(TestCase):
    """Phase 274.5 — composable rule classes for approval."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ASM-{uid}",
            slug=f"asm-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.active_user = User.objects.create_user(
            email=f"asm-active-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.inactive_user = User.objects.create_user(
            email=f"asm-inactive-{uid}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.DISABLED,
        )

    def test_approver_identity_active_user_passes(self):
        rule = ApproverIdentityRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.active_user.id),
        )
        result = rule.validate(None, self.tenant, self.active_user)
        assert result.is_valid

    def test_approver_identity_inactive_user_fails(self):
        rule = ApproverIdentityRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.inactive_user.id),
        )
        result = rule.validate(None, self.tenant, self.inactive_user)
        assert not result.is_valid
        assert "not active" in str(result.errors).lower()

    def test_approval_stage_pending_transition_valid(self):
        from hub.apps.governance.models import AccessRequest, AccessRequestStatus

        ar = AccessRequest(
            tenant=self.tenant,
            status=AccessRequestStatus.PENDING,
            requested_by=self.active_user,
        )
        rule = ApprovalStageRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.active_user.id),
        )
        result = rule.validate_transition(ar, self.tenant, self.active_user)
        assert result.is_valid

    def test_approval_stage_invalid_transition(self):
        """A REJECTED request cannot transition to APPROVED."""
        from hub.apps.governance.models import AccessRequest

        ar = AccessRequest(
            tenant=self.tenant,
            status="REJECTED",
            requested_by=self.active_user,
        )
        rule = ApprovalStageRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.active_user.id),
        )
        result = rule.validate_transition(ar, self.tenant, self.active_user)
        assert not result.is_valid

    def test_approval_quorum_passes_without_prior_approver(self):
        from hub.apps.governance.models import AccessRequest

        ar = AccessRequest(
            tenant=self.tenant,
            requested_by=self.active_user,
        )
        rule = ApprovalQuorumRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.active_user.id),
        )
        result = rule.validate(ar, self.tenant)
        assert result.is_valid

    def test_approval_quorum_blocks_consecutive_same_approver(self):
        """Anti-self-dealing: same user cannot approve consecutive steps."""
        from hub.apps.governance.models import AccessRequest

        ar = AccessRequest(
            tenant=self.tenant,
            requested_by=self.active_user,
            approved_by=self.active_user,
        )
        rule = ApprovalQuorumRule(
            tenant_id=str(self.tenant.id),
            user_id=str(self.active_user.id),
        )
        result = rule.validate(ar, self.tenant)
        assert not result.is_valid

    def test_approval_quorum_allows_different_user_approver(self):
        """Quorum rule allows a different approver than the requester."""
        from hub.apps.governance.models import AccessRequest

        # Create a second active user to serve as approver
        approver = User.objects.create_user(
            email=f"asm-approver-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # requested_by is active_user, approved_by is a different user → should pass
        ar = AccessRequest(
            tenant=self.tenant,
            requested_by=self.active_user,
            approved_by=approver,
        )
        rule = ApprovalQuorumRule(
            tenant_id=str(self.tenant.id),
            user_id=str(approver.id),
        )
        result = rule.validate(ar, self.tenant)
        assert result.is_valid, (
            f"Different-user approver should pass quorum, got errors: {result.errors}"
        )

    def test_multi_step_chain_different_approvers(self):
        """Multi-step chain: different approver per step is valid."""
        from hub.apps.governance.models import AccessRequest

        # Create two approvers for the chain
        approver_1 = User.objects.create_user(
            email=f"asm-step1-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        approver_2 = User.objects.create_user(
            email=f"asm-step2-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # 2-step approval chain — step 1 approved by approver_1,
        # step 2 to be approved by approver_2.
        chain = [
            {"step": 1, "approvers": [str(approver_1.id)], "required_count": 1},
            {"step": 2, "approvers": [str(approver_2.id)], "required_count": 1},
        ]

        # Simulate first step approval by approver_1
        ar = AccessRequest(
            tenant=self.tenant,
            requested_by=self.active_user,
            approved_by=approver_1,
            status="PENDING_NEXT_APPROVER",
        )
        ar.approval_workflow = chain

        # approver_1 is the previous approver, approver_2 is the current one
        # Anti-self-dealing: approver_2 != previous_approver → should pass
        rule = ApprovalQuorumRule(
            tenant_id=str(self.tenant.id),
            user_id=str(approver_2.id),
        )
        result = rule.validate(ar, self.tenant)
        assert result.is_valid, (
            f"Different approver per step should pass quorum, got errors: {result.errors}"
        )

        # Verify the chain contains the expected steps
        assert len(ar.approval_workflow) == 2
        assert ar.approval_workflow[0]["step"] == 1
        assert ar.approval_workflow[1]["step"] == 2

    # ── Phase 277.4.4 — depth expansion ────────────────────────────

    def test_constants_match_model_choices(self):
        """PENDING_NEXT_APPROVER string matches AccessRequestStatus value."""
        from hub.apps.governance.models import AccessRequestStatus

        assert AccessRequestStatus.PENDING_NEXT_APPROVER.value == PENDING_NEXT_APPROVER, (
            f"state_machine.PENDING_NEXT_APPROVER={PENDING_NEXT_APPROVER} "
            f"!= AccessRequestStatus value={AccessRequestStatus.PENDING_NEXT_APPROVER.value}"
        )

    def test_allowed_transitions_cover_all_statuses(self):
        """Every AccessRequestStatus value has a transition entry."""
        from hub.apps.governance.models import AccessRequestStatus

        for status in AccessRequestStatus.values:
            assert status in ALLOWED_TRANSITIONS, (
                f"Status {status} missing from ALLOWED_TRANSITIONS"
            )
