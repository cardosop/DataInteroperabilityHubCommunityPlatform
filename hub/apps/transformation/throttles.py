"""
285.9.1.0.2 — DRF throttles for transformation ViewSets.

Tenant-aware rate limiting per Phase 273 convention.
"""
from __future__ import annotations
from typing import Optional

from rest_framework.throttling import SimpleRateThrottle

from hub.apps.tenants.request_tenant import get_request_tenant_id


class TransformationTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for transformation endpoints (30/min)."""

    scope = "transformation"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }

    def throttled(self, request, wait):
        """Emit TRANSFORMATION_RATE_LIMIT_EXCEEDED audit event on 429 per Phase 273."""
        try:
            from hub.apps.audit.utils import create_audit_event

            tenant_id = get_request_tenant_id(request)
            create_audit_event(
                resource_type="transformation",
                action="transformation.rate_limit_exceeded",
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=None,
                resource_id=None,
                details={
                    "path": request.path,
                    "method": request.method,
                    "wait_seconds": wait,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
                request=request,
            )
        except Exception:
            pass  # audit-DB outage must never block the 429 response
        super().throttled(request, wait)
