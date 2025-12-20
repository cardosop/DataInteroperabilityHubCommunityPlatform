"""
Unit tests for ODPS schema directory structure.

Tests verify that the required directory structure exists for ODPS schema files.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import os
from pathlib import Path
from django.test import TestCase


class ODPSSchemaDirectoryStructureTest(TestCase):
    """Test ODPS schema directory structure"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for contracts app
        self.base_dir = Path(__file__).parent.parent
        self.schemas_dir = self.base_dir / "schemas"
        self.odps_dir = self.schemas_dir / "odps"

    def test_schemas_directory_exists(self):
        """Test that schemas directory exists"""
        self.assertTrue(
            self.schemas_dir.exists(),
            f"Schemas directory should exist at: {self.schemas_dir}"
        )
        self.assertTrue(
            self.schemas_dir.is_dir(),
            f"Schemas should be a directory: {self.schemas_dir}"
        )

    def test_odps_directory_exists(self):
        """Test that ODPS directory exists"""
        self.assertTrue(
            self.odps_dir.exists(),
            f"ODPS directory should exist at: {self.odps_dir}"
        )
        self.assertTrue(
            self.odps_dir.is_dir(),
            f"ODPS should be a directory: {self.odps_dir}"
        )

    def test_odps_version_directories_exist(self):
        """Test that all required ODPS version directories exist"""
        required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

        for version in required_versions:
            version_dir = self.odps_dir / version
            with self.subTest(version=version):
                self.assertTrue(
                    version_dir.exists(),
                    f"ODPS version directory '{version}' should exist at: {version_dir}"
                )
                self.assertTrue(
                    version_dir.is_dir(),
                    f"ODPS version '{version}' should be a directory: {version_dir}"
                )

    def test_odps_version_directories_are_python_packages(self):
        """Test that all ODPS version directories have __init__.py files"""
        required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

        for version in required_versions:
            version_dir = self.odps_dir / version
            init_file = version_dir / "__init__.py"
            with self.subTest(version=version):
                self.assertTrue(
                    init_file.exists(),
                    f"__init__.py should exist in '{version}' directory: {init_file}"
                )
                self.assertTrue(
                    init_file.is_file(),
                    f"__init__.py should be a file in '{version}' directory: {init_file}"
                )

    def test_schemas_directory_is_python_package(self):
        """Test that schemas directory has __init__.py file"""
        init_file = self.schemas_dir / "__init__.py"
        self.assertTrue(
            init_file.exists(),
            f"__init__.py should exist in schemas directory: {init_file}"
        )
        self.assertTrue(
            init_file.is_file(),
            f"__init__.py should be a file in schemas directory: {init_file}"
        )

    def test_odps_directory_is_python_package(self):
        """Test that ODPS directory has __init__.py file"""
        init_file = self.odps_dir / "__init__.py"
        self.assertTrue(
            init_file.exists(),
            f"__init__.py should exist in ODPS directory: {init_file}"
        )
        self.assertTrue(
            init_file.is_file(),
            f"__init__.py should be a file in ODPS directory: {init_file}"
        )

    def test_directory_structure_completeness(self):
        """Test that the complete directory structure is present"""
        expected_structure = [
            self.schemas_dir,
            self.odps_dir,
            self.odps_dir / "v4.1",
            self.odps_dir / "v4.0",
            self.odps_dir / "v3.x",
            self.odps_dir / "v2.x",
            self.odps_dir / "v1.x",
        ]

        for directory in expected_structure:
            with self.subTest(directory=directory):
                self.assertTrue(
                    directory.exists(),
                    f"Directory should exist: {directory}"
                )
                self.assertTrue(
                    directory.is_dir(),
                    f"Path should be a directory: {directory}"
                )

    def test_no_unexpected_directories(self):
        """Test that only expected version directories exist"""
        required_versions = {"v4.1", "v4.0", "v3.x", "v2.x", "v1.x"}

        if self.odps_dir.exists():
            actual_versions = {
                item.name
                for item in self.odps_dir.iterdir()
                if item.is_dir() and not item.name.startswith("__")
            }

            # Check that all required versions are present
            missing_versions = required_versions - actual_versions
            self.assertEqual(
                len(missing_versions),
                0,
                f"Missing required version directories: {missing_versions}"
            )

            # Check that no unexpected version directories exist
            # (allowing for __pycache__ and other Python artifacts)
            unexpected_versions = actual_versions - required_versions
            # Filter out common Python artifacts
            python_artifacts = {"__pycache__", ".pytest_cache", ".mypy_cache"}
            unexpected_versions = unexpected_versions - python_artifacts

            self.assertEqual(
                len(unexpected_versions),
                0,
                f"Unexpected version directories found: {unexpected_versions}. "
                f"Expected only: {required_versions}"
            )

