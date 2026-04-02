"""
Phase 26.15.2 — Management command for contract re-normalization.

Usage:
    python manage.py renormalize_contracts --spec-version 3.1.0
    python manage.py renormalize_contracts --spec-version 3.1.0 --dry-run
    python manage.py renormalize_contracts --spec-version 3.1.0 --tenant-id UUID
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Re-normalize contracts for a given spec version. "
        "In live mode, enqueues an async RQ task."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--spec-version",
            required=True,
            help="Spec version to re-normalize (e.g. 3.1.0)",
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict to a single tenant UUID",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Contracts per batch (default: 200)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview without writing to DB",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            default=False,
            help="Run synchronously (no RQ queue)",
        )

    def handle(self, *args, **options):
        spec_version = options["spec_version"]
        tenant_id = options["tenant_id"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        sync = options["sync"]

        if spec_version != "3.1.0":
            self.stderr.write(
                self.style.ERROR(
                    f"Only --spec-version 3.1.0 is supported"
                )
            )
            return

        from hub.apps.contracts.tasks import (
            renormalize_contracts_v310,
        )

        if dry_run or sync:
            self.stdout.write(
                f"Running {'dry-run' if dry_run else 'sync'}"
                f" re-normalization for v{spec_version}"
                f" (batch_size={batch_size})"
            )
            result = renormalize_contracts_v310(
                tenant_id=tenant_id,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Complete: {result.get('processed', 0)}"
                    f" processed,"
                    f" {result.get('failed', 0)} failed"
                )
            )
            if dry_run and result.get("dry_run_warnings"):
                for cid, warns in result[
                    "dry_run_warnings"
                ].items():
                    self.stdout.write(
                        f"  {cid}: {len(warns)} warning(s)"
                    )
        else:
            # Enqueue as RQ task
            import django_rq

            queue = django_rq.get_queue("job_default")
            job = queue.enqueue(
                renormalize_contracts_v310,
                tenant_id=tenant_id,
                batch_size=batch_size,
                dry_run=False,
                job_timeout=3600,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enqueued renormalize_contracts_v310"
                    f" on job_default — RQ job ID: {job.id}"
                )
            )
