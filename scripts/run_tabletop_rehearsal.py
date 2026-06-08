#!/usr/bin/env python3
"""
Phase 232.DoD.7 tabletop rehearsal runner.

Runs the rehearsal scenario probes via pytest, then composes a
machine-readable summary that maps directly onto a row in
``docs/audit-reports/232-tabletop-ledger.md``.

Use during development AND in CI:

* Locally: ``python scripts/run_tabletop_rehearsal.py`` runs the suite
  in-process and prints the rendered summary table.
* CI: a new GitHub Actions job invokes this script and uploads the
  per-scenario JSON artefacts so the team can review timing trends
  before scheduling the live quarterly tabletop.

The runner does NOT replace the live exercise. It is a **pre-flight**:
a green rehearsal is a necessary-but-insufficient condition for the
live run to even be scheduled. The DoD.7 closure block in the live
ledger is signed only after the live exercise (humans, real seats).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = Path(
    os.environ.get("TABLETOP_REHEARSAL_OUT_DIR", "/tmp/tabletop_rehearsal")
)
DEFAULT_TEST_PATH = REPO_ROOT / "tests" / "integration" / "tabletop_rehearsal"

EXPECTED_SCENARIO_IDS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")


def _run_pytest(out_dir: Path, test_path: Path, extra_args: list[str]) -> int:
    env = os.environ.copy()
    env["TABLETOP_REHEARSAL_OUT_DIR"] = str(out_dir)
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", "tabletop_rehearsal",
        "-q", "--no-header", "--tb=short",
        str(test_path),
    ] + list(extra_args)
    result = subprocess.run(cmd, env=env, cwd=REPO_ROOT)
    return result.returncode


def _collect_records(out_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not out_dir.exists():
        return records
    for path in sorted(out_dir.glob("S*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            records.append({
                "scenario_id": path.stem,
                "outcome": "fail",
                "failure_note": f"unparseable JSON: {exc}",
            })
    return records


def _render_summary(records: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Phase 232.DoD.7 tabletop **rehearsal** summary")
    lines.append("")
    lines.append(
        f"Run at: {datetime.now(timezone.utc).isoformat()} (UTC)"
    )
    lines.append("")
    lines.append("| Scenario | Title | Subsystems | Budget (min) | Duration (s) | Outcome | Notes |")
    lines.append("|----------|-------|------------|--------------|--------------|---------|-------|")

    by_id = {r["scenario_id"]: r for r in records if "scenario_id" in r}
    for sid in EXPECTED_SCENARIO_IDS:
        rec = by_id.get(sid)
        if rec is None:
            lines.append(
                f"| {sid} | _not yet implemented_ | _—_ | _—_ | _—_ | "
                f"_skipped_ | scenario test pending — see runbook |"
            )
            continue
        title = rec.get("title", "_?_")
        subs = ", ".join(rec.get("subsystems", []))
        budget = rec.get("budget_minutes", "—")
        dur = rec.get("duration_seconds", 0.0)
        outcome = rec.get("outcome", "fail")
        note = rec.get("failure_note") or "_—_"
        lines.append(
            f"| {sid} | {title} | {subs} | {budget} | "
            f"{dur:.2f} | `{outcome}` | {note} |"
        )

    aggregate = "green"
    for sid in EXPECTED_SCENARIO_IDS:
        rec = by_id.get(sid)
        if rec is None:
            aggregate = "partial"
            continue
        if rec.get("outcome") == "fail":
            aggregate = "red"
            break
        if rec.get("outcome") == "partial":
            aggregate = "partial"

    lines.append("")
    lines.append(f"**Aggregate rehearsal outcome:** `{aggregate}`")
    lines.append("")
    lines.append(
        "Map this row onto the live ledger at "
        "`docs/audit-reports/232-tabletop-ledger.md` only after the "
        "live tabletop exercise has been executed with humans in real "
        "seats — the rehearsal is a pre-flight, not a substitute."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=(
            f"Where scenario JSON artefacts land (default: {DEFAULT_OUT_DIR}). "
            "Cleared before each run."
        ),
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=DEFAULT_TEST_PATH,
        help=f"Pytest path to discover scenarios (default: {DEFAULT_TEST_PATH}).",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="Write the rendered Markdown summary to this path (in addition to stdout).",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip pytest invocation; just aggregate existing JSON artefacts.",
    )
    parser.add_argument(
        "extra_pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra args forwarded to pytest after `--`.",
    )
    args = parser.parse_args()

    if not args.skip_pytest:
        if args.out_dir.exists():
            shutil.rmtree(args.out_dir)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        rc = _run_pytest(args.out_dir, args.test_path, args.extra_pytest_args or [])
    else:
        rc = 0

    records = _collect_records(args.out_dir)
    summary = _render_summary(records)
    print(summary)
    if args.summary_out:
        args.summary_out.write_text(summary + "\n", encoding="utf-8")

    # Exit non-zero if pytest failed OR any scenario record reports fail.
    if rc != 0:
        return rc
    if any(r.get("outcome") == "fail" for r in records):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
