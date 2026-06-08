"""Phase 232.1 — tenant webhooks for consent lifecycle."""

from __future__ import annotations
from typing import Any, Dict

import structlog

from hub.apps.consent.models import ConsentRecord
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = structlog.get_logger(__name__)


def _scrub_record_payload(record: ConsentRecord) -> Dict[str, Any]:
    return {
        "record_id": str(record.id),
        "tenant_id": str(record.tenant_id),
        "user_id": str(record.user_id),
        "purpose_id": str(record.purpose_id),
        "purpose_key": record.purpose.key,
        "status": record.status,
        "granted_at": record.granted_at.isoformat() if record.granted_at else None,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        "event_id": str(record.id),
    }


def publish_consent_granted(record: ConsentRecord) -> int:
    """Fan-out ``consent.granted`` to active webhook subscriptions."""
    try:
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=str(record.tenant_id),
            event_type=str(WebhookEventType.CONSENT_GRANTED),
            resource_type="CONSENT_RECORD",
            resource_id=str(record.id),
            event_data=_scrub_record_payload(record),
        )
    except Exception as exc:
        logger.exception(
            "consent_granted_webhook_trigger_failed",
            record_id=str(record.id),
            tenant_id=str(record.tenant_id),
            error=str(exc),
        )
        return 0


def publish_consent_revoked(record: ConsentRecord) -> int:
    """Fan-out ``consent.revoked`` to active webhook subscriptions."""
    try:
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=str(record.tenant_id),
            event_type=str(WebhookEventType.CONSENT_REVOKED),
            resource_type="CONSENT_RECORD",
            resource_id=str(record.id),
            event_data=_scrub_record_payload(record),
        )
    except Exception as exc:
        logger.exception(
            "consent_revoked_webhook_trigger_failed",
            record_id=str(record.id),
            tenant_id=str(record.tenant_id),
            error=str(exc),
        )
        return 0
