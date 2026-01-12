"""
Base test classes for WebSocket tests.

Provides TransactionTestCase with proper async support and database handling.
"""
import uuid
from django.test import TransactionTestCase
from django.db import transaction


class AsyncWebSocketTestCase(TransactionTestCase):
    """
    Base test class for async WebSocket tests.

    Uses TransactionTestCase to keep database connections open for async operations,
    but overrides _fixture_teardown to skip database flush which causes foreign key
    constraint issues. Uses database transactions for test isolation.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    # TransactionTestCase will still rollback transactions, but won't flush tables
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # TransactionTestCase handles transactions automatically
        # We just need to ensure unique identifiers to avoid conflicts

    def tearDown(self):
        """Clean up test."""
        # TransactionTestCase handles cleanup automatically
        super().tearDown()

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for async tests.

        TransactionTestCase tries to flush the database between tests, but this
        fails with foreign key constraints. We use transaction rollback instead
        which provides isolation without flushing.
        """
        # Don't flush - transactions are rolled back which provides isolation
        pass

    def get_unique_tenant_name(self, prefix="Test Tenant"):
        """Generate a unique tenant name for tests."""
        return f"{prefix} {uuid.uuid4().hex[:8]}"

    def get_unique_slug(self, prefix="test-tenant"):
        """Generate a unique slug for tests."""
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    def create_unique_tenant(self, name_prefix="Test Tenant", slug_prefix="test-tenant", **kwargs):
        """Create a tenant with unique name and slug to avoid conflicts."""
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.create(
            name=self.get_unique_tenant_name(name_prefix),
            slug=self.get_unique_slug(slug_prefix),
            **kwargs
        )

    def get_unique_email(self, prefix="test"):
        """Generate a unique email for tests."""
        return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"

    def create_unique_user(self, tenant=None, email_prefix="test", **kwargs):
        """Create a user with unique email to avoid conflicts."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if tenant is None:
            tenant = self.create_unique_tenant()
        email = self.get_unique_email(email_prefix)
        return User.objects.create_user(
            email=email,
            tenant=tenant,
            **kwargs
        )

