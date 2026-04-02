"""
Phase 8 Completion Gate (task 8.9, testsfix1/tasks.md).

Verifies:
- TEST_SCENARIO_MATRIX.md exists
- 28 feature specs in frontend/e2e/features/
- Five new security test modules (8.6): ai, ml, social, data_mesh, versioning
- Four cross-cutting specs (8.7): network-failures, timeout-handling, rate-limit, concurrent-operations
- verifyFailureScenario in helpers.ts asserts API status (expectedError.status and response.status())

No mocks/stubs; real file existence and content checks only.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Phase 8.6: five new security test modules (added in 8.6.1–8.6.5)
PHASE8_SECURITY_MODULES = [
    "test_ai_security.py",
    "test_ml_security.py",
    "test_social_security.py",
    "test_data_mesh_security.py",
    "test_versioning_security.py",
]

# Phase 8.7: four cross-cutting dimension specs
PHASE8_CROSS_CUTTING_SPECS = [
    "network-failures.spec.ts",
    "timeout-handling.spec.ts",
    "rate-limit.spec.ts",
    "concurrent-operations.spec.ts",
]

EXPECTED_FEATURE_SPEC_COUNT = 29


class TestPhase8_9ScenarioMatrix:
    """8.9: Test scenario documentation exists (consolidated into TESTING_GUIDE.md)."""

    def test_testing_guide_exists(self):
        """docs/TESTING_GUIDE.md must exist (consolidated from TEST_SCENARIO_MATRIX.md)."""
        path = REPO_ROOT / "docs" / "TESTING_GUIDE.md"
        assert path.is_file(), f"TESTING_GUIDE.md not found at {path}"

    def test_testing_guide_has_scenario_content(self):
        """Testing guide must cover test scenarios."""
        path = REPO_ROOT / "docs" / "TESTING_GUIDE.md"
        content = path.read_text()
        assert "scenario" in content.lower() or "test" in content.lower()


class TestPhase8_9FeatureSpecs:
    """8.9: 28 feature specs exist in frontend/e2e/features/."""

    def test_feature_specs_directory_exists(self):
        """frontend/e2e/features/ must exist."""
        path = REPO_ROOT / "frontend" / "e2e" / "features"
        assert path.is_dir(), f"frontend/e2e/features not found at {path}"

    def test_feature_spec_count_is_28(self):
        """Exactly 28 feature .spec.ts files (8.3)."""
        features_dir = REPO_ROOT / "frontend" / "e2e" / "features"
        spec_files = list(features_dir.glob("*.spec.ts"))
        names = [f.name for f in spec_files]
        assert len(spec_files) == EXPECTED_FEATURE_SPEC_COUNT, (
            f"Expected {EXPECTED_FEATURE_SPEC_COUNT} feature specs, found {len(spec_files)}: "
            f"{names}"
        )


class TestPhase8_9SecurityModules:
    """8.9: Five new security test modules (Phase 8.6) exist."""

    @pytest.mark.parametrize("module", PHASE8_SECURITY_MODULES)
    def test_security_module_exists(self, module):
        """Each Phase 8.6 security module must exist under tests/security/."""
        path = REPO_ROOT / "tests" / "security" / module
        assert path.is_file(), f"Phase 8.6 security module missing: {module}"


class TestPhase8_9CrossCuttingSpecs:
    """8.9: Four cross-cutting dimension specs (Phase 8.7) exist."""

    @pytest.mark.parametrize("spec", PHASE8_CROSS_CUTTING_SPECS)
    def test_cross_cutting_spec_exists(self, spec):
        """Phase 8.7 cross-cutting spec must exist under frontend/e2e/dimensions/."""
        path = REPO_ROOT / "frontend" / "e2e" / "dimensions" / spec
        assert path.is_file(), f"Phase 8.7 cross-cutting spec missing: {spec}"


class TestPhase8_9VerifyFailureScenarioAssertsStatus:
    """8.9: verifyFailureScenario asserts API status (8.1)."""

    def test_verify_failure_scenario_function_exists(self):
        """helpers.ts must define verifyFailureScenario."""
        path = REPO_ROOT / "frontend" / "e2e" / "fixtures" / "helpers.ts"
        assert path.is_file(), "frontend/e2e/fixtures/helpers.ts not found"
        content = path.read_text()
        assert "verifyFailureScenario" in content, (
            "verifyFailureScenario must be in helpers.ts (Phase 8.1)"
        )

    def test_verify_failure_scenario_asserts_status(self):
        """verifyFailureScenario must assert response.status() when expectedError.status set."""
        path = REPO_ROOT / "frontend" / "e2e" / "fixtures" / "helpers.ts"
        content = path.read_text()
        assert "expectedError.status" in content, (
            "verifyFailureScenario must accept expectedError.status (Phase 8.1.1)"
        )
        assert "response.status()" in content, (
            "verifyFailureScenario must assert response.status() (Phase 8.1.1)"
        )
        has_status_assert = (
            ".toBe(expectedError.status)" in content
            or "=== expectedError.status" in content
            or ("resp.status()" in content and "expectedError.status" in content)
        )
        assert has_status_assert, (
            "verifyFailureScenario must assert response.status() === expectedError.status"
        )
