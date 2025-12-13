"""
Webhook operations for DataHub SDK.

Provides methods for managing webhook subscriptions, delivery history, and testing.
"""

from typing import Any, Dict, List, Optional

from .client import DataHubClient


class WebhooksAPI:
    """
    Webhooks API.

    Provides methods for managing webhook subscriptions and deliveries.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Webhooks API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def create(
        self,
        url: str,
        event_types: List[str],
        secret: Optional[str] = None,
        active: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create webhook subscription.

        Args:
            url: Webhook URL
            event_types: List of event types to subscribe to
            secret: Webhook secret for HMAC signature (optional)
            active: Whether webhook is active (default: True)
            **kwargs: Additional webhook parameters

        Returns:
            Created webhook subscription
        """
        data: Dict[str, Any] = {
            "url": url,
            "event_types": event_types,
            "active": active,
        }
        if secret:
            data["secret"] = secret
        data.update(kwargs)

        return await self.client.post("webhooks/webhooks/", data=data)

    async def list(
        self,
        active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List webhook subscriptions.

        Args:
            active: Filter by active status (optional)
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with webhooks
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if active is not None:
            params["active"] = active

        return await self.client.get("webhooks/webhooks/", params=params)

    async def get(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get webhook subscription by ID.

        Args:
            webhook_id: Webhook UUID

        Returns:
            Webhook subscription data
        """
        return await self.client.get(f"webhooks/webhooks/{webhook_id}/")

    async def update(
        self,
        webhook_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update webhook subscription.

        Args:
            webhook_id: Webhook UUID
            **kwargs: Fields to update

        Returns:
            Updated webhook subscription
        """
        return await self.client.patch(f"webhooks/webhooks/{webhook_id}/", data=kwargs)

    async def delete(self, webhook_id: str) -> None:
        """
        Delete webhook subscription.

        Args:
            webhook_id: Webhook UUID
        """
        await self.client.delete(f"webhooks/webhooks/{webhook_id}/")

    async def get_delivery_history(
        self,
        webhook_id: str,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get webhook delivery history.

        Args:
            webhook_id: Webhook UUID
            page: Page number (default: 1)
            page_size: Items per page (default: 50)
            status: Filter by delivery status (optional)

        Returns:
            Paginated response with delivery history
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status

        return await self.client.get(f"webhooks/webhooks/{webhook_id}/deliveries/", params=params)

    async def test(self, webhook_id: str) -> Dict[str, Any]:
        """
        Test webhook subscription.

        Args:
            webhook_id: Webhook UUID

        Returns:
            Test result
        """
        return await self.client.post(f"webhooks/webhooks/{webhook_id}/test/")
