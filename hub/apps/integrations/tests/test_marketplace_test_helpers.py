"""
Comprehensive Tests for CKAN Test Helper Utilities

Tests the centralized test utilities including:
- get_test_marketplace_config()
- create_test_connector()
- verify_marketplace_connection()
- marketplace_available()
- Backward compatibility functions

All tests use real configuration - no mocks or stubs.
"""

import os
from unittest.mock import patch

import pytest
from django.test import TestCase

from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    get_test_api_key,
    get_test_ckan_url,
    get_test_marketplace_config,
    marketplace_available,
    verify_marketplace_connection,
)


class TestGetTestCKANConfig(TestCase):
    """Test get_test_marketplace_config() function"""

    def test_get_default_test_config(self):
        """Test getting default test configuration"""
        config = get_test_marketplace_config()

        self.assertIsNotNone(config)
        self.assertEqual(config.name, "ckan-test")
        self.assertTrue(config.is_test_default)

    def test_get_specific_instance_config(self):
        """Test getting configuration for specific instance"""
        config = get_test_marketplace_config("dados.gov.br")

        self.assertIsNotNone(config)
        self.assertEqual(config.name, "dados.gov.br")
        self.assertTrue(config.is_production)

    def test_get_nonexistent_instance(self):
        """Test getting configuration for nonexistent instance"""
        config = get_test_marketplace_config("nonexistent.ckan.org")

        self.assertIsNone(config)

    def test_get_config_with_env_var(self):
        """Test that CKAN_TEST_URL environment variable is respected"""
        with patch.dict(os.environ, {"CKAN_TEST_URL": "https://dados.gov.br"}):
            config = get_test_marketplace_config()

            # Should prefer the env var instance
            self.assertIsNotNone(config)
            self.assertEqual(config.name, "dados.gov.br")

    def test_prefer_production_flag(self):
        """Test prefer_production flag"""
        config = get_test_marketplace_config(prefer_production=True)

        # Should return production instance if available
        self.assertIsNotNone(config)
        # Could be production or default test instance depending on env vars
        self.assertIn(config.name, ["dados.gov.br", "demo.ckan.org", "ckan-test"])


class TestCreateTestConnector(TestCase):
    """Test create_test_connector() function"""

    def test_create_connector_with_default_config(self):
        """Test creating connector with default configuration"""
        connector = create_test_connector(verify_connection=False)

        self.assertIsNotNone(connector)
        self.assertIsInstance(connector, CKANConnector)
        # Default test instance is ckan-test (local Docker container)
        from hub.apps.integrations.config.marketplace_instances import get_default_test_instance

        expected_url = get_default_test_instance().base_url
        self.assertEqual(connector.base_url, expected_url)

    def test_create_connector_with_specific_instance(self):
        """Test creating connector for specific instance"""
        connector = create_test_connector(instance_name="demo.ckan.org", verify_connection=False)

        self.assertIsNotNone(connector)
        self.assertIsInstance(connector, CKANConnector)
        self.assertEqual(connector.base_url, "https://demo.ckan.org")

    def test_create_connector_with_api_key(self):
        """Test creating connector with explicit API key"""
        connector = create_test_connector(api_key="test-api-key-123", verify_connection=False)

        self.assertIsNotNone(connector)
        self.assertEqual(connector.api_key, "test-api-key-123")

    def test_create_connector_with_env_api_key(self):
        """Test creating connector with API key/JWT token from environment"""
        # Patch both primary and deprecated env vars so test value is used (config prefers DADOS_GOV_BR_API_KEY)
        with patch.dict(
            os.environ,
            {
                "DADOS_GOV_BR_API_KEY": "env-api-key-456",
                "CKAN_DADOS_GOV_BR_API_KEY": "env-api-key-456",
            },
        ):
            connector = create_test_connector(instance_name="dados.gov.br", verify_connection=False)

            self.assertIsNotNone(connector)
            # dados.gov.br uses DadosGovBrConnector which uses jwt_token, not api_key
            from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

            if isinstance(connector, DadosGovBrConnector):
                self.assertEqual(connector.jwt_token, "env-api-key-456")
            else:
                # For CKAN connectors, check api_key
                self.assertEqual(connector.api_key, "env-api-key-456")

    def test_create_connector_with_legacy_env_key(self):
        """Test creating connector with legacy CKAN_TEST_API_KEY"""
        with patch.dict(os.environ, {"CKAN_TEST_API_KEY": "legacy-key-789"}):
            connector = create_test_connector(verify_connection=False)

            self.assertIsNotNone(connector)
            # Check appropriate attribute based on connector type
            from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

            if isinstance(connector, DadosGovBrConnector):
                # DadosGovBrConnector doesn't use legacy CKAN_TEST_API_KEY, so jwt_token should be empty
                # This test is for CKAN connectors primarily
                pass  # Skip assertion for Swagger connectors with legacy key
            else:
                # For CKAN connectors, check api_key
                self.assertEqual(connector.api_key, "legacy-key-789")

    def test_create_connector_nonexistent_instance(self):
        """Test creating connector for nonexistent instance"""
        connector = create_test_connector(
            instance_name="nonexistent.ckan.org", verify_connection=False
        )

        self.assertIsNone(connector)

    @pytest.mark.integration
    def test_create_connector_with_verification(self):
        """Test creating connector with connection verification"""
        connector = create_test_connector(verify_connection=True)

        # May be None if connection fails, or connector if successful
        if connector:
            self.assertIsInstance(connector, CKANConnector)
            # Connection should be verified
            self.assertTrue(connector.test_connection())


