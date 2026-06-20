"""
Base test classes for WebSocket tests.

Provides two base classes:
- AsyncWebSocketTestCase (TestCase) — fast, for in-memory async tests
- AsyncWebSocketTransactionTestCase — for tests needing cross-thread DB
"""

import uuid

from django.test import TestCase, TransactionTestCase


class _WebSocketTestHelpers:
    """Shared helper methods for WebSocket test cases."""

    def get_unique_tenant_name(self, prefix="Test Tenant"):
        return f"{prefix} {uuid.uuid4().hex[:8]}"

    def get_unique_slug(self, prefix="test-tenant"):
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    def create_unique_tenant(
        self,
        name_prefix="Test Tenant",
        slug_prefix="test-tenant",
        **kwargs,
    ):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.create(
            name=self.get_unique_tenant_name(name_prefix),
            slug=self.get_unique_slug(slug_prefix),
            **kwargs,
        )

    def get_unique_email(self, prefix="test"):
        return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"

    def create_unique_user(
        self,
        tenant=None,
        email_prefix="test",
        **kwargs,
    ):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if tenant is None:
            tenant = self.create_unique_tenant()
        email = self.get_unique_email(email_prefix)
        return User.objects.create_user(
            email=email,
            tenant=tenant,
            **kwargs,
        )

    def create_test_consumer(
        self,
        user=None,
        tenant=None,
        *,
        with_replay: bool = True,
        with_dedup_redis: bool = False,
    ):
        """Create a fully-mocked EventConsumer for unit testing.

        Returns an EventConsumer whose ``send_json_message``, ``send``,
        and ``close`` are all ``AsyncMock`` instances so tests can
        assert on calls without a real WebSocket connection.

        Args:
            user: Override the default test user in ``scope``.
            tenant: Override the default test tenant in ``scope``.
            with_replay: If True (default), set ``replay_enabled``,
                ``replay_window_seconds``, and ``last_event_timestamps``
                so replay-dependent tests work out of the box.
            with_dedup_redis: If True, mock ``_get_deduplication_redis_client``
                to return a ``MagicMock`` (prevents real Redis connections).
        """
        from unittest.mock import AsyncMock, MagicMock
        from datetime import UTC, datetime

        from hub.apps.websocket.consumers.event_consumer import EventConsumer

        consumer = EventConsumer()
        consumer.scope = {"user": user or self.user, "tenant": tenant or self.tenant}
        consumer.channel_name = "test_channel"
        consumer.channel_layer = None
        consumer.send_json_message = AsyncMock()
        consumer.send = AsyncMock()
        consumer.close = AsyncMock()
        consumer.last_activity = datetime.now(UTC)
        consumer._connection_closed = False
        if with_replay:
            consumer.replay_enabled = True
            consumer.replay_window_seconds = 3600
            consumer.last_event_timestamps = {}
        if with_dedup_redis:
            consumer._get_deduplication_redis_client = MagicMock(return_value=None)
        return consumer


class AsyncWebSocketTestCase(_WebSocketTestHelpers, TestCase):
    """Fast base class for async WebSocket tests (in-memory only).

    Uses TestCase (SAVEPOINT-wrapped) for speed.  Tests that need
    cross-thread DB visibility (database_sync_to_async,
    WebsocketCommunicator) must use AsyncWebSocketTransactionTestCase.
    """

    reset_sequences = False


class AsyncWebSocketTransactionTestCase(
    _WebSocketTestHelpers,
    TransactionTestCase,
):
    """Base class for async tests needing cross-thread DB access.

    Uses TransactionTestCase because database_sync_to_async and
    WebsocketCommunicator use separate threads with their own DB
    connections that cannot see SAVEPOINT-scoped data.

    Overrides _fixture_teardown to skip the expensive full-database
    flush (TRUNCATE on 117+ tables).  Since every test uses unique
    UUIDs for tenants/users/keys, rows from different tests never
    collide, so a full flush is unnecessary.
    """

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Skip TransactionTestCase's full DB flush.

        The default flushes ALL tables between tests which takes
        several seconds with 117+ models.  Our tests use unique
        UUIDs so rows never collide; skipping the flush cuts
        ~25s/test overhead.
        """
