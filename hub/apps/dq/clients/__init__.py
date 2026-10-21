"""
Phase 240.1.A.1 — DQ alert delivery clients.

Each channel (EMAIL / SLACK / WEBHOOK / PAGERDUTY) has its own
``BaseAlertClient`` subclass exposing a single ``deliver(rule, payload)``
method that returns a ``DeliveryResult``. The dispatcher
(``hub.apps.dq.alerting._deliver_alert``) routes to the right client
based on ``rule.channel`` / ``rule.alert_channels``.

Wire-protocol decisions are pinned per-channel in their respective
modules (see ``slack_client.py`` for the Block Kit shape, etc.). The
base class lives in ``base.py``; this package's ``__init__`` re-exports
the public surface.
"""

from __future__ import annotations

from .base import (
    AlertDeliveryError,
    BaseAlertClient,
    DeliveryResult,
    get_client_for_channel,
)
from .email_client import EmailAlertClient
from .pagerduty_client import PagerDutyAlertClient
from .slack_client import SlackAlertClient
from .webhook_client import WebhookAlertClient

__all__ = [
    "AlertDeliveryError",
    "BaseAlertClient",
    "DeliveryResult",
    "EmailAlertClient",
    "PagerDutyAlertClient",
    "SlackAlertClient",
    "WebhookAlertClient",
    "get_client_for_channel",
]
