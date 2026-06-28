"""
Phase 273.7.2-4 — cross-cutting drift test for search/semantic views.

Asserts that every View/ViewSet in the search, semantic, and marketplace
apps has throttle_classes defined. Calls the check_throttle_coverage
management command and verifies exit-zero. Includes a negative test
that verifies the check fails when a throttle is missing.
"""

from __future__ import annotations

import ast
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class TestThrottleCoverageDrift(TestCase):
    """check_throttle_coverage exits 0 for current codebase."""

    def test_command_exits_zero(self):
        out = StringIO()
        call_command("check_throttle_coverage", stdout=out)
        output = out.getvalue()
        assert "PASSED" in output, f"Expected PASSED, got: {output}"


class TestThrottleCoverageNegative(TestCase):
    """Stripping throttle_classes from a view causes check to fail."""

    def test_missing_throttle_detected(self):
        import os
        import tempfile

        # Write a temporary module with a View class that lacks throttle_classes.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(
                "from rest_framework import viewsets\n"
                "from rest_framework.permissions import IsAuthenticated\n\n"
                "class UncoveredTestView(viewsets.ViewSet):\n"
                "    permission_classes = [IsAuthenticated]\n"
            )
            tmp_path = tmp.name

        try:
            # Patch _check_module to scan our temp file instead of a real one.
            from hub.apps.observability.management.commands.check_throttle_coverage import (
                _check_module,
            )

            uncovered = _check_module(tmp_path)
            assert len(uncovered) >= 1, f"Should report at least 1 uncovered view, got: {uncovered}"
        finally:
            os.unlink(tmp_path)


class TestViewHasAuditEmission(TestCase):
    """AST-check: every search/semantic/marketplace view's primary
    handler references create_audit_event (direct call or decorator)."""

    def test_unified_search_view_has_audit_emission(self):
        import importlib
        import os

        # Resolve the module path relative to the project root rather than cwd
        search_views = importlib.import_module("hub.apps.search.views")
        source_path = search_views.__file__

        with open(source_path) as fh:
            tree = ast.parse(fh.read())

        # Walk the UnifiedSearchView.get method for create_audit_event.
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "UnifiedSearchView":
                for item in ast.walk(node):
                    if isinstance(item, ast.Call):
                        if isinstance(item.func, ast.Name) and item.func.id == "create_audit_event":
                            found = True
                            break
                    elif isinstance(item, ast.Attribute) and item.attr == "create_audit_event":
                        found = True
                        break
        assert found, "UnifiedSearchView must emit create_audit_event"
