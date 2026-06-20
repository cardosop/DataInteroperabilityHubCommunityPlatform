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

    async def list_tenants(
        self,
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """
        List tenants accessible to the current user.

        Args:
            page: Page number (1-indexed).
            page_size: Items per page.

        Returns:
            Paginated tenant list.
        """
        return await self.client.get("tenants/", params={"page": page, "page_size": page_size})
