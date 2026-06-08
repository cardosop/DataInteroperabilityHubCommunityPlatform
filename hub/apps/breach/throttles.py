"""283.3.4.4 — Tenant-scoped throttles for breach incident views."""
from rest_framework.throttling import SimpleRateThrottle


class BreachTenantRateThrottle(SimpleRateThrottle):
    """Per-tenant rate limit for breach incident operations."""
    scope = "breach_tenant"

    def get_cache_key(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            tenant = getattr(getattr(request, "user", None), "tenant", None)
        if tenant is None:
            return self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant.id),
        }
