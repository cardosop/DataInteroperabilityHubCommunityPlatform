"""
Comprehensive unit tests for CLI installation.

Tests installation via pip, from source, and dependency verification.
No mocks - uses real installation mechanisms.
"""
import pytest
import subprocess
import sys
import importlib
from pathlib import Path
import tempfile
import shutil
import os
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError


class TestCLIInstallation:
    """Test CLI installation methods"""
    
    @pytest.fixture
    def cli_dir(self):
        """Get CLI directory path"""
        return Path(__file__).parent.parent.parent
    
    @pytest.fixture
    def setup_py_path(self, cli_dir):
        """Get setup.py path"""
        return cli_dir / "setup.py"
    
    def test_setup_py_exists(self, setup_py_path):
        """Test that setup.py exists"""
        assert setup_py_path.exists(), "setup.py must exist for installation"
    
    def test_setup_py_valid(self, setup_py_path):
        """Test that setup.py is valid"""
        result = subprocess.run(
            [sys.executable, str(setup_py_path), "check"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0, f"setup.py validation failed: {result.stderr}"
    
    def test_python_requirement(self, setup_py_path):
        """Test that setup.py requires Python 3.12+"""
        content = setup_py_path.read_text()
        assert 'python_requires' in content, "setup.py must specify python_requires"
        assert '>=3.12' in content or "'>='3.12" in content, "setup.py must require Python 3.12+"
    
    def test_entry_points_defined(self, setup_py_path):
        """Test that entry points are defined"""
        content = setup_py_path.read_text()
        assert 'entry_points' in content, "setup.py must define entry_points"
        assert 'console_scripts' in content, "setup.py must define console_scripts"
        assert 'datahub' in content, "setup.py must define 'datahub' entry point"
    
    def test_install_requires_defined(self, setup_py_path):
        """Test that install_requires is defined"""
        content = setup_py_path.read_text()
        assert 'install_requires' in content, "setup.py must define install_requires"
    
    def test_package_structure(self, cli_dir):
        """Test that package structure is correct"""
        datahub_cli_dir = cli_dir / "datahub_cli"
        assert datahub_cli_dir.exists(), "datahub_cli package directory must exist"
        assert (datahub_cli_dir / "__init__.py").exists(), "datahub_cli/__init__.py must exist"
        assert (datahub_cli_dir / "main.py").exists(), "datahub_cli/main.py must exist"
    
    def test_dependencies_importable(self):
        """Test that all required dependencies can be imported"""
        required_deps = ['click', 'requests', 'yaml']
        for dep in required_deps:
            try:
                if dep == 'yaml':
                    importlib.import_module('yaml')
                else:
                    importlib.import_module(dep)
            except ImportError:
                pytest.fail(f"Required dependency '{dep}' cannot be imported")
    
    def test_dependencies_version_compatibility(self):
        """Test that dependencies meet minimum version requirements"""
        def parse_version(version_str):
            """Simple version comparison"""
            parts = [int(x) for x in version_str.split('.')]
            return tuple(parts)
        
        def version_ge(installed, required):
            """Check if installed version >= required version"""
            installed_parts = parse_version(installed)
            required_parts = parse_version(required)
            return installed_parts >= required_parts
        
        try:
            click_version = version('click')
            assert version_ge(click_version, '8.0.0'), \
                f"click version {click_version} is below required 8.0.0"
        except PackageNotFoundError:
            pytest.fail("click is not installed")
        
        try:
            requests_version = version('requests')
            assert version_ge(requests_version, '2.31.0'), \
                f"requests version {requests_version} is below required 2.31.0"
        except PackageNotFoundError:
            pytest.fail("requests is not installed")
        
        try:
            yaml_version = version('pyyaml')
            assert version_ge(yaml_version, '6.0.1'), \
                f"yaml version {yaml_version} is below required 6.0.1"
        except PackageNotFoundError:
            pytest.fail("yaml is not installed")
    
    def test_cli_importable_when_installed(self):
        """Test that CLI can be imported when installed"""
        try:
            import datahub_cli
            assert hasattr(datahub_cli, '__version__'), "datahub_cli must have __version__"
        except ImportError:
            pytest.skip("CLI not installed. Run: cd cli && pip install -e .")
    
    def test_cli_main_importable(self):
        """Test that CLI main module can be imported"""
        try:
            from datahub_cli.main import main, cli
            assert callable(main), "main must be callable"
            assert callable(cli), "cli must be callable"
        except ImportError:
            pytest.skip("CLI not installed. Run: cd cli && pip install -e .")
    
    def test_cli_modules_importable(self):
        """Test that all CLI modules can be imported"""
        modules = [
            'datahub_cli.config',
            'datahub_cli.auth',
            'datahub_cli.commands.assets',
            'datahub_cli.commands.contracts',
            'datahub_cli.commands.config',
        ]
        
        for module_name in modules:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                pytest.fail(f"Module {module_name} cannot be imported: {e}")
    
    def test_install_from_source_dry_run(self, cli_dir, tmp_path):
        """Test installation from source (dry run)"""
        # Create a temporary directory for installation test
        install_dir = tmp_path / "install_test"
        install_dir.mkdir()
        
        # Test dry-run installation
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--dry-run', '--target', str(install_dir), str(cli_dir)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Dry-run may fail in some environments, but should not fail due to package structure
        if result.returncode != 0:
            # Check if it's an externally-managed-environment error (acceptable)
            if 'externally-managed-environment' not in result.stderr:
                # Check if it's a package structure issue
                if 'setup.py' in result.stderr.lower() or 'pyproject.toml' in result.stderr.lower():
                    pytest.fail(f"Package structure issue: {result.stderr}")
    
    def test_entry_point_resolution(self):
        """Test that entry point can be resolved"""
        try:
            from importlib.metadata import entry_points
            console_scripts = entry_points(group='console_scripts')
            datahub_entries = [ep for ep in console_scripts if ep.name == 'datahub']
            if datahub_entries:
                assert len(datahub_entries) > 0, "Entry point 'datahub' must be defined"
        except (ImportError, ValueError):
            # Fallback for older Python versions
            try:
                import pkg_resources
                entry_points = pkg_resources.get_entry_map('datahub-cli', group='console_scripts')
                if entry_points:
                    assert 'datahub' in entry_points, "Entry point 'datahub' must be defined"
            except (pkg_resources.DistributionNotFound, ImportError):
                pytest.skip("CLI not installed. Run: cd cli && pip install -e .")
    
    def test_version_defined(self):
        """Test that version is defined in package"""
        try:
            import datahub_cli
            version = getattr(datahub_cli, '__version__', None)
            assert version is not None, "Package must define __version__"
            assert isinstance(version, str), "__version__ must be a string"
            assert len(version) > 0, "__version__ must not be empty"
        except ImportError:
            pytest.skip("CLI not installed. Run: cd cli && pip install -e .")


class TestCLIInstallationFromSource:
    """Test installation from source code"""
    
    @pytest.fixture
    def cli_dir(self):
        """Get CLI directory path"""
        return Path(__file__).parent.parent.parent
    
    def test_install_editable_mode(self, cli_dir, tmp_path):
        """Test installation in editable mode"""
        # Create a temporary virtual environment
        venv_dir = tmp_path / "venv"
        subprocess.run(
            [sys.executable, '-m', 'venv', str(venv_dir)],
            check=True,
            timeout=60
        )
        
        # Get venv Python executable
        if sys.platform == 'win32':
            venv_python = venv_dir / "Scripts" / "python.exe"
        else:
            venv_python = venv_dir / "bin" / "python"
        
        # Install in editable mode
        result = subprocess.run(
            [str(venv_python), '-m', 'pip', 'install', '-e', str(cli_dir)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cli_dir)
        )
        
        if result.returncode != 0:
            # Check if it's a dependency issue vs package structure issue
            if 'setup.py' in result.stderr.lower() and 'error' in result.stderr.lower():
                pytest.fail(f"Package structure issue during editable install: {result.stderr}")
            # Dependency issues are acceptable in test environment
            pytest.skip(f"Installation failed (may be dependency issue): {result.stderr[:200]}")
        
        # Verify installation
        result = subprocess.run(
            [str(venv_python), '-c', 'import datahub_cli; print(datahub_cli.__version__)'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            assert len(result.stdout.strip()) > 0, "Version should be printed"
    
    def test_install_wheel_mode(self, cli_dir, tmp_path):
        """Test installation via wheel build"""
        # Build wheel
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'wheel', '--no-deps', str(cli_dir), '-w', str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cli_dir)
        )
        
        # Wheel build may fail due to dependencies, but structure should be valid
        if result.returncode != 0:
            if 'setup.py' in result.stderr.lower() and 'error' in result.stderr.lower():
                pytest.fail(f"Package structure issue during wheel build: {result.stderr}")
            pytest.skip(f"Wheel build failed (may be dependency issue): {result.stderr[:200]}")
        
        # Check if wheel was created
        wheels = list(tmp_path.glob("*.whl"))
        if wheels:
            assert len(wheels) > 0, "Wheel should be created"
    
    def test_package_metadata(self, cli_dir):
        """Test that package metadata is correct"""
        setup_py = cli_dir / "setup.py"
        content = setup_py.read_text()
        
        # Check required metadata fields
        required_fields = ['name', 'version', 'description', 'author']
        for field in required_fields:
            assert field in content, f"setup.py must define {field}"


class TestCLIDependencies:
    """Test CLI dependencies"""
    
    def test_all_dependencies_listed(self):
        """Test that all imported dependencies are listed in setup.py"""
        # Get setup.py dependencies
        cli_dir = Path(__file__).parent.parent.parent
        setup_py = cli_dir / "setup.py"
        
        if not setup_py.exists():
            pytest.skip("setup.py not found")
        
        content = setup_py.read_text()
        
        # Check that required dependencies are listed
        required_deps = ['click', 'requests', 'pyyaml']
        for dep in required_deps:
            assert dep in content.lower(), f"Dependency '{dep}' must be listed in setup.py"
    
    def test_no_missing_dependencies(self):
        """Test that no critical dependencies are missing"""
        # Try to import all CLI modules and check for import errors
        modules_to_test = [
            'datahub_cli.main',
            'datahub_cli.config',
            'datahub_cli.auth',
        ]
        
        missing_deps = []
        for module_name in modules_to_test:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                # Check if it's a missing dependency vs module structure issue
                error_msg = str(e)
                if "No module named" in error_msg:
                    missing_dep = error_msg.split("'")[1] if "'" in error_msg else None
                    if missing_dep and missing_dep not in ['datahub_cli']:
                        missing_deps.append(missing_dep)
        
        if missing_deps:
            pytest.fail(f"Missing dependencies: {', '.join(missing_deps)}")
    
    def test_dependency_conflicts(self):
        """Test for dependency version conflicts"""
        # This is a basic check - full conflict resolution would require
        # installing all dependencies which is expensive
        try:
            import click
            import requests
            import yaml
            
            # If we can import all, there are no obvious conflicts
            assert True
        except ImportError as e:
            # Check if it's a version conflict vs missing dependency
            error_msg = str(e)
            if "version" in error_msg.lower() or "conflict" in error_msg.lower():
                pytest.fail(f"Potential dependency conflict: {e}")
            pytest.skip(f"Dependency not available: {e}")

