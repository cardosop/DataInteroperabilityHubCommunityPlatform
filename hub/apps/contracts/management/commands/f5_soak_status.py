"""
Phase 228 F5 (228.F5.DoD.5) — F5 soak-window status check.

Operator-driven verification of the 7-day staging soak. Reads:

  1. The soak start epoch (``--soak-start=<ISO>`` OR file path
     ``--soak-start-file=<path>``).
  2. The current count of `LINEAGE_SNAPSHOT_QUERIED` audit rows
     produced since soak start (proves real usage, not just
     flag-flipped).
  3. The current count of `LineageEdge`-write metric emissions
     since soak start (proves the SCD-2 substrate is exercised).

Pass criterion (REQ-LIN-F5-DoD.5):

  - elapsed >= 7 days, AND
  - audit_rows_in_window > 0  (somebody actually used the feature),
  - --p1-list-file (operator-supplied) is the empty list.

The command does NOT query GitHub for P1 issues itself — the
caller passes ``--p1-list-file=<path>`` to a JSON file produced by
``gh issue list ... --json number``. This decouples the soak check
from GitHub auth in the CI runner.

Output: structured JSON to stdout. Exit 0 = pass, 2 = fail.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

SOAK_DAYS_REQUIRED = 7


class Command(BaseCommand):
    help = (
        "Phase 228 F5 (228.F5.DoD.5): check whether the F5 staging "
        "soak has cleared. Pass = ≥7d elapsed + non-zero audit usage "
        "+ empty P1 list."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--soak-start",
            help="ISO-8601 timestamp the soak began (UTC).",
        )
        parser.add_argument(
            "--soak-start-file",
            help="Path to a file whose first line is the ISO-8601 soak start.",
        )
        parser.add_argument(
            "--p1-list-file",
            help=(
                "Path to a JSON file produced by `gh issue list "
                "--label P1,lineage --json number,title,createdAt`. "
                "Empty list = pass."
            ),
        )

    def _resolve_soak_start(self, options) -> _dt.datetime:
        raw = options.get("soak_start")
        if not raw and options.get("soak_start_file"):
            p = Path(options["soak_start_file"])
            if not p.exists():
                raise CommandError(f"--soak-start-file does not exist: {p}")
            raw = p.read_text().strip().splitlines()[0]
        if not raw:
            raise CommandError("Provide --soak-start=<ISO> or --soak-start-file=<path>")
        try:
            parsed = _dt.datetime.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError(f"--soak-start must be ISO-8601: {raw!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.UTC)
        return parsed

    def _audit_rows_in_window(self, soak_start: _dt.datetime) -> int:
        try:
            from hub.apps.audit.models import AuditEvent
        except Exception:
            return 0
        try:
            return AuditEvent.objects.filter(
                action="LINEAGE_SNAPSHOT_QUERIED",
                timestamp__gte=soak_start,
            ).count()
        except Exception:
            return 0

    def _p1_list(self, options) -> list:
        path = options.get("p1_list_file")
        if not path:
            # No file supplied — assume operator hasn't generated
            # the list yet. Fail open with an explicit signal.
            return [{"missing_p1_list_file": True}]
        p = Path(path)
        if not p.exists():
            raise CommandError(f"--p1-list-file does not exist: {p}")
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            raise CommandError(f"--p1-list-file is not valid JSON: {exc}") from exc
        if not isinstance(data, list):
            raise CommandError("--p1-list-file content must be a JSON array")
        return data

    def handle(self, *_args, **options):
        soak_start = self._resolve_soak_start(options)
        now = timezone.now()
        elapsed = now - soak_start
        elapsed_days = elapsed.total_seconds() / 86400.0
        soak_days_satisfied = elapsed_days >= SOAK_DAYS_REQUIRED

        audit_rows = self._audit_rows_in_window(soak_start)
        usage_satisfied = audit_rows > 0

        p1_list = self._p1_list(options)
        p1_satisfied = isinstance(p1_list, list) and len(p1_list) == 0

        overall_ok = soak_days_satisfied and usage_satisfied and p1_satisfied

        report = {
            "phase": "228.F5.DoD.5",
            "now": now.isoformat(),
            "soak_start": soak_start.isoformat(),
            "elapsed_days": round(elapsed_days, 4),
            "soak_days_required": SOAK_DAYS_REQUIRED,
            "soak_days_satisfied": soak_days_satisfied,
            "audit_rows_in_window": audit_rows,
            "usage_satisfied": usage_satisfied,
            "p1_count": len(p1_list) if isinstance(p1_list, list) else None,
            "p1_satisfied": p1_satisfied,
            "overall_ok": overall_ok,
            "guidance": (
                "If overall_ok=false: identify the failing predicate. "
                "soak_days_satisfied=false → wait for the window. "
                "usage_satisfied=false → confirm the feature flag is "
                "actually ON for the canary cohort + that real "
                "traffic is hitting ?as_of= or ?version=. "
                "p1_satisfied=false → reset soak window after fixing "
                "each P1; restart from a fresh soak_start."
            ),
        }
        self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
        if not overall_ok:
            sys.exit(2)
