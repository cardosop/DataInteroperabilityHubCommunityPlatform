"""TENANT_ADMIN gate for processor agreement APIs (Phase 232.6.11)."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from hub.apps.auth.permissions import IsTenantAdmin


def _tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsTenantAdminProcessorAgreements(IsTenantAdmin):
    """Canonical tenant-admin gate (W12.5) + the processor-agreements
    feature flag — the flag check is the ONLY thing this class adds over
    ``hub.apps.auth.permissions.IsTenantAdmin``."""

    message = "Processor agreement management requires TENANT_ADMIN and tenant feature flag."

    def has_permission(self, request, view) -> bool:  # DRF permission contract
        if not super().has_permission(request, view):
            return False
        tenant = _tenant(request)
        return bool(
            tenant
            and getattr(tenant, "compliance_processor_agreements_enabled", False)
        )
