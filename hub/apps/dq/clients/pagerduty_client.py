"""
Phase 240.1.A.1 — DQ alert delivery to PagerDuty Events API v2.

Wire format
-----------
HTTP POST to ``https://events.pagerduty.com/v2/enqueue`` with a JSON
body. The ``routing_key`` is the integration key tied to the tenant's
PagerDuty service; we DO NOT page the platform-ops PagerDuty here —
that's the dead-letter codepath in ``hub.apps.dq.tasks`` (D240.8).

Dedup
-----
PagerDuty has its own server-side dedup keyed by ``dedup_key``. We
pass the alerting pipeline's deterministic ``alert_id`` so PagerDuty
folds re-fires of the same condition into a single incident — even
across worker restarts where our local dedup state might be lost.

Severity mapping
----------------
Our ``DQAnomalySeverity`` (CRITICAL/HIGH/MEDIUM/LOW) maps to the
PagerDuty severity enum (critical/error/warning/info). LOW is the
only one that maps to ``info`` because PagerDuty's ``info`` does NOT
trigger a page — that's the desired behaviour for low-severity DQ
findings.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import AlertDeliveryError, BaseAlertClient, DeliveryResult

logger = logging.getLogger(__name__)


_PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"
_DEFAULT_TIMEOUT_SECONDS = 10

_SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "info",
}


class PagerDutyAlertClient(BaseAlertClient):
    """PagerDuty Events API v2 delivery."""

    channel = "PAGERDUTY"

    def _deliver(self, rule, payload: dict[str, Any]) -> DeliveryResult:
        import requests  # lazy import

        config = rule.get_channel_config() or {}
        routing_key = config.get("integration_key") or config.get("routing_key")
        if not routing_key:
            raise AlertDeliveryError(
                f"PAGERDUTY channel config has no integration_key (rule {rule.id})"
            )

        body = _build_event_body(rule, payload, routing_key)

        try:
            response = requests.post(
                _PAGERDUTY_EVENTS_URL,
                json=body,
                timeout=_DEFAULT_TIMEOUT_SECONDS,
                headers={"User-Agent": "Meshant-DQAlerter/1.0"},
            )
        except requests.exceptions.Timeout as exc:
            return DeliveryResult(
                success=False,
                error=f"timeout: {exc}",
                metadata={"transient": True},
            )
        except requests.exceptions.RequestException as exc:
            return DeliveryResult(
                success=False,
                error=f"network_error: {exc}",
                metadata={"transient": True},
            )

        # PagerDuty returns 202 on enqueue success, plus an envelope
        # containing ``status``, ``message``, ``dedup_key``.
        try:
            envelope = response.json()
        except ValueError:
            envelope = {}

        # 202 = accepted (the canonical success response).
        if response.status_code == 202 and envelope.get("status") == "success":
            return DeliveryResult(
                success=True,
                delivery_id=envelope.get("dedup_key", ""),
                metadata={
                    "http_status": 202,
                    "message": envelope.get("message", ""),
                    "incident_key": envelope.get("dedup_key", ""),
                },
            )

        # 400 = invalid event format → unrecoverable.
        if response.status_code == 400:
            raise AlertDeliveryError(
                f"pagerduty rejected event "
                f"(body={response.text[:200]}, errors={envelope.get('errors')})"
            )

        # 401/403 = bad routing_key → unrecoverable.
        if response.status_code in (401, 403):
            raise AlertDeliveryError(f"pagerduty auth failed (status={response.status_code})")

        # 429 = rate limited; transient — let breaker / dispatcher retry.
        # 5xx = pagerduty outage; transient.
        return DeliveryResult(
            success=False,
            error=(
                f"pagerduty_unexpected: status={response.status_code} body={response.text[:200]}"
            ),
            metadata={
                "http_status": response.status_code,
                "transient": True,
            },
        )


def _build_event_body(
    rule,
    payload: dict[str, Any],
    routing_key: str,
) -> dict[str, Any]:
    """Assemble the PagerDuty Events v2 body.

    See https://developer.pagerduty.com/docs/events-api-v2/trigger-events/
    """
    severity = payload.get("severity", "MEDIUM")
    pd_severity = _SEVERITY_MAP.get(severity, "warning")

    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        # ``dedup_key`` makes PagerDuty fold repeat alerts. Tying it to
        # the deterministic alert_id means a stuck condition becomes a
        # single incident with rising note count instead of N pages.
        "dedup_key": payload.get("alert_id", str(rule.id)),
        "payload": {
            "summary": payload.get("message") or f"DQ alert: {payload.get('rule_name', rule.name)}",
            "source": payload.get("source", "meshant-dq"),
            "severity": pd_severity,
            "component": payload.get("metric_type", rule.metric_type),
            "group": "data-quality",
            "class": payload.get("severity", "MEDIUM"),
            "custom_details": {
                "rule_id": str(rule.id),
                "rule_name": payload.get("rule_name") or rule.name,
                "metric_type": payload.get(
                    "metric_type",
                    rule.metric_type,
                ),
                "comparison_operator": payload.get(
                    "comparison_operator",
                    rule.comparison_operator,
                ),
                "threshold": payload.get("threshold", rule.threshold),
                "metric_value": payload.get("metric_value"),
                "dq_run_id": payload.get("dq_run_id"),
                "asset_id": payload.get("asset_id"),
                "dataset_id": payload.get("dataset_id"),
                "tenant_id": str(rule.tenant_id),
                "alert_id": payload.get("alert_id"),
                "triggered_at": payload.get("triggered_at"),
            },
        },
    }
