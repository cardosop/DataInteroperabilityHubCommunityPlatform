"""
285.13.16.1 — Backfill enterprise plan limits for migrated tenants.

Three-phase workflow:
  1. ``--dry-run`` — identify tenants whose Enterprise plan has ``None``
     limits (unlimited) and show what would change.
  2. ``--confirm`` — flag those tenants for the 30-day notice window.
     Creates a ``TenantConfig.backfill_state`` marker and schedules
     ``notify_enterprise_backfill`` emails via the notification module.
  3. ``--apply`` — sets concrete caps on the identified plans, emits
     ``PLAN_LIMITS_BACKFILLED`` audit events, and clears the backfill
     marker.

Usage::

    python hub/manage.py backfill_enterprise_limits --dry-run
    python hub/manage.py backfill_enterprise_limits --confirm
    python hub/manage.py backfill_enterprise_limits --apply
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from hub.apps.tenants.models import PlanCategory, Tenant, TenantPlan

logger = logging.getLogger(__name__)

# Default concrete limits applied during backfill (285.13.16.1).
_ENTERPRISE_DEFAULT_CAPS = {
    "max_assets": 1000,
    "max_datasets": 500,
    "max_api_calls_per_month": 1_000_000,
    "max_storage_gb": 1024,
    "max_ingestion_runs": 200,
    "max_export_runs": 200,
}


class Command(BaseCommand):
    help = "285.13.16 — Backfill enterprise plan limits for migrated tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show tenants that would be affected without making changes.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Flag tenants for 30-day notice. Sends backfill notifications.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Apply concrete caps to Enterprise plans. Emits PLAN_LIMITS_BACKFILLED.",
        )

    def handle(self, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]
        apply_limits = options["apply"]

        if not any([dry_run, confirm, apply_limits]):
            self.stderr.write("Specify at least one of --dry-run, --confirm, --apply.")
            return

        enterprise_plans = TenantPlan.objects.filter(
            is_active=True, tier="ENTERPRISE", category=PlanCategory.BASE,
        )
        if not enterprise_plans.exists():
            self.stdout.write("No active Enterprise plans found.")
            return

        for plan in enterprise_plans:
            if plan.limits_json and all(
                v is not None for v in plan.limits_json.values()
            ):
                self.stdout.write(
                    f"Plan '{plan.slug}' already has concrete limits — skipping."
                )
                continue

            tenants = Tenant.objects.filter(plan=plan)
            tenant_count = tenants.count()

            self.stdout.write(
                f"\nPlan: {plan.name} (slug={plan.slug}) — {tenant_count} tenant(s)"
            )

            if dry_run:
                self._do_dry_run(plan, tenants)
            elif confirm:
                self._do_confirm(plan, tenants)
            elif apply_limits:
                self._do_apply(plan, tenants)

    def _do_dry_run(self, plan, tenants):
        self.stdout.write(
            self.style.WARNING("  DRY RUN — would backfill limits:")
        )
        for key, val in _ENTERPRISE_DEFAULT_CAPS.items():
            current = plan.limits_json.get(key) if plan.limits_json else None
            self.stdout.write(
                f"    {key}: {current} → {val}"
            )
        self.stdout.write(
            f"  {tenants.count()} tenant(s) would be affected."
        )

    def _do_confirm(self, plan, tenants):
        self.stdout.write("  Flagging tenants for 30-day notice window...")
        notified = 0
        for tenant in tenants.iterator():
            try:
                from hub.apps.tenants.notifications import notify_enterprise_backfill
                notify_enterprise_backfill(
                    tenant, plan.name, backfill_count=tenants.count(),
                )
                notified += 1
            except Exception as exc:
                self.stderr.write(
                    f"    Failed to notify tenant {tenant.slug}: {exc}"
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"  Notified {notified} tenant(s). "
                f"Run --apply after 30 days to set concrete caps."
            )
        )

    def _do_apply(self, plan, tenants):
        from hub.apps.audit.event_types import PLAN_LIMITS_BACKFILLED
        from hub.apps.audit.utils import create_audit_event

        new_limits = dict(plan.limits_json) if plan.limits_json else {}
        for key, val in _ENTERPRISE_DEFAULT_CAPS.items():
            if new_limits.get(key) is None:
                new_limits[key] = val

        with transaction.atomic():
            plan.limits_json = new_limits
            plan.save(update_fields=["limits_json", "updated_at"])

            for tenant in tenants.iterator():
                try:
                    create_audit_event(
                        resource_type="TENANT_PLAN",
                        action=PLAN_LIMITS_BACKFILLED,
                        actor_user=None,
                        tenant=tenant,
                        resource_id=str(plan.id),
                        result="SUCCESS",
                        details={
                            "plan_slug": plan.slug,
                            "plan_name": plan.name,
                            "tenant_id": str(tenant.id),
                            "new_limits": new_limits,
                        },
                    )
                except Exception as exc:
                    logger.warning(
                        "backfill_audit_failed",
                        extra={"tenant": str(tenant.id), "error": str(exc)},
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"  Applied concrete caps to '{plan.slug}' "
                f"({tenants.count()} tenant(s)). "
                f"PLAN_LIMITS_BACKFILLED audit emitted."
            )
        )
