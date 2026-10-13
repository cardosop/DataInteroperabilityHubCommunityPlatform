"""Phase 1 (add-databricks-uc-read 1.5) — CronJob entry for the UC metadata sync.

Discovers tenants that own ACTIVE Databricks workspaces via
``DATABASES["admin"]`` (cross-tenant discovery, BYPASSRLS — the CLAUDE.md
management-command contract) and enqueues ONE
``JobType.DATABRICKS_UC_METADATA_SYNC`` RQ job per tenant. The Job row
is created UNDER that tenant's ``tenant_context`` (the jobs table is
RLS-scoped); the RQ worker runs the per-tenant delta under the same
context.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from hub.apps.audit.utils import create_audit_event
from hub.apps.databricks_admin.models import DatabricksWorkspace, DatabricksWorkspaceStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.request_tenant import tenant_context


class Command(BaseCommand):
    help = (
        "Enqueue one DATABRICKS_UC_METADATA_SYNC RQ job per tenant with "
        "ACTIVE Databricks workspaces (admin-DB discovery, tenant_context "
        "per job row)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the discovered tenants without creating/enqueuing jobs.",
        )

    def handle(self, *_args, **options):
        dry_run = options["dry_run"]

        tenant_ids = list(
            DatabricksWorkspace.objects.using("admin")
            .filter(status=DatabricksWorkspaceStatus.ACTIVE)
            .values_list("tenant_id", flat=True)
            .distinct()
            .order_by("tenant_id")
        )

        # 277.B.019 — every admin-DB command must emit an audit event
        # (cross-tenant discovery through the BYPASSRLS admin alias).
        try:
            create_audit_event(
                resource_type="DATABRICKS",
                action="DATABRICKS_UC_METADATA_SYNC_SWEEP_STARTED",
                actor_user=None,
                infer_tenant_from_actor=False,
                result="SUCCESS",
                details={
                    "actor": "PLATFORM_ADMIN",
                    "justification": "cross-tenant admin-DB UC metadata-sync sweep",
                    "discovered_tenants": len(tenant_ids),
                    "dry_run": dry_run,
                },
            )
        except Exception as audit_err:
            self.stderr.write(f"Audit event emission failed (non-fatal): {audit_err}")

        if dry_run:
            for tenant_id in tenant_ids:
                self.stdout.write(str(tenant_id))
            self.stdout.write(
                self.style.SUCCESS(f"Dry run: {len(tenant_ids)} tenant(s) with ACTIVE workspaces.")
            )
            return "\n".join(str(tenant_id) for tenant_id in tenant_ids)

        from rest_framework.exceptions import ValidationError

        from hub.apps.tenants.models import Tenant

        created = 0
        for tenant_id in tenant_ids:
            tenant = Tenant.objects.using("admin").get(id=tenant_id)
            try:
                with tenant_context(str(tenant_id)):
                    create_job(
                        tenant=tenant,
                        job_type=JobType.DATABRICKS_UC_METADATA_SYNC,
                        resource_type="TENANT",
                        resource_id=str(tenant_id),
                    )
            except ValidationError as exc:
                # Tenant job limits (concurrency/queue depth) — record and
                # continue; the next CronJob tick retries the tenant.
                self.stderr.write(f"tenant {tenant_id} skipped: {exc}")
                continue
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Enqueued {created} DATABRICKS_UC_METADATA_SYNC job(s) "
                f"across {len(tenant_ids)} discovered tenant(s)."
            )
        )
        return f"enqueued {created} of {len(tenant_ids)} tenant(s)"
