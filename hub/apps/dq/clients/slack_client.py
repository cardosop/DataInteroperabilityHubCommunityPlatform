"""
Phase 240.1.A.1 — DQ alert delivery to Slack via incoming webhooks.

Wire format
-----------
Slack incoming webhooks accept a JSON body with optional Block Kit
payload. We use a Block Kit message (header + section + context) so
the alert is readable in both desktop and mobile clients without
relying on the legacy ``attachments`` API.

Auth
----
The webhook URL itself is the credential; we send no Authorization
header. Per Slack docs, partial / malformed payloads return 400 +
text body. 5xx is the retry signal. Network errors / timeouts also
return ``success=False`` so the dispatcher schedules an RQ retry.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import AlertDeliveryError, BaseAlertClient, DeliveryResult

logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_SECONDS = 10
_SEVERITY_EMOJI = {
    "CRITICAL": ":rotating_light:",
    "HIGH": ":warning:",
    "MEDIUM": ":information_source:",
    "LOW": ":bulb:",
}


class SlackAlertClient(BaseAlertClient):
    """Slack delivery via incoming webhook (chat.postMessage shape)."""

    channel = "SLACK"

    def _deliver(self, rule, payload: dict[str, Any]) -> DeliveryResult:
        # Lazy import: keeps `requests` out of Django app-config import path.
        import requests

        config = rule.get_channel_config() or {}
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise AlertDeliveryError(f"SLACK channel config has no webhook_url (rule {rule.id})")

        body = _build_block_kit_message(rule, payload)

        try:
            response = requests.post(
                webhook_url,
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
            # ConnectionError, SSLError, etc. — treat as transient so
            # the breaker / dispatcher can retry.
            return DeliveryResult(
                success=False,
                error=f"network_error: {exc}",
                metadata={"transient": True},
            )

        # Slack webhook returns 200 + body "ok" on success, 4xx with
        # text reason on a malformed payload, 5xx on Slack outage.
        if response.status_code == 200:
            # Slack doesn't return a stable message id for incoming
            # webhooks; fall back to the response text (typically "ok")
            # so callers always have *some* delivery_id token to log.
            delivery_id = response.headers.get("X-Slack-Req-Id") or response.text.strip() or "ok"
            return DeliveryResult(
                success=True,
                delivery_id=delivery_id,
                metadata={"http_status": 200},
            )

        # 4xx → caller config bug; raise so we don't burn retry budget.
        if 400 <= response.status_code < 500:
            raise AlertDeliveryError(
                f"slack rejected payload "
                f"(status={response.status_code}, body={response.text[:200]})"
            )

        # 5xx → transient; let the breaker / dispatcher retry.
        return DeliveryResult(
            success=False,
            error=f"slack_5xx: status={response.status_code}",
            metadata={"http_status": response.status_code, "transient": True},
        )


def _build_block_kit_message(rule, payload: dict[str, Any]) -> dict[str, Any]:
    """Assemble a Block Kit message for the alert payload.

    Kept deterministic so tests can byte-compare against a snapshot —
    the dict insertion order matches the JSON order Slack expects.
    """
    severity = payload.get("severity", "UNKNOWN")
    emoji = _SEVERITY_EMOJI.get(severity, ":grey_question:")
    rule_name = payload.get("rule_name") or str(rule.id)

    return {
        "text": f"DQ Alert: {rule_name}",  # fallback for clients w/o Block Kit
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} DQ Alert: {rule_name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity*\n{severity}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": (f"*Metric*\n{payload.get('metric_type', '')}"),
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Threshold*\n"
                            f"{payload.get('comparison_operator', '')} "
                            f"{payload.get('threshold', '')}"
                        ),
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Actual*\n{payload.get('metric_value', '')}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_{payload.get('message', '')}_",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"alert_id `{payload.get('alert_id', '')}` · "
                            f"dq_run `{payload.get('dq_run_id', '')}` · "
                            f"{payload.get('triggered_at', '')}"
                        ),
                    }
                ],
            },
        ],
    }
