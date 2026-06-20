"""
285.9.I4 — Migrate legacy transformation pipelines to dbt-native format.

Lists pipelines still using the deprecated DuckDB/Polars engine
(``mode: SQL`` or ``mode: VISUAL`` in ``pipeline_definition``) and
provides a ``--dry-run`` mode to preview before migrating.

Usage:
    python manage.py migrate_legacy_transformation_pipelines --dry-run
    python manage.py migrate_legacy_transformation_pipelines
    python manage.py migrate_legacy_transformation_pipelines --pipeline-id=<uuid>
"""

from __future__ import annotations

import contextlib

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "List or migrate legacy transformation pipelines (DuckDB/Polars → dbt-native)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List legacy pipelines without modifying them.",
        )
        parser.add_argument(
            "--pipeline-id",
            type=str,
            help="Migrate a single pipeline by UUID.",
        )

    def handle(self, *args, **options):
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.transformation.models import (
            PipelineStatus,
            TransformationPipeline,
        )

        dry_run: bool = options["dry_run"]
        target_id = options.get("pipeline_id")

        qs = TransformationPipeline.objects.exclude(
            status=PipelineStatus.ARCHIVED,
        )
        if target_id:
            qs = qs.filter(id=target_id)

        legacy_pipelines = []
        for pipeline in qs:
            try:
                pdef = (
                    pipeline.get_pipeline_definition()
                    if hasattr(pipeline, "get_pipeline_definition")
                    else pipeline.pipeline_definition
                )
            except Exception:
                pdef = pipeline.pipeline_definition

            if isinstance(pdef, dict) and pdef.get("mode") in ("SQL", "VISUAL"):
                legacy_pipelines.append(pipeline)

        if not legacy_pipelines:
            self.stdout.write(self.style.SUCCESS("No legacy pipelines found."))
            return

        self.stdout.write(f"Found {len(legacy_pipelines)} legacy pipeline(s):")
        for pipeline in legacy_pipelines:
            self.stdout.write(
                f"  {pipeline.id}  {pipeline.name}  "
                f"(tenant={pipeline.tenant_id}, status={pipeline.status})"
            )

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    "\nDRY RUN — no pipelines were modified. Remove --dry-run to migrate."
                )
            )
            return

        migrated = 0
        for pipeline in legacy_pipelines:
            try:
                # Convert pipeline_definition: strip legacy mode,
                # add a deprecation marker in metadata.
                pdef = pipeline.pipeline_definition or {}
                if isinstance(pdef, dict):
                    pdef.pop("mode", None)
                    pdef["engine"] = "dbt"
                    pdef["migrated_from"] = "legacy_duckdb_polars"
                    pipeline.pipeline_definition = pdef

                metadata = pipeline.metadata or {}
                metadata["legacy_migration_timestamp"] = (
                    __import__("django").utils.timezone.now().isoformat()
                )
                pipeline.metadata = metadata
                pipeline.save(
                    update_fields=["pipeline_definition", "metadata", "updated_at"],
                )

                with contextlib.suppress(Exception):
                    create_audit_event(
                        resource_type="TRANSFORMATION_PIPELINE",
                        action="TRANSFORMATION_PIPELINE_MIGRATED_TO_DBT",
                        tenant=pipeline.tenant,
                        resource_id=str(pipeline.id),
                        details={
                            "pipeline_id": str(pipeline.id),
                            "pipeline_name": pipeline.name,
                            "tenant_id": str(pipeline.tenant_id),
                        },
                    )

                migrated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  Migrated: {pipeline.id} ({pipeline.name})")
                )
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  Failed: {pipeline.id} — {exc}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nMigrated {migrated} of {len(legacy_pipelines)} pipeline(s).")
        )
