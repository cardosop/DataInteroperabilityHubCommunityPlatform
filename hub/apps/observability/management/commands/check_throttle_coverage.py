"""
Phase 273.7.1 / Phase P.9 — management command that AST-walks the scoped
view modules and asserts every DRF view — ViewSet/View classes AND
``@api_view``-decorated function views — carries ``throttle_classes``.

Phase P.9 widening: the scan set is no longer three hardcoded
``views.py`` paths. ``_SCOPED_VIEW_MODULES`` is the single source of truth
for the documented scope: the Phase 273 contract apps (search / semantic /
marketplace, per CLAUDE.md) plus billing and baas, whose throttles module
documents this checker as the enforcement point. Function-based views were
invisible to the old checker (it only saw classes named *View/ViewSet) —
they are now detected by their ``@api_view`` decorator and counted as
covered only when ``@throttle_classes`` is present.

Exit code 0 when all views are covered; non-zero when a view lacks
coverage. Designed for CI (pure AST, no DB).
"""

import ast
import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

# Scan scope: app name (relative to hub/apps/) → view-bearing modules.
# Keep this list in sync with the claim in hub/apps/billing/throttles.py
# and with the CI step name in .github/workflows/ci.yml.
_SCOPED_VIEW_MODULES: dict[str, tuple[str, ...]] = {
    "search": ("views.py",),
    "semantic": ("views.py",),
    "marketplace": ("views.py", "saved_search_views.py"),
    "billing": ("views.py", "connect_views.py"),
    "baas": ("views.py", "developer_portal.py", "customer_billing_views.py"),
}


def _is_view_class(node: ast.ClassDef) -> bool:
    """True if the class name ends with View or ViewSet."""
    return node.name.endswith("View") or node.name.endswith("ViewSet")


def _has_throttle_classes(node: ast.ClassDef) -> bool:
    """True if the class body assigns to throttle_classes."""
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "throttle_classes":
                    return True
        # Also check if annotated: throttle_classes: list = [...]
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == "throttle_classes":
                return True
    return False


def _has_decorator(node: ast.FunctionDef, name: str) -> bool:
    return any(
        isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == name
        for dec in node.decorator_list
    )


def _is_api_view_function(node: ast.FunctionDef) -> bool:
    """True if the function is a DRF function-based view (@api_view)."""
    return _has_decorator(node, "api_view")


def _function_has_throttle_classes(node: ast.FunctionDef) -> bool:
    return _has_decorator(node, "throttle_classes")


def _check_module(filepath: str) -> list[str]:
    """Return uncovered view class/function names in the given module."""
    if not os.path.isfile(filepath):
        return []

    with open(filepath, encoding="utf-8") as fh:
        try:
            tree = ast.parse(fh.read(), filename=filepath)
        except SyntaxError:
            return [f"{filepath}: syntax error"]

    uncovered: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_view_class(node):
            if not _has_throttle_classes(node):
                uncovered.append(f"{filepath}:{node.name}")
        elif (
            isinstance(node, ast.FunctionDef)
            and _is_api_view_function(node)
            and not _function_has_throttle_classes(node)
        ):
            uncovered.append(f"{filepath}:{node.name}")
    return uncovered


class Command(BaseCommand):
    help = (
        "Phase 273.7.1 / P.9 — check that every scoped view (class AND "
        "function-based) has throttle_classes."
    )

    def handle(self, **_options):
        base = Path(__file__).resolve().parents[5]  # hub/apps/../.. = repo root
        all_uncovered: list[str] = []

        for app_name, modules in _SCOPED_VIEW_MODULES.items():
            for module_name in modules:
                full_path = base / "hub" / "apps" / app_name / module_name
                uncovered = _check_module(str(full_path))
                if uncovered:
                    all_uncovered.extend(uncovered)

        if all_uncovered:
            self.stderr.write(
                self.style.ERROR(
                    f"Throttle coverage check FAILED: {len(all_uncovered)} view(s) uncovered.\n"
                    + "\n".join(f"  - {u}" for u in all_uncovered)
                )
            )
            sys.exit(1)

        self.stdout.write(
            self.style.SUCCESS("Throttle coverage check PASSED — all views have throttle_classes.")
        )
