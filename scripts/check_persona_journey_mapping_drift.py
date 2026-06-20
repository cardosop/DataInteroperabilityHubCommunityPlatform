#!/usr/bin/env python3
"""Check persona-journey-mapping.yaml for drift against frontend specs and docs.

Verifies:
  1. Every journey in persona-journey-mapping.yaml exists in docs/USER_JOURNEYS.md.
  2. Every import in frontend/e2e/personas/*.spec.ts is reflected in the mapping.
  3. The mapping file is up-to-date (re-runnable extraction produces same result).

Phase 312.5.8 — D167 drift test for persona-journey mapping.
Modeled on check_persona_mapping_drift.py (Phase 217.0.4).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_FILE = REPO_ROOT / "docs" / "mvpdocs" / "_meta" / "persona-journey-mapping.yaml"
JOURNEYS_DOC = REPO_ROOT / "docs" / "USER_JOURNEYS.md"
PERSONAS_DIR = REPO_ROOT / "frontend" / "e2e" / "personas"


def _parse_mapping(mapping_path: Path) -> dict[str, list[str]]:
    """Parse persona-journey-mapping.yaml without PyYAML."""
    result: dict[str, list[str]] = {}
    current_persona = None
    if not mapping_path.exists():
        return result
    for line in mapping_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "mapping:":
            continue
        match = re.match(r"(\w+):", stripped)
        if match:
            persona = match.group(1)
            if persona not in result:
                result[persona] = []
            current_persona = persona
        elif stripped.startswith("- ") and current_persona:
            result[current_persona].append(stripped[2:].strip())
    return result


def _extract_doc_journey_ids(doc_path: Path) -> set[str]:
    """Extract all JOURNEY-XXX-NNN from the canonical journeys doc."""
    if not doc_path.exists():
        return set()
    return set(re.findall(r"JOURNEY-[A-Z]+-\d+", doc_path.read_text()))


def _extract_spec_imports(personas_dir: Path) -> dict[str, list[str]]:
    """Extract persona→journey from frontend persona spec imports."""
    result: dict[str, list[str]] = {}
    if not personas_dir.is_dir():
        return result
    import_re = re.compile(r"import\s+['\"]\.\.\/journeys\/\w+\/(JOURNEY-[A-Z]+-\d+)\.spec['\"]")
    for spec_file in sorted(personas_dir.glob("*.spec.ts")):
        persona_key = spec_file.stem.replace(".spec", "").replace("-", "_")
        journey_ids = import_re.findall(spec_file.read_text())
        if journey_ids:
            result[persona_key] = journey_ids
    return result


def run_check(repo_root: Path, blocking: bool = False) -> int:
    mapping_path = repo_root / "docs" / "mvpdocs" / "_meta" / "persona-journey-mapping.yaml"
    doc_path = repo_root / "docs" / "USER_JOURNEYS.md"
    personas_dir = repo_root / "frontend" / "e2e" / "personas"

    mapping = _parse_mapping(mapping_path)
    doc_ids = _extract_doc_journey_ids(doc_path)
    spec_imports = _extract_spec_imports(personas_dir)

    violations: list[str] = []

    # Check 1: every mapped journey exists in docs
    all_mapped_ids: set[str] = set()
    for journeys in mapping.values():
        all_mapped_ids.update(journeys)
    mapped_not_in_docs = all_mapped_ids - doc_ids
    for jid in sorted(mapped_not_in_docs):
        violations.append(
            f"Journey {jid} in persona-journey-mapping.yaml but NOT in docs/USER_JOURNEYS.md"
        )

    # Check 2: every spec import is in mapping
    for persona in sorted(spec_imports.keys()):
        if persona not in mapping:
            violations.append(f"Persona '{persona}' has spec imports but no entry in mapping")
            continue
        spec_only = set(spec_imports[persona]) - set(mapping[persona])
        for jid in sorted(spec_only):
            violations.append(f"Journey {jid} imported by {persona}.spec.ts but NOT in mapping")
        mapping_only = set(mapping[persona]) - set(spec_imports[persona])
        for jid in sorted(mapping_only):
            violations.append(
                f"Journey {jid} in mapping for {persona} but NOT imported in spec file"
            )

    # Check 3: persona keys match
    spec_keys = set(spec_imports.keys())
    mapping_keys = set(mapping.keys())
    for key in sorted(spec_keys - mapping_keys):
        violations.append(f"Persona '{key}' in spec files but NOT in mapping")
    for key in sorted(mapping_keys - spec_keys):
        violations.append(f"Persona '{key}' in mapping but NOT in spec files")

    if violations:
        print(f"Persona-Journey Mapping Drift Check: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        if blocking:
            return 1
        return 1 if any("NOT in docs" in v for v in violations) else 0

    print("Persona-Journey Mapping Drift Check: OK")
    print(f"  Personas in mapping: {len(mapping)}")
    print(f"  Total journeys mapped: {sum(len(v) for v in mapping.values())}")
    print(f"  Doc journeys: {len(doc_ids)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check persona-journey mapping for drift")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--blocking", action="store_true", help="Exit 1 on any violation")
    args = parser.parse_args()
    return run_check(Path(args.repo_root).resolve(), args.blocking)


if __name__ == "__main__":
    sys.exit(main())
