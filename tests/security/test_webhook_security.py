"""
Security tests: Webhook service (401 unauthenticated, tenant isolation).

Per tasks 29.6.3. Webhook API must return 401 when unauthenticated and enforce
tenant isolation for cross-tenant access. Real APIClient; no mocks.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def test_webhooks_list_returns_401_when_unauthenticated():
    """GET /api/v1/webhooks/webhooks/ without auth must return 401."""
    client = APIClient()
    response = client.get("/api/v1/webhooks/webhooks/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_webhook_retrieve_returns_401_when_unauthenticated():
    """GET /api/v1/webhooks/webhooks/{id}/ without auth must return 401."""
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"Webhook {uid}", slug=f"webhook-{uid}")
    user = User.objects.create_user(
        email=f"webhook-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    webhook = Webhook.objects.create(
        tenant=tenant,
        name="Test Webhook",
        url="https://example.com/webhook",
        secret="test-secret-value",
        event_types=[WebhookEventType.ASSET_CREATED],
        status=WebhookStatus.ACTIVE,
        created_by=user,
    )
    client = APIClient()
    response = client.get(f"/api/v1/webhooks/webhooks/{webhook.id}/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_webhooks_tenant_isolation_cross_tenant_returns_403_or_404():
    """User from tenant A must not access tenant B's webhook."""
    from .base_idor import IDORTestBase

    t = IDORTestBase()
    t.setUp()
    webhook_b = Webhook.objects.create(
        tenant=t.tenant_b,
        name="Webhook B",
        url="https://example.com/webhook-b",
        secret="test-secret-value",
        event_types=[WebhookEventType.ASSET_CREATED],
        status=WebhookStatus.ACTIVE,
        created_by=t.user_b,
    )
    t.client.force_authenticate(user=t.user_a)
    response = t.client.get(f"/api/v1/webhooks/webhooks/{webhook_b.id}/")
    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )
