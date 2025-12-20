"""
Unit tests for ODPS URL allowlist/denylist configuration.

Tests verify that URL allowlist/denylist configuration works correctly,
including environment variable support and per-tenant overrides.
"""
try:
    import pytest
    pytestmark = pytest.mark.django_db(transaction=True)
except ImportError:
    # pytest not available, using Django test runner
    pytest = None
    pytestmark = None

import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase

from hub.apps.contracts.config.odps_refs_config import (
    ODPSRefsConfig,
    get_odps_refs_config,
    is_url_allowed,
    ENV_ODPS_URL_ALLOWLIST,
    ENV_ODPS_URL_DENYLIST,
)


class ODPSURLAllowlistDenylistTest(TestCase):
    """Test ODPS URL allowlist/denylist configuration"""

    def setUp(self):
        """Set up test fixtures"""
        # Clear any cached config instance
        import hub.apps.contracts.config.odps_refs_config as config_module
        config_module._config_instance = None

        # Store original environment variables
        self.original_allowlist = os.environ.get(ENV_ODPS_URL_ALLOWLIST)
        self.original_denylist = os.environ.get(ENV_ODPS_URL_DENYLIST)

        # Clear environment variables for clean tests
        if ENV_ODPS_URL_ALLOWLIST in os.environ:
            del os.environ[ENV_ODPS_URL_ALLOWLIST]
        if ENV_ODPS_URL_DENYLIST in os.environ:
            del os.environ[ENV_ODPS_URL_DENYLIST]

    def tearDown(self):
        """Clean up after tests"""
        # Restore original environment variables
        if self.original_allowlist is not None:
            os.environ[ENV_ODPS_URL_ALLOWLIST] = self.original_allowlist
        elif ENV_ODPS_URL_ALLOWLIST in os.environ:
            del os.environ[ENV_ODPS_URL_ALLOWLIST]

        if self.original_denylist is not None:
            os.environ[ENV_ODPS_URL_DENYLIST] = self.original_denylist
        elif ENV_ODPS_URL_DENYLIST in os.environ:
            del os.environ[ENV_ODPS_URL_DENYLIST]

        # Clear cached config instance
        import hub.apps.contracts.config.odps_refs_config as config_module
        config_module._config_instance = None

    def test_default_allowlist_is_empty(self):
        """Test that default allowlist is empty"""
        config = ODPSRefsConfig()
        allowlist = config.url_allowlist

        self.assertIsInstance(allowlist, list)
        self.assertEqual(len(allowlist), 0, "Default allowlist should be empty")

    def test_default_denylist_is_empty(self):
        """Test that default denylist is empty"""
        config = ODPSRefsConfig()
        denylist = config.url_denylist

        self.assertIsInstance(denylist, list)
        self.assertEqual(len(denylist), 0, "Default denylist should be empty")

    def test_empty_allowlist_allows_all_urls(self):
        """Test that empty allowlist allows all URLs (unless in denylist)"""
        config = ODPSRefsConfig()

        # With empty allowlist, all URLs should be allowed
        self.assertTrue(config.is_url_allowed("https://example.com/schema.json"))
        self.assertTrue(config.is_url_allowed("https://any-domain.com/path"))
        self.assertTrue(config.is_url_allowed("http://localhost:8000/schema.json"))

    def test_allowlist_with_exact_url_match(self):
        """Test allowlist with exact URL match"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
url_allowlist:
  - "https://schemas.example.com/schema.json"
  - "https://trusted.com/api/schema"
url_denylist: []
""")
            config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=config_file)

            # Exact matches should be allowed
            self.assertTrue(config.is_url_allowed("https://schemas.example.com/schema.json"))
            self.assertTrue(config.is_url_allowed("https://trusted.com/api/schema"))

            # Non-matching URLs should be denied
            self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))
            self.assertFalse(config.is_url_allowed("https://schemas.example.com/other.json"))
        finally:
            config_file.unlink()

    def test_allowlist_with_domain_wildcard(self):
        """Test allowlist with domain wildcard patterns"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
url_allowlist:
  - "https://*.example.com"
  - "https://schemas.*.trusted.com"
url_denylist: []
""")
            config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=config_file)

            # URLs matching wildcard patterns should be allowed
            self.assertTrue(config.is_url_allowed("https://api.example.com/schema.json"))
            self.assertTrue(config.is_url_allowed("https://schemas.example.com/schema.json"))
            self.assertTrue(config.is_url_allowed("https://schemas.v1.trusted.com/schema.json"))

            # Non-matching URLs should be denied
            self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))
            self.assertFalse(config.is_url_allowed("http://api.example.com/schema.json"))  # Wrong scheme
        finally:
            config_file.unlink()

    def test_denylist_takes_precedence(self):
        """Test that denylist takes precedence over allowlist"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
url_allowlist:
  - "https://*.example.com"
url_denylist:
  - "https://malicious.example.com"
  - "http://*"
""")
            config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=config_file)

            # URL in allowlist but also in denylist should be denied
            self.assertFalse(config.is_url_allowed("https://malicious.example.com/schema.json"))

            # HTTP URLs should be denied (denylist pattern)
            self.assertFalse(config.is_url_allowed("http://api.example.com/schema.json"))

            # HTTPS URLs matching allowlist but not denylist should be allowed
            self.assertTrue(config.is_url_allowed("https://api.example.com/schema.json"))
        finally:
            config_file.unlink()

    def test_environment_variable_allowlist(self):
        """Test that environment variable allowlist works"""
        os.environ[ENV_ODPS_URL_ALLOWLIST] = "https://env.example.com,https://*.env-trusted.com"

        try:
            config = ODPSRefsConfig()

            # URLs from environment variable should be allowed
            self.assertTrue(config.is_url_allowed("https://env.example.com/schema.json"))
            self.assertTrue(config.is_url_allowed("https://api.env-trusted.com/schema.json"))

            # Other URLs should be denied (allowlist is not empty)
            self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))
        finally:
            del os.environ[ENV_ODPS_URL_ALLOWLIST]

    def test_environment_variable_denylist(self):
        """Test that environment variable denylist works"""
        os.environ[ENV_ODPS_URL_DENYLIST] = "http://*,https://*.malicious.com"

        try:
            config = ODPSRefsConfig()

            # URLs in environment denylist should be denied
            self.assertFalse(config.is_url_allowed("http://example.com/schema.json"))
            self.assertFalse(config.is_url_allowed("https://api.malicious.com/schema.json"))

            # Other HTTPS URLs should be allowed (empty allowlist)
            self.assertTrue(config.is_url_allowed("https://example.com/schema.json"))
        finally:
            del os.environ[ENV_ODPS_URL_DENYLIST]

    def test_per_tenant_allowlist_override(self):
        """Test that per-tenant allowlist overrides global config"""
        tenant_config = {
            "url_allowlist": ["https://tenant-specific.com", "https://*.tenant-trusted.com"]
        }

        config = ODPSRefsConfig(tenant_config=tenant_config)

        # Tenant-specific URLs should be allowed
        self.assertTrue(config.is_url_allowed("https://tenant-specific.com/schema.json"))
        self.assertTrue(config.is_url_allowed("https://api.tenant-trusted.com/schema.json"))

        # Other URLs should be denied
        self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))

    def test_per_tenant_denylist_override(self):
        """Test that per-tenant denylist overrides global config"""
        tenant_config = {
            "url_denylist": ["https://*.tenant-blocked.com"]
        }

        config = ODPSRefsConfig(tenant_config=tenant_config)

        # Tenant-blocked URLs should be denied
        self.assertFalse(config.is_url_allowed("https://api.tenant-blocked.com/schema.json"))

        # Other URLs should be allowed (empty allowlist)
        self.assertTrue(config.is_url_allowed("https://example.com/schema.json"))

    def test_per_tenant_both_allowlist_and_denylist(self):
        """Test per-tenant configuration with both allowlist and denylist"""
        tenant_config = {
            "url_allowlist": ["https://*.tenant-allowed.com"],
            "url_denylist": ["https://blocked.tenant-allowed.com"]
        }

        config = ODPSRefsConfig(tenant_config=tenant_config)

        # URL in allowlist but not denylist should be allowed
        self.assertTrue(config.is_url_allowed("https://api.tenant-allowed.com/schema.json"))

        # URL in both allowlist and denylist should be denied (denylist takes precedence)
        self.assertFalse(config.is_url_allowed("https://blocked.tenant-allowed.com/schema.json"))

        # URL not in allowlist should be denied
        self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))

    def test_url_pattern_matching_exact_url(self):
        """Test URL pattern matching with exact URL"""
        from urllib.parse import urlparse

        config = ODPSRefsConfig()

        # Test exact URL matching
        url = "https://example.com/schema.json"
        parsed = urlparse(url)
        self.assertTrue(config._url_matches_pattern(url, parsed, "https://example.com/schema.json"))

    def test_url_pattern_matching_domain_wildcard(self):
        """Test URL pattern matching with domain wildcard"""
        from urllib.parse import urlparse

        config = ODPSRefsConfig()

        # Test domain wildcard matching
        url = "https://api.example.com/schema.json"
        parsed_url = urlparse(url)
        self.assertTrue(config._url_matches_pattern(url, parsed_url, "https://*.example.com"))
        self.assertTrue(config._url_matches_pattern(url, parsed_url, "*.example.com"))
        self.assertFalse(config._url_matches_pattern(url, parsed_url, "https://*.other.com"))

    def test_url_pattern_matching_scheme_required(self):
        """Test that scheme matching works correctly"""
        from urllib.parse import urlparse

        config = ODPSRefsConfig()

        # HTTPS pattern should not match HTTP URL
        url = "http://example.com/schema.json"
        parsed_url = urlparse(url)
        self.assertFalse(config._url_matches_pattern(url, parsed_url, "https://example.com"))

        # HTTP pattern should match HTTP URL
        self.assertTrue(config._url_matches_pattern(url, parsed_url, "http://example.com"))

    def test_invalid_url_returns_false(self):
        """Test that invalid URLs return False"""
        config = ODPSRefsConfig()

        # Invalid URLs should return False
        self.assertFalse(config.is_url_allowed("not-a-url"))
        self.assertFalse(config.is_url_allowed("://invalid"))
        self.assertFalse(config.is_url_allowed(""))

    def test_convenience_function_is_url_allowed(self):
        """Test the convenience function is_url_allowed"""
        # With empty config, all URLs should be allowed
        self.assertTrue(is_url_allowed("https://example.com/schema.json"))

        # With tenant config, should respect tenant settings
        tenant_config = {
            "url_allowlist": ["https://tenant.com"]
        }
        self.assertTrue(is_url_allowed("https://tenant.com/schema.json", tenant_config=tenant_config))
        self.assertFalse(is_url_allowed("https://other.com/schema.json", tenant_config=tenant_config))

    def test_get_odps_refs_config_with_tenant_config(self):
        """Test get_odps_refs_config with tenant config"""
        tenant_config = {
            "url_allowlist": ["https://tenant.com"]
        }

        config = get_odps_refs_config(tenant_config=tenant_config)

        # Should use tenant config
        self.assertEqual(config.url_allowlist, ["https://tenant.com"])
        self.assertTrue(config.is_url_allowed("https://tenant.com/schema.json"))
        self.assertFalse(config.is_url_allowed("https://other.com/schema.json"))

    def test_yaml_config_file_loading(self):
        """Test loading URL allowlist/denylist from YAML config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
url_allowlist:
  - "https://schemas.example.com"
  - "https://*.trusted.com"
url_denylist:
  - "http://*"
  - "https://*.malicious.com"
""")
            config_file = Path(f.name)

        try:
            config = ODPSRefsConfig(config_file=config_file)

            # Verify allowlist loaded
            self.assertIn("https://schemas.example.com", config.url_allowlist)
            self.assertIn("https://*.trusted.com", config.url_allowlist)

            # Verify denylist loaded
            self.assertIn("http://*", config.url_denylist)
            self.assertIn("https://*.malicious.com", config.url_denylist)

            # Test URL validation
            self.assertTrue(config.is_url_allowed("https://schemas.example.com/schema.json"))
            self.assertTrue(config.is_url_allowed("https://api.trusted.com/schema.json"))
            self.assertFalse(config.is_url_allowed("http://example.com/schema.json"))
            self.assertFalse(config.is_url_allowed("https://api.malicious.com/schema.json"))
        finally:
            config_file.unlink()

    def test_environment_variable_overrides_yaml(self):
        """Test that environment variables override YAML config"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
url_allowlist:
  - "https://yaml.example.com"
url_denylist:
  - "https://yaml-blocked.com"
""")
            config_file = Path(f.name)

        try:
            os.environ[ENV_ODPS_URL_ALLOWLIST] = "https://env.example.com"
            os.environ[ENV_ODPS_URL_DENYLIST] = "https://env-blocked.com"

            config = ODPSRefsConfig(config_file=config_file)

            # Environment variable values should be present
            self.assertIn("https://env.example.com", config.url_allowlist)
            self.assertIn("https://env-blocked.com", config.url_denylist)

            # YAML values should also be present (merged)
            self.assertIn("https://yaml.example.com", config.url_allowlist)
            self.assertIn("https://yaml-blocked.com", config.url_denylist)
        finally:
            config_file.unlink()
            if ENV_ODPS_URL_ALLOWLIST in os.environ:
                del os.environ[ENV_ODPS_URL_ALLOWLIST]
            if ENV_ODPS_URL_DENYLIST in os.environ:
                del os.environ[ENV_ODPS_URL_DENYLIST]

    def test_tenant_config_overrides_environment_variables(self):
        """Test that tenant config overrides environment variables"""
        os.environ[ENV_ODPS_URL_ALLOWLIST] = "https://env.example.com"

        try:
            tenant_config = {
                "url_allowlist": ["https://tenant.com"]
            }

            config = ODPSRefsConfig(tenant_config=tenant_config)

            # Tenant config should override environment variable
            self.assertEqual(config.url_allowlist, ["https://tenant.com"])
            self.assertNotIn("https://env.example.com", config.url_allowlist)
        finally:
            if ENV_ODPS_URL_ALLOWLIST in os.environ:
                del os.environ[ENV_ODPS_URL_ALLOWLIST]

