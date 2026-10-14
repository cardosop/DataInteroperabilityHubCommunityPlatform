#!/usr/bin/env python3
"""GATE-54 — control-plane provider-boundary import checker
(openspec oss-release-remediation W4.6 / G1).

Enforces the "Control-Plane Provider Boundary" normative requirement
(openspec add-databricks-control-plane): control-plane estate code is
per-provider — NO module outside ``hub.apps.databricks_admin`` may import
estate modules from it (``from hub.apps.databricks_admin...`` / ``import
hub.apps.databricks_admin...`` at ANY nesting level — module, function,
class), except the audited sanctioned seams pinned in
``scripts/provider_boundary_allowlist.txt``.

Scope decisions (each one pinned by
``scripts/tests/test_check_provider_boundary.py`` — no mocks, real fixture
trees):

- **Test files are out of the blocking scope** — the G1 audit's finding is
  the "5 non-test consumers"; test files legitimately construct estate
  fixtures and reuse the estate's own test utilities
  (``RecordingHandler``/``_fixtures``) against real local servers.
  ``--include-tests`` lists their estate imports ADVISORY (the exit code is
  unchanged) so the W4.6 evidence can name them.
- **``if TYPE_CHECKING:`` imports are exempt** — a type-only annotation
  creates no runtime coupling; the boundary protects the runtime, not the
  type checker. The exemption is proven non-vacuous by pin: the same
  import outside the TYPE_CHECKING guard flips the gate RED.
- **String references are not imports** — ``apps.get_model(
  "databricks_admin", ...)``, migration FK labels, INSTALLED_APPS/urls
  entries, and the OpenAPI ``target_class`` strings are Django-idiomatic
  lazy references (no module coupling); they are out of scope by design
  and documented in CLAUDE.md.
- **Dead allowlist anchors are violations** — drift fails LOUDLY (the
  W0.4b lesson: 541 silent violations accumulated while GATE-29 had no CI).

Allowlist ratchet (``--check-allowlist-growth``): per-file entry-count
comparison against git HEAD (the GATE-29 accounting — a line shift inside
an allowlisted file is churn and passes; a NEW entry in any file is growth
and fails; removals always pass). A missing HEAD baseline (the allowlist
not yet committed) is treated as empty — every entry counts as growth.

Usage:
    python scripts/check_provider_boundary.py            # fail on violations
    python scripts/check_provider_boundary.py --list     # print all violations
    python scripts/check_provider_boundary.py --include-tests   # + advisory test rows
    python scripts/check_provider_boundary.py --check-allowlist-growth
    python scripts/check_provider_boundary.py --root DIR --allowlist FILE  # tests
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

DEFAULT_SCAN_DIRS = ("hub", "tests", "scripts", "cli", "sdk")

#: The provider estate app — the single protected namespace.
_ESTATE_APP = "hub.apps.databricks_admin"

DEFAULT_ALLOWLIST = "scripts/provider_boundary_allowlist.txt"


def _is_test_file(relpath: str) -> bool:
    """Test-file classification: any path component named ``tests`` (or
    ``test``) or a ``test_*``/``*_test`` basename. Everything under a
    tests/ dir counts — helpers and factories are test-support."""
    parts = Path(relpath).parts
    if any(part in ("tests", "test") for part in parts):
        return True
    name = parts[-1]
    return name.startswith("test_") or name.endswith("_test.py")


def _in_estate_app(relpath: str) -> bool:
    """Files inside the estate app itself may import their own modules."""
    return relpath.startswith(f"{_ESTATE_APP.replace('.', '/')}/")


def _estate_import_lines(tree: ast.Module):
    """Yield ``(lineno, in_typechecking_guard)`` for every Import/ImportFrom
    node referencing the estate app, at any nesting depth."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        in_guard = bool(_walk_to_typechecking_guard(node))
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _ESTATE_APP or alias.name.startswith(
                    _ESTATE_APP + "."
                ):
                    yield node.lineno, in_guard
                    break
        else:  # ImportFrom
            module = node.module or ""
            if module == _ESTATE_APP or module.startswith(_ESTATE_APP + "."):
                yield node.lineno, in_guard


