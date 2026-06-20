"""
Comprehensive Tests for CKAN Instance-Based Connector Creation

Tests the MarketplaceConnectorFactory.create_ckan_connector_from_instance() method
including:
- Instance ID lookup from registry
- API key resolution from environment variables
- API key override support
- Error handling for invalid instances
- Integration with CKANInstanceConfig system

All tests use real configuration - no mocks or stubs.
"""

import os

import pytest
from django.test import TestCase

from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.config.marketplace_instances import (
    get_marketplace_instance_config,
)
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
from hub.apps.integrations.factory import MarketplaceConnectorFactory

pytestmark = pytest.mark.django_db(transaction=True)


class TestCreateCKANConnectorFromInstance(TestCase):
    """Test create_ckan_connector_from_instance() method"""

    @classmethod
    def setUpClass(cls):
        """Set up test class - ensure CKAN connector is registered"""
        super().setUpClass()
        # Ensure CKAN connector is registered
        if not MarketplaceConnectorFactory.is_supported(MarketplaceType.CKAN_INSTANCE):
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.CKAN_INSTANCE, CKANConnector
            )

    def test_create_from_instance_name_dados_gov_br(self):
        """Test creating connector from 'dados.gov.br' instance name."""
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="dados.gov.br"
        )
        # dados.gov.br uses Swagger connector (DadosGovBrConnector), not CKANConnector
        self.assertIsInstance(connector, DadosGovBrConnector)
        self.assertEqual(connector.base_url, "https://dados.gov.br")
        self.assertEqual(connector.marketplace_type, MarketplaceType.CKAN_INSTANCE)

    def test_create_from_instance_name_case_insensitive(self):
        """Test that instance name lookup is case-insensitive."""
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="DADOS.GOV.BR"
        )
        # dados.gov.br uses Swagger connector (DadosGovBrConnector), not CKANConnector
        self.assertIsInstance(connector, DadosGovBrConnector)
        self.assertEqual(connector.base_url, "https://dados.gov.br")

    def test_create_from_instance_name_with_whitespace(self):
        """Test that instance name lookup handles whitespace."""
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="  dados.gov.br  "
        )
        # dados.gov.br uses Swagger connector (DadosGovBrConnector), not CKANConnector
        self.assertIsInstance(connector, DadosGovBrConnector)
        self.assertEqual(connector.base_url, "https://dados.gov.br")

    def test_create_from_instance_name_demo_ckan_org(self):
        """Test creating connector from 'demo.ckan.org' instance name."""
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="demo.ckan.org"
        )
        self.assertIsInstance(connector, CKANConnector)
        self.assertEqual(connector.base_url, "https://demo.ckan.org")

    def test_create_from_instance_name_data_gov(self):
        """Test creating connector from 'data.gov' instance name."""
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="data.gov"
        )
        self.assertIsInstance(connector, CKANConnector)
        self.assertEqual(connector.base_url, "https://data.gov")

    def test_create_with_api_key_from_environment(self):
        """Test that API key/JWT token is resolved from environment variable.

        Instance config uses DADOS_GOV_BR_API_KEY (primary); CKAN_DADOS_GOV_BR_API_KEY
        is deprecated fallback. Set primary so test is isolated from host env.
        """
        original_primary = os.environ.pop("DADOS_GOV_BR_API_KEY", None)
        original_deprecated = os.environ.pop("CKAN_DADOS_GOV_BR_API_KEY", None)
        test_key = "test-api-key-from-env-12345"

        try:
            os.environ["DADOS_GOV_BR_API_KEY"] = test_key
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="dados.gov.br"
            )
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, test_key)
        finally:
            if original_primary is not None:
                os.environ["DADOS_GOV_BR_API_KEY"] = original_primary
            elif "DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["DADOS_GOV_BR_API_KEY"]
            if original_deprecated is not None:
                os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = original_deprecated
            elif "CKAN_DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["CKAN_DADOS_GOV_BR_API_KEY"]

    def test_create_with_api_key_override(self):
        """Test that API key/JWT token override works."""
        original_key = os.environ.get("CKAN_DADOS_GOV_BR_API_KEY")
        env_key = "env-api-key-12345"
        override_key = "override-api-key-67890"

        try:
            os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = env_key
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="dados.gov.br", api_key=override_key
            )
            # Override should take precedence
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, override_key)
        finally:
            if original_key is not None:
                os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = original_key
            elif "CKAN_DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["CKAN_DADOS_GOV_BR_API_KEY"]

    def test_create_without_api_key_when_not_set(self):
        """Test that connector is created without API key/JWT token when not set.

        Instance config checks DADOS_GOV_BR_API_KEY first, then CKAN_DADOS_GOV_BR_API_KEY.
        Unset both so no key is resolved and test is isolated from host env.
        """
        original_primary = os.environ.pop("DADOS_GOV_BR_API_KEY", None)
        original_deprecated = os.environ.pop("CKAN_DADOS_GOV_BR_API_KEY", None)

        try:
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="dados.gov.br"
            )
            # JWT token should be empty string when not set (DadosGovBrConnector default)
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, "")
        finally:
            if original_primary is not None:
                os.environ["DADOS_GOV_BR_API_KEY"] = original_primary
            if original_deprecated is not None:
                os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = original_deprecated

    def test_create_with_none_api_key_override(self):
        """Test that None API key/JWT token override clears environment API key."""
        original_key = os.environ.get("CKAN_DADOS_GOV_BR_API_KEY")
        env_key = "env-api-key-12345"

        try:
            os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = env_key
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="dados.gov.br", api_key=None
            )
            # None override should result in empty string JWT token (DadosGovBrConnector default)
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, "")
        finally:
            if original_key is not None:
                os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = original_key
            elif "CKAN_DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["CKAN_DADOS_GOV_BR_API_KEY"]

    def test_create_with_invalid_instance_id(self):
        """Test that invalid instance ID raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="invalid-instance-name"
            )
        self.assertIn("not found", str(cm.exception).lower())

    def test_create_with_empty_instance_id(self):
        """Test that empty instance ID raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            MarketplaceConnectorFactory.create_ckan_connector_from_instance(instance_id="")
        self.assertIn("instance_id", str(cm.exception).lower())

    def test_create_with_none_instance_id(self):
        """Test that None instance ID raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            MarketplaceConnectorFactory.create_ckan_connector_from_instance(instance_id=None)
        self.assertIn("instance_id", str(cm.exception).lower())

    def test_create_uses_instance_config_base_url(self):
        """Test that connector uses base_url from instance config."""
        config = get_marketplace_instance_config("dados.gov.br")
        self.assertIsNotNone(config)

        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="dados.gov.br"
        )
        self.assertEqual(connector.base_url, config.base_url)

    def test_create_uses_instance_config_api_key_env_var(self):
        """Test that connector uses API key/JWT token from instance config's env var."""
        config = get_marketplace_instance_config("dados.gov.br")
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.api_key_env_var)

        original_key = os.environ.get(config.api_key_env_var)
        test_key = "test-instance-api-key-12345"

        try:
            os.environ[config.api_key_env_var] = test_key
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id="dados.gov.br"
            )
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, test_key)
        finally:
            if original_key is not None:
                os.environ[config.api_key_env_var] = original_key
            elif config.api_key_env_var in os.environ:
                del os.environ[config.api_key_env_var]

    def test_create_for_instance_without_api_key_env_var(self):
        """Test creating connector for instance without API key env var."""
        # demo.ckan.org doesn't have api_key_env_var set
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="demo.ckan.org"
        )
        self.assertIsInstance(connector, CKANConnector)
        self.assertEqual(connector.base_url, "https://demo.ckan.org")
        # API key should be None since instance doesn't have api_key_env_var
        self.assertIsNone(connector.api_key)

    def test_create_with_api_key_override_for_instance_without_env_var(self):
        """Test API key override for instance without env var."""
        override_key = "override-key-12345"
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
            instance_id="demo.ckan.org", api_key=override_key
        )
        self.assertEqual(connector.api_key, override_key)


