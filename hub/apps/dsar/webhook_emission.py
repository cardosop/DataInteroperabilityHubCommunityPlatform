"""Phase 232.2.12 — webhook fan-out for DSAR lifecycle."""

from __future__ import annotations
from typing import Any, Dict

import structlog

from hub.apps.dsar.models import DSARRequest
from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = structlog.get_logger(__name__)


def _payload(row: DSARRequest) -> Dict[str, Any]:
    return {
        "dsar_id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "status": row.status,
        "request_type": row.request_type,
        "public_reference_token": str(row.public_reference_token),
        "statutory_fulfil_deadline_utc": (
            row.statutory_fulfil_deadline_utc.isoformat()
            if row.statutory_fulfil_deadline_utc
            else None
        ),
    }


def publish_dsar_event(row: DSARRequest, event_type: WebhookEventType) -> int:
    try:
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=str(row.tenant_id),
            event_type=str(event_type),
            resource_type="DSAR_REQUEST",
            resource_id=str(row.id),
            event_data=_payload(row),
        )
    except Exception as exc:
        logger.exception(
            "dsar_webhook_trigger_failed",
            dsar_id=str(row.id),
            event_type=str(event_type),
            error=str(exc),
        )
        return 0
