"""
Integrations App

Provides marketplace connector interfaces and implementations for integrating
with external data marketplaces.
"""

# Both MarketplaceConnectorFactory and CKANConnector are imported lazily
# to avoid Django app registry issues. They import from modules that depend
# on Django models (AssetSourceType from hub.apps.assets.models).

def __getattr__(name):
    """Lazy import for MarketplaceConnectorFactory and CKANConnector to avoid Django app registry issues"""
    if name == "MarketplaceConnectorFactory":
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        return MarketplaceConnectorFactory
    elif name == "CKANConnector":
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector
        return CKANConnector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "DataMarketplaceConnector",
    "MarketplaceType",
    "SyncDirection",
    "SyncStatus",
    "MarketplaceListing",
    "MarketplaceResource",
    "SyncResult",
    "MarketplaceAssetMapping",
    "MarketplaceConnectorFactory",
    "CKANConnector",
    "validate_marketplace_config",
    "normalize_marketplace_metadata",
    "parse_marketplace_datetime",
    "sanitize_marketplace_id",
    "MarketplaceError",
    "MarketplaceConnectionError",
    "MarketplaceAuthenticationError",
    "MarketplaceSyncError",
    "MarketplaceConnection",
    "MarketplaceSyncJob",
    "MarketplaceMapping",
]

