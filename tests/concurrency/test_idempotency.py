"""
312.13.2 — Idempotency verification tests.

Verifies that repeatable operations remain idempotent: calling them
multiple times with the same inputs produces the same outcome without
side-effect duplication.  All tests use real functions — no mocks.
"""

import uuid

import pytest
from django.utils import timezone

from hub.apps.tenants.models import Tenant, TenantPlan, KYCStatus


@pytest.mark.integration
@pytest.mark.idempotency
class TestEnsureE2eTenantReadyIdempotent:
    """``ensure_e2e_tenant_ready()`` called twice → second call is a no-op."""

    @pytest.mark.django_db(transaction=True)
    def test_ensure_e2e_tenant_ready_twice_is_noop(self):
        from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

        plan = TenantPlan.objects.get(slug="enterprise")
        tenant = Tenant.objects.create(
            name=f"e2e-ready-{uuid.uuid4().hex[:8]}",
            slug=f"e2e-ready-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )

        # First call — provisions the tenant
        ensure_e2e_tenant_ready(tenant)
        tenant.refresh_from_db()
        assert tenant.onboarding_completed_at is not None, \
            "First call should set onboarding_completed_at"
        assert tenant.asset_creation_enabled is True, \
            "First call should enable asset creation"
        original_onboarding = tenant.onboarding_completed_at

        # Second call — must be a no-op (idempotent)
        ensure_e2e_tenant_ready(tenant)
        tenant.refresh_from_db()
        assert tenant.onboarding_completed_at == original_onboarding, \
            "Second call should not change onboarding_completed_at"
        assert tenant.asset_creation_enabled is True, \
            "Second call should not disable asset creation"

    @pytest.mark.django_db(transaction=True)
    def test_ensure_e2e_tenant_ready_repeatedly_no_duplicate_side_effects(self):
        """Repeated calls don't create duplicate subscriptions or KYC records."""
        from hub.apps.testing.billing_support import ensure_e2e_tenant_ready
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        plan = TenantPlan.objects.get(slug="enterprise")
        tenant = Tenant.objects.create(
            name=f"e2e-repeat-{uuid.uuid4().hex[:8]}",
            slug=f"e2e-repeat-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )

        # Call three times
        for _ in range(3):
            ensure_e2e_tenant_ready(tenant)
            tenant.refresh_from_db()

        # Should only have one active subscription
        active_subs = Subscription.objects.filter(
            tenant=tenant, status=SubscriptionStatus.ACTIVE,
        )
        assert active_subs.count() == 1, \
            f"Expected 1 active subscription, got {active_subs.count()}"
        # KYC should still be VERIFIED (not duplicated)
        tenant.refresh_from_db()
        assert tenant.kyc_status == KYCStatus.VERIFIED


@pytest.mark.integration
@pytest.mark.idempotency
class TestSeedDefaultPlansIdempotent:
    """``_seed_tenant_plans_if_missing()`` called twice → second call is a no-op."""

    @pytest.mark.django_db(transaction=True)
    def test_seed_default_plans_twice_is_noop(self):
        from hub.conftest import _seed_tenant_plans_if_missing

        # First call — seeds the plans
        _seed_tenant_plans_if_missing()
        original_counts = {
            slug: TenantPlan.objects.filter(slug=slug).count()
            for slug in ("free", "pro", "enterprise", "sandbox")
        }
        for slug, count in original_counts.items():
            assert count == 1, f"Expected 1 {slug} plan after seed, got {count}"

        # Second call — must be a no-op (idempotent via get_or_create)
        _seed_tenant_plans_if_missing()
        for slug in ("free", "pro", "enterprise", "sandbox"):
            count = TenantPlan.objects.filter(slug=slug).count()
            assert count == 1, \
                f"Second seed should not duplicate {slug} plan, got {count}"

    @pytest.mark.django_db(transaction=True)
    def test_seed_default_plans_does_not_modify_existing(self):
        """Seeding after modifying a plan's limits should not overwrite."""
        from hub.conftest import _seed_tenant_plans_if_missing

        _seed_tenant_plans_if_missing()
        free_plan = TenantPlan.objects.get(slug="free")
        original_limits = dict(free_plan.limits_json)
        free_plan.limits_json = {"max_assets": 999, "max_datasets": 999}
        free_plan.save(update_fields=["limits_json"])

        # Re-seed — should NOT overwrite custom limits (get_or_create skips)
        _seed_tenant_plans_if_missing()
        free_plan.refresh_from_db()
        assert free_plan.limits_json.get("max_assets") == 999, \
            "Existing plan limits should not be overwritten by re-seed"


@pytest.mark.integration
@pytest.mark.idempotency
class TestSubscriptionIdempotency:
    """Subscription operations respect idempotency keys."""

    @pytest.mark.django_db(transaction=True)
    def test_create_subscription_same_stripe_id_is_unique(self):
        """Two subscriptions with the same stripe_subscription_id hit unique constraint."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from django.db.utils import IntegrityError

        plan = TenantPlan.objects.get(slug="free")
        tenant = Tenant.objects.create(
            name=f"sub-idem-{uuid.uuid4().hex[:8]}",
            slug=f"sub-idem-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )
        stripe_id = f"sub_test_{uuid.uuid4().hex[:12]}"

        # First — succeeds
        Subscription.objects.create(
            tenant=tenant, plan=plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
            stripe_subscription_id=stripe_id,
        )

        # Second with same stripe_id — must fail
        with pytest.raises(IntegrityError):
            Subscription.objects.create(
                tenant=tenant, plan=plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=30),
                stripe_subscription_id=stripe_id,
            )

    @pytest.mark.django_db(transaction=True)
    def test_idempotent_get_or_create_subscription(self):
        """get_or_create with the same stripe_subscription_id returns the existing row."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        plan = TenantPlan.objects.get(slug="free")
        tenant = Tenant.objects.create(
            name=f"sub-goc-{uuid.uuid4().hex[:8]}",
            slug=f"sub-goc-{uuid.uuid4().hex[:8]}",
            plan=plan, kyc_status=KYCStatus.VERIFIED,
        )
        stripe_id = f"sub_test_{uuid.uuid4().hex[:12]}"

        sub1, created1 = Subscription.objects.get_or_create(
            tenant=tenant, stripe_subscription_id=stripe_id,
            defaults={
                "plan": plan, "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timezone.timedelta(days=30),
            },
        )
        assert created1 is True

        sub2, created2 = Subscription.objects.get_or_create(
            tenant=tenant, stripe_subscription_id=stripe_id,
            defaults={
                "plan": plan, "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timezone.timedelta(days=30),
            },
        )
        assert created2 is False
        assert sub1.id == sub2.id, \
            "Second get_or_create should return the same subscription"
