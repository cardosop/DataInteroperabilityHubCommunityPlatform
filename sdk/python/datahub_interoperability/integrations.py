"""Integration operations for DataHub SDK."""

from typing import Any, Dict

from .client import DataHubClient


class IntegrationsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    # Connections
    async def list_connections(self) -> Dict[str, Any]:
        return await self.client.get("integrations/connections/")

    async def create_connection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.post("integrations/connections/", data=data)

    async def get_connection(self, conn_id: str) -> Dict[str, Any]:
        return await self.client.get(f"integrations/connections/{conn_id}/")

    async def update_connection(self, conn_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.patch(f"integrations/connections/{conn_id}/", data=data)

    async def delete_connection(self, conn_id: str) -> None:
        await self.client.delete(f"integrations/connections/{conn_id}/")

    # Sync jobs
    async def list_sync_jobs(self) -> Dict[str, Any]:
        return await self.client.get("integrations/sync-jobs/")

    # Mappings
    async def list_mappings(self) -> Dict[str, Any]:
        return await self.client.get("integrations/mappings/")

    # Marketplace connectors
    async def list_marketplace_connectors(self) -> Dict[str, Any]:
        return await self.client.get("integrations/marketplace-connectors/")

    async def get_marketplace_connector(self, connector_id: str) -> Dict[str, Any]:
        return await self.client.get(f"integrations/marketplace-connectors/{connector_id}/")
