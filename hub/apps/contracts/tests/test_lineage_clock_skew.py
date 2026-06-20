"""
Phase 228 (228.0.23, REQ-LIN-F5-006) — clock-skew invariant.

Asserts that every lineage write path uses **DB-side time**
(``Func('NOW')`` / ``models.functions.Now`` / ``auto_now_add`` /
``auto_now``) and never application time. Application time would be
clock-skewed across pods and could violate the SCD Type 2 monotonicity
invariant (``valid_from`` of a re-opened edge must be > the
``valid_to`` of the just-closed prior edge).

The test uses static analysis on the source files — it greps for
``timezone.now()`` / ``datetime.now()`` / ``time.time()`` calls in the
lineage write paths and asserts an allow-list of legitimate uses
(test fixtures, audit-event metadata, observability). Production
write paths are forbidden from using app time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

# Files that constitute the lineage WRITE path. App-time calls in
# these files are forbidden.
LINEAGE_WRITE_FILES = (
    "hub/apps/contracts/lineage_sync.py",
    "hub/apps/contracts/management/commands/backfill_lineage_edges.py",
    # Note: ``lineage_service.py`` is read-only; not in the write set.
    # The model itself uses ``db_default=Now()`` declaratively which is
    # the DB-side primitive — the test asserts on the source string.
    "hub/apps/contracts/models.py",
)

# App-time call patterns that violate REQ-LIN-F5-006 in write paths.
# Each pattern is a regex matched against each LINE of the source.
APP_TIME_PATTERNS = (
    # Application-time wall-clock calls.
    re.compile(r"\btimezone\.now\s*\("),
    re.compile(r"\bdatetime\.now\s*\("),
    re.compile(r"\bdatetime\.utcnow\s*\("),
    re.compile(r"\btime\.time\s*\("),
)


def _read_source(rel: str) -> list[tuple[int, str]]:
    """Return ``(line_number, line_text)`` for each line in the file."""
    path = REPO_ROOT / rel
    text = path.read_text(encoding="utf-8")
    return list(enumerate(text.splitlines(), start=1))


def _is_in_models_lineage_block(rel: str, lineno: int) -> bool:
    """Returns True iff ``lineno`` is inside the ``LineageEdge`` /
    ``LineageEdgeType`` class definitions in ``models.py``. Other
    classes in the same file (``Contract`` etc.) are out of scope —
    this test guards lineage-only writes."""
    if not rel.endswith("models.py"):
        return True  # non-models.py files: every line is in scope.
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    lines = text.splitlines()
    # Find the LineageEdge / LineageEdgeType class boundaries.
    class_starts = [
        i + 1
        for i, ln in enumerate(lines)
        if re.match(r"^class\s+(LineageEdge|LineageEdgeType)\b", ln)
    ]
    if not class_starts:
        return False
    # The block ends at the next top-level ``class`` declaration or
    # EOF, whichever comes first.
    next_class_starts = [
        i + 1
        for i, ln in enumerate(lines)
        if re.match(r"^class\s+\w+", ln) and (i + 1) not in class_starts
    ]
    block_start = min(class_starts)
    later_class_starts = [c for c in next_class_starts if c > block_start]
    block_end = min(later_class_starts) if later_class_starts else len(lines) + 1
    return block_start <= lineno < block_end


@pytest.mark.parametrize("rel", LINEAGE_WRITE_FILES)
def test_no_app_time_in_lineage_write_path(rel: str):
    """REQ-LIN-F5-006: no ``timezone.now()`` / ``datetime.now()`` /
    ``time.time()`` in the lineage write path.

    The handler MUST use DB-side ``NOW()`` so SCD Type 2 monotonicity
    survives clock skew between pods. Failure of this test indicates
    the handler is using app time — a regression that would produce
    non-monotonic ``valid_from`` values under multi-pod load.
    """
    violations = []
    for lineno, line in _read_source(rel):
        # Skip comments + docstrings.
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Skip lines that are inside a module-level test fixture or
        # comment-mode reference (best-effort — if a write path embeds
        # the call in a string the test is too strict, but that's a
        # safer error mode than silently passing).
        for pat in APP_TIME_PATTERNS:
            if pat.search(line):
                if not _is_in_models_lineage_block(rel, lineno):
                    continue
                violations.append((rel, lineno, line.strip()))

    assert violations == [], (
        "REQ-LIN-F5-006 violation — lineage write path uses application "
        "time. Use ``models.functions.Now()`` / ``Func('NOW')`` / "
        "``auto_now``/``auto_now_add`` instead. Offending lines:\n"
        + "\n".join(f"  {rel}:{lineno}: {text}" for rel, lineno, text in violations)
    )


def test_lineage_edge_valid_from_uses_db_default():
    """Pin the model's ``valid_from`` field declaration: it must use
    ``db_default=Now()`` (or ``Func('NOW')``) — not ``default=...``
    with an app-time callable.

    Strips comment lines from the field-declaration block before
    matching so a comment that mentions the search terms cannot
    spuriously satisfy the assertion. The actual code in the field
    block is what guards REQ-LIN-F5-006, not the surrounding prose.
    """
    text = (REPO_ROOT / "hub/apps/contracts/models.py").read_text(
        encoding="utf-8",
    )
    # Locate the LineageEdge class block.
    block_match = re.search(
        r"class\s+LineageEdge\s*\(.+?\):(.+?)(?=^class\s+\w|\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert block_match is not None, "LineageEdge class block not found"
    block = block_match.group(1)
    # Strip ``#`` comment-only lines so prose mentioning ``Func('NOW')``
    # doesn't satisfy the assertion when the actual field declaration
    # uses a different default.
    code_only = "\n".join(ln for ln in block.splitlines() if not ln.strip().startswith("#"))
    valid_from = re.search(
        r"valid_from\s*=\s*models\.DateTimeField\(([^)]+)\)",
        code_only,
    )
    assert valid_from is not None, "valid_from field not found"
    args = valid_from.group(1)
    assert "db_default=" in args and "Now" in args, (
        f"valid_from must use db_default=Now() per REQ-LIN-F5-006; args={args!r}"
    )
