"""
Asset operations for DataHub SDK.
"""
from typing import Any, Dict, List, Optional

from .client import DataHubClient


class AssetsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_assets(
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
        return await self.client.get("assets/", params=params)

    async def get_asset(
        self,
        asset_id: str,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if include:
            params["include"] = ",".join(include)
        return await self.client.get(f"assets/{asset_id}/", params=params)

    async def create_asset(
        self,
        name: str,
        key: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "name": name,
            "key": key,
            "visibility": visibility,
        }
        if description:
            data["description"] = description
        if domain:
            data["domain"] = domain
        return await self.client.post("assets/", data=data)

    async def update_asset(self, asset_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch(f"assets/{asset_id}/", data=kwargs)

    async def delete_asset(self, asset_id: str) -> None:
        await self.client.delete(f"assets/{asset_id}/")

    async def activate_asset(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.post(f"assets/{asset_id}/activate/")

    async def get_health_score(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/health-score/")

    async def get_recommendations(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/recommendations/")

    async def get_popularity(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"assets/{asset_id}/popularity/")

    async def classify_asset(
        self,
        asset_id: str,
        classification: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await self.client.post(f"assets/{asset_id}/classify/", data=classification)
