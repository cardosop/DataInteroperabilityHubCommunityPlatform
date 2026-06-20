#!/usr/bin/env python3
"""
308.4 — Migration safety lint.

Detects dangerous operations in Django migration files:
  - DROP COLUMN (data loss)
  - DROP TABLE (data loss)
  - ALTER COLUMN ... TYPE (potential data loss / casting errors)
  - RemoveField with no prior deprecation notice
  - DeleteModel with no prior deprecation notice

Operates on the diff between the current branch and the merge-base.
Outputs warnings to stdout; exit code 0 on clean, 1 on violations.

Usage:
    python scripts/lint_migrations.py                      # scan PR diff
    python scripts/lint_migrations.py --base-ref origin/main
    python scripts/lint_migrations.py --all                # scan all migrations
    python scripts/lint_migrations.py --json               # JSON output for CI
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ── Patterns ────────────────────────────────────────────────────────────

DANGEROUS_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, severity, description)
    (r"\.\s*RemoveField\s*\(", "warning", "RemoveField — verify column is deprecated first"),
    (r"\.\s*DeleteModel\s*\(", "warning", "DeleteModel — verify table is deprecated first"),
    (r"DROP\s+COLUMN\b", "error", "DROP COLUMN — irreversible data loss"),
    (r"DROP\s+TABLE\b", "error", "DROP TABLE — irreversible data loss"),
    (
        r"ALTER\s+COLUMN\b.*\bTYPE\b",
        "warning",
        "ALTER COLUMN TYPE — may cause data loss or casting errors",
    ),
    (r"\.\s*RunSQL\s*\(.*DROP\b(?!.*IF\s+EXISTS)", "warning", "RunSQL with DROP without IF EXISTS"),
    (r"\.\s*RemoveIndex\s*\(", "info", "RemoveIndex — verify index is unused"),
    (
        r"\.\s*AlterUniqueTogether\s*\(\s*\)",
        "warning",
        "AlterUniqueTogether with empty constraints — drops constraint",
    ),
]


@dataclass
class Finding:
    file: str
    line: int
    severity: str  # error, warning, info
    description: str
    snippet: str


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _resolve_merge_base(repo_root: Path, base_ref: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", base_ref, "HEAD"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not resolve merge-base for '{base_ref}'")
    return result.stdout.strip()


def _changed_migrations(repo_root: Path, base_ref: str) -> list[str]:
    """Return list of changed migration files since merge-base."""
    merge_base = _resolve_merge_base(repo_root, base_ref)
    output = _run_git(repo_root, ["diff", "--name-only", f"{merge_base}..HEAD"])
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
        and "/migrations/" in line
        and line.endswith(".py")
        and not line.endswith("__init__.py")
    ]


def _all_migrations(repo_root: Path) -> list[str]:
    """Return all migration files in the repo."""
    result = subprocess.run(
        [
            "find",
            str(repo_root / "hub" / "apps"),
            "-path",
            "*/migrations/*.py",
            "-not",
            "-name",
            "__init__.py",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def scan_file(filepath: str) -> list[Finding]:
    """Scan a single migration file for dangerous patterns."""
    findings: list[Finding] = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return findings

    for i, line in enumerate(lines, 1):
        for pattern, severity, description in DANGEROUS_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    Finding(
                        file=filepath,
                        line=i,
                        severity=severity,
                        description=description,
                        snippet=line.strip()[:120],
                    )
                )
    return findings


def run_lint(
    repo_root: Path,
    base_ref: str | None = None,
    all_migrations: bool = False,
    json_output: bool = False,
) -> int:
    """Run the migration safety lint. Returns exit code."""
    if all_migrations:
        files = _all_migrations(repo_root)
    elif base_ref:
        files = _changed_migrations(repo_root, base_ref)
    else:
        files = _changed_migrations(repo_root, "origin/main")

    if not files:
        if json_output:
            print(json.dumps({"status": "ok", "findings": []}))
        else:
            print("No migration files to check.")
        return 0

    all_findings: list[Finding] = []
    for f in files:
        all_findings.extend(scan_file(f))

    errors = [f for f in all_findings if f.severity == "error"]
    warnings = [f for f in all_findings if f.severity == "warning"]
    infos = [f for f in all_findings if f.severity == "info"]

    if json_output:
        print(
            json.dumps(
                {
                    "status": "fail" if errors else ("warn" if warnings else "ok"),
                    "files_checked": len(files),
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "infos": len(infos),
                    "findings": [
                        {
                            "file": f.file,
                            "line": f.line,
                            "severity": f.severity,
                            "description": f.description,
                            "snippet": f.snippet,
                        }
                        for f in all_findings
                    ],
                },
                indent=2,
            )
        )
    else:
        print(f"Checked {len(files)} migration file(s).")
        for f in all_findings:
            tag = {"error": "✗", "warning": "⚠", "info": "ℹ"}[f.severity]
            print(f"  {tag} {f.file}:{f.line} [{f.severity}] {f.description}")
            if f.severity in ("error", "warning"):
                print(f"      {f.snippet}")

        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} info(s).")

    if errors:
        print("\nErrors must be fixed before merge (irreversible data loss).")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="308.4 — Migration safety lint")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root path.",
    )
    parser.add_argument(
        "--base-ref",
        type=str,
        default=None,
        help="Git base ref for PR diff (default: origin/main).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Scan all migrations in the repo.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    return run_lint(
        repo_root=args.repo_root,
        base_ref=args.base_ref,
        all_migrations=args.all,
        json_output=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
