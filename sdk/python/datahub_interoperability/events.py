"""Event/Dead Letter Queue operations for DataHub SDK."""

from typing import Any, Dict

from .client import DataHubClient


class EventsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def replay(self, event_id: str) -> Dict[str, Any]:
        return await self.client.post(f"events/{event_id}/replay/")

    async def dlq_list(self) -> Dict[str, Any]:
        return await self.client.get("events/dlq/")

    async def dlq_retry(self, event_id: str) -> Dict[str, Any]:
        return await self.client.post(f"events/dlq/{event_id}/retry/")

    async def dlq_resolve(self, event_id: str) -> Dict[str, Any]:
        return await self.client.post(f"events/dlq/{event_id}/resolve/")
