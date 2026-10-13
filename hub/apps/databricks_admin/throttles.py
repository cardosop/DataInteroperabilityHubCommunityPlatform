"""Per-surface throttles for the Databricks control plane.

Phase 273 contract: throttle cache keys MUST include tenant_id
(``f"throttle_{name}_{tenant_id}"``) — one tenant's exhaustion never
affects another's quota. The Delta Sharing throttle below keys per
RECIPIENT TOKEN (5.2): the tenant id AND the token's sha256 hash ride the
key, so a token's bucket is per-consumer while the key remains
tenant-scoped.
"""

from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from hub.apps.audit.event_types import DELTA_SHARE_RATE_LIMIT_EXCEEDED


class DeltaShareTokenRateThrottle(SimpleRateThrottle):
    """Per-recipient-token throttle for the Delta Sharing protocol
    surface (task 5.2 — the consumer wiring lands with 5.3).

    A ``SimpleRateThrottle`` subclass, NOT a ``ScopedRateThrottle``: the
    scope is FIXED (``delta_share_recipients``) for every view that
    mounts this throttle — DRF 3.16's ScopedRateThrottle derives the
    scope from the VIEW's ``throttle_scope`` and lets every other view
    through untouched, which would silently disable the per-token
    boundary here.

    The key resolves the presented bearer token through the production
    registry (``DeltaShareToken.resolve`` — hash lookup only, never the
    plaintext) and scopes the bucket to ``{tenant_id}_{token_hash}``.
    An unresolvable/missing token gets NO bucket here — the auth layer
    owns the 401.
    """

    scope = "delta_share_recipients"
    cache_format = "throttle_%(scope)s_%(ident)s"

    def __init__(self):
        super().__init__()
        self._token = None

    def get_cache_key(self, request, _view):
        plaintext = self._bearer_token(request)
        if not plaintext:
            return None
        from hub.apps.databricks_admin.models import DeltaShareToken

        token = DeltaShareToken.resolve(plaintext)
        if token is None:
            return None
        self._token = token
        ident = f"{token.tenant_id}_{token.token_hash}"
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def throttle_failure(self):
        """The 429 chokepoint (DRF 3.16 — the ``throttled()`` hook is
        dead code; the failure branch is the emission point): the
        rate-limit audit row, best-effort."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from hub.apps.audit.utils import create_audit_event

            token = self._token
            create_audit_event(
                resource_type="ASSET",
                action=DELTA_SHARE_RATE_LIMIT_EXCEEDED,
                tenant=token.tenant if token is not None else None,
                resource_id=str(token.id) if token is not None else None,
                details={
                    "token_prefix": token.token_prefix if token is not None else "",
                },
            )
        except Exception:
            logger.warning("delta_share_rate_limit_audit_failed")
        return False

    @staticmethod
    def _bearer_token(request) -> str:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, credentials = header.partition(" ")
        if scheme.lower() != "bearer" or not credentials.strip():
            return ""
        return credentials.strip()


class MlAssetsRateThrottle(ScopedRateThrottle):
    """The 12.6 ML-assets browse surface's throttle (Phase 273
    contract): the cache key carries the TENANT ID
    (``throttle_databricks_ml_assets_<tenant_id>`` — one tenant's
    exhaustion never affects another's quota; the views keep their
    ``throttle_scope``), and the ``allow_request`` failure branch
    emits ``DATABRICKS_ML_RATE_LIMIT_EXCEEDED`` (DRF 3.16 — the
    ``throttled()`` override is dead code).

    A tenant-level bucket (the search-throttle precedent), NOT a
    per-user one: the surface's quota is the tenant's, and the ML
    views resolve the tenant the same chain the gate uses
    (request.tenant → request.user.tenant). A request without a
    resolvable tenant falls back to the DRF ident bucket (still
    throttled, never fail-open).
    """

    scope = "databricks_ml_assets"
    audit_action = "DATABRICKS_ML_RATE_LIMIT_EXCEEDED"

    def get_cache_key(self, request, view):
        tenant = getattr(request, "tenant", None)
        if tenant is None and hasattr(request, "user") and hasattr(request.user, "tenant"):
            tenant = request.user.tenant
        if tenant is not None:
            return f"throttle_{self.scope}_{tenant.id}"
        return super().get_cache_key(request, view)

    def _on_throttled(self, request, wait):
        """The 429 chokepoint — best-effort audit, identifiers only."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from hub.apps.audit.event_types import DATABRICKS_ML_RATE_LIMIT_EXCEEDED
            from hub.apps.audit.utils import create_audit_event

            tenant = getattr(request, "tenant", None)
            if tenant is None and hasattr(request, "user") and hasattr(request.user, "tenant"):
                tenant = request.user.tenant
            create_audit_event(
                resource_type="DATABRICKS_ML_ASSET",
                action=DATABRICKS_ML_RATE_LIMIT_EXCEEDED,
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=tenant,
                resource_id=None,
                result="THROTTLED",
                details={"wait_seconds": int(wait)},
            )
        except Exception:
            logger.warning("databricks_ml_rate_limit_audit_failed")

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        if not allowed:
            self._on_throttled(request, int(self.wait()))
        return allowed
