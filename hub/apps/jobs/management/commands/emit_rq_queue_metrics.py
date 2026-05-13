"""
Phase 277.B.071 — management command to sample RQ queue depths.

Usage:
    python manage.py emit_rq_queue_metrics
    python manage.py emit_rq_queue_metrics --loop 30     # Run every 30s

Intended to be run as a sidecar in the worker pod or as a Kubernetes
CronJob every 30 seconds to keep the ``rq_queue_depth`` gauge current.
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sample RQ queue depths from Redis and report to Prometheus."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            type=int,
            default=0,
            help="Run continuously with N seconds between samples (0 = run once).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress per-sample output.",
        )

    def handle(self, *args, **options):
        loop_interval = options["loop"]
        quiet = options["quiet"]

        from hub.apps.jobs.queue_metrics import emit_rq_queue_depth

        while True:
            counts = emit_rq_queue_depth()
            if not quiet:
                if counts:
                    self.stdout.write(
                        f"[rq_queue_depth] {', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}"
                    )
                else:
                    self.stdout.write("[rq_queue_depth] No queues configured or Redis unavailable")

            if loop_interval <= 0:
                break
            time.sleep(loop_interval)
