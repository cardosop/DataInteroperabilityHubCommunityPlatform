"""DPIA RBAC — TENANT_ADMIN authors; DPO / LEGAL_ADMIN review."""

from __future__ import annotations
from rest_framework.permissions import BasePermission

from hub.apps.users.models import UserRole


def _tenant_for_request(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class IsDpiaParticipant(BasePermission):
    """Create/update draft: TENANT_ADMIN. Read/list: handlers. Review actions: DPO path."""

    message = "DPIA requires TENANT_ADMIN, DPO, or LEGAL_ADMIN (context-dependent)."

    def has_permission(self, request, view) -> bool:
        tenant = _tenant_for_request(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        roles = UserRole.objects.filter(user=request.user, tenant=tenant).values_list(
            "role__name", flat=True
        )
        role_set = set(roles)
        if view.action in ("create", "update", "partial_update", "destroy"):
            return bool(role_set & {"TENANT_ADMIN", "DPO", "LEGAL_ADMIN"})
        return bool(role_set & {"TENANT_ADMIN", "DPO", "LEGAL_ADMIN"})


class IsDpiaReviewer(BasePermission):
    """Submit review / consultation resolution — DPO or LEGAL_ADMIN (+ PLATFORM_ADMIN)."""

    message = "DPIA review requires DPO or LEGAL_ADMIN."

    def has_permission(self, request, view) -> bool:
        tenant = _tenant_for_request(request)
        if not tenant or not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_platform_admin", False):
            return True
        roles = UserRole.objects.filter(user=request.user, tenant=tenant).values_list(
            "role__name", flat=True
        )
        return bool(set(roles) & {"DPO", "LEGAL_ADMIN"})