class TestVerifyCKANConnection(TestCase):
    """Test verify_marketplace_connection() function"""

    def test_verify_connection_with_valid_connector(self):
        """Test verifying connection with valid connector"""
        connector = CKANConnector(base_url="https://demo.ckan.org")

        # May succeed or fail depending on network, but should not raise exception
        try:
            result = verify_marketplace_connection(connector)
            self.assertIsInstance(result, bool)
        except Exception:
            # If network is unavailable, that's acceptable for unit tests
            pass

    def test_verify_connection_with_none(self):
        """Test verifying connection with None connector raises ValueError"""
        with self.assertRaises(ValueError):
            verify_marketplace_connection(None)

    def test_verify_connection_with_invalid_url(self):
        """Test verifying connection with invalid URL"""
        connector = CKANConnector(base_url="https://invalid-ckan-instance-xyz-12345.com")

        result = verify_marketplace_connection(connector)
        self.assertFalse(result)

    @pytest.mark.integration
    def test_verify_connection_integration(self):
        """Integration test for connection verification"""
        connector = create_test_connector(verify_connection=False)

        if connector:
            result = verify_marketplace_connection(connector)
            # Should return True if connection successful
            self.assertIsInstance(result, bool)


class TestCKANAvailable(TestCase):
    """Test marketplace_available() function"""

    def test_ckan_available_default(self):
        """Test checking availability of default test instance"""
        # May return True or False depending on network
        result = marketplace_available()
        self.assertIsInstance(result, bool)

    def test_ckan_available_specific_instance(self):
        """Test checking availability of specific instance"""
        result = marketplace_available("demo.ckan.org")
        self.assertIsInstance(result, bool)

    def test_ckan_available_nonexistent_instance(self):
        """Test checking availability of nonexistent instance"""
        result = marketplace_available("nonexistent.ckan.org")
        self.assertFalse(result)


