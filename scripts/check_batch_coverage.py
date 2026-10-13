#!/usr/bin/env python3
"""
close-test-coverage-gaps 0.3 — batch-coverage gate for ``test-batch-13-x``.

``hub/apps/databricks_admin`` (113 test files, 1,462 tests) was the only
test-bearing app with NO Makefile batch: its tests ran exclusively via
the unscoped ``pytest hub/apps/`` catch-alls. This gate pins the
file-list slicing (13-1…13-7 + 13-6a) so the batch can never silently
drift again:

1. every ``test_*.py`` under ``hub/apps/databricks_admin/tests/`` MUST be
   referenced by EXACTLY ONE ``test-batch-13-x`` recipe (0 = a file fell
   out of the batches; ≥2 = duplicated between sub-batches — both break
   the exactly-once budget accounting);
2. the ``test-batch-13`` umbrella MUST invoke every defined 13-x leaf
   target;
3. ``test-batch-all`` MUST invoke ``test-batch-13``;
4. each leaf recipe MUST stay within the static file budget (26 files;
   the test-count budget of ~250 is documented in the ``##`` comments and
   checked by the pin suite against the live Makefile);
5. every ``test-batch-13*`` target MUST appear in ``.PHONY`` (the
   dedicated ``check_makefile_phony.py`` gate covers this globally; this
   check makes the batch domain self-contained).

Parsing is static text only (no make evaluation) — the same discipline
as ``check_makefile_phony.py``: column-0 target lines delimit recipes,
continuation lines accumulate until the next target or non-indented
non-continuation line.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
APP_TESTS = REPO_ROOT / "hub" / "apps" / "databricks_admin" / "tests"

BATCH_PREFIX = "test-batch-13"
MAX_FILES_PER_LEAF = 26

#: Batch-13 leaves that are intentionally NOT umbrella children (task 0.4 —
#: the DATABRICKS_E2E-gated live E2E wrapper runs out-of-band, never as part
#: of the every-push sequence). They still obey every OTHER rule here
#: (file slicing, .PHONY) — only the umbrella-invocation requirement is
#: waived, with the reason recorded.
GATED_LEAVES: dict[str, str] = {
    "test-batch-13-8": "DATABRICKS_E2E=1-gated live sandbox E2E; runs only when an operator arms the gate (task 0.4), never via the umbrella",
}

_TARGET_RULE = re.compile(r"^([^:#\t\n]+?)\s*:")
_FILE_ARG = re.compile(r"hub/apps/databricks_admin/tests/(test_[A-Za-z0-9_]+\.py)")
_INVOKED_TARGET = re.compile(r"\$\(MAKE\)\s+(test-batch-[\w-]+)")


def parse_recipes(text: str) -> dict[str, str]:
    """Map every ``test-batch-13*`` target to its raw recipe text."""
    recipes: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for raw in text.splitlines():
        m = _TARGET_RULE.match(raw)
        if m and not raw.startswith((" ", "\t")):
            if current is not None and lines:
                recipes[current] = "\n".join(lines)
            names = m.group(1).split()
            batch = [n for n in names if n.startswith(BATCH_PREFIX)]
            current = batch[0] if batch else None
            lines = []
            continue
        if current is not None:
            if raw.strip() == "":
                continue
            if raw.startswith(("\t", " ")):
                lines.append(raw)
                continue
            # Back at column 0 on a non-target line — recipe over.
            recipes[current] = "\n".join(lines)
            current = None
            lines = []
    if current is not None and lines:
        recipes[current] = "\n".join(lines)
    return recipes


def recipe_files(recipe_text: str) -> set[str]:
    """All databricks_admin test files referenced by a recipe."""
    return set(_FILE_ARG.findall(recipe_text))


def disk_files() -> set[str]:
    return {p.name for p in APP_TESTS.glob("test_*.py")}


def umbrella_invocations(recipe_text: str) -> set[str]:
    return set(_INVOKED_TARGET.findall(recipe_text))


def find_problems(
    text: str,
    disk_names: set[str] | None = None,
    gated: dict[str, str] | None = None,
) -> list[str]:
    """Find slicing problems. ``disk_names`` defaults to the real on-disk
    files; fixtures inject their own set for pure-text drills. ``gated``
    defaults to ``GATED_LEAVES``; fixtures inject their own for hermetic
    drills."""
    problems: list[str] = []
    gated = GATED_LEAVES if gated is None else gated
    on_disk = disk_files() if disk_names is None else disk_names
    recipes = parse_recipes(text)
    leaves = {t: r for t, r in recipes.items() if t != BATCH_PREFIX}
    files_to_leaves: dict[str, list[str]] = {}
    for target, recipe in leaves.items():
        if len(recipe_files(recipe)) > MAX_FILES_PER_LEAF:
            problems.append(
                f"{target} lists {len(recipe_files(recipe))} files — "
                f"over the {MAX_FILES_PER_LEAF}-file budget; split it"
            )
        for fname in recipe_files(recipe):
            files_to_leaves.setdefault(fname, []).append(target)

    for fname in sorted(on_disk - set(files_to_leaves)):
        problems.append(f"{fname} is not listed in any test-batch-13-x recipe")
    for fname, owners in files_to_leaves.items():
        if len(owners) > 1:
            problems.append(f"{fname} is listed in multiple recipes: {', '.join(sorted(owners))}")
    for fname in sorted(set(files_to_leaves) - on_disk):
        problems.append(f"{fname} is listed in a recipe but does not exist on disk")

    if BATCH_PREFIX in recipes:
        invoked = umbrella_invocations(recipes[BATCH_PREFIX])
        missing = sorted(set(leaves) - set(gated) - invoked)
        if missing:
            problems.append(f"test-batch-13 umbrella does not invoke: {', '.join(missing)}")
        phantom = sorted(invoked - set(leaves))
        if phantom:
            problems.append(
                f"test-batch-13 umbrella invokes undefined targets: {', '.join(phantom)}"
            )
    else:
        problems.append("test-batch-13 umbrella target is missing")

    for name in sorted(set(gated) - set(leaves)):
        problems.append(
            f"{name} is declared GATED but not defined in the Makefile (stale GATED_LEAVES entry)"
        )

    all_text = text
    if "test-batch-all:" in all_text:
        all_recipe = all_text.split("test-batch-all:", 1)[1].split("\n\n", 1)[0]
        if "test-batch-13" not in all_recipe:
            problems.append("test-batch-all does not invoke test-batch-13")
    else:
        problems.append("test-batch-all target is missing")

    phony_line = next((line for line in text.splitlines() if line.startswith(".PHONY")), "")
    phony_names = set(phony_line.split(":", 1)[1].split())
    for target in sorted(set(leaves) | {BATCH_PREFIX}):
        if target not in phony_names:
            problems.append(f"{target} is missing from .PHONY")

    return problems


def main() -> int:
    text = MAKEFILE.read_text()
    problems = find_problems(text)
    if problems:
        print(f"BATCH-COVERAGE gate: {len(problems)} problem(s) in the test-batch-13 slicing:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(
        f"BATCH-COVERAGE gate: PASSED — {len(disk_files())} databricks_admin test "
        "files covered exactly once by the test-batch-13-x recipes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
