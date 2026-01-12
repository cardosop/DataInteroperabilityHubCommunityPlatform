"""
Marketplace Instance Configuration Module

Provides configuration management for marketplace connector instances.
Supports both CKAN-standard APIs and custom Swagger APIs.
"""
from hub.apps.integrations.config.marketplace_instances import (
    MarketplaceInstanceConfig,
    get_marketplace_instance_config,
    get_default_test_instance,
    MARKETPLACE_INSTANCES,
    # Backward compatibility aliases (deprecated)
    CKANInstanceConfig,
    get_ckan_instance_config,
    CKAN_INSTANCES,
)

__all__ = [
    "MarketplaceInstanceConfig",
    "get_marketplace_instance_config",
    "get_default_test_instance",
    "MARKETPLACE_INSTANCES",
    # Backward compatibility exports (deprecated)
    "CKANInstanceConfig",
    "get_ckan_instance_config",
    "CKAN_INSTANCES",
]

