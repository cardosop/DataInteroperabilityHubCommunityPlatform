"""
Test support: ensure tenant has active subscription so billing middleware allows writes.

TenantSuspensionMiddleware blocks POST/PUT/PATCH/DELETE when the tenant has no
active subscription (returns 403). Tests that hit the full request stack (scheduled
export/ingestion views, jobs, etc.) must create a real TenantPlan and Subscription
so writes are allowed. No mocks: real records only.
"""

from datetime import timedelta

from django.utils import timezone

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan


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
        current_period_end=timezone.now() + timedelta(days=365),
    )

    if not getattr(tenant, "plan_id", None):
        tenant.plan = plan
        tenant.save(update_fields=["plan", "updated_at"])


# Plan with unlimited/generous limits for E2E (avoids plan_limit_exceeded after many runs)
E2E_PLAN_SLUG = "e2e-unlimited"


def ensure_e2e_tenant_ready(tenant: Tenant) -> None:
    """
    Ensure E2E test tenant has active subscription, VERIFIED KYC, and unlimited plan limits.

    Marketplace publish requires VERIFIED KYC. Asset creation and other E2E flows hit
    plan limits (max_assets) after many runs; this uses an e2e-unlimited plan so tests
    don't fail with plan_limit_exceeded. Idempotent: safe to call multiple times.
    """
    ensure_tenant_has_active_subscription(tenant)

    # Use E2E plan with unlimited/generous limits (avoids plan_limit_exceeded)
    e2e_plan, _ = TenantPlan.objects.get_or_create(
        slug=E2E_PLAN_SLUG,
        defaults={
            "name": "E2E Unlimited Plan",
            "tier": PlanTier.ENTERPRISE,
            "limits_json": {
                "max_assets": None,  # Unlimited
                "max_datasets": None,
                "max_api_calls_per_month": None,
                "max_scheduled_ingestions": None,
                "max_scheduled_runs_per_month": None,
                "max_scheduled_exports": None,
                "max_export_runs_per_month": None,
                "max_storage_gb": None,
            },
            "is_active": True,
        },
    )

    # Assign tenant to E2E plan (PlanLimitService uses tenant.plan)
    if getattr(tenant, "plan_id", None) != e2e_plan.id:
        tenant.plan = e2e_plan
        tenant.save(update_fields=["plan", "updated_at"])

    # Update active subscription to use E2E plan
    from hub.apps.billing.models import Subscription, SubscriptionStatus

    sub = (
        Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if sub and getattr(sub, "plan_id", None) != e2e_plan.id:
        sub.plan = e2e_plan
        sub.save(update_fields=["plan", "updated_at"])

    if tenant.kyc_status != KYCStatus.VERIFIED:
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status", "updated_at"])
