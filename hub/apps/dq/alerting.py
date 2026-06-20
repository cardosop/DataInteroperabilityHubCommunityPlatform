"""
DQ Alerting

Configurable alerting rules for data quality metrics with threshold-based alerts.

Phase 240.1.A — delivery is no longer log-only stubs. ``_deliver_alert``
dispatches to per-channel clients (``hub.apps.dq.clients``) which return
structured ``DeliveryResult``s; a deterministic dedup window (D240.8)
short-circuits re-fires; failures schedule RQ retries with exponential
back-off and dead-letter to the ops PagerDuty after the budget is
exhausted (see ``hub.apps.dq.tasks``).
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

import structlog
from django.utils import timezone

from .models import DQAlertingRule, DQRun

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Dedup window (D240.8)
# ---------------------------------------------------------------------------
#
# Re-firing the SAME alert (same rule, same dq_run, same alert_type)
# inside a 24 h window is short-circuited so a stuck condition doesn't
# flood partners. Window is per-rule, persisted on
# ``DQAlertingRule.last_fired_at``.
DEDUP_WINDOW_HOURS: int = 24


def compute_alert_id(*, rule_id: str, run_id: str, alert_type: str) -> str:
    """Deterministic alert_id used by the dedup short-circuit.

    Mirrors the format pinned in D240.8::

        sha256(f"{rule_id}:{run_id}:{alert_type}").hexdigest()[:32]

    Same rule + same DQ run + same alert_type => same alert_id, so
    the dispatcher can compare against ``rule.last_alert_id`` and
    skip delivery within the dedup window.
    """
    raw = f"{rule_id}:{run_id}:{alert_type}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


class DQAlertingService:
    """
    Service for evaluating and triggering DQ alerting rules.
    """

    @staticmethod
    def evaluate_rules(dq_run: DQRun, metric_type: str = "quality_score") -> list[dict[str, Any]]:
        """
        Evaluate all applicable alerting rules for a DQ run.

        Args:
            dq_run: DQ run to evaluate
            metric_type: Type of metric to evaluate

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        # Get metric value
        metric_value = DQAlertingService._get_metric_value(dq_run, metric_type)
        if metric_value is None:
            return triggered_alerts

        # Get applicable rules
        rules = DQAlertingService._get_applicable_rules(dq_run, metric_type)

        # Evaluate each rule
        for rule in rules:
            if rule.evaluate(metric_value):
                alert = DQAlertingService._create_alert(rule, dq_run, metric_type, metric_value)
                triggered_alerts.append(alert)

                # Trigger alert delivery
                DQAlertingService._deliver_alert(alert, rule)

        return triggered_alerts

    @staticmethod
    def _get_metric_value(dq_run: DQRun, metric_type: str) -> float | None:
        """Get metric value from DQ run"""
        if metric_type == "quality_score":
            return dq_run.quality_score

        # Extract from details_json
        if dq_run.details_json and isinstance(dq_run.details_json, dict):
            return dq_run.details_json.get(metric_type)

        return None

    @staticmethod
    def _get_applicable_rules(dq_run: DQRun, metric_type: str) -> list[DQAlertingRule]:
        """Get applicable alerting rules"""
        # Get asset-specific and global rules
        rules_query = DQAlertingRule.objects.filter(
            tenant=dq_run.tenant, enabled=True, metric_type=metric_type
        )

        # Asset-specific rules
        if dq_run.asset:
            asset_rules = rules_query.filter(asset=dq_run.asset)
        else:
            asset_rules = DQAlertingRule.objects.none()

        # Global rules (no asset specified)
        global_rules = rules_query.filter(asset__isnull=True)

        # Combine and return
        return list(asset_rules) + list(global_rules)

    @staticmethod
    def _create_alert(
        rule: DQAlertingRule, dq_run: DQRun, metric_type: str, metric_value: float
    ) -> dict[str, Any]:
        """Create alert dictionary"""
        return {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "severity": rule.severity,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "threshold": rule.threshold,
            "comparison_operator": rule.comparison_operator,
            "dq_run_id": str(dq_run.id),
            "asset_id": str(dq_run.asset.id) if dq_run.asset else None,
            "dataset_id": str(dq_run.dataset.id) if dq_run.dataset else None,
            "triggered_at": timezone.now().isoformat(),
            "message": f"{rule.name}: {metric_type} {rule.comparison_operator} {rule.threshold} (actual: {metric_value})",
        }

    @staticmethod
    def _deliver_alert(
        alert: dict[str, Any],
        rule: DQAlertingRule,
    ) -> list[dict[str, Any]]:
        """Deliver alert through configured channels.

        Phase 240.1.A.2 / 240.1.A.4 — replaces the four log-only stubs.
        Each configured ``rule.alert_channels`` entry is dispatched to
        the matching client (``hub.apps.dq.clients``); the synchronous
        first attempt is made via
        ``hub.apps.dq.tasks.deliver_or_schedule_retry`` so all paths
        share the same audit + retry + dead-letter machinery.

        A 24 h dedup window short-circuits re-fires of the same alert
        (rule + run + type → same ``alert_id``) so a stuck condition
        cannot flood partners.

        Returns
        -------
        list[dict]
            One outcome dict per channel attempted (channel, success,
            delivery_id, next_action). Empty if the dedup window
            short-circuited delivery for every channel.
        """
        from hub.apps.dq.tasks import deliver_or_schedule_retry

        run_id = alert.get("dq_run_id") or ""
        alert_type = alert.get("metric_type") or "metric"
        alert_id = compute_alert_id(
            rule_id=str(rule.id),
            run_id=str(run_id),
            alert_type=alert_type,
        )
        # Decorate the payload with the dedup token so every client
        # sends the SAME alert_id to its partner (PagerDuty dedup_key,
        # webhook X-DQ-Delivery-Id-friendly, audit row correlation).
        payload = dict(alert)
        payload.setdefault("alert_id", alert_id)

        if DQAlertingService._is_within_dedup_window(rule, alert_id):
            logger.info(
                "dq_alert_dedup_short_circuit",
                rule_id=str(rule.id),
                alert_id=alert_id,
                last_alert_id=rule.last_alert_id,
                last_fired_at=(rule.last_fired_at.isoformat() if rule.last_fired_at else None),
            )
            return []

        outcomes: list[dict[str, Any]] = []
        # ``rule.alert_channels`` is a JSON list of channel strings;
        # dedupe in case a tenant double-listed a channel.
        seen: set = set()
        for channel in rule.alert_channels or []:
            if not isinstance(channel, str) or channel in seen:
                continue
            seen.add(channel)
            try:
                outcome = deliver_or_schedule_retry(
                    rule_id=str(rule.id),
                    channel=channel,
                    payload=payload,
                    attempt_number=1,
                )
            except Exception as exc:
                # The dispatcher itself should never raise; if it does
                # we still want to emit a failure audit + log so the
                # delivery doesn't silently disappear.
                logger.error(
                    "dq_alert_dispatcher_unexpected_error",
                    channel=channel,
                    rule_id=str(rule.id),
                    alert_id=alert_id,
                    error=str(exc),
                    exc_info=True,
                )
                outcome = {
                    "success": False,
                    "delivery_id": "",
                    "error": f"dispatcher_error: {exc}",
                    "attempt_number": 1,
                    "next_action": "none",
                }
            outcome["channel"] = channel
            outcomes.append(outcome)

        return outcomes

    @staticmethod
    def _is_within_dedup_window(
        rule: DQAlertingRule,
        alert_id: str,
    ) -> bool:
        """True if the same alert_id was delivered within the dedup window.

        The window is the constant ``DEDUP_WINDOW_HOURS`` (24 h per
        D240.8). Returns False if the rule has never fired (NULL
        ``last_alert_id`` / ``last_fired_at``) — that's the
        first-fire path and MUST always be delivered.
        """
        if not rule.last_alert_id or not rule.last_fired_at:
            return False
        if rule.last_alert_id != alert_id:
            return False
        cutoff = timezone.now() - timedelta(hours=DEDUP_WINDOW_HOURS)
        return rule.last_fired_at >= cutoff

    @staticmethod
    def get_alert_history(
        tenant_id: str, asset_id: str | None = None, rule_id: str | None = None, days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get alert history (stored alerts would be in a separate table in production).

        Args:
            tenant_id: Tenant UUID
            asset_id: Optional asset UUID
            rule_id: Optional rule UUID
            days: Number of days to look back

        Returns:
            List of alert history entries
        """
        # In production, this would query a DQAlertHistory model
        # For now, return empty list
        return []
