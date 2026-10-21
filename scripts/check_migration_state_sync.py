#!/usr/bin/env python3
"""Migration state-sync lint — bans DDL that is not recorded in migration state.

Why this exists
===============
On 2026-08-25 ``makemigrations --check`` was found reporting **70 pending
operations across 16 apps**, four of them destructive (including a ``DROP
COLUMN`` on a populated, foreign-keyed column). The root cause was a single
recurring pattern:

    migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunSQL("ALTER TABLE ... ADD COLUMN ...")],
        state_operations=[],          # <-- the bug
    )

The database gets fixed; Django's migration state never learns about the
change. The autodetector therefore re-proposes that change on **every**
subsequent run, forever. Worse, the re-proposed operation is generated against
a stale model state, which is how a plain ``AddField`` turns into a
``RemoveField`` (i.e. ``DROP COLUMN``) a few phases later.

``state_operations=[]`` is almost never what you want. If the DDL genuinely
changed the schema, the state must say so. The legitimate uses are:

* the DDL is a no-op with respect to Django's model state (RLS policies,
  GRANTs, extensions, non-model indexes) — in which case there is nothing to
  record and ``SeparateDatabaseAndState`` is not needed at all;
* a follow-up migration records the state separately — in which case put the
  state operation THERE and add an allowlist entry naming it.

Rules
=====
``state-not-recorded`` (error)
    ``SeparateDatabaseAndState`` with non-empty ``database_operations`` and
    empty/absent ``state_operations``.

``ddl-outside-state`` (warning)
    A ``RunSQL`` whose FORWARD sql performs model-visible schema DDL
    (ADD/DROP/ALTER COLUMN, RENAME, CREATE/DROP TABLE) without being wrapped in
    ``SeparateDatabaseAndState``. ``reverse_sql`` is deliberately ignored — the
    reverse direction is *supposed* to drop things.

Analysis is AST-based, so comments and docstrings that merely mention
``DROP COLUMN`` are not matched (a defect that makes the older regex-based
``scripts/lint_migrations.py`` too noisy to run as a gate).

Usage
=====
    python scripts/check_migration_state_sync.py                  # changed vs origin/main
    python scripts/check_migration_state_sync.py --base-ref HEAD~1
    python scripts/check_migration_state_sync.py --all            # whole tree
    python scripts/check_migration_state_sync.py --json
    python scripts/check_migration_state_sync.py path/to/0001.py  # explicit files

Exit code 1 on any error-severity finding, else 0.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

# ── Pre-existing offenders ──────────────────────────────────────────────
#
# These shipped before this lint existed and are load-bearing on already
# migrated databases, so they cannot simply be edited. Each is paired with the
# migration that retro-records its state. Do NOT add entries without one.
ALLOWLIST: dict[str, str] = {
    "hub/apps/transformation/migrations/0015_ensure_prefect_flow_run_id_column.py": (
        "State retro-recorded by transformation/0017 (state-only AddField)."
    ),
    "hub/apps/orchestration/migrations/0012_ensure_lineage_edge_column.py": (
        "State retro-recorded by orchestration/0014."
    ),
}

# Model-visible schema DDL. Deliberately excludes ENABLE ROW LEVEL SECURITY,
# CREATE POLICY, GRANT and CREATE EXTENSION — those do not affect model state.
_DDL_MARKERS = (
    "ADD COLUMN",
    "DROP COLUMN",
    "ALTER COLUMN",
    "RENAME TO",
    "RENAME COLUMN",
    "CREATE TABLE",
    "DROP TABLE",
)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    severity: str
    rule: str
    message: str


def _callee(node: ast.Call) -> str:
    """Return the called name, e.g. ``migrations.RunSQL`` -> ``RunSQL``."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _argument(node: ast.Call, name: str, position: int) -> ast.expr | None:
    """Fetch an argument by keyword, falling back to its positional slot."""
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    if len(node.args) > position:
        return node.args[position]
    return None


def _is_empty_sequence(node: ast.expr | None) -> bool:
    """True when the node is absent or an empty list/tuple literal."""
    if node is None:
        return True
    if isinstance(node, ast.List | ast.Tuple):
        return len(node.elts) == 0
    return False


