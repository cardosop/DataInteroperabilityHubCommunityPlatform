"""
Phase 44 (44.6) — Webhook Event Type Validation Tests

Tests that invalid event types are rejected, duplicates are removed,
and empty list raises ValidationError.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus


@pytest.mark.django_db(transaction=True)
class EventTypeValidationTest(TestCase):
    """Test Webhook.clean() event type normalization."""

    def _make_webhook(self, event_types):
        """Helper: build an unsaved Webhook with given event_types."""
        from hub.apps.tenants.models import Tenant

        tenant, _ = Tenant.objects.get_or_create(
            name="event-type-test-tenant",
            defaults={"slug": "event-type-test"},
        )
        return Webhook(
            tenant=tenant,
            name="Test Webhook",
            url="https://example.com/hook",
            secret="test-secret",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            max_retries=5,
            retry_intervals=[1, 5, 30, 300, 1800],
        )

    def test_invalid_event_type_rejected(self):
        """Invalid event types raise ValidationError."""
        wh = self._make_webhook(["INVALID_EVENT"])
        with self.assertRaises(ValidationError) as ctx:
            wh.clean()
        self.assertIn("Invalid event type", str(ctx.exception))

    def test_duplicates_are_removed(self):
        """Duplicate event types are deduplicated."""
        wh = self._make_webhook(["asset.created", "asset.created", "asset.updated"])
        wh.clean()
        self.assertEqual(wh.event_types, ["asset.created", "asset.updated"])

    def test_empty_list_raises_validation_error(self):
        """Empty event_types raises ValidationError."""
        wh = self._make_webhook([])
        with self.assertRaises(ValidationError) as ctx:
            wh.clean()
        self.assertIn("At least one event type", str(ctx.exception))

    def test_mixed_invalid_and_valid_rejects(self):
        """A mix of valid and invalid event types raises on the invalid one."""
        wh = self._make_webhook(["asset.created", "INVALID", "asset.updated"])
        with self.assertRaises(ValidationError) as ctx:
            wh.clean()
        self.assertIn("INVALID", str(ctx.exception))

    def test_enum_values_are_normalized_to_strings(self):
        """Enum values are converted to plain strings."""
        wh = self._make_webhook([WebhookEventType.ASSET_CREATED])
        wh.clean()
        self.assertEqual(wh.event_types, ["asset.created"])
        self.assertIsInstance(wh.event_types[0], str)

    def test_all_enum_members_normalize_to_strings(self):
        """Every WebhookEventType member normalizes to its string value."""
        for member in WebhookEventType:
            wh = self._make_webhook([member])
            wh.clean()
            self.assertIsInstance(wh.event_types[0], str)
            self.assertEqual(wh.event_types[0], member.value)
