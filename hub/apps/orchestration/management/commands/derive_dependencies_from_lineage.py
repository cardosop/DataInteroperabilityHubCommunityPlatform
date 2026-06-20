"""
285.11.1.11 — derive_dependencies_from_lineage management command.

Walks the LineageEdge graph for a tenant, finds "A produces X,
B consumes X" patterns, and auto-creates ``PipelineDependency``
rows with ``created_by="LINEAGE_SYNC"``.

Deduplicates on the scope tuple (tenant, pipeline_type, pipeline_id,
dependency_type, downstream_pipeline_type, downstream_pipeline_id)
via ``UniqueConstraint``.
"""

from __future__ import annotations

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.contracts.models import LineageEdge, LineageEdgeType
from hub.apps.orchestration.models import (
    DependencySource,
    DependencyType,
    PipelineDependency,
    PipelineType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

logger = structlog.get_logger(__name__)

# Mapping from LineageEdgeType → PipelineType for auto-derivation.
_EDGE_TYPE_TO_PIPELINE_TYPE: dict[str, str] = {
    LineageEdgeType.UPLOAD: PipelineType.SCHEDULED_INGESTION,
    LineageEdgeType.TRANSFORMATION: PipelineType.TRANSFORMATION,
    LineageEdgeType.EXPORT: PipelineType.SCHEDULED_EXPORT,
}


class Command(BaseCommand):
    help = "285.11.1.11 — Derive PipelineDependency rows from LineageEdge graph"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict to a single tenant UUID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report what would be created without persisting.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        target_tenant_id = options.get("tenant_id")

        if target_tenant_id:
            tenant_ids = [str(target_tenant_id)]
        else:
            tenant_ids = [
                str(tid) for tid in Tenant.objects.order_by("id").values_list("id", flat=True)
            ]

        total_created = 0
        for tenant_id in tenant_ids:
            with tenant_context(tenant_id):
                created = self._derive_for_tenant(tenant_id, dry_run)
                total_created += created

        if total_created == 0:
            self.stdout.write(self.style.SUCCESS("No new pipeline dependencies derived."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Derived {total_created} new pipeline dependency(ies).")
            )

    def _derive_for_tenant(self, tenant_id: str, dry_run: bool) -> int:
        """Find producer→consumer relationships and create deps."""
        created = 0

        # Walk current (valid_to IS NULL) lineage edges.
        edges = LineageEdge.objects.filter(
            tenant_id=tenant_id,
            valid_to__isnull=True,
        ).select_related("source_contract", "target_contract")

        # Group by source→target pairs.  For each source contract that
        # has outgoing edges and each target contract with incoming edges
        # for the same model/field, create a DATA dependency.
        for edge in edges:
            source_type = _EDGE_TYPE_TO_PIPELINE_TYPE.get(
                edge.edge_type,
                None,
            )
            target_type = _EDGE_TYPE_TO_PIPELINE_TYPE.get(
                edge.edge_type,
                None,
            )
            # Only auto-derive for known edge→pipeline mappings.
            if source_type is None or target_type is None:
                continue

            source_id = str(edge.source_contract.id) if edge.source_contract else None
            target_id = str(edge.target_contract.id) if edge.target_contract else None
            if source_id is None or target_id is None:
                continue
            if source_id == target_id:
                continue  # skip self-loops

            # Dedup via UniqueConstraint — create_or_get.
            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] {source_type}:{source_id} "
                    f"→[{DependencyType.DATA}]→ "
                    f"{target_type}:{target_id}"
                    f"  (edge={edge.id})"
                )
                created += 1
                continue

            try:
                with transaction.atomic():
                    dep, was_created = PipelineDependency.objects.get_or_create(
                        tenant_id=tenant_id,
                        pipeline_type=source_type,
                        pipeline_id=source_id,
                        dependency_type=DependencyType.DATA,
                        downstream_pipeline_type=target_type,
                        downstream_pipeline_id=target_id,
                        defaults={
                            "created_by": DependencySource.LINEAGE_SYNC,
                            "lineage_edge": edge,
                            "priority": 0,
                            "is_active": True,
                        },
                    )
                    if was_created:
                        created += 1
                        logger.info(
                            "lineage_dependency_derived",
                            dep_id=str(dep.id),
                            source_type=source_type,
                            source_id=source_id,
                            target_type=target_type,
                            target_id=target_id,
                            lineage_edge_id=str(edge.id),
                        )
            except Exception as exc:
                logger.error(
                    "lineage_dependency_derivation_failed",
                    tenant_id=tenant_id,
                    edge_id=str(edge.id),
                    error=str(exc),
                )

        return created
