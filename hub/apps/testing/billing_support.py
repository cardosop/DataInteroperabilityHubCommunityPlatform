"""
Test support: ensure tenant has active subscription so billing middleware allows writes.

TenantSuspensionMiddleware blocks POST/PUT/PATCH/DELETE when the tenant has no
active subscription (returns 403). Tests that hit the full request stack (scheduled
export/ingestion views, jobs, etc.) must create a real TenantPlan and Subscription
so writes are allowed. No mocks: real records only.
"""

from django.utils import timezone

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan


def ensure_tenant_has_active_subscription(tenant: Tenant) -> None:
    """
    Ensure tenant has an active subscription so TenantSuspensionMiddleware allows writes.

    Creates a plan (get_or_create) and an ACTIVE subscription. Idempotent: if tenant
    already has an active subscription, does nothing.
    """
    existing = (
        Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if existing:
        return

    plan, _ = TenantPlan.objects.get_or_create(
        slug="scheduled-ops-test-plan",
        defaults={
            "name": "Scheduled Ops Test Plan",
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
        current_period_end=timezone.now() + timezone.timedelta(days=365),
    )

    if not tenant.plan_id:
        tenant.plan = plan
        tenant.save(update_fields=["plan", "updated_at"])