def _forward_sql_strings(node: ast.Call) -> list[str]:
    """Collect string constants from a RunSQL's FORWARD sql argument only.

    ``reverse_sql`` is excluded on purpose: a reverse operation that drops what
    the forward one created is correct, not a defect.
    """
    sql_arg = _argument(node, "sql", 0)
    if sql_arg is None:
        return []
    return [
        n.value
        for n in ast.walk(sql_arg)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def analyse(path: Path, repo_root: Path) -> list[Finding]:
    rel = path.relative_to(repo_root).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return [Finding(rel, 0, "error", "unparseable", f"Could not parse migration: {exc}")]

    findings: list[Finding] = []
    wrapped_runsql: set[int] = set()

    # Pass 1 — SeparateDatabaseAndState blocks.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _callee(node) != "SeparateDatabaseAndState":
            continue

        db_ops = _argument(node, "database_operations", 0)
        state_ops = _argument(node, "state_operations", 1)

        # Remember every RunSQL nested here so pass 2 does not double-report.
        if db_ops is not None:
            for inner in ast.walk(db_ops):
                if isinstance(inner, ast.Call) and _callee(inner) == "RunSQL":
                    wrapped_runsql.add(id(inner))

        if not _is_empty_sequence(db_ops) and _is_empty_sequence(state_ops):
            if rel in ALLOWLIST:
                continue
            findings.append(
                Finding(
                    rel,
                    node.lineno,
                    "error",
                    "state-not-recorded",
                    "SeparateDatabaseAndState changes the database but records no "
                    "state_operations — the autodetector will re-propose this change "
                    "forever. Record the equivalent state operation, or drop the "
                    "SeparateDatabaseAndState wrapper if the DDL is state-neutral.",
                )
            )

    # Pass 2 — bare RunSQL performing model-visible DDL.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _callee(node) != "RunSQL":
            continue
        if id(node) in wrapped_runsql or rel in ALLOWLIST:
            continue
        sql = " ".join(_forward_sql_strings(node)).upper()
        hits = [marker for marker in _DDL_MARKERS if marker in sql]
        if hits:
            findings.append(
                Finding(
                    rel,
                    node.lineno,
                    "warning",
                    "ddl-outside-state",
                    f"RunSQL performs model-visible DDL ({', '.join(hits)}) outside "
                    "SeparateDatabaseAndState. If this changes a model's schema, the "
                    "migration state must record it too.",
                )
            )

    return findings


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _changed_migrations(repo_root: Path, base_ref: str) -> list[Path]:
    merge_base = _git(repo_root, "merge-base", base_ref, "HEAD") or base_ref
    tracked = _git(repo_root, "diff", "--name-only", f"{merge_base}..HEAD").splitlines()
    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines()
    staged = _git(repo_root, "diff", "--name-only", "--cached").splitlines()
    seen: dict[str, None] = {}
    for raw_line in (*tracked, *untracked, *staged):
        line = raw_line.strip()
        if (
            line
            and "/migrations/" in line
            and line.endswith(".py")
            and not line.endswith("__init__.py")
        ):
            seen[line] = None
    return [repo_root / p for p in seen if (repo_root / p).is_file()]


def _all_migrations(repo_root: Path) -> list[Path]:
    return sorted(
        p for p in (repo_root / "hub" / "apps").rglob("migrations/*.py") if p.name != "__init__.py"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Migration state-sync lint")
    parser.add_argument("files", nargs="*", type=Path, help="Explicit migration files to check.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--base-ref", default="origin/main", help="Base ref for the changed-file diff."
    )
    parser.add_argument("--all", action="store_true", help="Scan every migration in the tree.")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()

    if args.files:
        paths = [p.resolve() for p in args.files if p.is_file()]
    elif args.all:
        paths = _all_migrations(repo_root)
    else:
        paths = _changed_migrations(repo_root, args.base_ref)

    findings: list[Finding] = []
    for path in paths:
        try:
            findings.extend(analyse(path, repo_root))
        except ValueError:
            # Path outside repo_root — skip rather than crash the hook.
            continue

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    if args.as_json:
        # Machine-readable output must be JSON and nothing else, so CI can pipe it.
        print(
            json.dumps(
                {
                    "status": "fail" if errors else ("warn" if warnings else "ok"),
                    "files_checked": len(paths),
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "findings": [asdict(f) for f in findings],
                },
                indent=2,
            )
        )
        return 1 if errors else 0

    print(f"Migration state-sync lint — {len(paths)} file(s) checked.")
    for f in sorted(findings, key=lambda f: (f.severity != "error", f.file, f.line)):
        mark = "✗" if f.severity == "error" else "⚠"
        print(f"  {mark} {f.file}:{f.line} [{f.rule}] {f.message}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    if errors:
        print(
            "\nDDL without recorded state is how migration drift accumulates. "
            "See the module docstring for the two legitimate alternatives."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
