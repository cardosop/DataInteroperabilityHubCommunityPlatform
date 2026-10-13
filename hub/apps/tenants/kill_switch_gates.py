"""
Phase 260.3.B — per-tenant Dataset and File REST kill switches.

Raises DRF :class:`APIException` subclasses so ViewSets can gate in
``initial()`` (after ``initialize_request``) without breaking renderer
negotiation.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from rest_framework import status
from rest_framework.exceptions import APIException


class FilesDisabledAPIException(APIException):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, tenant_id):
        super().__init__(
            detail={
                "error": (
                    "File management is disabled for this tenant. "
                    "Contact your administrator to re-enable files."
                ),
                "code": "FILES_DISABLED",
                "details": {
                    "tenant_id": str(tenant_id),
                    "capability": "files",
                },
            }
        )


class DatasetsDisabledAPIException(APIException):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, tenant_id):
        super().__init__(
            detail={
                "error": (
                    "Datasets are disabled for this tenant. "
                    "Contact your administrator to re-enable datasets."
                ),
                "code": "DATASETS_DISABLED",
                "details": {
                    "tenant_id": str(tenant_id),
                    "capability": "datasets",
                },
            }
        )


def ensure_tenant_files_api_allowed(request) -> None:
    """Raise :class:`FilesDisabledAPIException` when ``files_enabled`` is False."""
    from hub.apps.tenants.request_tenant import get_request_tenant

    try:
        _tid, tenant = get_request_tenant(request)
    except (ImportError, AttributeError, ValidationError, DatabaseError):
        tenant = None
    if tenant is None:
        return
    if getattr(tenant, "files_enabled", True):
        return
    raise FilesDisabledAPIException(tenant.id)


def ensure_tenant_datasets_api_allowed(request) -> None:
    """Raise :class:`DatasetsDisabledAPIException` when ``datasets_enabled`` is False."""
    from hub.apps.tenants.request_tenant import get_request_tenant

    try:
        _tid, tenant = get_request_tenant(request)
    except (ImportError, AttributeError, ValidationError, DatabaseError):
        tenant = None
    if tenant is None:
        return
    if getattr(tenant, "datasets_enabled", True):
        return
    raise DatasetsDisabledAPIException(tenant.id)


__all__ = [
    "DatabricksWorkspacesDisabledAPIException",
    "DatasetsDisabledAPIException",
    "FilesDisabledAPIException",
    "ensure_tenant_databricks_workspaces_allowed",
    "ensure_tenant_datasets_api_allowed",
    "ensure_tenant_files_api_allowed",
]


class DatabricksWorkspacesDisabledAPIException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "DATABRICKS_WORKSPACES_DISABLED"

    def __init__(self, tenant_id):
        super().__init__(
            detail={
                "error": (
                    "The Databricks control plane is temporarily disabled for this tenant. "
                    "Contact your administrator."
                ),
                "code": "DATABRICKS_WORKSPACES_DISABLED",
                "details": {
                    "tenant_id": str(tenant_id),
                    "capability": "databricks_workspaces",
                },
            }
        )


def ensure_tenant_databricks_workspaces_allowed(request) -> None:
    """Raise :class:`DatabricksWorkspacesDisabledAPIException` when the
    emergency kill switch is flipped for the tenant.

    Defensive getattr chain (no broad except) — the request may carry no
    tenant context at all, which simply means nothing to gate.
    """
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant", None)
    if tenant is None:
        return
    if not getattr(tenant, "databricks_workspaces_kill_switch", False):
        return
    raise DatabricksWorkspacesDisabledAPIException(tenant.id)


class DatabricksSSODisabledAPIException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "DATABRICKS_SSO_DISABLED"

    def __init__(self, tenant_id):
        super().__init__(
            detail={
                "error": (
                    "Sign-in with Databricks is disabled for this tenant. "
                    "Contact your administrator."
                ),
                "code": "DATABRICKS_SSO_DISABLED",
                "details": {"tenant_id": str(tenant_id)},
            }
        )


class DatabricksOBODisabledAPIException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "DATABRICKS_OBO_DISABLED"

    def __init__(self, tenant_id):
        super().__init__(
            detail={
                "error": (
                    "On-Behalf-Of Databricks execution is disabled for this tenant. "
                    "Contact your administrator."
                ),
                "code": "DATABRICKS_OBO_DISABLED",
                "details": {"tenant_id": str(tenant_id)},
            }
        )


def _request_tenant(request):
    """Defensive tenant resolution (no broad except) — same shape as the
    workspaces helper."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant", None)
    return tenant


def ensure_databricks_sso_allowed(request) -> None:
    """Kill switch FIRST (an emergency kill wins even when the flag is on),
    then the feature flag."""
    tenant = _request_tenant(request)
    if tenant is None:
        return
    if getattr(tenant, "databricks_sso_kill_switch", False):
        raise DatabricksSSODisabledAPIException(tenant.id)
    if not getattr(tenant, "databricks_sso_enabled", False):
        raise DatabricksSSODisabledAPIException(tenant.id)


def ensure_databricks_obo_allowed(request) -> None:
    """Kill switch FIRST, then the feature flag."""
    tenant = _request_tenant(request)
    if tenant is None:
        return
    if getattr(tenant, "databricks_obo_kill_switch", False):
        raise DatabricksOBODisabledAPIException(tenant.id)
    if not getattr(tenant, "databricks_obo_enabled", False):
        raise DatabricksOBODisabledAPIException(tenant.id)
