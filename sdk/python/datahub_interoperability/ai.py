"""
AI operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class AIAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"query": query}
        if filters:
            data["filters"] = filters
        return await self.client.post("ai/search/", data=data)

    async def schema_matching(
        self,
        source_schema: dict[str, Any],
        target_schema: dict[str, Any],
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "source_schema": source_schema,
            "target_schema": target_schema,
        }
        return await self.client.post("ai/schema-matching/", data=data)
