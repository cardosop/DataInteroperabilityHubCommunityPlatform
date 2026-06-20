"""
Tests for event subscribers.
"""

from unittest.mock import Mock, patch

from django.test import TestCase

from hub.apps.core.events.bus import EventBus
from hub.apps.core.events.models import EventSubscription
from hub.apps.core.events.subscriber import EventSubscriber


class EventSubscriberTest(TestCase):
    """Test event subscriber functionality."""

    def setUp(self):
        """Set up test data."""
        self.redis_client = Mock()
        self.event_bus = EventBus(redis_client=self.redis_client)

    @patch("hub.apps.core.events.subscriber.get_event_bus")
    def test_event_subscriber_subscribe(self, mock_get_bus):
        """Test EventSubscriber.subscribe."""
        mock_get_bus.return_value = self.event_bus

        subscriber = EventSubscriber("test_subscriber")

        handler = Mock()
        subscriber.subscribe("contract.*", handler)

        # Verify subscription created
        subscription = EventSubscription.objects.get(
            subscriber_name="test_subscriber", event_type_pattern="contract.*"
        )
        self.assertTrue(subscription.is_active)

    @patch("hub.apps.core.events.subscriber.get_event_bus")
    def test_event_subscriber_unsubscribe(self, mock_get_bus):
        """Test EventSubscriber.unsubscribe."""
        mock_get_bus.return_value = self.event_bus

        subscriber = EventSubscriber("test_subscriber")

        # Create subscription
        EventSubscription.objects.create(
            subscriber_name="test_subscriber", event_type_pattern="contract.*", is_active=True
        )

        # Unsubscribe
        subscriber.unsubscribe("contract.*")

        # Verify subscription deactivated
        subscription = EventSubscription.objects.get(
            subscriber_name="test_subscriber", event_type_pattern="contract.*"
        )
        self.assertFalse(subscription.is_active)
