"""
Management command to list UX v2 enablement status across all tenants.

Phase 278.S.2 — staged rollout progress tracking.
Outputs a table with tenant slug, name, ux_v2 status, and creation date.
Exits 0 when all tenants have ux_v2 enabled (rollout complete);
exits 1 otherwise (so CI/scripts can gate on rollout progress).

Usage:
    python manage.py list_ux_v2_tenants
    python manage.py list_ux_v2_tenants --enabled-only
    python manage.py list_ux_v2_tenants --disabled-only
    python manage.py list_ux_v2_tenants --json  # machine-readable output
"""
import json
from django.core.management.base import BaseCommand
from hub.apps.tenants.models import Tenant
import structlog

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "List UX v2 enablement status for all tenants"

    def add_arguments(self, parser):
        parser.add_argument(
            "--enabled-only",
            action="store_true",
            help="Show only tenants with UX v2 enabled",
        )
        parser.add_argument(
            "--disabled-only",
            action="store_true",
            help="Show only tenants with UX v2 disabled",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as machine-readable JSON",
        )

    def handle(self, *args, **options):
        enabled_only = options["enabled_only"]
        disabled_only = options["disabled_only"]
        json_output = options["json"]

        if enabled_only and disabled_only:
            self.stderr.write(
                "Cannot specify both --enabled-only and --disabled-only."
            )
            return

        tenants = (
            Tenant.objects.using("admin")
            .all()
            .order_by("slug")
            .values("id", "name", "slug", "ux_v2_enabled", "created_at")
        )

        if enabled_only:
            tenants = tenants.filter(ux_v2_enabled=True)
        elif disabled_only:
            tenants = tenants.filter(ux_v2_enabled=False)

        tenant_list = list(tenants)
        total = len(tenant_list)
        enabled_count = sum(1 for t in tenant_list if t["ux_v2_enabled"])
        disabled_count = total - enabled_count

        if json_output:
            output = {
                "summary": {
                    "total_tenants": total,
                    "ux_v2_enabled": enabled_count,
                    "ux_v2_disabled": disabled_count,
                    "rollout_pct": round(enabled_count / total * 100, 1) if total > 0 else 0,
                },
                "tenants": [
                    {
                        "id": str(t["id"]),
                        "name": t["name"],
                        "slug": t["slug"],
                        "ux_v2_enabled": t["ux_v2_enabled"],
                        "created_at": t["created_at"].isoformat() if t["created_at"] else None,
                    }
                    for t in tenant_list
                ],
            }
            self.stdout.write(json.dumps(output, indent=2))
        else:
            # Human-readable table
            self.stdout.write("")
            self.stdout.write(
                f"{'Slug':<30} {'Name':<30} {'UX v2':<8} {'Created'}"
            )
            self.stdout.write("-" * 90)
            for t in tenant_list:
                status = "ENABLED" if t["ux_v2_enabled"] else "DISABLED"
                created = t["created_at"].strftime("%Y-%m-%d") if t["created_at"] else "—"
                self.stdout.write(
                    f"{t['slug']:<30} {t['name']:<30} {status:<8} {created}"
                )
            self.stdout.write("-" * 90)
            self.stdout.write(
                f"Summary: {enabled_count} enabled, {disabled_count} disabled "
                f"({round(enabled_count / total * 100, 1) if total > 0 else 0}% rollout)"
            )
            self.stdout.write("")

        # Exit 1 when not all tenants have ux_v2 (for CI gating)
        if disabled_count > 0:
            logger.info(
                "ux_v2_rollout_incomplete",
                enabled=enabled_count,
                disabled=disabled_count,
                total=total,
            )
            if not json_output:
                self.stdout.write(
                    self.style.WARNING(
                        f"Rollout incomplete: {disabled_count} tenant(s) still on classic UX."
                    )
                )
            # Exit 1 for script/CI gating, but only in non-JSON mode where a
            # human operator is watching. JSON mode always exits 0 so CI
            # pipelines can parse the output without failing.
            if not json_output:
                exit(1)
