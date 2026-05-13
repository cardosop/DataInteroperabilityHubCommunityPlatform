"""
Phase 277.B.075 — worker p99 latency + uptime metrics per RQ queue.

Provides:

* ``record_job_latency()`` — call at job completion to observe the
  elapsed wall-clock time in the ``job_queue_latency_seconds`` histogram.
* ``record_worker_uptime()`` — call periodically from a worker heartbeat
  to set the ``worker_uptime_seconds`` gauge.
* ``task_latency_tracker(queue_name)`` — context-manager/decorator that
  wraps a task function and records its latency on exit.

All functions are best-effort — a metric emission failure is silently
swallowed (the job must never fail because of telemetry).
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Callable

logger = logging.getLogger(__name__)


def record_job_latency(
    queue_name: str,
    job_type: str,
    duration_seconds: float,
    status: str = "COMPLETED",
) -> None:
    """Observe a job's wall-clock latency in the per-queue histogram.

    Args:
        queue_name: RQ queue name (e.g. ``job_default``).
        job_type: Job type string (e.g. ``WEBHOOK_DELIVERY``).
        duration_seconds: Elapsed wall-clock seconds.
        status: ``COMPLETED`` or ``FAILED``.
    """
    try:
        from hub.apps.observability.otel_metrics import job_queue_latency_seconds

        job_queue_latency_seconds.labels(
            queue_name=queue_name,
            job_type=job_type,
            status=status,
        ).observe(duration_seconds)
    except Exception:
        logger.debug(
            "job_latency_metric_emit_failed",
            extra={"queue_name": queue_name, "job_type": job_type},
        )


def record_worker_uptime(queue_name: str, uptime_seconds: float) -> None:
    """Set the worker uptime gauge for a given queue.

    Args:
        queue_name: RQ queue name.
        uptime_seconds: Seconds since the worker process started.
    """
    try:
        from hub.apps.observability.otel_metrics import worker_uptime_seconds

        worker_uptime_seconds.labels(queue_name=queue_name).set(uptime_seconds)
    except Exception:
        logger.debug(
            "worker_uptime_metric_emit_failed",
            extra={"queue_name": queue_name},
        )


@contextmanager
def task_latency_tracker(queue_name: str, job_type: str):
    """Context manager: record elapsed time on exit.

    Usage::

        with task_latency_tracker("job_default", "WEBHOOK_DELIVERY"):
            do_work()

    On exit, records the elapsed seconds in ``job_queue_latency_seconds``
    with status=``COMPLETED``.  If an exception propagates, records with
    status=``FAILED`` and re-raises.
    """
    started = time.monotonic()
    status = "COMPLETED"
    try:
        yield
    except Exception:
        status = "FAILED"
        raise
    finally:
        elapsed = time.monotonic() - started
        record_job_latency(queue_name, job_type, elapsed, status=status)
