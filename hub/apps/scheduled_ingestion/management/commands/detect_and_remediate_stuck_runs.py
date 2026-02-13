"""
Management command to detect and remediate stuck scheduled ingestion runs.

A run is considered "stuck" if it has been in RUNNING status for longer than
the threshold (default: 2 hours, configurable via STUCK_RUN_THRESHOLD_HOURS).

This command:
1. Finds runs in RUNNING status for > threshold
2. Checks Prefect flow run status (if prefect_flow_run_id exists)
3. Updates hub run status to match Prefect status (if Prefect flow is CANCELLED/FAILED)
4. Marks hub run as FAILED if Prefect flow run not found or unreachable

Usage:
    python manage.py detect_and_remediate_stuck_runs
    python manage.py detect_and_remediate_stuck_runs --threshold-hours 3
    python manage.py detect_and_remediate_stuck_runs --dry-run
"""

import os
import sys
from datetime import timedelta
from typing import Optional

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun, ScheduledIngestionRunStatus


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

    def handle(self, *args, **options):
        threshold_hours = options["threshold_hours"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Detecting stuck runs (threshold: {threshold_hours} hours, dry-run: {dry_run})"
            )
        )

        threshold_time = timezone.now() - timedelta(hours=threshold_hours)
        stuck_runs = ScheduledIngestionRun.objects.filter(
            status=ScheduledIngestionRunStatus.RUNNING, started_at__lt=threshold_time
        ).order_by("started_at")

        if not stuck_runs.exists():
            self.stdout.write(self.style.SUCCESS("No stuck runs found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {stuck_runs.count()} stuck run(s):"))

        remediated_count = 0
        error_count = 0

        for run in stuck_runs:
            duration = timezone.now() - run.started_at
            self.stdout.write(
                f"\n  Run ID: {run.id}"
                f"\n    Scheduled Ingestion ID: {run.scheduled_ingestion_id}"
                f"\n    Prefect Flow Run ID: {run.prefect_flow_run_id or 'N/A'}"
                f"\n    Started At: {run.started_at}"
                f"\n    Running Duration: {duration}"
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
                    prefect_status = self._check_prefect_flow_run_status(run.prefect_flow_run_id)

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
                        remediated_count += 1
                else:
                    # Prefect flow run not found or unreachable
                    run.status = ScheduledIngestionRunStatus.FAILED
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

    def _check_prefect_flow_run_status(self, prefect_flow_run_id: str) -> Optional[dict]:
        """Check Prefect flow run status via Prefect API."""
        prefect_api_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
        prefect_api_key = os.getenv("PREFECT_API_KEY", "")

        headers = {}
        if prefect_api_key:
            headers["Authorization"] = f"Bearer {prefect_api_key}"

        try:
            url = f"{prefect_api_url}/flow_runs/{prefect_flow_run_id}"
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            self.stdout.write(
                self.style.WARNING(f"    ⚠️  Failed to check Prefect flow run status: {e}")
            )
            return None
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"    ⚠️  Error checking Prefect flow run status: {e}")
            )
            return None
