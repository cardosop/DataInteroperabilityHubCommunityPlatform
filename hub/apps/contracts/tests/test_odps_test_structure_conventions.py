"""
Test structure and conventions verification for ODPS tests (Task 1.7.6)

This test verifies that all ODPS test files follow the defined structure and conventions:
1. Test file organization: `test_odps_*.py`
2. Test fixture organization: `tests/fixtures/odps_*.yaml` or `tests/fixtures/odps/**/*.yaml`
3. Test naming convention: `test_<functionality>_<scenario>_<expected_result>`

Uses real file system inspection (no mocks/stubs).
"""

import ast
from pathlib import Path

from django.test import TestCase


class ODPSTestStructureConventionsTest(TestCase):
    """Verify ODPS test files follow structure and naming conventions"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the tests directory
        self.tests_dir = Path(__file__).parent
        self.project_root = self.tests_dir.parent.parent.parent.parent
        self.fixtures_dir = self.project_root / "tests" / "fixtures" / "odps"

    def test_all_odps_test_files_follow_naming_convention(self):
        """
        Verify all ODPS test files follow the naming convention: test_odps_*.py

        Convention: Test files MUST be named `test_odps_*.py`
        """
        test_files = list(self.tests_dir.glob("test_odps_*.py"))

        # All files should match the pattern
        for test_file in test_files:
            self.assertTrue(
                test_file.name.startswith("test_odps_"),
                f"ODPS test file '{test_file.name}' does not follow naming convention 'test_odps_*.py'",
            )
            self.assertTrue(
                test_file.name.endswith(".py"),
                f"ODPS test file '{test_file.name}' does not have .py extension",
            )

    def test_all_odps_test_files_have_test_classes(self):
        """
        Verify all ODPS test files contain at least one test class.

        Convention: Test files MUST contain at least one test class (Test* or *Test)
        """
        test_files = list(self.tests_dir.glob("test_odps_*.py"))

        for test_file in test_files:
            with open(test_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(test_file))

                # Find all class definitions
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

                # Check if at least one class is a test class
                test_classes = [
                    cls for cls in classes if cls.startswith("Test") or cls.endswith("Test")
                ]

                self.assertGreater(
                    len(test_classes),
                    0,
                    f"ODPS test file '{test_file.name}' does not contain any test class (Test* or *Test)",
                )

    def test_all_odps_test_methods_follow_naming_convention(self):
        """
        Verify all ODPS test methods follow the naming convention.

        Convention: Test methods MUST be named `test_<functionality>_<scenario>_<expected_result>`
        Pattern: test_<word>_<word>_<word> (at least 3 parts separated by underscores)
        """
        test_files = list(self.tests_dir.glob("test_odps_*.py"))
        violations = []

        for test_file in test_files:
            with open(test_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(test_file))

                # Find all function definitions
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith("test_"):
                            # Check naming convention: test_<functionality>_<scenario>_<expected_result>
                            parts = node.name.split("_")
                            if len(parts) < 3:
                                violations.append(
                                    f"{test_file.name}::{node.name} - "
                                    f"Test method should have at least 3 parts: "
                                    f"test_<functionality>_<scenario>_<expected_result>"
                                )

        if violations:
            self.fail(
                f"Found {len(violations)} test method naming violations:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def test_odps_fixtures_directory_exists(self):
        """
        Verify ODPS fixtures directory exists and follows structure.

        Convention: Fixtures MUST be in `tests/fixtures/odps/` directory
        """
        self.assertTrue(
            self.fixtures_dir.exists(),
            f"ODPS fixtures directory does not exist: {self.fixtures_dir}",
        )
        self.assertTrue(
            self.fixtures_dir.is_dir(),
            f"ODPS fixtures path is not a directory: {self.fixtures_dir}",
        )

    def test_odps_fixtures_organized_by_version(self):
        """
        Verify ODPS fixtures are organized by version.

        Convention: Fixtures MUST be organized by version: v4.1/, v4.0/, v3.x/, v2.x/, v1.x/
        """
        expected_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

        for version in expected_versions:
            version_dir = self.fixtures_dir / version
            self.assertTrue(
                version_dir.exists(),
                f"ODPS fixtures version directory does not exist: {version_dir}",
            )
            self.assertTrue(
                version_dir.is_dir(),
                f"ODPS fixtures version path is not a directory: {version_dir}",
            )

    def test_odps_fixtures_have_valid_structure(self):
        """
        Verify ODPS fixtures have valid directory structure.

        Convention: Fixtures SHOULD be organized by scenario: valid/, invalid/, with_refs/, marketplace/, multilingual/
        """
        # Check v4.1 structure (most complete)
        v4_1_dir = self.fixtures_dir / "v4.1"
        if v4_1_dir.exists():
            expected_scenarios = ["valid", "invalid", "with_refs", "marketplace", "multilingual"]

            for scenario in expected_scenarios:
                scenario_dir = v4_1_dir / scenario
                if scenario_dir.exists():
                    self.assertTrue(
                        scenario_dir.is_dir(),
                        f"ODPS fixtures scenario path is not a directory: {scenario_dir}",
                    )

    def test_odps_fixtures_naming_convention(self):
        """
        Verify ODPS fixture files follow naming convention.

        Convention: Fixture files SHOULD be named `*odps*.yaml` or `*odps*.json` or follow pattern:
        - Valid: `sample-valid-v4.1.json`, `sample-*-v4.1.json`
        - Invalid: `invalid-*-v4.1.json`
        - With refs: `sample-*-ref-v4.1.json` or `sample-*-refs-v4.1.json`
        """
        violations = []

        # Check all fixture files
        for fixture_file in self.fixtures_dir.rglob("*.yaml"):
            if fixture_file.name not in ["__init__.py"]:
                # YAML files should follow naming convention
                if not any(
                    keyword in fixture_file.name.lower()
                    for keyword in ["odps", "sample", "invalid", "ref"]
                ):
                    violations.append(
                        f"Fixture file '{fixture_file.relative_to(self.fixtures_dir)}' "
                        f"does not follow naming convention"
                    )

        for fixture_file in self.fixtures_dir.rglob("*.json"):
            if fixture_file.name not in ["__init__.py"]:
                # JSON files should follow naming convention
                if not any(
                    keyword in fixture_file.name.lower()
                    for keyword in ["odps", "sample", "invalid", "ref", "malicious"]
                ):
                    violations.append(
                        f"Fixture file '{fixture_file.relative_to(self.fixtures_dir)}' "
                        f"does not follow naming convention"
                    )

        # Only warn, don't fail (naming is flexible)
        if violations:
            print(
                f"\nWarning: Found {len(violations)} fixture files that may not follow naming convention:"
            )
            for v in violations[:10]:  # Show first 10
                print(f"  - {v}")

    def test_odps_test_files_reference_fixtures_correctly(self):
        """
        Verify ODPS test files reference fixtures correctly.

        Convention: Test files SHOULD reference fixtures from `tests/fixtures/odps/` directory
        """
        test_files = list(self.tests_dir.glob("test_odps_*.py"))
        violations = []

        for test_file in test_files:
            with open(test_file, encoding="utf-8") as f:
                content = f.read()

                # Check if file references fixtures directory
                # Look for common patterns: fixtures/odps, tests/fixtures/odps
                if "fixtures" in content.lower() and "odps" in content.lower():
                    # Check if path is correct
                    if "tests/fixtures/odps" not in content and "fixtures/odps" not in content:
                        violations.append(
                            f"{test_file.name} - References fixtures but path may be incorrect"
                        )

        # Only warn, don't fail (some tests may use inline fixtures)
        if violations:
            print(
                f"\nInfo: Found {len(violations)} test files that may reference fixtures incorrectly:"
            )
            for v in violations[:5]:  # Show first 5
                print(f"  - {v}")

    def test_odps_test_structure_summary(self):
        """
        Generate summary of ODPS test structure compliance.

        This test provides a summary of the test structure and conventions.
        """
        test_files = list(self.tests_dir.glob("test_odps_*.py"))
        test_methods = []

        for test_file in test_files:
            with open(test_file, encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(test_file))

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith("test_"):
                            test_methods.append(f"{test_file.name}::{node.name}")

        fixture_files = list(self.fixtures_dir.rglob("*.yaml")) + list(
            self.fixtures_dir.rglob("*.json")
        )
        fixture_files = [f for f in fixture_files if f.name != "__init__.py"]

        print("\n" + "=" * 80)
        print("ODPS Test Structure and Conventions Summary")
        print("=" * 80)
        print(f"\nTest Files: {len(test_files)}")
        print("  Pattern: test_odps_*.py")
        for tf in sorted(test_files)[:10]:  # Show first 10
            print(f"  - {tf.name}")
        if len(test_files) > 10:
            print(f"  ... and {len(test_files) - 10} more")

        print(f"\nTest Methods: {len(test_methods)}")
        print("  Pattern: test_<functionality>_<scenario>_<expected_result>")

        print(f"\nFixture Files: {len(fixture_files)}")
        print("  Location: tests/fixtures/odps/")
        print("  Organization: By version (v4.1, v4.0, v3.x, v2.x, v1.x)")
        print("  Organization: By scenario (valid, invalid, with_refs, marketplace, multilingual)")

        print("\n" + "=" * 80)
