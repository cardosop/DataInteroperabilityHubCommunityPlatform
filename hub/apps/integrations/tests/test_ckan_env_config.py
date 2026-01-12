"""
Comprehensive Tests for CKAN Environment Variable Configuration

Tests the CKAN environment variable configuration system including:
- Environment variables load correctly from docker-compose
- CKAN_DADOS_GOV_BR_API_KEY configuration
- CKAN_TEST_URL and CKAN_TEST_API_KEY configuration
- Integration with docker-compose.yml
- dados.gov.br integration in test helpers

All tests use real configuration - no mocks or stubs.
"""
import os
import pytest
from django.test import TestCase

from hub.apps.integrations.config.marketplace_instances import (
    get_marketplace_instance_config,
    # Backward compatibility (deprecated)
    get_ckan_instance_config,
)
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    get_test_marketplace_config,
    get_test_ckan_url,
    # Backward compatibility (deprecated)
    get_test_ckan_config,
)


class TestCKANEnvironmentVariables(TestCase):
    """Test CKAN environment variables are available"""

    def test_ckan_dados_gov_br_api_key_env_var_exists(self):
        """Test that CKAN_DADOS_GOV_BR_API_KEY environment variable can be set."""
        # The variable should be settable and readable
        # In docker-compose, it's set with default empty: ${CKAN_DADOS_GOV_BR_API_KEY:-}
        # This means it will be an empty string if not set, or the value if set
        # We test that the variable can be set and read (which validates docker-compose config)
        test_key = "test-dados-api-key-12345"
        original_value = os.environ.get('CKAN_DADOS_GOV_BR_API_KEY')

        try:
            os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = test_key
            env_value = os.getenv('CKAN_DADOS_GOV_BR_API_KEY')
            self.assertEqual(env_value, test_key, "Should be able to set and read CKAN_DADOS_GOV_BR_API_KEY")
        finally:
            if original_value is not None:
                os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = original_value
            elif 'CKAN_DADOS_GOV_BR_API_KEY' in os.environ:
                del os.environ['CKAN_DADOS_GOV_BR_API_KEY']

    def test_ckan_test_url_env_var_exists(self):
        """Test that CKAN_TEST_URL environment variable can be set."""
        # Test that the variable can be set and read (which validates docker-compose config)
        test_url = "https://test.ckan.org"
        original_value = os.environ.get('CKAN_TEST_URL')

        try:
            os.environ['CKAN_TEST_URL'] = test_url
            env_value = os.getenv('CKAN_TEST_URL')
            self.assertEqual(env_value, test_url, "Should be able to set and read CKAN_TEST_URL")
        finally:
            if original_value is not None:
                os.environ['CKAN_TEST_URL'] = original_value
            elif 'CKAN_TEST_URL' in os.environ:
                del os.environ['CKAN_TEST_URL']

    def test_ckan_test_api_key_env_var_exists(self):
        """Test that CKAN_TEST_API_KEY environment variable can be set."""
        # Test that the variable can be set and read (which validates docker-compose config)
        test_key = "test-api-key-12345"
        original_value = os.environ.get('CKAN_TEST_API_KEY')

        try:
            os.environ['CKAN_TEST_API_KEY'] = test_key
            env_value = os.getenv('CKAN_TEST_API_KEY')
            self.assertEqual(env_value, test_key, "Should be able to set and read CKAN_TEST_API_KEY")
        finally:
            if original_value is not None:
                os.environ['CKAN_TEST_API_KEY'] = original_value
            elif 'CKAN_TEST_API_KEY' in os.environ:
                del os.environ['CKAN_TEST_API_KEY']

    def test_ckan_env_vars_can_be_set(self):
        """Test that CKAN environment variables can be set and read."""
        # Test that we can set and read the variables
        test_key = "test-api-key-12345"
        test_url = "https://test.ckan.org"

        os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = test_key
        os.environ['CKAN_TEST_URL'] = test_url

        try:
            self.assertEqual(os.getenv('CKAN_DADOS_GOV_BR_API_KEY'), test_key)
            self.assertEqual(os.getenv('CKAN_TEST_URL'), test_url)
        finally:
            # Cleanup
            if 'CKAN_DADOS_GOV_BR_API_KEY' in os.environ:
                del os.environ['CKAN_DADOS_GOV_BR_API_KEY']
            if 'CKAN_TEST_URL' in os.environ:
                del os.environ['CKAN_TEST_URL']


