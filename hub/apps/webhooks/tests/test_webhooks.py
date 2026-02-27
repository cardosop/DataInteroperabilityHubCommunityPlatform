"""
Unit tests for Webhook Models and Service

Tests for webhook subscriptions and delivery.
Uses real HTTP server (TestWebhookServer) for delivery tests; no mocks.
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService

# Reuse real HTTP server from integration tests (no mocks)
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.polling import wait_until

pytestmark = pytest.mark.django_db(transaction=True)


class WebhookModelTest(TestCase):
    """Test Webhook model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_create_webhook(self):
        """Test webhook creation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )

        self.assertEqual(webhook.status, WebhookStatus.ACTIVE)
        self.assertIn(WebhookEventType.ASSET_CREATED, webhook.event_types)

    def test_webhook_signature(self):
        """Test webhook signature generation"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )

        payload = '{"test": "data"}'
        signature = webhook.generate_signature(payload)

        self.assertIsNotNone(signature)
        self.assertEqual(len(signature), 64)  # SHA256 hex length


class WebhookDeliveryServiceTest(TestCase):
    """Test WebhookDeliveryService with real HTTP server (no mocks)."""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_trigger_webhook_success(self):
        """Test successful webhook delivery via real HTTP server."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Test Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ASSET_CREATED],
                created_by=self.user,
            )
            count = WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ASSET_CREATED,
                resource_type="ASSET",
                resource_id="test-id",
                event_data={"test": "data"},
            )
            self.assertEqual(count, 1)

            def delivery_success():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(delivery_success, timeout=5.0, message="Webhook delivery not SUCCESS")
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["method"], "POST")

    def test_trigger_webhook_retry(self):
        """Test webhook delivery with 5xx response schedules retry (real server)."""
        with TestWebhookServer(response_status=500) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="Test Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ASSET_CREATED],
                created_by=self.user,
            )
            count = WebhookDeliveryService.trigger_webhook(
                tenant_id=str(self.tenant.id),
                event_type=WebhookEventType.ASSET_CREATED,
                resource_type="ASSET",
                resource_id="test-id",
                event_data={"test": "data"},
            )
            self.assertEqual(count, 1)

            def delivery_failed_with_retry():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return (
                    d is not None
                    and d.status == DeliveryStatus.FAILED
                    and d.next_retry_at is not None
                )

            wait_until(
                delivery_failed_with_retry,
                timeout=5.0,
                message="Webhook delivery not FAILED with next_retry_at",
            )
            delivery = WebhookDelivery.objects.filter(webhook=webhook).first()
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.status, DeliveryStatus.FAILED)
            self.assertIsNotNone(delivery.next_retry_at)
