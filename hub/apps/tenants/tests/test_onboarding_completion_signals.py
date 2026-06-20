"""
Phase 250.6.D — signal-driven onboarding-completion integration tests.

Companion to ``test_onboarding_completion.py`` (which pins the pure
helpers). This module pins the WIRING — the three post_save handlers
in ``hub.apps.tenants.signals`` actually fire on the right events
and produce the load-bearing side effects:

  * ``Tenant.onboarding_completed_at`` set to a real timestamp.
  * ``Tenant.asset_creation_enabled`` flipped from False → True.
  * Exactly ONE ``ONBOARDING_COMPLETED`` audit row emitted, regardless
    of which signal arrived last (we cover all three orderings).
  * Subsequent signals do NOT re-emit (idempotent ratchet).

Tests use real Django ORM rows + real django-rq dispatch is not
needed (signals fire synchronously in the test transaction).
``transaction=True`` is required so ``transaction.on_commit``
callbacks actually fire — without it, the signal handlers wouldn't
run because the test never commits.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TransactionTestCase
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _new_tenant() -> Tenant:
    """A tenant in the same starting state as the onboarding service produces.

    ``asset_creation_enabled=False`` — the gate starts CLOSED for new
    tenants. The signal handlers we're testing release the gate when
    onboarding completes.
    """
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"Sig {uid}",
        slug=f"sig-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        asset_creation_enabled=False,
    )


def _grant_admin(tenant: Tenant) -> User:
    """Grant TENANT_ADMIN — fires the UserRole.post_save handler."""
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"sig-{uid}@example.com",
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


def _submit_kyc(tenant: Tenant, *, status: str = KYCStatus.PENDING_REVIEW) -> None:
    """Submit KYC — fires the Tenant.post_save handler with the kyc_status delta.

    Goes through ``tenant.save()`` rather than ``QuerySet.update()``
    so the pre_save snapshot + post_save handlers fire (the existing
    KYC-audit handler also reads the snapshot).
    """
    tenant.kyc_status = status
    tenant.save(update_fields=["kyc_status"])


def _activate_subscription(
    tenant: Tenant, *, status: str = SubscriptionStatus.ACTIVE
) -> Subscription:
    """Create an active Subscription — fires the Subscription.post_save handler."""
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


def _onboarding_completed_audit_count(tenant: Tenant) -> int:
    return AuditEvent.objects.filter(tenant=tenant, action="ONBOARDING_COMPLETED").count()


# ---------------------------------------------------------------------------
# Each ordering of the three signals — completion fires when the LAST arrives.
# ---------------------------------------------------------------------------


class OnboardingSignalOrderingTests(TransactionTestCase):
    """All 3! = 6 orderings should converge on the same end state."""

    def test_admin_first_then_kyc_then_subscription(self):
        tenant = _new_tenant()

        _grant_admin(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertFalse(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 0)

        _submit_kyc(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertFalse(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 0)

        _activate_subscription(tenant)
        tenant.refresh_from_db()
        self.assertIsNotNone(tenant.onboarding_completed_at)
        self.assertTrue(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

        # The triggering signal carried in details_json:
        evt = AuditEvent.objects.get(tenant=tenant, action="ONBOARDING_COMPLETED")
        self.assertEqual(evt.details_json.get("triggered_by"), "subscription_activated")

    def test_kyc_first_then_subscription_then_admin(self):
        tenant = _new_tenant()
        _submit_kyc(tenant)
        _activate_subscription(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 0)

        _grant_admin(tenant)
        tenant.refresh_from_db()
        self.assertIsNotNone(tenant.onboarding_completed_at)
        self.assertTrue(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)
        evt = AuditEvent.objects.get(tenant=tenant, action="ONBOARDING_COMPLETED")
        self.assertEqual(evt.details_json.get("triggered_by"), "tenant_admin_assigned")

    def test_subscription_first_then_admin_then_kyc(self):
        tenant = _new_tenant()
        _activate_subscription(tenant)
        _grant_admin(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 0)

        _submit_kyc(tenant)
        tenant.refresh_from_db()
        self.assertIsNotNone(tenant.onboarding_completed_at)
        self.assertTrue(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)
        evt = AuditEvent.objects.get(tenant=tenant, action="ONBOARDING_COMPLETED")
        self.assertEqual(evt.details_json.get("triggered_by"), "kyc_submitted")


# ---------------------------------------------------------------------------
# Idempotency — repeated signals after completion do NOT re-emit / re-write.
# ---------------------------------------------------------------------------


class OnboardingSignalIdempotencyTests(TransactionTestCase):
    """The completion timestamp is a one-way ratchet."""

    def test_kyc_status_change_after_completion_does_not_reemit(self):
        tenant = _new_tenant()
        _grant_admin(tenant)
        _submit_kyc(tenant, status=KYCStatus.PENDING_REVIEW)
        _activate_subscription(tenant)

        tenant.refresh_from_db()
        first_timestamp = tenant.onboarding_completed_at
        self.assertIsNotNone(first_timestamp)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

        # KYC moves to VERIFIED — shouldn't re-emit (the post_save
        # handler skips because the kyc transition is no longer
        # FROM ``UNVERIFIED``).
        _submit_kyc(tenant, status=KYCStatus.VERIFIED)
        tenant.refresh_from_db()
        self.assertEqual(tenant.onboarding_completed_at, first_timestamp)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

    def test_second_admin_grant_after_completion_does_not_reemit(self):
        tenant = _new_tenant()
        _grant_admin(tenant)
        _submit_kyc(tenant)
        _activate_subscription(tenant)

        tenant.refresh_from_db()
        first_timestamp = tenant.onboarding_completed_at
        self.assertIsNotNone(first_timestamp)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

        # Adding a SECOND TENANT_ADMIN user shouldn't re-emit.
        uid = uuid.uuid4().hex[:8]
        user2 = User.objects.create_user(
            email=f"sig2-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        role = Role.objects.get(tenant=tenant, name="TENANT_ADMIN")
        UserRole.objects.create(user=user2, tenant=tenant, role=role)

        tenant.refresh_from_db()
        self.assertEqual(tenant.onboarding_completed_at, first_timestamp)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)


# ---------------------------------------------------------------------------
# Subscription-state edge cases — only ACTIVE/TRIAL/PAST_DUE trigger.
# ---------------------------------------------------------------------------


class OnboardingSignalSubscriptionGateTests(TransactionTestCase):
    def test_canceled_subscription_does_not_complete_onboarding(self):
        tenant = _new_tenant()
        _grant_admin(tenant)
        _submit_kyc(tenant)
        _activate_subscription(tenant, status=SubscriptionStatus.CANCELED)

        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertFalse(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 0)

    def test_incomplete_expired_subscription_does_not_complete_onboarding(self):
        tenant = _new_tenant()
        _grant_admin(tenant)
        _submit_kyc(tenant)
        _activate_subscription(tenant, status=SubscriptionStatus.INCOMPLETE_EXPIRED)

        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)

    def test_trial_subscription_completes_onboarding(self):
        tenant = _new_tenant()
        _grant_admin(tenant)
        _submit_kyc(tenant)
        _activate_subscription(tenant, status=SubscriptionStatus.TRIAL)

        tenant.refresh_from_db()
        self.assertIsNotNone(tenant.onboarding_completed_at)
        self.assertTrue(tenant.asset_creation_enabled)


# ---------------------------------------------------------------------------
# End-to-end: onboarding service starts gated; signal flow unlocks it.
# ---------------------------------------------------------------------------


class OnboardingKycHandlerOrderingRegressionTests(TransactionTestCase):
    """250.6.D audit-pass regression — pin the KYC-handler invariant.

    The original ``_onboarding_check_kyc_change`` implementation
    tried to gate on the kyc transition by reading
    ``_thread_local.kyc_before_save`` non-destructively. That broke
    silently because Django dispatches receivers in registration
    order and ``audit_kyc_status_change`` (registered earlier in
    ``tenants/signals.py``) ``pop``s the same key. By the time the
    onboarding handler ran, the entry was gone, ``old_kyc`` was
    ``None``, and the "subscription first, admin second, kyc third"
    ordering never reached the helper — onboarding stayed
    incomplete forever.

    This test pins the load-bearing scenario: when KYC is the
    LAST of the three signals to arrive, onboarding MUST complete
    (timestamp set, gate released, audit emitted with
    ``triggered_by=kyc_submitted``).
    """

    def test_kyc_as_last_signal_completes_onboarding(self):
        """KYC last → completion fires (regression for receiver-ordering bug)."""
        tenant = _new_tenant()
        # Subscription FIRST.
        _activate_subscription(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)

        # Admin SECOND.
        _grant_admin(tenant)
        tenant.refresh_from_db()
        self.assertIsNone(tenant.onboarding_completed_at)

        # KYC LAST — the bug-revealing transition. Must complete
        # onboarding even though ``audit_kyc_status_change`` has
        # already consumed the kyc-before-save thread-local.
        _submit_kyc(tenant, status=KYCStatus.PENDING_REVIEW)
        tenant.refresh_from_db()
        self.assertIsNotNone(
            tenant.onboarding_completed_at,
            "KYC as last signal MUST complete onboarding — receiver "
            "ordering must not silently swallow this case.",
        )
        self.assertTrue(tenant.asset_creation_enabled)
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

        evt = AuditEvent.objects.get(tenant=tenant, action="ONBOARDING_COMPLETED")
        self.assertEqual(evt.details_json.get("triggered_by"), "kyc_submitted")

    def test_redundant_kyc_save_after_completion_is_a_noop(self):
        """Redundant fires after completion don't double-emit.

        The audit-pass fix dropped the transition gate; the handler
        now fires on every non-create Tenant save where kyc is
        non-UNVERIFIED. The helper's idempotency must catch the
        redundant case so we don't flood the audit log with
        ``ONBOARDING_COMPLETED`` rows on every subsequent KYC update.
        """
        tenant = _new_tenant()
        _grant_admin(tenant)
        _activate_subscription(tenant)
        _submit_kyc(tenant, status=KYCStatus.PENDING_REVIEW)
        tenant.refresh_from_db()
        first_audit_count = _onboarding_completed_audit_count(tenant)
        self.assertEqual(first_audit_count, 1)

        # A non-kyc field changes (region) — handler fires (kyc is
        # non-UNVERIFIED), helper returns False (already complete),
        # no new audit.
        tenant.region = "us-east-1"
        tenant.save(update_fields=["region"])
        tenant.refresh_from_db()
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)

        # KYC moves to VERIFIED — same: handler fires, helper no-ops.
        _submit_kyc(tenant, status=KYCStatus.VERIFIED)
        tenant.refresh_from_db()
        self.assertEqual(_onboarding_completed_audit_count(tenant), 1)


class OnboardingServiceIntegrationTests(TransactionTestCase):
    """The 250.6.D.1 contract end-to-end: ``create_tenant_with_first_user``
    starts the gate CLOSED; downstream onboarding-flow steps release it."""

    def test_create_tenant_with_first_user_starts_gate_closed(self):
        from hub.apps.tenants.services import TenantOnboardingService

        # Need a plan to exist so the service can attach it.
        TenantPlan.objects.get_or_create(
            slug="free",
            defaults={
                "name": "Free",
                "tier": PlanTier.FREE,
                "is_active": True,
                "limits_json": {},
            },
        )

        uid = uuid.uuid4().hex[:8]
        result = TenantOnboardingService().create_tenant_with_first_user(
            name=f"Service {uid}",
            slug=f"service-{uid}",
            plan_slug="free",
            first_user_email=f"svc-{uid}@example.com",
            first_user_password="testpass123",
        )
        tenant = result["tenant"]
        # The gate STARTS closed.
        # Refresh because the service-internal handlers may have
        # already advanced state by the time we check.
        tenant.refresh_from_db()
        # NOTE: the service grants TENANT_ADMIN AND creates a FREE
        # subscription synchronously in the same transaction. KYC is
        # NOT submitted, so onboarding cannot complete yet. The
        # gate must therefore still be False AND the timestamp NULL.
        self.assertIsNone(tenant.onboarding_completed_at)
        self.assertFalse(tenant.asset_creation_enabled)
