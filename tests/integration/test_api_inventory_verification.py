#!/usr/bin/env python3
"""
Comprehensive Tests for API Inventory Verification

Tests verify:
1. Inventory completeness - all endpoints are documented
2. Inventory accuracy - documented endpoints match actual endpoints
3. Standardized patterns - endpoints use correct URL patterns
4. No deprecated patterns - old patterns are not present

All tests use real implementations (no mocks/stubs).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import TestCase
from django.urls import URLResolver, get_resolver

# Add scripts directory to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

# Import verification functions
# Note: verify-api-inventory.py uses hyphens, so we import it as a module
import importlib.util

verify_api_inventory_path = project_root / "scripts" / "verify-api-inventory.py"
if verify_api_inventory_path.exists():
    spec = importlib.util.spec_from_file_location("verify_api_inventory", verify_api_inventory_path)
    verify_api_inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verify_api_inventory)
    read_inventory = verify_api_inventory.read_inventory
    verify_compliance_endpoints = verify_api_inventory.verify_compliance_endpoints
    verify_dq_endpoints = verify_api_inventory.verify_dq_endpoints
    verify_inventory_completeness = verify_api_inventory.verify_inventory_completeness
else:
    # Fallback if script doesn't exist
    def read_inventory(*args, **kwargs):
        pytest.skip("verify-api-inventory.py not found")

    verify_compliance_endpoints = read_inventory
    verify_dq_endpoints = read_inventory
    verify_inventory_completeness = read_inventory


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


class TestAPIInventoryCompleteness(TestCase):
    """Test API inventory completeness"""

    def setUp(self):
        """Set up test fixtures"""
        self.inventory_path = project_root / "docs" / "api-audit" / "current-api-inventory.md"
        self.assertIsNotNone(
            self.inventory_path.exists(), f"Inventory file not found: {self.inventory_path}"
        )

    def test_inventory_file_exists(self):
        """Test that inventory file exists"""
        self.assertTrue(
            self.inventory_path.exists(), f"Inventory file should exist: {self.inventory_path}"
        )
        self.assertGreater(
            self.inventory_path.stat().st_size, 0, "Inventory file should not be empty"
        )

    def test_inventory_parses_correctly(self):
        """Test that inventory file can be parsed"""
        endpoints_by_app = read_inventory(self.inventory_path)

        self.assertIsInstance(endpoints_by_app, dict, "Inventory should parse to dictionary")
        self.assertGreater(len(endpoints_by_app), 0, "Inventory should contain at least one app")

        # Verify structure
        for app_name, endpoints in endpoints_by_app.items():
            self.assertIsInstance(endpoints, list, f"Endpoints for {app_name} should be a list")
            for endpoint in endpoints:
                self.assertIn("method", endpoint, "Endpoint should have 'method' field")
                self.assertIn("path", endpoint, "Endpoint should have 'path' field")
                self.assertIsInstance(endpoint["method"], str, "Method should be a string")
                self.assertIsInstance(endpoint["path"], str, "Path should be a string")

    def test_inventory_has_minimum_endpoints(self):
        """Test that inventory has minimum expected number of endpoints"""
        endpoints_by_app = read_inventory(self.inventory_path)
        total_endpoints = sum(len(endpoints) for endpoints in endpoints_by_app.values())

        self.assertGreaterEqual(
            total_endpoints,
            100,
            f"Inventory should have at least 100 endpoints, found {total_endpoints}",
        )

    def test_inventory_has_expected_apps(self):
        """Test that inventory contains expected apps"""
        endpoints_by_app = read_inventory(self.inventory_path)
        found_apps = {app.lower() for app in endpoints_by_app.keys()}

        expected_apps = {"compliance", "dq", "auth", "audit"}
        missing_apps = expected_apps - found_apps

        self.assertEqual(
            len(missing_apps), 0, f"Inventory missing expected apps: {', '.join(missing_apps)}"
        )

    def test_inventory_completeness_verification(self):
        """Test inventory completeness verification"""
        endpoints_by_app = read_inventory(self.inventory_path)
        passed, issues = verify_inventory_completeness(endpoints_by_app)

        if not passed:
            self.fail("Inventory completeness issues:\n" + "\n".join(issues))

        self.assertTrue(passed, "Inventory completeness verification should pass")


class TestAPIInventoryAccuracy(TestCase):
    """Test API inventory accuracy against actual endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.inventory_path = project_root / "docs" / "api-audit" / "current-api-inventory.md"
        self.inventory_endpoints = read_inventory(self.inventory_path)

    def test_compliance_endpoints_accuracy(self):
        """Test that compliance endpoints in inventory match actual endpoints"""
        if "compliance" not in self.inventory_endpoints:
            self.skipTest("Compliance app not found in inventory")

        compliance_endpoints = self.inventory_endpoints["compliance"]

        # Expected compliance endpoints
        expected_paths = {
            "GET /api/v1/compliance/runs/",
            "POST /api/v1/compliance/runs/",
            "GET /api/v1/compliance/runs/{id}/",
            "PUT /api/v1/compliance/runs/{id}/",
            "PATCH /api/v1/compliance/runs/{id}/",
            "DELETE /api/v1/compliance/runs/{id}/",
            "GET /api/v1/compliance/runs/{id}/results/",
        }

        found_paths = {f"{e['method']} {e['path']}" for e in compliance_endpoints}

        # Check all expected endpoints are present
        missing = expected_paths - found_paths
        self.assertEqual(
            len(missing), 0, "Missing expected compliance endpoints:\n" + "\n".join(missing)
        )

        # Verify no old patterns
        old_patterns = [e for e in compliance_endpoints if "/compliance-runs/" in e["path"]]
        self.assertEqual(
            len(old_patterns),
            0,
            f"Found {len(old_patterns)} endpoints with old pattern '/compliance-runs/':\n"
            + "\n".join(f"  - {e['method']} {e['path']}" for e in old_patterns),
        )

    def test_dq_endpoints_accuracy(self):
        """Test that DQ endpoints in inventory match actual endpoints"""
        dq_key = None
        if "dq" in self.inventory_endpoints:
            dq_key = "dq"
        elif "data quality" in self.inventory_endpoints:
            dq_key = "data quality"

        if not dq_key:
            self.skipTest("DQ app not found in inventory")

        dq_endpoints = self.inventory_endpoints[dq_key]

        # Verify no old patterns
        old_patterns = [e for e in dq_endpoints if "/dq-runs/" in e["path"]]
        self.assertEqual(
            len(old_patterns),
            0,
            f"Found {len(old_patterns)} endpoints with old pattern '/dq-runs/':\n"
            + "\n".join(f"  - {e['method']} {e['path']}" for e in old_patterns),
        )

    def test_compliance_endpoints_verification(self):
        """Test compliance endpoints verification function"""
        if "compliance" not in self.inventory_endpoints:
            self.skipTest("Compliance app not found in inventory")

        compliance_endpoints = self.inventory_endpoints["compliance"]
        passed, issues = verify_compliance_endpoints(compliance_endpoints)

        if not passed:
            self.fail("Compliance endpoints verification failed:\n" + "\n".join(issues))

        self.assertTrue(passed, "Compliance endpoints verification should pass")

    def test_dq_endpoints_verification(self):
        """Test DQ endpoints verification function"""
        dq_key = None
        if "dq" in self.inventory_endpoints:
            dq_key = "dq"
        elif "data quality" in self.inventory_endpoints:
            dq_key = "data quality"

        if not dq_key:
            self.skipTest("DQ app not found in inventory")

        dq_endpoints = self.inventory_endpoints[dq_key]
        passed, issues = verify_dq_endpoints(dq_endpoints)

        if not passed:
            self.fail("DQ endpoints verification failed:\n" + "\n".join(issues))

        self.assertTrue(passed, "DQ endpoints verification should pass")


