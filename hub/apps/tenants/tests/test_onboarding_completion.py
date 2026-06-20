"""
Phase 250.6.D — Tenant onboarding-completion tracking.

TDD pin for the three signals that together flip
``Tenant.onboarding_completed_at`` from NULL to a timestamp:

  1. Tenant admin invited — at least one user holds the
     ``TENANT_ADMIN`` role for this tenant.
  2. KYC submitted — ``Tenant.kyc_status`` is anything other than
     ``UNVERIFIED`` (i.e. PENDING_REVIEW or VERIFIED). "Submitted"
     captures the user's ACTION, not the provider's verdict — a
     tenant whose KYC is under review still cleared the onboarding
     step. Treating UNVERIFIED as the only "not yet submitted"
     state matches the existing ``KYCStatus`` enum semantics.
  3. Billing setup — at least one ``Subscription`` row exists with
     status in {ACTIVE, TRIAL, PAST_DUE}. ``CANCELED`` /
     ``INCOMPLETE`` / ``INCOMPLETE_EXPIRED`` / ``UNPAID`` do NOT
     count: they represent NO active billing relationship, and
     gating asset creation behind a real subscription is the
     load-bearing point of the gate.

The companion test module ``test_onboarding_completion_signals.py``
covers the signal-driven side (post_save handlers actually firing
and persisting the timestamp). This module pins the PURE FUNCTIONS
in ``hub.apps.tenants.onboarding`` so a future refactor can verify
the helpers behave correctly outside of the Django signal cascade.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus
from hub.apps.tenants.onboarding import (
    compute_onboarding_state,
    evaluate_onboarding_completion,
    mark_onboarding_complete_if_ready,
)
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant(*, slug_prefix: str = "ob", asset_creation_enabled: bool = False) -> Tenant:
    """Create an unsaved-state-fresh tenant with no roles, no users, no sub.

    Uses ``asset_creation_enabled=False`` to mirror what the onboarding
    service should produce for new tenants (250.6.D.1 requirement —
    the gate stays closed until onboarding completes). Tests that
    want the existing-tenant default of ``True`` pass it explicitly.
    """
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix.title()} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        asset_creation_enabled=asset_creation_enabled,
    )


def _grant_tenant_admin(tenant: Tenant) -> User:
    """Create a user + assign TENANT_ADMIN role on this tenant.

    Uses the canonical role-assignment pattern (``Role.get_or_create``
    + ``UserRole.get_or_create``) — the same shape the onboarding
    service uses, so the signal handlers see real ``UserRole.save``
    events.
    """
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"admin-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant admin"},
    )
    UserRole.objects.create(user=user, tenant=tenant, role=role)
    return user


def _grant_subscription(tenant: Tenant, *, status: str = SubscriptionStatus.ACTIVE) -> Subscription:
    """Create a real Subscription row in the requested status.

    Uses the existing ``TenantPlan`` if one exists or seeds a
    minimal one — keeping the test self-contained without any
    fixture dependency.
    """
    plan, _ = TenantPlan.objects.get_or_create(
        slug="onboarding-test-free",
        defaults={
            "name": "Onboarding Test Free",
            "tier": PlanTier.FREE,
            "is_active": True,
            "limits_json": {},
        },
    )
    return Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=status,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timezone.timedelta(days=30),
    )


# ---------------------------------------------------------------------------
# evaluate_onboarding_completion(tenant) → bool
# ---------------------------------------------------------------------------


class EvaluateOnboardingCompletionTests(TestCase):
    """Pin the three-signal truth table.

    ``evaluate_onboarding_completion`` is a pure function: it takes a
    tenant, queries the ORM (no caching, no side effects), and
    returns True iff all three signals are satisfied. It NEVER
    writes; the side-effecting wrapper is
    ``mark_onboarding_complete_if_ready``.
    """

    def test_fresh_tenant_returns_false(self):
        """No admin, no KYC, no sub → False."""
        tenant = _make_tenant()
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_only_tenant_admin_returns_false(self):
        """Admin alone is not enough — needs KYC + billing too."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_only_kyc_submitted_returns_false(self):
        """KYC alone is not enough — needs admin + billing too."""
        tenant = _make_tenant()
        tenant.kyc_status = KYCStatus.PENDING_REVIEW
        tenant.save(update_fields=["kyc_status"])
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_only_subscription_returns_false(self):
        """Subscription alone is not enough — needs admin + KYC too."""
        tenant = _make_tenant()
        _grant_subscription(tenant)
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_all_three_with_kyc_pending_review_returns_true(self):
        """admin + KYC PENDING_REVIEW + ACTIVE sub → True.

        PENDING_REVIEW counts as "submitted" — the user took the KYC
        action; the provider hasn't yet verified. Asset creation can
        proceed; production publish_to_marketplace remains gated on
        VERIFIED at a different layer (see ``Tenant.can_publish_to_marketplace``).
        """
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.PENDING_REVIEW
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)
        self.assertTrue(evaluate_onboarding_completion(tenant))

    def test_all_three_with_kyc_verified_returns_true(self):
        """admin + KYC VERIFIED + ACTIVE sub → True (most common end state)."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)
        self.assertTrue(evaluate_onboarding_completion(tenant))

    def test_kyc_unverified_keeps_returning_false(self):
        """The default KYCStatus.UNVERIFIED is NOT submitted."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        # kyc_status stays UNVERIFIED (default)
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_subscription_canceled_does_not_count(self):
        """CANCELED is a terminal state — NOT an active billing relationship."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.CANCELED)
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_subscription_incomplete_expired_does_not_count(self):
        """Expired-incomplete is the failure mode of stripe checkout — not active."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.INCOMPLETE_EXPIRED)
        self.assertFalse(evaluate_onboarding_completion(tenant))

    def test_subscription_trial_counts(self):
        """TRIAL is a real billing relationship (Stripe charges trial-end)."""
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.TRIAL)
        self.assertTrue(evaluate_onboarding_completion(tenant))

    def test_subscription_past_due_counts(self):
        """PAST_DUE is still an active subscription — Stripe is retrying.

        Gating asset creation behind PAST_DUE would punish a tenant
        for a Stripe retry that's about to succeed. The dunning surface
        is a separate UX layer (banner + email); onboarding completion
        is about "did we get a billing relationship at all".
        """
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.PAST_DUE)
        self.assertTrue(evaluate_onboarding_completion(tenant))


