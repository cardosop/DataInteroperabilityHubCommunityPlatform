"""
Unit tests for ODPS test fixtures directory structure.

Tests verify that the required directory structure exists for ODPS test fixtures.
This ensures that test fixtures are properly organized and accessible for ODPS testing.
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


class ODPSFixturesDirectoryStructureTest(TestCase):
    """Test ODPS test fixtures directory structure"""

    def setUp(self):
        """Set up test fixtures"""
        # Get the base directory for tests
        self.base_dir = Path(__file__).parent.parent.parent
        self.fixtures_dir = self.base_dir / "tests" / "fixtures"
        self.odps_fixtures_dir = self.fixtures_dir / "odps"

    def test_fixtures_directory_exists(self):
        """Test that fixtures directory exists"""
        self.assertTrue(
            self.fixtures_dir.exists(),
            f"Fixtures directory should exist at: {self.fixtures_dir}"
        )
        self.assertTrue(
            self.fixtures_dir.is_dir(),
            f"Fixtures should be a directory: {self.fixtures_dir}"
        )

    def test_odps_fixtures_directory_exists(self):
        """Test that ODPS fixtures directory exists"""
        self.assertTrue(
            self.odps_fixtures_dir.exists(),
            f"ODPS fixtures directory should exist at: {self.odps_fixtures_dir}"
        )
        self.assertTrue(
            self.odps_fixtures_dir.is_dir(),
            f"ODPS fixtures should be a directory: {self.odps_fixtures_dir}"
        )

    def test_odps_fixtures_directory_is_python_package(self):
        """Test that ODPS fixtures directory has __init__.py file"""
        init_file = self.odps_fixtures_dir / "__init__.py"
        self.assertTrue(
            init_file.exists(),
            f"__init__.py should exist in ODPS fixtures directory: {init_file}"
        )
        self.assertTrue(
            init_file.is_file(),
            f"__init__.py should be a file in ODPS fixtures directory: {init_file}"
        )

    def test_odps_version_directories_exist(self):
        """Test that all required ODPS version directories exist"""
        required_versions = ["v4.1", "v4.0", "v3.x", "v2.x", "v1.x"]

        for version in required_versions:
            version_dir = self.odps_fixtures_dir / version
            with self.subTest(version=version):
                self.assertTrue(
                    version_dir.exists(),
                    f"ODPS version directory '{version}' should exist at: {version_dir}"
                )
                self.assertTrue(
                    version_dir.is_dir(),
                    f"ODPS version '{version}' should be a directory: {version_dir}"
                )

    def test_odps_v4_1_subdirectories_exist(self):
        """Test that ODPS v4.1 subdirectories exist"""
        v4_1_dir = self.odps_fixtures_dir / "v4.1"
        required_subdirs = ["valid", "invalid", "with_refs"]

        for subdir in required_subdirs:
            subdir_path = v4_1_dir / subdir
            with self.subTest(subdir=subdir):
                self.assertTrue(
                    subdir_path.exists(),
                    f"ODPS v4.1 subdirectory '{subdir}' should exist at: {subdir_path}"
                )
                self.assertTrue(
                    subdir_path.is_dir(),
                    f"ODPS v4.1 '{subdir}' should be a directory: {subdir_path}"
                )

    def test_security_directory_exists(self):
        """Test that security directory exists"""
        security_dir = self.odps_fixtures_dir / "security"
        self.assertTrue(
            security_dir.exists(),
            f"Security directory should exist at: {security_dir}"
        )
        self.assertTrue(
            security_dir.is_dir(),
            f"Security should be a directory: {security_dir}"
        )

    def test_malicious_directory_exists(self):
        """Test that malicious directory exists"""
        malicious_dir = self.odps_fixtures_dir / "security" / "malicious"
        self.assertTrue(
            malicious_dir.exists(),
            f"Malicious directory should exist at: {malicious_dir}"
        )
        self.assertTrue(
            malicious_dir.is_dir(),
            f"Malicious should be a directory: {malicious_dir}"
        )

    def test_directory_structure_completeness(self):
        """Test that the complete directory structure is present"""
        expected_structure = [
            self.fixtures_dir,
            self.odps_fixtures_dir,
            self.odps_fixtures_dir / "v4.1",
            self.odps_fixtures_dir / "v4.1" / "valid",
            self.odps_fixtures_dir / "v4.1" / "invalid",
            self.odps_fixtures_dir / "v4.1" / "with_refs",
            self.odps_fixtures_dir / "v4.0",
            self.odps_fixtures_dir / "v3.x",
            self.odps_fixtures_dir / "v2.x",
            self.odps_fixtures_dir / "v1.x",
            self.odps_fixtures_dir / "security",
            self.odps_fixtures_dir / "security" / "malicious",
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

    def test_all_directories_have_init_files(self):
        """Test that all directories have __init__.py files (Python package structure)"""
        directories_to_check = [
            self.odps_fixtures_dir,
            self.odps_fixtures_dir / "v4.1",
            self.odps_fixtures_dir / "v4.1" / "valid",
            self.odps_fixtures_dir / "v4.1" / "invalid",
            self.odps_fixtures_dir / "v4.1" / "with_refs",
            self.odps_fixtures_dir / "v4.0",
            self.odps_fixtures_dir / "v3.x",
            self.odps_fixtures_dir / "v2.x",
            self.odps_fixtures_dir / "v1.x",
            self.odps_fixtures_dir / "security",
            self.odps_fixtures_dir / "security" / "malicious",
        ]

        for directory in directories_to_check:
            init_file = directory / "__init__.py"
            with self.subTest(directory=directory):
                self.assertTrue(
                    init_file.exists(),
                    f"__init__.py should exist in {directory}: {init_file}"
                )
                self.assertTrue(
                    init_file.is_file(),
                    f"__init__.py should be a file in {directory}: {init_file}"
                )

