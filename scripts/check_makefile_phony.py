#!/usr/bin/env python3
"""
close-test-coverage-gaps 0.1 — Makefile ``.PHONY`` completeness gate.

Every target declared in the Makefile MUST appear in a ``.PHONY`` line.
A target that is not phony silently stops running the moment a file or
directory with its name exists next to the Makefile (the canonical Make
failure mode) — and batch targets in particular drift out of ``.PHONY``
when they are added without updating line 1 (measured: ``test-batch-6-7``
…``6-21``, ``7-7``…``7-12``, ``8-4``…``8-7``, ``test-batch-1-6-clamav``,
``staging-*`` and the lint helpers were all runnable-but-unprotected).
This gate makes the drift fail the build, so the ``test-batch-13-x``
targets (close-test-coverage-gaps 0.3/0.4) are covered automatically the
moment they land.

Parsing is static text only (no make evaluation):

- a target line is a line at column 0 matching ``<name>… : [prereqs]``;
  a multi-target rule (``a b c: deps``) contributes EVERY name;
- recipe lines (leading TAB) and variable assignments (``:=``, ``=``,
  ``?=``, ``+=``, ``!=``) are skipped;
- directives (``ifeq/ifneq/ifdef/ifndef/else/endif/include/export/
  define/endef/override/unexport/vpath``) are skipped;
- pattern rules (names containing ``%``) are skipped — they are
  implicit-rule definitions, not phony candidates;
- special targets (names starting with ``.``) are skipped — they are
  Make built-ins, not phony candidates.

Exit 0 on clean, 1 with the missing-target list.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"

# Column-0 Make directives that are not targets.
_DIRECTIVES = {
    "ifeq",
    "ifneq",
    "ifdef",
    "ifndef",
    "else",
    "endif",
    "include",
    "-include",
    "sinclude",
    "export",
    "unexport",
    "override",
    "define",
    "endef",
    "vpath",
}

# A variable assignment, not a target rule.
_VAR_ASSIGN = re.compile(r"^[A-Za-z0-9_ .-]+[+?:!]?=")

# A rule line: one or more target names, then `:`.  Pattern rules (`%.o`)
# are excluded after the match.
_TARGET_RULE = re.compile(r"^([^:#\t\n]+?)\s*:")


def parse_targets(text: str) -> set[str]:
    """Extract every declared target name from Makefile text."""
    targets: set[str] = set()
    for raw_line in text.splitlines():
        if not raw_line or raw_line[0] in " \t":
            # Recipe line or continuation — never a target.
            continue
        first_word = raw_line.split(None, 1)[0] if raw_line.split() else ""
        if first_word in _DIRECTIVES or first_word.startswith("export "):
            continue
        if _VAR_ASSIGN.match(raw_line):
            continue
        match = _TARGET_RULE.match(raw_line)
        if not match:
            continue
        for name in match.group(1).split():
            if name.startswith(".") or "%" in name:
                # Special targets (.PHONY itself) and pattern rules are
                # not phony candidates.
                continue
            targets.add(name)
    return targets


def parse_phony(text: str) -> set[str]:
    """Collect every name across ALL ``.PHONY:`` lines."""
    phony: set[str] = set()
    for raw_line in text.splitlines():
        if raw_line.startswith(".PHONY"):
            phony.update(raw_line.split(":", 1)[1].split())
    return phony


def find_missing(text: str) -> tuple[set[str], set[str], list[str]]:
    """Return ``(targets, phony, sorted_missing)`` for Makefile text."""
    targets = parse_targets(text)
    phony = parse_phony(text)
    missing = sorted(targets - phony)
    return targets, phony, missing


def main() -> int:
    text = MAKEFILE.read_text()
    targets, phony, missing = find_missing(text)

    if missing:
        print(f"MAKEFILE-PHONY gate: {len(missing)} target(s) missing from .PHONY:")
        for name in missing:
            print(f"  {name}")
        print(
            f"  ({len(targets)} targets declared, {len(targets & phony)} covered; "
            "add the missing names to the .PHONY line in the Makefile)"
        )
        return 1

    print(f"MAKEFILE-PHONY gate: PASSED — all {len(targets)} targets are listed in .PHONY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
