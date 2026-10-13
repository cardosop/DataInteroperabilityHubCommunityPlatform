"""Databricks job-fleet webhook seam (openspec add-databricks-jobs task 4.5).

``notify_job_run_failed`` is the BEST-EFFORT seam the 4.4 poller calls
when a run reaches a terminal FAILED state (D5): it fans the event out
through the production ``WebhookDeliveryService`` to every webhook the
tenant subscribed to ``databricks.job.run.failed``. A delivery outage or
a malformed caller input NEVER blocks the terminal transition — every
failure is swallowed with a log record and the call reports how many
webhooks were triggered (0 on any failure).
"""

from __future__ import annotations

import logging

from hub.apps.webhooks.models import WebhookEventType
from hub.apps.webhooks.service import WebhookDeliveryService

logger = logging.getLogger(__name__)


def notify_job_run_failed(
    *,
    tenant_id: str,
    workspace_id: str,
    job_id: str,
    run_id: str,
    result_state: str,
    error_message: str | None,
) -> int:
    """Fan a terminal run failure out to subscribed webhooks.

    Returns the number of webhooks triggered — 0 when nothing is
    subscribed OR the delivery service failed (best-effort by contract:
    the caller's terminal transition proceeds regardless).
    """
    try:
        return WebhookDeliveryService.trigger_webhook(
            tenant_id=tenant_id,
            event_type=str(WebhookEventType.DATABRICKS_JOB_RUN_FAILED),
            resource_type="DATABRICKS_JOB_RUN",
            resource_id=run_id,
            event_data={
                "workspace_id": workspace_id,
                "job_id": job_id,
                "run_id": run_id,
                "result_state": result_state,
                "error_message": error_message,
            },
        )
    except Exception:
        logger.exception(
            "databricks_job_run_failed_webhook_trigger_failed",
            extra={
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "job_id": job_id,
                "run_id": run_id,
            },
        )
        return 0
