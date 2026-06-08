"""TENANT_ADMIN gate for processor agreement APIs (Phase 232.6.11)."""

from __future__ import annotations
from rest_framework.permissions import BasePermission

from hub.apps.users.models import UserRole


def _tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsTenantAdminProcessorAgreements(BasePermission):
    message = "Processor agreement management requires TENANT_ADMIN and tenant feature flag."

    def has_permission(self, request, view) -> bool:
        tenant = _tenant(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        if not getattr(tenant, "compliance_processor_agreements_enabled", False):
            return False
        return UserRole.objects.filter(
            user=request.user,
            tenant=tenant,
            role__name="TENANT_ADMIN",
        ).exists()
