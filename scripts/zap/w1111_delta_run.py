#!/usr/bin/env python3
"""W11.11 — DAST delta-run orchestrator (oss-release-remediation).

The GitHub workflow's ``zap-delta-gate`` job calls this script after
downloading every surface's ZAP ``-J`` report: it runs the GATE-64
delta checker (``scripts/check_zap_delta.py``) per surface against the
committed baselines, writes the machine-readable delta reports, emits a
structured ledger row for the phase-232 pen-test ledger consumer, and
fails when ANY surface is missing or reports a new HIGH (the W11.11
acceptance: delta vs baseline zero-new-highs).

A missing scan report is a FAILURE, never a skip — the environment
policy (CI raises instead of skipping) applies to DAST evidence too.

Usage:
  python scripts/zap/w1111_delta_run.py --input-dir zap-input --out-dir delta-out
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKER = PROJECT_ROOT / "scripts" / "check_zap_delta.py"
DEFAULT_MANIFEST = PROJECT_ROOT / "scripts" / "zap" / "w1111_role_matrix.json"
BASELINE_DIR = PROJECT_ROOT / "docs" / "security" / "zap" / "baselines"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="downloaded ZAP -J reports")
    parser.add_argument("--out-dir", required=True, help="delta report output directory")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--baseline-dir", default=str(BASELINE_DIR), help="baseline directory")
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    baseline_dir = Path(args.baseline_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    results: dict[str, dict] = {}
    for surface in manifest["surfaces"]:
        key = surface["key"]
        scan = input_dir / surface["report_file"]
        baseline = baseline_dir / surface["baseline"]
        report = out_dir / f"delta-{key}.json"

        if not scan.is_file():
            print(f"::error::missing ZAP report for {key}: {scan}")
            results[key] = {"verdict": "MISSING", "detail": f"report not found: {scan.name}"}
            continue

        if not baseline.is_file():
            print(
                f"::error::missing baseline for {key}: {baseline} — "
                "establish it with the deliberate re-baseline step "
                "(REBASELINE=1 locally; a reviewed PR against hosted staging)"
            )
            results[key] = {
                "verdict": "NO_BASELINE",
                "detail": f"baseline not found: {baseline.name}",
            }
            continue

        proc = subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--scan",
                str(scan),
                "--baseline",
                str(baseline),
                "--report",
                str(report),
                "--surface",
                key,
                "--ci",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(report.read_text(encoding="utf-8"))
        results[key] = {
            "verdict": payload["verdict"],
            "new_highs": len(payload["new_highs"]),
            "escalated": len(payload["escalated"]),
            "resolved_highs": payload["resolved_high_count"],
            "new_medium_low": payload["new_medium_low_count"],
            "checker_exit": proc.returncode,
        }
        print(proc.stdout.strip())

    failed = [k for k, r in results.items() if r["verdict"] in ("FAIL", "MISSING")]

    run_url = (
        f"{os.environ['SERVER']}/{os.environ['REPO']}/actions/runs/{os.environ['RUN_ID']}"
        if os.environ.get("SERVER") and os.environ.get("REPO") and os.environ.get("RUN_ID")
        else "local"
    )
    row = {
        "kind": "zap-delta",
        "run_date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "run_url": run_url,
        "target": os.environ.get("ZAP_TARGET", ""),
        "surfaces": results,
        "gate": "GATE-64",
        "outcome": "FAIL" if failed else "PASS",
    }
    (out_dir / "ledger-row.json").write_text(json.dumps(row, indent=2) + "\n")

    lines = [
        "# W11.11 authenticated ZAP DAST — delta vs baseline",
        "",
        "| Surface | Verdict | New highs | Escalated | Resolved | New M/L |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for key, result in results.items():
        lines.append(
            f"| {key} | {result['verdict']} | {result.get('new_highs', '')} | "
            f"{result.get('escalated', '')} | {result.get('resolved_highs', '')} | "
            f"{result.get('new_medium_low', '')} |"
        )
    summary = "\n".join(lines) + "\n"
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(summary)
    print(summary)

    if failed:
        print(f"::error::GATE-64 FAIL — new highs on: {', '.join(failed)}")
        return 1
    print("GATE-64 PASS — zero new highs across all surfaces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
