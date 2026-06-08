"""
285.12.1.16 — Shared per-tenant throttles for Quick Win coverage.

Provides light-weight tenant-scoped throttles that satisfy the
``check_throttle_coverage`` CI gate.  Apps can import and assign
to their ViewSets' ``throttle_classes``.

285.14.11.V.7 — ``throttle_hit_total`` counter emitted on 429 responses.

Cache resilience
----------------
All throttle classes in this module are cache-resilient: when the
cache backend is unavailable (Redis down, connection refused, etc.),
``allow_request`` degrades gracefully by returning ``True`` (allow the
request).  This is intentional "fail-open" behaviour for rate
limiting — a cache outage must never block legitimate traffic.
"""
import logging
from rest_framework.throttling import SimpleRateThrottle

logger = logging.getLogger(__name__)


def _emit_throttle_hit_metric(app: str, view: str, scope: str, tenant_id: str) -> None:
    """Best-effort emission of throttle_hit_total on 429 responses."""
    try:
        from hub.apps.core.metrics import throttle_hit_total
        throttle_hit_total.labels(
            app=app, view=view, scope=scope, tenant_id=tenant_id,
        ).inc()
    except Exception:
        pass


def _resolve_app_and_view(view) -> tuple:
    """Resolve the app label and view class name from a DRF view instance."""
    try:
        app = view.__module__.split(".")[2]  # hub.apps.<app>...
    except (IndexError, AttributeError):
        app = "unknown"
    view_name = view.__class__.__name__ if view else "unknown"
    return app, view_name


class TenantScopedThrottle(SimpleRateThrottle):
    """30/min per tenant in production; relaxed to 5000/min in E2E/test envs."""
    scope = "tenant_scoped"

    def get_rate(self):
        """Return a relaxed rate when RATE_LIMIT_E2E_RELAX is True.

        Default ``tenant_scoped=30/minute`` is tuned for production
        multi-tenant safety.  E2E suites share a single tenant across
        2–4 parallel Playwright workers and routinely issue >30 asset/
        contract/dataset reads per minute — the production limit
        produces a cascade of HTTP 429 (RATE_LIMIT_EXCEEDED) that
        breaks the page render and skips/silent-fails tests.

        The production path is unchanged: ``get_rate()`` delegates to
        the parent (which reads ``DEFAULT_THROTTLE_RATES[scope]`` from
        settings).  The override only fires when the operator has
        explicitly set ``RATE_LIMIT_E2E_RELAX=True``, which is the
        documented contract for the E2E harness (see
        ``frontend/e2e/E2E_PIPELINE_DOCUMENTATION.md:49``).
        """
        from django.conf import settings

        if getattr(settings, "RATE_LIMIT_E2E_RELAX", False):
            return "5000/minute"
        return super().get_rate()

    def allow_request(self, request, view):
        # Store view reference for throttled() metric emission.
        # DRF's SimpleRateThrottle does not expose the view in
        # throttled(), so we capture it here.
        self._view = view
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning(
                "throttle_cache_unavailable",
                extra={
                    "scope": self.scope,
                    "key": self.get_cache_key(request, view),
                },
                exc_info=True,
            )
            return True

    def get_cache_key(self, request, view):
        try:
            from hub.apps.tenants.request_tenant import get_request_tenant
            _tid, _ = get_request_tenant(request)
            return f"throttle_{self.scope}_{_tid}" if _tid else None
        except Exception:
            return None  # pass-through on resolution failure

    def throttled(self, request, wait):
        """285.14.11.V.7 — emit throttle_hit_total on 429."""
        try:
            from hub.apps.tenants.request_tenant import get_request_tenant_id
            tenant_id = get_request_tenant_id(request) or "unknown"
        except Exception:
            tenant_id = "unknown"
        app, view_name = _resolve_app_and_view(getattr(self, "_view", None))
        _emit_throttle_hit_metric(app, view_name, self.scope, str(tenant_id))
        super().throttled(request, wait)


class AnonTenantThrottle(SimpleRateThrottle):
    """60/min for anonymous/unauth requests; relaxed in E2E/test envs."""
    scope = "anon_tenant"

    def get_rate(self):
        """Return a relaxed rate when RATE_LIMIT_E2E_RELAX is True."""
        from django.conf import settings

        if getattr(settings, "RATE_LIMIT_E2E_RELAX", False):
            return "5000/minute"
        return super().get_rate()

    def allow_request(self, request, view):
        self._view = view
        try:
            return super().allow_request(request, view)
        except Exception:
            logger.warning(
                "throttle_cache_unavailable",
                extra={
                    "scope": self.scope,
                    "key": self.get_cache_key(request, view),
                },
                exc_info=True,
            )
            return True

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # only throttle anonymous
        try:
            from hub.apps.tenants.request_tenant import get_request_tenant
            _tid, _ = get_request_tenant(request)
            return f"throttle_{self.scope}_{_tid}" if _tid else self.get_ident(request)
        except Exception:
            return self.get_ident(request)

    def throttled(self, request, wait):
        """285.14.11.V.7 — emit throttle_hit_total on 429."""
        try:
            from hub.apps.tenants.request_tenant import get_request_tenant_id
            tenant_id = get_request_tenant_id(request) or "unknown"
        except Exception:
            tenant_id = "unknown"
        app, view_name = _resolve_app_and_view(getattr(self, "_view", None))
        _emit_throttle_hit_metric(app, view_name, self.scope, str(tenant_id))
        super().throttled(request, wait)
