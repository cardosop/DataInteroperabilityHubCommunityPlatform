"""
hub/tests/test_no_named_cursors.py

CI-enforced ban on named database cursors.

PgBouncer operates in transaction pooling mode (pool_mode=transaction).
In this mode a server connection is returned to the pool after each
transaction, which breaks server-side state that spans transactions:

  - Named cursors (DECLARE <name> CURSOR … / FETCH … / CLOSE …)
    require a dedicated connection for the lifetime of the cursor.
    Django creates named cursors via cursor(name="…").  They are
    incompatible with transaction pooling and will raise
    "cursor does not exist" errors in production.

  - Advisory locks, LISTEN/NOTIFY, and SET/RESET outside a transaction
    share the same problem — they are tracked separately and NOT caught
    by this test.

This test scans every Python source file under hub/ and services/ for
patterns that create named cursors and fails the CI build if any are found,
preventing accidental reintroduction.

Allowed exemptions (add to EXEMPTION_PATHS):
  - Tests that explicitly verify the absence of named cursors (this file).
  - Infrastructure tooling that connects directly to PostgreSQL bypassing
    PgBouncer (e.g. pg_dump scripts, migration runners) — these must be
    documented in EXEMPTION_PATHS with a comment explaining why.
"""

import ast
import pathlib
import re
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root directories to scan (relative to repository root).
SCAN_ROOTS = ["hub", "services"]

# Paths to skip (relative to repository root).  Add entries here only with a
# comment explaining the exemption and why named cursors are safe there.
EXEMPTION_PATHS: set[str] = {
    # This test file itself — it contains the string 'cursor(name=' in
    # comments and docstrings as part of the explanation.
    "hub/tests/test_no_named_cursors.py",
}

# Regex patterns for text-level scanning (catches string literals, comments,
# and dynamic cursor() calls that static AST analysis may miss).
_TEXT_PATTERNS = [
    # Django named cursor: connection.cursor(name="…") or cursor(name=…)
    re.compile(r"""cursor\s*\(\s*name\s*="""),
    # Direct DECLARE … CURSOR SQL in string literals
    re.compile(r"""DECLARE\s+\w+\s+(?:NO\s+SCROLL\s+)?CURSOR""", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _repo_root() -> pathlib.Path:
    """Return the repository root (two levels up from hub/tests/)."""
    return pathlib.Path(__file__).resolve().parent.parent.parent


def _is_exempt(path: pathlib.Path, repo_root: pathlib.Path) -> bool:
    rel = str(path.relative_to(repo_root))
    return rel in EXEMPTION_PATHS


def _scan_file_text(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (line_number, line) pairs that match any forbidden pattern."""
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in _TEXT_PATTERNS:
            if pattern.search(line):
                hits.append((lineno, line.rstrip()))
                break
    return hits


def _scan_file_ast(path: pathlib.Path) -> list[tuple[int, str]]:
    """
    Walk the AST to find cursor(name=…) calls.

    Text scanning catches most cases, but AST analysis catches multi-line
    calls where the keyword argument is on a different line from 'cursor'.
    """
    hits: list[tuple[int, str]] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return hits

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match connection.cursor(…) or cursor(…)
        is_cursor_call = (
            isinstance(func, ast.Attribute) and func.attr == "cursor"
        ) or (isinstance(func, ast.Name) and func.id == "cursor")
        if not is_cursor_call:
            continue
        # Check for 'name' keyword argument
        for kw in node.keywords:
            if kw.arg == "name":
                hits.append(
                    (
                        node.lineno,
                        f"cursor(name=…) at line {node.lineno}",
                    )
                )
    return hits


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def _collect_violations() -> list[str]:
    repo_root = _repo_root()
    violations: list[str] = []

    for root_name in SCAN_ROOTS:
        scan_root = repo_root / root_name
        if not scan_root.exists():
            continue
        for py_file in sorted(scan_root.rglob("*.py")):
            if _is_exempt(py_file, repo_root):
                continue

            rel = str(py_file.relative_to(repo_root))

            # Text-level scan (fast, catches everything including strings)
            text_hits = _scan_file_text(py_file)
            for lineno, line in text_hits:
                violations.append(f"  {rel}:{lineno}: {line.strip()}")

            # AST scan for multi-line calls (skip if text already flagged)
            if not text_hits:
                ast_hits = _scan_file_ast(py_file)
                for lineno, desc in ast_hits:
                    violations.append(f"  {rel}:{lineno}: {desc}")

    return violations


def test_no_named_cursors() -> None:
    """
    Fail if any Python source file uses named database cursors.

    Named cursors are incompatible with PgBouncer transaction pooling.
    See module docstring for details and exemption instructions.
    """
    violations = _collect_violations()
    if not violations:
        return

    report = textwrap.dedent(
        """
        ╔══════════════════════════════════════════════════════════════════╗
        ║  NAMED CURSOR DETECTED — incompatible with PgBouncer transaction ║
        ║  pooling (pool_mode=transaction).                                ║
        ╠══════════════════════════════════════════════════════════════════╣
        ║  Named cursors hold a server connection open across transactions  ║
        ║  and will fail with "cursor does not exist" in production.       ║
        ║                                                                  ║
        ║  Fix: rewrite the query using LIMIT/OFFSET or keyset pagination  ║
        ║  instead of a server-side cursor.                                ║
        ║                                                                  ║
        ║  If the code connects directly to PostgreSQL (bypassing          ║
        ║  PgBouncer), add the file path to EXEMPTION_PATHS in            ║
        ║  hub/tests/test_no_named_cursors.py with a comment explaining    ║
        ║  why it is safe.                                                 ║
        ╚══════════════════════════════════════════════════════════════════╝

        Violations found:
        """
    ).strip()
    violation_list = "\n".join(violations)
    pytest.fail(f"{report}\n{violation_list}", pytrace=False)
