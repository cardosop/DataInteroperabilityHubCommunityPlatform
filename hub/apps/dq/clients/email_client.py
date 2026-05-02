"""
Phase 240.1.A.1 — DQ alert delivery over email.

Reuses the project-wide email service (``hub.apps.notifications.services.
get_email_service``) so the SendGrid / SMTP / SES backends are
configured in exactly one place. Each recipient receives a separate
message — a single multi-recipient send would mask per-recipient
failures behind a single result.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..log_helpers import _redact
from .base import AlertDeliveryError, BaseAlertClient, DeliveryResult


logger = logging.getLogger(__name__)


_SUBJECT_TEMPLATE = "[DQ Alert][{severity}] {rule_name}"

_TEXT_TEMPLATE = (
    "DQ alerting rule '{rule_name}' fired.\n\n"
    "Severity:    {severity}\n"
    "Metric:      {metric_type}\n"
    "Threshold:   {comparison_operator} {threshold}\n"
    "Actual:      {metric_value}\n"
    "DQ Run ID:   {dq_run_id}\n"
    "Alert ID:    {alert_id}\n"
    "Triggered:   {triggered_at}\n\n"
    "{message}\n"
)

_HTML_TEMPLATE = (
    "<p>DQ alerting rule <strong>{rule_name}</strong> fired.</p>"
    "<table>"
    "<tr><td><b>Severity</b></td><td>{severity}</td></tr>"
    "<tr><td><b>Metric</b></td><td>{metric_type}</td></tr>"
    "<tr><td><b>Threshold</b></td><td>{comparison_operator} {threshold}</td></tr>"
    "<tr><td><b>Actual</b></td><td>{metric_value}</td></tr>"
    "<tr><td><b>DQ Run ID</b></td><td><code>{dq_run_id}</code></td></tr>"
    "<tr><td><b>Alert ID</b></td><td><code>{alert_id}</code></td></tr>"
    "<tr><td><b>Triggered</b></td><td>{triggered_at}</td></tr>"
    "</table>"
    "<p>{message}</p>"
)


class EmailAlertClient(BaseAlertClient):
    """Email delivery via the shared notification email service."""

    channel = "EMAIL"

    def _deliver(self, rule, payload: Dict[str, Any]) -> DeliveryResult:
        config = rule.get_channel_config() or {}
        emails: List[str] = list(config.get("emails") or [])
        if not emails:
            # Mis-configured rule — recipients were never set. Don't
            # waste retry budget; surface as unrecoverable.
            raise AlertDeliveryError(
                f"EMAIL channel config has no recipients (rule {rule.id})"
            )

        # Lazy import — keeps Django app-config-time imports lean and
        # lets tests patch the factory at the boundary.
        from hub.apps.notifications.services import (
            EmailServiceError,
            get_email_service,
        )

        try:
            service = get_email_service()
        except EmailServiceError as exc:
            # Mis-configured EMAIL_BACKEND — retry won't help.
            raise AlertDeliveryError(
                f"email service unavailable: {exc}"
            ) from exc

        subject = _SUBJECT_TEMPLATE.format(
            severity=payload.get("severity", "UNKNOWN"),
            rule_name=payload.get("rule_name", str(rule.id)),
        )
        text_body = _TEXT_TEMPLATE.format(**_render_context(payload, rule))
        html_body = _HTML_TEMPLATE.format(**_render_context(payload, rule))

        delivered_to: List[str] = []
        last_message_id = ""
        last_error = None
        for email in emails:
            try:
                result = service.send_email(
                    to_email=email,
                    subject=subject,
                    html_content=html_body,
                    text_content=text_body,
                )
            except Exception as exc:  # noqa: BLE001 — boundary exception
                last_error = str(exc)
                logger.warning(
                    "dq_alert_email_send_failed",
                    extra=_redact({
                        "rule_id": str(rule.id),
                        "alert_id": payload.get("alert_id"),
                        "to_email_redacted": _redact_email(email),
                        "error": last_error,
                    }),
                )
                continue

            if not result or not result.get("success"):
                last_error = (result or {}).get("error") or "send_email_returned_falsy"
                logger.warning(
                    "dq_alert_email_send_failed_result",
                    extra=_redact({
                        "rule_id": str(rule.id),
                        "alert_id": payload.get("alert_id"),
                        "to_email_redacted": _redact_email(email),
                        "result": result,
                    }),
                )
                continue

            delivered_to.append(email)
            last_message_id = (
                result.get("message_id")
                or result.get("delivery_id")
                or last_message_id
            )

        if not delivered_to:
            # All recipients failed — this is a transient failure
            # (SMTP outage, SendGrid 5xx, network blip). Mark
            # ``transient=True`` so ``BaseAlertClient.deliver`` re-
            # raises and the circuit breaker counts it. Without this
            # flag the breaker would never open on an extended SMTP
            # outage and we'd burn the entire RQ retry budget for
            # every alert.
            return DeliveryResult(
                success=False,
                error=last_error or "no recipients accepted",
                metadata={
                    "recipient_count": len(emails),
                    "transient": True,
                },
            )

        return DeliveryResult(
            success=True,
            delivery_id=last_message_id,
            metadata={
                "delivered_to_count": len(delivered_to),
                "recipient_count": len(emails),
                "partial": len(delivered_to) < len(emails),
            },
        )


def _render_context(payload: Dict[str, Any], rule) -> Dict[str, Any]:
    """Build the template context with safe defaults.

    Missing keys from ``payload`` are coerced to empty strings so the
    f-string-style templates above never KeyError on a partial alert.
    """
    return {
        "rule_name": payload.get("rule_name") or str(rule.id),
        "severity": payload.get("severity") or rule.severity,
        "metric_type": payload.get("metric_type") or rule.metric_type,
        "comparison_operator": (
            payload.get("comparison_operator") or rule.comparison_operator
        ),
        "threshold": payload.get("threshold") or rule.threshold,
        "metric_value": payload.get("metric_value", ""),
        "dq_run_id": payload.get("dq_run_id", ""),
        "alert_id": payload.get("alert_id", ""),
        "triggered_at": payload.get("triggered_at", ""),
        "message": payload.get("message", ""),
    }


def _redact_email(email: str) -> str:
    """Redact local-part for log lines so PII doesn't leak.

    Mirrors the convention used by ``hub.apps.audit.utils.redact_string``
    so log + audit redaction stay aligned.
    """
    if "@" not in email:
        return "[REDACTED]"
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"
