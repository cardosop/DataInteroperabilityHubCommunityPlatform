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
from hub.apps.tenants.models import KYCStatus, PlanCategory, PlanTier, Tenant, TenantPlan


def ensure_tenant_has_active_subscription(tenant: Tenant) -> None:
    """
    Ensure tenant has an active subscription so TenantSuspensionMiddleware allows writes.

    Creates a plan (get_or_create) and an ACTIVE subscription. Idempotent: if tenant
    already has an active subscription, does nothing.
    """
    _ensure_subscription_inner(tenant)


def _ensure_subscription_inner(tenant: Tenant) -> None:
    """Core logic for ensure_tenant_has_active_subscription.

    Retries once on transient ``OperationalError`` (e.g.
    ``statement_timeout`` from lock contention in the shared e2e
    database). The retry uses ``transaction.atomic()`` which creates
    a savepoint inside the outer test transaction, so a failed
    attempt does not poison the connection.
    """
    import time

    from django.db import OperationalError, transaction

    existing = (
        Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if existing:
        return

    required_limits = {
        "max_assets": 100,
        "max_contracts": 100,
        "max_datasets": 100,
        "max_ml_models": 100,
        "max_ml_training_jobs": 100,
        "max_ml_deployments": 100,
    }

    # Also ensure the canonical free plan exists (some tests reach
    # PlanLimitService.check_limit() before tenant.plan is assigned,
    # and plan resolution falls back to slug="free").
    TenantPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": "Free",
            "tier": PlanTier.FREE,
            "limits_json": required_limits,
            "is_active": True,
        },
    )

    plan, created = TenantPlan.objects.get_or_create(
        slug="scheduled-ops-test-plan",
        defaults={
            "name": "Scheduled Ops Test Plan",
            "tier": PlanTier.FREE,
            "limits_json": required_limits,
            "is_active": True,
        },
    )

    # Ensure existing plan has all required limits (get_or_create only sets defaults on create)
    if not created:
        current_limits = plan.limits_json or {}
        missing = {k: v for k, v in required_limits.items() if k not in current_limits}
        if missing:
            current_limits.update(missing)
            plan.limits_json = current_limits
            plan.save(update_fields=["limits_json"])

    for attempt in range(2):
        try:
            with transaction.atomic():
                Subscription.objects.create(
                    tenant=tenant,
                    plan=plan,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now() + timedelta(days=365),
                )
            break
        except OperationalError:
            if attempt == 0:
                time.sleep(2)  # Let the blocker commit/rollback
            else:
                raise

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

    # Use E2E plan with unlimited/generous limits (avoids plan_limit_exceeded).
    # Key names MUST match TenantPlan.ML_LIMIT_KEYS for ML limits and the
    # billing limit_registry for non-ML limits.
    unlimited_limits = {
        "max_assets": None,  # Unlimited
        "max_datasets": None,
        "max_api_calls_per_month": None,
        "max_scheduled_ingestions": None,
        "max_scheduled_runs_per_month": None,
        "max_scheduled_exports": None,
        "max_export_runs_per_month": None,
        "max_storage_gb": None,
        # ML limits (must match TenantPlan.ML_LIMIT_KEYS exactly)
        "max_ml_models": None,
        "max_ml_training_jobs_per_month": None,
        "max_ml_inference_requests_per_month": None,
        "max_ml_deployed_models": None,
        "max_ml_storage_gb": None,
    }
    e2e_plan, created = TenantPlan.objects.get_or_create(
        slug=E2E_PLAN_SLUG,
        defaults={
            "name": "E2E Unlimited Plan",
            "tier": PlanTier.ENTERPRISE,
            "limits_json": unlimited_limits,
            "is_active": True,
        },
    )

    # Ensure existing plan has all required unlimited limits (get_or_create only sets defaults on create)
    if not created:
        current_limits = e2e_plan.limits_json or {}
        missing = {k: v for k, v in unlimited_limits.items() if k not in current_limits}
        if missing:
            current_limits.update(missing)
            e2e_plan.limits_json = current_limits
            e2e_plan.save(update_fields=["limits_json"])

    # Assign tenant to E2E plan.
    # PlanLimitService routes ML limit keys to tenant.ml_plan and
    # everything else to tenant.plan — both must be set.
    update_fields = ["updated_at"]
    if getattr(tenant, "plan_id", None) != e2e_plan.id:
        tenant.plan = e2e_plan
        update_fields.append("plan")
    if getattr(tenant, "ml_plan_id", None) != e2e_plan.id:
        tenant.ml_plan = e2e_plan
        update_fields.append("ml_plan")
    if len(update_fields) > 1:
        tenant.save(update_fields=update_fields)

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

    # Ensure an ML_AI subscription record exists so GET
    # billing/subscription/ml/current/ returns data (not 404).
    # Setting tenant.ml_plan above enables ML limits but the ML
    # subscription viewset queries Subscription by category=ML_AI.
    #
    # NOTE: Subscription.save() auto-sets category from plan.category,
    # so we must use .update() after creation to force ML_AI.
    ml_sub = (
        Subscription.objects.filter(
            tenant=tenant,
            category=PlanCategory.ML_AI,
        )
        .order_by("-created_at")
        .first()
    )
    if not ml_sub:
        ml_sub = Subscription.objects.create(
            tenant=tenant,
            plan=e2e_plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=365 * 100),
        )
        # Force category to ML_AI — .save() would reset it to plan.category (BASE)
        Subscription.objects.filter(pk=ml_sub.pk).update(
            category=PlanCategory.ML_AI,
        )

    if tenant.kyc_status != KYCStatus.VERIFIED:
        tenant.kyc_status = KYCStatus.VERIFIED
        tenant.save(update_fields=["kyc_status", "updated_at"])
