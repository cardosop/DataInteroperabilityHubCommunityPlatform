#!/usr/bin/env python3
"""
TR.M.1 — CI gate: migration reversibility test.

For every new migration file in a PR, runs:
  1. ``manage.py migrate <app> <previous>`` (reverse)
  2. ``manage.py migrate <app>`` (re-apply forward)

Blocks on any failure. Designed for CI.

Usage:
    python scripts/test_migration_reversibility.py
    python scripts/test_migration_reversibility.py --app tenants
    python scripts/test_migration_reversibility.py --base-ref origin/main
    python scripts/test_migration_reversibility.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

MIGRATION_PATH_RE = re.compile(
    r"^hub/apps/(?P<app>[a-zA-Z0-9_]+)/migrations/(?P<name>\d{4}_.*)\.py$"
)


def _run_git(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _changed_migrations(repo_root: Path, base_ref: str) -> list[tuple[str, str]]:
    """Return list of (app_name, migration_name) for new migration files."""
    merge_base = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", base_ref, "HEAD"],
        check=False,
        text=True,
        capture_output=True,
    ).stdout.strip()

    output = _run_git(
        repo_root,
        ["diff", "--name-only", f"{merge_base}..HEAD"],
    )
    migrations: list[tuple[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        m = MIGRATION_PATH_RE.match(line)
        if m and not line.endswith("__init__.py"):
            app = m.group("app")
            # Get the migration number prefix (e.g., "0001")
            mig_name = m.group("name")
            migrations.append((app, mig_name))
    return migrations


def _get_previous_migration(repo_root: Path, app: str, migration_name: str) -> str | None:
    """Find the migration immediately before the given one."""
    mig_dir = repo_root / "hub" / "apps" / app / "migrations"
    if not mig_dir.is_dir():
        return None
    files = sorted(f for f in os.listdir(mig_dir) if f.endswith(".py") and f != "__init__.py")
    try:
        idx = files.index(migration_name)
    except ValueError:
        return None
    if idx == 0:
        return "zero"  # First migration — reverse to zero state
    prev = files[idx - 1]
    # Strip .py and return just the name part
    return prev.replace(".py", "")


def test_reversibility(
    repo_root: Path,
    app: str,
    migration_name: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Test that a migration can be reversed and re-applied."""
    migration_key = migration_name.replace(".py", "")
    prev = _get_previous_migration(repo_root, app, migration_name)

    if prev is None:
        return False, f"Could not find previous migration for {app}/{migration_name}"

    manage_py = str(repo_root / "hub" / "manage.py")

    if dry_run:
        return True, (
            f"DRY-RUN: would test {app} {migration_key} (reverse to {prev}, then re-apply)"
        )

    # Step 1: Reverse migration
    if prev == "zero":
        cmd = f"python {manage_py} migrate {app} zero"
    else:
        cmd = f"python {manage_py} migrate {app} {prev}"

    result = subprocess.run(
        cmd,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
        cwd=str(repo_root),
        timeout=120,
    )
    if result.returncode != 0:
        return False, (
            f"Reverse migration FAILED for {app}/{migration_key} → {prev}:\n{result.stderr[:500]}"
        )

    # Step 2: Re-apply forward
    cmd = f"python {manage_py} migrate {app} {migration_key}"
    result = subprocess.run(
        cmd,
        check=False,
        shell=True,
        text=True,
        capture_output=True,
        cwd=str(repo_root),
        timeout=120,
    )
    if result.returncode != 0:
        return False, (
            f"Re-apply migration FAILED for {app}/{migration_key}:\n{result.stderr[:500]}"
        )

    return True, f"PASS: {app}/{migration_key} reversed to {prev} and re-applied"


def run_tests(
    repo_root: Path,
    base_ref: str = "origin/main",
    app_filter: str | None = None,
    dry_run: bool = False,
) -> int:
    """Run reversibility tests for all new migrations."""
    migrations = _changed_migrations(repo_root, base_ref)
    if app_filter:
        migrations = [(a, m) for a, m in migrations if a == app_filter]

    if not migrations:
        print("No new migration files to test.")
        return 0

    failures = 0
    for app, mig_name in migrations:
        ok, msg = test_reversibility(repo_root, app, mig_name, dry_run)
        status = "✓" if ok else "✗"
        print(f"  {status} {msg}")
        if not ok:
            failures += 1

    print(f"\n{migrations.__len__()} migration(s) tested, {failures} failure(s).")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.M.1 — Migration reversibility test")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", type=str, default="origin/main")
    parser.add_argument("--app", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return run_tests(args.repo_root, args.base_ref, args.app, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
