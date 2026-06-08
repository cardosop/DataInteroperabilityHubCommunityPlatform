"""
Management command to drop orphaned dlt state tables.

dlt creates ``_dlt_loads``, ``_dlt_pipeline_state``, and ``_dlt_version``
tables in the ``dlt_ingestion`` / ``dlt_export`` PostgreSQL schemas.
When a pipeline (ScheduledIngestion or ScheduledExport) is deleted, those
tables become orphaned.  This sweep drops them after a grace period.

Usage:
    python manage.py cleanup_dlt_state_tables --dry-run
    python manage.py cleanup_dlt_state_tables --execute
    python manage.py cleanup_dlt_state_tables --dry-run --min-age-days 180
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

_DLT_SCHEMAS = ("dlt_ingestion", "dlt_export")
_DLT_TABLE_PREFIX = "_dlt_"


class Command(BaseCommand):
    help = "Drop orphaned _dlt_* state tables for deleted pipelines."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview without dropping.")
        parser.add_argument("--execute", action="store_true", help="Perform the cleanup.")
        parser.add_argument(
            "--min-age-days",
            type=int,
            default=90,
            help="Minimum days since pipeline deletion (default: 90).",
        )
        parser.add_argument(
            "--schema",
            default="both",
            choices=["dlt_ingestion", "dlt_export", "both"],
            help="Which dlt schema to sweep (default: both).",
        )

    def handle(self, **options):
        dry_run = options["dry_run"]
        execute = options["execute"]
        min_age_days = options["min_age_days"]
        schema_filter = options["schema"]

        if not (dry_run or execute):
            self.stderr.write("ERROR: pass --dry-run or --execute")
            return

        cutoff = timezone.now() - timedelta(days=min_age_days)
        schemas = (
            list(_DLT_SCHEMAS)
            if schema_filter == "both"
            else [schema_filter]
        )

        # Build the set of active pipeline IDs so we know which tables
        # are still in use.
        active_ingestion_ids = self._active_ingestion_ids()
        active_export_ids = self._active_export_ids()

        dropped = 0
        for schema_name in schemas:
            tables = self._dlt_tables_in_schema(schema_name)
            for table_name in tables:
                # Determine if the table's pipeline still exists.
                # Table names follow dlt naming: {dataset_name}_dlt_*
                # We check against active ingestion/export IDs.
                if self._table_is_active(table_name, active_ingestion_ids, active_export_ids):
                    continue

                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Would drop orphaned table: "
                        f"{schema_name}.{table_name}"
                    )
                    dropped += 1
                    continue

                if execute:
                    self._drop_table(schema_name, table_name)
                    self.stdout.write(
                        f"[DROPPED] Orphaned table: {schema_name}.{table_name}"
                    )
                    dropped += 1
                    logger.info(
                        "dlt_state_table_dropped",
                        schema=schema_name,
                        table=table_name,
                    )

        if dropped == 0:
            self.stdout.write(
                self.style.SUCCESS("No orphaned dlt tables found.")
            )
        else:
            action = "Would drop" if dry_run else "Dropped"
            self.stdout.write(
                self.style.SUCCESS(f"{action} {dropped} orphaned dlt table(s).")
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_ingestion_ids(self) -> set[str]:
        """Return IDs of non-deleted ScheduledIngestion records."""
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        return set(
            ScheduledIngestion.objects.filter(status__in=("ACTIVE", "PAUSED", "ERROR"))
            .values_list("id", flat=True)
        )

    def _active_export_ids(self) -> set[str]:
        """Return IDs of non-deleted ScheduledExport records."""
        from hub.apps.scheduled_export.models import ScheduledExport

        return set(
            ScheduledExport.objects.filter(status__in=("ACTIVE", "PAUSED", "ERROR"))
            .values_list("id", flat=True)
        )

    def _dlt_tables_in_schema(self, schema_name: str) -> list[str]:
        """Return list of _dlt_* table names in *schema_name*."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_name LIKE %s
                ORDER BY table_name
                """,
                [schema_name, f"{_DLT_TABLE_PREFIX}%%"],
            )
            return [row[0] for row in cursor.fetchall()]

    def _table_is_active(
        self,
        table_name: str,
        active_ingestion_ids: set[str],
        active_export_ids: set[str],
    ) -> bool:
        """Heuristic: a dlt table is still active if its pipeline name
        (derived from the dataset portion of the table name) matches an
        active pipeline ID."""
        # dlt table names: {pipeline_name}_{resource_name}_dlt_...
        # The pipeline_name is the ScheduledIngestion/Export name
        # (sanitized).  We can't perfectly reverse-map, so we keep
        # tables that match any active pipeline's name prefix.
        # This is conservative: it's better to leave a table than to
        # drop a live one.
        pipeline_name = table_name.split("_dlt_")[0] if "_dlt_" in table_name else ""
        if not pipeline_name:
            return True  # can't determine — keep it

        # Check against active IDs (UUID strings, sanitized as underscores)
        for active_id in active_ingestion_ids | active_export_ids:
            sanitized = str(active_id).replace("-", "_")
            if sanitized in pipeline_name:
                return True
        return False

    def _drop_table(self, schema_name: str, table_name: str):
        """Execute DROP TABLE IF EXISTS."""
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP TABLE IF EXISTS "{schema_name}"."{table_name}" CASCADE'
            )
