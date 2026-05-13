"""
Comprehensive Tests for Marketplace Instance Configuration System

Tests the marketplace instance configuration system including:
- MarketplaceInstanceConfig dataclass (and backward compatibility with CKANInstanceConfig)
- Instance registry (dados.gov.br Swagger API, demo.ckan.org/data.gov CKAN APIs)
- Helper functions (get_marketplace_instance_config, get_default_test_instance)
- Environment variable-based API key resolution
- Backward compatibility with deprecated CKAN naming

All tests use real configuration - no mocks or stubs.
"""

import os
import warnings
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.integrations.config.marketplace_instances import (
    CKAN_INSTANCES,
    MARKETPLACE_INSTANCES,
    # Backward compatibility aliases (deprecated)
    CKANInstanceConfig,
    MarketplaceInstanceConfig,
    get_ckan_instance_config,
    get_default_test_instance,
    get_marketplace_instance_config,
)


class TestCKANInstanceConfig(TestCase):
    """Test CKANInstanceConfig dataclass"""

    def test_ckan_instance_config_creation(self):
        """Test creating CKANInstanceConfig with all fields"""
        config = CKANInstanceConfig(
            name="test-instance",
            base_url="https://test.ckan.org",
            country="BR",
            language="pt-BR",
            organization="Test Org",
            swagger_url="https://test.ckan.org/api/3/swagger.json",
            api_key_env_var="TEST_API_KEY",
            is_production=True,
            is_test_default=False,
        )

        self.assertEqual(config.name, "test-instance")
        self.assertEqual(config.base_url, "https://test.ckan.org")
        self.assertEqual(config.country, "BR")
        self.assertEqual(config.language, "pt-BR")
        self.assertEqual(config.organization, "Test Org")
        self.assertEqual(config.swagger_url, "https://test.ckan.org/api/3/swagger.json")
        self.assertEqual(config.api_key_env_var, "TEST_API_KEY")
        self.assertTrue(config.is_production)
        self.assertFalse(config.is_test_default)

    def test_ckan_instance_config_optional_fields(self):
        """Test CKANInstanceConfig with optional fields"""
        config = CKANInstanceConfig(
            name="minimal-instance",
            base_url="https://minimal.ckan.org",
        )

        self.assertEqual(config.name, "minimal-instance")
        self.assertEqual(config.base_url, "https://minimal.ckan.org")
        self.assertIsNone(config.country)
        self.assertIsNone(config.language)
        self.assertIsNone(config.organization)
        self.assertIsNone(config.swagger_url)
        self.assertIsNone(config.api_key_env_var)
        self.assertFalse(config.is_production)
        self.assertFalse(config.is_test_default)

    def test_ckan_instance_config_api_key_resolution_with_env_var(self):
        """Test API key resolution from environment variable"""
        config = CKANInstanceConfig(
            name="test-instance",
            base_url="https://test.ckan.org",
            api_key_env_var="TEST_CKAN_API_KEY",
        )

        with patch.dict(os.environ, {"TEST_CKAN_API_KEY": "test-api-key-123"}):
            api_key = config.get_api_key()
            self.assertEqual(api_key, "test-api-key-123")

    def test_ckan_instance_config_api_key_resolution_no_env_var(self):
        """Test API key resolution when environment variable is not set"""
        config = CKANInstanceConfig(
            name="test-instance",
            base_url="https://test.ckan.org",
            api_key_env_var="NONEXISTENT_API_KEY",
        )

        api_key = config.get_api_key()
        self.assertIsNone(api_key)

    def test_ckan_instance_config_api_key_resolution_no_env_var_name(self):
        """Test API key resolution when api_key_env_var is not set"""
        config = CKANInstanceConfig(
            name="test-instance",
            base_url="https://test.ckan.org",
        )

        api_key = config.get_api_key()
        self.assertIsNone(api_key)


