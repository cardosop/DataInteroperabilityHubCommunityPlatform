"""Cross-tenant denial telemetry helpers.

Phase 260.A.5 introduces a single helper to ensure denied cross-tenant
attempts produce a consistent signal across logging, audit, and metrics.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from django.http import HttpRequest

logger = logging.getLogger(__name__)


class _DeniedCounter(Protocol):
    def labels(self, **kwargs) -> "_DeniedCounter": ...

    def inc(self) -> None: ...


try:
    from prometheus_client import Counter

    cross_tenant_denied_total: _DeniedCounter = Counter(
        "cross_tenant_denied_total",
        "Cross-tenant requests denied",
        ["endpoint", "reason"],
    )
except Exception:  # pragma: no cover - defensive fallback
    class _CounterStub:
        def labels(self, **kwargs):  # noqa: ARG002
            return self

        def inc(self):
            return None

    cross_tenant_denied_total = _CounterStub()


def cross_tenant_denied(
    endpoint: str,
    reason: str,
    request: HttpRequest,
    requested_tenant_id: Any,
    actual_tenant_id: Any,
) -> None:
    """Emit cross-tenant denial telemetry in one place.

    This helper is best-effort by design: observability failures should
    never change the HTTP denial outcome.
    """
    requested = str(requested_tenant_id or "")
    actual = str(actual_tenant_id or "")

    try:
        from hub.apps.audit import event_types
        from hub.apps.audit.utils import create_audit_event

        actor_user = getattr(request, "user", None)
        if actor_user is not None and not getattr(
            actor_user,
            "is_authenticated",
            False,
        ):
            actor_user = None
        tenant = (
            getattr(actor_user, "tenant", None)
            if actor_user is not None
            else None
        )

        create_audit_event(
            resource_type="AUTH",
            action=event_types.CROSS_TENANT_DENIED,
            actor_user=actor_user,
            tenant=tenant,
            result="FAILURE",
            details={
                "endpoint": endpoint,
                "reason": reason,
                "requested_tenant_id": requested,
                "actual_tenant_id": actual,
                "path": request.path,
                "method": request.method,
            },
            request=request,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning(
            "cross_tenant_denied_audit_failed endpoint=%s reason=%s error=%s",
            endpoint,
            reason,
            exc,
        )

    try:
        cross_tenant_denied_total.labels(endpoint=endpoint, reason=reason).inc()
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning(
            "cross_tenant_denied_metric_failed endpoint=%s reason=%s error=%s",
            endpoint,
            reason,
            exc,
        )

    logger.warning(
        "cross_tenant_denied endpoint=%s reason=%s "
        "requested_tenant_id=%s actual_tenant_id=%s",
        endpoint,
        reason,
        requested,
        actual,
    )
