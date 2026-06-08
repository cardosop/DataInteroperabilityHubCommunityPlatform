from __future__ import annotations
from rest_framework.permissions import BasePermission

from hub.apps.users.models import UserRole


def _tenant_for_request(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsDsarHandler(BasePermission):
    """Handlers: TENANT_ADMIN, DPO, LEGAL_ADMIN (Phase 232.2.15 baseline)."""

    message = "DSAR handling requires TENANT_ADMIN, DPO, or LEGAL_ADMIN."

    def has_permission(self, request, view) -> bool:
        tenant = _tenant_for_request(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        return UserRole.objects.filter(
            user=request.user,
            tenant=tenant,
            role__name__in=["TENANT_ADMIN", "DPO", "LEGAL_ADMIN"],
        ).exists()

