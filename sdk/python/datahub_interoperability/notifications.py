"""Notification operations for DataHub SDK."""

from typing import Any

from .client import DataHubClient


class NotificationAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_notifications(
        self, page: int = 1, page_size: int = 25, category: str | None = None
    ) -> dict[str, Any]:
        params = {"page": page, "page_size": page_size}
        if category:
            params["category"] = category
        # The canonical list endpoint is the user-notifications ViewSet
        # (hub/apps/notifications/urls.py).  "notifications/" is the DRF
        # router INDEX (a URL map), which this method hit before — a real
        # SDK bug pinned by the CLI↔SDK consistency suite.
        return await self.client.get("notifications/user-notifications/", params=params)

    async def get_notification(self, notification_id: str) -> dict[str, Any]:
        return await self.client.get(f"notifications/user-notifications/{notification_id}/")

    async def unread_count(self) -> dict[str, Any]:
        return await self.client.get("notifications/user-notifications/unread-count/")

    async def mark_read(self, notification_id: str) -> dict[str, Any]:
        return await self.client.post(f"notifications/user-notifications/{notification_id}/read/")

    async def mark_all_read(self) -> dict[str, Any]:
        return await self.client.post("notifications/user-notifications/read-all/")
