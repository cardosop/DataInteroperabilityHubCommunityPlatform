"""
Phase 228 F4 (228.F4.12) — operator-driven DLQ replay.

Wraps :func:`openlineage_dlq_replay_sweep` for the operator's CLI.
The sweep itself is the canonical implementation; this command is
the operator entry-point + structured-output wrapper.

Usage::

    # Default — replay up to 100 rows:
    python manage.py replay_openlineage_dlq

    # Override max:
    python manage.py replay_openlineage_dlq --max=500

    # Dry-run (lists pending without firing replays):
    python manage.py replay_openlineage_dlq --dry-run
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand


DEFAULT_MAX = 100


class Command(BaseCommand):
    help = (
        "Phase 228 F4 (228.F4.12): replay pending OpenLineage DLQ "
        "rows. Bumps replay_attempts; marks permanently_failed=True "
        "after the 10th attempt."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max",
            type=int,
            default=DEFAULT_MAX,
            help=f"Max rows to replay in this run (default {DEFAULT_MAX}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List pending rows without firing replays.",
        )

    def handle(self, *_args, **options):
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        max_rows: int = options["max"]
        dry_run: bool = options["dry_run"]

        if dry_run:
            pending = OpenLineageDeadLetter.objects.filter(
                delivered_at__isnull=True,
                permanently_failed=False,
            ).order_by("created_at")[:max_rows]
            rows = [
                {
                    "id": str(r.id),
                    "tenant_id": str(r.tenant_id),
                    "event_id": r.event_id,
                    "attempts": r.attempts,
                    "replay_attempts": r.replay_attempts,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "failure_reason": r.failure_reason,
                }
                for r in pending
            ]
            self.stdout.write(json.dumps({
                "phase": "228.F4.12",
                "dry_run": True,
                "max_rows": max_rows,
                "pending_count": len(rows),
                "pending": rows,
            }, sort_keys=True))
            return

        # NOT a dry-run: invoke the sweep DIRECTLY (synchronous in
        # the operator's process). The decorator that turns it into
        # an RQ job is a no-op when called directly — which is what
        # we want for ops because the operator is watching stdout
        # for the result.
        result = openlineage_dlq_replay_sweep(max_rows=max_rows)
        self.stdout.write(json.dumps({
            "phase": "228.F4.12",
            "dry_run": False,
            "max_rows": max_rows,
            **result,
        }, sort_keys=True))
