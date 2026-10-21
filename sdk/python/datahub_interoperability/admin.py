"""Admin operations — PLATFORM_ADMIN gated."""

from typing import Any

from .client import DataHubClient


class AdminAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_feature_flags(self, tenant_id: str) -> dict[str, Any]:
        return await self.client.get(f"admin/tenants/{tenant_id}/feature-flags/")

    async def update_feature_flags(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return await self.client.patch(f"admin/tenants/{tenant_id}/feature-flags/", data=data)

    async def impersonate(self, user_id: str) -> dict[str, Any]:
        return await self.client.post("admin/impersonate/", data={"user_id": user_id})

    async def dashboard_summary(self) -> dict[str, Any]:
        return await self.client.get("admin/dashboard-summary/")

    async def tenant_lifecycle(self, tenant_id: str, action: str) -> dict[str, Any]:
        return await self.client.post(
            f"admin/tenants/{tenant_id}/lifecycle/", data={"action": action}
        )
