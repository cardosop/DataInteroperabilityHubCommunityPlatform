#!/usr/bin/env python3
"""
Report which use cases (USE_CASES.md) and user journeys (USER_JOURNEYS.md)
have at least one test. Output: Markdown or JSON listing UC/journey → test file(s).
Optionally fail or warn if a configured set has zero tests.
Per openspec/changes/testsfix1 task 5.5.

Usage:
  python scripts/report_uc_journey_test_coverage.py [--json] [--fail-if-zero] [--audit-traceability]
  --json: output JSON instead of Markdown
  --fail-if-zero: exit 1 if any UC or journey has zero tests
  --audit-traceability: check TEST_TRACEABILITY.md file paths exist; report broken links
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def repo_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def extract_uc_ids(use_cases_path: Path) -> list[str]:
    """Extract UC-* IDs from USE_CASES.md (lines like **ID**: UC-XXX)."""
    ids: list[str] = []
    content = use_cases_path.read_text()
    for m in re.finditer(r"\*\*ID\*\*:\s*(UC-[A-Za-z0-9-]+)", content):
        ids.append(m.group(1))
    return sorted(set(ids))


def extract_journey_ids(user_journeys_path: Path) -> list[str]:
    """Extract JOURNEY-* IDs from USER_JOURNEYS.md (**Journey ID**: JOURNEY-XXX)."""
    ids: list[str] = []
    content = user_journeys_path.read_text()
    for m in re.finditer(r"\*\*Journey ID\*\*:\s*(JOURNEY-[A-Za-z0-9-]+)", content):
        ids.append(m.group(1))
    return sorted(set(ids))


def collect_test_files(root: Path) -> list[Path]:
    """Collect backend and frontend test file paths."""
    files: list[Path] = []
    for pattern in [
        "hub/apps/**/tests/*.py",
        "hub/apps/**/tests/**/*.py",
        "tests/**/*.py",
        "frontend/e2e/**/*.spec.ts",
    ]:
        for p in root.glob(pattern):
            if p.is_file():
                files.append(p)
    return sorted(set(files))


def find_references_in_file(file_path: Path, ids: list[str]) -> list[str]:
    """Return which of the given IDs appear in the file content (docstring, name)."""
    try:
        content = file_path.read_text()
    except Exception:
        return []
    found: list[str] = []
    for id_ in ids:
        if id_ in content:
            found.append(id_)
    return found


def build_coverage(
    root: Path,
    uc_ids: list[str],
    journey_ids: list[str],
    test_files: list[Path],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build UC → [files] and Journey → [files] by scanning test files."""
    uc_to_files: dict[str, list[str]] = {uc: [] for uc in uc_ids}
    journey_to_files: dict[str, list[str]] = {j: [] for j in journey_ids}
    all_ids = uc_ids + journey_ids

    for f in test_files:
        rel = str(f.relative_to(root))
        found = find_references_in_file(f, all_ids)
        for id_ in found:
            if id_.startswith("UC-"):
                uc_to_files.setdefault(id_, []).append(rel)
            else:
                journey_to_files.setdefault(id_, []).append(rel)

    for k in list(uc_to_files.keys()):
        uc_to_files[k] = sorted(set(uc_to_files[k]))
    for k in list(journey_to_files.keys()):
        journey_to_files[k] = sorted(set(journey_to_files[k]))
    return uc_to_files, journey_to_files


def audit_traceability(root: Path, traceability_path: Path) -> list[str]:
    """Extract file paths from TEST_TRACEABILITY.md and check they exist. Return broken."""
    content = traceability_path.read_text()
    # Paths like `hub/apps/...` or hub/apps/... or tests/... or frontend/...
    pattern = r"(?:^|\s|`)((?:hub/apps/|tests/|frontend/)[a-zA-Z0-9_/.-]+\.(?:py|ts))\b"
    paths = set(re.findall(pattern, content))
    broken: list[str] = []
    for p in paths:
        if "..." in p or "**" in p:
            continue
        full = root / p
        if not full.is_file():
            broken.append(p)
    return sorted(broken)


