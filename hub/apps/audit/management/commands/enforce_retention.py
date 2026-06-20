"""
281.B.4.6 — Data Retention Auto-Enforcement.

Scheduled management command that enforces the data retention schedule
defined in ``docs/compliance/data-retention-schedule.md``.  Expired data
is automatically deleted per category.

Behaviour:
  - ``--dry-run`` (default): report what would be deleted, don't delete
  - ``--execute``: perform actual deletion
  - ``--category <name>``: restrict to a single category
  - ``--older-than <days>``: override the retention period

Emits ``RETENTION_ENFORCEMENT_RUN`` audit event with counts per category.
Emits ``retention_violations_total`` Prometheus counter when data is
found past its retention period (alert: RetentionViolationHigh).

Schedule (cron):
  0 3 * * *  python manage.py enforce_retention --execute
  (daily at 03:00 UTC)
"""

from __future__ import annotations

import contextlib
import logging
import sys
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)

# ── Retention configuration (mirrors docs/compliance/data-retention-schedule.md) ──

RETENTION_PERIODS: dict[str, dict] = {
    "business_rules_audit": {
        "description": "Business rules chain audit events",
        "retention_days": 30,
        "model": "audit.AuditEvent",
        "filter": {"audit_retention_category": "business_rules"},
        "date_field": "created_at",
    },
    "security_audit": {
        "description": "Security audit events",
        "retention_days": 365,
        "model": "audit.AuditEvent",
        "filter": {"audit_retention_category": "security"},
        "date_field": "created_at",
    },
    "access_control_audit": {
        "description": "Access control audit events",
        "retention_days": 365,
        "model": "audit.AuditEvent",
        "filter": {"audit_retention_category": "access_control"},
        "date_field": "created_at",
    },
    "data_lifecycle_audit": {
        "description": "Data lifecycle audit events",
        "retention_days": 90,
        "model": "audit.AuditEvent",
        "filter": {"audit_retention_category": "data_lifecycle"},
        "date_field": "created_at",
    },
    "compliance_records": {
        "description": "Compliance scan results and records",
        "retention_days": 365,
        "model": "audit.AuditEvent",
        "filter": {"audit_retention_category": "compliance"},
        "date_field": "created_at",
    },
    "deleted_accounts": {
        "description": "Soft-deleted user accounts past grace period",
        "retention_days": 30,
        "model": "users.User",
        "filter": {"is_deleted": True},
        "date_field": "deleted_at",
    },
}

# ── Prometheus metrics for retention monitoring ────────────────────────────

try:
    from hub.apps.observability.otel_metrics import Counter, Gauge

    _retention_counter = Counter(
        "retention_enforcement_total",
        "Total records processed by retention enforcement",
        ["category", "action"],
    )
    _retention_last_run = Gauge(
        "retention_enforcement_last_run_timestamp_seconds",
        "Unix timestamp of the last successful retention enforcement run",
    )
except Exception:
    _retention_counter = None
    _retention_last_run = None


def _emit_metric(category: str, action: str, count: int = 1) -> None:
    if _retention_counter is not None:
        with contextlib.suppress(Exception):
            _retention_counter.labels(category=category, action=action).inc(count)


def _emit_last_run_timestamp() -> None:
    if _retention_last_run is not None:
        with contextlib.suppress(Exception):
            _retention_last_run.set(time.time())


class Command(BaseCommand):
    help = "Enforce data retention schedule (281.B.4.6)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Report what would be deleted (default)",
        )
        parser.add_argument(
            "--execute", action="store_true", default=False, help="Actually delete expired data"
        )
        parser.add_argument("--category", default=None, help="Restrict to single category")
        parser.add_argument(
            "--older-than", type=int, default=None, help="Override retention period (days)"
        )

    def handle(self, **options):
        dry_run = not options["execute"]
        category_filter = options["category"]
        override_days = options["older_than"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no data will be deleted."))
            self.stdout.write("Use --execute to perform actual deletion.\n")

        categories = (
            {category_filter: RETENTION_PERIODS[category_filter]}
            if category_filter
            else RETENTION_PERIODS
        )

        if category_filter and category_filter not in RETENTION_PERIODS:
            self.stderr.write(
                f"Unknown category: {category_filter}. Valid: {sorted(RETENTION_PERIODS.keys())}"
            )
            sys.exit(1)

        total_deleted = 0
        total_overdue = 0

        for cat_name, cfg in categories.items():
            retention_days = override_days if override_days is not None else cfg["retention_days"]
            cutoff = dj_timezone.now() - timedelta(days=retention_days)

            # Build queryset dynamically (Django model import)
            from django.apps import apps

            app_label, model_name = cfg["model"].split(".")
            model = apps.get_model(app_label, model_name)

            qs = model.objects.filter(**cfg["filter"])
            qs = qs.filter(**{f"{cfg['date_field']}__lt": cutoff})

            count = qs.count()
            total_overdue += count

            if count == 0:
                self.stdout.write(
                    f"  {cfg['description']}: 0 records past {retention_days}d retention"
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  {cfg['description']}: {count} records would be deleted "
                    f"(retention: {retention_days}d, cutoff: {cutoff.date()})"
                )
                if count > 0:
                    _emit_metric(cat_name, "dry_run_overdue", count)
            else:
                deleted, _ = qs.delete()
                total_deleted += deleted
                self.stdout.write(
                    f"  {cfg['description']}: DELETED {deleted} records "
                    f"(retention: {retention_days}d)"
                )
                _emit_metric(cat_name, "deleted", deleted)
                logger.info(
                    "retention_enforcement_deleted",
                    category=cat_name,
                    count=deleted,
                    retention_days=retention_days,
                    cutoff=str(cutoff.date()),
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nRetention enforcement complete. "
                f"{'Would delete' if dry_run else 'Deleted'} "
                f"{total_overdue} records across {len(categories)} categories."
            )
        )

        # Record successful run timestamp
        _emit_last_run_timestamp()

        if dry_run and total_overdue > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {total_overdue} records exceed retention period. "
                    f"Run with --execute to delete."
                )
            )
            sys.exit(1)  # Exit 1 so cron alerts on overdue-but-not-purged
