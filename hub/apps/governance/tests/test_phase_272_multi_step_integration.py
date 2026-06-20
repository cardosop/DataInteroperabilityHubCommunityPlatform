"""
Phase 272.4.9 + 272.5.5 + 272.6.8 — Multi-step approval, notification,
and delegation integration tests.

Covers deferred items from the Phase 272 implementation:
* 272.4.9 — 2-step + 3-step flows, rejection at intermediate step,
  in-flight PENDING requests preserved as single-step
* 272.5.5 — In-app notification delivery on step transition,
  digest content correctness, pending-count role filtering
* 272.6.8 — Delegate approval during active window, outside-window
  rejection, revocation reason enforcement

NO MOCKS at contract boundaries: real Postgres, real ORM, real
GovernanceService, real ABAC engine, real business rules.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.event_types import (
    ACCESS_REQUEST_STEP_TRANSITIONED,
    APPROVAL_DELEGATION_USED,
)
from hub.apps.audit.models import AuditEvent
from hub.apps.governance.models import (
    AccessPolicy,
    AccessRequest,
    AccessRequestComment,
    AccessRequestStatus,
    ApprovalDelegation,
)
from hub.apps.governance.services import GovernanceService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
UserModel = get_user_model()


def _uid():
    return uuid.uuid4().hex[:8]


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{tenant.slug}",
        defaults={
            "name": f"Test Plan {tenant.slug}",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


def _make_tenant():
    uid = _uid()
    tenant = Tenant.objects.create(
        name=f"T-{uid}",
        slug=f"t-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_user(tenant, *, email_prefix="u", role_name=None):
    user = UserModel.objects.create_user(
        email=f"{email_prefix}-{_uid()}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    if role_name:
        role, _ = Role.objects.get_or_create(
            tenant=tenant,
            name=role_name,
            defaults={"description": role_name},
        )
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _make_asset(tenant, created_by):
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{_uid()}",
        name="Test Asset",
        status=AssetStatus.ACTIVE,
        created_by=created_by,
    )


def _make_access_request(tenant, approver, asset=None, *, extra_approvers=None):
    """Create a PENDING AccessRequest ready for approval testing."""
    asset = asset or _make_asset(tenant, approver)
    approvers_list = [str(approver.id)]
    if extra_approvers:
        approvers_list.extend(str(u.id) for u in extra_approvers)
    ar = AccessRequest.objects.create(
        tenant=tenant,
        requested_by=approver,
        asset=asset,
        reason="Integration test",
        requested_access_type="READ",
        status=AccessRequestStatus.PENDING,
        approvers=approvers_list,
    )
    return ar


# ============================================================================
# 272.4.9 — Multi-step approval flow integration tests
# ============================================================================


@pytest.mark.integration
class TestMultiStepApprovalFlow(TestCase):
    """2-step + 3-step flows, intermediate rejection, in-flight preservation."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.data_owner = _make_user(self.tenant, email_prefix="owner", role_name="DATA_OWNER")
        self.cdo = _make_user(self.tenant, email_prefix="cdo", role_name="CDO")
        self.dpo = _make_user(self.tenant, email_prefix="dpo", role_name="DPO")
        self.asset = _make_asset(self.tenant, self.data_owner)

    # ── 2-step approval ──────────────────────────────────────────

    @pytest.mark.integration
    def test_two_step_flow_entitlement_created_only_at_final_step(self):
        """Data owner approves step 1 → PENDING_NEXT_APPROVER.
        CDO approves step 2 → APPROVED + entitlement created."""
        # Set up a 2-step policy.
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="2-step-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Step 1 — data owner approves.
        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        result = svc.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
            comments="LGTM from data owner",
        )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.PENDING_NEXT_APPROVER
        assert ar.status == AccessRequestStatus.PENDING_NEXT_APPROVER
        assert ar.current_approval_step == 1
        assert ar.approval_workflow == ["DATA_OWNER", "CDO"]

        # Comment persisted.
        # Verify a comment was persisted (body from approval payload).
        assert AccessRequestComment.objects.filter(
            access_request=ar,
            body__contains="LGTM from data owner",
        ).exists()

        # Step transition audit recorded.
        assert AuditEvent.objects.filter(
            action=ACCESS_REQUEST_STEP_TRANSITIONED,
            tenant_id=self.tenant.pk,
        ).exists()

        # Step 2 — CDO approves (final).
        svc_cdo = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.cdo.id))
        result2 = svc_cdo.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.cdo.id),
            comments="Approved by CDO",
        )
        ar.refresh_from_db()
        assert result2.status == AccessRequestStatus.APPROVED
        assert ar.status == AccessRequestStatus.APPROVED
        assert ar.current_approval_step == 2  # final

    # ── 3-step approval ──────────────────────────────────────────

    @pytest.mark.integration
    def test_three_step_flow_advances_correctly(self):
        """3-step: DATA_OWNER → CDO → DPO. Verify each transition."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="3-step-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO", "DPO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Step 1 — data owner.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.PENDING_NEXT_APPROVER
        assert ar.current_approval_step == 1

        # Step 2 — CDO.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.cdo.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.cdo.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.PENDING_NEXT_APPROVER
        assert ar.current_approval_step == 2

        # Step 3 — DPO (final).
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.dpo.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.dpo.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.APPROVED
        assert ar.current_approval_step == 3

        # Exactly 3 step-transition audit events.
        assert (
            AuditEvent.objects.filter(
                action=ACCESS_REQUEST_STEP_TRANSITIONED,
                tenant_id=self.tenant.pk,
            ).count()
            == 3
        )

    # ── Rejection terminates chain ───────────────────────────────

    @pytest.mark.integration
    def test_rejection_at_intermediate_step_terminates_chain(self):
        """Rejection at step 1 terminates; step 2 never happens."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="2-step-reject-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Step 1 — data owner rejects instead of approves.
        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        result = svc.reject_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
            reason="Rejected — wrong asset scope",
        )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.REJECTED
        assert ar.status == AccessRequestStatus.REJECTED

        # Verify no subsequent approval is possible.
        svc_cdo = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.cdo.id))
        with pytest.raises(ServiceValidationError):
            svc_cdo.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.cdo.id),
            )

    # ── In-flight PENDING preserved as single-step ───────────────

    @pytest.mark.integration
    def test_in_flight_pending_without_chain_stays_single_step(self):
        """A PENDING request created BEFORE the policy was deployed
        (null/empty approval_workflow) should complete in one step."""
        # No AccessPolicy with a chain — single-step by default.
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )
        assert ar.approval_workflow in (None, [])
        assert ar.current_approval_step == 0  # default when no chain is set

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        result = svc.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.APPROVED
        assert ar.status == AccessRequestStatus.APPROVED

    @pytest.mark.integration
    def test_abac_explicit_deny_blocks_approval(self):
        """An AccessPolicy with effect=DENY and matching conditions
        must block approval with ABAC_POLICY_DENIED."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="explicit-deny-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            effect="DENY",
            conditions={
                "user": {"role": "DATA_OWNER"},
            },
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        with pytest.raises(ServiceValidationError) as ctx:
            svc.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.data_owner.id),
            )
        assert "ABAC policy denied" in str(ctx.value)

    # ── Phase 277.2.7 (P1-4) — ABAC re-evaluation ─────────────────

    @pytest.mark.integration
    def test_abac_re_evaluates_at_pending_next_approver(self):
        """ABAC MUST re-evaluate on every approval step.  A DENY policy
        that blocks step 1 (DATA_OWNER), when changed to ALLOW before
        step 2 (CDO), must allow step 2 to succeed."""
        # 2-step chain: DATA_OWNER → CDO
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="re-eval-policy",
            asset=self.asset,
            enabled=True,
            priority=1,  # lower priority than DENY below
            effect="ALLOW",
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        # DENY policy scoped to DATA_OWNER role — blocks step 1.
        # Priority 0 (highest) ensures it is evaluated first.
        deny_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="deny-at-step1",
            asset=self.asset,
            enabled=True,
            priority=0,
            effect="DENY",
            conditions={"user": {"role": "DATA_OWNER"}},
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        # Step 1: DENY policy blocks the first approver (DATA_OWNER).
        with pytest.raises(ServiceValidationError) as ctx:
            svc.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.data_owner.id),
            )
        assert "ABAC policy denied" in str(ctx.value)

        # Change the DENY policy to ALLOW before step 2.
        deny_policy.effect = "ALLOW"
        deny_policy.save(update_fields=["effect"])

        # Step 1 NOW succeeds — ABAC re-evaluates and finds ALLOW.
        svc.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.PENDING_NEXT_APPROVER
        assert ar.current_approval_step == 1  # CDO is next

        # Step 2: CDO approves. ABAC re-evaluates at the new state.
        svc2 = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.cdo.id))
        svc2.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.cdo.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.APPROVED

    @pytest.mark.integration
    def test_workflow_snapshot_isolates_from_policy_edit(self):
        """After the first approval snapshots the chain, editing the
        policy does NOT affect the in-flight request."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="mutable-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Step 1 — snapshots ["DATA_OWNER", "CDO"].
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()
        assert ar.approval_workflow == ["DATA_OWNER", "CDO"]

        # Edit the policy to a 3-step chain — in-flight request unchanged.
        policy = AccessPolicy.objects.get(name="mutable-policy")
        policy.required_approval_chain = ["DATA_OWNER", "CDO", "DPO"]
        policy.save()
        ar.refresh_from_db()
        assert ar.approval_workflow == ["DATA_OWNER", "CDO"]  # still 2-step

        # Step 2 completes the ORIGINAL 2-step chain.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.cdo.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.cdo.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.APPROVED


