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
        self, name_prefix="Test Tenant",
        slug_prefix="test-tenant", **kwargs,
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
        self, tenant=None, email_prefix="test", **kwargs,
    ):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if tenant is None:
            tenant = self.create_unique_tenant()
        email = self.get_unique_email(email_prefix)
        return User.objects.create_user(
            email=email, tenant=tenant, **kwargs,
        )


class AsyncWebSocketTestCase(_WebSocketTestHelpers, TestCase):
    """Fast base class for async WebSocket tests (in-memory only).

    Uses TestCase (SAVEPOINT-wrapped) for speed.  Tests that need
    cross-thread DB visibility (database_sync_to_async,
    WebsocketCommunicator) must use AsyncWebSocketTransactionTestCase.
    """

    reset_sequences = False


class AsyncWebSocketTransactionTestCase(
    _WebSocketTestHelpers, TransactionTestCase,
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
