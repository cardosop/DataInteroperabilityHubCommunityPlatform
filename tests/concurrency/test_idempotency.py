"""
312.13.2 — Idempotency verification tests.

Verifies that repeatable operations remain idempotent: calling them
multiple times with the same inputs produces the same outcome without
side-effect duplication.  All tests use real functions — no mocks.
"""

import uuid

import pytest
from django.utils import timezone

from hub.apps.tenants.models import KYCStatus, Tenant, TenantPlan


def _seed_plans():
    """Seed the default TenantPlans.

    TransactionTestCase truncation wipes the migrate-seeded plan rows, and
    these tests query TenantPlan directly — seed first so the lookups below
    (e.g. ``slug="enterprise"``) resolve.
    """
    from hub.conftest import _seed_tenant_plans_if_missing

    _seed_tenant_plans_if_missing()


@pytest.mark.integration
@pytest.mark.idempotency
class TestEnsureE2eTenantReadyIdempotent:
    """``ensure_e2e_tenant_ready()`` called twice → second call is a no-op."""

    @pytest.mark.django_db(transaction=True)
    def test_ensure_e2e_tenant_ready_twice_is_noop(self):
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.billing.test_support import E2E_PLAN_SLUG, ensure_e2e_tenant_ready

        _seed_plans()
        plan = TenantPlan.objects.get(slug="enterprise")
        tenant = Tenant.objects.create(
            name=f"e2e-ready-{uuid.uuid4().hex[:8]}",
            slug=f"e2e-ready-{uuid.uuid4().hex[:8]}",
            plan=plan,
            kyc_status=KYCStatus.VERIFIED,
        )

        # First call — provisions the tenant (active subscription +
        # e2e-unlimited plan; the helper does not set onboarding fields).
        ensure_e2e_tenant_ready(tenant)
        tenant.refresh_from_db()
        first_ids = set(
            Subscription.objects.filter(
                tenant=tenant, status=SubscriptionStatus.ACTIVE
            ).values_list("id", flat=True)
        )
        assert first_ids, "First call should create an active subscription"
        assert tenant.plan.slug == E2E_PLAN_SLUG, (
            "First call should switch the tenant to the e2e-unlimited plan"
        )

        # Second call — must be a no-op (idempotent)
        ensure_e2e_tenant_ready(tenant)
        tenant.refresh_from_db()
        second_ids = set(
            Subscription.objects.filter(
                tenant=tenant, status=SubscriptionStatus.ACTIVE
            ).values_list("id", flat=True)
        )
        assert second_ids == first_ids, "Second call should not create or remove subscriptions"
        assert tenant.plan.slug == E2E_PLAN_SLUG, "Second call should not change the plan"
        assert tenant.kyc_status == KYCStatus.VERIFIED

    @pytest.mark.django_db(transaction=True)
    def test_ensure_e2e_tenant_ready_repeatedly_no_duplicate_side_effects(self):
        """Repeated calls don't create duplicate subscriptions or KYC records."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.billing.test_support import ensure_e2e_tenant_ready

        _seed_plans()
        plan = TenantPlan.objects.get(slug="enterprise")
        tenant = Tenant.objects.create(
            name=f"e2e-repeat-{uuid.uuid4().hex[:8]}",
            slug=f"e2e-repeat-{uuid.uuid4().hex[:8]}",
            plan=plan,
            kyc_status=KYCStatus.VERIFIED,
        )

        # First call, then two more — the steady state is one BASE
        # subscription + one ML_AI subscription; repeated calls must
        # not create duplicates of either.
        ensure_e2e_tenant_ready(tenant)
        tenant.refresh_from_db()
        first_ids = set(
            Subscription.objects.filter(
                tenant=tenant, status=SubscriptionStatus.ACTIVE
            ).values_list("id", flat=True)
        )
        for _ in range(2):
            ensure_e2e_tenant_ready(tenant)
            tenant.refresh_from_db()

        active_subs = Subscription.objects.filter(
            tenant=tenant,
            status=SubscriptionStatus.ACTIVE,
        )
        assert active_subs.count() == 2, (
            f"Expected 2 active subscriptions (BASE + ML_AI), got {active_subs.count()}"
        )
        assert set(active_subs.values_list("id", flat=True)) == first_ids, (
            "Repeated calls must not create duplicate subscriptions"
        )
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
            for slug in ("free", "pro", "enterprise")
        }
        for slug, count in original_counts.items():
            assert count == 1, f"Expected 1 {slug} plan after seed, got {count}"

        # Second call — must be a no-op (idempotent via get_or_create)
        _seed_tenant_plans_if_missing()
        for slug in ("free", "pro", "enterprise"):
            count = TenantPlan.objects.filter(slug=slug).count()
            assert count == 1, f"Second seed should not duplicate {slug} plan, got {count}"

    @pytest.mark.django_db(transaction=True)
    def test_seed_default_plans_does_not_modify_existing(self):
        """Seeding after modifying a plan's limits should not overwrite."""
        from hub.conftest import _seed_tenant_plans_if_missing

        _seed_tenant_plans_if_missing()
        free_plan = TenantPlan.objects.get(slug="free")
        dict(free_plan.limits_json)
        free_plan.limits_json = {"max_assets": 999, "max_datasets": 999}
        free_plan.save(update_fields=["limits_json"])

        # Re-seed — should NOT overwrite custom limits (get_or_create skips)
        _seed_tenant_plans_if_missing()
        free_plan.refresh_from_db()
        assert free_plan.limits_json.get("max_assets") == 999, (
            "Existing plan limits should not be overwritten by re-seed"
        )


