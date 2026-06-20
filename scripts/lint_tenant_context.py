#!/usr/bin/env python3
"""
Phase 277.B.095 — CI enforcement of ``tenant_context()`` wrapping.

Scans worker task files (``tasks.py``) and signal files (``signals.py``)
for accesses to tenant-scoped models without a surrounding ``tenant_context()``
call.  Files that query/create/update tenant-scoped data but lack a
``tenant_context`` import + usage are reported and exit 1.

Usage:
    python scripts/lint_tenant_context.py                    # Check all
    python scripts/lint_tenant_context.py --check-file <f>    # Check one file

CI integration:
    The ``lint-tenant-context`` job in ci.yml runs this script.
    Exit 0 = all compliant.  Exit 1 = gaps found.
"""

from __future__ import annotations

import ast
from pathlib import Path

# Patterns that indicate ORM access to tenant-scoped data.
# These are string patterns found in Python source that suggest a Django
# queryset is being built against a tenant-scoped model column.
_TENANT_ACCESS_PATTERNS = frozenset(
    {
        ".objects.filter(tenant",
        ".objects.get(tenant",
        ".objects.create(tenant",
        ".objects.update(tenant",
        ".all_objects.filter(tenant",
        ".objects.exclude(tenant",
        ".objects.values(",
        ".objects.values_list(",
    }
)

# Files/suffixes that are explicitly exempt (test files run with pytest
# fixtures that set up tenant context, management commands go through
# the admin DB router)
_EXEMPT_SUFFIXES = frozenset({"/tests/", "/migrations/", "/management/commands/"})

# Files that MUST be checked (worker tasks + signals)
_CHECK_SUFFIXES = frozenset({"/tasks.py", "/signals.py"})


def _has_tenant_context_import(tree: ast.AST) -> bool:
    """Check if the module imports ``tenant_context`` from the canonical path."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "hub.apps.tenants.request_tenant":
                for alias in node.names:
                    if alias.name == "tenant_context":
                        return True
    return False


def _has_tenant_context_usage(tree: ast.AST) -> bool:
    """Check if the module calls ``tenant_context(...)`` or uses ``with tenant_context``."""
    for node in ast.walk(tree):
        # Check for function calls: tenant_context(something)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "tenant_context":
                return True
        # Check for with statements: with tenant_context(id):
        if isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    if isinstance(item.context_expr.func, ast.Name):
                        if item.context_expr.func.id == "tenant_context":
                            return True
    return False


def _accesses_tenant_scoped_data(source: str) -> bool:
    """Heuristic: does this file access tenant-scoped model data?

    Looks for patterns like ``tenant_id=``, ``tenant__field``, etc.
    that indicate querying/filtering by tenant.
    """
    for pattern in _TENANT_ACCESS_PATTERNS:
        if pattern in source:
            return True
    return False


def _is_exempt(filepath: str) -> bool:
    for suffix in _EXEMPT_SUFFIXES:
        if suffix in filepath:
            return True
    return False


def lint_file(filepath: str) -> str | None:
    """Lint a single file.  Returns an error message or None."""
    if _is_exempt(filepath):
        return None

    # Only check worker task + signal files
    if not any(filepath.endswith(suffix.strip("/")) for suffix in _CHECK_SUFFIXES):
        return None

    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return None

    # Skip files that don't touch tenant-scoped data
    if not _accesses_tenant_scoped_data(source):
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"{filepath}: syntax error — {exc}"

    has_import = _has_tenant_context_import(tree)
    has_usage = _has_tenant_context_usage(tree)

    if not has_import:
        return (
            f"{filepath}: accesses tenant-scoped data but does NOT import "
            f"tenant_context from hub.apps.tenants.request_tenant"
        )
    if not has_usage:
        return (
            f"{filepath}: imports tenant_context but does NOT wrap "
            f"tenant-scoped access in a with tenant_context(id): block"
        )

    return None


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Lint worker/signal files for tenant_context() wrapping."
    )
    parser.add_argument(
        "--check-file",
        type=str,
        help="Check a single file instead of all.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if args.check_file:
        files = [args.check_file]
    else:
        # Find all tasks.py and signals.py files under hub/
        hub_dir = repo_root / "hub"
        files = []
        for suffix in (("tasks.py",), ("signals.py",)):
            for path in hub_dir.rglob(suffix[0]):
                files.append(str(path))

    violations: list[str] = []
    for fpath in sorted(files):
        error = lint_file(fpath)
        if error:
            violations.append(error)
            print(f"  VIOLATION: {error}")
        else:
            print(f"  OK: {fpath}")

    checked = len(files)
    print(f"\nChecked {checked} worker/signal files.")

    if violations:
        print(f"\n{len(violations)} violation(s) found:")
        for v in violations:
            print(f"  {v}")
        print(
            "\nWorker/signal code that touches tenant-scoped models MUST run inside "
            "tenant_context(tenant_id) — see CLAUDE.md § Tenant Isolation RLS Contract."
        )
        return 1

    print("OK: all worker/signal files with tenant access use tenant_context().")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
