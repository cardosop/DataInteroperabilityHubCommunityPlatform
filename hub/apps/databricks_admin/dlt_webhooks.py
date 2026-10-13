"""Databricks DLT pipeline webhook seam (openspec
add-databricks-dlt-pipelines task 10.6).

``notify_dlt_update_failed`` is the BEST-EFFORT seam the terminal
transition calls when an update reaches a terminal FAILED state (design
D6): it fans the event out through the production
``WebhookDeliveryService`` to every webhook the tenant subscribed to
``databricks.dlt.update.failed``. A delivery outage or a malformed
caller input NEVER blocks the terminal transition — every failure is
swallowed with a log record and the call reports how many webhooks were
triggered (0 on any failure).
"""

from __future__ import annotations

import logging

from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = logging.getLogger(__name__)


def notify_dlt_update_failed(
    *,
    tenant_id: str,
    workspace_id: str,
    pipeline_id: str,
    update_id: str,
    state: str,
    error_message: str | None,
) -> int:
    """Fan a terminal update failure out to subscribed webhooks.

    Returns the number of webhooks triggered — 0 when nothing is
    subscribed OR the delivery service failed (best-effort by contract:
    the caller's terminal transition proceeds regardless).
    """
    try:
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=tenant_id,
            event_type=str(WebhookEventType.DATABRICKS_DLT_UPDATE_FAILED),
            resource_type="DATABRICKS_DLT_PIPELINE_UPDATE",
            resource_id=update_id,
            event_data={
                "workspace_id": workspace_id,
                "pipeline_id": pipeline_id,
                "update_id": update_id,
                "state": state,
                "error_message": error_message,
            },
        )
    except Exception:
        logger.exception(
            "databricks_dlt_update_failed_webhook_trigger_failed",
            extra={
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "pipeline_id": pipeline_id,
                "update_id": update_id,
            },
        )
        return 0