@pytest.mark.integration
@pytest.mark.idempotency
class TestSubscriptionIdempotency:
    """Subscription operations respect idempotency keys."""

    @pytest.mark.django_db(transaction=True)
    def test_create_subscription_same_stripe_id_is_unique(self):
        """Two subscriptions with the same stripe_subscription_id hit unique constraint."""
        from django.db.utils import IntegrityError

        from hub.apps.billing.models import Subscription, SubscriptionStatus

        _seed_plans()
        plan = TenantPlan.objects.get(slug="free")
        tenant = Tenant.objects.create(
            name=f"sub-idem-{uuid.uuid4().hex[:8]}",
            slug=f"sub-idem-{uuid.uuid4().hex[:8]}",
            plan=plan,
            kyc_status=KYCStatus.VERIFIED,
        )
        stripe_id = f"sub_test_{uuid.uuid4().hex[:12]}"

        # First — succeeds
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
            stripe_subscription_id=stripe_id,
        )

        # Second with same stripe_id — must fail
        with pytest.raises(IntegrityError):
            Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=30),
                stripe_subscription_id=stripe_id,
            )

    @pytest.mark.django_db(transaction=True)
    def test_idempotent_get_or_create_subscription(self):
        """get_or_create with the same stripe_subscription_id returns the existing row."""
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        _seed_plans()
        plan = TenantPlan.objects.get(slug="free")
        tenant = Tenant.objects.create(
            name=f"sub-goc-{uuid.uuid4().hex[:8]}",
            slug=f"sub-goc-{uuid.uuid4().hex[:8]}",
            plan=plan,
            kyc_status=KYCStatus.VERIFIED,
        )
        stripe_id = f"sub_test_{uuid.uuid4().hex[:12]}"

        sub1, created1 = Subscription.objects.get_or_create(
            tenant=tenant,
            stripe_subscription_id=stripe_id,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timezone.timedelta(days=30),
            },
        )
        assert created1 is True

        sub2, created2 = Subscription.objects.get_or_create(
            tenant=tenant,
            stripe_subscription_id=stripe_id,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now() + timezone.timedelta(days=30),
            },
        )
        assert created2 is False
        assert sub1.id == sub2.id, "Second get_or_create should return the same subscription"
