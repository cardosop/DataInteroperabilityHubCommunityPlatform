#!/usr/bin/env python3
"""CODEOWNERS path gate (Phase T.6 / W18).

A CODEOWNERS typo is invisible until the owned tree ships with no
codeowner and no required reviewer — the W18 incident: ``sdk/py/`` was
declared while the real directory is ``sdk/python/``, so
``sdk/python/tests/security/test_api_key_scope.py`` had no owner. This
gate asserts every CODEOWNERS path prefix resolves to the tree.

Resolution rules (GitHub semantics, documented rather than assumed):
  * DIRECTORY rules (trailing ``/``) must resolve to an existing directory.
  * FILE rules (no glob characters) must resolve to an existing file.
  * GLOB rules (``*``/``?``/``[``) must match at least one path — single
    ``*`` matches within the same directory level as the literal prefix,
    ``**`` recurses (``pathlib.glob`` implements both natively).
  * Negation rules (``!pattern``) are excluded from resolution — they
    modify earlier rules and GitHub owns their semantics.
  * Comment/blank lines are ignored.

Exit codes: 0 clean, 1 dead path(s), 2 usage error.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CODEOWNERS = Path(__file__).resolve().parent.parent / ".github" / "CODEOWNERS"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent

_GLOB_CHARS = ("*", "?", "[")


@dataclass
class CodeownersEntry:
    pattern: str
    owners: list[str]


def parse_codeowners(path: Path) -> list[CodeownersEntry]:
    """Parse CODEOWNERS into (pattern, owners) entries.

    Comments and blanks are skipped; owner columns are everything after
    the first whitespace run following the pattern. Negation rules
    (``!pattern``) are dropped — they scope earlier rules, not the tree.
    """
    entries: list[CodeownersEntry] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            continue
        parts = line.split()
        if len(parts) < 2:
            # A pattern with no owners is itself an ownership gap — the
            # parser keeps it (resolution still runs); the owners column is
            # deliberately not validated here (GitHub validates it).
            pattern = parts[0]
            owners: list[str] = []
        else:
            pattern, owners = parts[0], parts[1:]
        entries.append(CodeownersEntry(pattern=pattern, owners=owners))
    return entries


def _pattern_matches_something(pattern: str, root: Path) -> bool:
    """Does the (glob-capable) pattern match at least one path in the tree?"""
    if pattern.endswith("/"):
        pattern = pattern[:-1]
        return (root / pattern).is_dir() or any(root.glob(pattern + "/**"))
    if any(ch in pattern for ch in _GLOB_CHARS):
        # pathlib glob: single `*` stays within one level; `**` recurses —
        # matching GitHub's semantics for each. Python 3.12 raises for a
        # `**` glued to a name (`**.md` — the "any depth" form GitHub
        # accepts); normalize it to the recursive form first.
        if pattern.startswith("**") and not pattern.startswith("**/"):
            # ``**.md`` (GitHub: any depth) ≡ ``**/*.md`` — keep the
            # filename's own glob star and insert the recursive prefix.
            pattern = "**/*" + pattern[2:]
        return any(root.glob(pattern)) or any(root.glob("**/" + pattern))
    return (root / pattern).exists()


def resolve_violations(codeowners: Path, root: Path) -> list[str]:
    """Patterns in the document that resolve to nothing in the tree."""
    violations: list[str] = []
    for entry in parse_codeowners(codeowners):
        if not _pattern_matches_something(entry.pattern, root):
            violations.append(entry.pattern)
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CODEOWNERS path gate — every path prefix must resolve to the tree."
    )
    parser.add_argument("--codeowners", type=Path, default=DEFAULT_CODEOWNERS)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)

    if not args.codeowners.exists():
        print(f"CODEOWNERS gate: document missing at {args.codeowners}")
        return 2

    violations = resolve_violations(args.codeowners, args.root)
    if violations:
        print(
            f"CODEOWNERS gate: {len(violations)} path(s) resolve to nothing — "
            "the owned tree would ship with no codeowner and no required "
            "reviewer (the W18 sdk/py typo class):"
        )
        for pattern in violations:
            print(f"  {pattern}")
        return 1

    entries = len(parse_codeowners(args.codeowners))
    print(f"CODEOWNERS gate: clean — {entries} rule(s), every path resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
