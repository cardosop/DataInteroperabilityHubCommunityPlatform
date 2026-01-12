"""
Marketplace Connector Test Utilities Module

Provides centralized test utilities for marketplace connector tests (supports both CKAN and Swagger connectors).
"""
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    get_test_marketplace_config,
    create_test_connector,
    verify_marketplace_connection,
    marketplace_available,
    get_test_ckan_url,  # Backward compatibility
    get_test_api_key,   # Backward compatibility
    # Deprecated aliases (with warnings)
    get_test_ckan_config,
    verify_ckan_connection,
    ckan_available,
)

__all__ = [
    "get_test_marketplace_config",
    "create_test_connector",
    "verify_marketplace_connection",
    "marketplace_available",
    "get_test_ckan_url",
    "get_test_api_key",
    # Backward compatibility exports (deprecated)
    "get_test_ckan_config",
    "verify_ckan_connection",
    "ckan_available",
]

