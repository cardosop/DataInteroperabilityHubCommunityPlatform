#!/usr/bin/env python3
"""
CI gate: fail if any Django app exceeds the migration squash threshold.

Usage:
    python scripts/check_migration_count.py [--threshold 200] [--ci]

Exit codes:
    0 — all apps below threshold
    1 — one or more apps exceed threshold (CI gate failure)
    2 — usage / invocation error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 200
MIGRATIONS_DIR = "migrations"
HUB_APPS_DIR = Path("hub/apps")


def count_migrations(app_dir: Path) -> int:
    """Count migration files in an app's migrations directory."""
    mig_dir = app_dir / MIGRATIONS_DIR
    if not mig_dir.is_dir():
        return 0
    return len([f for f in mig_dir.iterdir() if f.suffix == ".py" and f.name != "__init__.py"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Django app migration counts against squash threshold"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Max migrations per app before squash is required (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit 1 on threshold breach (default: warn only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if not HUB_APPS_DIR.is_dir():
        print(f"Error: {HUB_APPS_DIR} not found — run from repo root", file=sys.stderr)
        return 2

    results: dict[str, int] = {}
    violations: dict[str, int] = {}

    for app_dir in sorted(HUB_APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        mig_dir = app_dir / MIGRATIONS_DIR
        if not mig_dir.is_dir():
            continue
        count = count_migrations(app_dir)
        if count > 0:
            results[app_dir.name] = count
            if count > args.threshold:
                violations[app_dir.name] = count

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "threshold": args.threshold,
                    "apps": results,
                    "violations": violations,
                },
                indent=2,
            )
        )
        return 1 if violations else 0

    print(f"Migration count audit (threshold: {args.threshold})")
    print(f"{'App':<30} {'Migrations':>12} {'Status'}")
    print("-" * 54)
    for name, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
        status = "⚠️  SQUASH REQUIRED" if count > args.threshold else "✅ OK"
        print(f"{name:<30} {count:>12}  {status}")

    if violations:
        print(f"\n{len(violations)} app(s) exceed the {args.threshold}-migration threshold:")
        for name, count in sorted(violations.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {name}: {count} migrations (limit: {args.threshold})")
            print(f"    Squash: python manage.py squashmigrations {name} <start> <end>")
        if args.ci:
            print("\nCI gate: FAILED — squash required before merge.")
        return 1

    print(f"\nAll apps within {args.threshold}-migration limit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
