"""
Phase 277.B.088 — breach notification SLA metrics.

Emits ``breach_hours_since_discovery`` gauge for every unresolved
(non-CLOSED, non-legal-hold) breach incident so Prometheus alerts
can fire when the GDPR Art. 33 72h window is approached.

Usage:
    from hub.apps.breach.sla_metrics import emit_breach_sla_metrics
    emit_breach_sla_metrics()
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def emit_breach_sla_metrics() -> list[dict]:
    """Scan unresolved breach incidents and update the SLA gauge.

    Returns a list of ``{tenant_id, breach_id, hours}`` dicts for
    testability.

    Best-effort: a metric emission failure is silently swallowed.
    """
    from hub.apps.breach.models import BreachIncident, BreachIncidentStatus
    from hub.apps.observability.otel_metrics import breach_hours_since_discovery

    now = timezone.now()
    unresolved = BreachIncident.objects.filter(
        status__in=(
            BreachIncidentStatus.OPEN,
            BreachIncidentStatus.CONTAINED,
            BreachIncidentStatus.NOTIFIED,
        ),
        legal_hold=False,
        discovered_at__isnull=False,
    ).select_related("tenant").order_by("discovered_at")

    results: list[dict] = []
    try:
        for incident in unresolved:
            delta = now - incident.discovered_at
            hours = max(0.0, delta.total_seconds() / 3600.0)
            results.append({
                "tenant_id": str(incident.tenant_id),
                "breach_id": str(incident.id),
                "hours": round(hours, 1),
            })
            breach_hours_since_discovery.labels(
                tenant_id=str(incident.tenant_id),
                breach_id=str(incident.id),
            ).set(hours)
    except Exception:
        logger.exception("breach_sla_metrics_emit_failed")

    if results:
        oldest = results[0]
        logger.info(
            "breach_sla_metrics_emitted",
            extra={
                "unresolved_count": len(results),
                "oldest_hours": oldest["hours"],
                "oldest_breach_id": oldest["breach_id"],
            },
        )

    return results
