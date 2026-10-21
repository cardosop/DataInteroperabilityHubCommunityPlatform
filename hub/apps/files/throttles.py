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

from rest_framework.throttling import SimpleRateThrottle


class _FileInitAuditMixin:
    """W11.9 — file-init 429s emit FILE_UPLOAD_RATE_LIMIT_EXCEEDED
    (the Phase 273 per-surface contract; the pre-fix throttles emitted
    nothing).  The G10 pattern: the emission hooks the ALLOW_REQUEST
    failure branch (the DRF base never calls ``_on_throttled``)."""

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            self._on_throttled(request, int(self.wait()))
        return allowed

    def _on_throttled(self, request, wait):
        try:
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="FILE",
                action="FILE_UPLOAD_RATE_LIMIT_EXCEEDED",
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=getattr(request.user, "tenant", None)
                if request.user.is_authenticated
                else None,
                resource_id=None,
                result="THROTTLED",
                details={
                    "remote_addr": request.META.get("REMOTE_ADDR", ""),
                    "wait_seconds": int(wait),
                },
                infer_tenant_from_actor=True,
            )
        except Exception:  # noqa: BLE001 - the Phase 273 best-effort audit contract
            pass


class FileInitUserThrottle(_FileInitAuditMixin, SimpleRateThrottle):
    """Per-user throttle for ``POST /files/init/`` (60/min)."""

    scope = "file_init_user"

    def get_cache_key(self, request, view) -> str | None:  # DRF throttle contract
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class FileInitTenantThrottle(_FileInitAuditMixin, SimpleRateThrottle):
    """Per-tenant throttle for ``POST /files/init/`` (600/min)."""

    scope = "file_init_tenant"

    def get_cache_key(self, request, view) -> str | None:  # DRF throttle contract
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

    def get_cache_key(self, request, view) -> str | None:  # DRF throttle contract
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class FileScanStatusTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for ``GET …/scan-status/`` (300/min)."""

    scope = "file_scan_status_tenant"

    def get_cache_key(self, request, view) -> str | None:  # DRF throttle contract
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
