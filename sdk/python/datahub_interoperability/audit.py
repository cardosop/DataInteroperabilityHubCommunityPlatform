"""
Audit operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class AuditAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_events(
        self,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if resource_type:
            params["resource_type"] = resource_type
        if action:
            params["action"] = action
        return await self.client.get("audit/events/", params=params)

    async def get_event(self, event_id: str) -> Dict[str, Any]:
        return await self.client.get(f"audit/events/{event_id}/")

    async def export_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        format: str = "json",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"format": format}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self.client.get("audit/events/export/", params=params)
