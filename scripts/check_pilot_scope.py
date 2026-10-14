#!/usr/bin/env python3
"""
GATE-45 (pilot-readiness 3.2) — the pilot-scope record contract checker.

The Week-3 workshop record (docs/runbooks/PILOT_SCOPE.md) must:
- contain the four mandated sections (journey selection, capability
  manifest, Unity Catalog / Delta Sharing decision, data-migration
  approach);
- select 18-22 journey/UC IDs, anchored to the critical registry
  (>=18 critical IDs — the plan's "critical-first, ~20 total" rule);
- list only IDs that exist in the canonical registries
  (docs/USER_JOURNEYS.md, docs/USE_CASES.md) — no invented IDs;
- name only RUNTIME capability keys — AST-parsed from
  hub/apps/api/capabilities.py's ``LINEAGE_CAPABILITY_FLAGS`` (the
  shared registry the SPA keys against) — never invented keys;
- record the decisions without TBD/TODO placeholders.

Exit 0 when the record satisfies the contract; 1 otherwise, each
problem named.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPORT_DEFAULT = Path("docs/runbooks/PILOT_SCOPE.md")
JOURNEYS_DEFAULT = Path("docs/USER_JOURNEYS.md")
USE_CASES_DEFAULT = Path("docs/USE_CASES.md")
CRITICAL_DEFAULT = Path("docs/CRITICAL_UC_JOURNEY_IDS.yaml")
CAPABILITIES_DEFAULT = Path("hub/apps/api/capabilities.py")

REQUIRED_SECTIONS = (
    "## Journey selection",
    "## Capability manifest",
    "## Unity Catalog / Delta Sharing decision",
    "## Data-migration approach",
)
MIN_SELECTED = 18
MAX_SELECTED = 22
MIN_CRITICAL = 18

_ID_RE = re.compile(r"\b(?:JOURNEY|UC)-[A-Z0-9-]+\b")
_PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def _ids(text: str) -> set[str]:
    return set(_ID_RE.findall(text))


def _capability_keys(capabilities_path: Path) -> set[str]:
    """The RUNTIME registry, AST-parsed from the module (no Django
    import - the tuple is a module-level annotated literal)."""
    tree = ast.parse(capabilities_path.read_text())
    for node in ast.walk(tree):
        # AnnAssign: ``LINEAGE_CAPABILITY_FLAGS: tuple[str, ...] = (...)``
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "LINEAGE_CAPABILITY_FLAGS"
            and isinstance(node.value, ast.Tuple)
        ) or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "LINEAGE_CAPABILITY_FLAGS" for t in node.targets
            )
            and isinstance(node.value, ast.Tuple)
        ):
            return {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)}
    return set()


def check(
    report_path: Path,
    journeys_path: Path,
    use_cases_path: Path,
    critical_path: Path,
    capabilities_path: Path,
) -> list[str]:
    problems: list[str] = []
    if not report_path.exists():
        return [f"pilot-scope record missing: {report_path}"]
    text = report_path.read_text()
    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")
    registry_ids = _ids(journeys_path.read_text()) | _ids(use_cases_path.read_text())
    selected = _ids(text)
    unknown = selected - registry_ids
    for name in sorted(unknown):
        problems.append(f"selected ID {name!r} does not exist in the canonical registries")
    if not (MIN_SELECTED <= len(selected) <= MAX_SELECTED):
        problems.append(
            f"selected-ID count {len(selected)} outside [{MIN_SELECTED}, {MAX_SELECTED}]"
        )
    critical_ids = _ids(critical_path.read_text())
    critical_selected = len(selected & critical_ids)
    if critical_selected < MIN_CRITICAL:
        problems.append(
            f"critical anchoring: only {critical_selected} of the selected IDs "
            f"are critical-registry IDs (need >= {MIN_CRITICAL})"
        )
    manifest_section = text.split("## Capability manifest", 1)
    if len(manifest_section) > 1:
        runtime_keys = _capability_keys(capabilities_path)
        section = manifest_section[1].split("## ", 1)[0]
        for key in sorted(set(re.findall(r"\blineage\.[a-z_]+\b", section)) - runtime_keys):
            problems.append(f"capability key {key!r} is not a runtime registry key")
    decisions = text.split("## Unity Catalog / Delta Sharing decision", 1)
    if len(decisions) > 1:
        for match in _PLACEHOLDER_RE.findall(decisions[1]):
            problems.append(f"unresolved placeholder {match!r} in the decision sections")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--journeys", type=Path, default=JOURNEYS_DEFAULT)
    parser.add_argument("--use-cases", type=Path, default=USE_CASES_DEFAULT)
    parser.add_argument("--critical", type=Path, default=CRITICAL_DEFAULT)
    parser.add_argument("--capabilities", type=Path, default=CAPABILITIES_DEFAULT)
    args = parser.parse_args()
    problems = check(args.report, args.journeys, args.use_cases, args.critical, args.capabilities)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-45 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-45 PASSED: {args.report} satisfies the pilot-scope contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
