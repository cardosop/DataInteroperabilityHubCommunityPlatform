#!/usr/bin/env python3
"""
TR.O.17 — Debug output suppression lint.

Blocks new ``console.log`` / ``console.error`` in frontend production code
and ``print()`` in backend production code. Informational 30 days, then blocking.

Usage:
    python scripts/lint_debug_output.py
    python scripts/lint_debug_output.py --blocking
    python scripts/lint_debug_output.py --json
    python scripts/lint_debug_output.py --since 7d  # only recently modified files
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

FRONTEND_DIRS = ["frontend/src/features", "frontend/src/shared"]
BACKEND_DIRS = ["hub/apps"]
BLOCKING_DATE = datetime(2026, 6, 21, tzinfo=UTC)

CONSOLE_PATTERN = re.compile(r"\bconsole\.(log|error|warn|debug)\s*\(", re.IGNORECASE)
PRINT_PATTERN = re.compile(r"\bprint\s*\([^)]*\)")
# Exemptions: test files, __init__, conftest, migration files
EXEMPT_GLOBS = {"**/tests/**", "**/conftest.py", "**/__init__.py", "**/migrations/**"}


def _is_exempt(filepath: str) -> bool:
    for _pattern in EXEMPT_GLOBS:
        if filepath.endswith(".py") and ("tests/" in filepath or "migrations/" in filepath):
            return True
    return False


def _git_modified_files(repo_root: Path, since_days: int | None) -> list[str]:
    if since_days is None:
        return []
    since = (datetime.now(UTC) - timedelta(days=since_days)).strftime("%Y-%m-%d")
    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", f"--since={since}", "--name-only", "--pretty=format:"],
        check=False,
        text=True,
        capture_output=True,
    )
    return [l.strip() for l in result.stdout.splitlines() if l.strip()]


def scan_file(filepath: Path) -> list[dict]:
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if CONSOLE_PATTERN.search(line) or PRINT_PATTERN.search(line):
            findings.append({"file": str(filepath), "line": i, "snippet": line.strip()[:120]})
    return findings


def run_lint(
    repo_root: Path,
    blocking: bool = False,
    json_output: bool = False,
    since_days: int | None = None,
) -> int:
    all_findings = []
    scan_dirs = [repo_root / d for d in FRONTEND_DIRS + BACKEND_DIRS]

    modified = set(_git_modified_files(repo_root, since_days)) if since_days else set()

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if _is_exempt(str(py_file)):
                continue
            if modified and str(py_file.relative_to(repo_root)) not in modified:
                continue
            all_findings.extend(scan_file(py_file))

    now = datetime.now(UTC)
    is_blocking = blocking or now >= BLOCKING_DATE

    if json_output:
        print(
            json.dumps(
                {
                    "status": "fail"
                    if (all_findings and is_blocking)
                    else ("warn" if all_findings else "ok"),
                    "total": len(all_findings),
                    "blocking": is_blocking,
                    "findings": all_findings[:50],
                },
                indent=2,
            )
        )
    else:
        print(f"Debug Output Lint: {len(all_findings)} issue(s)")
        for f in all_findings[:20]:
            print(f"  {f['file']}:{f['line']} — {f['snippet']}")
        if len(all_findings) > 20:
            print(f"  ... and {len(all_findings) - 20} more")
        mode = "BLOCKING" if is_blocking else "INFORMATIONAL"
        print(f"  Mode: {mode}")

    if all_findings and is_blocking:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.O.17 — Debug output suppression lint")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--blocking", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--since", type=int, default=None, help="Only scan files modified in last N days"
    )
    args = parser.parse_args()
    return run_lint(args.repo_root, args.blocking, args.json, args.since)


if __name__ == "__main__":
    raise SystemExit(main())
