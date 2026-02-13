"""
Test support: ensure tenant has active subscription so billing middleware allows writes.

Jobs API tests use authenticated tenants; SubscriptionStatusMiddleware blocks
POST/PUT/PATCH/DELETE when the tenant has no active subscription. This helper
creates a plan and active subscription so tests (create job, cancel job) get
200/201 instead of 403. No mocks: real TenantPlan and Subscription records.
"""

from django.utils import timezone

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan


def ensure_tenant_has_active_subscription(tenant: Tenant) -> None:
    """
    Ensure tenant has an active subscription so billing middleware allows writes.

    Creates a FREE plan (get_or_create) and an ACTIVE subscription.
    Idempotent: if tenant already has an active subscription, does nothing.
    """
    # Avoid duplicate subscriptions: if tenant already has an active one, skip
    existing = (
        Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if existing:
        return

    plan, _ = TenantPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": "Free Plan",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 10},
            "is_active": True,
        },
    )

    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timezone.timedelta(days=365),
    )

    if not tenant.plan_id:
        tenant.plan = plan
        tenant.save(update_fields=["plan", "updated_at"])
