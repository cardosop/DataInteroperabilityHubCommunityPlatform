"""
Tenant operations for DataHub SDK (Phase 25).

Provides methods for tenant usage and configuration.
Uses real hub API - no mocks/stubs.
"""

from typing import Any, Dict

from .client import DataHubClient


class TenantsAPI:
    """
    Tenants API.

    Provides methods for tenant usage and configuration.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Tenants API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def get_usage(self) -> Dict[str, Any]:
        """
        Get current usage for tenant.

        Returns:
            Usage data with plan limits and usage percentages
        """
        return await self.client.get("tenants/me/usage/")
