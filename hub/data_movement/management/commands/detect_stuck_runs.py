"""
285.6.4.4 — Detect stuck dlt pipeline runs.

Queries _dlt_loads (PostgreSQL dlt state tables) and ScheduledExportRun
(filesystem-based exports) to identify runs stuck in RUNNING state beyond
their timeout window.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "285.6.4.4 — Detect stuck dlt pipeline runs"

    def add_arguments(self, parser):
        parser.add_argument("--timeout-hours", type=int, default=24, help="Max hours before a run is considered stuck")
        parser.add_argument("--dry-run", action="store_true", help="Report only, no modifications")
        parser.add_argument("--direction", choices=["ingestion", "export", "both"], default="both")

    def handle(self, **options):
        timeout_hours = options["timeout_hours"]
        dry_run = options["dry_run"]
        direction = options["direction"]
        cutoff = timezone.now() - timedelta(hours=timeout_hours)

        stuck_count = 0

        if direction in ("ingestion", "both"):
            stuck_count += self._check_ingestion(cutoff, dry_run)
        if direction in ("export", "both"):
            stuck_count += self._check_export(cutoff, dry_run)

        if stuck_count == 0:
            self.stdout.write(self.style.SUCCESS(f"No stuck runs found (timeout: {timeout_hours}h)"))
        else:
            self.stdout.write(self.style.WARNING(f"Found {stuck_count} stuck run(s)"))

    def _check_ingestion(self, cutoff, dry_run: bool) -> int:
        from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun
        stuck = ScheduledIngestionRun.objects.filter(
            status="RUNNING",
            started_at__lt=cutoff,
        )
        count = stuck.count()
        for run in stuck:
            self.stdout.write(f"  STUCK ingestion: {run.id} (started: {run.started_at}, tenant: {run.tenant_id})")
            if not dry_run:
                run.status = "FAILED"
                run.error_message = f"Run stuck >{int((timezone.now() - run.started_at).total_seconds() / 3600)}h"
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "error_message", "completed_at"])
        return count

    def _check_export(self, cutoff, dry_run: bool) -> int:
        from hub.apps.scheduled_export.models import ScheduledExportRun
        stuck = ScheduledExportRun.objects.filter(
            status="RUNNING",
            started_at__lt=cutoff,
        )
        count = stuck.count()
        for run in stuck:
            self.stdout.write(f"  STUCK export: {run.id} (started: {run.started_at}, tenant: {run.tenant_id})")
            if not dry_run:
                run.status = "FAILED"
                run.error_message = f"Run stuck >{int((timezone.now() - run.started_at).total_seconds() / 3600)}h"
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "error_message", "completed_at"])
        return count
