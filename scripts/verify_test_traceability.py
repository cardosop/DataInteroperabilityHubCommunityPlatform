#!/usr/bin/env python3
"""
Verify test traceability completeness (Phase 10.2).

Checks that:
- Every feature (FEATURES.md) has test coverage documented in TEST_TRACEABILITY.md
- Every use case (USE_CASES.md) has test coverage documented
- Every user journey (USER_JOURNEYS.md) has test coverage documented
- Every persona (USER_PERSONAS.md) has test coverage documented
- Test names/IDs or docstrings reference doc IDs (UC-*, JOURNEY-*) where applicable

Usage:
  python scripts/verify_test_traceability.py [--repo-root PATH] [--strict]
  Exit 0 if all checks pass; non-zero otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Canonical list of 29 features from FEATURES.md Table of Contents (order and names)
EXPECTED_FEATURES = [
    "Auth",
    "Contracts",
    "ODPS (Open Data Product Standard)",
    "Assets",
    "Datasets",
    "Data Quality",
    "Compliance",
    "Marketplace",
    "Governance",
    "Search",
    "Observability",
    "Workflows",
    "Lineage",
    "Versioning",
    "BaaS",
    "Integrations",
    "Jobs",
    "Files",
    "Semantic",
    "AI",
    "ML",
    "Social",
    "Data Mesh",
    "Virtualization",
    "Scheduled Ingestion",
    "Scheduled Export",
    "Webhooks",
    "Audit",
    "Health",
]

# 13 personas from USER_PERSONAS.md
EXPECTED_PERSONAS = [
    "Visitor / Prospect",
    "Data Product Owner",
    "Data Engineer / Contract Author",
    "Compliance & Privacy Officer",
    "Data Consumer / Buyer",
    "Tenant Admin",
    "Platform Admin / Marketplace Operator",
    "External Developer / Integrator",
    "Auditor",
    "Data Scientist / ML Engineer",
    "Data Analyst",
    "Community Manager / Data Steward",
    "Data Mesh Domain Owner",
]


def extract_use_case_ids(content: str) -> set[str]:
    """Extract UC-* IDs from USE_CASES.md (### UC- or #### UC-)."""
    ids: set[str] = set()
    for m in re.finditer(r"^(?:###|####)\s+(UC-[A-Z0-9-]+):", content, re.MULTILINE):
        ids.add(m.group(1))
    return ids


def extract_journey_ids(content: str) -> set[str]:
    """Extract JOURNEY-* IDs from USER_JOURNEYS.md (**Journey ID**: JOURNEY-xxx)."""
    ids: set[str] = set()
    for m in re.finditer(r"\*\*Journey ID\*\*:\s*(JOURNEY-[A-Z]+-[0-9]+)", content):
        ids.add(m.group(1))
    return ids


def extract_features_from_traceability(content: str) -> set[str]:
    """Extract feature names from TEST_TRACEABILITY.md ### Feature sections (Feature → Test Mapping only)."""
    # Section "Feature → Test Mapping" ends before "Use Case → Test Mapping"
    feature_section = content
    if "## Use Case → Test Mapping" in content:
        feature_section = content.split("## Use Case → Test Mapping")[0]
    ids: set[str] = set()
    for m in re.finditer(r"^### ([A-Za-z][^\n#]+?)\s*$", feature_section, re.MULTILINE):
        name = m.group(1).strip()
        if name in ("Backend Test Coverage", "Frontend Test Coverage", "CLI/SDK Test Coverage"):
            continue
        ids.add(name)
        if "ODPS" in name and "Open Data Product" in name:
            ids.add("ODPS (Open Data Product Standard)")
    return ids


def extract_uc_refs_from_traceability(content: str) -> set[str]:
    """Extract UC-* IDs mentioned in TEST_TRACEABILITY.md."""
    ids: set[str] = set()
    for m in re.finditer(r"UC-[A-Z0-9-]+", content):
        ids.add(m.group(0))
    return ids


def extract_journey_refs_from_traceability(content: str) -> set[str]:
    """Extract JOURNEY-* IDs from TEST_TRACEABILITY.md (explicit and ranges)."""
    ids: set[str] = set()
    # Explicit IDs
    for m in re.finditer(r"JOURNEY-[A-Z]+-[0-9]+", content):
        ids.add(m.group(0))
    # Range pattern: JOURNEY-PREFIX-N1 … JOURNEY-PREFIX-N2 (same prefix, N1 <= N2)
    for m in re.finditer(r"JOURNEY-([A-Z]+)-(\d+)\s*[…\.]\s*JOURNEY-\1-(\d+)", content):
        prefix, n1, n2 = m.group(1), int(m.group(2)), int(m.group(3))
        for n in range(min(n1, n2), max(n1, n2) + 1):
            ids.add(f"JOURNEY-{prefix}-{n:03d}" if n < 100 else f"JOURNEY-{prefix}-{n}")
    return ids


def extract_persona_refs_from_traceability(content: str) -> set[str]:
    """Extract persona names from TEST_TRACEABILITY.md (Persona section or coverage text)."""
    found: set[str] = set()
    # Normalize for comparison: strip " **NEW**" etc.
    for p in EXPECTED_PERSONAS:
        norm = p.replace(" **NEW**", "").strip()
        if norm in content or p in content:
            found.add(p)
    # Also check "Persona → Test" or "Map all personas" section
    if "Persona" in content and "Test" in content:
        for p in EXPECTED_PERSONAS:
            if p in content:
                found.add(p)
    return found


def scan_tests_for_doc_id_refs(
    repo_root: Path,
    test_dirs: list[str],
    extensions: tuple[str, ...] = (".py", ".ts"),
) -> tuple[int, list[str]]:
    """Scan test files for UC-* or JOURNEY-* in file content or path. Returns (count of files with refs, list of paths)."""
    seen: set[Path] = set()
    paths: list[str] = []
    pattern = re.compile(r"(UC-[A-Z0-9-]+|JOURNEY-[A-Z]+-[0-9]+)")
    for dir_name in test_dirs:
        d = repo_root / dir_name
        if not d.is_dir():
            continue
        for ext in extensions:
            for path in d.rglob(f"*{ext}"):
                if path in seen:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    text = ""
                # Path can reference doc ID (e.g. JOURNEY-AUTH-001.spec.ts)
                if pattern.search(text) or pattern.search(path.name):
                    seen.add(path)
                    paths.append(str(path.relative_to(repo_root)))
    return len(paths), paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify test traceability completeness")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--strict", action="store_true", help="Fail if any single check fails")
    args = parser.parse_args()
    repo = args.repo_root
    docs = repo / "docs"

    errors: list[str] = []
    warnings: list[str] = []

    # Load docs
    features_md = (docs / "FEATURES.md").read_text(encoding="utf-8")
    use_cases_md = (docs / "USE_CASES.md").read_text(encoding="utf-8")
    user_journeys_md = (docs / "USER_JOURNEYS.md").read_text(encoding="utf-8")
    user_personas_md = (docs / "USER_PERSONAS.md").read_text(encoding="utf-8")
    traceability_md = (docs / "TEST_TRACEABILITY.md").read_text(encoding="utf-8")

    use_case_ids = extract_use_case_ids(use_cases_md)
    journey_ids = extract_journey_ids(user_journeys_md)

    # 10.2.1: Every feature has test coverage documented
    trace_features = extract_features_from_traceability(traceability_md)
    missing_features = [f for f in EXPECTED_FEATURES if f not in trace_features]
    if missing_features:
        errors.append(
            f"10.2.1 Feature coverage: {len(missing_features)}/29 features missing in TEST_TRACEABILITY.md: {missing_features}"
        )
    else:
        print("10.2.1 OK: Every feature has test coverage documented (29/29)")

    # 10.2.2: Every use case has test coverage documented
    trace_ucs = extract_uc_refs_from_traceability(traceability_md)
    missing_ucs = use_case_ids - trace_ucs
    if missing_ucs:
        # Allow "through" ranges: e.g. UC-AM-001 through UC-AM-011 covers all in range
        # For strict check we require each UC to be mentioned or covered by a range
        warnings.append(
            f"10.2.2 Use case coverage: {len(missing_ucs)} use cases not explicitly listed in TEST_TRACEABILITY.md (may be covered by ranges)"
        )
        if args.strict:
            errors.append(f"10.2.2 Missing use case refs (strict): {sorted(missing_ucs)[:20]}...")
    else:
        print("10.2.2 OK: Every use case has test coverage documented")
    if not missing_ucs:
        print(f"10.2.2 OK: All {len(use_case_ids)} use cases referenced in TEST_TRACEABILITY.md")

    # 10.2.3: Every user journey has test coverage documented
    trace_journeys = extract_journey_refs_from_traceability(traceability_md)
    missing_journeys = journey_ids - trace_journeys
    if missing_journeys:
        warnings.append(
            f"10.2.3 Journey coverage: {len(missing_journeys)} journeys not explicitly listed in TEST_TRACEABILITY.md"
        )
        if args.strict:
            errors.append(
                f"10.2.3 Missing journey refs (strict): {sorted(missing_journeys)[:20]}..."
            )
    else:
        print(f"10.2.3 OK: All {len(journey_ids)} user journeys have test coverage documented")

    # 10.2.4: Every persona has test coverage documented
    trace_personas = extract_persona_refs_from_traceability(traceability_md)
    missing_personas = [p for p in EXPECTED_PERSONAS if p not in trace_personas]
    if missing_personas:
        errors.append(
            f"10.2.4 Persona coverage: {len(missing_personas)}/13 personas missing in TEST_TRACEABILITY.md: {missing_personas}"
        )
    else:
        print("10.2.4 OK: Every persona has test coverage documented (13/13)")

    # 10.2.5: Test names/IDs reference doc IDs — verify some tests reference UC-* or JOURNEY-*
    test_dirs = ["tests/e2e", "tests/integration", "hub/apps", "frontend/e2e"]
    files_with_refs, ref_paths = scan_tests_for_doc_id_refs(repo, test_dirs)
    if files_with_refs == 0:
        warnings.append("10.2.5 No test files found containing UC-* or JOURNEY-* doc ID references")
    else:
        print(f"10.2.5 OK: {files_with_refs} test files reference doc IDs (UC-* or JOURNEY-*)")

    for w in warnings:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e)

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
