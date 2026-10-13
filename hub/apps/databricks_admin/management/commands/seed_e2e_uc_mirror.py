"""W4.6 (openspec oss-release-remediation, G1) — the E2E UC-mirror seed
(openspec add-databricks-uc-read task 1.11), moved OUT of the users
``ensure_e2e_user_roles`` command.

JOURNEY-DB-005/006 E2E browse the REAL mirror rows of a deterministic
workspace (the mirror is normally populated by the UC metadata sync,
which needs live Databricks; the seed gives the e2e tenant a stable
catalog → schema → table chain). The seed writes ESTATE models — it
lives HERE, in the estate app that owns them (the provider-boundary
direction); the outer command invokes it by NAME through Django's
command registry (``call_command``) — no estate import on the caller
side.

RLS contract: the tenant-scoped writes run inside
``tenant_context(tenant_id)`` (the management-command convention — the
pre-move block ran unarmed; the mirror tables are strict-RLS and an
unarmed write is a silent no-op under arming). The tenant row itself is
fetched on the default alias — the command targets ONE tenant passed by
id (not a cross-tenant iteration), matching the caller's E2E seeding
environment (the test stack runs with row_security=off rather than the
admin alias).
"""

from django.core.management.base import BaseCommand, CommandError

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context


class Command(BaseCommand):
    help = (
        "Seed the e2e tenant's UC mirror (workspace e2e-databricks → "
        "e2e_main.e2e_sales.e2e_orders) for JOURNEY-DB-005/006."
    )

    def add_arguments(self, parser):
        parser.add_argument("tenant_id", help="the e2e tenant's UUID")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="report the seed without writing",
        )

    def handle(self, *_args, **options):
        tenant_id = options["tenant_id"]
        dry_run = options["dry_run"]

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise CommandError(f"tenant {tenant_id} not found") from None

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    "[dry-run] would seed the e2e UC mirror "
                    f"(workspace e2e-databricks) for tenant {tenant_id}."
                )
            )
            return

        # The RLS contract: tenant-scoped writes inside tenant_context.
        with tenant_context(str(tenant.id)):
            from hub.apps.databricks_admin.models import (
                DatabricksCloud,
                DatabricksWorkspace,
                DatabricksWorkspaceStatus,
                UCCatalog,
                UCSchema,
                UCTable,
            )

            workspace, _ws_created = DatabricksWorkspace.objects.get_or_create(
                tenant=tenant,
                name="e2e-databricks",
                defaults={
                    "host": "dbc-6710eb95-8fe1.cloud.databricks.com",
                    "cloud": DatabricksCloud.AWS,
                    "region": "us-east-1",
                    "status": DatabricksWorkspaceStatus.ACTIVE,
                },
            )
            catalog, _cat_created = UCCatalog.objects.get_or_create(
                workspace=workspace,
                name="e2e_main",
                defaults={"comment": "e2e seed catalog"},
            )
            schema, _sch_created = UCSchema.objects.get_or_create(
                catalog=catalog, name="e2e_sales"
            )
            table, _tbl_created = UCTable.objects.get_or_create(
                schema=schema,
                name="e2e_orders",
                defaults={
                    "table_type": "MANAGED",
                    "columns": [{"name": "id", "type_text": "BIGINT"}],
                    "full_name": "e2e_main.e2e_sales.e2e_orders",
                },
            )
            # Mirror the real UC sync: full_name is what the catalog
            # browser renders (row.full_name || row.name). Rows seeded
            # before this backfill keep '' and render as bare names,
            # which breaks the JOURNEY-DB-005/006 drill pins
            # (e2e_main.e2e_sales regexes). Set unconditionally so the
            # seed is idempotent over pre-existing rows.
            catalog.full_name = "e2e_main"
            catalog.save(update_fields=["full_name"])
            schema.full_name = "e2e_main.e2e_sales"
            schema.save(update_fields=["full_name"])
            table.full_name = "e2e_main.e2e_sales.e2e_orders"
            table.save(update_fields=["full_name"])

        self.stdout.write(
            self.style.SUCCESS("Seeded the e2e UC mirror (workspace e2e-databricks).")
        )
