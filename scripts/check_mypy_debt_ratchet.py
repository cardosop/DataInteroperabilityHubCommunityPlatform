#!/usr/bin/env python3
"""Phase Q.1.2/Q.1.3 — mypy debt ratchet (W1).

Runs the REAL mypy invocation over the tree — the exact command the CI
lint job must use (``--explicit-package-bases`` is REQUIRED: without it the
script-module-mapping fatal can crash mypy before any file is checked, the
Phase Q.1.1 crash class) — and compares the error count against a committed
baseline (``scripts/mypy_debt_baseline.json``). Net-accounting: the count is
TOTAL error lines, so a finding moving between files cannot false-fail the
gate. Growth past the baseline fails; ``--update`` ratchets the floor after
a fix wave.

Exit codes: 0 clean, 1 mypy debt growth, 2 usage error (missing mypy,
missing/unreadable baseline).

This gate replaces the old ``mypy ... || true`` + ``continue-on-error``
step in ci.yml — the step that made "MyPy ✓" unfalsifiable (Phase 0.2).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).resolve().parent / "mypy_debt_baseline.json"

# The Q.1.1 contract: the CI invocation MUST carry --explicit-package-bases
# (script-module-mapping fatal otherwise) — keep this in step with ci.yml.
MYPY_FLAGS = ["--explicit-package-bases", "--show-error-codes", "--no-error-summary"]


def _resolve_mypy(explicit: str | None) -> str:
    """Resolve the mypy binary, preferring the repo venv's pinned version.

    The trap this exists to kill: ``shutil.which("mypy")`` on a developer
    host can resolve to a USER-LOCAL mypy of a different major version
    (this machine: ~/.local/bin/mypy = 2.1.0, which exits rc 1 with EMPTY
    stderr under --no-error-summary) — the gate would then count 0 errors
    on a broken tree. The CI-installed mypy lives in the canonical venv;
    resolve there first.
    """
    if explicit:
        return explicit
    repo_venv_mypy = Path(__file__).resolve().parents[1] / "venv" / "bin" / "mypy"
    if repo_venv_mypy.exists():
        return str(repo_venv_mypy)
    return shutil.which("mypy") or (str(sys.executable) + " -m mypy")


def run_mypy(
    root: Path,
    mypy_binary: str | None = None,
    json_report_dir: str | None = None,
) -> tuple[int | None, str | None]:
    """Run mypy over root; return (error-count, stderr-on-failure).

    Error lines are counted from stderr (``: error:`` prefix) — version-proof,
    no junit dependency. rc 0/1 are both RUNS; rc 2 (usage/crash) is a failure.
    ``json_report_dir`` adds ``--json-report <dir>`` for the metrics artifact
    (code-quality.yml) without affecting the count.
    """
    binary = _resolve_mypy(mypy_binary)
    extra = f" --json-report {json_report_dir}" if json_report_dir else ""
    command = f"{binary} {root} {' '.join(MYPY_FLAGS)}{extra}"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, f"mypy executable not found: {binary}"
    if proc.returncode == 2:
        return None, f"mypy crashed (rc 2) — {proc.stderr.strip()[-400:]}"
    # mypy 1.19 emits error lines on STDOUT (stderr carries notes/warnings);
    # count both — a wrong-stream assumption reads 0 errors on a broken tree.
    count = proc.stdout.count(": error:") + proc.stderr.count(": error:")
    return count, None


def load_baseline(path: Path) -> dict:
    payload: dict = json.loads(path.read_text())
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mypy debt ratchet")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--mypy-binary", default=None, help="mypy executable (default: PATH)")
    parser.add_argument(
        "--json-report-dir",
        default=None,
        help="also emit mypy's --json-report into this dir (metrics artifact)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="regenerate the baseline from the current tree",
    )
    args = parser.parse_args(argv)

    count, error = run_mypy(args.root, args.mypy_binary, args.json_report_dir)
    if error:
        print(f"MYPY-RATCHET: mypy run failed: {error}")
        return 2

    if args.update:
        baseline = {
            "generated_at": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip(),
            "total": count,
        }
        args.baseline.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
        print(f"MYPY-RATCHET: baseline written — total={count}")
        return 0

    baseline_total: int | None = None
    if args.baseline.exists():
        try:
            value = load_baseline(args.baseline).get("total")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"MYPY-RATCHET: baseline unreadable: {exc}")
            return 2
        if isinstance(value, int):
            baseline_total = value
    if baseline_total is None:
        print(
            f"MYPY-RATCHET: baseline missing or 'total' not an integer: "
            f"{args.baseline} (run --update to create)"
        )
        return 2
    if count > baseline_total:
        print(
            f"MYPY-RATCHET: {count} errors > baseline {baseline_total} "
            f"(net growth of {count - baseline_total})"
        )
        return 1
    print(f"MYPY-RATCHET: clean — {count} errors (baseline {baseline_total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
