"""Shared DoD (helm CronJobs for recurring jobs) — the recurring Delta
Sharing Parquet snapshot sweep (the CronJob entry).

Discovers tenants that own >=1 ``DeltaShareRecipient`` AND >=1 shareable
asset (LIVE_QUERY + connected + opted in — the exact ``shareable_assets``
serving-side filter) via ``DATABASES["admin"]`` (cross-tenant discovery,
BYPASSRLS — the CLAUDE.md management-command contract), then per tenant
UNDER that tenant's ``tenant_context`` (the jobs + snapshots tables are
RLS-scoped) refreshes every expired/missing snapshot through the 5.4
``run_snapshot_job`` spine (one Hub Job row + audit per refresh). A
FRESH snapshot is zero work (the ``latest_snapshot`` lookup); a
per-asset failure is recorded and the sweep CONTINUES (the next
CronJob tick retries) — a broken table never starves the tenant's other
tables. Assets without an external table ref are never served by the
protocol and are skipped outright.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from hub.apps.assets.models import Asset, DataStrategy
from hub.apps.audit.utils import create_audit_event
from hub.apps.databricks_admin.delta_sharing_service import (
    SHARE_NAME,
    latest_snapshot,
    schema_name_for,
    shareable_assets,
    table_name_for,
)
from hub.apps.databricks_admin.delta_sharing_snapshot import (
    run_snapshot_job,
)
from hub.apps.databricks_admin.models import DeltaShareRecipient
from hub.apps.jobs.models import JobStatus
from hub.apps.tenants.request_tenant import tenant_context


class Command(BaseCommand):
    help = (
        "Refresh expired/missing Delta Sharing Parquet snapshots for every "
        "tenant with recipients + shareable assets (admin-DB discovery, "
        "tenant_context per tenant; the 5.4 run_snapshot_job spine per table)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the tenants with stale or missing snapshots without refreshing.",
        )

    def _discover_tenant_ids(self) -> list:
        """Tenant ids that own >=1 recipient AND >=1 shareable asset
        (admin-DB discovery — cross-tenant by design, the management-
        command contract)."""
        recipient_tenant_ids = set(
            DeltaShareRecipient.objects.using("admin").values_list("tenant_id", flat=True)
        )
        asset_tenant_ids = set(
            Asset.objects.using("admin")
            .filter(
                data_strategy=DataStrategy.LIVE_QUERY,
                warehouse_connection__isnull=False,
                semantic_federate_optout=False,
            )
            .values_list("tenant_id", flat=True)
        )
        return sorted(recipient_tenant_ids & asset_tenant_ids)

    def _stale_assets(self, tenant_id) -> tuple[list, int]:
        """The tenant's shareable tables whose snapshot is stale or
        missing (a NULL expiry is EXPIRED — the fail-closed rule), plus
        the count of shareable assets without an external table ref
        (never served by the protocol — never snapshotted)."""
        stale = []
        tableless = 0
        for asset in shareable_assets(tenant_id):
            table = table_name_for(asset)
            if not table:
                tableless += 1
                continue
            if (
                latest_snapshot(
                    tenant_id,
                    share=SHARE_NAME,
                    schema=schema_name_for(asset),
                    table=table,
                )
                is None
            ):
                stale.append(asset)
        return stale, tableless

    def handle(self, *_args, **options):
        dry_run = options["dry_run"]

        # 277.B.019 — every admin-DB command must emit an audit event
        # (cross-tenant discovery through the BYPASSRLS admin alias).
        try:
            create_audit_event(
                resource_type="DATABRICKS",
                action="DATABRICKS_DELTA_SHARE_SNAPSHOT_SWEEP_STARTED",
                actor_user=None,
                infer_tenant_from_actor=False,
                result="SUCCESS",
                details={
                    "actor": "PLATFORM_ADMIN",
                    "justification": "cross-tenant admin-DB delta-share snapshot sweep",
                    "dry_run": dry_run,
                },
            )
        except Exception as audit_err:
            self.stderr.write(f"Audit event emission failed (non-fatal): {audit_err}")

        reported: list[str] = []
        refreshed = 0
        failed = 0
        tableless = 0

        for tenant_id in self._discover_tenant_ids():
            try:
                with tenant_context(str(tenant_id)):
                    stale_assets, tenant_tableless = self._stale_assets(tenant_id)
            except Exception as exc:
                self.stderr.write(f"tenant {tenant_id} skipped: {exc}")
                continue

            tableless += tenant_tableless
            if not stale_assets:
                continue

            reported.append(str(tenant_id))
            if dry_run:
                continue

            for asset in stale_assets:
                try:
                    # The 5.4 spine runs IN-PROCESS (the CronJob pod is the
                    # executor) — the Job row + audit land under the tenant's
                    # RLS context.
                    with tenant_context(str(tenant_id)):
                        job = run_snapshot_job(asset=asset)
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f"asset {asset.id} refresh failed: {exc}")
                    continue
                # The spine signals failure through the Job row's terminal
                # status, never an exception (the ensure_fresh_snapshot
                # contract) — a non-COMPLETED job is a failed refresh.
                if job is None or job.status != JobStatus.COMPLETED:
                    failed += 1
                    message = (
                        getattr(job, "error_message", None)
                        or "the snapshot refresh did not complete"
                    )
                    self.stderr.write(f"asset {asset.id} refresh failed: {message}")
                    continue
                refreshed += 1

        summary = (
            f"Refreshed {refreshed} snapshot(s) across {len(reported)} "
            f"discovered tenant(s) — {failed} failed, {tableless} table-less "
            "asset(s) skipped."
        )
        if dry_run:
            for tenant_id in reported:
                self.stdout.write(tenant_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run: {len(reported)} tenant(s) with stale or missing snapshot(s)."
                )
            )
            return "\n".join(reported)

        self.stdout.write(self.style.SUCCESS(summary))
        return (
            f"refreshed {refreshed} of {refreshed + failed} attempted across "
            f"{len(reported)} tenant(s), {failed} failed"
        )
