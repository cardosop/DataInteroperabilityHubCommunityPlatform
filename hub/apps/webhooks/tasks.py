"""
Webhook Delivery RQ Tasks

Async delivery workers that decouple HTTP fan-out from the request thread.
Each task receives a WebhookDelivery PK, reloads it from the DB (so the
caller's transaction is already committed), and delegates to the existing
_attempt_delivery() synchronous path — preserving all retry/circuit-breaker
logic in one place (13.6).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from django_rq import job

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


def _run_with_tenant_context[T](
    tenant_id: str | None,
    func: Callable[[], T],
) -> T:
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
def deliver_webhook(delivery_id: str, tenant_id: str | None = None) -> None:
    """
    RQ task: attempt delivery for an existing WebhookDelivery record.

    Args:
        delivery_id: UUID string of the WebhookDelivery to deliver.
        tenant_id: Tenant the delivery belongs to. Worker connections do
            not run inside a request, so tenant-scoped reads (the
            ``webhooks`` RLS policy applies to the ``select_related``
            join) must run inside ``tenant_context(tenant_id)`` — without
            it every delivery resolves to ``DoesNotExist`` under a
            RLS-enforcing DB role (staging/prod ``meshant_app``).
    """
    from .models import WebhookDelivery
    from .service import WebhookDeliveryService

    def _deliver() -> None:
        try:
            delivery = WebhookDelivery.objects.select_related("webhook").get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            logger.exception("webhook_delivery_not_found", delivery_id=delivery_id)
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

    _run_with_tenant_context(tenant_id, _deliver)
