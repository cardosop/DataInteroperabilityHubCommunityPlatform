"""
Phase 275.B.10 — Daily schema drift check for LIVE_QUERY assets.

Iterates all active LIVE_QUERY assets, compares the warehouse schema
against the stored Dataset.schema_json, and emits
``WAREHOUSE_SCHEMA_DRIFT_DETECTED`` audit events for any drift found.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Check LIVE_QUERY assets for warehouse schema drift."

    def add_arguments(self, parser):
        parser.add_argument(
            "--asset-id", type=str, help="Check a single asset by UUID.",
        )
        parser.add_argument(
            "--tenant-id", type=str, help="Limit check to one tenant.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report drift without updating Dataset flags.",
        )

    def handle(self, *args, **options):
        from hub.apps.assets.models import Asset, DataStrategy
        from hub.apps.warehouses.schema_drift import check_schema_drift
        from hub.apps.audit.utils import create_audit_event

        qs = Asset.objects.filter(
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection__isnull=False,
            warehouse_connection__is_active=True,
        ).select_related("warehouse_connection", "tenant")

        asset_id = options.get("asset_id")
        tenant_id = options.get("tenant_id")
        dry_run = options.get("dry_run")

        if asset_id:
            qs = qs.filter(id=asset_id)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        total = qs.count()
        drift_count = 0

        self.stdout.write(f"Checking {total} LIVE_QUERY asset(s) for schema drift...")

        for asset in qs.iterator():
            try:
                drift = check_schema_drift(
                    asset=asset,
                    warehouse_connection=asset.warehouse_connection,
                    tenant=asset.tenant,
                )

                if drift:
                    drift_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  DRIFT: {asset.id} ({asset.name}) — "
                            f"added={len(drift.get('added_columns', []))}, "
                            f"removed={len(drift.get('removed_columns', []))}, "
                            f"changed={len(drift.get('type_changes', []))}"
                        )
                    )

                    if not dry_run:
                        from hub.apps.datasets.models import Dataset
                        Dataset.objects.filter(asset=asset).update(
                            schema_drift_pending=True,
                        )

                    create_audit_event(
                        resource_type="ASSET",
                        action="WAREHOUSE_SCHEMA_DRIFT_DETECTED",
                        tenant=asset.tenant,
                        resource_id=str(asset.id),
                        result="WARNING",
                        details={
                            "asset_id": str(asset.id),
                            "warehouse_type": asset.warehouse_connection.warehouse_type,
                            "drift": drift,
                        },
                    )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"  ERROR: {asset.id} — {exc}")
                )

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"\nDRY RUN — {drift_count} asset(s) with drift detected. "
                    "No Dataset flags were updated."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone. {drift_count} of {total} asset(s) have schema drift."
                )
            )
