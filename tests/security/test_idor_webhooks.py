"""
Security tests: IDOR for Webhooks.

Per tasks 29.5.1. User from tenant A must not access tenant B's webhook by ID.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import pytest
from rest_framework import status

from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class WebhookIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's webhook by ID."""

    def test_webhook_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET webhooks/webhooks/{id}/ for other tenant's webhook must return 403 or 404."""
        webhook_b = Webhook.objects.create(
            tenant=self.tenant_b,
            name="Webhook B",
            url="https://example.com/webhook",
            secret="secret-key-b",
            event_types=[WebhookEventType.ASSET_CREATED],
            status=WebhookStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/webhooks/webhooks/{webhook_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant webhook access must be 403 or 404",
        )

    def test_webhook_retrieve_succeeds_for_own_tenant(self):
        """GET webhooks/webhooks/{id}/ for own tenant's webhook can return 200."""
        webhook_a = Webhook.objects.create(
            tenant=self.tenant_a,
            name="Webhook A",
            url="https://example.com/webhook",
            secret="secret-key-a",
            event_types=[WebhookEventType.ASSET_CREATED],
            status=WebhookStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/webhooks/webhooks/{webhook_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
