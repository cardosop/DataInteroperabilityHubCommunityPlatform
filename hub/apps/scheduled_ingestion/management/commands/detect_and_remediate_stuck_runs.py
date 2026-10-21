"""
Management command to detect and remediate stuck scheduled ingestion runs.

W3.5 (R2-P4) — the lease contract: a run is stuck when it is old AND
its last heartbeat is stale or missing (a fresh heartbeat means the
worker is alive and the run is never touched). Detection covers
RUNNING runs (including NULL ``started_at``) and PENDING runs the
worker never picked up (aged by ``created_at``).

Remediation: check the Prefect flow run (when one exists) and mirror
its terminal state; otherwise mark FAILED with the stuck message.
Scheduled as a CronJob (helm) — see the runbook for the compose
invocation.

Usage:
    python manage.py detect_and_remediate_stuck_runs
    python manage.py detect_and_remediate_stuck_runs --threshold-hours 3
    python manage.py detect_and_remediate_stuck_runs --dry-run
"""

import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun, ScheduledIngestionRunStatus
from hub.apps.scheduled_ingestion.stuck_run_detection import (
    fetch_prefect_flow_run_status,
    stuck_run_predicate,
)


class Command(BaseCommand):
    help = "Detect and remediate stuck scheduled ingestion runs"

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
                f"Detecting stuck runs (threshold: {threshold_hours} hours, dry-run: {dry_run})"
            )
        )

        stuck_runs = ScheduledIngestionRun.objects.filter(
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
            duration = timezone.now() - started
            self.stdout.write(
                f"\n  Run ID: {run.id}"
                f"\n    Status: {run.status}"
                f"\n    Scheduled Ingestion ID: {run.scheduled_ingestion_id}"
                f"\n    Prefect Flow Run ID: {run.prefect_flow_run_id or 'N/A'}"
                f"\n    Started At: {run.started_at or 'N/A (created ' + str(run.created_at) + ')'}"
                f"\n    Last Heartbeat: {run.heartbeat_at or 'N/A'}"
                f"\n    Age: {duration}"
                f"\n    Files Found: {run.files_found}"
                f"\n    Files Processed: {run.files_processed}"
            )

            if dry_run:
                self.stdout.write(self.style.WARNING("    [DRY RUN] Would remediate this run"))
                continue

            try:
                # Check Prefect flow run status
                prefect_status = None
                if run.prefect_flow_run_id:
                    prefect_status = fetch_prefect_flow_run_status(
                        run.prefect_flow_run_id,
                        on_warning=lambda msg: self.stdout.write(
                            self.style.WARNING(f"    ⚠️  {msg}")
                        ),
                    )

                # Determine new status
                if prefect_status:
                    prefect_state_type = prefect_status.get("state_type", "").upper()
                    self.stdout.write(f"    Prefect Flow Status: {prefect_state_type}")

                    if prefect_state_type in ("CANCELLED", "FAILED"):
                        # Update hub run to match Prefect status
                        new_status = (
                            ScheduledIngestionRunStatus.CANCELLED
                            if prefect_state_type == "CANCELLED"
                            else ScheduledIngestionRunStatus.FAILED
                        )
                        run.status = new_status
                        run.error_message = (
                            f"Prefect flow run {prefect_state_type.lower()}; "
                            f"hub run status updated by stuck-run detection"
                        )
                        run.completed_at = timezone.now()
                        run.save(
                            update_fields=[
                                "status",
                                "error_message",
                                "completed_at",
                                "updated_at",
                            ]
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f"    ✅ Updated hub run to {new_status}")
                        )
                        self._sync_dlq(run)
                        remediated_count += 1
                    elif prefect_state_type == "RUNNING":
                        # Prefect flow is still running; check if it's actually stuck
                        # (e.g., no progress for extended period)
                        # For now, mark as FAILED if running > threshold
                        run.status = ScheduledIngestionRunStatus.FAILED
                        run.error_message = (
                            f"Stuck run detected (RUNNING > {threshold_hours}h); "
                            f"Prefect flow still RUNNING but no progress"
                        )
                        run.completed_at = timezone.now()
                        run.save(
                            update_fields=[
                                "status",
                                "error_message",
                                "completed_at",
                                "updated_at",
                            ]
                        )
                        self.stdout.write(
                            self.style.SUCCESS("    ✅ Marked hub run as FAILED (stuck)")
                        )
                        self._sync_dlq(run)
                        remediated_count += 1
                    else:
                        # Prefect flow in other state (PENDING, SCHEDULED, etc.)
                        # Mark hub run as FAILED
                        run.status = ScheduledIngestionRunStatus.FAILED
                        run.error_message = (
                            f"Stuck run detected (RUNNING > {threshold_hours}h); "
                            f"Prefect flow in {prefect_state_type} state"
                        )
                        run.completed_at = timezone.now()
                        run.save(
                            update_fields=[
                                "status",
                                "error_message",
                                "completed_at",
                                "updated_at",
                            ]
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ✅ Marked hub run as FAILED (Prefect: {prefect_state_type})"
                            )
                        )
                        self._sync_dlq(run)
                        remediated_count += 1
                else:
                    # Prefect flow run not found or unreachable
                    was_pending = run.status == ScheduledIngestionRunStatus.PENDING
                    run.status = ScheduledIngestionRunStatus.FAILED
                    if was_pending:
                        run.error_message = (
                            f"Stuck run detected (PENDING > {threshold_hours}h); "
                            f"the worker never picked the run up"
                        )
                    else:
                        run.error_message = (
                            f"Stuck run detected (RUNNING > {threshold_hours}h); "
                            f"Prefect flow run not found or unreachable"
                        )
                    run.completed_at = timezone.now()
                    run.save(
                        update_fields=[
                            "status",
                            "error_message",
                            "completed_at",
                            "updated_at",
                        ]
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            "    ✅ Marked hub run as FAILED (Prefect flow run not found)"
                        )
                    )
                    self._sync_dlq(run)
                    remediated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ❌ Error remediating run: {e}"))
                error_count += 1

        # Summary
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

    def _sync_dlq(self, run: ScheduledIngestionRun) -> None:
        """
        Sync DLQ items from ingestion state after marking a run as FAILED.

        OOM-killed flow pods never report completion, so stuck-run remediation
        is the only opportunity to surface permanently-failed files into the DLQ.
        Failures here are non-fatal — the run is already marked FAILED.
        """
        try:
            synced = DeadLetterQueueManager.sync_from_ingestion_state(
                str(run.scheduled_ingestion_id)
            )
            if synced:
                self.stdout.write(f"    DLQ sync: {synced} item(s) synced")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    ⚠️  DLQ sync failed (non-fatal): {e}"))
