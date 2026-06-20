"""Capability listing for DataHub SDK."""

from typing import Any, Dict

from .client import DataHubClient


class CapabilitiesAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_capabilities(self) -> Dict[str, Any]:
        return await self.client.get("capabilities/")
