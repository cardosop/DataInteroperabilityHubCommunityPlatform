"""
285.11.5.4 — clean_pipeline_deps management command.

Queries each PipelineDependency's (pipeline_type, pipeline_id) against
the target pipeline execution table. If the referenced pipeline no
longer exists (soft-deleted, hard-deleted, or never existed), sets
``is_active=False`` and emits a ``PIPELINE_DEPENDENCY_STALE_CLEANED``
audit event.

Designed to run weekly via Kubernetes CronJob.
"""
from __future__ import annotations
import structlog
from django.core.management.base import BaseCommand

from hub.apps.audit.utils import create_audit_event
from hub.apps.orchestration.models import PipelineDependency
from hub.apps.orchestration.trigger_engine import (
    _get_pipeline_execution_status,
)
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "285.11.5.4 — Deactivate stale PipelineDependency references"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id", default=None,
            help="Restrict to a single tenant UUID.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Report stale deps without modifying them.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        target_tenant_id = options.get("tenant_id")

        if target_tenant_id:
            tenant_ids = [str(target_tenant_id)]
        else:
            tenant_ids = [
                str(tid) for tid in
                Tenant.objects.order_by("id").values_list("id", flat=True)
            ]

        total_cleaned = 0
        for tenant_id in tenant_ids:
            with tenant_context(tenant_id):
                total_cleaned += self._clean_for_tenant(tenant_id, dry_run)

        if total_cleaned == 0:
            self.stdout.write(
                self.style.SUCCESS("No stale pipeline dependencies found.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleaned {total_cleaned} stale pipeline dependency(ies)."
                )
            )

    def _clean_for_tenant(self, tenant_id: str, dry_run: bool) -> int:
        deps = PipelineDependency.objects.filter(
            tenant_id=tenant_id, is_active=True,
        )
        cleaned = 0

        for dep in deps:
            # Check if the upstream pipeline still exists.
            upstream_status = _get_pipeline_execution_status(
                tenant_id, dep.pipeline_type, str(dep.pipeline_id),
            )
            if upstream_status is not None:
                continue  # pipeline still exists

            # Upstream pipeline is gone — deactivate the dep.
            if dry_run:
                self.stdout.write(
                    f"  [DRY-RUN] {dep.pipeline_type}:{dep.pipeline_id} "
                    f"→ {dep.downstream_pipeline_type}:{dep.downstream_pipeline_id}"
                    f"  (upstream pipeline missing)"
                )
                cleaned += 1
                continue

            dep.is_active = False
            dep.save(update_fields=["is_active", "updated_at"])
            cleaned += 1

            try:
                create_audit_event(
                    resource_type="PIPELINE_DEPENDENCY",
                    action="PIPELINE_DEPENDENCY_STALE_CLEANED",
                    actor_user=None,
                    tenant=dep.tenant,
                    resource_id=str(dep.id),
                    details={
                        "pipeline_type": dep.pipeline_type,
                        "pipeline_id": str(dep.pipeline_id),
                        "downstream_type": dep.downstream_pipeline_type,
                        "downstream_id": str(dep.downstream_pipeline_id),
                    },
                )
            except Exception as exc:
                logger.warning(
                    "clean_deps_audit_failed",
                    dep_id=str(dep.id), error=str(exc),
                )

            logger.info(
                "pipeline_dependency_stale_cleaned",
                dep_id=str(dep.id),
                tenant_id=tenant_id,
            )

        return cleaned
