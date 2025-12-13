"""
Tests for Python SDK installation and dependencies.

Tests installation via pip, from source, and dependency management.
"""
import pytest
import subprocess
import sys
import importlib
from pathlib import Path


class TestSDKInstallation:
    """Test SDK installation methods"""
    
    def test_sdk_importable(self):
        """
        Test that SDK can be imported after installation
        """
        try:
            import datahub_interoperability
            assert datahub_interoperability.__version__ is not None
        except ImportError:
            pytest.skip("SDK not installed. Run: cd sdk/python && pip install -e .")
    
    def test_sdk_main_modules_importable(self):
        """
        Test that all main SDK modules can be imported
        """
        try:
            from datahub_interoperability import (
                DataHubClient,
                DataHubClientConfig,
                ContractsAPI,
                LineageAPI,
                ScheduledIngestionAPI,
                VersioningAPI,
                GovernanceAPI,
                SearchAPI,
                ObservabilityAPI,
                WebhooksAPI,
            )
            assert DataHubClient is not None
            assert DataHubClientConfig is not None
            assert ContractsAPI is not None
            assert LineageAPI is not None
            assert ScheduledIngestionAPI is not None
            assert VersioningAPI is not None
            assert GovernanceAPI is not None
            assert SearchAPI is not None
            assert ObservabilityAPI is not None
            assert WebhooksAPI is not None
        except ImportError:
            pytest.skip("SDK not installed. Run: cd sdk/python && pip install -e .")
    
    def test_sdk_error_classes_importable(self):
        """
        Test that all error classes can be imported
        """
        try:
            from datahub_interoperability.errors import (
                DataHubError,
                ValidationError,
                UnauthorizedError,
                ForbiddenError,
                NotFoundError,
                ConflictError,
                RateLimitError,
                ServerError,
                NetworkError,
                parse_error,
            )
            assert DataHubError is not None
            assert ValidationError is not None
            assert UnauthorizedError is not None
            assert ForbiddenError is not None
            assert NotFoundError is not None
            assert ConflictError is not None
            assert RateLimitError is not None
            assert ServerError is not None
            assert NetworkError is not None
            assert parse_error is not None
        except ImportError:
            pytest.skip("SDK not installed. Run: cd sdk/python && pip install -e .")
    
    def test_sdk_dependencies_installed(self):
        """
        Test that SDK dependencies are installed
        """
        try:
            import httpx
            import pydantic
            assert httpx is not None
            assert pydantic is not None
        except ImportError as e:
            pytest.fail(f"SDK dependency not installed: {e}")
    
    def test_sdk_version_attribute(self):
        """
        Test that SDK has version attribute
        """
        try:
            import datahub_interoperability
            version = datahub_interoperability.__version__
            assert version is not None
            assert isinstance(version, str)
            # Version should be in format X.Y.Z
            parts = version.split('.')
            assert len(parts) >= 2
        except ImportError:
            pytest.skip("SDK not installed. Run: cd sdk/python && pip install -e .")
    
    def test_sdk_all_export(self):
        """
        Test that SDK __all__ export is correct
        """
        try:
            import datahub_interoperability
            assert hasattr(datahub_interoperability, '__all__')
            assert isinstance(datahub_interoperability.__all__, list)
            assert len(datahub_interoperability.__all__) > 0
        except ImportError:
            pytest.skip("SDK not installed. Run: cd sdk/python && pip install -e .")

