"""
Management command to archive audit events older than retention period.

Archival marks events via queryset.update() (bypasses the model's append-only
save() guard — intentional for this administrative operation).  Archived events
remain in the database but are excluded from default API queries.

Run periodically via cron or Kubernetes CronJob:
    python manage.py archive_old_audit_events
    python manage.py archive_old_audit_events --dry-run
    python manage.py archive_old_audit_events --retention-years 5
    python manage.py archive_old_audit_events --batch-size 5000
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.audit.models import AuditEvent

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10_000


class Command(BaseCommand):
    help = "Archive audit events older than the retention period (default: 3 years)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be archived without actually archiving",
        )
        parser.add_argument(
            "--retention-years",
            type=int,
            default=getattr(settings, "AUDIT_RETENTION_YEARS", 3),
            help="Number of years to retain audit events (default: 3)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Events to archive per batch (default: {DEFAULT_BATCH_SIZE})",
        )

    def handle(self, *args, **options):
        retention_years = options["retention_years"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        if retention_years < 1:
            self.stderr.write(self.style.ERROR("--retention-years must be >= 1"))
            return

        cutoff_date = timezone.now() - timedelta(days=retention_years * 365)

        # Use all_objects to bypass the ActiveAuditEventManager default filter
        eligible = AuditEvent.all_objects.filter(
            timestamp__lt=cutoff_date,
            is_archived=False,
        )
        total_count = eligible.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("No unarchived audit events older than retention period.")
            )
            return

        if dry_run:
            self._report_dry_run(eligible, total_count, cutoff_date)
            return

        archived_total = self._archive_in_batches(eligible, batch_size)

        summary = (
            f"Archived {archived_total} audit events older than "
            f"{cutoff_date.date().isoformat()} (retention: {retention_years}y)."
        )
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info(summary)

    def _report_dry_run(self, eligible, total_count, cutoff_date):
        self.stdout.write(
            self.style.WARNING(
                f"DRY RUN: Would archive {total_count} events "
                f"older than {cutoff_date.date().isoformat()}"
            )
        )
        sample = eligible.order_by("timestamp")[:5]
        for event in sample:
            self.stdout.write(
                f"  - {event.action} on {event.resource_type} "
                f"at {event.timestamp.isoformat()}"
            )
        if total_count > 5:
            self.stdout.write(f"  ... and {total_count - 5} more")

    def _archive_in_batches(self, eligible, batch_size):
        """Archive in batches to avoid long table locks.

        Uses queryset.update() which bypasses the model's save() guard.
        This is the intended mechanism for administrative archival.
        """
        now = timezone.now()
        archived_total = 0

        while True:
            batch_pks = list(
                eligible.order_by("timestamp")
                .values_list("pk", flat=True)[:batch_size]
            )
            if not batch_pks:
                break

            updated = AuditEvent.all_objects.filter(pk__in=batch_pks).update(
                is_archived=True,
                archived_at=now,
            )
            archived_total += updated
            self.stdout.write(
                f"  Archived batch: {updated} (total: {archived_total})"
            )

        return archived_total
