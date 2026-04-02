"""
AI operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class AIAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"query": query}
        if filters:
            data["filters"] = filters
        return await self.client.post("ai/search/", data=data)

    async def schema_matching(
        self,
        source_schema: Dict[str, Any],
        target_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "source_schema": source_schema,
            "target_schema": target_schema,
        }
        return await self.client.post("ai/schema-matching/", data=data)
