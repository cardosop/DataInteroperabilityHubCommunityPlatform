"""
Phase 25.7.1 — Django management command for periodic Prefect status reconciliation.

Finds ScheduledIngestionRun and ScheduledExportRun records stuck in
RUNNING/PENDING state (updated_at older than 5 minutes) and reconciles
their status with the Prefect integration service.

Designed to run every 5 minutes via a Kubernetes CronJob.
"""

import structlog
from django.core.management.base import BaseCommand

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = (
        "Reconcile RUNNING/PENDING Prefect flow-run statuses with the "
        "integration service. Runs every 5 minutes via CronJob (25.7)."
    )

    def handle(self, *args, **options):
        from django.conf import settings

        if getattr(settings, "MVP_MODE", False):
            self.stdout.write(
                self.style.WARNING("MVP_MODE enabled — skipping Prefect reconciliation.")
            )
            return

        from hub.apps.jobs.tasks_prefect_sync import (
            reconcile_prefect_run_statuses,
        )

        reconciled = reconcile_prefect_run_statuses()
        self.stdout.write(
            self.style.SUCCESS(f"Reconciled {reconciled} stale run(s).")
        )