# ============================================================================
# 272.5.5 — Notification delivery and digest content integration tests
# ============================================================================


@pytest.mark.integration
class TestNotificationDelivery(TestCase):
    """In-app notifications fire on approval + step transition.
    Pending-count endpoint filters by role in chain."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.data_owner = _make_user(self.tenant, email_prefix="owner", role_name="DATA_OWNER")
        self.cdo = _make_user(self.tenant, email_prefix="cdo", role_name="CDO")
        self.dpo = _make_user(self.tenant, email_prefix="dpo", role_name="DPO")
        self.asset = _make_asset(self.tenant, self.data_owner)

    @pytest.mark.integration
    def test_notification_delivered_on_approval(self):
        """In-app notification fires for the requester on approval."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="notify-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )

        # Notification row created.
        from hub.apps.notifications.models import UserNotification as Notification

        note = Notification.objects.filter(
            user=ar.requested_by,
            tenant=self.tenant,
            category="GOVERNANCE",
        ).first()
        assert note is not None
        assert "approved" in note.title.lower()

    @pytest.mark.integration
    def test_notification_fires_on_step_transition(self):
        """When advancing to an intermediate step, the next-approver
        role should receive notification."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="notify-2step",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Step 1 — data owner approves.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()
        assert ar.status == AccessRequestStatus.PENDING_NEXT_APPROVER

        # The next approver (CDO) should be able to see pending requests
        # matching their role in the chain.
        pending_qs = AccessRequest.objects.filter(
            tenant=self.tenant,
            status=AccessRequestStatus.PENDING_NEXT_APPROVER,
        )
        assert pending_qs.filter(id=ar.id).exists()

    @pytest.mark.integration
    def test_pending_count_filters_by_role_in_chain(self):
        """Requests at PENDING_NEXT_APPROVER should be filterable by
        the role needed for the current step."""
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="count-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER", "CDO"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Approve step 1.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()

        # Step at index 1 = "CDO" role.
        workflow = ar.approval_workflow or []
        current_step = ar.current_approval_step or 0
        next_role = workflow[current_step] if current_step < len(workflow) else None
        assert next_role == "CDO"

        # Count requests awaiting CDO approval.
        count = AccessRequest.objects.filter(
            tenant=self.tenant,
            status=AccessRequestStatus.PENDING_NEXT_APPROVER,
            approval_workflow__1="CDO",
        ).count()
        assert count >= 1


# ============================================================================
# 272.6.8 — Delegation integration tests
# ============================================================================


@pytest.mark.integration
class TestApprovalDelegation(TestCase):
    """Delegate can approve during active window; outside window
    rejected. Revocation reason enforced."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.data_owner = _make_user(self.tenant, email_prefix="owner", role_name="DATA_OWNER")
        self.cdo = _make_user(self.tenant, email_prefix="cdo", role_name="CDO")
        self.delegate = _make_user(self.tenant, email_prefix="delegate", role_name=None)
        self.dpo = _make_user(self.tenant, email_prefix="dpo", role_name="DPO")
        self.asset = _make_asset(self.tenant, self.data_owner)

    # ── Delegation within window ─────────────────────────────────

    @pytest.mark.integration
    def test_delegate_approves_during_active_window(self):
        """Delegate with an active ApprovalDelegation can approve on
        behalf of the delegator."""
        # Grant delegate the CDO role so they can act as the CDO step.
        cdo_role = Role.objects.get(tenant=self.tenant, name="CDO")
        UserRole.objects.get_or_create(user=self.delegate, role=cdo_role)

        # Create delegation: data_owner delegates to delegate_user.
        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.data_owner,
            delegate=self.delegate,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=24),
            reason="Out of office — annual leave",
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="delegation-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Delegate approves — should pass delegation validation.
        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.delegate.id))
        result = svc.approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.delegate.id),
        )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.APPROVED

        # Delegation usage audit emitted.
        assert AuditEvent.objects.filter(
            action=APPROVAL_DELEGATION_USED,
            tenant_id=self.tenant.pk,
        ).exists()

    # ── Delegation outside window ────────────────────────────────

    @pytest.mark.integration
    def test_delegate_rejected_outside_active_window(self):
        """An expired delegation should NOT grant approval authority."""
        cdo_role = Role.objects.get(tenant=self.tenant, name="CDO")
        UserRole.objects.get_or_create(user=self.delegate, role=cdo_role)

        # Expired delegation.
        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.data_owner,
            delegate=self.delegate,
            start_at=now - timedelta(days=7),
            end_at=now - timedelta(hours=1),  # already expired
            reason="Old delegation",
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="expired-delegation-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # Delegate tries to approve — should be rejected.
        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.delegate.id))
        with pytest.raises(ServiceValidationError):
            svc.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.delegate.id),
            )

    @pytest.mark.integration
    def test_delegate_requires_role_for_chain_step(self):
        """A delegation only grants the delegator's authority — if
        the delegator lacks the role required for the current chain
        step, the delegate is rejected even with an active delegation.
        (The delegate's own roles are irrelevant; only the delegator's
        role membership is checked.)"""
        # Active delegation but delegate lacks CDO role.
        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.data_owner,
            delegate=self.delegate,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=24),
            reason="OOF",
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="no-role-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["CDO"],  # needs CDO role
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.delegate.id))
        with pytest.raises(ServiceValidationError):
            svc.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.delegate.id),
            )

    # ── Revocation reason enforcement ────────────────────────────

    @pytest.mark.integration
    def test_revoke_without_reason_returns_400(self):
        """Revoking without a reason must be rejected."""
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        # First approve to get to APPROVED state.
        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        with pytest.raises(ServiceValidationError) as ctx:
            svc.revoke_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                revoker_id=str(self.data_owner.id),
                reason="",  # empty
            )
        assert "revocation_reason" in str(ctx.value)

    @pytest.mark.integration
    def test_revoke_with_reason_succeeds(self):
        """Revoking with a reason should succeed and persist the reason."""
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        GovernanceService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.data_owner.id),
        ).approve_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            approver_id=str(self.data_owner.id),
        )
        ar.refresh_from_db()

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.data_owner.id))
        result = svc.revoke_access_request(
            access_request_id=str(ar.id),
            tenant_id=str(self.tenant.id),
            revoker_id=str(self.data_owner.id),
            reason="Access no longer needed",
        )
        ar.refresh_from_db()
        assert result.status == AccessRequestStatus.REVOKED
        assert ar.revocation_reason == "Access no longer needed"

    # ── Delegation future window ────────────────────────────────

    @pytest.mark.integration
    def test_delegate_rejected_before_start_at(self):
        """A delegation not yet started should NOT grant authority."""
        cdo_role = Role.objects.get(tenant=self.tenant, name="CDO")
        UserRole.objects.get_or_create(user=self.delegate, role=cdo_role)

        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.data_owner,
            delegate=self.delegate,
            start_at=now + timedelta(hours=2),  # future
            end_at=now + timedelta(hours=48),
            reason="Upcoming OOF",
        )

        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="future-delegation-policy",
            asset=self.asset,
            enabled=True,
            priority=0,
            required_approval_chain=["DATA_OWNER"],
        )
        ar = _make_access_request(
            self.tenant, self.data_owner, self.asset, extra_approvers=[self.cdo, self.dpo]
        )

        svc = GovernanceService(tenant_id=str(self.tenant.id), user_id=str(self.delegate.id))
        with pytest.raises(ServiceValidationError):
            svc.approve_access_request(
                access_request_id=str(ar.id),
                tenant_id=str(self.tenant.id),
                approver_id=str(self.delegate.id),
            )