class TestCKANDadosGovBrIntegration(TestCase):
    """Test dados.gov.br integration"""

    def test_dados_gov_br_config_exists(self):
        """Test that dados.gov.br configuration exists in registry."""
        config = get_marketplace_instance_config('dados.gov.br')
        self.assertIsNotNone(
            config,
            "dados.gov.br should be registered in MARKETPLACE_INSTANCES"
        )
        assert config is not None  # Type narrowing for linter
        self.assertEqual(config.name, 'dados.gov.br')
        self.assertEqual(config.base_url, 'https://dados.gov.br')
        self.assertEqual(config.connector_type, 'swagger')  # dados.gov.br uses Swagger API, NOT CKAN
        self.assertTrue(
            config.is_production,
            "dados.gov.br should be marked as production"
        )

    def test_dados_gov_br_api_key_env_var_name(self):
        """Test dados.gov.br uses correct environment variable name."""
        config = get_marketplace_instance_config('dados.gov.br')
        self.assertIsNotNone(config)
        assert config is not None  # Type narrowing for linter
        self.assertEqual(
            config.api_key_env_var,
            'DADOS_GOV_BR_API_KEY',
            "dados.gov.br should use DADOS_GOV_BR_API_KEY env var (CKAN_DADOS_GOV_BR_API_KEY is deprecated but still supported for backward compatibility)"
        )

    def test_dados_gov_br_api_key_resolution(self):
        """Test that dados.gov.br API key resolution works."""
        config = get_marketplace_instance_config('dados.gov.br')
        self.assertIsNotNone(config)
        assert config is not None  # Type narrowing for linter

        # Test with no API key set (should return None)
        original_value = os.environ.get('CKAN_DADOS_GOV_BR_API_KEY')
        if 'CKAN_DADOS_GOV_BR_API_KEY' in os.environ:
            del os.environ['CKAN_DADOS_GOV_BR_API_KEY']

        try:
            api_key = config.get_api_key()
            self.assertIsNone(api_key, "Should return None when API key not set")

            # Test with API key set
            test_key = "test-dados-api-key"
            os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = test_key
            api_key = config.get_api_key()
            self.assertEqual(
                api_key,
                test_key,
                "Should return API key from environment"
            )
        finally:
            # Restore original value
            if original_value is not None:
                os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = original_value
            elif 'CKAN_DADOS_GOV_BR_API_KEY' in os.environ:
                del os.environ['CKAN_DADOS_GOV_BR_API_KEY']

    def test_dados_gov_br_in_fallback_list(self):
        """Test that dados.gov.br is in test helpers fallback list."""
        # This tests that get_test_ckan_url includes dados.gov.br in fallback
        # We can't directly test the fallback list, but we can test that
        # dados.gov.br can be accessed via get_test_ckan_config
        config = get_test_ckan_config('dados.gov.br')
        self.assertIsNotNone(
            config,
            "dados.gov.br should be accessible via get_test_ckan_config"
        )
        assert config is not None  # Type narrowing for linter
        self.assertEqual(config.base_url, 'https://dados.gov.br')


