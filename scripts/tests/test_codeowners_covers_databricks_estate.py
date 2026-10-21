"""GATE-41 coverage pin — every databricks control-plane estate path
must resolve to a CODEOWNERS rule (the W18 dead-ownership class).

The CI gate (``scripts/check_codeowners_paths.py``) verifies the
DEAD-PATH direction: every rule in CODEOWNERS resolves to the tree.
This pin verifies the COVERAGE direction for the 12.x estate: every
tree path the add-databricks-* changes introduce resolves to a rule
(GitHub last-wins matching semantics), so the estate can never ship
with no codeowner and no required reviewer — including the explicit
``hub/apps/databricks_admin/`` rule the umbrella task names.

Non-vacuity: ``test_pin_catches_removed_databricks_rule`` proves the
scan flags the estate when the rule disappears (the W18 typo class),
so a green run on the real file is a real check, not a tautology.

Runs dependency-free (no Django) — the scripts/tests convention:
``venv/bin/python -m pytest scripts/tests/test_codeowners_covers_databricks_estate.py
-q -p no:cacheprovider --confcutdir=scripts/tests --override-ini="addopts="``
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"

# The 12.x estate's tree categories (all currently untracked — the org's
# public/private split — but these are the paths that WILL enter the
# committed tree when the estate lands, and CODEOWNERS must cover them).
ESTATE_DIRS = [
    "hub/apps/databricks_admin",
    "frontend/src/features/databricks",
]
ESTATE_SUFFIXES = [
    ("frontend/e2e/journeys", "JOURNEY-DB"),
    ("docs/mvpdocs/journeys", "JOURNEY-DB"),
    ("docs/mvpdocs/use-cases", "UC-DB"),
]


def parse_rules(codeowners: Path) -> list[tuple[str, list[str]]]:
    """Parse CODEOWNERS into (pattern, owners) entries.

    Comments, blanks, and negation rules are skipped (negations scope
    earlier rules; GitHub owns their semantics — same as the gate).
    """
    rules: list[tuple[str, list[str]]] = []
    for raw in codeowners.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rules.append((parts[0], parts[1:]))
    return rules


def github_matches(pattern: str, relpath: str) -> bool:
    """GitHub CODEOWNERS pattern matching (documented semantics).

    * A trailing ``/`` anchors a directory rule covering the subtree.
    * A pattern WITHOUT ``/`` matches the basename at any level.
    * Otherwise the pattern is anchored at the repo root; ``*`` matches
      within one path segment, ``**`` recurses, ``?`` matches one char.
    """
    if pattern.endswith("/"):
        return relpath.startswith(pattern)
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if "/" not in pattern:
        return fnmatch.fnmatch(relpath.rsplit("/", 1)[-1], pattern)
    regex = re.escape(pattern)
    regex = regex.replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
    return bool(re.match("^" + regex + r"(/|$)", relpath))


def owner_of(relpath: str, rules: list[tuple[str, list[str]]]) -> list[str] | None:
    """The owners of ``relpath`` under GitHub last-wins semantics."""
    owner: list[str] | None = None
    for pattern, owners in rules:
        if github_matches(pattern, relpath):
            owner = owners
    return owner


def estate_paths(root: Path) -> list[str]:
    """The estate's tree paths, as repo-relative posix paths."""
    paths: list[str] = []
    for d in ESTATE_DIRS:
        base = root / d
        if base.is_dir():
            paths.extend(p.relative_to(root).as_posix() for p in base.rglob("*") if p.is_file())
    for d, marker in ESTATE_SUFFIXES:
        base = root / d
        if base.is_dir():
            paths.extend(
                p.relative_to(root).as_posix()
                for p in base.rglob("*")
                if p.is_file() and marker in p.name
            )
    return sorted(set(paths))


def uncovered_paths(codeowners: Path, root: Path) -> list[str]:
    """Estate paths that no CODEOWNERS rule covers (last-wins)."""
    rules = parse_rules(codeowners)
    return [p for p in estate_paths(root) if not owner_of(p, rules)]


# ── pins ────────────────────────────────────────────────────────────────────


def test_estate_has_files_on_disk():
    """The coverage scan is non-vacuous: the estate is a real tree."""
    paths = estate_paths(ROOT)
    assert len(paths) >= 500, (
        f"Expected >=500 estate files on disk (the 12.x estate is a real "
        f"tree), found {len(paths)} — the coverage pin would be vacuous "
        "without the estate present."
    )


def test_every_estate_path_has_an_owner():
    """Every estate path resolves to a CODEOWNERS rule (last-wins)."""
    uncovered = uncovered_paths(CODEOWNERS, ROOT)
    assert not uncovered, (
        "Estate paths with no CODEOWNERS rule — the owned tree would ship "
        "with no codeowner and no required reviewer:\n"
        + "\n".join("  " + p for p in uncovered[:20])
    )


def test_databricks_admin_rule_present_with_two_owners():
    """The umbrella task's named rule: hub/apps/databricks_admin/ with
    >=1 primary + >=1 secondary owner (the file's own convention)."""
    rules = parse_rules(CODEOWNERS)
    entries = [(p, o) for p, o in rules if p == "hub/apps/databricks_admin/"]
    assert entries, "hub/apps/databricks_admin/ rule is missing from CODEOWNERS"
    owners = entries[-1][1]
    assert len(owners) >= 2, (
        f"hub/apps/databricks_admin/ needs >=1 primary + >=1 secondary owner, got {owners}"
    )
    assert (ROOT / "hub/apps/databricks_admin").is_dir(), (
        "hub/apps/databricks_admin/ rule points at a directory that does "
        "not exist (the dead-path direction of GATE-41)."
    )


def test_pin_catches_removed_databricks_rule(tmp_path):
    """Non-vacuity: without the databricks rule the scan MUST flag the
    estate — proving a green run on the real file is a real check (the
    W18 typo class the gate exists to forbid)."""
    stripped = tmp_path / "CODEOWNERS"
    lines = [
        line
        for line in CODEOWNERS.read_text(encoding="utf-8").splitlines()
        if "hub/apps/databricks_admin/" not in line
    ]
    stripped.write_text("\n".join(lines), encoding="utf-8")

    uncovered = uncovered_paths(stripped, ROOT)
    assert uncovered, (
        "Removing the databricks_admin rule was NOT caught by the coverage "
        "scan — the pin is vacuous."
    )
    assert any(p.startswith("hub/apps/databricks_admin/") for p in uncovered), (
        f"Expected hub/apps/databricks_admin/* paths to surface as uncovered, got: {uncovered[:5]}"
    )
