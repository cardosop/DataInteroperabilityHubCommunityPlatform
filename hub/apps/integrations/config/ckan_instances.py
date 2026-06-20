"""
DEPRECATED: This module has been renamed to marketplace_instances.py

This file is kept for backward compatibility only. All new code should import from
hub.apps.integrations.config.marketplace_instances instead.

The configuration system now supports both CKAN-standard APIs and custom Swagger APIs.
dados.gov.br uses Swagger APIs (NOT CKAN), while demo.ckan.org and data.gov use CKAN APIs.

This module will be removed in a future version.
"""

import warnings

# Import everything from the new module
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

# Warn on import
warnings.warn(
    "hub.apps.integrations.config.ckan_instances is deprecated. "
    "Use hub.apps.integrations.config.marketplace_instances instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
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
