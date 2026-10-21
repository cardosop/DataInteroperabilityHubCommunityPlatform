"""Meta-test: every CLI test file must be reachable from a Makefile batch.

The ``test-batch-9-3*`` targets enumerate CLI test files by hand.  A file
that no target selects is never executed by any routine path — it does not
fail, it simply does not run, so it can contradict the production code
indefinitely without anyone noticing.

That is not hypothetical.  ``tests/unit/test_token_refresh_race.py`` sat
outside every batch while asserting a ``_is_token_expired`` contract that
``tests/unit/test_auth.py`` — which *is* batched — asserts the opposite
of.  The orphan was only found by running the directory directly.

Two subtleties this guard has to get right:

* **Root-relative vs cli-relative paths.**  The Makefile drives both the
  project-root suite and the CLI suite, and both have a ``tests/``
  directory.  ``tests/e2e/test_cli_e2e.py`` exists in *both* trees, so
  naively matching cli-relative paths against every ``tests/...`` token in
  the Makefile reports coverage that does not exist.  Only tokens from
  recipe lines that run inside ``cd cli`` count.
* **``--ignore``.**  ``test-batch-9-3`` passes ``--ignore=tests/e2e`` (and
  ``integration``/``performance``), so those paths are explicitly *not*
  selected even though they appear in the Makefile text.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import pytest

CLI_TESTS_DIR = Path(__file__).resolve().parent
CLI_DIR = CLI_TESTS_DIR.parent
MAKEFILE = CLI_DIR.parent / "Makefile"

_TEST_PATH_RE = re.compile(r"(?<![\w/=])tests/[A-Za-z0-9_*./-]+")
_IGNORE_RE = re.compile(r"--ignore=(tests/[A-Za-z0-9_*./-]+)")

# Directories that require a live backend and are deliberately excluded
# from every CLI batch (``test-batch-9-3`` passes ``--ignore`` for each).
# They are NOT covered — this map records that fact with a reason so the
# gap is visible instead of silent.  Removing an entry is how a directory
# gets promoted into a routine path.
UNRUN_BY_DESIGN: dict[str, str] = {
    "tests/e2e/": (
        "Requires a live backend AND a Django test database. Explicitly "
        "--ignore'd by test-batch-9-3; the nightly cli-sdk workflow runs "
        "`-m mvp` only and these modules carry no mvp marker, so nothing "
        "executes them. Tracked as a P.5 residual."
    ),
    "tests/integration/": (
        "Requires a live backend; --ignore'd by test-batch-9-3 and run only in CI compose jobs."
    ),
    "tests/performance/": ("Load/perf tests; --ignore'd by test-batch-9-3 and run on demand."),
}


def _cli_scoped_makefile_text() -> str:
    """Return only the Makefile recipe text that runs inside ``cd cli``.

    Recipes are line-continued with trailing backslashes, so a ``cd cli``
    command spans until the first line that does not continue.
    """
    chunks: list[str] = []
    collecting = False
    for raw_line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if "cd cli" in raw_line:
            collecting = True
        if collecting:
            chunks.append(raw_line)
            if not raw_line.rstrip().endswith("\\"):
                collecting = False
    return "\n".join(chunks)


def _selectors() -> tuple[set[str], set[str]]:
    """Return ``(selected, ignored)`` path tokens from CLI-scoped recipes."""
    text = _cli_scoped_makefile_text()
    ignored = set(_IGNORE_RE.findall(text))
    selected = set(_TEST_PATH_RE.findall(text)) - ignored
    return selected, ignored


def _matches(rel_path: str, selector: str) -> bool:
    if selector.endswith("/"):
        return rel_path.startswith(selector)
    return fnmatch.fnmatch(rel_path, selector) or rel_path.startswith(selector.rstrip("/") + "/")


def _cli_test_files() -> list[str]:
    """Every ``test_*.py`` under ``cli/tests/``, relative to ``cli/``."""
    return sorted(
        path.relative_to(CLI_DIR).as_posix()
        for path in CLI_TESTS_DIR.rglob("test_*.py")
        if path.is_file()
    )


def test_makefile_is_readable() -> None:
    """Guard the guard: a moved Makefile must fail loudly, not silently pass."""
    assert MAKEFILE.is_file(), f"Makefile not found at {MAKEFILE}"
    selected, _ = _selectors()
    assert selected, f"No CLI-scoped 'tests/...' path tokens found in {MAKEFILE}"


def test_unrun_by_design_entries_are_still_unrun() -> None:
    """An UNRUN_BY_DESIGN entry that IS now batched must be removed.

    Keeps the exclusion map honest: once a directory gets wired into a
    target, its excuse has to go so the gap does not stay documented as
    open after it is closed.
    """
    selected, _ = _selectors()
    promoted = sorted(
        prefix
        for prefix in UNRUN_BY_DESIGN
        if any(_matches(prefix.rstrip("/") + "/x.py", sel) for sel in selected)
    )
    if promoted:
        pytest.fail(
            "These directories are now selected by a CLI batch but are still "
            "listed in UNRUN_BY_DESIGN — remove them to lock the win:\n"
            + "\n".join(f"  {p}" for p in promoted)
        )


def test_every_cli_test_file_is_in_a_batch() -> None:
    """Each CLI test file MUST be batched, or declared UNRUN_BY_DESIGN."""
    selected, _ = _selectors()
    orphans = [
        f
        for f in _cli_test_files()
        if not any(_matches(f, sel) for sel in selected)
        and not any(f.startswith(prefix) for prefix in UNRUN_BY_DESIGN)
    ]
    if orphans:
        listing = "\n".join(f"  {o}" for o in orphans)
        pytest.fail(
            f"{len(orphans)} CLI test file(s) are selected by no Makefile "
            f"batch target, so no routine path runs them:\n"
            f"{listing}\n"
            "Add each file to the appropriate test-batch-9-3* target in the "
            "root Makefile, or record the directory in UNRUN_BY_DESIGN with "
            "a reason."
        )
