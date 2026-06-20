"""
In-Memory Marketplace Connector (documented fake for tests).

Implements the DataMarketplaceConnector interface with in-memory storage.
Used in tests to exercise federated asset and virtualization code paths
without mocks or external services. No mocks in critical path: this is a
real implementation of the connector interface.

Config shape:
    {"resources": {<resource_id: str>: <content: bytes or str>}}

- download_resource(resource_id, destination_path) writes the preloaded
  content to the file and returns the path. Content can be bytes or str
  (str is encoded as utf-8).
- All other methods return minimal/empty results and do not perform I/O.

Usage in tests:
    - Create MarketplaceConnection with marketplace_type=IN_MEMORY_FAKE and
      config={"resources": {"res-123": b"id,name\\n1,Alice\\n2,Bob"}}
    - Create federated Asset with ExternalResourceReference pointing to
      that connection.
    - Asset.download_external_resource("res-123") will use this connector
      and return the file path and content without any mock.
"""

import os
from typing import Any

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)


class InMemoryMarketplaceConnector(DataMarketplaceConnector):
    """
    In-memory implementation of DataMarketplaceConnector for testing.

    Implements the full connector interface. download_resource() writes preloaded
    content from config["resources"][resource_id] to destination_path. Other methods
    return minimal/empty results. No network or external I/O.
    """

    def __init__(self, config: dict[str, Any] | None = None, **kwargs):
        """
        Initialize with optional config.

        Args:
            config: Optional dict with "resources" key mapping resource_id to content
                (bytes or str).         Example: {"resources": {"res-1": b"csv,data\\n1,2"}}
        """
        self._config = config or {}
        self._resources: dict[str, bytes] = {}
        raw = self._config.get("resources") or {}
        for rid, content in raw.items():
            if isinstance(content, str):
                self._resources[str(rid)] = content.encode("utf-8")
            else:
                self._resources[str(rid)] = bytes(content) if content is not None else b""

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.IN_MEMORY_FAKE

    @property
    def supported_sync_directions(self) -> list[SyncDirection]:
        return [SyncDirection.PULL]

    def authenticate(self, credentials: dict[str, Any]) -> bool:
        return True

    def test_connection(self) -> bool:
        return True

    def list_listings(
        self,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[MarketplaceListing]:
        return []

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        raise NotFoundError("Listing not found: %s" % listing_id)

    def list_resources(self, listing_id: str) -> list[MarketplaceResource]:
        return []

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        return listing

    def update_listing(self, listing_id: str, listing: MarketplaceListing) -> MarketplaceListing:
        return listing

    def publish_resource(
        self, listing_id: str, resource: MarketplaceResource
    ) -> MarketplaceResource:
        return resource

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """
        Write preloaded content for resource_id to destination_path.

        Content is taken from config["resources"][resource_id] set at init.
        Raises NotFoundError if resource_id is not in config.
        """
        if resource_id not in self._resources:
            avail = list(self._resources.keys())
            raise NotFoundError("Resource not found: %s. Available: %s" % (resource_id, avail))
        content = self._resources[resource_id]
        dir_path = os.path.dirname(destination_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(destination_path, "wb") as f:
            f.write(content)
        return destination_path

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: str | None = None,
    ) -> MarketplaceAssetMapping:
        title = listing.title or "in-memory"
        return MarketplaceAssetMapping(
            asset_data={
                "name": title,
                "description": listing.description or "",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": MarketplaceType.IN_MEMORY_FAKE.value,
                "listing_id": listing.marketplace_id,
            },
            odps_metadata={
                "product": {
                    "productID": listing.marketplace_id or "in-memory",
                    "product_name": title,
                    "details": {"en": {"name": title}},
                },
            },
            odcs_metadata={
                "kind": "DataContract",
                "name": title,
            },
            resources=[],
        )

    def map_from_hub_asset(
        self,
        asset_data: dict[str, Any],
        odps_metadata: dict[str, Any] | None = None,
        odcs_metadata: dict[str, Any] | None = None,
    ) -> MarketplaceListing:
        return MarketplaceListing(
            marketplace_id="",
            marketplace_type=MarketplaceType.IN_MEMORY_FAKE,
            title=asset_data.get("name", "in-memory"),
            description=asset_data.get("description", ""),
        )

    def sync_push(
        self,
        asset_ids: list[str],
        options: dict[str, Any] | None = None,
    ) -> SyncResult:
        return SyncResult(
            status=SyncStatus.COMPLETED,
            total_items=0,
            successful_items=0,
            failed_items=0,
            skipped_items=0,
        )

    def sync_pull(
        self,
        listing_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> SyncResult:
        return SyncResult(
            status=SyncStatus.COMPLETED,
            total_items=0,
            successful_items=0,
            failed_items=0,
            skipped_items=0,
            metadata={"mappings": []},
        )
