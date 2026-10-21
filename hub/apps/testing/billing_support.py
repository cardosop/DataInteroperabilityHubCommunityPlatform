"""
Test support: ensure tenant has active subscription so billing middleware allows writes.

TenantSuspensionMiddleware blocks POST/PUT/PATCH/DELETE when the tenant has no
active subscription (returns 403). Tests that hit the full request stack must
create a real TenantPlan and Subscription so writes are allowed. No mocks:
real records only.

Phase 313.2 — this core facade delegates to the paid billing app through the
commercial hook (set_subscription_factory). In core-only mode no factory
exists and the helper returns None (no billing in core).
"""

from typing import TYPE_CHECKING, Any

from hub.apps.core.commercial_hooks import get_subscription_factory

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant


def ensure_tenant_has_active_subscription(tenant: "Tenant") -> Any:
    """
    Ensure tenant has an active subscription so TenantSuspensionMiddleware allows writes.

    Idempotent: if the tenant already has an active subscription, the factory
    is a no-op. Returns the factory result (None in core-only mode).
    """
    factory = get_subscription_factory()
    if factory is None:
        return None
    return factory(tenant)