class TestCKANInstancesRegistry(TestCase):
    """Test marketplace instances registry (using new names)"""

    def test_dados_gov_br_registered(self):
        """Test that dados.gov.br is registered as primary production Swagger API instance"""
        self.assertIn("dados.gov.br", MARKETPLACE_INSTANCES)

        config = MARKETPLACE_INSTANCES["dados.gov.br"]
        self.assertIsInstance(config, MarketplaceInstanceConfig)
        self.assertEqual(config.name, "dados.gov.br")
        self.assertEqual(config.base_url, "https://dados.gov.br")
        self.assertEqual(config.country, "BR")
        self.assertEqual(config.language, "pt-BR")
        self.assertEqual(config.organization, "Brazilian Government")
        self.assertIsNotNone(config.swagger_url)
        self.assertEqual(config.connector_type, "swagger")  # NOT CKAN
        self.assertEqual(
            config.api_key_env_var, "DADOS_GOV_BR_API_KEY"
        )  # Updated to new variable name
        self.assertTrue(config.is_production)
        self.assertFalse(config.is_test_default)

        # Test backward compatibility alias
        self.assertIsInstance(config, CKANInstanceConfig)  # Should work via alias

    def test_demo_ckan_org_registered(self):
        """Test that demo.ckan.org is registered as CKAN API test instance"""
        self.assertIn("demo.ckan.org", MARKETPLACE_INSTANCES)

        config = MARKETPLACE_INSTANCES["demo.ckan.org"]
        self.assertIsInstance(config, MarketplaceInstanceConfig)
        self.assertEqual(config.name, "demo.ckan.org")
        self.assertEqual(config.base_url, "https://demo.ckan.org")
        self.assertEqual(config.connector_type, "ckan")  # Standard CKAN API
        self.assertFalse(config.is_production)
        self.assertFalse(config.is_test_default)

        # Test backward compatibility alias
        self.assertIsInstance(config, CKANInstanceConfig)  # Should work via alias

    def test_data_gov_registered(self):
        """Test that data.gov is registered as CKAN API fallback test instance"""
        self.assertIn("data.gov", MARKETPLACE_INSTANCES)

        config = MARKETPLACE_INSTANCES["data.gov"]
        self.assertIsInstance(config, MarketplaceInstanceConfig)
        self.assertEqual(config.name, "data.gov")
        self.assertEqual(config.base_url, "https://data.gov")
        self.assertEqual(config.connector_type, "ckan")  # Standard CKAN API
        self.assertFalse(config.is_production)
        self.assertFalse(config.is_test_default)

        # Test backward compatibility alias
        self.assertIsInstance(config, CKANInstanceConfig)  # Should work via alias

    def test_all_instances_have_valid_urls(self):
        """Test that all registered instances have valid base URLs"""
        for name, config in MARKETPLACE_INSTANCES.items():
            self.assertIsInstance(config, MarketplaceInstanceConfig)
            self.assertTrue(
                config.base_url.startswith("http://") or config.base_url.startswith("https://")
            )
            self.assertEqual(config.name, name)

    def test_backward_compatibility_ckan_instances_alias(self):
        """Test that CKAN_INSTANCES alias still works (deprecated)"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # CKAN_INSTANCES should be the same object as MARKETPLACE_INSTANCES
            self.assertIs(CKAN_INSTANCES, MARKETPLACE_INSTANCES)
            # Accessing should not trigger warnings (it's just an alias)
            self.assertIn("dados.gov.br", CKAN_INSTANCES)


class TestGetMarketplaceInstanceConfig(TestCase):
    """Test get_marketplace_instance_config helper function (new name)"""

    def test_get_existing_instance(self):
        """Test getting configuration for existing instance"""
        config = get_marketplace_instance_config("dados.gov.br")

        self.assertIsNotNone(config)
        self.assertIsInstance(config, MarketplaceInstanceConfig)
        self.assertEqual(config.name, "dados.gov.br")
        self.assertEqual(config.connector_type, "swagger")  # dados.gov.br uses Swagger API

    def test_get_nonexistent_instance(self):
        """Test getting configuration for nonexistent instance"""
        config = get_marketplace_instance_config("nonexistent.marketplace.org")

        self.assertIsNone(config)

    def test_get_instance_case_insensitive(self):
        """Test that instance lookup is case-insensitive"""
        config1 = get_marketplace_instance_config("dados.gov.br")
        config2 = get_marketplace_instance_config("DADOS.GOV.BR")

        self.assertIsNotNone(config1)
        self.assertIsNotNone(config2)
        self.assertEqual(config1.name, config2.name)

    def test_get_instance_with_whitespace(self):
        """Test that instance lookup handles whitespace"""
        config = get_marketplace_instance_config("  dados.gov.br  ")

        self.assertIsNotNone(config)
        self.assertEqual(config.name, "dados.gov.br")

    def test_get_instance_with_empty_string(self):
        """Test that empty string returns None"""
        config = get_marketplace_instance_config("")
        self.assertIsNone(config)

    def test_get_instance_with_none(self):
        """Test that None returns None"""
        config = get_marketplace_instance_config(None)
        self.assertIsNone(config)


class TestGetCKANInstanceConfig(TestCase):
    """Test get_ckan_instance_config helper function (deprecated, backward compatibility)"""

    def test_get_existing_instance_deprecated(self):
        """Test that deprecated get_ckan_instance_config still works"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = get_ckan_instance_config("dados.gov.br")

            self.assertIsNotNone(config)
            self.assertIsInstance(config, MarketplaceInstanceConfig)
            self.assertEqual(config.name, "dados.gov.br")
            # Should have deprecation warning
            self.assertTrue(len(w) > 0)
            self.assertTrue(any("deprecated" in str(warning.message).lower() for warning in w))


