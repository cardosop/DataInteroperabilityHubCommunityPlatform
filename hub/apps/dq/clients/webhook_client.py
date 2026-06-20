"""
Phase 240.1.A.1 — DQ alert delivery to a generic HTTP webhook.

Wire format
-----------
JSON body containing the full alert payload. The receiver decides
how to handle it. For tenants that need authenticated webhook receivers
the channel_config can supply ``headers`` (a dict of header name →
value pairs); we forward those untouched (capped at 32 to stop
runaway configs).

Auth
----
By convention a tenant-supplied ``Authorization`` header is the
caller's responsibility. For HMAC-signed deliveries (the dominant
production pattern) we ALSO compute an ``X-DQ-Signature`` header when
the channel_config supplies a ``hmac_secret`` — this matches the
project-wide webhook delivery convention used in
``hub.apps.webhooks.service_client``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from typing import Any

from ..log_helpers import _redact
from .base import AlertDeliveryError, BaseAlertClient, DeliveryResult

logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_SECONDS = 10

# Bound forwarded header counts to prevent a misconfigured rule from
# blowing up the request line.
_MAX_FORWARDED_HEADERS = 32

# Header names: RFC 7230 token chars only. Block CR/LF / spaces / etc.
_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$")


class WebhookAlertClient(BaseAlertClient):
    """Generic HTTP webhook delivery."""

    channel = "WEBHOOK"

    def _deliver(self, rule, payload: dict[str, Any]) -> DeliveryResult:
        import requests  # lazy import — see slack_client

        config = rule.get_channel_config() or {}
        webhook_url = config.get("url") or config.get("webhook_url")
        if not webhook_url:
            raise AlertDeliveryError(f"WEBHOOK channel config has no url (rule {rule.id})")

        body = json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
        headers = _build_headers(config, body)

        try:
            response = requests.post(
                webhook_url,
                data=body,
                headers=headers,
                timeout=_DEFAULT_TIMEOUT_SECONDS,
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

        # 2xx success — accept any 2xx since some receivers return 202.
        if 200 <= response.status_code < 300:
            delivery_id = (
                response.headers.get("X-Request-Id")
                or response.headers.get("X-Delivery-Id")
                or headers.get("X-DQ-Delivery-Id", "")
            )
            return DeliveryResult(
                success=True,
                delivery_id=delivery_id,
                metadata={"http_status": response.status_code},
            )

        # 4xx → caller payload / config bug; don't waste retry budget.
        if 400 <= response.status_code < 500:
            raise AlertDeliveryError(
                f"webhook rejected (status={response.status_code}, body={response.text[:200]})"
            )

        # 5xx → transient.
        return DeliveryResult(
            success=False,
            error=f"webhook_5xx: status={response.status_code}",
            metadata={"http_status": response.status_code, "transient": True},
        )


# ---------------------------------------------------------------------------
# Header / signature helpers
# ---------------------------------------------------------------------------


def _build_headers(config: dict[str, Any], body_bytes: bytes) -> dict[str, str]:
    """Build the outgoing header set: defaults + tenant-supplied + sig.

    Order of precedence (last wins):
        1. defaults (Content-Type, User-Agent, X-DQ-Delivery-Id)
        2. tenant-supplied ``headers`` dict (filtered for valid names)
        3. computed HMAC signature when ``hmac_secret`` is set —
           tenant cannot override these.
    """
    delivery_id = uuid.uuid4().hex
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Meshant-DQAlerter/1.0",
        "X-DQ-Delivery-Id": delivery_id,
    }

    extra = config.get("headers") or {}
    if isinstance(extra, dict):
        for i, (name, value) in enumerate(extra.items()):
            if i >= _MAX_FORWARDED_HEADERS:
                logger.warning(
                    "dq_alert_webhook_headers_truncated",
                    extra=_redact({"limit": _MAX_FORWARDED_HEADERS}),
                )
                break
            # ``name`` is a reserved attribute on ``LogRecord``, so passing
            # it via ``extra=`` raises KeyError("Attempt to overwrite
            # 'name' in LogRecord"). Use ``header_name`` instead.
            if not isinstance(name, str) or not _HEADER_NAME_RE.match(name):
                logger.warning(
                    "dq_alert_webhook_header_name_invalid",
                    extra=_redact({"header_name": str(name)[:64]}),
                )
                continue
            if not isinstance(value, str):
                value = str(value)
            # Reject CR/LF in header values (header injection).
            if "\r" in value or "\n" in value:
                logger.warning(
                    "dq_alert_webhook_header_value_rejected",
                    extra=_redact({"header_name": name}),
                )
                continue
            headers[name] = value

    # HMAC-SHA256 signature if secret is configured. Reserved headers —
    # tenant-supplied values for these are overwritten.
    secret = config.get("hmac_secret")
    if isinstance(secret, str) and secret:
        sig, ts = _compute_hmac(secret, body_bytes)
        headers["X-DQ-Signature"] = sig
        headers["X-DQ-Signature-Timestamp"] = ts

    return headers


def _compute_hmac(secret: str, body_bytes: bytes) -> tuple[str, str]:
    """Compute the (signature, timestamp) tuple used by webhook receivers.

    Format mirrors the project-wide webhook signing convention
    (timestamp.body) so receivers that already verify
    ``hub.apps.webhooks`` deliveries don't need a second code path.
    """
    import time

    ts = str(int(time.time()))
    payload = f"{ts}.".encode() + body_bytes
    digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}", ts
