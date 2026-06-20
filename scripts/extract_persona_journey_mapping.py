#!/usr/bin/env python3
"""Extract persona→journey mapping from frontend persona aggregator imports.

Parses frontend/e2e/personas/*.spec.ts files, extracts JOURNEY-XXX-NNN IDs
from import statements, and writes a machine-readable YAML mapping to
docs/mvpdocs/_meta/persona-journey-mapping.yaml.

Usage:
    python scripts/extract_persona_journey_mapping.py
    python scripts/extract_persona_journey_mapping.py --check  # exit 1 if drift

Phase 312.5.7 — D166 persona-journey mapping extraction.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = REPO_ROOT / "frontend" / "e2e" / "personas"
OUTPUT_FILE = REPO_ROOT / "docs" / "mvpdocs" / "_meta" / "persona-journey-mapping.yaml"

JOURNEY_IMPORT_RE = re.compile(
    r"import\s+['\"]\.\.\/journeys\/\w+\/(JOURNEY-[A-Z]+-\d+)\.spec['\"]\s*;?"
)


def extract_persona_journeys(personas_dir: Path) -> dict[str, list[str]]:
    """Extract persona→journey list from all persona aggregator specs."""
    mapping: dict[str, list[str]] = {}
    if not personas_dir.is_dir():
        return mapping

    for spec_file in sorted(personas_dir.glob("*.spec.ts")):
        persona_key = spec_file.stem.replace(".spec", "").replace("-", "_")
        content = spec_file.read_text()
        journey_ids: list[str] = []
        for match in JOURNEY_IMPORT_RE.finditer(content):
            journey_ids.append(match.group(1))
        if journey_ids:
            mapping[persona_key] = journey_ids

    return mapping


def write_mapping(mapping: dict[str, list[str]], output_path: Path) -> None:
    """Write the mapping to a YAML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Auto-generated from frontend/e2e/personas/*.spec.ts import statements.",
        "# Regenerate: python scripts/extract_persona_journey_mapping.py",
        "# Generated: Phase 312.5.7",
        "",
        "mapping:",
    ]
    for persona_key in sorted(mapping.keys()):
        journeys = mapping[persona_key]
        lines.append(f"  {persona_key}:")
        for jid in journeys:
            lines.append(f"    - {jid}")
    output_path.write_text("\n".join(lines) + "\n")


def check_drift(mapping: dict[str, list[str]], output_path: Path) -> tuple[bool, list[str]]:
    """Check if the current mapping matches what's on disk."""
    issues: list[str] = []
    if not output_path.exists():
        issues.append(
            f"Mapping file {output_path} does not exist. Run without --check to generate."
        )
        return False, issues

    # Parse the existing mapping file
    existing: dict[str, list[str]] = {}
    current_persona = None
    for line in output_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "mapping:":
            continue
        # e.g. "  data_product_owner:"
        match = re.match(r"(\w+):", stripped)
        if match and not stripped.endswith("-"):
            current_persona = match.group(1)
            existing[current_persona] = []
        elif stripped.startswith("- ") and current_persona:
            jid = stripped[2:].strip()
            existing[current_persona].append(jid)

    if set(existing.keys()) != set(mapping.keys()):
        only_existing = set(existing.keys()) - set(mapping.keys())
        only_new = set(mapping.keys()) - set(existing.keys())
        if only_existing:
            issues.append(f"Personas in mapping but not in specs: {sorted(only_existing)}")
        if only_new:
            issues.append(f"Personas in specs but not in mapping: {sorted(only_new)}")

    for persona in sorted(set(mapping.keys()) & set(existing.keys())):
        if mapping[persona] != existing[persona]:
            issues.append(
                f"Journey list drift for {persona}: "
                f"specs={len(mapping[persona])} journeys, "
                f"mapping={len(existing[persona])} journeys"
            )

    return len(issues) == 0, issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract persona→journey mapping from frontend spec imports"
    )
    parser.add_argument("--check", action="store_true", help="Exit 1 if drift detected")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()

    personas_dir = args.repo_root / "frontend" / "e2e" / "personas"
    output_path = args.repo_root / "docs" / "mvpdocs" / "_meta" / "persona-journey-mapping.yaml"

    mapping = extract_persona_journeys(personas_dir)

    if not mapping:
        print("ERROR: No persona specs found or no journey imports detected.")
        return 1

    if args.check:
        ok, issues = check_drift(mapping, output_path)
        if not ok:
            print("DRIFT DETECTED:")
            for issue in issues:
                print(f"  - {issue}")
            print("\nRun without --check to regenerate the mapping.")
            return 1
        print("OK: persona-journey mapping is in sync with frontend specs.")
        return 0

    write_mapping(mapping, output_path)
    print(
        f"Wrote {sum(len(v) for v in mapping.values())} journeys across "
        f"{len(mapping)} personas to {output_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
