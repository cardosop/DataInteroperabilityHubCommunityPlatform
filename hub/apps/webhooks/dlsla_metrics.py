"""
Phase 277.B.099 — webhook DLQ gauge emitter.

Counts WebhookDelivery rows in DEAD_LETTER status per tenant and
sets the ``webhook_dlq_size`` gauge so Prometheus can alert when
undelivered webhooks accumulate silently.
"""

from __future__ import annotations

import logging

from django.db import utils as django_db_utils

logger = logging.getLogger(__name__)


def emit_webhook_dlq_metrics() -> dict[str, int]:
    """Count dead-lettered webhook deliveries per tenant and report to Prometheus.

    Returns a ``{tenant_id: count}`` dict for testability.
    Best-effort: metric emission failure is silently swallowed.
    """
    from django.db.models import Count

    from hub.apps.observability.otel_metrics import webhook_dlq_size
    from hub.apps.webhooks.models import DeliveryStatus, WebhookDelivery

    try:
        qs = (
            WebhookDelivery.objects.filter(status=DeliveryStatus.DEAD_LETTER)
            .values("webhook__tenant_id")
            .annotate(dlq_count=Count("id"))
            .order_by("-dlq_count")
        )
    except django_db_utils.DatabaseError:
        logger.exception("webhook_dlq_query_failed")
        return {}

    result: dict[str, int] = {}
    for row in qs:
        tid = str(row["webhook__tenant_id"] or "__platform__")
        count = row["dlq_count"]
        result[tid] = count
        try:
            webhook_dlq_size.labels(tenant_id=tid).set(count)
        except Exception:
            logger.debug("webhook_dlq_metric_emit_failed", extra={"tenant_id": tid})

    if result:
        logger.info(
            "webhook_dlq_metrics_emitted",
            extra={"total_dlq": sum(result.values()), "tenant_count": len(result)},
        )

    return result
