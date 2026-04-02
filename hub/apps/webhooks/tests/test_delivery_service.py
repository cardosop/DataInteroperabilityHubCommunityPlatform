"""Comprehensive webhook delivery service tests — Phase 100.6

Tests delivery record creation, payload structure, and webhook filtering.
Does NOT make real HTTP calls — tests the service logic up to the delivery point.
"""
import uuid
import json
import hmac
import hashlib
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import (
    Webhook, WebhookDelivery, WebhookStatus, WebhookEventType, DeliveryStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class WebhookFilteringTest(TestCase):
    """Test webhook event type filtering and matching."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )

    def _create_webhook(self, event_types, wh_status=WebhookStatus.ACTIVE):
        return Webhook.objects.create(
            tenant=self.tenant,
            name=f"WH {uuid.uuid4().hex[:6]}",
            url="https://example.com/hook",
            secret="test-secret",
            event_types=event_types,
            status=wh_status,
            created_by=self.user,
        )

    def test_get_webhooks_for_event_type_matches(self):
        self._create_webhook([WebhookEventType.CONTRACT_CREATED])
        self._create_webhook([WebhookEventType.ASSET_CREATED])
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 1)

    def test_get_webhooks_for_event_type_skips_paused(self):
        self._create_webhook([WebhookEventType.CONTRACT_CREATED], WebhookStatus.PAUSED)
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 0)

    def test_get_webhooks_for_event_type_skips_disabled(self):
        self._create_webhook([WebhookEventType.CONTRACT_CREATED], WebhookStatus.DISABLED)
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 0)

    def test_multiple_webhooks_same_event(self):
        self._create_webhook([WebhookEventType.CONTRACT_CREATED])
        self._create_webhook([WebhookEventType.CONTRACT_CREATED])
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 2)

    def test_webhook_subscribes_to_multiple_events(self):
        wh = self._create_webhook([
            WebhookEventType.CONTRACT_CREATED,
            WebhookEventType.CONTRACT_UPDATED,
            WebhookEventType.ASSET_CREATED,
        ])
        self.assertTrue(wh.subscribes_to_event_type("contract.created"))
        self.assertTrue(wh.subscribes_to_event_type("contract.updated"))
        self.assertTrue(wh.subscribes_to_event_type("asset.created"))
        self.assertFalse(wh.subscribes_to_event_type("ingestion.completed"))

    def test_no_webhooks_returns_empty(self):
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 0)

    def test_cross_tenant_isolation(self):
        """Webhooks from another tenant are not returned."""
        uid2 = uuid.uuid4().hex[:8]
        other = Tenant.objects.create(
            name=f"Other {uid2}", slug=f"other-{uid2}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        Webhook.objects.create(
            tenant=other, name="Foreign", url="https://example.com/f",
            secret="s", event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
        )
        self._create_webhook([WebhookEventType.CONTRACT_CREATED])
        results = WebhookDeliveryService.get_webhooks_for_event_type(
            str(self.tenant.id), "contract.created"
        )
        self.assertEqual(len(results), 1)


class DeliveryRecordTest(TestCase):
    """Test WebhookDelivery record creation and status tracking."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant, name="WH", url="https://example.com/wh",
            secret="test-secret-abc", event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE, created_by=self.user,
        )

    def test_delivery_created_with_pending_status(self):
        d = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="contract.created",
            payload={"event_type": "contract.created", "data": {}},
            signature="abc123", status=DeliveryStatus.PENDING,
        )
        self.assertEqual(d.status, DeliveryStatus.PENDING)
        self.assertEqual(d.attempt_number, 0)

    def test_delivery_success_tracking(self):
        d = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="contract.created",
            payload={"event_type": "contract.created"},
            signature="sig", status=DeliveryStatus.SUCCESS,
            http_status_code=200, delivered_at=timezone.now(),
        )
        self.assertEqual(d.status, DeliveryStatus.SUCCESS)
        self.assertEqual(d.http_status_code, 200)
        self.assertIsNotNone(d.delivered_at)

    def test_delivery_failure_tracking(self):
        d = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="contract.created",
            payload={"event_type": "contract.created"},
            signature="sig", status=DeliveryStatus.FAILED,
            attempt_number=3, error_message="Connection timeout",
            http_status_code=504,
        )
        self.assertEqual(d.attempt_number, 3)
        self.assertEqual(d.error_message, "Connection timeout")
        self.assertEqual(d.http_status_code, 504)

    def test_delivery_dead_letter(self):
        d = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="contract.created",
            payload={"event_type": "contract.created"},
            signature="sig", status=DeliveryStatus.DEAD_LETTER,
            attempt_number=5, error_message="Max retries exceeded",
        )
        self.assertEqual(d.status, DeliveryStatus.DEAD_LETTER)
        self.assertEqual(d.attempt_number, 5)

    def test_signature_matches_hmac_sha256(self):
        """Verify signature generation is correct HMAC-SHA256."""
        payload_dict = {"event_type": "contract.created", "data": {"id": "123"}}
        payload_json = json.dumps(payload_dict, sort_keys=True)
        expected_sig = hmac.new(
            "test-secret-abc".encode("utf-8"),
            payload_json.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        actual_sig = self.webhook.generate_signature(payload_json)
        self.assertEqual(actual_sig, expected_sig)

    def test_payload_has_required_fields(self):
        """Delivery payload should contain standard webhook fields."""
        payload = {
            "event_type": "contract.created",
            "resource_type": "CONTRACT",
            "resource_id": str(uuid.uuid4()),
            "timestamp": timezone.now().isoformat(),
            "data": {"name": "Test Contract"},
        }
        d = WebhookDelivery.objects.create(
            webhook=self.webhook, event_type="contract.created",
            payload=payload, signature="sig", status=DeliveryStatus.PENDING,
        )
        self.assertEqual(d.payload["event_type"], "contract.created")
        self.assertEqual(d.payload["resource_type"], "CONTRACT")
        self.assertIn("resource_id", d.payload)
        self.assertIn("timestamp", d.payload)
        self.assertIn("data", d.payload)


class OdpsWebhookFilteringTest(TestCase):
    """Test ODPS-specific webhook filtering."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )

    def test_get_webhooks_for_odps_events(self):
        Webhook.objects.create(
            tenant=self.tenant, name="ODPS WH", url="https://example.com/odps",
            secret="s", event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE, created_by=self.user,
        )
        Webhook.objects.create(
            tenant=self.tenant, name="Non-ODPS", url="https://example.com/other",
            secret="s", event_types=[WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE, created_by=self.user,
        )
        results = WebhookDeliveryService.get_webhooks_for_odps_events(str(self.tenant.id))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "ODPS WH")

    def test_subscribes_to_odps_events(self):
        wh = Webhook.objects.create(
            tenant=self.tenant, name="Mixed", url="https://example.com/m",
            secret="s",
            event_types=[WebhookEventType.CONTRACT_CREATED, WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE, created_by=self.user,
        )
        self.assertTrue(wh.subscribes_to_odps_events())