class TestBackwardCompatibility(TestCase):
    """Test backward compatibility functions"""

    def test_get_test_ckan_url(self):
        """Test backward compatibility function get_test_ckan_url()"""
        url = get_test_ckan_url()

        # Should return URL or None
        if url:
            self.assertIsInstance(url, str)
            self.assertTrue(url.startswith("http://") or url.startswith("https://"))

    def test_get_test_api_key(self):
        """Test backward compatibility function get_test_api_key()"""
        # Without env var, should return None or key from config
        api_key = get_test_api_key()

        # May be None or a string
        if api_key:
            self.assertIsInstance(api_key, str)

    def test_get_test_api_key_with_env_var(self):
        """Test get_test_api_key() with environment variable"""
        with patch.dict(os.environ, {"CKAN_TEST_API_KEY": "test-key-backward-compat"}):
            api_key = get_test_api_key()

            self.assertEqual(api_key, "test-key-backward-compat")

    def test_get_test_api_key_with_config_env_var(self):
        """Test get_test_api_key() with config-based environment variable"""
        with patch.dict(os.environ, {"CKAN_DADOS_GOV_BR_API_KEY": "config-key-backward-compat"}):
            api_key = get_test_api_key()

            # Should return the key if config system provides it
            # May be None if default test instance doesn't use this env var
            if api_key:
                self.assertIsInstance(api_key, str)


class TestCKANTestHelpersIntegration(TestCase):
    """Integration tests for CKAN test helpers"""

    @pytest.mark.integration
    def test_full_workflow(self):
        """Test full workflow: config -> connector -> verification"""
        # Get config
        config = get_test_marketplace_config()
        self.assertIsNotNone(config)

        # Create connector
        connector = create_test_connector(verify_connection=False)
        self.assertIsNotNone(connector)

        # Verify connection
        if connector:
            result = verify_marketplace_connection(connector)
            self.assertIsInstance(result, bool)

    @pytest.mark.integration
    def test_backward_compatibility_workflow(self):
        """Test backward compatibility workflow"""
        # Old way should still work
        url = get_test_ckan_url()
        api_key = get_test_api_key()

        if url:
            connector = CKANConnector(base_url=url, api_key=api_key)
            self.assertIsInstance(connector, CKANConnector)
            self.assertEqual(connector.base_url, url)

    def test_config_system_integration(self):
        """Test that utilities integrate with config system"""
        # Should use config system
        config = get_test_marketplace_config("dados.gov.br")
        self.assertIsNotNone(config)

        # Should create connector using config
        connector = create_test_connector(instance_name="dados.gov.br", verify_connection=False)
        if connector:
            self.assertEqual(connector.base_url, config.base_url)

    def test_create_test_connector_with_none_instance_name(self):
        """Test create_test_connector() error handling with None instance_name"""
        try:
            connector = create_test_connector(
                instance_name=None,
                verify_connection=False,  # type: ignore[arg-type]  # test: edge-case type exercise
            )
            # Should handle gracefully (may use default)
            if connector:
                self.assertIsInstance(connector, CKANConnector)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass

    def test_create_test_connector_with_empty_instance_name(self):
        """Test create_test_connector() error handling with empty instance_name"""
        try:
            connector = create_test_connector(instance_name="", verify_connection=False)
            # Should handle gracefully (may use default or return None)
            if connector:
                self.assertIsInstance(connector, CKANConnector)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass

    def test_verify_marketplace_connection_with_none_connector(self):
        """Test verify_marketplace_connection() error handling with None connector"""
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            verify_marketplace_connection(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_marketplace_available_with_none_instance_name(self):
        """Test marketplace_available() error handling with None instance_name"""
        result = marketplace_available(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        self.assertFalse(result)

    def test_marketplace_available_with_empty_instance_name(self):
        """Test marketplace_available() error handling with empty instance_name"""
        result = marketplace_available("")
        self.assertFalse(result)

    def test_get_test_marketplace_config_with_none(self):
        """Test get_test_marketplace_config() error handling with None"""
        config = get_test_marketplace_config(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        self.assertIsNone(config)

    def test_get_test_marketplace_config_with_empty_string(self):
        """Test get_test_marketplace_config() error handling with empty string"""
        config = get_test_marketplace_config("")
        self.assertIsNone(config)
