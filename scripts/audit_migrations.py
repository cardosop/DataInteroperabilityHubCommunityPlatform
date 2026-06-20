#!/usr/bin/env python3
"""
281.A.1.1 — Migration Squash Audit.

Audits every Django app under ``hub/apps/`` for migration file count.
Reports apps exceeding the squash threshold (default: 200) and generates
a structured JSON report.

Usage:
  python scripts/audit_migrations.py                # audit all apps
  python scripts/audit_migrations.py --threshold 50 # lower threshold
  python scripts/audit_migrations.py --json         # JSON output
  python scripts/audit_migrations.py --check        # exit 1 if any app > threshold
"""

import json
import sys
from argparse import ArgumentParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = PROJECT_ROOT / "hub" / "apps"
DEFAULT_THRESHOLD = 200


def count_migrations(app_dir: Path) -> tuple[int, list[str]]:
    """Return (count, [migration_names]) for an app's migrations directory."""
    mig_dir = app_dir / "migrations"
    if not mig_dir.is_dir():
        return 0, []

    files = sorted(
        f.stem for f in mig_dir.glob("*.py") if f.stem != "__init__" and not f.name.startswith(".")
    )
    return len(files), files


def audit_all_apps(threshold: int) -> dict:
    """Audit all Django apps and return a structured report."""
    results = {
        "threshold": threshold,
        "total_apps": 0,
        "total_migrations": 0,
        "apps_over_threshold": [],
        "apps_under_threshold": [],
        "per_app": {},
    }

    if not APPS_DIR.is_dir():
        return results

    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        if not (app_dir / "migrations").is_dir():
            continue

        app_name = app_dir.name
        count, files = count_migrations(app_dir)
        results["total_apps"] += 1
        results["total_migrations"] += count
        results["per_app"][app_name] = {
            "count": count,
            "newest": files[-1] if files else None,
            "oldest": files[0] if files else None,
        }

        if count > threshold:
            results["apps_over_threshold"].append(app_name)
        else:
            results["apps_under_threshold"].append(app_name)

    results["apps_over_threshold"].sort()
    results["apps_under_threshold"].sort()
    return results


def print_report(results: dict) -> None:
    """Print a human-readable audit report."""
    t = results["threshold"]
    print(f"Migration Audit — threshold: >{t} migrations")
    print(f"  Total apps with migrations: {results['total_apps']}")
    print(f"  Total migration files:     {results['total_migrations']}")
    print()

    if results["apps_over_threshold"]:
        print(f"  🚫 Apps OVER {t} migrations (needs squash):")
        for app in results["apps_over_threshold"]:
            info = results["per_app"][app]
            print(
                f"    {app}: {info['count']} migrations "
                f"(oldest={info['oldest']}, newest={info['newest']})"
            )
    else:
        print(f"  ✅ No apps exceed the {t}-migration threshold.")

    print()
    print("  Top 10 apps by migration count:")
    top = sorted(results["per_app"].items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    for app, info in top:
        bar = "█" * min(info["count"], 40)
        print(f"    {app:25s} {info['count']:4d} {bar}")


def main():
    parser = ArgumentParser(description="Audit Django migration counts")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Squash threshold (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--check", action="store_true", help="Exit 1 if any app exceeds threshold")
    args = parser.parse_args()

    results = audit_all_apps(args.threshold)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    if args.check and results["apps_over_threshold"]:
        print(
            f"\nError: {len(results['apps_over_threshold'])} app(s) exceed "
            f"the {args.threshold}-migration threshold.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
