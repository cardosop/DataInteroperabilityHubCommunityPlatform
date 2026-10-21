"""Test factories for the tenants app.

Provides ``TenantFactory``, ``TenantConfigFactory``, and
``SubscriptionFactory`` with auto-generated unique identifiers
so that every call produces a collision-free row — no dependency
on the conftest idempotent-create monkey-patch.

Usage::

    from hub.apps.tenants.tests.factories import (
        TenantFactory,
        TenantConfigFactory,
        SubscriptionFactory,
    )

    tenant = TenantFactory.create_tenant()
    config = TenantConfigFactory.create_config(tenant=tenant)
    sub = SubscriptionFactory.create_subscription(tenant=tenant)
"""

import uuid

# Phase 313.H.3 — the subscription helpers are paid-layer (billing).
# Core-only test runs (pytest loads this module via conftest) have no
# billing app; both absence forms are caught so the factory degrades to
# "no subscription to create" instead of crashing collection.
try:
    from hub.apps.billing.models import Subscription, SubscriptionStatus
except (RuntimeError, ModuleNotFoundError):
    Subscription = SubscriptionStatus = None  # type: ignore[assignment]

from hub.apps.tenants.models import (
    KYCStatus,
    Tenant,
    TenantConfig,
    TenantPlan,
    TenantStatus,
)


class TenantFactory:
    """Create Tenant instances with auto-generated unique name/slug."""

    @staticmethod
    def create_tenant(
        *,
        name=None,
        slug=None,
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        plan=None,
        **overrides,
    ):
        uid = uuid.uuid4().hex[:8]
        return Tenant.objects.create(
            name=name or f"Test Tenant {uid}",
            slug=slug or f"test-tenant-{uid}",
            status=status,
            kyc_status=kyc_status,
            plan=plan,
            **overrides,
        )


class TenantConfigFactory:
    """Create TenantConfig with platform defaults."""

    @staticmethod
    def create_config(*, tenant):
        from hub.apps.tenants.validators import get_platform_defaults

        defaults = get_platform_defaults()
        return TenantConfig.objects.create(
            tenant=tenant,
            default_dq_profile=defaults["default_dq_profile"],
            allowed_compliance_regimes=defaults["allowed_compliance_regimes"],
            default_compliance_regimes=defaults["default_compliance_regimes"],
            data_retention_days=defaults["data_retention_days"],
            max_file_size_bytes=defaults["max_file_size_bytes"],
            max_job_concurrency=defaults["max_job_concurrency"],
            max_queued_jobs=defaults["max_queued_jobs"],
            rate_limits=defaults["rate_limits"],
        )


class SubscriptionFactory:
    """Create an active Subscription for a tenant.

    If no plan is provided, defaults to the 'free' plan (creating one
    if it doesn't exist).
    """

    @staticmethod
    def create_subscription(*, tenant, plan=None, status=None):
        if Subscription is None:
            # Core-only test run: no billing app — no subscription to create.
            return None
        if status is None:
            status = SubscriptionStatus.ACTIVE
        if plan is None:
            plan = TenantPlan.objects.filter(
                slug="free",
                is_active=True,
            ).first()
            if plan is None:
                plan = TenantPlan.objects.create(
                    slug=f"free-{uuid.uuid4().hex[:8]}",
                    name="Free Plan",
                    tier="FREE",
                    order=0,
                    is_active=True,
                )
        return Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            status=status,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:16]}",
        )


def activate_billing(tenant) -> None:
    """Ensure an active BASE subscription + TenantConfig for the billing
    middleware (test helper).

    The billing import lives HERE — the one allowlisted + guarded site
    (313.H.3) — so core-side suites (databricks_admin, warehouses)
    delegate to this helper instead of importing billing themselves:
    their duplicated ``_activate_billing`` shims were each a GATE-29
    boundary violation (1.3 review fix). Idempotent; degrades to a no-op
    in core-only runs (no billing app → no middleware → nothing to
    activate)."""
    if Subscription is None:
        # Core-only test run: no billing app → no middleware to satisfy.
        return
    TenantConfig.objects.get_or_create(tenant=tenant)
    plan = TenantPlan.objects.filter(slug="free", is_active=True).first()
    if plan and not Subscription.objects.filter(tenant=tenant, category="BASE").exists():
        Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            category="BASE",
            status=SubscriptionStatus.ACTIVE,
        )
