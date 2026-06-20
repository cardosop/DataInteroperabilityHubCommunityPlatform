"""
Marketplace test fixtures for federated assets from demo.ckan.org.

Provides get_or_create_demo_ckan_federated_asset() for virtualization and
marketplace tests that need a pre-created federated asset from demo.ckan.org.
Uses real PULL from demo.ckan.org — no mocks or stubs.
"""

import logging

from django.db import transaction

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection
from hub.apps.integrations.services import MarketplaceIntegrationService

logger = logging.getLogger(__name__)

DEFAULT_LISTING_ID = "annakarenina"
DEFAULT_CONNECTION_NAME = "Demo CKAN E2E Connection"


def _get_demo_ckan_base_url() -> str:
    """Get demo.ckan.org base URL from marketplace instance config."""
    config = get_marketplace_instance_config("demo.ckan.org")
    if config:
        return config.base_url.rstrip("/")
    return "https://demo.ckan.org"


def get_or_create_demo_ckan_federated_asset(
    tenant,
    user,
    listing_id: str = DEFAULT_LISTING_ID,
    connection_name: str = DEFAULT_CONNECTION_NAME,
) -> tuple[Asset, MarketplaceConnection]:
    """
    Get or create a federated asset from demo.ckan.org for the given tenant/user.

    If an asset with source_metadata.listing_id matching listing_id already exists
    for this tenant, returns it. Otherwise PULLs from demo.ckan.org and creates
    a new federated asset synchronously (no workflow).

    Args:
        tenant: Tenant model instance
        user: User model instance
        listing_id: CKAN package ID (default: annakarenina)
        connection_name: Marketplace connection name (default: Demo CKAN E2E Connection)

    Returns:
        Tuple of (Asset, MarketplaceConnection)

    Raises:
        Exception: If demo.ckan.org is unreachable or listing not found
    """
    # Try to find existing asset for this tenant + listing_id
    existing = Asset.objects.filter(
        tenant=tenant,
        source_type=AssetSourceType.FEDERATED,
        source_metadata__listing_id=listing_id,
    ).first()

    if existing:
        connection = MarketplaceConnection.objects.filter(
            tenant=tenant,
            name=connection_name,
        ).first()
        if connection:
            base_url = _get_demo_ckan_base_url()
            cfg = connection.get_config() if connection.config else {}
            if cfg.get("base_url") != base_url:
                connection.set_config({"base_url": base_url})
                connection.is_active = True
                connection.save(update_fields=["config", "is_active"])
            return (existing, connection)
        # Asset exists but connection may have different name; create connection for consistency
        base_url = _get_demo_ckan_base_url()
        connection, _ = MarketplaceConnection.objects.get_or_create(
            tenant=tenant,
            name=connection_name,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            defaults={
                "config": {"base_url": base_url},
                "is_active": True,
            },
        )
        return (existing, connection)

    # Create new federated asset via PULL from demo.ckan.org
    base_url = _get_demo_ckan_base_url()
    connector = MarketplaceConnectorFactory.create_connector(
        MarketplaceType.CKAN_INSTANCE,
        config={"base_url": base_url},
    )
    listing = connector.get_listing(listing_id)
    mapping = connector.map_to_hub_asset(listing)

    with transaction.atomic():
        connection, created = MarketplaceConnection.objects.get_or_create(
            tenant=tenant,
            name=connection_name,
            marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
            defaults={
                "config": {"base_url": base_url},
                "is_active": True,
            },
        )
        if not created:
            connection.set_config({"base_url": base_url})
            connection.is_active = True
            connection.save(update_fields=["config", "is_active"])

    service = MarketplaceIntegrationService(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
    )
    asset = service.create_federated_asset_with_contracts(
        asset_mapping=mapping,
        connection=connection,
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        data_strategy="METADATA_ONLY",
    )

    return (asset, connection)
