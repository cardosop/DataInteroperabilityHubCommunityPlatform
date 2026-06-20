#!/usr/bin/env python3
"""
TR.L.4 — CI check: journey marker coverage must not decrease.

Compares journey IDs from ``docs/CRITICAL_UC_JOURNEY_IDS.yaml`` against
``@pytest.mark.journey("JOURNEY-XX-NNN")`` markers in backend tests.
Reports uncovered journeys. Informational for 30 days, then blocking.

Usage:
    python scripts/lint_journey_marker_coverage.py
    python scripts/lint_journey_marker_coverage.py --blocking
    python scripts/lint_journey_marker_coverage.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

JOURNEY_IDS_FILE = "docs/CRITICAL_UC_JOURNEY_IDS.yaml"
SCAN_DIRS = ["hub/apps", "tests", "cli/tests", "sdk/python/tests", "services"]
BLOCKING_DATE = datetime(2026, 6, 21, tzinfo=UTC)


def _extract_yaml_journey_ids(filepath: Path) -> set[str]:
    """Extract all JOURNEY-XX-NNN IDs from the YAML file."""
    if not filepath.exists():
        return set()
    content = filepath.read_text()
    return set(re.findall(r"JOURNEY-[A-Z]+-\d+", content))


def _extract_marked_journey_ids(scan_dirs: list[Path]) -> set[str]:
    """Find all journey IDs marked with @pytest.mark.journey in test files."""
    marked: set[str] = set()
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", ".venv")]
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                except Exception:
                    continue
                for match in re.finditer(
                    r'(?:pytest\.mark\.journey|@pytest\.mark\.journey)\s*\(\s*["\'](JOURNEY-[A-Z]+-\d+)["\']',
                    content,
                ):
                    marked.add(match.group(1))
    return marked


def run_lint(
    repo_root: Path,
    blocking: bool = False,
    json_output: bool = False,
) -> int:
    yaml_ids = _extract_yaml_journey_ids(repo_root / JOURNEY_IDS_FILE)
    marked_ids = _extract_marked_journey_ids(
        [repo_root / d for d in SCAN_DIRS],
    )

    uncovered = yaml_ids - marked_ids
    now = datetime.now(UTC)
    is_blocking = blocking or now >= BLOCKING_DATE

    if json_output:
        print(
            json.dumps(
                {
                    "status": "fail"
                    if (uncovered and is_blocking)
                    else ("warn" if uncovered else "ok"),
                    "yaml_journey_count": len(yaml_ids),
                    "marked_journey_count": len(marked_ids),
                    "uncovered_count": len(uncovered),
                    "coverage_pct": round(
                        (len(yaml_ids) - len(uncovered)) / max(len(yaml_ids), 1) * 100,
                        1,
                    ),
                    "blocking": is_blocking,
                    "uncovered": sorted(uncovered),
                },
                indent=2,
            )
        )
    else:
        coverage = round(
            (len(yaml_ids) - len(uncovered)) / max(len(yaml_ids), 1) * 100,
            1,
        )
        print("Journey Marker Coverage Check")
        print(f"  YAML journey IDs: {len(yaml_ids)}")
        print(f"  Marked in tests:  {len(marked_ids)}")
        print(f"  Uncovered:        {len(uncovered)}")
        print(f"  Coverage:         {coverage}%")
        mode = "BLOCKING" if is_blocking else "INFORMATIONAL"
        print(f"  Mode: {mode} (until {BLOCKING_DATE.strftime('%Y-%m-%d')})")
        if uncovered:
            print("\n  Uncovered journeys:")
            for j in sorted(uncovered):
                print(f"    - {j}")
            print(
                f'\n  Add @pytest.mark.journey("{sorted(uncovered)[0]}") to the relevant test file.'
            )

    if uncovered and is_blocking:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.L.4 — Journey marker coverage lint")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--blocking", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return run_lint(Path(args.repo_root).resolve(), args.blocking, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
