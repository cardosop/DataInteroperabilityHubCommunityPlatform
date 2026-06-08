"""Developer portal and BaaS operations for DataHub SDK."""
from typing import Any, Dict, Optional
from .client import DataHubClient

class DeveloperAPI:
    def __init__(self, client: DataHubClient): self.client = client
    # Plugins
    async def list_plugins(self) -> Dict[str, Any]:
        return await self.client.get("developer/plugins/")
    async def create_plugin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("developer/plugins/", data=data)
    async def get_plugin(self, plugin_id: str) -> Dict[str, Any]:
        return await self.client.get(f"developer/plugins/{plugin_id}/")
    async def delete_plugin(self, plugin_id: str) -> None:
        await self.client.delete(f"developer/plugins/{plugin_id}/")
    # API Keys
    async def list_api_keys(self) -> Dict[str, Any]:
        return await self.client.get("developer/api-keys/")
    async def create_api_key(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("developer/api-keys/", data=data)
    async def revoke_api_key(self, key_id: str) -> None:
        await self.client.delete(f"developer/api-keys/{key_id}/")
    # SDK + Docs + Portal
    async def get_sdk(self) -> Dict[str, Any]:
        return await self.client.get("developer/sdk/")
    async def get_docs(self) -> Dict[str, Any]:
        return await self.client.get("developer/docs/")
    async def get_portal(self) -> Dict[str, Any]:
        return await self.client.get("developer/portal/")
    # Usage
    async def get_api_usage(self) -> Dict[str, Any]:
        return await self.client.get("developer/api-usage/")
