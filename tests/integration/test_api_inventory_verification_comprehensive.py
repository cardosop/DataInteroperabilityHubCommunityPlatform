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

pytestmark = [pytest.mark.integration]


class TestAPIInventoryVerificationScript:
    """Test the API inventory verification script"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.script_path = self.project_root / "scripts" / "verify-api-inventory.py"
        self.inventory_path = self.project_root / "docs" / "api-audit" / "current-api-inventory.md"

    def test_verification_script_exists(self):
        """Test that verification script exists"""
        assert self.script_path.exists(), f"Verification script should exist: {self.script_path}"
        assert self.script_path.is_file(), (
            f"Verification script should be a file: {self.script_path}"
        )

    def test_verification_script_runs_successfully(self):
        """Test that verification script runs without errors"""
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Verification script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # Should contain success message
        assert "All verification checks passed" in result.stdout, (
            f"Script should report success.\nSTDOUT:\n{result.stdout}"
        )

    def test_verification_script_checks_compliance_endpoints(self):
        """Test that verification script checks compliance endpoints"""
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=30,
        )

        assert result.returncode == 0, "Script should succeed"
        assert "compliance" in result.stdout.lower(), (
            f"Script should check compliance endpoints.\nSTDOUT:\n{result.stdout}"
        )
        assert (
            "standardized patterns" in result.stdout.lower() or "verified" in result.stdout.lower()
        ), f"Script should verify standardized patterns.\nSTDOUT:\n{result.stdout}"

    def test_verification_script_checks_dq_endpoints(self):
        """Test that verification script checks DQ endpoints"""
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=30,
        )

        assert result.returncode == 0, "Script should succeed"
        # Should check DQ endpoints (case-insensitive)
        output_lower = result.stdout.lower()
        assert "dq" in output_lower or "data quality" in output_lower, (
            f"Script should check DQ endpoints.\nSTDOUT:\n{result.stdout}"
        )

    def test_verification_script_checks_completeness(self):
        """Test that verification script checks inventory completeness"""
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=30,
        )

        assert result.returncode == 0, "Script should succeed"
        assert "completeness" in result.stdout.lower(), (
            f"Script should check completeness.\nSTDOUT:\n{result.stdout}"
        )

    def test_verification_script_reports_endpoint_count(self):
        """Test that verification script reports endpoint count"""
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=30,
        )

        assert result.returncode == 0, "Script should succeed"
        # Should report endpoint count
        assert "endpoints" in result.stdout.lower(), (
            f"Script should report endpoint count.\nSTDOUT:\n{result.stdout}"
        )
        # Should have a number
        assert re.search(r"\d+\s+endpoints?", result.stdout, re.IGNORECASE), (
            f"Script should report numeric endpoint count.\nSTDOUT:\n{result.stdout}"
        )


class TestAPIInventoryFile:
    """Test the API inventory file itself"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.inventory_path = self.project_root / "docs" / "api-audit" / "current-api-inventory.md"

    def test_inventory_file_exists(self):
        """Test that inventory file exists"""
        assert self.inventory_path.exists(), f"Inventory file should exist: {self.inventory_path}"
        assert self.inventory_path.is_file(), (
            f"Inventory file should be a file: {self.inventory_path}"
        )

    def test_inventory_file_not_empty(self):
        """Test that inventory file is not empty"""
        assert self.inventory_path.stat().st_size > 0, "Inventory file should not be empty"

    def test_inventory_file_has_compliance_section(self):
        """Test that inventory file has compliance section"""
        content = self.inventory_path.read_text(encoding="utf-8")
        assert "compliance" in content.lower(), "Inventory should contain compliance section"
        assert "/api/v1/compliance/runs/" in content, (
            "Inventory should contain standardized compliance endpoints"
        )

    def test_inventory_file_has_no_old_compliance_patterns(self):
        """Test that inventory file has no old compliance patterns"""
        content = self.inventory_path.read_text(encoding="utf-8")
        # Should not have old pattern
        assert "/compliance-runs/" not in content, (
            "Inventory should not contain old '/compliance-runs/' pattern"
        )

    def test_inventory_file_has_no_old_dq_patterns(self):
        """Test that inventory file has no old DQ patterns"""
        content = self.inventory_path.read_text(encoding="utf-8")
        # Should not have old pattern
        assert "/dq-runs/" not in content, "Inventory should not contain old '/dq-runs/' pattern"

    def test_inventory_file_has_standardized_runs_patterns(self):
        """Test that inventory file uses standardized runs patterns"""
        content = self.inventory_path.read_text(encoding="utf-8")
        # Should have standardized patterns
        assert "/api/v1/compliance/runs/" in content, (
            "Inventory should contain standardized '/api/v1/compliance/runs/' pattern"
        )
        assert "/api/v1/dq/runs/" in content or "/api/v1/dq/" in content, (
            "Inventory should contain DQ endpoints"
        )

    def test_inventory_file_has_expected_structure(self):
        """Test that inventory file has expected structure"""
        content = self.inventory_path.read_text(encoding="utf-8")

        # Should have headers
        assert "# Current API Inventory" in content, "Inventory should have main header"
        assert "## Overview" in content, "Inventory should have overview section"
        assert "## Endpoints by Application" in content, "Inventory should have endpoints section"
        assert "## Summary Statistics" in content, "Inventory should have summary section"

    def test_inventory_file_has_endpoint_tables(self):
        """Test that inventory file has endpoint tables"""
        content = self.inventory_path.read_text(encoding="utf-8")

        # Should have table headers
        assert "| Method | Path |" in content, "Inventory should have endpoint table"
        assert "|--------|------|" in content, "Inventory should have table separator"

    def test_inventory_file_has_compliance_endpoints(self):
        """Test that inventory file has all expected compliance endpoints"""
        content = self.inventory_path.read_text(encoding="utf-8")

        # Expected compliance endpoints
        expected_endpoints = [
            "GET /api/v1/compliance/runs/",
            "POST /api/v1/compliance/runs/",
            "GET /api/v1/compliance/runs/{id}/",
            "GET /api/v1/compliance/runs/{id}/results/",
        ]

        for endpoint in expected_endpoints:
            # Check for endpoint in table format
            _method, path = endpoint.split(" ", 1)
            # Path might be in backticks in markdown
            assert path in content or path.replace("/", " /") in content, (
                f"Inventory should contain endpoint: {endpoint}"
            )


class TestAPIInventoryRegeneration:
    """Test API inventory regeneration script"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.regeneration_script = (
            self.project_root / "scripts" / "regenerate-api-inventory-static.py"
        )
        self.inventory_path = self.project_root / "docs" / "api-audit" / "current-api-inventory.md"

    def test_regeneration_script_exists(self):
        """Test that regeneration script exists"""
        assert self.regeneration_script.exists(), (
            f"Regeneration script should exist: {self.regeneration_script}"
        )

    @pytest.mark.slow
    def test_regeneration_script_runs_successfully(self):
        """Test that regeneration script runs without errors"""
        result = subprocess.run(
            [sys.executable, str(self.regeneration_script)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Regeneration script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # Should report success
        assert "Inventory generated" in result.stdout or "endpoints" in result.stdout.lower(), (
            f"Script should report success.\nSTDOUT:\n{result.stdout}"
        )

        # Inventory file should exist after regeneration
        assert self.inventory_path.exists(), "Inventory file should exist after regeneration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