# ---------------------------------------------------------------------------
# compute_onboarding_state(tenant) → dict (diagnostic for UI / debugging)
# ---------------------------------------------------------------------------


class ComputeOnboardingStateTests(TestCase):
    """Pin the per-signal breakdown helper.

    The diagnostic helper returns the three sub-flags so the SPA can
    render a checklist (admin invited ✓ / KYC submitted ✗ / billing
    setup ✗) instead of the binary "not done" result. The helper is
    pure — no DB writes, no side effects.
    """

    def test_returns_all_false_for_fresh_tenant(self):
        tenant = _make_tenant()
        state = compute_onboarding_state(tenant)
        self.assertEqual(
            state,
            {
                "tenant_admin_invited": False,
                "kyc_submitted": False,
                "billing_setup": False,
                "all_complete": False,
            },
        )

    def test_returns_partial_state(self):
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        state = compute_onboarding_state(tenant)
        self.assertTrue(state["tenant_admin_invited"])
        self.assertFalse(state["kyc_submitted"])
        self.assertFalse(state["billing_setup"])
        self.assertFalse(state["all_complete"])

    def test_returns_all_true_when_all_signals_satisfied(self):
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)
        state = compute_onboarding_state(tenant)
        self.assertTrue(state["tenant_admin_invited"])
        self.assertTrue(state["kyc_submitted"])
        self.assertTrue(state["billing_setup"])
        self.assertTrue(state["all_complete"])


# ---------------------------------------------------------------------------
# mark_onboarding_complete_if_ready(tenant) — idempotent side-effecting wrapper
# ---------------------------------------------------------------------------


class MarkOnboardingCompleteIfReadyTests(TestCase):
    """Pin the side-effect contract.

    Contract:
      - When all three signals satisfied AND ``onboarding_completed_at IS NULL``:
        sets the timestamp to ``timezone.now()`` AND flips
        ``asset_creation_enabled`` to True (so the kill-switch
        gate releases automatically when onboarding completes).
      - When not all signals satisfied: NO-OP (timestamp stays NULL).
      - When timestamp is already set: NO-OP (idempotent — never
        overwrites an existing completion timestamp; ops can manually
        clear if they want a re-onboarding flow).
      - Returns True iff the call DID set the timestamp; False otherwise.
        The boolean return lets signal handlers decide whether to emit
        the ``ONBOARDING_COMPLETED`` audit event (only on the
        false-to-set transition).
    """

    def test_returns_false_when_signals_unsatisfied(self):
        tenant = _make_tenant()
        result = mark_onboarding_complete_if_ready(tenant)
        self.assertFalse(result)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)

    def test_returns_true_and_sets_timestamp_when_signals_satisfied(self):
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)

        result = mark_onboarding_complete_if_ready(tenant)
        self.assertTrue(result)

        tenant.refresh_from_db()
        self.assertIsNotNone(tenant.onboarding_completed_at)
        # Timestamp lands within the last few seconds.
        delta = timezone.now() - tenant.onboarding_completed_at
        self.assertLess(delta.total_seconds(), 5)

    def test_flips_asset_creation_enabled_when_completing(self):
        """Onboarding completion releases the kill switch automatically.

        The 250.6.A audit-pass identified the gap: new tenants would
        otherwise stay at ``asset_creation_enabled=False`` forever.
        The completion event is the natural moment to flip it on.
        """
        tenant = _make_tenant(asset_creation_enabled=False)
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)

        mark_onboarding_complete_if_ready(tenant)

        tenant.refresh_from_db()
        self.assertTrue(tenant.asset_creation_enabled)

    def test_does_not_flip_asset_creation_enabled_back_when_already_true(self):
        """Existing tenant (default True) stays True. We never flip True→False here."""
        tenant = _make_tenant(asset_creation_enabled=True)
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)

        mark_onboarding_complete_if_ready(tenant)

        tenant.refresh_from_db()
        self.assertTrue(tenant.asset_creation_enabled)

    def test_is_idempotent_when_timestamp_already_set(self):
        """Re-invoking after completion does NOT update the timestamp.

        Onboarding-completion is a one-way ratchet. Returning False
        on the second call lets signal handlers know "no audit event
        to emit this time".
        """
        tenant = _make_tenant()
        _grant_tenant_admin(tenant)
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status"])
        _grant_subscription(tenant, status=SubscriptionStatus.ACTIVE)

        first_result = mark_onboarding_complete_if_ready(tenant)
        self.assertTrue(first_result)
        tenant.refresh_from_db()
        first_timestamp = tenant.onboarding_completed_at

        # Force time to advance noticeably so the assertion is meaningful.
        # Re-invoke; timestamp must NOT change, return must be False.
        second_result = mark_onboarding_complete_if_ready(tenant)
        self.assertFalse(second_result)

        tenant.refresh_from_db()
        self.assertEqual(tenant.onboarding_completed_at, first_timestamp)
