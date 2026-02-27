"""
Azure Marketplace (Commercial Marketplace) connector.

Implements DataMarketplaceConnector for the Azure Marketplace Catalog API.
Supports discovery (list products, get product) and harvest (sync_pull).
Uses real HTTP; config: base_url, api_key (X-API-Key), api_version.

API: https://learn.microsoft.com/en-us/rest/api/marketplacecatalog/dataplane/
Auth: X-API-Key header (https://aka.ms/DiscoveryAPI/keys)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from hub.apps.assets.models import AssetSourceType
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
from hub.apps.core.services.base import ConnectionError, NotFoundError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://catalogapi.azure.com"
DEFAULT_API_VERSION = "2025-05-01"


class AzureMarketplaceConnector(DataMarketplaceConnector):
    """
    Connector for Azure Commercial Marketplace (Catalog API).

    Harvest-only (PULL). Discovery via List Products / Get Product.
    Push operations (create_listing, update_listing, publish_resource, sync_push)
    are not supported; use Partner Center for publishing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize Azure Marketplace connector.

        Args:
            base_url: Catalog API base URL (default: https://catalogapi.azure.com).
            api_key: X-API-Key for Catalog API (required for real API).
            api_version: API version query param (default: 2025-05-01).
            config: Optional dict; if provided, base_url/api_key/api_version
                are taken from config if not passed as kwargs.
        """
        if config:
            base_url = base_url or config.get("base_url")
            api_key = api_key or config.get("api_key")
            api_version = api_version or config.get("api_version")
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = api_key or ""
        self._api_version = api_version or DEFAULT_API_VERSION
        self._timeout = 30
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {"Accept": "application/json"}
            if self._api_key:
                headers["X-API-Key"] = self._api_key
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=headers,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as e:
                logger.warning("Error closing Azure Marketplace client: %s", e)
            self._client = None

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.AZURE_MARKETPLACE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        if not credentials:
            raise ValueError("Credentials dictionary is required")
        api_key = credentials.get("api_key") or credentials.get("X-API-Key")
        if not api_key:
            raise ValueError("api_key or X-API-Key is required")
        self._api_key = api_key
        if self._client is not None:
            self._client.close()
            self._client = None
        return self.test_connection()

    def test_connection(self) -> bool:
        try:
            client = self._get_client()
            r = client.get(
                f"/products",
                params={"api-version": self._api_version, "$top": 1},
            )
            if r.status_code == 401:
                raise ConnectionError("Azure Marketplace API key invalid or missing")
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Azure Marketplace connection failed: {e.response.status_code} {e}"
            ) from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Azure Marketplace connection failed: {e}") from e

    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[MarketplaceListing]:
        filters = filters or {}
        params: Dict[str, Any] = {"api-version": self._api_version}
        if limit is not None and limit > 0:
            params["$top"] = min(limit, 100)
        if offset is not None and offset > 0:
            params["$skip"] = offset
        for k, v in filters.items():
            if k.startswith("$"):
                params[k] = v
            elif k == "productType":
                params["$filter"] = f"productType eq '{v}'"
            elif k == "search":
                params["$search"] = v
        try:
            client = self._get_client()
            r = client.get("/products", params=params)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise ConnectionError(
                f"Azure Marketplace list products failed: {e}"
            ) from e
        except httpx.RequestError as e:
            raise ConnectionError(f"Azure Marketplace list products failed: {e}") from e

        value = data.get("value") or []
        listings: List[MarketplaceListing] = []
        for p in value:
            try:
                listings.append(self._product_to_listing(p))
            except Exception as e:
                logger.warning("Skip product %s: %s", p.get("uniqueProductId"), e)
        return listings

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        if not (listing_id and isinstance(listing_id, str)):
            raise ValueError("listing_id must be a non-empty string")
        encoded_id = quote(str(listing_id), safe="")
        try:
            client = self._get_client()
            r = client.get(
                f"/products/{encoded_id}",
                params={"api-version": self._api_version},
            )
            if r.status_code == 404:
                raise NotFoundError(f"Product not found: {listing_id}")
            r.raise_for_status()
            p = r.json()
            return self._product_to_listing(p)
        except NotFoundError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Product not found: {listing_id}") from e
            raise ConnectionError(
                f"Azure Marketplace get product failed: {e}"
            ) from e
        except httpx.RequestError as e:
            raise ConnectionError(
                f"Azure Marketplace get product failed: {e}"
            ) from e

    def _product_to_listing(self, p: Dict[str, Any]) -> MarketplaceListing:
        uid = p.get("uniqueProductId") or p.get("productId") or ""
        if not uid:
            raise ValueError("Product missing uniqueProductId/productId")
        title = p.get("displayName") or p.get("summary") or uid
        desc = p.get("description") or p.get("longSummary") or p.get("summary") or ""
        modified = p.get("lastModifiedDateTime")
        try:
            updated_at = (
                datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if modified
                else None
            )
        except Exception:
            updated_at = None
        plans = p.get("plans") or []
        resources: List[MarketplaceResource] = []
        for i, plan in enumerate(plans):
            if not isinstance(plan, dict):
                continue
            plan_id = plan.get("planId") or plan.get("uniquePlanId") or str(i)
            resources.append(
                MarketplaceResource(
                    resource_id=f"{uid}/{plan_id}",
                    resource_type="PLAN",
                    name=plan.get("displayName") or plan_id,
                    description=plan.get("description") or plan.get("summary"),
                    metadata={"plan": plan},
                )
            )
        return MarketplaceListing(
            marketplace_id=str(uid),
            marketplace_type=MarketplaceType.AZURE_MARKETPLACE,
            title=str(title),
            description=str(desc)[:5000] if desc else None,
            product_id=str(p.get("productId", "") or uid),
            category=p.get("productFamily") or p.get("serviceFamily"),
            tags=list(p.get("categoryIds") or []) + list(p.get("industryIds") or []),
            metadata={
                "publisherId": p.get("publisherId"),
                "publisherDisplayName": p.get("publisherDisplayName"),
                "productType": p.get("productType"),
                "pricingTypes": p.get("pricingTypes"),
                "startingPrice": p.get("startingPrice"),
                "plans": plans,
            },
            resources=resources,
            created_at=None,
            updated_at=updated_at,
            url=f"https://azuremarketplace.microsoft.com/en-us/marketplace/apps/{uid}"
            if uid
            else None,
        )

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        listing = self.get_listing(listing_id)
        resources: List[MarketplaceResource] = []
        plans = (listing.metadata or {}).get("plans") or []
        for i, plan in enumerate(plans):
            if not isinstance(plan, dict):
                continue
            plan_id = plan.get("planId") or plan.get("uniquePlanId") or str(i)
            resources.append(
                MarketplaceResource(
                    resource_id=f"{listing_id}/{plan_id}",
                    resource_type="PLAN",
                    name=plan.get("displayName") or plan_id,
                    description=plan.get("description") or plan.get("summary"),
                    metadata={"plan": plan},
                )
            )
        return resources

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        raise NotImplementedError(
            "Azure Marketplace connector does not support push (create_listing); "
            "use Partner Center to publish."
        )

    def update_listing(
        self, listing_id: str, listing: MarketplaceListing
    ) -> MarketplaceListing:
        raise NotImplementedError(
            "Azure Marketplace connector does not support push (update_listing); "
            "use Partner Center to update."
        )

    def publish_resource(
        self, listing_id: str, resource: MarketplaceResource
    ) -> MarketplaceResource:
        raise NotImplementedError(
            "Azure Marketplace connector does not support push (publish_resource); "
            "use Partner Center to publish."
        )

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        raise NotImplementedError(
            "Azure Marketplace connector does not support download_resource; "
            "resource access is via Azure portal or Partner Center."
        )

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None,
    ) -> MarketplaceAssetMapping:
        from django.utils import timezone

        source_metadata: Dict[str, Any] = {
            "marketplace_type": MarketplaceType.AZURE_MARKETPLACE.value,
            "marketplace_id": listing.marketplace_id,
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url,
            "synced_at": timezone.now().isoformat(),
        }
        if sync_job_id:
            source_metadata["sync_job_id"] = sync_job_id

        odps_metadata: Optional[Dict[str, Any]] = None
        if listing.metadata:
            sp = listing.metadata.get("startingPrice")
            if isinstance(sp, dict):
                odps_metadata = {
                    "pricing_plans": [
                        {
                            "name": "default",
                            "currency": sp.get("currency", "USD"),
                            "price": sp.get("minTermPrice") or sp.get("minMeterPrice"),
                        }
                    ],
                    "access_methods": {},
                    "payment_gateways": {},
                }

        resources: List[MarketplaceResource] = []
        for res in listing.resources:
            resources.append(
                MarketplaceResource(
                    resource_id=res.resource_id,
                    resource_type=res.resource_type,
                    name=res.name,
                    description=res.description,
                    url=res.url,
                    format=res.format,
                    size_bytes=res.size_bytes,
                    metadata={**(res.metadata or {}), "external": True},
                )
            )

        return MarketplaceAssetMapping(
            asset_data={
                "name": listing.title,
                "description": listing.description or "",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata,
            odcs_metadata=None,
            resources=resources,
        )

    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None,
    ) -> MarketplaceListing:
        raise NotImplementedError(
            "Azure Marketplace connector does not support push (map_from_hub_asset); "
            "use Partner Center to publish."
        )

    def sync_push(
        self,
        asset_ids: List[str],
        options: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        raise NotImplementedError(
            "Azure Marketplace connector does not support push (sync_push); "
            "use Partner Center to publish."
        )

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        from django.utils import timezone

        started_at = timezone.now()
        options = options or {}
        limit = options.get("limit")
        mappings: List[MarketplaceAssetMapping] = []
        errors: List[str] = []

        try:
            if listing_ids:
                for lid in listing_ids:
                    try:
                        listing = self.get_listing(lid)
                        mapping = self.map_to_hub_asset(
                            listing,
                            sync_job_id=options.get("sync_job_id"),
                        )
                        mappings.append(mapping)
                    except Exception as e:
                        errors.append(f"{lid}: {e}")
            else:
                listings = self.list_listings(
                    filters=filters, limit=limit, offset=options.get("offset")
                )
                for listing in listings:
                    try:
                        mapping = self.map_to_hub_asset(
                            listing,
                            sync_job_id=options.get("sync_job_id"),
                        )
                        mappings.append(mapping)
                    except Exception as e:
                        errors.append(f"{listing.marketplace_id}: {e}")

            completed_at = timezone.now()
            failed_count = len(errors)
            successful_count = len(mappings)
            status = (
                SyncStatus.FAILED
                if failed_count and not successful_count
                else SyncStatus.PARTIAL
                if failed_count
                else SyncStatus.COMPLETED
            )
            return SyncResult(
                status=status,
                total_items=successful_count + failed_count,
                successful_items=successful_count,
                failed_items=failed_count,
                skipped_items=0,
                errors=errors,
                metadata={
                    "mappings": [
                        {
                            "asset_data": m.asset_data,
                            "source_type": m.source_type.value,
                            "source_metadata": m.source_metadata,
                            "odps_metadata": m.odps_metadata,
                            "odcs_metadata": m.odcs_metadata,
                            "resources": [
                                {
                                    "resource_id": r.resource_id,
                                    "resource_type": r.resource_type,
                                    "name": r.name,
                                    "description": r.description,
                                    "url": r.url,
                                    "format": r.format,
                                    "size_bytes": r.size_bytes,
                                    "metadata": r.metadata or {},
                                }
                                for r in m.resources
                            ],
                        }
                        for m in mappings
                    ],
                },
                started_at=started_at,
                completed_at=completed_at,
            )
        except Exception as e:
            logger.exception("Azure sync_pull failed: %s", e)
            return SyncResult(
                status=SyncStatus.FAILED,
                total_items=0,
                successful_items=0,
                failed_items=1,
                skipped_items=0,
                errors=[str(e)],
                metadata={"mappings": []},
                started_at=started_at,
                completed_at=timezone.now(),
            )
