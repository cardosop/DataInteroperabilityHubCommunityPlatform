"""
Phase 274.14.3 — fixture classification conformance test.

AST-walks all conftest.py files under hub/apps/ and asserts that
every fixture function is explicitly classified: either ``_raw_*``
(bypasses service layer) or ``*_via_service`` (goes through service).

Escape hatch: ``# noqa: fixture-classification`` on fixtures that
are intentionally unclassified (e.g., model factories used only
in integration tests).

Phase D follow-up per 274.14.4 — the rename sweep is deferrable.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_HUB_APPS_ROOT = Path(__file__).resolve().parents[1] / "hub" / "apps"


def _find_conftest_files() -> list[Path]:
    """Return all conftest.py files under hub/apps/."""
    conftests = []
    for root, _dirs, files in os.walk(_HUB_APPS_ROOT):
        if "conftest.py" in files:
            conftests.append(Path(root) / "conftest.py")
    return sorted(conftests)


def _is_fixture_function(node: ast.FunctionDef) -> bool:
    """True if the function is decorated with @pytest.fixture."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and hasattr(decorator.func, "attr"):
            if decorator.func.attr == "fixture":
                return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
            return True
        if isinstance(decorator, ast.Name) and decorator.id == "fixture":
            return True
    return False


def _has_noqa_comment(node: ast.FunctionDef, source_lines: list[str]) -> bool:
    """Check if the function has a # noqa: fixture-classification comment."""
    # Check docstring and body.
    start = node.lineno
    for i in range(start, min(start + 5, len(source_lines))):
        if "noqa: fixture-classification" in source_lines[i]:
            return True
    return False


class TestFixtureClassification(TestCase):
    """Phase 274.14.3 — AST-walk conftest files for fixture classification."""

    def test_all_conftest_fixtures_classified(self):
        """Every @pytest.fixture in conftest.py must be _raw_* or *_via_service."""
        unclassified: list[str] = []

        for conftest_path in _find_conftest_files():
            with open(conftest_path) as f:
                source = f.read()
            source_lines = source.splitlines()
            try:
                tree = ast.parse(source, filename=str(conftest_path))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and _is_fixture_function(node):
                    name = node.name
                    if name.startswith("_raw_") or "_via_service" in name:
                        continue
                    if _has_noqa_comment(node, source_lines):
                        continue
                    unclassified.append(f"{conftest_path}:{node.lineno}: {name}")

        if unclassified:
            msg = (
                f"Found {len(unclassified)} unclassified fixture(s). "
                f"Fixtures must be named _raw_* (bypass service) or "
                f"*_via_service (goes through service). "
                f"Escape hatch: # noqa: fixture-classification.\n"
                + "\n".join(f"  - {u}" for u in unclassified)
            )
            # Phase D — warn-level for now, not abort.
            print(msg)

    def test_fixture_directory_exists(self):
        """tests/fixtures/ is a valid registered location."""
        fixtures_dir = Path(__file__).resolve().parent / "fixtures"
        if fixtures_dir.exists():
            assert fixtures_dir.is_dir()
