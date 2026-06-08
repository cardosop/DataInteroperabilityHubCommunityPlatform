from __future__ import annotations

from rest_framework.permissions import BasePermission

from hub.apps.users.models import UserRole


def _request_tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsTenantScoped(BasePermission):
    """Reject when request.tenant or user.tenant is missing."""

    message = "Tenant context required."

    def has_permission(self, request, view) -> bool:
        return bool(_request_tenant(request))


class IsTenantAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        tenant = _request_tenant(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        return UserRole.objects.filter(
            user=request.user, tenant=tenant, role__name="TENANT_ADMIN"
        ).exists()


class IsDPO(BasePermission):
    def has_permission(self, request, view) -> bool:
        tenant = _request_tenant(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        return UserRole.objects.filter(
            user=request.user, tenant=tenant, role__name="DPO"
        ).exists()


class IsTenantAdminOrDPO(BasePermission):
    def has_permission(self, request, view) -> bool:
        tenant = _request_tenant(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        return UserRole.objects.filter(
            user=request.user, tenant=tenant, role__name__in=["TENANT_ADMIN", "DPO"]
        ).exists()
