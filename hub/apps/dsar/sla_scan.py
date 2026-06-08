"""Nightly statutory-clock evaluation (Phase 232.2.5)."""

from __future__ import annotations
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.dsar.models import DSARRequest, DSARSLALevel, DSARStatus
from hub.apps.dsar.webhook_emission import publish_dsar_event
from hub.apps.regulation_policies.registry import dsar_statutory_clock_matrix
from hub.apps.webhooks.models import WebhookEventType


def _days_remaining(dsar: DSARRequest) -> float | None:
    if not dsar.statutory_fulfil_deadline_utc:
        return None
    deadline = dsar.statutory_fulfil_deadline_utc
    now = timezone.now()
    return (deadline - now).total_seconds() / 86400.0


def run_dsar_statutory_clock_scan(*, limits: tuple[str, ...] | None = None) -> dict[str, int]:
    """
    Warn / alert / escalate based on regime matrix. Legal-hold rows are skipped.

    Args:
        limits: Optional subset of statuses to inspect (defaults to active pipeline).
    """
    terminal = (
        DSARStatus.CLOSED_FULFILLED,
        DSARStatus.CLOSED_REJECTED,
    )
    statuses = limits or (
        DSARStatus.SUBMITTED,
        DSARStatus.IDV_PENDING,
        DSARStatus.UNDER_REVIEW,
        DSARStatus.PACKAGE_IN_PROGRESS,
        DSARStatus.AWAITING_DOWNLOAD,
    )

    qs = DSARRequest.objects.exclude(status__in=terminal).filter(status__in=statuses)
    qs = qs.filter(legal_hold=False)

    counters = {"warn": 0, "critical": 0, "escalated": 0}

    for dsar in qs.iterator(chunk_size=200):
        regimes = dsar.regimes or ["GDPR"]
        regime_key = str(regimes[0]).upper()
        matrix = dsar_statutory_clock_matrix(regime_key)

        warn_d = float(matrix["sla_warn_days_before_deadline"])
        alert_d = float(matrix["sla_alert_days_before_deadline"])
        remaining = _days_remaining(dsar)
        if remaining is None:
            continue

        target_level = DSARSLALevel.NONE
        webhook_type = None
        audit_suffix = ""

        if remaining < 0 and matrix.get("sla_escalate_on_deadline_breach"):
            target_level = DSARSLALevel.ESCALATED
            webhook_type = WebhookEventType.DSAR_SLA_ESCALATED
            audit_suffix = "OVERDUE"
        elif remaining <= alert_d:
            target_level = DSARSLALevel.ALERT
            webhook_type = WebhookEventType.DSAR_SLA_CRITICAL
            audit_suffix = "CRITICAL_WINDOW"
        elif remaining <= warn_d:
            target_level = DSARSLALevel.WARN
            webhook_type = WebhookEventType.DSAR_SLA_WARNING
            audit_suffix = "WARN_WINDOW"

        if target_level == DSARSLALevel.NONE:
            continue

        severity_rank = {
            DSARSLALevel.NONE: 0,
            DSARSLALevel.WARN: 1,
            DSARSLALevel.ALERT: 2,
            DSARSLALevel.ESCALATED: 3,
        }

        prev = dsar.last_sla_level
        if severity_rank.get(prev, 0) >= severity_rank[target_level]:
            continue

        dsar.last_sla_level = target_level
        dsar.save(update_fields=["last_sla_level", "updated_at"])

        create_audit_event(
            resource_type="DSAR_REQUEST",
            action=f"DSAR_SLA_{audit_suffix}",
            tenant=dsar.tenant,
            resource_id=str(dsar.id),
            details={
                "remaining_days": round(remaining, 4),
                "regime": regime_key,
            },
        )
        publish_dsar_event(dsar, webhook_type)

        if target_level == DSARSLALevel.ESCALATED:
            counters["escalated"] += 1
        elif target_level == DSARSLALevel.ALERT:
            counters["critical"] += 1
        elif target_level == DSARSLALevel.WARN:
            counters["warn"] += 1

    return counters
