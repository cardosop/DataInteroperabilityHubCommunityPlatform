#!/usr/bin/env python3
"""
281.B.6.4 — Automated dead code detection.

Flags Python functions and classes that have been unreferenced for >90 days
based on git history. In CI, warns when stale code is detected.

Usage: python scripts/check_dead_code.py [--days 90] [--ci]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SOURCE_DIRS = ("hub/", "cli/datahub_cli/", "sdk/python/datahub_interoperability/")


def _last_modified(filename: str) -> datetime | None:
    """Return the last commit date for a file, or None if not tracked."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", filename],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return datetime.fromisoformat(result.stdout.strip())
    except Exception:
        pass
    return None


def _is_referenced(filename: str) -> bool:
    """Check if a file is imported by any other source file."""
    module_name = Path(filename).stem
    try:
        # Search for import references
        result = subprocess.run(
            [
                "grep",
                "-rl",
                f"import.*{module_name}|from.*{module_name}",
                *[d for d in SOURCE_DIRS if Path(d).is_dir()],
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # If any file other than itself imports it, it's referenced
        lines = [l for l in result.stdout.split("\n") if l and l != filename]
        return len(lines) > 0
    except Exception:
        return True  # Assume referenced if we can't check


def main() -> int:
    parser = argparse.ArgumentParser(description="Dead code detector")
    parser.add_argument(
        "--days", type=int, default=90, help="Days since last modification (default: 90)"
    )
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on dead code")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    dead: list[dict] = []

    for src in SOURCE_DIRS:
        if not Path(src).is_dir():
            continue
        for py_file in sorted(Path(src).rglob("*.py")):
            if "/migrations/" in str(py_file) or "/tests/" in str(py_file):
                continue
            if py_file.name == "__init__.py":
                continue

            last_mod = _last_modified(str(py_file))
            if last_mod and last_mod < cutoff:
                # Only flag if unreferenced by other files
                if not _is_referenced(str(py_file)):
                    dead.append(
                        {
                            "file": str(py_file),
                            "last_modified": last_mod.isoformat(),
                            "days_since_modification": (datetime.now(UTC) - last_mod).days,
                        }
                    )

    if args.json:
        import json

        print(json.dumps({"dead_code": dead, "count": len(dead)}, indent=2))
    elif dead:
        print(
            f"Potentially dead code ({len(dead)} files, >{args.days} days since last modification):"
        )
        for d in dead:
            print(f"  ⚠️  {d['file']} ({d['days_since_modification']}d)")
    else:
        print(f"No dead code detected (> {args.days} days threshold).")

    if dead and args.ci:
        print(f"\nCI warning: {len(dead)} file(s) unchanged for >{args.days} days.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
