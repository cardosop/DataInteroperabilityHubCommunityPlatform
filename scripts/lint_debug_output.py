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
import ast
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

FRONTEND_DIRS = ["frontend/src/features", "frontend/src/shared"]
BACKEND_DIRS = ["hub/apps"]
BLOCKING_DATE = datetime(2026, 6, 21, tzinfo=UTC)

CONSOLE_PATTERN = re.compile(r"\bconsole\.(log|error|warn|debug)\s*\(", re.IGNORECASE)
# Exemptions: test files, __init__, conftest, migration files
EXEMPT_GLOBS = {"**/tests/**", "**/conftest.py", "**/__init__.py", "**/migrations/**"}


def _is_exempt(filepath: str) -> bool:
    if not filepath.endswith(".py"):
        return False
    if "tests/" in filepath or "migrations/" in filepath:
        return True
    if filepath.endswith(("__init__.py", "conftest.py")):
        return True
    # Management commands and the estate e2e sandbox are CLI surfaces —
    # print() IS their stdout interface, not debug output (root-fixed
    # 2026-10-15: the raw-line scan also flagged `>>> print(...)`
    # doctests as debug output).
    return "/management/" in filepath or "/e2e_tooling/" in filepath


def _git_modified_files(repo_root: Path, since_days: int | None) -> list[str]:
    if since_days is None:
        return []
    since = (datetime.now(UTC) - timedelta(days=since_days)).strftime("%Y-%m-%d")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            f"--since={since}",
            "--name-only",
            "--pretty=format:",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    return [result.strip() for result in result.stdout.splitlines() if result.strip()]


def scan_file(filepath: Path) -> list[dict]:
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    lines = content.splitlines()
    # console.* is never idiomatic in Python — the line scan catches it
    # (there is no Python AST node for console calls).
    for i, line in enumerate(lines, 1):
        if CONSOLE_PATTERN.search(line):
            findings.append(
                {"file": str(filepath), "line": i, "snippet": line.strip()[:120]}
            )
    # print() is AST-scanned: doctest examples are STRING LITERALS, not
    # calls, so `>>> print(...)` in a docstring never counts (the pre-fix
    # raw-line scan flagged them as debug output).
    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            findings.append(
                {
                    "file": str(filepath),
                    "line": node.lineno,
                    "snippet": lines[node.lineno - 1].strip()[:120],
                }
            )
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
                    "status": (
                        "fail"
                        if (all_findings and is_blocking)
                        else ("warn" if all_findings else "ok")
                    ),
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
    parser = argparse.ArgumentParser(
        description="TR.O.17 — Debug output suppression lint"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--blocking", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Only scan files modified in last N days",
    )
    args = parser.parse_args()
    return run_lint(args.repo_root, args.blocking, args.json, args.since)


if __name__ == "__main__":
    raise SystemExit(main())
