"""
Webhook Delivery RQ Tasks

Async delivery workers that decouple HTTP fan-out from the request thread.
Each task receives a WebhookDelivery PK, reloads it from the DB (so the
caller's transaction is already committed), and delegates to the existing
_attempt_delivery() synchronous path — preserving all retry/circuit-breaker
logic in one place (13.6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import structlog
from django_rq import job

logger = structlog.get_logger(__name__)

_T = TypeVar("_T")


def _run_with_tenant_context(
    tenant_id: str | None,
    func: Callable[[], _T],
) -> _T:
    """Run *func* inside ``tenant_context(tenant_id)`` when *tenant_id*
    is provided, or directly when it is ``None``.

    Worker/signal code that touches tenant-scoped models MUST use this
    helper so that RLS policies (which reference
    ``current_setting('app.current_tenant_id')``) can resolve rows.
    """
    if tenant_id is None:
        return func()
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(tenant_id):
        return func()


@job("default", timeout=120)
def deliver_webhook(delivery_id: str) -> None:
    """
    RQ task: attempt delivery for an existing WebhookDelivery record.

    Args:
        delivery_id: UUID string of the WebhookDelivery to deliver.
    """
    from .models import WebhookDelivery
    from .service import WebhookDeliveryService

    try:
        delivery = WebhookDelivery.objects.select_related("webhook").get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.error("webhook_delivery_not_found", delivery_id=delivery_id)
        return

    logger.info(
        "webhook_delivery_task_start",
        delivery_id=delivery_id,
        webhook_id=str(delivery.webhook_id),
        event_type=delivery.event_type,
    )

    try:
        WebhookDeliveryService._attempt_delivery(delivery)
    except Exception as exc:
        logger.error(
            "webhook_delivery_task_error",
            delivery_id=delivery_id,
            error=str(exc),
            exc_info=True,
        )
        raise  # Let RQ move the job to the failed queue for inspection
