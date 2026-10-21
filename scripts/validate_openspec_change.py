"""validate_openspec_change.py — structural validator for an openspec change dir.

The official `npx @fission-ai/openspec validate` cannot run in offline /
restricted environments (external package download). This repo-owned
validator enforces the change structure the repo's specs actually follow,
with a NET-growth baseline so pre-existing violations are pinned but new
ones fail CI:

    python scripts/validate_openspec_change.py --change openspec/changes/preprod01 \
        --baseline scripts/openspec_validation_baseline.txt

Rules (keys are line-number-free so line-shift churn never false-fails):
  R1  change dir contains proposal.md, tasks.md, specs/
  R2  proposal.md has `## Why`, `## What Changes`, `## Impact` sections
  R3  every spec file has a `#` title
  R4  every spec file has an ADDED and/or MODIFIED Requirements section
  R5  every requirement contains SHALL
  R6  every requirement has at least one scenario
  R7  every scenario has WHEN and THEN bullets
  R8  no duplicate requirement titles within a file
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_REQUIREMENT = re.compile(r"^### Requirement: (.+)$", re.MULTILINE)
_SCENARIO = re.compile(r"^#### Scenario: (.+)$", re.MULTILINE)
_SECTION = re.compile(r"^## (ADDED|MODIFIED) Requirements$", re.MULTILINE)


def collect_violations(change_dir: Path) -> list[str]:
    """Return stable violation keys (file::rule::subject — no line numbers)."""
    violations: list[str] = []

    proposal = change_dir / "proposal.md"
    tasks = change_dir / "tasks.md"
    specs_dir = change_dir / "specs"

    if not proposal.exists():
        violations.append("proposal.md::missing")
    else:
        text = proposal.read_text()
        for section in ("## Why", "## What Changes", "## Impact"):
            if section not in text:
                violations.append(f"proposal.md::missing-section::{section}")

    if not tasks.exists():
        violations.append("tasks.md::missing")

    if not specs_dir.is_dir() or not any(specs_dir.rglob("*.md")):
        violations.append("specs/::missing")

    for spec in sorted(specs_dir.rglob("*.md")) if specs_dir.is_dir() else []:
        rel = str(spec.relative_to(change_dir))
        violations.extend(_validate_spec_file(rel, spec.read_text().splitlines()))

    return sorted(set(violations))


def _validate_spec_file(rel: str, lines: list[str]) -> list[str]:
    """Validate one spec file; block-based parsing (no closures over loop
    variables — the earlier closure design was a B023 bug class)."""
    violations: list[str] = []

    # Title = first NON-BLANK line — leading blank lines are formatting
    # churn and must not flip the no-title key.
    first_non_blank = next((line for line in lines if line.strip()), None)
    if first_non_blank is None or not first_non_blank.startswith("# "):
        violations.append(f"{rel}::no-title")

    if not any(_SECTION.match(line) for line in lines):
        violations.append(f"{rel}::no-requirements-section")

    blocks = _parse_requirement_blocks(lines)

    seen: set[str] = set()
    for title, body in blocks:
        violations.extend(_check_requirement_block(rel, title, body, seen))

    return violations


def _parse_requirement_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split a spec into (title, body-lines) pairs. Intro prose belongs to
    no block."""
    blocks: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []
    for line in lines:
        requirement = _REQUIREMENT.match(line)
        if requirement:
            if current_title is not None:
                blocks.append((current_title, current_body))
            current_title = requirement.group(1)
            current_body = []
        elif current_title is not None:
            current_body.append(line)
    if current_title is not None:
        blocks.append((current_title, current_body))
    return blocks


def _check_requirement_block(rel: str, title: str, body: list[str], seen: set[str]) -> list[str]:
    violations: list[str] = []
    body_text = "\n".join(body)

    if title in seen:
        violations.append(f"{rel}::duplicate-requirement::{title}")
    seen.add(title)

    if "SHALL" not in title and "SHALL" not in body_text:
        violations.append(f"{rel}::requirement-no-shall::{title}")

    # Scenario regions: slice the body between scenario headers.
    scenario_matches = list(_SCENARIO.finditer(body_text))
    if not scenario_matches:
        violations.append(f"{rel}::requirement-no-scenario::{title}")
    for index, match in enumerate(scenario_matches):
        scenario_title = match.group(1)
        region_end = (
            scenario_matches[index + 1].start()
            if index + 1 < len(scenario_matches)
            else len(body_text)
        )
        scenario_text = body_text[match.end() : region_end]
        if not re.search(r"^-\s+\*\*WHEN\*\*", scenario_text, re.MULTILINE):
            violations.append(f"{rel}::scenario-no-when::{title}::{scenario_title}")
        if not re.search(r"^-\s+\*\*THEN\*\*", scenario_text, re.MULTILINE):
            violations.append(f"{rel}::scenario-no-then::{title}::{scenario_title}")

    return violations


def _load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an openspec change dir")
    parser.add_argument("--change", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument(
        "--emit-baseline",
        action="store_true",
        help="print the current violation set (to seed a baseline file)",
    )
    args = parser.parse_args(argv)

    violations = collect_violations(args.change)

    if args.emit_baseline:
        print("\n".join(violations))
        return 0

    baseline = _load_baseline(args.baseline) if args.baseline else set()
    new = sorted(set(violations) - baseline)
    if new:
        print(f"OPENSPEC-STRUCT: {len(new)} NEW structural violation(s):")
        for entry in new:
            print(f"  {entry}")
        print(
            "Fix the spec file, or (only for pre-existing debt) record it in "
            "the baseline — the baseline only shrinks (net growth fails)."
        )
        return 1

    shrunk = sorted(baseline - set(violations))
    print(
        f"OPENSPEC-STRUCT: clean ({len(violations)} baselined, {len(shrunk)} fixed since baseline)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
