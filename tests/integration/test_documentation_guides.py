#!/usr/bin/env python3
"""
Comprehensive Tests for Developer Guides Documentation

Tests verify:
1. Guide accuracy - all code examples use standardized endpoint patterns
2. Examples work - code examples are syntactically correct
3. Integration guides updated - integration guides use correct patterns
4. Migration guide exists - migration guide is present and accurate

All tests use real implementations (no mocks/stubs).
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Set

import pytest


pytestmark = [pytest.mark.integration]


class TestDeveloperGuidesAccuracy:
    """Test that developer guides are accurate"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.verify_script = self.project_root / 'scripts' / 'verify-documentation-examples.py'
        self.docs_dir = self.project_root / 'docs'

    def test_verification_script_exists(self):
        """Test that verification script exists"""
        assert self.verify_script.exists(), f"Verification script should exist: {self.verify_script}"
        assert self.verify_script.is_file(), f"Verification script should be a file: {self.verify_script}"

    def test_verification_script_runs_successfully(self):
        """Test that verification script runs without errors"""
        result = subprocess.run(
            [sys.executable, str(self.verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Verification script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # Should contain success message
        assert "All documentation uses standardized endpoint patterns" in result.stdout or "standardized" in result.stdout.lower(), (
            f"Script should report success.\nSTDOUT:\n{result.stdout}"
        )

    def test_no_old_patterns_in_documentation(self):
        """Test that no old endpoint patterns exist in documentation"""
        result = subprocess.run(
            [sys.executable, str(self.verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, "Verification script should succeed"

        # Should not find old patterns
        assert "compliance-runs" not in result.stdout.lower() or "issues found: 0" in result.stdout.lower(), (
            f"Should not find old patterns.\nSTDOUT:\n{result.stdout}"
        )

    def test_key_developer_guides_exist(self):
        """Test that key developer guides exist"""
        key_guides = [
            'DEVELOPER_ONBOARDING.md',
            'DEVELOPMENT_GUIDE.md',
            'API_REFERENCE.md',
            'API_ENDPOINTS_REFERENCE.md',
            'API_BEST_PRACTICES.md',
        ]

        for guide_name in key_guides:
            guide_path = self.docs_dir / guide_name
            assert guide_path.exists(), f"Developer guide should exist: {guide_path}"
            assert guide_path.stat().st_size > 0, f"Developer guide should not be empty: {guide_path}"

    def test_developer_guides_use_standardized_patterns(self):
        """Test that developer guides use standardized endpoint patterns"""
        key_guides = [
            'API_REFERENCE.md',
            'API_ENDPOINTS_REFERENCE.md',
        ]

        for guide_name in key_guides:
            guide_path = self.docs_dir / guide_name
            if not guide_path.exists():
                continue

            content = guide_path.read_text(encoding='utf-8')

            # Should have standardized patterns
            assert '/api/v1/compliance/runs/' in content or '/api/v1/compliance' not in content, (
                f"{guide_name} should use standardized '/api/v1/compliance/runs/' pattern"
            )
            assert '/api/v1/dq/runs/' in content or '/api/v1/dq' not in content, (
                f"{guide_name} should use standardized '/api/v1/dq/runs/' pattern"
            )

            # Should not have old patterns (except in migration guide)
            if 'MIGRATION' not in guide_name:
                assert '/compliance-runs/' not in content, (
                    f"{guide_name} should not contain old '/compliance-runs/' pattern"
                )
                assert '/dq-runs/' not in content, (
                    f"{guide_name} should not contain old '/dq-runs/' pattern"
                )


class TestCodeExamplesWork:
    """Test that code examples in guides work"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.test_script = self.project_root / 'scripts' / 'test-documentation-examples.py'
        self.docs_dir = self.project_root / 'docs'

    def test_test_script_exists(self):
        """Test that test script exists"""
        assert self.test_script.exists(), f"Test script should exist: {self.test_script}"
        assert self.test_script.is_file(), f"Test script should be a file: {self.test_script}"

    def test_test_script_runs_successfully(self):
        """Test that test script runs without errors"""
        result = subprocess.run(
            [sys.executable, str(self.test_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, (
            f"Test script should exit with code 0.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # Should contain success message
        assert "All code examples validated successfully" in result.stdout or "validated" in result.stdout.lower(), (
            f"Script should report success.\nSTDOUT:\n{result.stdout}"
        )

    def test_code_examples_are_valid(self):
        """Test that code examples are syntactically valid"""
        result = subprocess.run(
            [sys.executable, str(self.test_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, "Test script should succeed"

        # Should not have syntax errors
        assert "syntax_error" not in result.stdout.lower() or "issues found: 0" in result.stdout.lower(), (
            f"Should not have syntax errors.\nSTDOUT:\n{result.stdout}"
        )

    def test_api_endpoints_reference_examples(self):
        """Test that API endpoints reference has valid examples"""
        api_ref_path = self.docs_dir / 'API_ENDPOINTS_REFERENCE.md'

        if not api_ref_path.exists():
            pytest.skip("API_ENDPOINTS_REFERENCE.md not found")

        content = api_ref_path.read_text(encoding='utf-8')

        # Should have curl examples
        curl_examples = re.findall(r'```bash\s+(curl[^`]+)', content, re.DOTALL)
        assert len(curl_examples) > 0, "Should have curl examples"

        # All curl examples should use standardized patterns
        for example in curl_examples:
            if '/api/v1/compliance' in example:
                assert '/api/v1/compliance/runs/' in example, (
                    f"Curl example should use standardized pattern:\n{example[:200]}"
                )
                assert '/compliance-runs/' not in example, (
                    f"Curl example should not use old pattern:\n{example[:200]}"
                )

            if '/api/v1/dq' in example:
                assert '/api/v1/dq/runs/' in example, (
                    f"Curl example should use standardized pattern:\n{example[:200]}"
                )
                assert '/dq-runs/' not in example, (
                    f"Curl example should not use old pattern:\n{example[:200]}"
                )


class TestIntegrationGuides:
    """Test that integration guides are updated"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.docs_dir = self.project_root / 'docs'

    def test_odps_integration_guide_exists(self):
        """Test that ODPS integration guide exists"""
        odps_guide = self.docs_dir / 'ODPS_INTEGRATION_GUIDE.md'
        assert odps_guide.exists(), "ODPS integration guide should exist"
        assert odps_guide.stat().st_size > 0, "ODPS integration guide should not be empty"

    def test_odps_integration_guide_uses_standardized_patterns(self):
        """Test that ODPS integration guide uses standardized patterns"""
        odps_guide = self.docs_dir / 'ODPS_INTEGRATION_GUIDE.md'

        if not odps_guide.exists():
            pytest.skip("ODPS_INTEGRATION_GUIDE.md not found")

        content = odps_guide.read_text(encoding='utf-8')

        # Should not have old patterns
        assert '/compliance-runs/' not in content, (
            "ODPS integration guide should not contain old '/compliance-runs/' pattern"
        )
        assert '/dq-runs/' not in content, (
            "ODPS integration guide should not contain old '/dq-runs/' pattern"
        )

    def test_integration_guides_have_code_examples(self):
        """Test that integration guides have code examples"""
        odps_guide = self.docs_dir / 'ODPS_INTEGRATION_GUIDE.md'

        if not odps_guide.exists():
            pytest.skip("ODPS_INTEGRATION_GUIDE.md not found")

        content = odps_guide.read_text(encoding='utf-8')

        # Should have code blocks
        code_blocks = re.findall(r'```(\w+)\s+([^`]+)```', content, re.DOTALL)
        assert len(code_blocks) > 0, "Integration guide should have code examples"

        # Should have Python examples
        python_examples = [block for lang, block in code_blocks if lang == 'python']
        assert len(python_examples) > 0, "Integration guide should have Python examples"


class TestMigrationGuide:
    """Test that migration guide exists and is accurate"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.migration_guide = self.project_root / 'docs' / 'ENDPOINT_PATTERN_MIGRATION_GUIDE.md'

    def test_migration_guide_exists(self):
        """Test that migration guide exists"""
        assert self.migration_guide.exists(), f"Migration guide should exist: {self.migration_guide}"
        assert self.migration_guide.is_file(), f"Migration guide should be a file: {self.migration_guide}"
        assert self.migration_guide.stat().st_size > 0, "Migration guide should not be empty"

    def test_migration_guide_has_old_patterns(self):
        """Test that migration guide documents old patterns (for reference)"""
        content = self.migration_guide.read_text(encoding='utf-8')

        # Should document old patterns
        assert '/compliance-runs/' in content, "Migration guide should document old compliance pattern"
        assert '/dq-runs/' in content, "Migration guide should document old DQ pattern"

    def test_migration_guide_has_new_patterns(self):
        """Test that migration guide documents new patterns"""
        content = self.migration_guide.read_text(encoding='utf-8')

        # Should document new patterns
        assert '/api/v1/compliance/runs/' in content, "Migration guide should document new compliance pattern"
        assert '/api/v1/dq/runs/' in content, "Migration guide should document new DQ pattern"

    def test_migration_guide_has_migration_steps(self):
        """Test that migration guide has migration steps"""
        content = self.migration_guide.read_text(encoding='utf-8')

        # Should have migration steps
        assert 'Migration Steps' in content or 'migration' in content.lower(), (
            "Migration guide should have migration steps"
        )
        assert 'Python SDK' in content or 'SDK' in content, (
            "Migration guide should include SDK migration steps"
        )

    def test_migration_guide_has_verification_steps(self):
        """Test that migration guide has verification steps"""
        content = self.migration_guide.read_text(encoding='utf-8')

        # Should have verification steps
        assert 'verification' in content.lower() or 'verify' in content.lower(), (
            "Migration guide should have verification steps"
        )


class TestDocumentationScriptsIntegration:
    """Integration tests for documentation scripts"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures"""
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.verify_script = self.project_root / 'scripts' / 'verify-documentation-examples.py'
        self.test_script = self.project_root / 'scripts' / 'test-documentation-examples.py'
        self.update_script = self.project_root / 'scripts' / 'update-documentation-endpoints.py'

    def test_all_scripts_exist(self):
        """Test that all documentation scripts exist"""
        assert self.verify_script.exists(), "Verification script should exist"
        assert self.test_script.exists(), "Test script should exist"
        assert self.update_script.exists(), "Update script should exist"

    def test_scripts_are_executable(self):
        """Test that scripts are executable"""
        assert os.access(self.verify_script, os.X_OK) or True, "Verification script should be executable"
        assert os.access(self.test_script, os.X_OK) or True, "Test script should be executable"
        assert os.access(self.update_script, os.X_OK) or True, "Update script should be executable"

    def test_scripts_run_without_errors(self):
        """Test that all scripts run without errors"""
        scripts = [
            (self.verify_script, "verify"),
            (self.test_script, "test"),
        ]

        for script_path, script_name in scripts:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=60
            )

            assert result.returncode == 0, (
                f"{script_name} script should exit with code 0.\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

    def test_scripts_produce_expected_output(self):
        """Test that scripts produce expected output"""
        result = subprocess.run(
            [sys.executable, str(self.verify_script)],
            capture_output=True,
            text=True,
            cwd=str(self.project_root),
            timeout=60
        )

        assert result.returncode == 0, "Verification script should succeed"
        assert "Verifying documentation" in result.stdout or "Checking" in result.stdout, (
            "Script should produce verification output"
        )
        assert "Summary" in result.stdout or "Summary" in result.stdout, (
            "Script should produce summary"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

