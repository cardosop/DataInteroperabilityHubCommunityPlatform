"""
Integrations App Configuration
"""
from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    """Configuration for integrations app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.integrations'
    verbose_name = 'Integrations'

    def ready(self):
        """Import signal handlers and register connectors when app is ready"""
        import hub.apps.integrations.signals  # noqa: F401

        # Register marketplace connectors
        self._register_connectors()

    def _register_connectors(self):
        """Register marketplace connectors with the factory"""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.base import MarketplaceType
        import logging

        logger = logging.getLogger(__name__)

        # Register CKAN connector
        try:
            from hub.apps.integrations.connectors.ckan_connector import CKANConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.CKAN_INSTANCE,
                CKANConnector
            )
        except ImportError as e:
            # Log but don't fail if connector can't be imported
            logger.warning(f"Failed to register CKAN connector: {e}")

        # Register dados.gov.br connector (uses CKAN_INSTANCE type for compatibility)
        try:
            from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
            # Note: DadosGovBrConnector uses CKAN_INSTANCE type for compatibility
            # It's already registered via CKANConnector above, but we register it explicitly
            # to ensure it's available when using marketplace instance config
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.CKAN_INSTANCE,
                DadosGovBrConnector
            )
        except ImportError as e:
            logger.warning(f"Failed to register dados.gov.br connector: {e}")

        # Register Snowflake Data Marketplace connector
        try:
            from hub.apps.integrations.connectors.snowflake_connector import SnowflakeConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                SnowflakeConnector
            )
        except ImportError as e:
            logger.warning(f"Failed to register Snowflake connector: {e}")

        # Register AWS Data Exchange connector
        try:
            from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                AWSDataExchangeConnector
            )
        except ImportError as e:
            logger.warning(f"Failed to register AWS Data Exchange connector: {e}")

        # Register GCP Marketplace connector
        try:
            from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                GCPMarketplaceConnector
            )
        except ImportError as e:
            logger.warning(f"Failed to register GCP Marketplace connector: {e}")

        # Register Databricks Marketplace connector
        try:
            from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.DATABRICKS_MARKETPLACE,
                DatabricksConnector
            )
        except ImportError as e:
            logger.warning(f"Failed to register Databricks connector: {e}")