def output_markdown(
    uc_to_files: dict[str, list[str]],
    journey_to_files: dict[str, list[str]],
    broken_links: list[str] | None,
) -> None:
    """Print Markdown report to stdout."""
    print("# Use Case and User Journey Test Coverage Report\n")
    print("## Use cases → test files\n")
    zero_uc = [uc for uc, files in uc_to_files.items() if not files]
    for uc, files in sorted(uc_to_files.items()):
        status = "✅" if files else "⚠️ no tests"
        print(f"- **{uc}**: {status}")
        for f in files[:10]:
            print(f"  - `{f}`")
        if len(files) > 10:
            print(f"  - ... and {len(files) - 10} more")
        if not files:
            print()
    print("\n## User journeys → test files\n")
    zero_journey = [j for j, files in journey_to_files.items() if not files]
    for j, files in sorted(journey_to_files.items()):
        status = "✅" if files else "⚠️ no tests"
        print(f"- **{j}**: {status}")
        for f in files[:10]:
            print(f"  - `{f}`")
        if len(files) > 10:
            print(f"  - ... and {len(files) - 10} more")
        if not files:
            print()
    if zero_uc or zero_journey:
        print("\n## Zero-test items\n")
        if zero_uc:
            print(f"- Use cases with no tests: {len(zero_uc)} — {', '.join(zero_uc[:15])}{'...' if len(zero_uc) > 15 else ''}")
        if zero_journey:
            print(f"- Journeys with no tests: {len(zero_journey)} — {', '.join(zero_journey[:15])}{'...' if len(zero_journey) > 15 else ''}")
    if broken_links:
        print("\n## Broken file links (TEST_TRACEABILITY.md)\n")
        for p in broken_links:
            print(f"- `{p}`")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report UC/journey → test file coverage (task 5.5)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of Markdown",
    )
    parser.add_argument(
        "--fail-if-zero",
        action="store_true",
        help="Exit 1 if any UC or journey has zero tests",
    )
    parser.add_argument(
        "--audit-traceability",
        action="store_true",
        help="Check TEST_TRACEABILITY.md file paths exist; report broken links",
    )
    args = parser.parse_args()

    root = repo_root()
    docs = root / "docs"
    use_cases_path = docs / "USE_CASES.md"
    user_journeys_path = docs / "USER_JOURNEYS.md"
    traceability_path = docs / "TEST_TRACEABILITY.md"

    if not use_cases_path.is_file():
        print("USE_CASES.md not found", file=sys.stderr)
        return 1
    if not user_journeys_path.is_file():
        print("USER_JOURNEYS.md not found", file=sys.stderr)
        return 1

    uc_ids = extract_uc_ids(use_cases_path)
    journey_ids = extract_journey_ids(user_journeys_path)
    test_files = collect_test_files(root)
    uc_to_files, journey_to_files = build_coverage(
        root, uc_ids, journey_ids, test_files
    )

    broken_links: list[str] = []
    if args.audit_traceability and traceability_path.is_file():
        broken_links = audit_traceability(root, traceability_path)

    if args.json:
        out = {
            "use_cases": uc_to_files,
            "user_journeys": journey_to_files,
            "broken_traceability_links": broken_links,
        }
        print(json.dumps(out, indent=2))
    else:
        output_markdown(uc_to_files, journey_to_files, broken_links or None)

    if args.fail_if_zero:
        zero_uc = [uc for uc, files in uc_to_files.items() if not files]
        zero_journey = [j for j, files in journey_to_files.items() if not files]
        if zero_uc or zero_journey:
            print(
                f"\nExit: {len(zero_uc)} UC(s) and {len(zero_journey)} journey(s) with zero tests.",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
