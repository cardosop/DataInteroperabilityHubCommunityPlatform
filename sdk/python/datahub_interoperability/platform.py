"""Platform admin operations — PLATFORM_ADMIN gated."""
from typing import Any, Dict, Optional
from .client import DataHubClient

class PlatformAPI:
    def __init__(self, client: DataHubClient): self.client = client
    # Tenant management (PLATFORM_ADMIN only)
    async def list_tenants(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get("platform/tenants/", params={"page": page, "page_size": page_size})
    async def create_tenant(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("platform/tenants/", data=data)
    async def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        return await self.client.get(f"platform/tenants/{tenant_id}/")
    async def update_tenant(self, tenant_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.patch(f"platform/tenants/{tenant_id}/", data=data)
    async def delete_tenant(self, tenant_id: str) -> None:
        await self.client.delete(f"platform/tenants/{tenant_id}/")
    # User management (PLATFORM_ADMIN only)
    async def list_users(self, page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        return await self.client.get("platform/users/", params={"page": page, "page_size": page_size})
    async def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("platform/users/", data=data)
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        return await self.client.get(f"platform/users/{user_id}/")
    async def update_user(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.patch(f"platform/users/{user_id}/", data=data)