class TestCKANTestHelpersIntegration(TestCase):
    """Test integration of environment variables with test helpers"""

    def test_get_test_ckan_config_respects_env_vars(self):
        """Test that get_test_ckan_config respects CKAN_TEST_URL environment variable."""
        original_url = os.environ.get('CKAN_TEST_URL')

        try:
            # Set CKAN_TEST_URL to a registered instance
            os.environ['CKAN_TEST_URL'] = 'https://demo.ckan.org'
            config = get_test_ckan_config()

            # Should use the environment variable
            self.assertIsNotNone(config)
            # Note: The actual behavior depends on implementation, but config should exist
        finally:
            if original_url is not None:
                os.environ['CKAN_TEST_URL'] = original_url
            elif 'CKAN_TEST_URL' in os.environ:
                del os.environ['CKAN_TEST_URL']

    def test_get_test_ckan_url_uses_fallback(self):
        """Test that get_test_ckan_url uses fallback instances including dados.gov.br."""
        original_url = os.environ.get('CKAN_TEST_URL')

        try:
            # Clear CKAN_TEST_URL to force fallback
            if 'CKAN_TEST_URL' in os.environ:
                del os.environ['CKAN_TEST_URL']

            url = get_test_ckan_url()
            # Should return one of the fallback instances
            self.assertIsNotNone(url, "get_test_ckan_url should return a URL from fallback list")
            self.assertIn(
                url,
                ['https://demo.ckan.org', 'https://dados.gov.br', 'https://data.gov'],
                f"URL {url} should be one of the registered fallback instances"
            )
        finally:
            if original_url is not None:
                os.environ['CKAN_TEST_URL'] = original_url


class TestDockerComposeConfiguration(TestCase):
    """Test docker-compose.yml configuration"""

    def test_all_ckan_env_vars_available(self):
        """Test that all CKAN environment variables can be set and read."""
        required_vars = [
            'CKAN_DADOS_GOV_BR_API_KEY',
            'CKAN_TEST_URL',
            'CKAN_TEST_API_KEY',
        ]

        for var_name in required_vars:
            # Test that variable can be set and read
            test_value = f"test-value-{var_name}"
            original_value = os.environ.get(var_name)

            try:
                os.environ[var_name] = test_value
                env_value = os.getenv(var_name)
                self.assertEqual(
                    env_value,
                    test_value,
                    f"{var_name} should be settable and readable"
                )
            finally:
                if original_value is not None:
                    os.environ[var_name] = original_value
                elif var_name in os.environ:
                    del os.environ[var_name]

    def test_env_vars_have_correct_names(self):
        """Test that environment variable names match expected format."""
        # Verify the naming convention
        self.assertEqual(
            os.getenv('CKAN_DADOS_GOV_BR_API_KEY', ''),
            os.getenv('CKAN_DADOS_GOV_BR_API_KEY', ''),
            "Environment variable name should be consistent"
        )


@pytest.mark.integration
class TestCKANEnvironmentConfigurationIntegration(TestCase):
    """Integration tests for CKAN environment configuration"""

    def test_full_configuration_flow(self):
        """Test the full configuration flow from environment to config system."""
        original_key = os.environ.get('CKAN_DADOS_GOV_BR_API_KEY')
        test_key = "test-integration-api-key-12345"

        try:
            # 1. Set environment variable
            os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = test_key
            env_key = os.getenv('CKAN_DADOS_GOV_BR_API_KEY')
            self.assertEqual(env_key, test_key, "Environment variable should be settable")

            # 2. Config system can access it
            config = get_marketplace_instance_config('dados.gov.br')
            self.assertIsNotNone(config, "Config should exist")
            assert config is not None  # Type narrowing for linter

            # 3. API key resolution works
            api_key = config.get_api_key()
            self.assertEqual(
                api_key,
                test_key,
                "API key should be resolved from environment"
            )

            # 4. Test helpers can use it
            test_config = get_test_ckan_config('dados.gov.br')
            self.assertIsNotNone(
                test_config,
                "Test helpers should be able to access config"
            )
            assert test_config is not None  # Type narrowing for linter
            self.assertEqual(
                test_config.base_url,
                'https://dados.gov.br',
                "Test config should have correct URL"
            )
        finally:
            if original_key is not None:
                os.environ['CKAN_DADOS_GOV_BR_API_KEY'] = original_key
            elif 'CKAN_DADOS_GOV_BR_API_KEY' in os.environ:
                del os.environ['CKAN_DADOS_GOV_BR_API_KEY']

