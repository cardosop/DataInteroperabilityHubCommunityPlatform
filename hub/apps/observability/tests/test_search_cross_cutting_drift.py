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

    def _check_temp_module(self, source: str) -> list[str]:
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        try:
            from hub.apps.observability.management.commands.check_throttle_coverage import (
                _check_module,
            )

            return _check_module(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_missing_throttle_detected(self):
        uncovered = self._check_temp_module(
            "from rest_framework import viewsets\n"
            "from rest_framework.permissions import IsAuthenticated\n\n"
            "class UncoveredTestView(viewsets.ViewSet):\n"
            "    permission_classes = [IsAuthenticated]\n"
        )
        assert len(uncovered) >= 1, f"Should report at least 1 uncovered view, got: {uncovered}"

    def test_uncovered_function_view_detected(self):
        """Phase P.9 — function-based @api_view endpoints were invisible to
        the checker (it only saw classes named *View/ViewSet); a function
        view without @throttle_classes must be flagged."""
        uncovered = self._check_temp_module(
            "from rest_framework.decorators import api_view\n"
            "from rest_framework.permissions import IsAuthenticated\n\n"
            "@api_view(['GET'])\n"
            "@permission_classes([IsAuthenticated])\n"
            "def public_endpoint(request):\n"
            "    return None\n"
        )
        assert any("public_endpoint" in u for u in uncovered), uncovered

    def test_covered_function_view_passes(self):
        """The decorator form the six semantic/billing function views use
        must count as coverage."""
        uncovered = self._check_temp_module(
            "from rest_framework.decorators import api_view, throttle_classes\n"
            "from rest_framework.throttling import UserRateThrottle\n\n"
            "@api_view(['GET'])\n"
            "@throttle_classes([UserRateThrottle])\n"
            "def public_endpoint(request):\n"
            "    return None\n"
        )
        assert uncovered == [], uncovered


class TestThrottleCoverageScope(TestCase):
    """Phase P.9 — the scan set is the single source of truth for the
    documented scope; billing + baas are scanned (their throttles module
    claims the checker covers them) alongside the Phase 273 contract apps."""

    def test_scan_set_covers_billing_and_baas(self):
        from hub.apps.observability.management.commands.check_throttle_coverage import (
            _SCOPED_VIEW_MODULES,
        )

        assert "billing" in _SCOPED_VIEW_MODULES, (
            "billing views must be scanned — billing/throttles.py claims the checker picks them up"
        )
        assert "baas" in _SCOPED_VIEW_MODULES
        assert {"search", "semantic", "marketplace"} <= set(_SCOPED_VIEW_MODULES)

    def test_billing_scan_set_names_the_real_view_modules(self):
        import os

        from hub.apps.observability.management.commands.check_throttle_coverage import (
            _SCOPED_VIEW_MODULES,
        )

        base = os.path.join("hub", "apps")
        for app, modules in _SCOPED_VIEW_MODULES.items():
            for module in modules:
                full = os.path.join(base, app, module)
                assert os.path.isfile(full), f"scan target missing: {full}"


class TestViewHasAuditEmission(TestCase):
    """AST-check: every search/semantic/marketplace view's primary
    handler references create_audit_event (direct call or decorator)."""

    def test_unified_search_view_has_audit_emission(self):
        import importlib

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
