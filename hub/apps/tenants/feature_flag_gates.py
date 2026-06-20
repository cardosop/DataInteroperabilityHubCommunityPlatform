"""
285.5.2 — Feature-flag gate helpers for Phase 285.5.2 flags.

Each helper follows the DQFeatureFlagMixin pattern from
``hub/apps/dq/feature_flags.py``: returns the resolved Tenant on success
or a 403 Response on failure.

Usage in ViewSets:

    from hub.apps.tenants.feature_flag_gates import check_ml_enabled

    class MLModelViewSet(viewsets.ModelViewSet):
        def initial(self, request, *args, **kwargs):
            super().initial(request, *args, **kwargs)
            check_ml_enabled(request)  # raises/returns 403 if disabled
"""

from __future__ import annotations

from typing import Union

from django.http import HttpRequest
from rest_framework import status
from rest_framework.response import Response

from hub.apps.tenants.models import Tenant

# Each gate returns either the resolved Tenant (success) or a 403 Response (blocked).
GateResult = Union[Tenant, Response]


def _gate_disabled(flag_name: str, error_code: str) -> Response:
    """Return a canonical 403 gate-disabled response."""
    return Response(
        {"error_code": error_code, "detail": f"Feature '{flag_name}' is disabled for this tenant."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _get_tenant(request: HttpRequest) -> Tenant | None:
    """Resolve the request tenant. Returns None if unresolvable."""
    tenant = getattr(request, "tenant", None)
    if tenant is None and hasattr(request, "user") and request.user.is_authenticated:
        tenant = getattr(request.user, "tenant", None)
    return tenant


def check_marketplace_integrations_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.1 — Gate marketplace integrations (DRAFT).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "marketplace_integrations_enabled", False):
        return _gate_disabled(
            "marketplace_integrations_enabled", "MARKETPLACE_INTEGRATIONS_DISABLED"
        )
    return tenant


def check_data_mesh_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.2 — Gate Data Mesh domains (CANARY).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "data_mesh_enabled", False):
        return _gate_disabled("data_mesh_enabled", "DATA_MESH_DISABLED")
    return tenant


def check_virtualization_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.3 — Gate data virtualization (CANARY).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "virtualization_enabled", False):
        return _gate_disabled("virtualization_enabled", "VIRTUALIZATION_DISABLED")
    return tenant


def check_developer_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.4 — Gate developer portal + plugins (DRAFT).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "developer_enabled", False):
        return _gate_disabled("developer_enabled", "DEVELOPER_DISABLED")
    return tenant


def check_ml_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.5 — Gate ML Model Registry + Inference (CANARY).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "ml_enabled", False):
        return _gate_disabled("ml_enabled", "ML_DISABLED")
    return tenant


def check_transformation_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.6 — Gate ETL/ELT transformation pipelines (DRAFT).

    When the tenant cannot be resolved (platform admin or unauthenticated
    user), the gate passes — platform admins have cross-tenant access and
    unauthenticated users are caught by ``IsAuthenticated`` (which returns
    401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "transformation_enabled", False):
        return _gate_disabled("transformation_enabled", "TRANSFORMATION_DISABLED")
    return tenant


def check_baas_enabled(request: HttpRequest) -> GateResult:
    """285.5.2.7 — Gate Backend-as-a-Service (CANARY).

    When the tenant cannot be resolved (platform admin or
    unauthenticated user), the gate passes — platform admins have
    cross-tenant access and unauthenticated users are caught by
    ``IsAuthenticated`` (which returns 401, not 403).
    """
    tenant = _get_tenant(request)
    if tenant is None:
        return tenant
    if not getattr(tenant, "baas_enabled", False):
        return _gate_disabled("baas_enabled", "BAAS_DISABLED")
    return tenant
