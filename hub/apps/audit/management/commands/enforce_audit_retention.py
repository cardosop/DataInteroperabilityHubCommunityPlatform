"""285.14.8.7 — Enforce audit event retention policies.

Deletes audit events past their retention window per category:
  business_rules: 30 days
  compliance:      7 years
  security:        7 years
  billing:         7 years
  general:         90 days

Usage:
    python manage.py enforce_audit_retention --dry-run
    python manage.py enforce_audit_retention --batch-size 10000
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Enforce audit event retention policies by category."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report events that would be deleted without deleting them.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Number of events to delete per batch.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        # Retention windows in days per category
        retention_windows = {
            "business_rules": 30,
            "general": 90,
            "compliance": 2555,   # 7 years
            "security": 2555,
            "billing": 2555,
        }

        self.stdout.write(
            f"enforce_audit_retention: dry_run={dry_run} batch_size={batch_size}"
        )

        from hub.apps.audit.models import AuditEvent
        from datetime import timedelta

        total_deleted = 0
        for category, days in retention_windows.items():
            cutoff = timezone.now() - timedelta(days=days)
            qs = AuditEvent.objects.filter(
                audit_retention_category=category,
                timestamp__lt=cutoff,
            )
            count = qs.count()
            if count == 0:
                continue

            self.stdout.write(
                f"  {category}: {count} events past {days}d retention"
            )

            if not dry_run:
                # Delete in batches to avoid long-running transactions
                while True:
                    ids = list(
                        qs.values_list("pk", flat=True)[:batch_size]
                    )
                    if not ids:
                        break
                    deleted, _ = AuditEvent.objects.filter(
                        pk__in=ids,
                    ).delete()
                    total_deleted += deleted

        if dry_run:
            self.stdout.write("DRY RUN — no events deleted.")
        else:
            self.stdout.write(f"Deleted {total_deleted} expired audit events.")
