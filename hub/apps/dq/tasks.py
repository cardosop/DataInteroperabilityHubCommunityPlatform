"""
Phase 240.1.A.5 — RQ tasks for DQ alert delivery + retry + dead-letter.

The dispatcher (``hub.apps.dq.alerting._deliver_alert``) calls
``deliver_or_schedule_retry`` synchronously on the first attempt. On
failure we enqueue ``dq_alert_redeliver`` with a back-off-aware delay
(1m → 5m → 30m → dead-letter). The back-off ladder is derived from
D240.8.

Why deliver synchronously on attempt 1?
---------------------------------------
The first delivery happens in the same request that just finished
evaluating DQ rules. Synchronous delivery there means: (1) the call
chain is debug-friendly, (2) success bypasses RQ entirely (less load,
no end-to-end queue latency), and (3) we don't need to serialize the
``rule + payload`` twice for the success path.

Why hand off retries to RQ?
---------------------------
Retries need to survive worker restarts, get scheduled with delay,
and not block the original caller. RQ's ``enqueue_in`` covers all
three. The retry task takes only serializable scalars (``rule_id``,
``payload``, ``attempt_number``) so it round-trips cleanly through
Redis.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone

from django_rq import get_queue, job

# Phase 240.5.F.3 — wrap every ``logger.*(..., extra={...})`` call's
# payload in ``_redact()`` before emit so future field additions
# (e.g. accidental ``details_json`` / ``row_samples``) are stripped.
from .log_helpers import _redact


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Back-off ladder (D240.8)
# ---------------------------------------------------------------------------
#
# Each entry is (delay_seconds, attempt_number_after_this_delay). The
# dispatcher's first synchronous attempt is "attempt 1" — if it fails,
# we schedule attempt 2 to fire after 60 s, then attempt 3 after 5 m,
# then attempt 4 after 30 m. After attempt 4 fails we dead-letter.
RETRY_SCHEDULE_SECONDS: List[int] = [60, 5 * 60, 30 * 60]

#: Total attempts INCLUDING the synchronous first attempt. Equals
#: ``len(RETRY_SCHEDULE_SECONDS) + 1`` by construction.
MAX_DELIVERY_ATTEMPTS: int = len(RETRY_SCHEDULE_SECONDS) + 1


# ---------------------------------------------------------------------------
# Public entry-point — synchronous first attempt
# ---------------------------------------------------------------------------


def deliver_or_schedule_retry(
    *,
    rule_id: str,
    channel: str,
    payload: Dict[str, Any],
    attempt_number: int = 1,
) -> Dict[str, Any]:
    """Try one delivery; on failure schedule the next retry / dead-letter.

    Returns
    -------
    dict
        ``{"success": bool, "delivery_id": str, "error": str | None,
        "attempt_number": int, "next_action": str}`` where
        ``next_action`` is one of ``"none"`` (delivered),
        ``"retry_scheduled"`` (will retry after back-off), or
        ``"dead_lettered"`` (retry budget exhausted).
    """
    from hub.apps.dq.clients import (
        DeliveryResult,
        get_client_for_channel,
    )
    from hub.apps.dq.models import DQAlertingRule

    rule = DQAlertingRule.objects.filter(pk=rule_id).first()
    if rule is None:
        # Rule was deleted between scheduling and execution. Nothing
        # to do — the partner won't see a stale alert because we
        # never made the request.
        logger.warning(
            "dq_alert_rule_missing_for_retry",
            extra=_redact({"rule_id": rule_id, "attempt_number": attempt_number}),
        )
        return {
            "success": False,
            "delivery_id": "",
            "error": "rule_missing",
            "attempt_number": attempt_number,
            "next_action": "none",
        }

    try:
        client = get_client_for_channel(channel)
    except ValueError as exc:
        logger.error(
            "dq_alert_unknown_channel",
            extra=_redact({
                "rule_id": rule_id, "channel": channel, "error": str(exc),
            }),
        )
        _emit_dead_letter_audit(rule, channel, payload, str(exc), attempt_number)
        return {
            "success": False,
            "delivery_id": "",
            "error": f"unknown_channel: {exc}",
            "attempt_number": attempt_number,
            "next_action": "dead_lettered",
        }

    result: DeliveryResult = client.deliver(rule, payload)

    if result.success:
        _emit_delivered_audit(rule, channel, payload, result, attempt_number)
        _stamp_last_fired(rule, payload)
        return {
            "success": True,
            "delivery_id": result.delivery_id,
            "error": None,
            "attempt_number": attempt_number,
            "next_action": "none",
        }

    # Failure — emit FAILED audit, then decide retry vs dead-letter.
    _emit_failed_audit(
        rule, channel, payload, result.error or "unknown", attempt_number,
    )

    # Unrecoverable failures should NOT be retried.
    unrecoverable = bool((result.metadata or {}).get("unrecoverable"))
    next_action = _schedule_retry_or_dead_letter(
        rule_id=str(rule.id),
        channel=channel,
        payload=payload,
        attempt_number=attempt_number,
        last_error=result.error or "unknown",
        unrecoverable=unrecoverable,
    )
    if next_action == "dead_lettered":
        _emit_dead_letter_audit(
            rule, channel, payload, result.error or "unknown", attempt_number,
        )

    return {
        "success": False,
        "delivery_id": result.delivery_id,
        "error": result.error,
        "attempt_number": attempt_number,
        "next_action": next_action,
    }


# ---------------------------------------------------------------------------
# RQ retry task
# ---------------------------------------------------------------------------


@job("job_low", timeout=120)
def dq_alert_redeliver(
    *,
    rule_id: str,
    channel: str,
    payload: Dict[str, Any],
    attempt_number: int,
) -> Dict[str, Any]:
    """RQ task — re-attempt delivery after back-off.

    Wired in from ``deliver_or_schedule_retry`` via ``enqueue_in``.
    Calls back into ``deliver_or_schedule_retry`` so the success
    audit / dead-letter logic is shared with the synchronous path.
    """
    return deliver_or_schedule_retry(
        rule_id=rule_id,
        channel=channel,
        payload=payload,
        attempt_number=attempt_number,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _schedule_retry_or_dead_letter(
    *,
    rule_id: str,
    channel: str,
    payload: Dict[str, Any],
    attempt_number: int,
    last_error: str,
    unrecoverable: bool,
) -> str:
    """Schedule the next retry attempt OR move to dead-letter.

    Returns ``"retry_scheduled"`` or ``"dead_lettered"``.
    """
    if unrecoverable or attempt_number >= MAX_DELIVERY_ATTEMPTS:
        # Either out of attempts OR the failure mode is config-level
        # (mis-typed webhook URL etc.) — retrying won't change the
        # outcome.
        _page_ops_pagerduty(
            rule_id=rule_id,
            channel=channel,
            payload=payload,
            attempt_number=attempt_number,
            last_error=last_error,
        )
        return "dead_lettered"

    # attempt_number is 1-indexed; first retry uses index 0 in the
    # schedule. Defensive bound check.
    schedule_index = attempt_number - 1
    if schedule_index < 0 or schedule_index >= len(RETRY_SCHEDULE_SECONDS):
        return "dead_lettered"

    delay_seconds = RETRY_SCHEDULE_SECONDS[schedule_index]
    next_attempt = attempt_number + 1

    from datetime import timedelta

    queue = get_queue("job_low")
    queue.enqueue_in(
        timedelta(seconds=delay_seconds),
        dq_alert_redeliver,
        rule_id=rule_id,
        channel=channel,
        payload=payload,
        attempt_number=next_attempt,
    )
    logger.info(
        "dq_alert_retry_scheduled",
        extra=_redact({
            "rule_id": rule_id,
            "channel": channel,
            "alert_id": payload.get("alert_id"),
            "attempt_number": next_attempt,
            "delay_seconds": delay_seconds,
        }),
    )
    return "retry_scheduled"


def _stamp_last_fired(rule, payload: Dict[str, Any]) -> None:
    """Persist the dedup window state — atomic UPDATE, no full save."""
    from hub.apps.dq.models import DQAlertingRule

    alert_id = payload.get("alert_id") or ""
    DQAlertingRule.objects.filter(pk=rule.pk).update(
        last_alert_id=alert_id[:64],
        last_fired_at=timezone.now(),
    )


def _record_audit_write_failure(action: str, exc: Exception) -> None:
    """Phase 240.1.B audit-fix — count DQ-domain audit-write failures.

    The ``create_audit_event`` helper is best-effort (so the surrounding
    request never fails), which means an audit-row absence is silent
    today. The Prometheus counter incremented here drives the
    ``DQAuditWriteFailing`` alert (>1/min for 5m, severity critical) so
    oncall sees compliance evidence at risk BEFORE the next audit query
    surfaces the gap.
    """
    try:
        from services.shared.metrics import dq_audit_write_errors_total

        dq_audit_write_errors_total.labels(
            service="hub", action=action,
        ).inc()
    except Exception:  # noqa: BLE001
        pass
    logger.warning(
        "dq_audit_write_failed action=%s error=%s", action, exc,
    )


def _emit_delivered_audit(rule, channel, payload, result, attempt_number) -> None:
    from hub.apps.audit.event_types import (
        DQ_ALERT_DELIVERED,
        DQ_ALERT_RESOURCE_TYPE,
    )
    from hub.apps.audit.utils import create_audit_event

    # Phase 240.1.B audit-fix — increment the delivery counter so the
    # DQAlertDeliveryFailing alert (>10% FAIL over 30m) and the
    # dashboard "alert rule firing count by channel" panel see real
    # series.  Wrapped in try/except because the metric is observability,
    # not load-bearing.
    try:
        from services.shared.metrics import dq_alert_deliveries_total

        dq_alert_deliveries_total.labels(
            service="hub", channel=channel, status="SUCCESS",
        ).inc()
    except Exception:
        pass

    try:
        create_audit_event(
            resource_type=DQ_ALERT_RESOURCE_TYPE,
            action=DQ_ALERT_DELIVERED,
            actor_user=None,
            tenant=rule.tenant,
            resource_id=str(rule.id),
            result="SUCCESS",
            details={
                "channel": channel,
                "delivery_id": result.delivery_id,
                "alert_id": payload.get("alert_id"),
                "rule_id": str(rule.id),
                "rule_name": rule.name,
                "run_id": payload.get("dq_run_id"),
                "attempt_number": attempt_number,
                "metadata": result.metadata,
            },
        )
    except Exception as exc:  # noqa: BLE001 — best-effort audit
        # Phase 240.1.B audit-fix — count audit-write failures so the
        # DQAuditWriteFailing alert can fire.  We re-raise on the
        # underlying create_audit_event failure path is not desirable
        # here (caller's job-system would fail open), so we count and
        # continue; the audit row's absence is the regulator-grade
        # signal, but the metric makes it visible BEFORE the next
        # audit query.
        _record_audit_write_failure("DQ_ALERT_DELIVERED", exc)


def _emit_failed_audit(rule, channel, payload, error, attempt_number) -> None:
    from hub.apps.audit.event_types import (
        DQ_ALERT_FAILED,
        DQ_ALERT_RESOURCE_TYPE,
    )
    from hub.apps.audit.utils import create_audit_event

    # Phase 240.1.B audit-fix — symmetrical FAIL counter so the
    # DQAlertDeliveryFailing alert sees both the numerator and
    # denominator series.
    try:
        from services.shared.metrics import dq_alert_deliveries_total

        dq_alert_deliveries_total.labels(
            service="hub", channel=channel, status="FAIL",
        ).inc()
    except Exception:
        pass

    try:
        create_audit_event(
            resource_type=DQ_ALERT_RESOURCE_TYPE,
            action=DQ_ALERT_FAILED,
            actor_user=None,
            tenant=rule.tenant,
            resource_id=str(rule.id),
            result="FAILURE",
            details={
                "channel": channel,
                "alert_id": payload.get("alert_id"),
                "rule_id": str(rule.id),
                "error": str(error)[:1024],
                "attempt_number": attempt_number,
            },
        )
    except Exception as exc:  # noqa: BLE001 — best-effort audit
        _record_audit_write_failure("DQ_ALERT_FAILED", exc)


def _emit_dead_letter_audit(rule, channel, payload, error, attempt_number) -> None:
    from hub.apps.audit.event_types import (
        DQ_ALERT_DEAD_LETTER,
        DQ_ALERT_RESOURCE_TYPE,
    )
    from hub.apps.audit.utils import create_audit_event

    create_audit_event(
        resource_type=DQ_ALERT_RESOURCE_TYPE,
        action=DQ_ALERT_DEAD_LETTER,
        actor_user=None,
        tenant=rule.tenant,
        resource_id=str(rule.id),
        result="FAILURE",
        details={
            "channel": channel,
            "alert_id": payload.get("alert_id"),
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "last_error": str(error)[:1024],
            "total_attempts": attempt_number,
            "dead_lettered_at": timezone.now().isoformat(),
        },
    )


def _page_ops_pagerduty(
    *,
    rule_id: str,
    channel: str,
    payload: Dict[str, Any],
    attempt_number: int,
    last_error: str,
) -> None:
    """Page the platform-ops PagerDuty when an alert dead-letters.

    This is the OPS-PagerDuty (the platform team's) and is distinct
    from the customer-facing PagerDuty channel — D240.8 is explicit
    that customer-facing PD MUST NOT be the dead-letter destination
    (would self-amplify on a configuration bug).

    The integration key is read from ``settings.OPS_PAGERDUTY_KEY``.
    Absent / empty → no-op + structured log so dev environments don't
    fail when the secret isn't wired.
    """
    from django.conf import settings

    routing_key: Optional[str] = getattr(settings, "OPS_PAGERDUTY_KEY", None)
    if not routing_key:
        logger.warning(
            "dq_alert_dead_letter_ops_pagerduty_skipped",
            extra=_redact({
                "reason": "OPS_PAGERDUTY_KEY not configured",
                "rule_id": rule_id,
                "channel": channel,
                "attempt_number": attempt_number,
            }),
        )
        return

    try:
        import requests

        response = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json={
                "routing_key": routing_key,
                "event_action": "trigger",
                "dedup_key": (
                    f"dq_alert_dead_letter:{rule_id}:"
                    f"{payload.get('alert_id', '')}"
                ),
                "payload": {
                    "summary": (
                        f"DQ alert dead-letter for rule {rule_id} "
                        f"on channel {channel}"
                    ),
                    "source": "meshant-dq-ops",
                    "severity": "error",
                    "component": "dq-alerting-pipeline",
                    "group": "platform-ops",
                    "class": "dead-letter",
                    "custom_details": {
                        "rule_id": rule_id,
                        "channel": channel,
                        "alert_id": payload.get("alert_id"),
                        "last_error": last_error[:1024],
                        "attempt_number": attempt_number,
                    },
                },
            },
            timeout=10,
            headers={"User-Agent": "Meshant-DQAlerter-Ops/1.0"},
        )
        if response.status_code != 202:
            logger.error(
                "dq_alert_dead_letter_ops_pagerduty_failed",
                # Phase 240.5.F.3 — body_preview is bounded to 200 chars
                # but could in principle echo customer-derived content;
                # _redact() drops any redacted-key bag a future change
                # might introduce here.
                extra=_redact({
                    "rule_id": rule_id,
                    "channel": channel,
                    "http_status": response.status_code,
                    "body_preview": response.text[:200],
                }),
            )
    except Exception as exc:  # noqa: BLE001 — boundary
        # Don't let an ops-paging failure mask the dead-letter audit
        # row that already landed. Log loudly and move on; ops
        # already has the audit-event-based on-call dashboard.
        logger.error(
            "dq_alert_dead_letter_ops_pagerduty_exception",
            extra=_redact({
                "rule_id": rule_id,
                "channel": channel,
                "error": str(exc),
            }),
            exc_info=True,
        )
