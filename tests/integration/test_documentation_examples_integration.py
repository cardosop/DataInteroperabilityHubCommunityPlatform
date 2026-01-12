#!/usr/bin/env python3
"""
Integration Tests for Documentation Code Examples

Tests verify that code examples in developer guides:
1. Use correct endpoint patterns
2. Are syntactically valid
3. Can be executed against running API (if services available)

All tests use real implementations (no mocks/stubs).
"""

import os
import sys
import subprocess
import re
import requests
from pathlib import Path
from typing import List, Dict, Optional

import pytest


pytestmark = [pytest.mark.integration]


class TestDocumentationExamplesIntegration:
    """Integration tests for documentation code examples"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.docs_dir = self.project_root / 'docs'
        self.api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.services_available = self._check_services_available()

    def _check_services_available(self) -> bool:
        """Check if API services are available"""
        try:
            # Try multiple health check endpoints
            health_endpoints = [
                f"{self.api_base_url}/api/v1/health/",
                f"{self.api_base_url}/health/",
                f"{self.api_base_url}/api/health/",
            ]
            for endpoint in health_endpoints:
                try:
                    response = requests.get(endpoint, timeout=2)
                    if response.status_code in [200, 404]:  # 404 means service is up but endpoint doesn't exist
                        return True
                except requests.exceptions.RequestException:
                    continue

            # If health endpoints don't work, try a simple API endpoint
            response = requests.get(f"{self.api_base_url}/api/v1/compliance/runs/", timeout=2)
            return response.status_code != 500  # Any status except 500 means service is up
        except Exception:
            return False

    def test_verify_script_runs(self):
        """Test that verification script runs successfully"""
        verify_script = self.project_root / 'scripts' / 'verify-documentation-examples.py'

        result = subprocess.run(
            [sys.executable, str(verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Verification script failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "All documentation uses standardized endpoint patterns" in result.stdout or "issues found: 0" in result.stdout

    def test_test_script_runs(self):
        """Test that test script runs successfully"""
        test_script = self.project_root / 'scripts' / 'test-documentation-examples.py'

        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Test script failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "All code examples validated successfully" in result.stdout or "issues found: 0" in result.stdout

    def test_api_endpoints_reference_curl_examples(self):
        """Test that API endpoints reference has valid curl examples"""
        api_ref_path = self.docs_dir / 'API_ENDPOINTS_REFERENCE.md'

        if not api_ref_path.exists():
            pytest.skip("API_ENDPOINTS_REFERENCE.md not found")

        content = api_ref_path.read_text(encoding='utf-8')

        # Extract curl examples for compliance endpoints
        curl_pattern = r'```bash\s+(curl[^`]+)```'
        curl_examples = re.findall(curl_pattern, content, re.DOTALL)

        compliance_examples = [ex for ex in curl_examples if '/api/v1/compliance' in ex]

        # Verify all compliance examples use standardized patterns
        for example in compliance_examples:
            assert '/api/v1/compliance/runs/' in example, (
                f"Curl example should use standardized pattern:\n{example[:300]}"
            )
            assert '/compliance-runs/' not in example, (
                f"Curl example should not use old pattern:\n{example[:300]}"
            )

    def test_compliance_endpoints_accessible(self):
        """Test that compliance endpoints are accessible (if services running)"""
        if not self.services_available:
            pytest.skip("API services not available")

        # Test list endpoint
        try:
            response = requests.get(
                f"{self.api_base_url}/api/v1/compliance/runs/",
                timeout=5
            )
            # Should return 401 (unauthorized) or 200 (if public), not 404
            assert response.status_code != 404, "Compliance runs endpoint should exist"
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Could not connect to API: {e}")

    def test_migration_guide_completeness(self):
        """Test that migration guide is complete"""
        migration_guide = self.docs_dir / 'ENDPOINT_PATTERN_MIGRATION_GUIDE.md'

        assert migration_guide.exists(), "Migration guide should exist"

        content = migration_guide.read_text(encoding='utf-8')

        # Should have required sections
        required_sections = [
            'What Changed',
            'Migration Steps',
            'Verification',
            'Breaking Changes',
        ]

        for section in required_sections:
            assert section in content, f"Migration guide should have '{section}' section"

        # Should document old patterns
        assert '/compliance-runs/' in content, "Should document old compliance pattern"
        assert '/dq-runs/' in content, "Should document old DQ pattern"

        # Should document new patterns
        assert '/api/v1/compliance/runs/' in content, "Should document new compliance pattern"
        assert '/api/v1/dq/runs/' in content, "Should document new DQ pattern"


class TestDocumentationScriptsWork:
    """Test that documentation scripts work correctly"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent

    def test_verify_script_checks_all_files(self):
        """Test that verify script checks all documentation files"""
        verify_script = self.project_root / 'scripts' / 'verify-documentation-examples.py'

        result = subprocess.run(
            [sys.executable, str(verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, "Verify script should succeed"
        assert "Files checked" in result.stdout or "Checking" in result.stdout

    def test_test_script_validates_examples(self):
        """Test that test script validates code examples"""
        test_script = self.project_root / 'scripts' / 'test-documentation-examples.py'

        result = subprocess.run(
            [sys.executable, str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, "Test script should succeed"
        assert "examples validated" in result.stdout.lower() or "tested" in result.stdout.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

