"""
DEPRECATED: This module has been renamed to marketplace_test_helpers.py

This file is kept for backward compatibility only. All new code should import from
hub.apps.integrations.tests.utils.marketplace_test_helpers instead.

The test utilities now support both CKAN-standard APIs and custom Swagger APIs.
dados.gov.br uses Swagger APIs (NOT CKAN), while demo.ckan.org and data.gov use CKAN APIs.

This module will be removed in a future version.
"""

import warnings

# Import everything from the new module
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    ckan_available,
    create_test_connector,
    get_test_api_key,
    # Deprecated aliases (with warnings)
    get_test_ckan_config,
    get_test_ckan_url,
    get_test_marketplace_config,
    marketplace_available,
    verify_ckan_connection,
    verify_marketplace_connection,
)

# Warn on import
warnings.warn(
    "hub.apps.integrations.tests.utils.ckan_test_helpers is deprecated. "
    "Use hub.apps.integrations.tests.utils.marketplace_test_helpers instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
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
