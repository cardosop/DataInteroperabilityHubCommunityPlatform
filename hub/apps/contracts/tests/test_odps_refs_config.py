"""
Unit tests for ODPS $ref resolver configuration.

Tests verify that:
1. Configuration loads from YAML file
2. Environment variables override YAML values
3. Default values are used when no config file exists
4. Directory whitelist validation works correctly
5. Path traversal prevention works
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase

from hub.apps.contracts.config.odps_refs_config import (
    ODPSRefsConfig,
    get_odps_refs_config,
    get_allowed_base_dirs,
    DEFAULT_ALLOWED_BASE_DIRS,
    ENV_ODPS_REFS_DIR,
)


class ODPSRefsConfigTest(TestCase):
    """Test ODPS $ref resolver configuration"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear any cached config instance
        import hub.apps.contracts.config.odps_refs_config as config_module
        config_module._config_instance = None

    def tearDown(self):
        """Clean up after tests"""
        # Clear environment variables
        if ENV_ODPS_REFS_DIR in os.environ:
            del os.environ[ENV_ODPS_REFS_DIR]

        # Clear cached config instance
        import hub.apps.contracts.config.odps_refs_config as config_module
        config_module._config_instance = None

    def test_default_allowed_base_dirs(self):
        """Test that default allowed base directories are correct"""
        self.assertEqual(
            DEFAULT_ALLOWED_BASE_DIRS,
            ["./contracts/refs", "./odps-refs"],
            "Default allowed base directories should match expected values"
        )

    def test_config_loads_defaults_when_no_file(self):
        """Test that configuration loads defaults when config file doesn't exist"""
        # Use a non-existent config file
        non_existent_file = Path("/non/existent/config.yaml")
        config = ODPSRefsConfig(config_file=non_existent_file)

        allowed_dirs = config.allowed_base_dirs
        self.assertEqual(
            allowed_dirs,
            DEFAULT_ALLOWED_BASE_DIRS,
            "Should use default values when config file doesn't exist"
        )

    def test_config_loads_from_yaml_file(self):
        """Test that configuration loads from YAML file"""
        try:
            import yaml
        except ImportError:
            self.skipTest("yaml library not available")

        # Create temporary YAML config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'allowed_base_dirs': ['./custom/refs', './custom/odps-refs']
            }, f)
            temp_config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=temp_config_file)
            allowed_dirs = config.allowed_base_dirs

            self.assertIn('./custom/refs', allowed_dirs)
            self.assertIn('./custom/odps-refs', allowed_dirs)
        finally:
            # Clean up
            temp_config_file.unlink()

    def test_environment_variable_adds_directory(self):
        """Test that ODPS_REFS_DIR environment variable adds directory to allowed list"""
        # Set environment variable
        os.environ[ENV_ODPS_REFS_DIR] = "/custom/env/refs"

        try:
            # Create config with default file (which may not exist)
            config = ODPSRefsConfig()
            allowed_dirs = config.allowed_base_dirs

            # Should include default directories
            self.assertIn("./contracts/refs", allowed_dirs)
            self.assertIn("./odps-refs", allowed_dirs)

            # Should also include environment variable directory
            self.assertIn("/custom/env/refs", allowed_dirs)
        finally:
            # Clean up
            del os.environ[ENV_ODPS_REFS_DIR]

    def test_environment_variable_does_not_duplicate(self):
        """Test that environment variable doesn't add duplicate directories"""
        # Set environment variable to a directory that's already in defaults
        os.environ[ENV_ODPS_REFS_DIR] = "./contracts/refs"

        try:
            config = ODPSRefsConfig()
            allowed_dirs = config.allowed_base_dirs

            # Should only appear once
            self.assertEqual(
                allowed_dirs.count("./contracts/refs"),
                1,
                "Environment variable directory should not be duplicated"
            )
        finally:
            del os.environ[ENV_ODPS_REFS_DIR]

    def test_get_allowed_base_dirs_absolute(self):
        """Test getting allowed base directories as absolute paths"""
        config = ODPSRefsConfig()

        # Use a known base path
        base_path = Path("/project/root")
        absolute_dirs = config.get_allowed_base_dirs_absolute(base_path)

        self.assertIsInstance(absolute_dirs, list)
        self.assertGreater(len(absolute_dirs), 0)

        # All paths should be absolute
        for dir_path in absolute_dirs:
            self.assertTrue(
                dir_path.is_absolute(),
                f"Path should be absolute: {dir_path}"
            )

    def test_is_path_allowed_within_allowed_directory(self):
        """Test that paths within allowed directories are allowed"""
        config = ODPSRefsConfig()

        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create allowed directory
            allowed_dir = temp_path / "contracts" / "refs"
            allowed_dir.mkdir(parents=True)

            # Create a file within allowed directory
            test_file = allowed_dir / "schema.yaml"
            test_file.touch()

            # Update config to use our temp directory by patching _config_data
            with patch.object(config, '_config_data', {'allowed_base_dirs': [str(allowed_dir)]}):
                # Test with relative path
                is_allowed = config.is_path_allowed(test_file, base_path=temp_path)
                self.assertTrue(
                    is_allowed,
                    f"Path within allowed directory should be allowed: {test_file}"
                )

                # Test with absolute path
                is_allowed = config.is_path_allowed(test_file.resolve(), base_path=temp_path)
                self.assertTrue(
                    is_allowed,
                    f"Absolute path within allowed directory should be allowed: {test_file.resolve()}"
                )

    def test_is_path_allowed_outside_allowed_directory(self):
        """Test that paths outside allowed directories are blocked"""
        config = ODPSRefsConfig()

        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create allowed directory
            allowed_dir = temp_path / "contracts" / "refs"
            allowed_dir.mkdir(parents=True)

            # Create a file outside allowed directory
            outside_dir = temp_path / "outside"
            outside_dir.mkdir()
            test_file = outside_dir / "malicious.yaml"
            test_file.touch()

            # Update config to use our temp directory by patching _config_data
            with patch.object(config, '_config_data', {'allowed_base_dirs': [str(allowed_dir)]}):
                is_allowed = config.is_path_allowed(test_file, base_path=temp_path)
                self.assertFalse(
                    is_allowed,
                    f"Path outside allowed directory should be blocked: {test_file}"
                )

    def test_is_path_allowed_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented"""
        config = ODPSRefsConfig()

        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create allowed directory
            allowed_dir = temp_path / "contracts" / "refs"
            allowed_dir.mkdir(parents=True)

            # Create a file in a subdirectory
            subdir = allowed_dir / "subdir"
            subdir.mkdir()
            legitimate_file = subdir / "file.yaml"
            legitimate_file.touch()

            # Try path traversal attack
            traversal_path = allowed_dir / "subdir" / ".." / ".." / "etc" / "passwd"

            # Update config to use our temp directory by patching _config_data
            with patch.object(config, '_config_data', {'allowed_base_dirs': [str(allowed_dir)]}):
                # Legitimate file should be allowed
                is_allowed = config.is_path_allowed(legitimate_file, base_path=temp_path)
                self.assertTrue(
                    is_allowed,
                    "Legitimate file in subdirectory should be allowed"
                )

                # Path traversal should be blocked (even if it resolves to a path outside)
                # Note: The traversal path might not exist, but we test the logic
                is_allowed = config.is_path_allowed(traversal_path, base_path=temp_path)
                # The resolved path should be outside allowed directory
                resolved = traversal_path.resolve()
                try:
                    if not resolved.is_relative_to(allowed_dir.resolve()):
                        self.assertFalse(
                            is_allowed,
                            "Path traversal attack should be blocked"
                        )
                except AttributeError:
                    # Python < 3.9 doesn't have is_relative_to, check differently
                    try:
                        common = Path(os.path.commonpath([resolved, allowed_dir.resolve()]))
                        if common != allowed_dir.resolve():
                            self.assertFalse(
                                is_allowed,
                                "Path traversal attack should be blocked"
                            )
                    except ValueError:
                        # Paths don't share a common path
                        self.assertFalse(
                            is_allowed,
                            "Path traversal attack should be blocked"
                        )

    def test_get_odps_refs_config_singleton(self):
        """Test that get_odps_refs_config returns singleton instance"""
        config1 = get_odps_refs_config()
        config2 = get_odps_refs_config()

        self.assertIs(
            config1,
            config2,
            "get_odps_refs_config should return the same instance"
        )

    def test_get_odps_refs_config_custom_file(self):
        """Test that get_odps_refs_config can use custom config file"""
        try:
            import yaml
        except ImportError:
            self.skipTest("yaml library not available")

        # Create temporary YAML config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'allowed_base_dirs': ['./custom/config/refs']
            }, f)
            temp_config_file = Path(f.name)

        try:
            config = get_odps_refs_config(config_file=temp_config_file)
            allowed_dirs = config.allowed_base_dirs

            self.assertIn('./custom/config/refs', allowed_dirs)
        finally:
            temp_config_file.unlink()

    def test_get_allowed_base_dirs_convenience_function(self):
        """Test the convenience function get_allowed_base_dirs()"""
        dirs = get_allowed_base_dirs()

        self.assertIsInstance(dirs, list)
        self.assertGreater(len(dirs), 0)
        # Should include at least the default directories
        self.assertIn("./contracts/refs", dirs)

    def test_config_handles_invalid_yaml(self):
        """Test that configuration handles invalid YAML gracefully"""
        # Create a file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            temp_config_file = Path(f.name)

        try:
            # Should not raise exception, should use defaults
            config = ODPSRefsConfig(config_file=temp_config_file)
            allowed_dirs = config.allowed_base_dirs

            # Should fall back to defaults
            self.assertEqual(allowed_dirs, DEFAULT_ALLOWED_BASE_DIRS)
        finally:
            temp_config_file.unlink()

    def test_config_handles_missing_yaml_key(self):
        """Test that configuration handles missing allowed_base_dirs key"""
        try:
            import yaml
        except ImportError:
            self.skipTest("yaml library not available")

        # Create YAML file without allowed_base_dirs
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'other_key': 'value'}, f)
            temp_config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=temp_config_file)
            allowed_dirs = config.allowed_base_dirs

            # Should use defaults when key is missing
            self.assertEqual(allowed_dirs, DEFAULT_ALLOWED_BASE_DIRS)
        finally:
            temp_config_file.unlink()

    def test_config_handles_non_list_allowed_base_dirs(self):
        """Test that configuration handles non-list allowed_base_dirs gracefully"""
        try:
            import yaml
        except ImportError:
            self.skipTest("yaml library not available")

        # Create YAML file with allowed_base_dirs as string instead of list
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'allowed_base_dirs': 'not-a-list'}, f)
            temp_config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=temp_config_file)
            allowed_dirs = config.allowed_base_dirs

            # Should use defaults when value is not a list
            self.assertEqual(allowed_dirs, DEFAULT_ALLOWED_BASE_DIRS)
        finally:
            temp_config_file.unlink()

    def test_is_path_allowed_with_absolute_allowed_dir(self):
        """Test path validation with absolute allowed directory"""
        config = ODPSRefsConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            allowed_dir = temp_path / "allowed"
            allowed_dir.mkdir()

            test_file = allowed_dir / "file.yaml"
            test_file.touch()

            # Use absolute path for allowed directory by patching _config_data
            with patch.object(config, '_config_data', {'allowed_base_dirs': [str(allowed_dir.resolve())]}):
                is_allowed = config.is_path_allowed(test_file, base_path=temp_path)
                self.assertTrue(
                    is_allowed,
                    "Path should be allowed when using absolute allowed directory"
                )

    def test_is_path_allowed_with_subdirectory(self):
        """Test that files in subdirectories of allowed directories are allowed"""
        config = ODPSRefsConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            allowed_dir = temp_path / "contracts" / "refs"
            allowed_dir.mkdir(parents=True)

            # Create nested subdirectories
            nested_dir = allowed_dir / "level1" / "level2" / "level3"
            nested_dir.mkdir(parents=True)
            test_file = nested_dir / "deep_file.yaml"
            test_file.touch()

            with patch.object(config, '_config_data', {'allowed_base_dirs': [str(allowed_dir)]}):
                is_allowed = config.is_path_allowed(test_file, base_path=temp_path)
                self.assertTrue(
                    is_allowed,
                    "Files in nested subdirectories should be allowed"
                )

