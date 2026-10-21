"""
Management command to detect and remediate stuck scheduled export runs.

W3.5 (R2-P4) — the lease contract (shared with the ingestion detector
via ``hub.apps.scheduled_ingestion.stuck_run_detection``): a RUNNING
export run is stuck when it is old AND its last heartbeat is stale or
missing (a fresh heartbeat means the worker is alive and the run is
never touched). NULL ``started_at`` never hides a run.

Remediation: check the Prefect flow run (when one exists) and mirror
its terminal state; otherwise mark FAILED with the stuck message.
Scheduled as a CronJob (helm) — see the runbook for the compose
invocation.

Usage:
    python manage.py detect_and_remediate_stuck_export_runs
    python manage.py detect_and_remediate_stuck_export_runs --threshold-hours 3
    python manage.py detect_and_remediate_stuck_export_runs --dry-run
"""

import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.scheduled_export.models import (
    ScheduledExportRun,
    ScheduledExportRunStatus,
)
from hub.apps.scheduled_ingestion.stuck_run_detection import (
    fetch_prefect_flow_run_status,
    stuck_run_predicate,
)


class Command(BaseCommand):
    help = "Detect and remediate stuck scheduled export runs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold-hours",
            type=int,
            default=int(os.getenv("STUCK_RUN_THRESHOLD_HOURS", "2")),
            help="Threshold in hours for considering a run stuck (default: 2)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Dry run mode: detect stuck runs but do not remediate",
        )

    def handle(self, *_args, **options):
        threshold_hours = options["threshold_hours"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Detecting stuck export runs "
                f"(threshold: {threshold_hours} hours, dry-run: {dry_run})"
            )
        )

        stuck_runs = ScheduledExportRun.objects.filter(
            stuck_run_predicate(threshold_hours)
        ).order_by("started_at")

        if not stuck_runs.exists():
            self.stdout.write(self.style.SUCCESS("No stuck runs found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {stuck_runs.count()} stuck run(s):"))

        remediated_count = 0
        error_count = 0

        for run in stuck_runs:
            started = run.started_at or run.created_at
            self.stdout.write(
                f"\n  Run ID: {run.id}"
                f"\n    Status: {run.status}"
                f"\n    Scheduled Export ID: {run.scheduled_export_id}"
                f"\n    Prefect Flow Run ID: {run.prefect_flow_run_id or 'N/A'}"
                f"\n    Started At: {run.started_at or 'N/A (created ' + str(run.created_at) + ')'}"
                f"\n    Last Heartbeat: {run.heartbeat_at or 'N/A'}"
                f"\n    Age: {timezone.now() - started}"
                f"\n    Items Found: {run.items_found}"
                f"\n    Items Exported: {run.items_exported}"
            )

            if dry_run:
                self.stdout.write(self.style.WARNING("    [DRY RUN] Would remediate this run"))
                continue

            try:
                prefect_status = None
                if run.prefect_flow_run_id:
                    prefect_status = fetch_prefect_flow_run_status(
                        run.prefect_flow_run_id,
                        on_warning=lambda msg: self.stdout.write(
                            self.style.WARNING(f"    ⚠️  {msg}")
                        ),
                    )

                if prefect_status:
                    prefect_state_type = prefect_status.get("state_type", "").upper()
                    self.stdout.write(f"    Prefect Flow Status: {prefect_state_type}")

                    if prefect_state_type == "CANCELLED":
                        run.status = ScheduledExportRunStatus.CANCELLED
                        run.completed_at = timezone.now()
                        run.save(update_fields=["status", "completed_at", "updated_at"])
                        self.stdout.write(self.style.SUCCESS("    ✅ Updated hub run to CANCELLED"))
                        remediated_count += 1
                    else:
                        run.status = ScheduledExportRunStatus.FAILED
                        run.completed_at = timezone.now()
                        run.save(update_fields=["status", "completed_at", "updated_at"])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ✅ Marked hub run as FAILED (Prefect: {prefect_state_type})"
                            )
                        )
                        remediated_count += 1
                else:
                    run.status = ScheduledExportRunStatus.FAILED
                    # The export run carries errors in result_json (the
                    # canonical carrier the notifications read) — the
                    # model has no error_message column.
                    run.result_json = {
                        **(run.result_json or {}),
                        "error_message": (
                            f"Stuck run detected (RUNNING > {threshold_hours}h); "
                            f"Prefect flow run not found or unreachable"
                        ),
                    }
                    run.completed_at = timezone.now()
                    run.save(
                        update_fields=[
                            "status",
                            "result_json",
                            "completed_at",
                            "updated_at",
                        ]
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            "    ✅ Marked hub run as FAILED (Prefect flow run not found)"
                        )
                    )
                    remediated_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ❌ Error remediating run: {e}"))
                error_count += 1

        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Found {stuck_runs.count()} stuck run(s) (no changes made)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Remediation complete: {remediated_count} run(s) remediated, "
                    f"{error_count} error(s)"
                )
            )
