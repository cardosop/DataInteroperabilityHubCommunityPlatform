"""
Phase 240.1.B audit-fix — sample DQ async queue depth.

The ``DQRunQueueDepth`` Prometheus alert (``> 100 pending for 30m``)
needs a real ``dq_async_queue_depth`` series.  RQ doesn't auto-export
queue depth as a metric, so this short-running management command
samples the queue length for each DQ-bearing queue and writes it to
the gauge.

Wired in production via ``helm/templates/cronjob/sample-dq-queue-depth.yaml``
which runs every 5 minutes.  The 5-minute cadence is half the alert's
30-minute ``for:`` window so the alert sees enough samples to confirm
a sustained breach.
"""
from __future__ import annotations

import logging
from typing import List

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# RQ queues that DQ jobs land on.  ``job_low`` is where the
# alert-redeliver path (Phase 240.1.A.5) lives; ``job_default`` is
# where the synchronous DQ-run dispatcher hands off long-running
# work.  Adding a queue is one-line — append the name here.
DEFAULT_DQ_QUEUES: List[str] = ["job_default", "job_low"]


class Command(BaseCommand):
    help = (
        "Sample RQ queue depth for the DQ-bearing queues and update "
        "the dq_async_queue_depth gauge."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--queues",
            nargs="+",
            default=None,
            help=(
                "Queue names to sample.  Defaults to "
                "['job_default', 'job_low']."
            ),
        )

    def handle(self, *args, **opts):
        queues = opts.get("queues") or DEFAULT_DQ_QUEUES

        try:
            from django_rq import get_queue
        except ImportError:  # pragma: no cover — django_rq is a hard dep
            self.stdout.write(self.style.ERROR(
                "django_rq not installed; cannot sample queue depth.",
            ))
            return

        try:
            from services.shared.metrics import dq_async_queue_depth
        except ImportError:
            self.stdout.write(self.style.ERROR(
                "services.shared.metrics not importable.",
            ))
            return

        total = 0
        per_queue: dict[str, int] = {}
        for qname in queues:
            try:
                q = get_queue(qname)
                # rq.Queue.count is the pending-job count.
                depth = int(q.count)
            except Exception as exc:  # noqa: BLE001 — fail-soft per-queue
                logger.warning(
                    "sample_dq_queue_depth_queue_failed queue=%s error=%s",
                    qname, exc,
                )
                continue
            per_queue[qname] = depth
            total += depth
            dq_async_queue_depth.labels(
                service="hub", queue=qname,
            ).set(depth)

        self.stdout.write(self.style.SUCCESS(
            f"Sampled DQ queue depth: total={total}, "
            f"per-queue={per_queue}"
        ))