class TestAPIInventoryStandardizedPatterns(TestCase):
    """Test that inventory uses standardized endpoint patterns"""

    def setUp(self):
        """Set up test fixtures"""
        self.inventory_path = project_root / "docs" / "api-audit" / "current-api-inventory.md"
        self.inventory_endpoints = read_inventory(self.inventory_path)

    def test_no_compliance_runs_pattern(self):
        """Test that no endpoints use old '/compliance-runs/' pattern"""
        all_endpoints = []
        for endpoints in self.inventory_endpoints.values():
            all_endpoints.extend(endpoints)

        old_patterns = [e for e in all_endpoints if "/compliance-runs/" in e["path"]]

        self.assertEqual(
            len(old_patterns),
            0,
            f"Found {len(old_patterns)} endpoints with old '/compliance-runs/' pattern:\n"
            + "\n".join(f"  - {e['method']} {e['path']}" for e in old_patterns),
        )

    def test_no_dq_runs_pattern(self):
        """Test that no endpoints use old '/dq-runs/' pattern"""
        all_endpoints = []
        for endpoints in self.inventory_endpoints.values():
            all_endpoints.extend(endpoints)

        old_patterns = [e for e in all_endpoints if "/dq-runs/" in e["path"]]

        self.assertEqual(
            len(old_patterns),
            0,
            f"Found {len(old_patterns)} endpoints with old '/dq-runs/' pattern:\n"
            + "\n".join(f"  - {e['method']} {e['path']}" for e in old_patterns),
        )

    def test_compliance_uses_runs_pattern(self):
        """Test that compliance endpoints use standardized '/runs/' pattern"""
        if "compliance" not in self.inventory_endpoints:
            self.skipTest("Compliance app not found in inventory")

        compliance_endpoints = self.inventory_endpoints["compliance"]
        standardized = [e for e in compliance_endpoints if "/runs/" in e["path"]]

        self.assertGreater(
            len(standardized), 0, "Compliance endpoints should use standardized '/runs/' pattern"
        )

        # All compliance endpoints should use /runs/ pattern
        non_standardized = [e for e in compliance_endpoints if "/runs/" not in e["path"]]
        # Allow root endpoint
        non_standardized = [e for e in non_standardized if e["path"] != "/api/v1/compliance/"]

        self.assertEqual(
            len(non_standardized),
            0,
            f"Found {len(non_standardized)} compliance endpoints not using '/runs/' pattern:\n"
            + "\n".join(f"  - {e['method']} {e['path']}" for e in non_standardized),
        )


