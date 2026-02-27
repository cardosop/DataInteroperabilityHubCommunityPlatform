"""
Integration tests for ODPS event handling in webhook service.

Tests that ODPS events can be subscribed to via webhooks and are properly validated.
"""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus, DeliveryStatus
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSEventIntegrationTest(TestCase):
    """Integration tests for ODPS event handling"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

    def test_webhook_can_subscribe_to_odps_created(self):
        """Test that webhook can subscribe to odps.created event"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Created Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        self.assertEqual(webhook.status, WebhookStatus.ACTIVE)
        self.assertIn(WebhookEventType.ODPS_CREATED, webhook.event_types)
        self.assertEqual(len(webhook.event_types), 1)

    def test_webhook_can_subscribe_to_multiple_odps_events(self):
        """Test that webhook can subscribe to multiple ODPS events"""
        event_types = [
            WebhookEventType.ODPS_CREATED,
            WebhookEventType.ODPS_UPDATED,
            WebhookEventType.ODPS_LINKED,
            WebhookEventType.ODPS_NORMALIZED,
        ]

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        self.assertEqual(len(webhook.event_types), 4)
        for event_type in event_types:
            self.assertIn(event_type, webhook.event_types)

    def test_webhook_can_subscribe_to_all_odps_events(self):
        """Test that webhook can subscribe to all ODPS events"""
        all_odps_events = [
            WebhookEventType.ODPS_CREATED,
            WebhookEventType.ODPS_UPDATED,
            WebhookEventType.ODPS_DELETED,
            WebhookEventType.ODPS_NORMALIZED,
            WebhookEventType.ODPS_LINKED,
            WebhookEventType.ODPS_UNLINKED,
            WebhookEventType.ODPS_EXPORT_STARTED,
            WebhookEventType.ODPS_EXPORT_COMPLETED,
            WebhookEventType.ODPS_EXPORT_FAILED,
        ]

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="All ODPS Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=all_odps_events,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        self.assertEqual(len(webhook.event_types), 9)
        for event_type in all_odps_events:
            self.assertIn(event_type, webhook.event_types)

    def test_webhook_validation_accepts_odps_events(self):
        """Test that webhook validation accepts ODPS event types"""
        webhook = Webhook(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

        # Should not raise ValidationError
        webhook.full_clean()
        webhook.save()

        self.assertIsNotNone(webhook.id)

    def test_webhook_validation_rejects_invalid_event_type(self):
        """Test that webhook validation rejects invalid event types"""
        webhook = Webhook(
            tenant=self.tenant,
            name="Invalid Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=["invalid.event.type"],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

        # Should raise ValidationError
        with self.assertRaises(ValidationError) as cm:
            webhook.full_clean()

        self.assertIn("Invalid event type", str(cm.exception))

    def test_webhook_can_subscribe_to_mixed_event_types(self):
        """Test that webhook can subscribe to ODPS and non-ODPS events"""
        event_types = [
            WebhookEventType.ODPS_CREATED,
            WebhookEventType.CONTRACT_CREATED,
            WebhookEventType.ODPS_LINKED,
            WebhookEventType.ASSET_CREATED,
        ]

        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mixed Events Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        self.assertEqual(len(webhook.event_types), 4)
        self.assertIn(WebhookEventType.ODPS_CREATED, webhook.event_types)
        self.assertIn(WebhookEventType.CONTRACT_CREATED, webhook.event_types)

    def test_webhook_query_by_odps_event_type(self):
        """Test querying webhooks by ODPS event type"""
        # Create webhooks with different event types
        odps_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/odps",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        contract_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Contract Webhook",
            url="https://example.com/contract",
            secret="test-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Query webhooks that subscribe to ODPS events
        # Note: This is a simple check - in production, you'd use JSON field queries
        odps_webhooks = [
            w for w in Webhook.objects.filter(tenant=self.tenant)
            if WebhookEventType.ODPS_CREATED in w.event_types
        ]

        self.assertEqual(len(odps_webhooks), 1)
        self.assertEqual(odps_webhooks[0].id, odps_webhook.id)

    def test_webhook_tenant_isolation(self):
        """Test that webhooks are tenant-isolated"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other_tenant)

        # Create webhook in current tenant
        my_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="My ODPS Webhook",
            url="https://example.com/my-webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Create webhook in other tenant
        other_webhook = Webhook.objects.create(
            tenant=other_tenant,
            name="Other ODPS Webhook",
            url="https://example.com/other-webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Query webhooks for current tenant
        my_webhooks = Webhook.objects.filter(tenant=self.tenant)
        self.assertEqual(my_webhooks.count(), 1)
        self.assertEqual(my_webhooks.first().id, my_webhook.id)

        # Query webhooks for other tenant
        other_webhooks = Webhook.objects.filter(tenant=other_tenant)
        self.assertEqual(other_webhooks.count(), 1)
        self.assertEqual(other_webhooks.first().id, other_webhook.id)

    def test_webhook_subscribes_to_odps_events(self):
        """Test subscribes_to_odps_events() method"""
        # Webhook with ODPS events
        odps_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/odps",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertTrue(odps_webhook.subscribes_to_odps_events())

        # Webhook without ODPS events
        contract_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Contract Webhook",
            url="https://example.com/contract",
            secret="test-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertFalse(contract_webhook.subscribes_to_odps_events())

        # Webhook with mixed events
        mixed_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mixed Webhook",
            url="https://example.com/mixed",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )
        self.assertTrue(mixed_webhook.subscribes_to_odps_events())

    def test_webhook_subscribes_to_event_type(self):
        """Test subscribes_to_event_type() method"""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/test",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        self.assertTrue(webhook.subscribes_to_event_type(WebhookEventType.ODPS_CREATED))
        self.assertTrue(webhook.subscribes_to_event_type(WebhookEventType.ODPS_UPDATED))
        self.assertFalse(webhook.subscribes_to_event_type(WebhookEventType.ODPS_DELETED))
        self.assertFalse(webhook.subscribes_to_event_type(WebhookEventType.CONTRACT_CREATED))

    def test_filter_by_odps_events(self):
        """Test filter_by_odps_events() class method"""
        # Create webhooks with different event types
        odps_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Webhook",
            url="https://example.com/odps",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        contract_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Contract Webhook",
            url="https://example.com/contract",
            secret="test-secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        mixed_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Mixed Webhook",
            url="https://example.com/mixed",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Filter by ODPS events
        odps_webhooks = Webhook.filter_by_odps_events(
            Webhook.objects.filter(tenant=self.tenant)
        )

        odps_webhook_ids = {w.id for w in odps_webhooks}
        self.assertIn(odps_webhook.id, odps_webhook_ids)
        self.assertIn(mixed_webhook.id, odps_webhook_ids)
        self.assertNotIn(contract_webhook.id, odps_webhook_ids)

    def test_filter_by_event_type(self):
        """Test filter_by_event_type() class method"""
        # Create webhooks
        webhook1 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 1",
            url="https://example.com/1",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook2 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 2",
            url="https://example.com/2",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        webhook3 = Webhook.objects.create(
            tenant=self.tenant,
            name="Webhook 3",
            url="https://example.com/3",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED, WebhookEventType.ODPS_UPDATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Filter by specific event type (using string value)
        created_webhooks = Webhook.filter_by_event_type(
            str(WebhookEventType.ODPS_CREATED),  # Convert enum to string
            Webhook.objects.filter(tenant=self.tenant)
        )

        created_webhook_ids = {w.id for w in created_webhooks}
        self.assertIn(webhook1.id, created_webhook_ids)
        self.assertIn(webhook3.id, created_webhook_ids)
        self.assertNotIn(webhook2.id, created_webhook_ids)

