"""
285.9.4.15 — Cleanup orphaned dbt project clones.

Removes ``/tmp/meshant_dbt_*`` directories older than the specified
threshold.  Designed for cron / scheduled Prefect flow to prevent
tmpfs accumulation on long-running worker hosts.
"""

import argparse
import os
import shutil
import time

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Remove orphaned dbt project work directories older than N days."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=7,
            help="Remove directories older than this many days (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List directories that would be removed without deleting them",
        )

    def handle(self, **options) -> None:
        older_than_days: int = options["older_than_days"]
        dry_run: bool = options["dry_run"]
        cutoff = time.time() - (older_than_days * 86400)

        removed = 0

        if not os.path.isdir("/tmp"):
            self.stdout.write("No /tmp directory found.")
            return

        for entry in os.listdir("/tmp"):
            if not entry.startswith("meshant_dbt_"):
                continue

            full_path = os.path.join("/tmp", entry)
            if not os.path.isdir(full_path):
                continue

            try:
                mtime = os.path.getmtime(full_path)
            except OSError:
                continue

            if mtime < cutoff:
                if dry_run:
                    self.stdout.write(f"[DRY RUN] Would remove: {full_path}")
                else:
                    try:
                        shutil.rmtree(full_path)
                        self.stdout.write(f"Removed: {full_path}")
                        removed += 1
                    except OSError as exc:
                        self.stderr.write(f"Failed to remove {full_path}: {exc}")

        if dry_run:
            self.stdout.write(f"Dry run complete. {removed} directories would be removed.")
        else:
            self.stdout.write(f"Cleanup complete. {removed} directories removed.")