def _walk_to_typechecking_guard(node: ast.AST) -> ast.If | None:
    """The innermost enclosing ``if TYPE_CHECKING:`` guard, if any.

    Matches both the canonical ``from typing import TYPE_CHECKING`` shape
    (a bare Name test) and the qualified ``typing.TYPE_CHECKING`` form."""
    parent = getattr(node, "_provider_boundary_parent", None)
    if parent is None:
        return None
    if isinstance(parent, ast.If):
        test = parent.test
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return parent
        if (
            isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id == "typing"
        ):
            return parent
    return _walk_to_typechecking_guard(parent)


def _attach_parents(tree: ast.AST) -> None:
    """Attach ``_provider_boundary_parent`` references so the
    TYPE_CHECKING-guard walk can climb the AST (the guard is lexical)."""
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            # ast nodes carry a plain __dict__ — direct attribute assignment.
            child._provider_boundary_parent = parent


def collect_imports_with_guards(
    root: Path,
    scan_dirs: tuple[str, ...] = DEFAULT_SCAN_DIRS,
) -> list[tuple[str, int, bool, bool]]:
    """AST-scan every Python file under ``scan_dirs`` for imports of the
    estate app at any nesting level, with TYPE_CHECKING-guard detection.

    Returns ``(relpath, lineno, is_test, is_typechecking)`` tuples — one
    per import statement (not per imported name).
    """
    findings: list[tuple[str, int, bool, bool]] = []
    for scan_dir in scan_dirs:
        base = root / scan_dir
        if not base.is_dir():
            continue
        for py_file in sorted(base.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            if any(part in (".venv", "venv", "node_modules") for part in py_file.parts):
                continue
            relpath = py_file.relative_to(root).as_posix()
            if _in_estate_app(relpath):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=relpath)
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue
            _attach_parents(tree)
            is_test = _is_test_file(relpath)
            for lineno, typechecking in _estate_import_lines(tree):
                findings.append((relpath, lineno, is_test, typechecking))
    return findings


