"""
Social operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class SocialAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_ratings(self, asset_id: str) -> dict[str, Any]:
        return await self.client.get("social/ratings/", params={"asset_id": asset_id})

    async def create_rating(
        self,
        asset_id: str,
        score: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"asset_id": asset_id, "score": score}
        if comment:
            data["comment"] = comment
        return await self.client.post("social/ratings/", data=data)

    async def list_reviews(self, asset_id: str) -> dict[str, Any]:
        return await self.client.get("social/reviews/", params={"asset_id": asset_id})

    async def create_review(
        self,
        asset_id: str,
        title: str,
        body: str,
        rating: int,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "asset_id": asset_id,
            "title": title,
            "body": body,
            "rating": rating,
        }
        return await self.client.post("social/reviews/", data=data)

    async def list_comments(
        self,
        resource_type: str,
        resource_id: str,
    ) -> dict[str, Any]:
        return await self.client.get(
            "social/comments/",
            params={"resource_type": resource_type, "resource_id": resource_id},
        )

    async def create_comment(
        self,
        resource_type: str,
        resource_id: str,
        body: str,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "body": body,
        }
        return await self.client.post("social/comments/", data=data)

    async def list_communities(self) -> dict[str, Any]:
        return await self.client.get("social/communities/")

    async def get_community(self, community_id: str) -> dict[str, Any]:
        return await self.client.get(f"social/communities/{community_id}/")
