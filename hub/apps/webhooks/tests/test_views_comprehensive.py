"""Comprehensive webhook views tests — Phase 100.4

Tests webhook REST API endpoints via APIClient.

URL structure (verified against live routing):
    - Webhook list/create:  /api/v1/webhooks/webhooks/
    - Webhook detail:       /api/v1/webhooks/webhooks/{id}/
    - Event types:          /api/v1/webhooks/webhooks/event-types/
    - Webhook test:         /api/v1/webhooks/webhooks/{id}/test/
    - Rotate secret:        /api/v1/webhooks/webhooks/{id}/rotate_secret/
    - Webhook deliveries:   /api/v1/webhooks/webhook-deliveries/
"""

import uuid

import pytest

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.slow, pytest.mark.uc("UC-WH-001")]
User = get_user_model()

# Canonical URL prefix — the webhooks app is included at ``webhooks/``
# in the API v1 urlconf, and its router registers ``webhooks`` as the
# ViewSet prefix, so the full path is ``/api/v1/webhooks/webhooks/``.
_WH_LIST = "/api/v1/webhooks/webhooks/"
_WH_DELIVERIES = "/api/v1/webhooks/webhook-deliveries/"
_WH_EVENT_TYPES = "/api/v1/webhooks/webhooks/event-types/"


def _wh_detail(webhook_id):
    return f"/api/v1/webhooks/webhooks/{webhook_id}/"


class WebhookListTest(TestCase):
    """Test webhook list and event-types endpoints."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_webhooks_authenticated_returns_200(self):
        resp = self.client.get(_WH_LIST)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Response is a paginated list with standard DRF keys.
        data = resp.data
        self.assertIn("results", data)
        self.assertIn("count", data)

    def test_list_webhooks_unauthenticated_returns_401(self):
        client = APIClient()
        resp = client.get(_WH_LIST)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_event_types_endpoint_returns_200(self):
        resp = self.client.get(_WH_EVENT_TYPES)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("event_types", data)
        self.assertIsInstance(data["event_types"], list)

    def test_list_webhooks_tenant_scoped(self):
        """Webhooks from other tenants are not visible."""
        uid2 = uuid.uuid4().hex[:8]
        other = Tenant.objects.create(
            name=f"T2 {uid2}",
            slug=f"t2-{uid2}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        Webhook.objects.create(
            tenant=other,
            name="Foreign",
            url="https://example.com/f",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
        )
        Webhook.objects.create(
            tenant=self.tenant,
            name="Mine",
            url="https://example.com/m",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        resp = self.client.get(_WH_LIST)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", [])
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1, "Expected exactly one webhook in results")
        names = [w["name"] for w in results]
        # Foreign tenant's webhooks must never be visible
        self.assertNotIn("Foreign", names)
        # Our own webhook must be visible
        self.assertIn("Mine", names)

    def test_get_webhook_detail(self):
        wh = Webhook.objects.create(
            tenant=self.tenant,
            name="Detail",
            url="https://example.com/d",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        resp = self.client.get(_wh_detail(wh.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Detail")

    def test_get_webhook_detail_cross_tenant_returns_404(self):
        """A user cannot access another tenant's webhook detail."""
        uid2 = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"T2 {uid2}",
            slug=f"t2-{uid2}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_wh = Webhook.objects.create(
            tenant=other_tenant,
            name="Foreign",
            url="https://example.com/f",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
        )
        resp = self.client.get(_wh_detail(other_wh.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_webhook_create_via_api(self):
        payload = {
            "name": f"Hook {uuid.uuid4().hex[:6]}",
            "url": "https://example.com/webhook",
            "secret": "test-secret-key-12345",
            "event_types": [WebhookEventType.CONTRACT_CREATED],
            "status": WebhookStatus.ACTIVE,
        }
        resp = self.client.post(_WH_LIST, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data["name"], payload["name"])
        self.assertEqual(resp.data["url"], payload["url"])

    def test_webhook_create_empty_event_types_rejected(self):
        payload = {
            "name": "Bad",
            "url": "https://example.com/bad",
            "secret": "s",
            "event_types": [],
        }
        resp = self.client.post(_WH_LIST, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_create_invalid_event_type_rejected(self):
        payload = {
            "name": "Bad",
            "url": "https://example.com/bad",
            "secret": "s",
            "event_types": ["nonexistent.event"],
        }
        resp = self.client.post(_WH_LIST, payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class WebhookDeliveryListTest(TestCase):
    """Test webhook delivery read-only API."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com",
            password="pass",
            tenant=self.tenant,
            status="ACTIVE",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="WH",
            url="https://example.com/wh",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    def test_list_deliveries_returns_200(self):
        WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type="contract.created",
            payload={"test": True},
            signature="abc",
            status=DeliveryStatus.SUCCESS,
        )
        resp = self.client.get(_WH_DELIVERIES)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)
        self.assertGreaterEqual(len(data["results"]), 1)
