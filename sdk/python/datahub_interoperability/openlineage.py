"""OpenLineage operations — capability-gated."""

from typing import Any, Dict

from .client import DataHubClient


class OpenLineageAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_keys(self) -> Dict[str, Any]:
        return await self.client.get("openlineage/keys/")

    async def create_key(self, name: str) -> Dict[str, Any]:
        return await self.client.post("openlineage/keys/", data={"name": name})

    async def revoke_key(self, key_id: str) -> None:
        await self.client.delete(f"openlineage/keys/{key_id}/")

    async def status(self) -> Dict[str, Any]:
        return await self.client.get("openlineage/status/")
