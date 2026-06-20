"""
Phase 72.4 — Retry failed DLQ sync for scheduled ingestion runs.

Finds runs where dlq_sync_status == "FAILED" (older than 1 hour)
and re-attempts the DLQ sync.
"""

from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Retry DLQ sync for scheduled ingestion runs that failed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--cooldown-hours", type=int, default=1)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(hours=options["cooldown_hours"])

        runs = ScheduledIngestionRun.objects.filter(
            dlq_sync_status="FAILED",
            updated_at__lt=cutoff,
        ).select_related("scheduled_ingestion")[:50]

        retried = 0
        failed = 0

        for run in runs:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would retry DLQ sync for run {run.id}")
                retried += 1
                continue

            try:
                from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager

                DeadLetterQueueManager.sync_from_ingestion_state(str(run.scheduled_ingestion_id))
                run.dlq_sync_status = "SYNCED"
                run.save(update_fields=["dlq_sync_status", "updated_at"])
                retried += 1
                logger.info("dlq_sync_retry_success", run_id=str(run.id))
            except Exception as exc:
                failed += 1
                logger.warning("dlq_sync_retry_failed", run_id=str(run.id), error=str(exc))

        self.stdout.write(f"DLQ sync retry: {retried} retried, {failed} failed")
