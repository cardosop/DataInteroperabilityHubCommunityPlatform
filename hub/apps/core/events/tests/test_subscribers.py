"""
Tests for event subscribers.
"""

import uuid
from unittest.mock import Mock, patch

from django.test import TestCase

from hub.apps.core.events.subscribers import (
    NotificationSubscriber,
    WebhookSubscriber,
    WorkflowTriggerSubscriber,
)


class WebhookSubscriberTest(TestCase):
    """Test WebhookSubscriber."""

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_webhook_subscriber_init(self, mock_get_bus):
        """Test WebhookSubscriber initialization."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WebhookSubscriber()
        self.assertIsNotNone(subscriber.subscriber)
        self.assertEqual(subscriber.subscriber.subscriber_name, "webhook_subscriber")

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_webhook_subscriber_start(self, mock_get_bus):
        """Test starting webhook subscriber subscribes with wildcard pattern."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WebhookSubscriber()
        subscriber.subscriber = Mock()

        subscriber.start()

        subscriber.subscriber.subscribe.assert_called_once_with(
            event_type_pattern="*.*",
            handler=subscriber._handle_event,
            is_active=True,
        )

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_webhook_subscriber_handle_event(self, mock_get_bus):
        """Test webhook subscriber event handling delivers to webhook service."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_webhook_service = Mock()

        subscriber = WebhookSubscriber(webhook_service=mock_webhook_service)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "data": {"contract_id": "c-123"},
        }

        subscriber._handle_event(event)
        mock_webhook_service.deliver_webhook.assert_called_once_with(event)

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_webhook_subscriber_handle_event_no_service(self, mock_get_bus):
        """Test webhook subscriber does not crash when webhook_service is None."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WebhookSubscriber(webhook_service=None)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "data": {},
        }

        # Should not raise
        subscriber._handle_event(event)

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_webhook_subscriber_handle_event_delivery_exception(self, mock_get_bus):
        """Test webhook subscriber handles delivery exceptions gracefully."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_webhook_service = Mock()
        mock_webhook_service.deliver_webhook.side_effect = RuntimeError("connection error")

        subscriber = WebhookSubscriber(webhook_service=mock_webhook_service)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "data": {},
        }

        # Should not raise despite delivery failure
        subscriber._handle_event(event)
        mock_webhook_service.deliver_webhook.assert_called_once_with(event)


class NotificationSubscriberTest(TestCase):
    """Test NotificationSubscriber."""

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_notification_subscriber_init(self, mock_get_bus):
        """Test NotificationSubscriber initialization."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = NotificationSubscriber()
        self.assertIsNotNone(subscriber.subscriber)
        self.assertEqual(subscriber.subscriber.subscriber_name, "notification_subscriber")

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_notification_subscriber_start(self, mock_get_bus):
        """Test starting notification subscriber subscribes to all notification event patterns."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = NotificationSubscriber()
        subscriber.subscriber = Mock()

        subscriber.start()

        expected_patterns = [
            "access.requested",
            "access.granted",
            "access.revoked",
            "workflow.failed",
            "workflow.completed",
            "quality.anomaly.detected",
            "compliance.check.failed",
            "marketplace.order.created",
            "marketplace.order.approved",
            "marketplace.order.rejected",
        ]

        self.assertEqual(
            subscriber.subscriber.subscribe.call_count,
            len(expected_patterns),
        )

        [
            c.kwargs.get("event_type_pattern") or c.args[0]
            for c in subscriber.subscriber.subscribe.call_args_list
        ]
        # Use keyword arg form -- production code uses keyword args
        for pattern in expected_patterns:
            subscriber.subscriber.subscribe.assert_any_call(
                event_type_pattern=pattern,
                handler=subscriber._handle_event,
                is_active=True,
            )

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_notification_subscriber_handle_event(self, mock_get_bus):
        """Test notification subscriber event handling."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_notification_service = Mock()

        subscriber = NotificationSubscriber(notification_service=mock_notification_service)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "access.requested",
            "data": {},
        }

        subscriber._handle_event(event)
        mock_notification_service.send_notification.assert_called_once_with(event)

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_notification_subscriber_handle_event_no_service(self, mock_get_bus):
        """Test notification subscriber does not crash when notification_service is None."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = NotificationSubscriber(notification_service=None)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "access.requested",
            "data": {},
        }

        # Should not raise
        subscriber._handle_event(event)


class WorkflowTriggerSubscriberTest(TestCase):
    """Test WorkflowTriggerSubscriber."""

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_init(self, mock_get_bus):
        """Test WorkflowTriggerSubscriber initialization."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WorkflowTriggerSubscriber()
        self.assertIsNotNone(subscriber.subscriber)
        self.assertEqual(subscriber.subscriber.subscriber_name, "workflow_trigger_subscriber")

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_start(self, mock_get_bus):
        """Test starting workflow trigger subscriber subscribes to trigger event patterns."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WorkflowTriggerSubscriber()
        subscriber.subscriber = Mock()

        subscriber.start()

        expected_patterns = [
            "asset.created",
            "contract.created",
            "dataset.created",
            "ingestion.completed",
            "quality.check.completed",
            "compliance.check.completed",
        ]

        self.assertEqual(
            subscriber.subscriber.subscribe.call_count,
            len(expected_patterns),
        )

        for pattern in expected_patterns:
            subscriber.subscriber.subscribe.assert_any_call(
                event_type_pattern=pattern,
                handler=subscriber._handle_event,
                is_active=True,
            )

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_handle_event(self, mock_get_bus):
        """Test workflow trigger subscriber routes asset.created to asset_activation workflow."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_workflow_engine = Mock()
        mock_instance = Mock()
        mock_instance.id = uuid.uuid4()
        mock_workflow_engine.create_instance.return_value = mock_instance

        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())

        subscriber = WorkflowTriggerSubscriber(workflow_engine=mock_workflow_engine)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "asset.created",
            "source": {
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
            "data": {
                "asset_id": asset_id,
            },
        }

        subscriber._handle_event(event)

        mock_workflow_engine.create_instance.assert_called_once_with(
            workflow_name="asset_activation",
            input_data={"asset_id": asset_id},
            tenant_id=tenant_id,
            created_by_id=user_id,
        )
        mock_workflow_engine.start_instance.assert_called_once_with(str(mock_instance.id))
        mock_workflow_engine.execute_instance.assert_called_once_with(str(mock_instance.id))

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_handle_event_contract(self, mock_get_bus):
        """Test workflow trigger subscriber routes contract.created to contract_validation."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_workflow_engine = Mock()
        mock_instance = Mock()
        mock_instance.id = uuid.uuid4()
        mock_workflow_engine.create_instance.return_value = mock_instance

        subscriber = WorkflowTriggerSubscriber(workflow_engine=mock_workflow_engine)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "contract.created",
            "source": {"tenant_id": "t1", "user_id": "u1"},
            "data": {"contract_id": "c-1"},
        }

        subscriber._handle_event(event)

        mock_workflow_engine.create_instance.assert_called_once_with(
            workflow_name="contract_validation",
            input_data={"contract_id": "c-1"},
            tenant_id="t1",
            created_by_id="u1",
        )

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_handle_event_no_engine(self, mock_get_bus):
        """Test workflow trigger subscriber does not crash when workflow_engine is None."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus

        subscriber = WorkflowTriggerSubscriber(workflow_engine=None)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "asset.created",
            "source": {"tenant_id": "t1", "user_id": "u1"},
            "data": {},
        }

        # Should not raise
        subscriber._handle_event(event)

    @patch("hub.apps.core.events.subscribers.get_event_bus")
    def test_workflow_trigger_subscriber_handle_event_unknown_type(self, mock_get_bus):
        """Test workflow trigger subscriber ignores unmapped event types."""
        mock_bus = Mock()
        mock_get_bus.return_value = mock_bus
        mock_workflow_engine = Mock()

        subscriber = WorkflowTriggerSubscriber(workflow_engine=mock_workflow_engine)
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "unknown.event.type",
            "source": {"tenant_id": "t1", "user_id": "u1"},
            "data": {},
        }

        subscriber._handle_event(event)

        mock_workflow_engine.create_instance.assert_not_called()
        mock_workflow_engine.start_instance.assert_not_called()
        mock_workflow_engine.execute_instance.assert_not_called()
