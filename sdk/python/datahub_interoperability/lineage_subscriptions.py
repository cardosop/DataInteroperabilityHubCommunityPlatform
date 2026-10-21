"""Lineage subscription operations — capability-gated."""

from typing import Any

from .client import DataHubClient


class LineageSubscriptionsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_subscriptions(self) -> dict[str, Any]:
        return await self.client.get("lineage-subscriptions/")

    async def create_subscription(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.client.post("lineage-subscriptions/", data=data)

    async def get_subscription(self, sub_id: str) -> dict[str, Any]:
        return await self.client.get(f"lineage-subscriptions/{sub_id}/")

    async def update_subscription(self, sub_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.client.patch(f"lineage-subscriptions/{sub_id}/", data=data)

    async def delete_subscription(self, sub_id: str) -> None:
        await self.client.delete(f"lineage-subscriptions/{sub_id}/")
