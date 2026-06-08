"""Breach statutory SLA scanner (Phase 232.3.7), mirrors DSAR clock sweeper."""

from __future__ import annotations
from django.utils import timezone

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.breach.models import BreachIncident, BreachIncidentStatus, BreachSLALevel
from hub.apps.regulation_policies.registry import merge_breach_incident_sla_windows


def _hours_remaining(deadline) -> float | None:
    if deadline is None:
        return None
    return (deadline - timezone.now()).total_seconds() / 3600.0


def run_breach_notification_clock_scan(*, limits: tuple[str, ...] | None = None) -> dict[str, int]:
    terminal = (BreachIncidentStatus.CLOSED,)
    active = limits or (
        BreachIncidentStatus.OPEN,
        BreachIncidentStatus.CONTAINED,
        BreachIncidentStatus.NOTIFIED,
    )
    qs = BreachIncident.objects.exclude(status__in=terminal).filter(status__in=active)
    qs = qs.filter(legal_hold=False)

    counters = {"warn": 0, "critical": 0, "escalated": 0}

    for row in qs.iterator(chunk_size=200):
        regimes = row.regimes or ["GDPR"]
        matrix = merge_breach_incident_sla_windows(regimes)
        warn_h = float(matrix["sla_warn_hours_before_deadline"])
        alert_h = float(matrix["sla_alert_hours_before_deadline"])
        remaining = _hours_remaining(row.statutory_authority_deadline_utc)
        if remaining is None:
            continue

        target = BreachSLALevel.NONE
        audit_suffix = ""

        if remaining < 0 and matrix.get("sla_escalate_on_deadline_breach"):
            target = BreachSLALevel.ESCALATED
            audit_suffix = "OVERDUE"
        elif remaining <= alert_h:
            target = BreachSLALevel.ALERT
            audit_suffix = "CRITICAL_WINDOW"
        elif remaining <= warn_h:
            target = BreachSLALevel.WARN
            audit_suffix = "WARN_WINDOW"

        if target == BreachSLALevel.NONE:
            continue

        severity_rank = {
            BreachSLALevel.NONE: 0,
            BreachSLALevel.WARN: 1,
            BreachSLALevel.ALERT: 2,
            BreachSLALevel.ESCALATED: 3,
        }
        prev = row.last_sla_level
        if severity_rank.get(prev, 0) >= severity_rank[target]:
            continue

        row.last_sla_level = target
        row.save(update_fields=["last_sla_level", "updated_at"])

        create_audit_event(
            resource_type="BREACH_INCIDENT",
            action={
                "WARN_WINDOW": audit_event_types.BREACH_SLA_WARN_WINDOW,
                "CRITICAL_WINDOW": audit_event_types.BREACH_SLA_CRITICAL_WINDOW,
                "OVERDUE": audit_event_types.BREACH_SLA_OVERDUE,
            }[audit_suffix],
            tenant=row.tenant,
            resource_id=str(row.id),
            details={
                "remaining_hours": round(remaining, 4),
                "regimes": list(regimes),
            },
        )

        if target == BreachSLALevel.ESCALATED:
            counters["escalated"] += 1
        elif target == BreachSLALevel.ALERT:
            counters["critical"] += 1
        elif target == BreachSLALevel.WARN:
            counters["warn"] += 1

    return counters