def parse_allowlist(path: Path) -> list[tuple[str, int, str]]:
    """Parse the allowlist — exact ``relpath:lineno:reason`` triples.

    A malformed line (no integer lineno) fails LOUDLY with ValueError:
    a silently dropped entry would weaken the gate."""
    entries: list[tuple[str, int, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            relpath, lineno_str, reason = line.split(":", 2)
            entries.append((relpath, int(lineno_str), reason))
        except ValueError as exc:
            raise ValueError(
                f"malformed allowlist entry {line!r} in {path} "
                "(expected relpath:lineno:reason)"
            ) from exc
    return entries


def _violations_report(
    findings: list[tuple[str, int, bool, bool]],
    allowlist_entries: list[tuple[str, int, str]],
    *,
    include_tests: bool,
):
    """Classify the findings: blocking violations (non-test, not
    TYPE_CHECKING-guarded, not allowlisted), dead allowlist anchors, and
    the advisory test-file rows."""
    allowlisted = {(relpath, lineno) for relpath, lineno, _reason in allowlist_entries}
    violations: list[tuple[str, int]] = []
    advisory: list[tuple[str, int]] = []
    for relpath, lineno, is_test, typechecking in findings:
        if is_test:
            advisory.append((relpath, lineno))
            continue
        if typechecking:
            continue
        if (relpath, lineno) in allowlisted:
            continue
        violations.append((relpath, lineno))

    # Dead anchors: an allowlist entry matching no blocking violation
    # (a drifted line anchor fails loudly — never silently rots).
    blocking_sites = {
        (relpath, lineno)
        for relpath, lineno, is_test, typechecking in findings
        if not is_test and not typechecking
    }
    dead_anchors = [
        (relpath, lineno)
        for relpath, lineno, _reason in allowlist_entries
        if (relpath, lineno) not in blocking_sites
    ]

    if include_tests:
        return violations, dead_anchors, advisory
    return violations, dead_anchors, []


def _print_violations(
    violations, dead_anchors, advisory, *, include_tests: bool, out
) -> None:
    for relpath, lineno in sorted(violations):
        print(
            f"VIOLATION {relpath}:{lineno} — imports "
            f"{_ESTATE_APP} outside the sanctioned seams",
            file=out,
        )
    for relpath, lineno in sorted(dead_anchors):
        print(
            f"DEAD ANCHOR {relpath}:{lineno} — allowlist entry matches no import",
            file=out,
        )
    if include_tests:
        for relpath, lineno in sorted(advisory):
            print(
                f"ADVISORY (test file) {relpath}:{lineno} — test-scope estate import",
                file=out,
            )


def allowlist_ratchet_report(head_text: str, work_text: str):
    """Per-file NET accounting between the HEAD and working allowlists
    (the GATE-29 semantics): a file whose working entry count EXCEEDS its
    HEAD count is GROWTH; equal counts (line churn) and shrinks pass.

    Pure function — the CLI feeds it ``git show HEAD:<allowlist>``."""
    from collections import Counter

    def _count(text: str) -> Counter:
        counts: Counter = Counter()
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                relpath, lineno_str, _reason = line.split(":", 2)
                int(lineno_str)
            except ValueError:
                continue
            counts[relpath] += 1
        return counts

    head = _count(head_text)
    work = _count(work_text)
    grown = sorted(relpath for relpath in work if work[relpath] > head.get(relpath, 0))
    return RatchetReport(grown=grown)


class RatchetReport:
    def __init__(self, grown: list[str]):
        self.grown = grown

    @property
    def ok(self) -> bool:
        return not self.grown


def _read_head_allowlist(root: Path, allowlist_relpath: str) -> str | None:
    """``git show HEAD:<allowlist>`` — None when the baseline does not
    exist (the allowlist is not committed yet; every entry then counts as
    growth, documented)."""
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{allowlist_relpath}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GATE-54 — provider-boundary import checker"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to scan (default: this script's parent.parent)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="allowlist file (default: <root>/scripts/provider_boundary_allowlist.txt)",
    )
    parser.add_argument("--list", action="store_true", help="print every finding")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="list test-file estate imports ADVISORY (exit code unchanged)",
    )
    parser.add_argument(
        "--check-allowlist-growth",
        action="store_true",
        help="ratchet the allowlist against git HEAD (per-file accounting)",
    )
    args = parser.parse_args(argv)

    allowlist_path = args.allowlist or (args.root / DEFAULT_ALLOWLIST)
    allowlist_entries = parse_allowlist(allowlist_path)

    findings = collect_imports_with_guards(args.root)
    violations, dead_anchors, advisory = _violations_report(
        findings, allowlist_entries, include_tests=args.include_tests
    )

    exit_code = 0

    if args.list:
        for relpath, lineno, is_test, typechecking in findings:
            scope = (
                "test" if is_test else ("typechecking" if typechecking else "blocking")
            )
            print(f"{scope}\t{relpath}:{lineno}")

    _print_violations(
        violations,
        dead_anchors,
        advisory,
        include_tests=args.include_tests,
        out=sys.stdout,
    )
    if violations:
        exit_code = 1
        print(
            f"\nGATE-54 FAILED: {len(violations)} unsanctioned import site(s) "
            f"of {_ESTATE_APP} (outside the estate app, not TYPE_CHECKING-only, "
            f"not allowlisted). Route them through the sanctioned seams "
            f"(CLAUDE.md 'Control-Plane Provider Boundary Contract').",
        )
    if dead_anchors:
        exit_code = 1
        print(
            f"\nGATE-54 FAILED: {len(dead_anchors)} dead allowlist anchor(s) — "
            f"drifted or removed sites. Re-anchor or delete them; the allowlist "
            f"never rots silently."
        )

    if args.check_allowlist_growth:
        allowlist_relpath = allowlist_path.relative_to(args.root).as_posix()
        head_text = _read_head_allowlist(args.root, allowlist_relpath)
        if head_text is None:
            print(
                "GATE-54 ratchet: no HEAD baseline for the allowlist "
                "(not yet committed) — every entry counts as growth."
            )
            head_text = ""
        report = allowlist_ratchet_report(head_text, allowlist_path.read_text())
        if not report.ok:
            exit_code = 1
            print(
                "GATE-54 ratchet FAILED: allowlist GROWTH in "
                + ", ".join(report.grown)
                + " — new audited violations may only ship behind the "
                "sanctioned seams, never new allowlist entries."
            )

    if exit_code == 0:
        print("GATE-54 PASSED: provider boundary clean.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
