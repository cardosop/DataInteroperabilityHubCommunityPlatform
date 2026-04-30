"""
Phase 227 Wave 0 (227.0.1) — turn-key capture command.

Wraps `renormalize_contracts --filter=structureless --dry-run --output=json`
with the operator-friendly defaults specified in the runbook:

* Auto-creates `audit-reports/` if missing.
* Auto-names the file `structureless-pre-rollout-YYYY-MM-DD.jsonl`.
* Prints a path + count summary to stdout for the operator.
* Idempotent — overwrites today's file with a warning so re-running
  during an incident is safe.
* Accepts `--tenant-id` for per-tenant scoping.

Why a separate command instead of a shell wrapper
-------------------------------------------------
A shell one-liner depends on operator memory for the directory and
filename convention. Drift between the runbook and reality is the
single most common Wave-0 failure mode (per Phase 227 doctrine).
Wrapping in a Django command makes the convention executable code
that's covered by tests at `test_wave0_capture_command.py`.
"""
from __future__ import annotations

from datetime import date
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 0 (227.0.1): capture the current structureless-"
        "contract population to a dated JSONL artefact under audit-reports/."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--audit-reports-dir",
            default="audit-reports",
            help=(
                "Directory to write the JSONL artefact into. "
                "Auto-created if missing. Defaults to 'audit-reports' "
                "relative to the working directory."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict the capture to a single tenant UUID.",
        )

    def handle(self, *_args, **options):
        audit_dir = Path(options["audit_reports_dir"])
        tenant_id = options.get("tenant_id")
        today = date.today().isoformat()
        artefact = audit_dir / f"structureless-pre-rollout-{today}.jsonl"

        # Idempotency — overwrite today's file with a clear warning so the
        # operator notices when a re-run is unintended (e.g. partial CSV
        # uploaded vs already-archived report).
        if artefact.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  [warn] {artefact} exists; overwriting."
                )
            )

        audit_dir.mkdir(parents=True, exist_ok=True)

        # Run the existing diagnosis path with stdout captured. We do
        # NOT pipe via the shell because we want the management command
        # framework to enforce the same arg parsing the runbook
        # documents.
        capture = StringIO()
        renorm_args = [
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=json",
        ]
        if tenant_id:
            renorm_args.append(f"--tenant-id={tenant_id}")

        call_command(*renorm_args, stdout=capture)

        body = capture.getvalue()
        artefact.write_text(body, encoding="utf-8")

        # Count the JSONL rows for the summary. Header / trailer lines
        # are prefixed with `#` and excluded.
        json_rows = [
            ln for ln in body.splitlines()
            if ln.startswith("{") and ln.rstrip().endswith("}")
        ]
        structureless_count = len(json_rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"  Wrote {artefact} ({structureless_count} structureless rows)"
            )
        )
        if structureless_count == 0:
            self.stdout.write(
                "  Note: zero rows. Verify the staging-clone DB has "
                "the expected contract corpus before considering this "
                "a clean Wave 0 result."
            )
        else:
            self.stdout.write(
                f"  Next: review with "
                f"`jq -c 'select(.contract_id) | .classification' {artefact} "
                f"| sort | uniq -c`"
            )
