"""
Tests for hub.apps.integrations module exports.

Tests verify that CKANConnector and MarketplaceConnectorFactory
can be imported from the integrations module.
"""
import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)


class TestIntegrationsModuleExports(TestCase):
    """Test that integrations module exports are accessible"""

    def test_import_marketplace_connector_factory(self):
        """Test that MarketplaceConnectorFactory can be imported"""
        from hub.apps.integrations import MarketplaceConnectorFactory

        # Verify it's the correct class
        assert MarketplaceConnectorFactory is not None
        assert hasattr(MarketplaceConnectorFactory, 'register_connector')
        assert hasattr(MarketplaceConnectorFactory, 'get_connector')
        assert hasattr(MarketplaceConnectorFactory, 'create_connector')
        assert hasattr(MarketplaceConnectorFactory, 'is_supported')

    def test_import_ckan_connector(self):
        """Test that CKANConnector can be imported via lazy loading"""
        from hub.apps.integrations import CKANConnector

        # Verify it's the correct class
        assert CKANConnector is not None

        # Verify it has expected attributes
        from hub.apps.integrations.base import DataMarketplaceConnector
        assert issubclass(CKANConnector, DataMarketplaceConnector)

        # Verify it can be instantiated
        connector = CKANConnector(base_url='https://test.ckan.org')
        assert connector is not None
        assert connector.marketplace_type.value == 'CKAN_INSTANCE'

    def test_import_both_together(self):
        """Test importing both CKANConnector and MarketplaceConnectorFactory together"""
        from hub.apps.integrations import MarketplaceConnectorFactory, CKANConnector

        # Verify both are accessible
        assert MarketplaceConnectorFactory is not None
        assert CKANConnector is not None

        # Verify they work together
        connector = CKANConnector(base_url='https://test.ckan.org')
        assert connector.marketplace_type.value == 'CKAN_INSTANCE'

    def test_import_from_all(self):
        """Test that __all__ includes both exports"""
        import hub.apps.integrations as integrations_module

        # Check __all__ contains both
        assert 'MarketplaceConnectorFactory' in integrations_module.__all__
        assert 'CKANConnector' in integrations_module.__all__

        # Verify they can be accessed
        assert hasattr(integrations_module, 'MarketplaceConnectorFactory')
        assert hasattr(integrations_module, 'CKANConnector')

    def test_import_ckan_connector_lazy_loading(self):
        """Test that CKANConnector uses lazy loading (doesn't fail before Django ready)"""
        # This test verifies that the lazy import mechanism works
        # The import should succeed even though CKANConnector imports Django models
        from hub.apps.integrations import CKANConnector

        # Verify the class is accessible
        assert CKANConnector is not None

        # Verify it's the correct class by checking its module
        assert CKANConnector.__module__ == 'hub.apps.integrations.connectors.ckan_connector'

    def test_import_ckan_connector_multiple_times(self):
        """Test that importing CKANConnector multiple times returns the same class"""
        from hub.apps.integrations import CKANConnector as CKAN1
        from hub.apps.integrations import CKANConnector as CKAN2

        # Should be the same class object
        assert CKAN1 is CKAN2

    def test_import_with_factory_usage(self):
        """Test that imported classes work with factory"""
        from hub.apps.integrations import MarketplaceConnectorFactory, CKANConnector
        from hub.apps.integrations.base import MarketplaceType

        # Register CKAN connector if not already registered
        if not MarketplaceConnectorFactory.is_supported(MarketplaceType.CKAN_INSTANCE):
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.CKAN_INSTANCE,
                CKANConnector
            )

        # Verify factory can create connector using imported class
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.CKAN_INSTANCE,
            config={'endpoint': 'https://test.ckan.org'}
        )

        assert isinstance(connector, CKANConnector)
        assert connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

