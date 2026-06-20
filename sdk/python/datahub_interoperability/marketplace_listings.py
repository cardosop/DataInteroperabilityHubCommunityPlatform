"""
Marketplace listing operations for DataHub SDK.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class MarketplaceListingsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_listings(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if domain:
            params["domain"] = domain
        return await self.client.get("marketplace/listings/", params=params)

    async def get_listing(self, listing_id: str) -> Dict[str, Any]:
        return await self.client.get(f"marketplace/listings/{listing_id}/")

    async def create_listing(
        self,
        asset_id: str,
        pricing_model: str = "free",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "pricing_model": pricing_model,
        }
        if metadata:
            data["metadata"] = metadata
        return await self.client.post("marketplace/listings/", data=data)

    async def update_listing(self, listing_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch(f"marketplace/listings/{listing_id}/", data=kwargs)

    async def publish_listing(self, listing_id: str) -> Dict[str, Any]:
        return await self.client.post(f"marketplace/listings/{listing_id}/publish/")

    async def list_orders(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("marketplace/orders/", params=params)

    async def create_order(self, listing_id: str) -> Dict[str, Any]:
        return await self.client.post("marketplace/orders/", data={"listing_id": listing_id})

    async def approve_order(
        self,
        order_id: str,
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if comments:
            data["comments"] = comments
        return await self.client.post(f"marketplace/orders/{order_id}/approve/", data=data)

    async def reject_order(
        self,
        order_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if reason:
            data["reason"] = reason
        return await self.client.post(f"marketplace/orders/{order_id}/reject/", data=data)

    async def list_entitlements(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        return await self.client.get("marketplace/entitlements/", params=params)

    async def check_access(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(
            "marketplace/entitlements/check-access/", params={"asset_id": asset_id}
        )
