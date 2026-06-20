"""
Tests for WebSocket reconnection logic and health checks.

These tests verify:
- Ping/pong heartbeat mechanism
- Connection timeout detection
- Automatic connection cleanup
- Background task management
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import WebSocketMessage, WebSocketMessageType
from hub.apps.websocket.tests.test_base import AsyncWebSocketTestCase


class WebSocketReconnectionTest(AsyncWebSocketTestCase):
    """Test WebSocket reconnection logic and health checks."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.create_unique_tenant()
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )

    async def test_handle_pong_updates_timestamp(self):
        """Test that handling pong updates last_pong_received timestamp."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.last_pong_received = None
        consumer.pending_ping = True

        # Create pong message
        pong_message = WebSocketMessage(
            type=WebSocketMessageType.PONG.value,
            data={"timestamp": datetime.now(UTC).isoformat()},
        )

        # Handle pong
        await consumer.handle_pong(pong_message)

        # Verify timestamp was updated
        self.assertIsNotNone(consumer.last_pong_received)
        self.assertFalse(consumer.pending_ping)

    async def test_ping_loop_sends_pings(self):
        """Test that ping loop sends periodic pings."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.ping_interval = 0.1  # Short interval for testing
        consumer._connection_closed = False
        consumer.send_json_message = AsyncMock()
        consumer.last_activity = datetime.now(UTC)  # Set to avoid timeout

        # Start ping loop
        ping_task = asyncio.create_task(consumer._ping_loop())

        try:
            # Wait for at least one ping
            await asyncio.sleep(0.15)

            # Verify ping was sent
            self.assertTrue(consumer.send_json_message.called)

            # Verify ping message structure
            call_args = consumer.send_json_message.call_args
            message = call_args[0][0]
            self.assertEqual(message.type, WebSocketMessageType.PING.value)
            self.assertTrue(consumer.pending_ping)
        finally:
            consumer._connection_closed = True
            ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ping_task

    async def test_health_check_detects_pong_timeout(self):
        """Test that health check detects pong timeout."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.pong_timeout = 0.1  # Short timeout for testing
        consumer.pending_ping = True
        consumer.last_pong_received = datetime.now(UTC) - timedelta(seconds=0.2)
        consumer._connection_closed = False
        consumer.close = AsyncMock()

        # Start health check loop
        health_task = asyncio.create_task(consumer._health_check_loop())

        try:
            # Wait for health check to detect timeout
            await asyncio.sleep(0.15)

            # Verify connection was closed due to pong timeout
            # May need a bit more time for the check to complete
            await asyncio.sleep(0.05)
            self.assertTrue(consumer.close.called)
        finally:
            consumer._connection_closed = True
            health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await health_task

    async def test_health_check_detects_inactivity_timeout(self):
        """Test that health check detects inactivity timeout."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.pong_timeout = 0.05  # Short pong timeout
        consumer.connection_timeout = 0.1  # Short connection timeout for testing
        consumer.pending_ping = False  # No pending ping, so pong check is skipped
        consumer.last_activity = datetime.now(UTC) - timedelta(seconds=0.2)
        consumer._connection_closed = False
        consumer.close = AsyncMock()

        # Start health check loop
        health_task = asyncio.create_task(consumer._health_check_loop())

        try:
            # Wait for health check to detect timeout
            # First iteration checks pong (skipped), second checks inactivity
            await asyncio.sleep(0.15)

            # Verify connection was closed due to inactivity
            self.assertTrue(consumer.close.called)
        finally:
            consumer._connection_closed = True
            health_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await health_task

    async def test_last_activity_updated_on_message(self):
        """Test that last_activity is updated when receiving messages."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.send_json_message = AsyncMock()
        consumer.last_activity = None

        # Create a message
        message = WebSocketMessage(
            type=WebSocketMessageType.PING.value,
            data={"timestamp": datetime.now(UTC).isoformat()},
        )

        # Simulate receiving message
        await consumer.handle_ping(message)

        # Verify last_activity was updated
        self.assertIsNotNone(consumer.last_activity)
        self.assertIsInstance(consumer.last_activity, datetime)

    async def test_last_activity_updated_on_send(self):
        """Test that last_activity is updated when sending messages."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.send = AsyncMock()
        consumer.last_activity = None

        # Create a message
        message = WebSocketMessage(
            type=WebSocketMessageType.PONG.value,
            data={"timestamp": datetime.now(UTC).isoformat()},
        )

        # Send message
        await consumer.send_json_message(message)

        # Verify last_activity was updated
        self.assertIsNotNone(consumer.last_activity)
        self.assertIsInstance(consumer.last_activity, datetime)
        self.assertTrue(consumer.send.called)

    async def test_background_tasks_cancelled_on_disconnect(self):
        """Test that background tasks are cancelled on disconnect."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer._connection_closed = False
        consumer.send_json_message = AsyncMock()
        consumer.last_activity = datetime.now(UTC)

        # Start background tasks
        ping_task = asyncio.create_task(consumer._ping_loop())
        health_task = asyncio.create_task(consumer._health_check_loop())

        consumer.ping_task = ping_task
        consumer.health_check_task = health_task

        # Wait a bit for tasks to start
        await asyncio.sleep(0.05)

        # Disconnect
        await consumer.disconnect(None)

        # Wait for cancellation to complete
        await asyncio.sleep(0.05)

        # Verify tasks are cancelled or done
        self.assertTrue(ping_task.cancelled() or ping_task.done())
        self.assertTrue(health_task.cancelled() or health_task.done())
        self.assertTrue(consumer._connection_closed)

    async def test_ping_loop_respects_connection_closed(self):
        """Test that ping loop stops when connection is closed."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.ping_interval = 0.1
        consumer._connection_closed = False
        consumer.send_json_message = AsyncMock()
        consumer.last_activity = datetime.now(UTC)

        # Start ping loop
        ping_task = asyncio.create_task(consumer._ping_loop())

        # Wait a bit
        await asyncio.sleep(0.05)

        # Close connection
        consumer._connection_closed = True

        # Wait for loop to exit (check on next iteration)
        await asyncio.sleep(0.15)

        # Verify task completed
        self.assertTrue(ping_task.done())

    async def test_health_check_respects_connection_closed(self):
        """Test that health check loop stops when connection is closed."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.pong_timeout = 0.1
        consumer._connection_closed = False
        consumer.last_activity = datetime.now(UTC)

        # Start health check loop
        health_task = asyncio.create_task(consumer._health_check_loop())

        # Wait a bit
        await asyncio.sleep(0.05)

        # Close connection
        consumer._connection_closed = True

        # Wait for loop to exit (check on next iteration)
        await asyncio.sleep(0.15)

        # Verify task completed
        self.assertTrue(health_task.done())

    async def test_configuration_from_settings(self):
        """Test that configuration is loaded from Django settings."""
        from django.test import override_settings

        with override_settings(
            WEBSOCKET_PING_INTERVAL=60,
            WEBSOCKET_PONG_TIMEOUT=20,
            WEBSOCKET_CONNECTION_TIMEOUT=600,
        ):
            consumer = EventConsumer()
            consumer.scope = {"user": self.user, "tenant": self.tenant}

            self.assertEqual(consumer.ping_interval, 60)
            self.assertEqual(consumer.pong_timeout, 20)
            self.assertEqual(consumer.connection_timeout, 600)

    async def test_default_configuration_values(self):
        """Test default configuration values when settings not provided."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}

        # Should use defaults
        self.assertEqual(consumer.ping_interval, 30)  # DEFAULT_PING_INTERVAL
        self.assertEqual(consumer.pong_timeout, 10)  # DEFAULT_PONG_TIMEOUT
        self.assertEqual(consumer.connection_timeout, 300)  # DEFAULT_CONNECTION_TIMEOUT

    async def test_ping_loop_handles_send_errors(self):
        """Test that ping loop handles send errors gracefully."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.ping_interval = 0.1
        consumer._connection_closed = False
        consumer.send_json_message = AsyncMock(side_effect=Exception("Send error"))
        consumer.last_activity = datetime.now(UTC)

        # Start ping loop
        ping_task = asyncio.create_task(consumer._ping_loop())

        try:
            # Wait for error to occur
            await asyncio.sleep(0.15)

            # Verify task completed (exited on error)
            self.assertTrue(ping_task.done())
        finally:
            consumer._connection_closed = True

    async def test_health_check_handles_close_errors(self):
        """Test that health check handles close errors gracefully."""
        consumer = EventConsumer()
        consumer.scope = {"user": self.user, "tenant": self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.pong_timeout = 0.1
        consumer.pending_ping = True
        consumer.last_pong_received = datetime.now(UTC) - timedelta(seconds=0.2)
        consumer._connection_closed = False
        consumer.close = AsyncMock(side_effect=Exception("Close error"))

        # Start health check loop
        health_task = asyncio.create_task(consumer._health_check_loop())

        try:
            # Wait for error to occur
            await asyncio.sleep(0.15)

            # Verify task completed (exited on error)
            self.assertTrue(health_task.done())
        finally:
            consumer._connection_closed = True
