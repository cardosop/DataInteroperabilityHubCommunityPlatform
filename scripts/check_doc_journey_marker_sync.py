#!/usr/bin/env python3
"""Check bidirectional sync between canonical journey docs and test markers.

Performs five checks:
  1. Forward:  Every JOURNEY-XXX in docs/USER_JOURNEYS.md has >=1
     @pytest.mark.journey("JOURNEY-XXX") marker in test code.
  2. Reverse:  Every @pytest.mark.journey("JOURNEY-XXX") in test code
     has a corresponding entry in canonical docs.
  3. Critical: Every JOURNEY-XXX in CRITICAL_UC_JOURNEY_IDS.yaml exists
     in canonical docs.
  4. Frontend: Every frontend/e2e/journeys/**/JOURNEY-*.spec.ts filename
     has a doc entry.
  5. Duplicate: No duplicate journey IDs in canonical docs.

Output modes:
  --ci-mode     exit 1 on any BLOCKING violation, JSON summary to stdout
  --report      markdown report of all drift
  --fix-hints   print exact lines where markers/docs are missing

Phase 312.5.5 — D164 drift test for journey documentation.
Modeled on check_persona_mapping_drift.py (Phase 217.0.4).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOURNEYS_DOC = REPO_ROOT / "docs" / "USER_JOURNEYS.md"
CRITICAL_YAML = REPO_ROOT / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
FRONTEND_JOURNEYS_DIR = REPO_ROOT / "frontend" / "e2e" / "journeys"

SCAN_DIRS = [
    "hub/apps",
    "tests/e2e",
    "tests/integration",
    "tests/performance",
    "tests/security",
    "cli/tests",
    "sdk/python/tests",
    "services",
]


def _extract_doc_journey_ids(doc_path: Path) -> set[str]:
    """Extract all JOURNEY-XXX-NNN from the canonical journeys doc."""
    if not doc_path.exists():
        return set()
    content = doc_path.read_text()
    return set(re.findall(r"JOURNEY-[A-Z]+-\d+", content))


def _extract_critical_journey_ids(yaml_path: Path) -> set[str]:
    """Extract JOURNEY-XXX-NNN from the critical YAML registry."""
    if not yaml_path.exists():
        return set()
    content = yaml_path.read_text()
    return set(re.findall(r"JOURNEY-[A-Z]+-\d+", content))


def _extract_marked_journey_ids(scan_dirs: list[Path]) -> set[str]:
    """Find all journey IDs from @pytest.mark.journey decorators in test files."""
    marked: set[str] = set()
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [
                d
                for d in dirs
                if d not in ("__pycache__", "node_modules", ".venv", ".git", "migrations")
            ]
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


def _extract_frontend_journey_ids(journeys_dir: Path) -> set[str]:
    """Extract JOURNEY-XXX-NNN from frontend spec filenames."""
    ids: set[str] = set()
    if not journeys_dir.is_dir():
        return ids
    for _root, _dirs, files in os.walk(journeys_dir):
        for f in files:
            match = re.match(r"(JOURNEY-[A-Z]+-\d+)\.spec\.ts$", f)
            if match:
                ids.add(match.group(1))
    return ids


def _check_duplicates(doc_path: Path) -> list[str]:
    """Check for duplicate journey IDs in the canonical doc."""
    if not doc_path.exists():
        return []
    content = doc_path.read_text()
    all_ids = re.findall(r"JOURNEY-[A-Z]+-\d+", content)
    seen: set[str] = set()
    duplicates: list[str] = []
    for jid in all_ids:
        if jid in seen:
            duplicates.append(jid)
        seen.add(jid)
    return duplicates


def run_check(
    repo_root: Path,
    ci_mode: bool = False,
    report: bool = False,
    fix_hints: bool = False,
) -> int:
    doc_path = repo_root / "docs" / "USER_JOURNEYS.md"
    yaml_path = repo_root / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
    frontend_dir = repo_root / "frontend" / "e2e" / "journeys"
    scan_dirs = [repo_root / d for d in SCAN_DIRS]

    doc_ids = _extract_doc_journey_ids(doc_path)
    critical_ids = _extract_critical_journey_ids(yaml_path)
    marked_ids = _extract_marked_journey_ids(scan_dirs)
    frontend_ids = _extract_frontend_journey_ids(frontend_dir)
    duplicates = _check_duplicates(doc_path)

    # Forward: doc -> markers
    doc_only = doc_ids - marked_ids
    # Reverse: markers -> doc
    markers_only = marked_ids - doc_ids
    # Critical -> doc
    critical_missing = critical_ids - doc_ids
    # Frontend -> doc
    frontend_only = frontend_ids - doc_ids
    # All test layers combined (markers + frontend filenames)
    all_test_ids = marked_ids | frontend_ids
    untested = doc_ids - all_test_ids

    violations: list[dict] = []

    for jid in sorted(doc_only):
        violations.append(
            {
                "id": jid,
                "check": "forward",
                "severity": "BLOCKING" if jid in critical_ids else "WARNING",
                "message": f"Documented journey {jid} has no @pytest.mark.journey() marker in any test file.",
            }
        )

    for jid in sorted(markers_only):
        violations.append(
            {
                "id": jid,
                "check": "reverse",
                "severity": "WARNING",
                "message": f'Test marker @pytest.mark.journey("{jid}") has no corresponding entry in docs/USER_JOURNEYS.md.',
            }
        )

    for jid in sorted(critical_missing):
        violations.append(
            {
                "id": jid,
                "check": "critical",
                "severity": "BLOCKING",
                "message": f"Critical journey {jid} (in CRITICAL_UC_JOURNEY_IDS.yaml) is missing from docs/USER_JOURNEYS.md.",
            }
        )

    for jid in sorted(frontend_only):
        violations.append(
            {
                "id": jid,
                "check": "frontend",
                "severity": "WARNING",
                "message": f"Frontend spec {jid}.spec.ts has no corresponding entry in docs/USER_JOURNEYS.md.",
            }
        )

    for jid in sorted(untested):
        if jid not in {v["id"] for v in violations}:
            violations.append(
                {
                    "id": jid,
                    "check": "untested",
                    "severity": "WARNING",
                    "message": f"Documented journey {jid} has no test coverage in any layer (markers or frontend specs).",
                }
            )

    for jid in sorted(duplicates):
        violations.append(
            {
                "id": jid,
                "check": "duplicate",
                "severity": "BLOCKING",
                "message": f"Duplicate journey ID {jid} found in docs/USER_JOURNEYS.md.",
            }
        )

    blocking_count = sum(1 for v in violations if v["severity"] == "BLOCKING")
    warning_count = sum(1 for v in violations if v["severity"] == "WARNING")

    if report or ci_mode:
        summary = {
            "status": "fail" if blocking_count > 0 else ("warn" if warning_count > 0 else "ok"),
            "doc_journey_count": len(doc_ids),
            "marked_journey_count": len(marked_ids),
            "frontend_journey_count": len(frontend_ids),
            "critical_journey_count": len(critical_ids),
            "blocking_violations": blocking_count,
            "warning_violations": warning_count,
            "violations": violations,
        }
        if ci_mode:
            print(json.dumps(summary, indent=2))

    if fix_hints and doc_only:
        print("\n# To fix forward violations, add markers to the relevant test files:")
        for jid in sorted(doc_only):
            print(f'#   @pytest.mark.journey("{jid}")')

    if fix_hints and markers_only:
        print("\n# To fix reverse violations, add entries to docs/USER_JOURNEYS.md:")
        for jid in sorted(markers_only):
            print(f"#   | {jid} | <Title> | <Persona> | <Phase> |")

    if fix_hints and frontend_only:
        print("\n# To fix frontend violations, add entries to docs/USER_JOURNEYS.md:")
        for jid in sorted(frontend_only):
            print(f"#   | {jid} | <Title> | <Persona> | <Phase> |")

    if not ci_mode:
        print("\nJourney Documentation Sync Check")
        print(f"  Doc journeys:     {len(doc_ids)}")
        print(f"  Test markers:     {len(marked_ids)}")
        print(f"  Frontend specs:   {len(frontend_ids)}")
        print(f"  Critical IDs:     {len(critical_ids)}")
        print(f"  Doc-only (no marker):  {len(doc_only)}")
        print(f"  Marker-only (no doc):  {len(markers_only)}")
        print(f"  Frontend-only (no doc): {len(frontend_only)}")
        print(f"  Untested (no coverage): {len(untested)}")
        print(f"  Duplicates:             {len(duplicates)}")
        print(f"  BLOCKING: {blocking_count}  WARNING: {warning_count}")

    if ci_mode:
        return 1 if blocking_count > 0 else 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check bidirectional sync between journey docs and test markers"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--ci-mode", action="store_true", help="Exit 1 on blocking violations, output JSON"
    )
    parser.add_argument("--report", action="store_true", help="Output markdown report")
    parser.add_argument("--fix-hints", action="store_true", help="Print fix hints for violations")
    args = parser.parse_args()
    return run_check(
        Path(args.repo_root).resolve(),
        ci_mode=args.ci_mode,
        report=args.report,
        fix_hints=args.fix_hints,
    )


if __name__ == "__main__":
    sys.exit(main())
