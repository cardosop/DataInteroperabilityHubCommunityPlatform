#!/usr/bin/env python3
"""
Phase 228 (228.0.DoD.6) — E2E staging-cycle aggregator.

DoD.6 requires "E2E baseline strict-count assertion green for ≥7
staging cycles". Each staging E2E run appends one record to a
JSONL history file (one line per cycle). This script reads the
history, verifies the strict-content + empty-state spec each ran
with status ``passed``, and reports the consecutive-green-streak
count. Exits non-zero unless the streak is ≥ the threshold.

History file format
-------------------

JSONL — one JSON object per line. Canonical record shape::

    {
      "cycle_id": "staging-2026-04-30-cycle-3",   # operator-supplied
      "timestamp": "2026-04-30T12:00:00Z",
      "lineage_strict_content_status": "passed",  # passed|failed|skipped
      "lineage_empty_state_status": "passed",
      "commit_sha": "<sha>",                      # build under test
      "playwright_run_url": "<url>"               # CI artefact link
    }

The file lives at ``audit-reports/lineage-e2e-cycles.jsonl`` by
default; override via ``--history-file``.

The CI workflow appends a fresh record with ``--append`` after
every staging E2E run; the daily cron (or a pre-merge gate) calls
``--report`` to verify the streak.

Usage
-----

    # Append today's cycle (CI workflow does this):
    python scripts/lineage_e2e_cycle_report.py append \\
        --cycle-id="staging-$(date +%F)-cycle-1" \\
        --strict-status=passed --empty-status=passed \\
        --commit-sha="$GITHUB_SHA"

    # Verify the streak (gate):
    python scripts/lineage_e2e_cycle_report.py report --threshold=7

Exit codes
----------

* 0 — streak ≥ threshold (or report mode reading a history that
  satisfies the gate).
* 1 — streak < threshold.
* 2 — malformed history file / missing required arg.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections.abc import Iterable
from pathlib import Path

DEFAULT_HISTORY_FILE = "audit-reports/lineage-e2e-cycles.jsonl"
DEFAULT_THRESHOLD = 7

CANONICAL_KEYS = (
    "cycle_id",
    "timestamp",
    "lineage_strict_content_status",
    "lineage_empty_state_status",
)


def _load_history(path: Path) -> list[dict]:
    """Return one parsed dict per JSONL line. Skips blank lines.
    Raises ValueError on malformed JSON so the CI gate fails fast
    rather than producing a misleading streak count."""
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSONL at {path}: {raw!r} — {exc}") from exc
    return out


def _is_green(record: dict) -> bool:
    """A record counts as 'green' iff BOTH spec statuses are
    ``passed``. Any other value (failed / skipped / missing) breaks
    the streak — DoD.6 requires the strict-content assertion to be
    green; a skip is not a pass."""
    return (
        record.get("lineage_strict_content_status") == "passed"
        and record.get("lineage_empty_state_status") == "passed"
    )


def compute_consecutive_green_streak(history: Iterable[dict]) -> int:
    """Return the length of the consecutive-green tail of the history.

    The streak counts cycles in the order they were appended (oldest
    first; newest last). The streak ends as soon as a non-green
    cycle is encountered when scanning from the END backwards. If
    the most-recent cycle is non-green, streak is 0 — even if every
    earlier cycle was green.
    """
    streak = 0
    for record in reversed(list(history)):
        if _is_green(record):
            streak += 1
        else:
            break
    return streak


def cmd_append(args: argparse.Namespace) -> int:
    """Append a cycle record to the history file."""
    record = {
        "cycle_id": args.cycle_id,
        "timestamp": _dt.datetime.now(_dt.UTC).isoformat(),
        "lineage_strict_content_status": args.strict_status,
        "lineage_empty_state_status": args.empty_status,
        "commit_sha": args.commit_sha or "",
        "playwright_run_url": args.run_url or "",
    }
    path = Path(args.history_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"Appended cycle {args.cycle_id!r} to {path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Verify the consecutive-green streak meets the threshold."""
    path = Path(args.history_file)
    try:
        history = _load_history(path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    streak = compute_consecutive_green_streak(history)
    total = len(history)
    last = history[-1] if history else None

    report = {
        "phase": "228.0.DoD.6",
        "history_file": str(path),
        "total_cycles": total,
        "consecutive_green_streak": streak,
        "threshold": args.threshold,
        "status": "ok" if streak >= args.threshold else "INSUFFICIENT",
        "last_cycle_id": (last or {}).get("cycle_id") if last else None,
        "last_cycle_timestamp": (last or {}).get("timestamp") if last else None,
        "checked_at": _dt.datetime.now(_dt.UTC).isoformat(),
    }
    print(json.dumps(report, sort_keys=True))
    if streak < args.threshold:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    sub = parser.add_subparsers(dest="cmd", required=True)

    append = sub.add_parser("append", help="Append a cycle record.")
    append.add_argument("--history-file", default=DEFAULT_HISTORY_FILE)
    append.add_argument("--cycle-id", required=True)
    append.add_argument(
        "--strict-status",
        required=True,
        choices=("passed", "failed", "skipped"),
    )
    append.add_argument(
        "--empty-status",
        required=True,
        choices=("passed", "failed", "skipped"),
    )
    append.add_argument("--commit-sha", default=None)
    append.add_argument("--run-url", default=None)

    report = sub.add_parser("report", help="Report the streak status.")
    report.add_argument("--history-file", default=DEFAULT_HISTORY_FILE)
    report.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Required consecutive-green streak (default {DEFAULT_THRESHOLD}).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "append":
        return cmd_append(args)
    if args.cmd == "report":
        return cmd_report(args)
    parser.error(f"unknown subcommand {args.cmd!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
