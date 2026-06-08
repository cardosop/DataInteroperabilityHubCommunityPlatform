"""283.3.5.4 — Tenant-scoped throttles for DPIA views."""
from rest_framework.throttling import SimpleRateThrottle


class DpiaTenantRateThrottle(SimpleRateThrottle):
    """Per-tenant rate limit for DPIA operations."""
    scope = "dpia_tenant"

    def get_cache_key(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            tenant = getattr(getattr(request, "user", None), "tenant", None)
        if tenant is None:
            return self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": str(tenant.id)}