class TestFactoryUsesInstanceConfiguration(TestCase):
    """Test that factory uses instance configuration when available"""

    @classmethod
    def setUpClass(cls):
        """Set up test class - ensure CKAN connector is registered"""
        super().setUpClass()
        if not MarketplaceConnectorFactory.is_supported(MarketplaceType.CKAN_INSTANCE):
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.CKAN_INSTANCE, CKANConnector
            )

    def test_create_connector_with_instance_config_in_config_dict(self):
        """Test that create_connector() can use instance_id in config dict."""
        connector = MarketplaceConnectorFactory.create_connector(
            marketplace_type=MarketplaceType.CKAN_INSTANCE, config={"instance_id": "dados.gov.br"}
        )
        # dados.gov.br uses Swagger connector (DadosGovBrConnector), not CKANConnector
        self.assertIsInstance(connector, DadosGovBrConnector)
        self.assertEqual(connector.base_url, "https://dados.gov.br")

    def test_create_connector_with_instance_config_and_api_key_override(self):
        """Test create_connector() with instance_id and API key/JWT token override."""
        override_key = "override-key-from-config-12345"
        connector = MarketplaceConnectorFactory.create_connector(
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            config={"instance_id": "dados.gov.br", "api_key": override_key},
        )
        # dados.gov.br uses Swagger connector (DadosGovBrConnector), not CKANConnector
        self.assertIsInstance(connector, DadosGovBrConnector)
        self.assertEqual(connector.base_url, "https://dados.gov.br")
        # DadosGovBrConnector uses jwt_token, not api_key
        self.assertEqual(connector.jwt_token, override_key)

    def test_create_connector_prefers_instance_config_over_base_url(self):
        """Test that instance_id takes precedence over base_url in config."""
        connector = MarketplaceConnectorFactory.create_connector(
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            config={
                "instance_id": "dados.gov.br",
                "base_url": "https://other.ckan.org",  # Should be ignored
            },
        )
        # Should use instance config base_url, not the one in config dict
        self.assertEqual(connector.base_url, "https://dados.gov.br")

    def test_create_connector_with_instance_config_and_env_api_key(self):
        """Test create_connector() with instance_id uses env API key/JWT token.

        Instance config uses DADOS_GOV_BR_API_KEY (primary). Set it so test is isolated."""
        original_primary = os.environ.pop("DADOS_GOV_BR_API_KEY", None)
        original_deprecated = os.environ.pop("CKAN_DADOS_GOV_BR_API_KEY", None)
        test_key = "test-env-key-from-config-12345"

        try:
            os.environ["DADOS_GOV_BR_API_KEY"] = test_key
            connector = MarketplaceConnectorFactory.create_connector(
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                config={"instance_id": "dados.gov.br"},
            )
            # DadosGovBrConnector uses jwt_token, not api_key
            self.assertEqual(connector.jwt_token, test_key)
        finally:
            if original_primary is not None:
                os.environ["DADOS_GOV_BR_API_KEY"] = original_primary
            elif "DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["DADOS_GOV_BR_API_KEY"]
            if original_deprecated is not None:
                os.environ["CKAN_DADOS_GOV_BR_API_KEY"] = original_deprecated
            elif "CKAN_DADOS_GOV_BR_API_KEY" in os.environ:
                del os.environ["CKAN_DADOS_GOV_BR_API_KEY"]