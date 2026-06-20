from __future__ import annotations

from rest_framework.permissions import BasePermission

from hub.apps.users.models import UserRole


def _tenant_for_request(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsBreachResponder(BasePermission):
    """TENANT_ADMIN, DPO, or SECURITY_ADMIN (Phase 232.3.13 baseline)."""

    message = "Breach response requires TENANT_ADMIN, DPO, or SECURITY_ADMIN."

    def has_permission(self, request, view) -> bool:
        tenant = _tenant_for_request(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        return UserRole.objects.filter(
            user=request.user,
            tenant=tenant,
            role__name__in=["TENANT_ADMIN", "DPO", "SECURITY_ADMIN"],
        ).exists()
