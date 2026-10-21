"""
284.A.1 — DRF throttles for FederatedImportViewSet.

Tenant-aware rate limiting: 30/min per tenant for provider discovery,
60/min per tenant for import job submission.
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class FederatedImportThrottle(SimpleRateThrottle):
    """Per-tenant throttle for FederatedImportViewSet (30/min)."""

    scope = "federated_import"

    def get_cache_key(self, request, view) -> str | None:
        if not request.user or not request.user.is_authenticated:
            return None
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }
