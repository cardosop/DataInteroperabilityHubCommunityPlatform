#!/usr/bin/env python3
"""Check bidirectional sync between canonical use case docs and test markers.

Performs five checks:
  1. Forward:  Every UC-XXX in docs/USE_CASES.md has >=1
     @pytest.mark.uc("UC-XXX") marker in test code.
  2. Reverse:  Every @pytest.mark.uc("UC-XXX") in test code has a
     corresponding entry in canonical docs.
  3. Critical: Every UC-XXX in CRITICAL_UC_JOURNEY_IDS.yaml exists in
     canonical docs.
  4. Frontend: Every frontend/e2e/use-cases/**/UC-*.spec.ts filename
     has a doc entry.
  5. Duplicate: No duplicate UC IDs in canonical docs.

Output modes:
  --ci-mode     exit 1 on any BLOCKING violation, JSON summary to stdout
  --report      markdown report of all drift
  --fix-hints   print exact lines where markers/docs are missing

Phase 312.5.6 — D165 drift test for use case documentation.
Modeled on check_doc_journey_marker_sync.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from boundary_scope import add_scope_argument, build_scan_dirs, paid_ids

REPO_ROOT = Path(__file__).resolve().parent.parent
USE_CASES_DOC = REPO_ROOT / "docs" / "USE_CASES.md"
CRITICAL_YAML = REPO_ROOT / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
FRONTEND_UC_DIR = REPO_ROOT / "frontend" / "e2e" / "use-cases"

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


def _extract_doc_uc_ids(doc_path: Path) -> set[str]:
    """Extract all UC-XXX-NNN from the canonical use cases doc."""
    if not doc_path.exists():
        return set()
    content = doc_path.read_text()
    # Match: UC-XXX-NNN, UC-XXX-XXX-NNN, UC-XXX-XXX-XXX-NNN
    return set(re.findall(r"UC-[A-Z]+(?:-[A-Z]+)*-\d+[A-Z]?", content))


def _extract_critical_uc_ids(yaml_path: Path) -> set[str]:
    """Extract UC-XXX-NNN from the critical YAML registry."""
    if not yaml_path.exists():
        return set()
    content = yaml_path.read_text()
    return set(re.findall(r"UC-[A-Z]+(?:-[A-Z]+)*-\d+[A-Z]?", content))


def _extract_marked_uc_ids(scan_dirs: list[Path]) -> set[str]:
    """Find all UC IDs from @pytest.mark.uc decorators in test files."""
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
                    r'(?:pytest\.mark\.uc|@pytest\.mark\.uc)\s*\(\s*["\'](UC-[A-Z]+(?:-[A-Z]+)*-\d+[A-Z]?)["\']',
                    content,
                ):
                    marked.add(match.group(1))
    return marked


def _extract_frontend_uc_ids(uc_dir: Path) -> set[str]:
    """Extract UC-XXX-NNN from frontend use-case spec filenames."""
    ids: set[str] = set()
    if not uc_dir.is_dir():
        return ids
    for _root, _dirs, files in os.walk(uc_dir):
        for f in files:
            match = re.match(r"(UC-[A-Z]+-\d+[A-Z]?)\.spec\.ts$", f)
            if match:
                ids.add(match.group(1))
    return ids


def _check_duplicates(doc_path: Path) -> list[str]:
    """Check for duplicate UC IDs in the canonical doc."""
    if not doc_path.exists():
        return []
    content = doc_path.read_text()
    # Only match UC IDs in markdown table first column: | UC-XXX |
    # Avoid matching UC IDs inside file paths like `mvpdocs/use-cases/UC-XXX.md`
    all_ids = re.findall(r"^\|\s*(UC-[A-Z]+(?:-[A-Z]+)*-\d+[A-Z]?)\s*\|", content, re.MULTILINE)
    seen: set[str] = set()
    duplicates: list[str] = []
    for uid in all_ids:
        if uid in seen:
            duplicates.append(uid)
        seen.add(uid)
    return duplicates


def run_check(
    repo_root: Path,
    ci_mode: bool = False,
    scope: str = "full",
    report: bool = False,
    fix_hints: bool = False,
) -> int:
    doc_path = repo_root / "docs" / "USE_CASES.md"
    yaml_path = repo_root / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
    frontend_dir = repo_root / "frontend" / "e2e" / "use-cases"
    scan_dirs = build_scan_dirs(repo_root, SCAN_DIRS, scope)

    doc_ids = _extract_doc_uc_ids(doc_path)
    critical_ids = _extract_critical_uc_ids(yaml_path)
    marked_ids = _extract_marked_uc_ids(scan_dirs)
    frontend_ids = _extract_frontend_uc_ids(frontend_dir)
    if scope == "core":
        skip = paid_ids(repo_root)
        doc_ids -= skip
        critical_ids -= skip
        marked_ids -= skip
        frontend_ids -= skip
    duplicates = _check_duplicates(doc_path)

    # Forward: doc -> markers
    doc_only = doc_ids - marked_ids
    # Reverse: markers -> doc
    markers_only = marked_ids - doc_ids
    # Critical -> doc
    critical_missing = critical_ids - doc_ids
    # Frontend -> doc
    frontend_only = frontend_ids - doc_ids
    # All test layers combined
    all_test_ids = marked_ids | frontend_ids
    untested = doc_ids - all_test_ids

    violations: list[dict] = []

    for uid in sorted(doc_only):
        violations.append(
            {
                "id": uid,
                "check": "forward",
                "severity": "BLOCKING" if uid in critical_ids else "WARNING",
                "message": f"Documented UC {uid} has no @pytest.mark.uc() marker in any test file.",
            }
        )

    for uid in sorted(markers_only):
        violations.append(
            {
                "id": uid,
                "check": "reverse",
                "severity": "WARNING",
                "message": f'Test marker @pytest.mark.uc("{uid}") has no corresponding entry in docs/USE_CASES.md.',
            }
        )

    for uid in sorted(critical_missing):
        violations.append(
            {
                "id": uid,
                "check": "critical",
                "severity": "BLOCKING",
                "message": f"Critical UC {uid} (in CRITICAL_UC_JOURNEY_IDS.yaml) is missing from docs/USE_CASES.md.",
            }
        )

    for uid in sorted(frontend_only):
        violations.append(
            {
                "id": uid,
                "check": "frontend",
                "severity": "WARNING",
                "message": f"Frontend spec {uid}.spec.ts has no corresponding entry in docs/USE_CASES.md.",
            }
        )

    for uid in sorted(untested):
        if uid not in {v["id"] for v in violations}:
            violations.append(
                {
                    "id": uid,
                    "check": "untested",
                    "severity": "WARNING",
                    "message": f"Documented UC {uid} has no test coverage in any layer (markers or frontend specs).",
                }
            )

    for uid in sorted(duplicates):
        violations.append(
            {
                "id": uid,
                "check": "duplicate",
                "severity": "BLOCKING",
                "message": f"Duplicate UC ID {uid} found in docs/USE_CASES.md.",
            }
        )

    blocking_count = sum(1 for v in violations if v["severity"] == "BLOCKING")
    warning_count = sum(1 for v in violations if v["severity"] == "WARNING")

    if report or ci_mode:
        summary = {
            "status": "fail" if blocking_count > 0 else ("warn" if warning_count > 0 else "ok"),
            "doc_uc_count": len(doc_ids),
            "marked_uc_count": len(marked_ids),
            "frontend_uc_count": len(frontend_ids),
            "critical_uc_count": len(critical_ids),
            "blocking_violations": blocking_count,
            "warning_violations": warning_count,
            "violations": violations,
        }
        if ci_mode:
            print(json.dumps(summary, indent=2))

    if fix_hints and doc_only:
        print("\n# To fix forward violations, add markers to the relevant test files:")
        for uid in sorted(doc_only):
            print(f'#   @pytest.mark.uc("{uid}")')

    if fix_hints and markers_only:
        print("\n# To fix reverse violations, add entries to docs/USE_CASES.md:")
        for uid in sorted(markers_only):
            print(f"#   | {uid} | <Title> | <Persona> | <File> |")

    if fix_hints and frontend_only:
        print("\n# To fix frontend violations, add entries to docs/USE_CASES.md:")
        for uid in sorted(frontend_only):
            print(f"#   | {uid} | <Title> | <Persona> | <File> |")

    if not ci_mode:
        print("\nUse Case Documentation Sync Check")
        print(f"  Doc UCs:          {len(doc_ids)}")
        print(f"  Test markers:     {len(marked_ids)}")
        print(f"  Frontend specs:   {len(frontend_ids)}")
        print(f"  Critical IDs:     {len(critical_ids)}")
        print(f"  Doc-only (no marker):   {len(doc_only)}")
        print(f"  Marker-only (no doc):   {len(markers_only)}")
        print(f"  Frontend-only (no doc): {len(frontend_only)}")
        print(f"  Untested (no coverage): {len(untested)}")
        print(f"  Duplicates:             {len(duplicates)}")
        print(f"  BLOCKING: {blocking_count}  WARNING: {warning_count}")

    if ci_mode:
        return 1 if blocking_count > 0 else 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check bidirectional sync between UC docs and test markers"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--ci-mode", action="store_true", help="Exit 1 on blocking violations, output JSON"
    )
    add_scope_argument(parser)
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
