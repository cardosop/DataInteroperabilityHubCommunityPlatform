"""Developer portal and BaaS operations for DataHub SDK."""

from typing import Any

from .client import DataHubClient
from .scopes import validate_scopes


class DeveloperAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    # Plugins
    async def list_plugins(self) -> dict[str, Any]:
        return await self.client.get("developer/plugins/")

    async def create_plugin(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self.client.post("developer/plugins/", data=data)

    async def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        return await self.client.get(f"developer/plugins/{plugin_id}/")

    async def delete_plugin(self, plugin_id: str) -> None:
        await self.client.delete(f"developer/plugins/{plugin_id}/")

    # API Keys
    async def list_api_keys(self) -> dict[str, Any]:
        return await self.client.get("developer/api-keys/")

    async def create_api_key(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an API key.  When ``data["scopes"]`` is present it is
        validated against the W6.5 scope vocabulary BEFORE the request —
        a typo'd or unmintable scope fails fast with a clear ValueError
        instead of a round-trip 400 (the backend still enforces the
        role allowlist — R2-B2)."""
        scopes = data.get("scopes")
        if scopes is not None:
            invalid = validate_scopes(list(scopes))
            if invalid:
                raise ValueError(
                    f"Invalid API-key scopes: {', '.join(invalid)}. "
                    "Valid scopes are documented in "
                    "datahub_interoperability.scopes (ALL_SCOPES); "
                    "'*' is PLATFORM_ADMIN-only and "
                    "'scheduled_ingestion:internal' is never mintable."
                )
        return await self.client.post("developer/api-keys/", data=data)

    async def revoke_api_key(self, key_id: str) -> None:
        await self.client.delete(f"developer/api-keys/{key_id}/")

    # SDK + Docs + Portal
    async def get_sdk(self) -> dict[str, Any]:
        return await self.client.get("developer/sdk/")

    async def get_docs(self) -> dict[str, Any]:
        return await self.client.get("developer/docs/")

    async def get_portal(self) -> dict[str, Any]:
        return await self.client.get("developer/portal/")

    # Usage
    async def get_api_usage(self) -> dict[str, Any]:
        return await self.client.get("developer/api-usage/")
