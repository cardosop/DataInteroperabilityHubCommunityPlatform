"""
Phase 228 F4 (228.F4.9) — async tasks for the OpenLineage integration.

The spec calls for "Celery task ``openlineage_dlq_replay``", but the
project's queue framework is ``django_rq`` (see ADR-LIN-008). The
RQ-decorated task below is the canonical equivalent — same
fire-and-forget semantics, same retry-via-dispatcher pattern, same
operational visibility through ``django_rq``'s admin UI.

Two task entry points:

* :func:`send_openlineage_event_async` — fire-and-forget outbound
  emit. Wraps :class:`OpenLineageAdapter` so callers don't need to
  manage threading or retries.
* :func:`openlineage_dlq_replay_sweep` — scheduled / on-demand DLQ
  drain. Picks up un-delivered + non-permanently-failed rows,
  retries them via the adapter, marks ``permanently_failed=True``
  after the 10th replay attempt (per spec).
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


PERMANENT_FAIL_REPLAY_THRESHOLD = 10
"""Per spec: after 10 DLQ replay attempts, mark as permanently failed."""


def _job_decorator():
    """Return the ``@job`` decorator from ``django_rq`` if available,
    otherwise a no-op so the module imports in environments without
    the queue framework (test pre-discovery)."""
    try:
        from django_rq import job

        return job("default")
    except ImportError:

        def _passthrough(fn):
            return fn

        return _passthrough


@_job_decorator()
def send_openlineage_event_async(
    event: dict[str, Any],
    *,
    target_url: str | None = None,
    tenant_id: str | None = None,
) -> str:
    """Fire-and-forget outbound emit.

    Resolves ``tenant`` from ``tenant_id``, then calls
    :meth:`OpenLineageAdapter.deliver`. Returns the
    :class:`DeliveryOutcome` value as a string for queue introspection.
    """
    from hub.apps.integrations.openlineage.adapter import OpenLineageAdapter
    from hub.apps.tenants.models import Tenant

    if not tenant_id:
        logger.warning("openlineage_async_missing_tenant_id")
        return "skipped:no_tenant"
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        logger.warning(
            "openlineage_async_tenant_not_found",
            extra={"tenant_id": str(tenant_id)},
        )
        return "skipped:tenant_not_found"

    url = target_url or getattr(settings, "OPENLINEAGE_URL", None)
    if not url:
        logger.warning("openlineage_async_no_target_url")
        return "skipped:no_target_url"

    outcome = OpenLineageAdapter().deliver(
        event=event,
        target_url=url,
        tenant=tenant,
    )
    return str(outcome)


_DLQ_RETRY_BACKOFF_SECONDS = (60, 120, 240, 480, 960, 1800, 3600, 7200, 14400, 28800)
"""Per-attempt backoff for DLQ replay scheduling. ``next_retry_at`` is
set to ``NOW() + backoff[replay_attempts-1]`` after a failed replay
so subsequent sweeps don't busy-loop a known-failing row."""


def _record_dlq_depth_metric() -> None:
    """Phase 228 F4 (REQ-LIN-F4-004 / DoD self-audit GAP-D10) — emit
    ``openlineage_dlq_depth{permanently_failed}`` for the dlq-depth
    scrape. Best-effort: a metrics-emit error must not fail the
    sweep."""
    try:
        from hub.apps.observability.metrics import openlineage_dlq_depth
    except ImportError:
        return
    try:
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )

        pending = OpenLineageDeadLetter.objects.filter(
            delivered_at__isnull=True,
            permanently_failed=False,
        ).count()
        permafail = OpenLineageDeadLetter.objects.filter(
            permanently_failed=True,
        ).count()
        openlineage_dlq_depth.labels(permanently_failed="false").inc(pending)
        openlineage_dlq_depth.labels(permanently_failed="true").inc(permafail)
    except (ImportError, AttributeError, ValueError, TypeError, OSError):
        logger.debug("openlineage_dlq_depth_emit_failed")


