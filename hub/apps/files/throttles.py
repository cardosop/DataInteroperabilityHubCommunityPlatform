"""
Phase 260.2.E — DRF throttles for ``POST /files/init/``.

Per pass-2 S-9, multi-part upload init runs presign and metadata work per call.
Two-tier limits mirror asset-creation (S-8):

* :class:`FileInitUserThrottle` — per-user 60/min
  (``DEFAULT_THROTTLE_RATES["file_init_user"]``).
* :class:`FileInitTenantThrottle` — per-tenant 600/min
  (``DEFAULT_THROTTLE_RATES["file_init_tenant"]``).

Phase 260.3.D — DRF throttles for ``GET /files/{id}/scan-status/`` (pass-2
S2-3): polling abuse caps — :class:`FileScanStatusUserThrottle` (30/min per
user) and :class:`FileScanStatusTenantThrottle` (300/min per tenant).

DRF runs each throttle from ``FileViewSet.get_throttles()`` in order; if any
deny, ``rest_framework.exceptions.Throttled`` is raised using the maximum
``wait`` among denials (every ``allow_request`` runs). ``SimpleRateThrottle``
uses Django's default cache (Redis in staging/production).
"""
from __future__ import annotations
from typing import Optional

from rest_framework.throttling import SimpleRateThrottle


class FileInitUserThrottle(SimpleRateThrottle):
    """Per-user throttle for ``POST /files/init/`` (60/min)."""

    scope = "file_init_user"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class FileInitTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for ``POST /files/init/`` (600/min)."""

    scope = "file_init_tenant"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }


class FileScanStatusUserThrottle(SimpleRateThrottle):
    """Per-user throttle for ``GET …/scan-status/`` (30/min)."""

    scope = "file_scan_status_user"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class FileScanStatusTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for ``GET …/scan-status/`` (300/min)."""

    scope = "file_scan_status_tenant"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }
