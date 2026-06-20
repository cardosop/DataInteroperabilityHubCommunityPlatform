"""
cleanup_transformation_runs — Phase 115E.4

Deletes old PipelineExecution records matching age + status criteria.

Usage:
    python manage.py cleanup_transformation_runs --older-than=90d --status=FAILED
    python manage.py cleanup_transformation_runs --older-than=180d --status=COMPLETED
    python manage.py cleanup_transformation_runs --older-than=90d  # all terminal
    python manage.py cleanup_transformation_runs --dry-run --older-than=30d
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")


class Command(BaseCommand):
    help = (
        "Delete old transformation pipeline executions. "
        "Only terminal statuses (COMPLETED, FAILED, CANCELLED) "
        "are eligible for cleanup."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than",
            default="90d",
            help=("Age threshold. Format: <number>d for days, <number>h for hours. Default: 90d"),
        )
        parser.add_argument(
            "--status",
            choices=["COMPLETED", "FAILED", "CANCELLED"],
            default=None,
            help=(
                "Only delete executions with this status. "
                "If omitted, all terminal statuses are cleaned."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making changes.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of records to delete per batch. Default: 500",
        )

    def handle(self, *args, **options):
        from hub.apps.transformation.models import PipelineExecution

        threshold = self._parse_duration(options["older_than"])
        cutoff = timezone.now() - threshold
        status_filter = options["status"]
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        statuses = [status_filter] if status_filter else list(TERMINAL_STATUSES)

        qs = PipelineExecution.objects.filter(
            status__in=statuses,
            created_at__lt=cutoff,
        )

        total = qs.count()

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"No executions to clean up "
                    f"(older than {options['older_than']}, "
                    f"status={statuses})"
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would delete {total} executions "
                    f"(older than {options['older_than']}, "
                    f"status={statuses})"
                )
            )
            return

        deleted_total = 0
        while True:
            batch_ids = list(qs.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            count, _ = PipelineExecution.objects.filter(
                id__in=batch_ids,
            ).delete()
            deleted_total += count
            logger.info(
                "cleanup_transformation_runs_batch",
                extra={
                    "batch_deleted": count,
                    "total_deleted": deleted_total,
                    "remaining": total - deleted_total,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_total} executions "
                f"(older than {options['older_than']}, "
                f"status={statuses})"
            )
        )

    @staticmethod
    def _parse_duration(value: str) -> timedelta:
        """Parse duration string like '90d', '24h', '4320m'."""
        value = value.strip().lower()
        if not value:
            raise ValueError("Duration cannot be empty")

        if value.endswith("d"):
            num = int(value[:-1])
        elif value.endswith("h"):
            num = int(value[:-1])
            return timedelta(hours=num) if num > 0 else None
        elif value.endswith("m"):
            num = int(value[:-1])
            return timedelta(minutes=num) if num > 0 else None
        else:
            num = int(value)

        if num <= 0:
            raise ValueError(f"Duration must be positive, got: {value}")

        if value.endswith("h"):
            return timedelta(hours=num)
        if value.endswith("m"):
            return timedelta(minutes=num)
        return timedelta(days=num)
