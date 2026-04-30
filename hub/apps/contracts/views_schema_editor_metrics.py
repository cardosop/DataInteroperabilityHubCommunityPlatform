"""
Phase 227 Wave 1 (227.L7.2) — Schema-editor metrics receive endpoint.

The frontend ``ModelsEditor.tsx`` POSTs metric events to this endpoint
on tab open and on save. We translate each event into an OTel
counter / histogram increment server-side rather than embed an OTLP
exporter in the SPA bundle (saves ~200 KB of vendored SDK and keeps
the metric inventory consistent with the rest of the codebase).

Authentication
--------------
Requires the standard authenticated session. Tenant is derived from
the request (no client-supplied ``tenant_id`` to prevent cross-tenant
metric pollution).

Schema
------
``POST /api/v1/contracts/schema-editor/metrics`` body::

    {
        "event": "opened" | "save",
        "spec_type": "ODCS" | "ODPS" | string,
        "outcome": "success" | "conflict" | "validation_error" | "error",
        "time_to_first_save_seconds": <float>  // only for the first
                                                 // successful save in
                                                 // a session
    }

Response: ``204 No Content`` on success. Unknown event names are
ignored with ``204`` (forward-compat: a future frontend release can
ship new events without a backend bump).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


# Allowed values per the spec — kept as constants here so the
# frontend can mirror them without server round-trips.
EVENT_OPENED = "opened"
EVENT_SAVE = "save"
ALLOWED_OUTCOMES = {"success", "conflict", "validation_error", "error"}


def _resolve_tenant_id(request: Request) -> str | None:
    """Resolve the calling tenant_id without trusting the client body.

    Falls back to ``request.user.tenant_id`` then ``request.user.tenant.id``.
    Returns ``None`` if no tenant context is available — the metric is
    then tagged with ``UNKNOWN``.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id:
        return str(tenant_id)
    tenant = getattr(user, "tenant", None)
    if tenant is not None and getattr(tenant, "id", None):
        return str(tenant.id)
    return None


def _emit_event(
    *,
    event: str,
    spec_type: str,
    tenant_id: str | None,
    outcome: str | None,
    time_to_first_save_seconds: float | None,
) -> None:
    """Forward a single event to the OTel metric wrappers."""
    try:
        from hub.apps.observability.otel_metrics import (
            schema_editor_opened_total,
            schema_editor_save_total,
            schema_editor_time_to_first_save_seconds,
        )
    except ImportError:
        # OTel SDK not installed in this env — silently drop.
        return

    safe_tenant = tenant_id or "UNKNOWN"
    safe_spec = (spec_type or "UNKNOWN").upper()

    if event == EVENT_OPENED:
        schema_editor_opened_total.labels(
            tenant_id=safe_tenant,
            spec_type=safe_spec,
        ).inc()
        return

    if event == EVENT_SAVE:
        normalized_outcome = (outcome or "error").lower()
        if normalized_outcome not in ALLOWED_OUTCOMES:
            normalized_outcome = "error"
        schema_editor_save_total.labels(
            tenant_id=safe_tenant,
            spec_type=safe_spec,
            outcome=normalized_outcome,
        ).inc()
        # Histogram only fires on the first successful save (sender
        # responsibility); we observe whatever value is supplied.
        if (
            normalized_outcome == "success"
            and time_to_first_save_seconds is not None
        ):
            try:
                ttfs = float(time_to_first_save_seconds)
            except (TypeError, ValueError):
                return
            if ttfs >= 0:
                schema_editor_time_to_first_save_seconds.labels(
                    tenant_id=safe_tenant,
                    spec_type=safe_spec,
                ).observe(ttfs)
        return

    # Unknown event — ignored for forward-compat.
    logger.debug(
        "schema_editor_metrics_unknown_event", extra={"event": event}
    )


class SchemaEditorMetricsView(APIView):
    """Receives schema-editor telemetry events from the frontend.

    Auth-only (no tenant- or role-gated check beyond authentication
    because the metric labels are server-derived from
    ``request.user`` — no opportunity for cross-tenant pollution).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        body: Dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        event = str(body.get("event", "")).strip()
        if not event:
            return Response(
                {"error": "event is required", "code": "EVENT_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        spec_type = str(body.get("spec_type", "")).strip()
        outcome = body.get("outcome")
        ttfs_raw = body.get("time_to_first_save_seconds")

        _emit_event(
            event=event,
            spec_type=spec_type,
            tenant_id=_resolve_tenant_id(request),
            outcome=str(outcome).strip() if outcome is not None else None,
            time_to_first_save_seconds=(
                float(ttfs_raw)
                if isinstance(ttfs_raw, (int, float)) and ttfs_raw >= 0
                else None
            ),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
