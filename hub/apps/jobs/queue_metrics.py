"""
Phase 277.B.071 — RQ queue depth Prometheus metric emitter.

Reads the current length of each RQ queue from Redis and reports it
as a Prometheus gauge via ``rq_queue_depth``.  Intended to be called
periodically (e.g. by a management command, a cron job, or a worker
heartbeat).

Usage:
    from hub.apps.jobs.queue_metrics import emit_rq_queue_depth
    emit_rq_queue_depth()
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_redis_connection():
    """Return a Redis connection for the RQ queue backend."""
    import redis

    raw_url = settings.REDIS_QUEUE_URL
    return redis.Redis.from_url(raw_url, decode_responses=False)


def emit_rq_queue_depth() -> dict[str, int]:
    """Sample RQ queue depths from Redis and report to Prometheus.

    Reads the length of every configured queue from the ``RQ_QUEUES``
    setting.  Also reports deferred, started, finished, and failed
    registry sizes when available.

    Returns a dict of ``{queue_name: count}`` for testability.

    Best-effort: a Redis connection failure is logged at WARNING and
    the function returns an empty dict — the gauge is NOT updated.
    """
    from hub.apps.observability.otel_metrics import rq_queue_depth as _metric

    counts: dict[str, int] = {}

    try:
        redis_conn = _get_redis_connection()
    except Exception as exc:
        logger.warning(
            "rq_queue_depth_redis_connect_failed",
            extra={"error": str(exc)},
        )
        return counts

    rq_queues = getattr(settings, "RQ_QUEUES", {})
    if not rq_queues:
        return counts

    try:
        for queue_name, queue_config in rq_queues.items():
            # RQ stores jobs under rq:queue:<name>
            redis_key = f"rq:queue:{queue_name}"
            try:
                count = redis_conn.llen(redis_key)
            except Exception:
                count = 0

            counts[queue_name] = count
            _metric.labels(queue_name=queue_name, status="queued").set(count)

            # Also report registry sizes (started, deferred, finished, failed)
            for registry in ("started", "deferred", "finished", "failed"):
                reg_key = f"rq:{registry}:{queue_name}"
                try:
                    reg_count = redis_conn.zcard(reg_key)
                except Exception:
                    reg_count = 0
                _metric.labels(queue_name=queue_name, status=registry).set(reg_count)

    except Exception:
        logger.exception("rq_queue_depth_emit_failed")
    finally:
        try:
            redis_conn.close()
        except Exception:
            pass

    if counts:
        logger.debug(
            "rq_queue_depth_emitted",
            extra={"queue_depths": counts},
        )

    return counts
