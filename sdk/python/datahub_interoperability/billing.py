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
        return await self.client.get(f"billing/invoices/{invoice_id}/")

    # ── 118F.16: Expanded billing methods ────────────────

    async def list_plans(self, **kwargs) -> Dict[str, Any]:
        return await self.client.get("billing/plans/", params=kwargs or None)

    async def get_plan(self, plan_id: str) -> Dict[str, Any]:
        return await self.client.get(f"billing/plans/{plan_id}/")

    async def change_plan(self, plan_slug: str) -> Dict[str, Any]:
        return await self.client.post(
            "billing/subscription/current/change-plan/",
            data={"plan_slug": plan_slug},
        )

    async def get_ml_subscription(self) -> Dict[str, Any]:
        return await self.client.get("billing/subscription/ml/current/")

    async def change_ml_plan(self, plan_slug: str) -> Dict[str, Any]:
        return await self.client.post(
            "billing/subscription/ml/current/change-plan/",
            data={"plan_slug": plan_slug},
        )

    async def get_plan_limits(self) -> Dict[str, Any]:
        data = await self.client.get("billing/subscription/current/")
        return data.get("limits", {})

    async def get_usage(
        self,
        metric_key: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if metric_key:
            params["metric_key"] = metric_key
        return await self.client.get("billing/usage/", params=params)

    async def process_refund(
        self,
        payment_intent_id: str,
        amount_cents: int,
        reason: str,
    ) -> Dict[str, Any]:
        return await self.client.post(
            "billing/refunds/",
            data={
                "payment_intent_id": payment_intent_id,
                "amount_cents": amount_cents,
                "reason": reason,
            },
        )

    async def trigger_reconciliation(
        self,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return await self.client.post(
            "billing/admin/reconcile/",
            data={"dry_run": dry_run},
        )
