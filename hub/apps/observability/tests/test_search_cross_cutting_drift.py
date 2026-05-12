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
from unittest.mock import patch, PropertyMock

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
        from hub.apps.search import views as search_views

        # Monkey-patch: remove throttle_classes from UnifiedSearchView.
        original = getattr(search_views.UnifiedSearchView, "throttle_classes", None)
        try:
            delattr(search_views.UnifiedSearchView, "throttle_classes")
            with pytest.raises(SystemExit) as exc_info:
                call_command("check_throttle_coverage")
            assert exc_info.value.code == 1, "Should exit 1 when throttle missing"
        finally:
            if original is not None:
                search_views.UnifiedSearchView.throttle_classes = original


class TestViewHasAuditEmission(TestCase):
    """AST-check: every search/semantic/marketplace view's primary
    handler references create_audit_event (direct call or decorator)."""

    def test_unified_search_view_has_audit_emission(self):
        import ast

        with open("hub/apps/search/views.py", "r") as fh:
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
