"""
285.14.3.6 — DRF throttles for scheduled_export ViewSets.

Tenant-aware rate limiting per Phase 273 convention.
"""
from __future__ import annotations
from typing import Optional

from rest_framework.throttling import SimpleRateThrottle

from hub.apps.tenants.request_tenant import get_request_tenant_id


class ScheduledExportTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for scheduled export endpoints (30/min)."""

    scope = "scheduled_export"

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
        try:
            from hub.apps.audit.utils import create_audit_event

            tenant_id = get_request_tenant_id(request)
            create_audit_event(
                resource_type="scheduled_export",
                action="scheduled_export.rate_limit_exceeded",
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
            pass
        super().throttled(request, wait)
