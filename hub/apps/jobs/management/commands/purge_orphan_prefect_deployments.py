"""
Phase 25.9.2 — Purge orphan Prefect deployments.

Finds ScheduledIngestion and ScheduledExport records that are soft-deleted
(status=DELETED) but still have a prefect_deployment_id — meaning the Prefect
deployment delete failed during the user's DELETE request and needs to be
retried.

For each orphan:
  1. Call the integration service POST /deployments/delete.
  2. On success: hard-delete the DB record.
  3. On failure: leave the record for the next run to retry.

Designed to run hourly via a Kubernetes CronJob.
"""

import structlog
from django.core.management.base import BaseCommand

from hub.apps.core.utils.prefect_deployment import delete_prefect_deployment

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Purge orphan Prefect deployments for soft-deleted ScheduledIngestion "
        "and ScheduledExport records. Runs hourly via CronJob (Phase 25.9.2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List orphans without modifying them.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        ingestion_purged = self._purge_ingestions(dry_run)
        export_purged = self._purge_exports(dry_run)

        total = ingestion_purged + export_purged
        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {total} orphan deployment(s) "
                f"({ingestion_purged} ingestion, {export_purged} export)."
            )
        )

    def _purge_ingestions(self, dry_run: bool) -> int:
        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestion,
            ScheduledIngestionStatus,
        )

        orphans = ScheduledIngestion.objects.filter(
            status=ScheduledIngestionStatus.DELETED,
            prefect_deployment_id__isnull=False,
        ).exclude(prefect_deployment_id="")

        return self._purge_queryset(
            orphans, "scheduled_ingestion", dry_run,
        )

    def _purge_exports(self, dry_run: bool) -> int:
        from hub.apps.scheduled_export.models import (
            ScheduledExport,
            ScheduledExportStatus,
        )

        orphans = ScheduledExport.objects.filter(
            status=ScheduledExportStatus.DELETED,
            prefect_deployment_id__isnull=False,
        ).exclude(prefect_deployment_id="")

        return self._purge_queryset(
            orphans, "scheduled_export", dry_run,
        )

    def _purge_queryset(self, queryset, resource_type: str, dry_run: bool) -> int:
        count = queryset.count()
        if count == 0:
            return 0

        self.stdout.write(
            f"Found {count} orphan {resource_type} record(s) "
            f"with pending Prefect deployments."
        )

        if dry_run:
            for record in queryset:
                self.stdout.write(
                    f"  [DRY-RUN] {record.id}  "
                    f"deployment={record.prefect_deployment_id}"
                )
            return 0

        purged = 0
        for record in queryset:
            deleted = delete_prefect_deployment(
                deployment_id=str(record.prefect_deployment_id),
                resource_id=str(record.id),
                resource_type=resource_type,
                tenant_id=str(record.tenant_id),
            )
            if deleted:
                record_id = str(record.id)
                # Hard-delete the DB record now that deployment is gone.
                # No save() needed — the record is about to be removed.
                record.delete()
                logger.info(
                    "purge_orphan_record_deleted",
                    resource_type=resource_type,
                    resource_id=record_id,
                )
                purged += 1
            else:
                logger.warning(
                    "purge_orphan_skipped",
                    resource_type=resource_type,
                    resource_id=str(record.id),
                    deployment_id=str(record.prefect_deployment_id),
                )

        return purged
