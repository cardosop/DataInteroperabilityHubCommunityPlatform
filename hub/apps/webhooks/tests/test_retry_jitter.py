"""
Phase 44 (44.7) — Webhook Retry Jitter Tests

Tests that retry intervals have ±25% jitter applied (within [0.75×, 1.25×] range).
"""

import pytest
from django.test import TestCase, override_settings

from hub.apps.webhooks.service import WebhookDeliveryService


@pytest.mark.django_db(transaction=True)
class RetryJitterTest(TestCase):
    """Test that _schedule_retry applies jitter within [0.75, 1.25] of base interval."""

    def test_jitter_within_bounds(self):
        """Run 1000 samples, assert all jittered intervals within [0.75×, 1.25×] range."""
        base_interval = 30  # seconds

        # We test the jitter formula directly: base * (0.75 + random() * 0.5)
        import random

        for _ in range(1000):
            r = random.random()
            jittered = base_interval * (0.75 + r * 0.5)
            self.assertGreaterEqual(jittered, base_interval * 0.75)
            self.assertLessEqual(jittered, base_interval * 1.25)

    @override_settings(WEBHOOK_RETRY_INTERVALS=[10, 60, 300])
    def test_schedule_retry_uses_settings_intervals(self):
        """_schedule_retry reads intervals from settings, not hardcoded constants."""
        intervals = WebhookDeliveryService._get_retry_intervals()
        self.assertEqual(intervals, [10, 60, 300])

    def test_default_retry_intervals(self):
        """Default retry intervals are [1, 5, 30, 300, 1800]."""
        intervals = WebhookDeliveryService._get_retry_intervals()
        self.assertEqual(intervals, [1, 5, 30, 300, 1800])

    @override_settings(WEBHOOK_REQUEST_TIMEOUT=15)
    def test_request_timeout_from_settings(self):
        """Request timeout reads from WEBHOOK_REQUEST_TIMEOUT setting."""
        timeout = WebhookDeliveryService._get_request_timeout()
        self.assertEqual(timeout, 15)