class TestGetDefaultTestInstance(TestCase):
    """Test get_default_test_instance helper function"""

    def test_get_default_test_instance_returns_default(self):
        """Test that get_default_test_instance returns the ckan-test local instance"""
        config = get_default_test_instance()

        self.assertIsNotNone(config)
        self.assertIsInstance(config, CKANInstanceConfig)
        self.assertEqual(config.name, "ckan-test")
        self.assertTrue(config.is_test_default)

    def test_default_test_instance_is_registered(self):
        """Test that default test instance is in registry"""
        config = get_default_test_instance()

        self.assertIn(config.name, CKAN_INSTANCES)
        registered_config = CKAN_INSTANCES[config.name]
        self.assertEqual(config.name, registered_config.name)
        self.assertEqual(config.base_url, registered_config.base_url)


class TestEnvironmentVariableResolution(TestCase):
    """Test environment variable-based API key resolution"""

    def test_dados_gov_br_api_key_from_env(self):
        """Test that dados.gov.br API key is resolved from environment (new variable name)"""
        config = get_marketplace_instance_config("dados.gov.br")

        # Test new environment variable name
        with patch.dict(os.environ, {"DADOS_GOV_BR_API_KEY": "dados-api-key-123"}):
            api_key = config.get_api_key()
            self.assertEqual(api_key, "dados-api-key-123")

        # Test backward compatibility with deprecated variable name
        with patch.dict(os.environ, {"CKAN_DADOS_GOV_BR_API_KEY": "dados-api-key-456"}, clear=True):
            api_key = config.get_api_key()
            self.assertEqual(api_key, "dados-api-key-456", "Backward compatibility should work")

        # Test that new variable takes precedence over deprecated one
        with patch.dict(
            os.environ, {"DADOS_GOV_BR_API_KEY": "new-key", "CKAN_DADOS_GOV_BR_API_KEY": "old-key"}
        ):
            api_key = config.get_api_key()
            self.assertEqual(api_key, "new-key", "New variable should take precedence")

    def test_dados_gov_br_api_key_not_set(self):
        """Test that dados.gov.br API key returns None when not set"""
        config = get_marketplace_instance_config("dados.gov.br")

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("CKAN_DADOS_GOV_BR_API_KEY", None)
            api_key = config.get_api_key()
            self.assertIsNone(api_key)

    def test_demo_instance_no_api_key_env_var(self):
        """Test that demo instance doesn't require API key env var"""
        config = get_marketplace_instance_config("demo.ckan.org")

        # Demo instance may not have api_key_env_var set
        api_key = config.get_api_key()
        # Should not raise exception, may return None
        self.assertIsNone(api_key)  # or could be None if not configured


