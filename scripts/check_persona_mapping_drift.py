#!/usr/bin/env python3
"""Check persona-mapping.yaml covers every fixture persona.

Enumerates persona keys from three sources:
  1. frontend/e2e/personas/*.spec.ts  (filename stems)
  2. cli/tests/fixtures/personas.py   (MVP_PERSONA_ROLES list)
  3. sdk/python/tests/fixtures/personas.py (MVP_PERSONA_ROLES list)

Asserts every discovered persona appears as a key in
docs/mvpdocs/_meta/persona-mapping.yaml and every mapping
value is one of the 6 product-canonical personas.

Phase 217.0.4 — D163 drift test.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_FILE = (
    REPO_ROOT / "docs" / "mvpdocs" / "_meta"
    / "persona-mapping.yaml"
)

CANON_PERSONAS = frozenset(
    {"DPO", "DE", "CPO", "DC", "MPA", "DEV"}
)


def _parse_mapping() -> dict[str, str]:
    """Parse persona-mapping.yaml without PyYAML."""
    result: dict[str, str] = {}
    in_mapping = False
    for line in MAPPING_FILE.read_text().splitlines():
        stripped = line.strip()
        if stripped == "mapping:":
            in_mapping = True
            continue
        if not in_mapping:
            continue
        if stripped.startswith("#") or not stripped:
            continue
        # e.g. "  data_product_owner: DPO"
        match = re.match(r"(\w+):\s*(\w+)", stripped)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _extract_frontend_personas() -> set[str]:
    """Extract persona names from frontend e2e spec filenames."""
    personas_dir = (
        REPO_ROOT / "frontend" / "e2e" / "personas"
    )
    if not personas_dir.is_dir():
        return set()
    result = set()
    for spec in personas_dir.glob("*.spec.ts"):
        # e.g. data-product-owner.spec.ts -> data_product_owner
        name = spec.stem.replace(".spec", "")
        name = name.replace("-", "_")
        result.add(name)
    return result


def _extract_python_personas(filepath: Path) -> set[str]:
    """Extract MVP_PERSONA_ROLES from a Python personas.py."""
    if not filepath.exists():
        return set()
    tree = ast.parse(filepath.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "MVP_PERSONA_ROLES"
                ):
                    val = ast.literal_eval(node.value)
                    return set(val)
    return set()


def main() -> int:
    errors: list[str] = []

    if not MAPPING_FILE.exists():
        print(f"FAIL: {MAPPING_FILE} does not exist")
        return 1

    mapping = _parse_mapping()

    # Collect all personas from sources
    fe_personas = _extract_frontend_personas()
    cli_personas = _extract_python_personas(
        REPO_ROOT / "cli" / "tests" / "fixtures" / "personas.py"
    )
    sdk_personas = _extract_python_personas(
        REPO_ROOT / "sdk" / "python" / "tests"
        / "fixtures" / "personas.py"
    )

    all_personas = fe_personas | cli_personas | sdk_personas
    sources = {
        "frontend/e2e/personas/": fe_personas,
        "cli/tests/fixtures/personas.py": cli_personas,
        "sdk/python/tests/fixtures/personas.py": sdk_personas,
    }

    print(f"Mapping keys: {sorted(mapping.keys())}")
    print(f"All fixture personas: {sorted(all_personas)}")

    # Check 1: every fixture persona has a mapping
    for source, personas in sources.items():
        for p in sorted(personas):
            if p not in mapping:
                errors.append(
                    f"Persona {p!r} from {source}"
                    " missing from mapping"
                )

    # Check 2: every mapping value is canonical
    for key, value in sorted(mapping.items()):
        if value not in CANON_PERSONAS:
            errors.append(
                f"Mapping {key!r} -> {value!r}"
                f" is not a canon persona"
                f" (expected one of {sorted(CANON_PERSONAS)})"
            )

    # Check 3: no stale mapping keys
    for key in sorted(mapping.keys()):
        if key not in all_personas:
            print(
                f"WARN: Mapping key {key!r} not found"
                " in any fixture source (may be stale)"
            )

    if errors:
        print(f"\nFAIL: {len(errors)} persona-mapping drift "
              "error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"\nPASS: {len(mapping)} personas mapped,"
          f" {len(all_personas)} fixture personas covered,"
          f" all values in {sorted(CANON_PERSONAS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
