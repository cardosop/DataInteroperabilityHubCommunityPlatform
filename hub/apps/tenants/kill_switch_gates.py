"""
Phase 260.3.B — per-tenant Dataset and File REST kill switches.

Raises DRF :class:`APIException` subclasses so ViewSets can gate in
``initial()`` (after ``initialize_request``) without breaking renderer
negotiation.
"""
from __future__ import annotations
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
    except Exception:  # noqa: BLE001
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
    except Exception:  # noqa: BLE001
        tenant = None
    if tenant is None:
        return
    if getattr(tenant, "datasets_enabled", True):
        return
    raise DatasetsDisabledAPIException(tenant.id)


__all__ = [
    "DatasetsDisabledAPIException",
    "FilesDisabledAPIException",
    "ensure_tenant_datasets_api_allowed",
    "ensure_tenant_files_api_allowed",
]
