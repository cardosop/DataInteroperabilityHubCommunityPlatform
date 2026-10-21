#!/usr/bin/env python3
"""Phase Q.3 W3.3 — lint debt ratchet (GATE-35).

Runs the REAL ruff check over the tree and compares the per-rule finding
counts against a committed baseline (``scripts/lint_debt_baseline.json``).
Net-accounting semantics: counts are per RULE, not per file, so a finding
moving between files (line-shift churn) does not grow any count and cannot
false-fail the gate. Any rule that EXCEEDS its baseline, or any rule that
appears that has no baseline entry, fails the gate. Counts below baseline
pass (the baseline only ever tightens — run ``--update`` to record the
new floor after a fix wave).

Exit codes: 0 clean, 1 lint debt growth, 2 usage error (missing ruff,
missing baseline, unreadable JSON).

This gate IS the blocking lint job for ``ci.yml`` (W3.5): it replaces the
raw ``ruff check .`` step so the job is genuinely blocking AND green by
construction — a check that can fail only on real growth, never on the
historical baseline.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).resolve().parent / "lint_debt_baseline.json"


def run_ruff(root: Path, ruff_binary: str | None) -> tuple[dict[str, int], str | None]:
    """Run ruff check and return per-rule counts + stderr on failure.

    A missing binary and a failing run are the same error shape — the
    caller only cares that no counts could be produced.
    """
    binary = ruff_binary or shutil.which("ruff")
    if not binary:
        return {}, "ruff executable not found — install ruff first"
    try:
        proc = subprocess.run(
            [binary, "check", str(root), "--output-format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {}, f"ruff executable not found: {binary}"
    counts: dict[str, int] = {}
    if not proc.stdout.strip():
        if proc.returncode == 0:
            return {}, None
        return {}, proc.stderr.strip()
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"ruff emitted non-JSON output: {exc}"
    for entry in payload:
        code = entry.get("code")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts, None


def load_baseline(path: Path) -> dict:
    payload: dict = json.loads(path.read_text())
    return payload


def compare(counts: dict[str, int], baseline: dict) -> list[str]:
    """Return violations: growth in any baselined rule or an unbaselined rule."""
    violations: list[str] = []
    baseline_rules: dict[str, int] = baseline.get("rules", {})
    for rule, count in sorted(counts.items()):
        baseline_count = baseline_rules.get(rule)
        if baseline_count is None:
            violations.append(
                f"{rule}: {count} finding(s) with no baseline entry "
                f"(run --update to ratchet it in, or fix the findings)"
            )
        elif count > baseline_count:
            violations.append(
                f"{rule}: {count} > baseline {baseline_count} "
                f"(net growth of {count - baseline_count})"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint debt net-accounting ratchet")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--ruff-binary", default=None, help="ruff executable (default: PATH)")
    parser.add_argument(
        "--update",
        action="store_true",
        help="regenerate the baseline from the current tree (tighten-only is manual)",
    )
    args = parser.parse_args(argv)

    counts, error = run_ruff(args.root, args.ruff_binary)
    if error:
        print(f"LINT-RATCHET: ruff run failed: {error}")
        return 2

    total = sum(counts.values())

    if args.update:
        baseline = {
            "generated_at": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip(),
            "total": total,
            "rules": counts,
        }
        args.baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"LINT-RATCHET: baseline written — total={total}, {len(counts)} rules")
        return 0

    if not args.baseline.exists():
        print(f"LINT-RATCHET: baseline file missing: {args.baseline} (run --update to create)")
        return 2

    try:
        baseline = load_baseline(args.baseline)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"LINT-RATCHET: baseline unreadable: {exc}")
        return 2

    violations = compare(counts, baseline)
    if violations:
        print(f"LINT-RATCHET: {len(violations)} rule(s) grew past the baseline:")
        for entry in violations:
            print(f"  {entry}")
        return 1
    baseline_total = baseline.get("total", 0)
    print(
        f"LINT-RATCHET: clean — {total} findings across {len(counts)} rules "
        f"(baseline total {baseline_total})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