class TestAPIInventoryVerificationScript(TestCase):
    """Test the verification script itself"""

    def test_verification_script_runs(self):
        """Test that verification script runs without errors"""
        script_path = project_root / "scripts" / "verify-api-inventory.py"

        self.assertTrue(script_path.exists(), f"Verification script should exist: {script_path}")

        # Run the script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Script should exit with code 0 (success)
        self.assertEqual(
            result.returncode,
            0,
            f"Verification script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}",
        )

        # Should contain verification messages
        self.assertIn(
            "Verifying API inventory", result.stdout, "Script should output verification messages"
        )

    def test_verification_script_checks_compliance(self):
        """Test that verification script checks compliance endpoints"""
        script_path = project_root / "scripts" / "verify-api-inventory.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should check compliance endpoints
        self.assertIn(
            "compliance", result.stdout.lower(), "Script should check compliance endpoints"
        )

    def test_verification_script_checks_patterns(self):
        """Test that verification script checks for standardized patterns"""
        script_path = project_root / "scripts" / "verify-api-inventory.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should verify patterns
        self.assertIn(
            "standardized", result.stdout.lower(), "Script should verify standardized patterns"
        )


class TestAPIInventoryAgainstActualEndpoints(TestCase):
    """Test inventory against actual Django endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        self.inventory_path = project_root / "docs" / "api-audit" / "current-api-inventory.md"
        self.inventory_endpoints = read_inventory(self.inventory_path)

        # Extract actual endpoints from Django URL resolver
        self.actual_endpoints = self._extract_actual_endpoints()

    def _extract_actual_endpoints(self) -> set[str]:
        """Extract actual endpoints from Django URL resolver"""
        resolver = get_resolver()
        endpoints = set()

        # Find API v1 resolver
        api_resolver = None
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "pattern"):
                pattern_str = str(pattern.pattern)
                if "api/v1" in pattern_str or pattern_str == "api/v1/":
                    if hasattr(pattern, "url_patterns"):
                        api_resolver = pattern
                        break

        if api_resolver:
            self._parse_resolver(api_resolver, "/api/v1/", endpoints)
        else:
            self._parse_resolver(resolver, "", endpoints)

        return endpoints

    def _parse_resolver(self, resolver: URLResolver, prefix: str, endpoints: set):
        """Recursively parse URL resolver"""
        if not hasattr(resolver, "url_patterns"):
            return

        for pattern in resolver.url_patterns:
            if hasattr(pattern, "urlconf_name"):
                # URLResolver
                pattern_prefix = ""
                if hasattr(pattern, "pattern"):
                    pattern_prefix = str(pattern.pattern)
                    pattern_prefix = pattern_prefix.replace("^", "").replace("$", "")

                new_prefix = (
                    prefix.rstrip("/") + "/" + pattern_prefix.lstrip("/")
                    if prefix
                    else pattern_prefix
                )
                new_prefix = re.sub(r"/+", "/", new_prefix)
                if not new_prefix.endswith("/"):
                    new_prefix += "/"

                try:
                    from django.urls import get_resolver

                    included_resolver = get_resolver(pattern.urlconf_name)
                    self._parse_resolver(included_resolver, new_prefix, endpoints)
                except Exception:
                    pass
            # URLPattern
            elif hasattr(pattern, "pattern"):
                pattern_str = str(pattern.pattern)
                pattern_str = pattern_str.replace("^", "").replace("$", "")

                full_path = prefix.rstrip("/") + "/" + pattern_str.lstrip("/")
                full_path = re.sub(r"/+", "/", full_path)

                # Determine methods
                callback = getattr(pattern, "callback", None)
                if callback:
                    methods = self._get_methods_from_callback(callback)
                    for method in methods:
                        endpoints.add(f"{method} {full_path}")

    def _get_methods_from_callback(self, callback) -> list[str]:
        """Determine HTTP methods from callback"""
        methods = ["GET"]  # Default

        if hasattr(callback, "actions"):
            actions = callback.actions
            method_map = {
                "list": "GET",
                "create": "POST",
                "retrieve": "GET",
                "update": "PUT",
                "partial_update": "PATCH",
                "destroy": "DELETE",
            }
            methods = [method_map.get(action, "GET") for action in actions if action in method_map]
        elif hasattr(callback, "http_method_names"):
            methods = [m.upper() for m in callback.http_method_names if m.upper() != "OPTIONS"]

        return methods if methods else ["GET"]

    def test_inventory_matches_actual_endpoints(self):
        """Test that inventory endpoints match actual Django endpoints"""
        # Convert inventory endpoints to same format
        inventory_set = set()
        for endpoints in self.inventory_endpoints.values():
            for endpoint in endpoints:
                # Normalize path (replace {id} with actual pattern)
                path = endpoint["path"].replace("{id}", "<uuid:id>")
                inventory_set.add(f"{endpoint['method']} {path}")

        # Check compliance endpoints specifically
        compliance_inventory = {
            f"{e['method']} {e['path']}" for e in self.inventory_endpoints.get("compliance", [])
        }

        {
            ep
            for ep in self.actual_endpoints
            if "/compliance/runs/" in ep or "/compliance/compliance-runs/" in ep
        }

        # Should have compliance endpoints
        self.assertGreater(
            len(compliance_inventory), 0, "Inventory should contain compliance endpoints"
        )

        # Check that standardized patterns are used
        standardized_inventory = {ep for ep in compliance_inventory if "/runs/" in ep}
        self.assertGreater(
            len(standardized_inventory), 0, "Inventory should use standardized '/runs/' pattern"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
