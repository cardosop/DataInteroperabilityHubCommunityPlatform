"""
Phase 44 (44.7) — Webhook Retry Jitter Tests

Tests that _schedule_retry applies jitter within [0.75x, 1.25x] of base interval
and that configuration settings are correctly read.
"""

import datetime
import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.tenants.models import Tenant
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.service import WebhookDeliveryService


def _make_webhook_and_delivery(tenant=None, attempt_number=2):
    """Create a webhook + delivery pair for retry testing."""
    if tenant is None:
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"RJ-{uid}",
            slug=f"rj-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
    webhook = Webhook.objects.create(
        tenant=tenant,
        name="Retry-Test",
        url="https://example.com/webhook",
        event_types=[WebhookEventType.ASSET_CREATED],
        secret=uuid.uuid4().hex[:16],
        status=WebhookStatus.ACTIVE,
        max_retries=5,
    )
    delivery = WebhookDelivery.objects.create(
        webhook=webhook,
        event_type="asset.created",
        payload={"test": True},
        signature="x",
        status=DeliveryStatus.FAILED,
        attempt_number=attempt_number,
    )
    return webhook, delivery


@pytest.mark.django_db(transaction=True)
class RetryJitterTest(TestCase):
    """Test that _schedule_retry applies jitter within [0.75, 1.25] of base interval."""

    @patch.object(timezone, "now")
    def test_jitter_within_bounds(self, mock_now):
        """Run 100 samples, assert all jittered next_retry_at is within [0.75x, 1.25x] range."""
        base_interval = 30  # seconds (index 2 of default retry_intervals=[1,5,30,300,1800])
        mock_now.return_value = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

        for _ in range(100):
            webhook, delivery = _make_webhook_and_delivery()
            delivery.status = DeliveryStatus.FAILED
            delivery.attempt_number = 2
            delivery.save(update_fields=["status", "attempt_number"])

            WebhookDeliveryService._schedule_retry(delivery)
            delivery.refresh_from_db()

            self.assertIsNotNone(delivery.next_retry_at)
            delta = (delivery.next_retry_at - mock_now.return_value).total_seconds()
            self.assertGreaterEqual(delta, base_interval * 0.75)
            self.assertLessEqual(delta, base_interval * 1.25)

    @override_settings(WEBHOOK_RETRY_INTERVALS=[10, 60, 300])
    def test_get_retry_intervals_reads_settings(self):
        """_get_retry_intervals returns the value from Django settings."""
        intervals = WebhookDeliveryService._get_retry_intervals()
        self.assertEqual(intervals, [10, 60, 300])

    @patch.object(timezone, "now")
    def test_schedule_retry_uses_custom_webhook_intervals(self, mock_now):
        """_schedule_retry uses webhook.retry_intervals when set."""
        mock_now.return_value = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

        webhook, delivery = _make_webhook_and_delivery()
        # Custom retry_intervals must match max_retries (5) per model validation.
        webhook.max_retries = 3
        webhook.retry_intervals = [20, 90, 400]
        webhook.save(update_fields=["max_retries", "retry_intervals"])
        delivery.webhook.refresh_from_db()
        delivery.attempt_number = 0  # index 0 → 20
        delivery.save(update_fields=["attempt_number"])

        WebhookDeliveryService._schedule_retry(delivery)
        delivery.refresh_from_db()

        self.assertIsNotNone(delivery.next_retry_at)
        self.assertEqual(delivery.attempt_number, 1)
        # base_interval=20, jittered in [15, 30]
        delta = (delivery.next_retry_at - mock_now.return_value).total_seconds()
        self.assertGreaterEqual(delta, 15)   # 20 * 0.75
        self.assertLessEqual(delta, 30)      # 20 * 1.25

    def test_default_retry_intervals(self):
        """Default retry intervals are [1, 5, 30, 300, 1800]."""
        intervals = WebhookDeliveryService._get_retry_intervals()
        self.assertEqual(intervals, [1, 5, 30, 300, 1800])

    @override_settings(WEBHOOK_REQUEST_TIMEOUT=15)
    def test_request_timeout_from_settings(self):
        """Request timeout reads from WEBHOOK_REQUEST_TIMEOUT setting."""
        timeout = WebhookDeliveryService._get_request_timeout()
        self.assertEqual(timeout, 15)

    def test_schedule_retry_increments_attempt_number(self):
        """_schedule_retry increments attempt_number on the delivery."""
        webhook, delivery = _make_webhook_and_delivery()
        delivery.attempt_number = 0
        delivery.save(update_fields=["attempt_number"])

        WebhookDeliveryService._schedule_retry(delivery)
        delivery.refresh_from_db()

        self.assertEqual(delivery.attempt_number, 1)

    def test_schedule_retry_sets_next_retry_at(self):
        """_schedule_retry always sets a non-null next_retry_at (when not DEAD_LETTER)."""
        webhook, delivery = _make_webhook_and_delivery()
        delivery.attempt_number = 1
        delivery.save(update_fields=["attempt_number"])

        WebhookDeliveryService._schedule_retry(delivery)
        delivery.refresh_from_db()

        self.assertIsNotNone(delivery.next_retry_at)
        self.assertEqual(delivery.status, DeliveryStatus.FAILED)  # stays FAILED until delivered

    def test_schedule_retry_dead_letter_when_max_retries_exceeded(self):
        """When attempt_number >= max_retries, delivery is marked DEAD_LETTER."""
        webhook, delivery = _make_webhook_and_delivery()
        delivery.attempt_number = 5  # equal to max_retries
        delivery.save(update_fields=["attempt_number"])

        WebhookDeliveryService._schedule_retry(delivery)
        delivery.refresh_from_db()

        self.assertEqual(delivery.status, DeliveryStatus.DEAD_LETTER)
        self.assertIsNone(delivery.next_retry_at)