@_job_decorator()
def openlineage_dlq_replay_sweep(*, max_rows: int = 100) -> dict[str, int]:
    """Drain the DLQ — replay un-delivered, non-permanently-failed
    rows. Returns ``{processed, replayed_ok, replayed_dead, permanently_failed_now}``.

    Idempotent: a same-state rerun skips already-delivered rows
    (``delivered_at IS NOT NULL``) and already-permanently-failed
    rows (``permanently_failed=True``).

    Phase 228 F4 (DoD self-audit GAP-D9) — also filters
    ``next_retry_at IS NULL OR next_retry_at <= NOW()`` so a row
    that just failed a replay isn't immediately re-tried. The next
    retry timestamp is set to ``NOW() + backoff[replay_attempts]``
    after every failed replay (the backoff schedule is internal to
    this module — ramp from 1 min to 8 h).

    Phase 228 F4 (DoD self-audit GAP-D10) — emits
    ``openlineage_dlq_depth`` after the sweep so Prometheus has the
    post-sweep depth on every scrape.
    """
    from datetime import timedelta

    from django.db.models import Q

    from hub.apps.integrations.openlineage.adapter import (
        DeliveryOutcome,
        OpenLineageAdapter,
    )
    from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter

    adapter = OpenLineageAdapter()
    now = timezone.now()
    pending = (
        OpenLineageDeadLetter.objects.filter(
            delivered_at__isnull=True,
            permanently_failed=False,
        )
        .filter(
            Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now),
        )
        .order_by("created_at")[:max_rows]
    )

    processed = 0
    replayed_ok = 0
    replayed_dead = 0
    permanently_failed_now = 0

    for row in pending:
        processed += 1
        # Decrypt + retry. Failures during decrypt are skipped — the
        # row is poisoned, ops investigates manually.
        try:
            event = row.event_payload
        except Exception as exc:
            logger.exception(
                "openlineage_dlq_decrypt_failed",
                extra={"dlq_id": str(row.id), "error": str(exc)},
            )
            continue

        outcome = adapter.deliver(
            event=event,
            target_url=row.target_url,
            tenant=row.tenant,
        )
        # Bump replay counter regardless of outcome.
        row.replay_attempts += 1
        row.last_replay_at = timezone.now()

        if outcome == DeliveryOutcome.DELIVERED:
            # Phase 228 F4 (REQ-LIN-F4-004 spec scenario "DLQ retry
            # succeeds") — the spec says "the row is deleted" on
            # successful replay. We honour that literally: the DLQ
            # is the queue of "currently failing" rows, so a
            # successfully redelivered row no longer belongs there.
            # The original dead-letter event is preserved in the
            # ``openlineage_adapter_dlq`` warning logged at the time
            # of the original DLQ insert, so the audit trail is not
            # lost by deletion.
            row_id = row.id
            row.delete()
            replayed_ok += 1
            logger.info(
                "openlineage_dlq_replayed_and_deleted",
                extra={"dlq_id": str(row_id)},
            )
            continue

        replayed_dead += 1
        if row.replay_attempts >= PERMANENT_FAIL_REPLAY_THRESHOLD:
            row.permanently_failed = True
            row.next_retry_at = None
            permanently_failed_now += 1
        else:
            # Schedule the next retry — bounded ramp.
            idx = min(
                row.replay_attempts - 1,
                len(_DLQ_RETRY_BACKOFF_SECONDS) - 1,
            )
            row.next_retry_at = timezone.now() + timedelta(
                seconds=_DLQ_RETRY_BACKOFF_SECONDS[idx],
            )

        row.save(
            update_fields=[
                "replay_attempts",
                "last_replay_at",
                "permanently_failed",
                "next_retry_at",
            ]
        )

    # Emit the depth gauge AFTER the sweep so Prometheus sees the
    # post-sweep state.
    _record_dlq_depth_metric()

    return {
        "processed": processed,
        "replayed_ok": replayed_ok,
        "replayed_dead": replayed_dead,
        "permanently_failed_now": permanently_failed_now,
    }


__all__ = [
    "PERMANENT_FAIL_REPLAY_THRESHOLD",
    "openlineage_dlq_replay_sweep",
    "send_openlineage_event_async",
]