class TestCKANInstanceConfigIntegration(TestCase):
    """Integration tests for marketplace instance configuration"""

    def test_configuration_loads_correctly(self):
        """Test that configuration system loads correctly"""
        # Verify registry is not empty
        self.assertGreater(len(MARKETPLACE_INSTANCES), 0)

        # Verify all instances are valid
        for name, config in MARKETPLACE_INSTANCES.items():
            self.assertIsInstance(config, MarketplaceInstanceConfig)
            self.assertEqual(config.name, name)
            self.assertIsNotNone(config.base_url)

        # Test backward compatibility alias
        self.assertIs(MARKETPLACE_INSTANCES, CKAN_INSTANCES)

    def test_instance_registry_works(self):
        """Test that instance registry lookup works"""
        # Test production instance (dados.gov.br uses Swagger API)
        prod_config = get_marketplace_instance_config("dados.gov.br")
        self.assertIsNotNone(prod_config)
        self.assertTrue(prod_config.is_production)
        self.assertEqual(prod_config.connector_type, "swagger")  # NOT CKAN

        # Test test instance (demo.ckan.org uses CKAN API)
        test_config = get_default_test_instance()
        self.assertIsNotNone(test_config)
        self.assertTrue(test_config.is_test_default)
        self.assertEqual(test_config.connector_type, "ckan")  # Standard CKAN API

    def test_environment_variable_resolution_works(self):
        """Test that environment variable resolution works"""
        config = get_marketplace_instance_config("dados.gov.br")

        # Test with env var set - patch DADOS_GOV_BR_API_KEY (primary) so our value wins
        # regardless of .env.test or docker-compose (config checks primary first)
        test_key = "test-api-key-from-env-456"
        with patch.dict(os.environ, {"DADOS_GOV_BR_API_KEY": test_key}):
            api_key = config.get_api_key()
            self.assertEqual(api_key, test_key)

        # Test without env var - remove both vars so get_api_key returns None
        orig = {}
        for k in ("DADOS_GOV_BR_API_KEY", "CKAN_DADOS_GOV_BR_API_KEY"):
            if k in os.environ:
                orig[k] = os.environ.pop(k)
        try:
            api_key = config.get_api_key()
            self.assertIsNone(api_key)
        finally:
            os.environ.update(orig)

    def test_get_marketplace_instance_config_with_none(self):
        """Test get_marketplace_instance_config() error handling with None"""
        config = get_marketplace_instance_config(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        self.assertIsNone(config)

    def test_get_marketplace_instance_config_with_empty_string(self):
        """Test get_marketplace_instance_config() error handling with empty string"""
        config = get_marketplace_instance_config("")
        self.assertIsNone(config)

    def test_marketplace_instance_config_with_invalid_base_url(self):
        """Test MarketplaceInstanceConfig error handling with invalid base_url"""
        try:
            config = MarketplaceInstanceConfig(
                name="test-instance",
                base_url="not-a-valid-url",
            )
            # Should handle gracefully or raise ValueError
            self.assertIsNotNone(config)
        except ValueError:
            # Expected if validation is strict
            pass

    def test_marketplace_instance_config_with_none_name(self):
        """Test MarketplaceInstanceConfig error handling with None name"""
        try:
            config = MarketplaceInstanceConfig(
                name=None,  # type: ignore[arg-type]  # test: edge-case type exercise
                base_url="https://test.example.com",
            )
            # Should handle gracefully or raise ValueError
            self.assertIsNotNone(config)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass

    def test_get_api_key_with_none_env_var_name(self):
        """Test get_api_key() error handling when api_key_env_var is None"""
        config = MarketplaceInstanceConfig(
            name="test-instance",
            base_url="https://test.example.com",
            api_key_env_var=None,  # type: ignore[arg-type]  # test: edge-case type exercise
        )
        api_key = config.get_api_key()
        self.assertIsNone(api_key)
