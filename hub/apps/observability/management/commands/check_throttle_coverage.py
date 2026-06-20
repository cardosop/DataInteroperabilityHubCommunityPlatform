"""
Phase 273.7.1 — management command that AST-walks search / semantic /
marketplace views.py and asserts every View / ViewSet has a
``throttle_classes`` attribute.

Exit code 0 when all views are covered; non-zero when a view lacks
coverage. Designed for CI (piggybacks on the django tests job).
"""

import ast
import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

# Modules to scan, keyed by app name relative to hub/apps/.
_MODULES: dict[str, str] = {
    "search": "hub/apps/search/views.py",
    "semantic": "hub/apps/semantic/views.py",
    "marketplace": "hub/apps/marketplace/views.py",
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


def _check_module(filepath: str) -> list[str]:
    """Return a list of uncovered view class names in the given module."""
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
    return uncovered


class Command(BaseCommand):
    help = "Phase 273.7.1 — check that every search/semantic/marketplace view has throttle_classes."

    def handle(self, **options):
        base = Path(__file__).resolve().parents[5]  # hub/apps/../.. = repo root
        all_uncovered: list[str] = []

        for _module_name, relative_path in _MODULES.items():
            full_path = base / relative_path
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
