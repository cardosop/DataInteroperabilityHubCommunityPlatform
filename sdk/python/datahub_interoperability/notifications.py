"""Notification operations for DataHub SDK."""
from typing import Any, Dict, Optional
from .client import DataHubClient

class NotificationAPI:
    def __init__(self, client: DataHubClient): self.client = client
    async def list_notifications(self, page: int = 1, page_size: int = 25, category: Optional[str] = None) -> Dict[str, Any]:
        params = {"page": page, "page_size": page_size}
        if category: params["category"] = category
        return await self.client.get("notifications/", params=params)
    async def get_notification(self, notification_id: str) -> Dict[str, Any]:
        return await self.client.get(f"notifications/{notification_id}/")
    async def unread_count(self) -> Dict[str, Any]:
        return await self.client.get("notifications/unread-count/")
    async def mark_read(self, notification_id: str) -> Dict[str, Any]:
        return await self.client.post(f"notifications/{notification_id}/mark-read/")
    async def mark_all_read(self) -> Dict[str, Any]:
        return await self.client.post("notifications/mark-all-read/")
