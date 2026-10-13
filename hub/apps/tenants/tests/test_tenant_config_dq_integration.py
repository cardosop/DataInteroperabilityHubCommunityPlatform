"""
Integration tests for TenantConfig with DQ service.

GAP-1.2.1.3: Tests for DQ service integration with tenant configuration.

All tests use real implementations (no mocks of hub services).
DQServiceClient uses real service with graceful handling when unavailable.
"""

import contextlib
import uuid

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.db.transaction import TransactionManagementError
from django.test import TestCase
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from rest_framework.test import APIClient

from hub.apps.dq.service_client import DQServiceClient
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def check_dq_service_available():
    """Check if DQ service is available"""
    try:
        client = DQServiceClient()
        is_healthy, _ = client.health_check()
    except (httpx.InvalidURL, RedisError, ValueError):
        return False
    else:
        return is_healthy


# Using TestCase since _fixture_teardown is pass (no flush needed)
class TenantConfigDQIntegrationTest(TestCase):
    """Test DQ service integration with tenant configuration"""

    @classmethod
    def tearDownClass(cls):
        with contextlib.suppress(TransactionManagementError):
            super().tearDownClass()

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def setUpClass(cls):
        # Recover from a stale connection left by a preceding
        # TransactionTestCase on the shared test DB.
        from django.db import connection as db_conn

        raw = db_conn.connection
        if raw is not None and getattr(raw, "closed", 0) != 0:
            db_conn.connection = None
            db_conn.closed_in_transaction = False
        super().setUpClass()

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Recover from a stale connection left by a preceding
        # TransactionTestCase on the shared test DB.  Only touch
        # 'default' — other aliases raise DatabaseOperationForbidden.
        from django.db import connections

        conn = connections["default"]
        with contextlib.suppress(Exception):
            conn.close_if_unusable_or_obsolete()
        if conn.connection is None or getattr(conn.connection, "closed", 1):
            with contextlib.suppress(Exception):
                conn.close()
            conn.connection = None
            conn.closed_in_transaction = False
            conn.needs_rollback = False
            conn.in_atomic_block = False
            conn.savepoint_ids = []
            conn.atomic_blocks = []
            conn.ensure_connection()

        # Drain the DQ job queue so stale jobs from prior test runs
        # don't produce NoSuchKey ERROR logs when the worker processes
        # them against files that no longer exist in MinIO.
        try:
            from django_rq import get_queue

            queue = get_queue("job_critical")
            queue.empty()
        except (ImportError, KeyError, RedisConnectionError):
            pass

        self.client = APIClient()

        # Use unique names to avoid duplicate key violations
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}", slug=f"test-tenant-{unique_id}"
        )

        self.user = User.objects.create_user(
            email=f"user-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Assign DATA_PROVIDER role so user passes permission checks
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.create(user=self.user, role=provider_role)

        # Create subscription so middleware doesn't block write ops
        try:
            from hub.apps.billing.models import Subscription, SubscriptionStatus
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.billing (paid layer) not installed in core-only mode")
        from hub.apps.tenants.models import TenantPlan

        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                },
            )