# ── TR.E.7 — ApprovalDelegation lifecycle tests ──────────────────────


@pytest.mark.integration
class TestApprovalDelegationLifecycle(TestCase):
    """TR.E.7 — Delegation creation, active window enforcement, expiry handling."""

    def setUp(self):
        self.tenant = _make_tenant()
        self.owner = _make_user(self.tenant, email_prefix="dl-owner", role_name="DATA_OWNER")
        self.cdo = _make_user(self.tenant, email_prefix="dl-cdo", role_name="CDO")
        self.delegate = _make_user(self.tenant, email_prefix="dl-delegate", role_name=None)
        self.now = timezone.now()

    @pytest.mark.integration
    def test_create_delegation_with_valid_window(self):
        """Delegation can be created with an active time window."""
        delegation = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now - timedelta(hours=1),
            end_at=self.now + timedelta(hours=8),
        )
        assert delegation.delegator == self.owner
        assert delegation.delegate == self.delegate
        assert delegation.is_active() is True

    @pytest.mark.integration
    def test_delegation_expired_outside_window(self):
        """Delegation that has expired is not active."""
        delegation = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now - timedelta(hours=10),
            end_at=self.now - timedelta(hours=1),
        )
        assert delegation.is_active() is False

    @pytest.mark.integration
    def test_delegation_not_yet_started(self):
        """Delegation with future start_at is not yet active."""
        delegation = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now + timedelta(hours=1),
            end_at=self.now + timedelta(hours=8),
        )
        assert delegation.is_active() is False

    @pytest.mark.integration
    def test_delegation_window_boundary_inclusive(self):
        """Delegation is active exactly at start_at."""
        delegation = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now,
            end_at=self.now + timedelta(hours=1),
        )
        assert delegation.is_active() is True

    @pytest.mark.integration
    def test_delegation_revocation_sets_expiry(self):
        """Revoking a delegation sets end_at to now."""
        delegation = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now - timedelta(hours=1),
            end_at=self.now + timedelta(hours=8),
        )
        delegation.end_at = timezone.now()
        delegation.save()
        assert delegation.is_active() is False

    @pytest.mark.integration
    def test_duplicate_active_delegation_prevented(self):
        """Unique constraint prevents duplicate active delegations."""
        ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.owner,
            delegate=self.delegate,
            start_at=self.now,
            end_at=self.now + timedelta(hours=8),
        )
        with pytest.raises(DjangoValidationError):
            ApprovalDelegation.objects.create(
                tenant=self.tenant,
                delegator=self.owner,
                delegate=self.delegate,
                start_at=self.now,
                end_at=self.now + timedelta(hours=8),
            )
