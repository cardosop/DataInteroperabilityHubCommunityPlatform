"""
Billing operations for DataHub SDK (Phase 25).

Provides methods for managing subscriptions and invoices.
Uses real hub API - no mocks/stubs.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class BillingAPI:
    """
    Billing API.

    Provides methods for subscription and invoice management.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Billing API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def get_subscription(self) -> Dict[str, Any]:
        """
        Get current subscription for tenant.

        Returns:
            Subscription data
        """
        return await self.client.get("billing/subscription/current/")

    async def list_invoices(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List invoices for tenant.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with invoices
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get("billing/invoices/", params=params)

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Get invoice by ID.

        Args:
            invoice_id: Invoice UUID

        Returns:
            Invoice data
        """
        return await self.client.get(f"billing/invoices/{invoice_id}/")
