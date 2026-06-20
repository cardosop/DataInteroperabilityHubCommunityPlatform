"""
Base test classes for contracts tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


class ContractsTestBase(TestCase):
    """Base test class for contracts tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()

        uid = uuid.uuid4().hex[:8]
        # Create tenant with unique name (reuse-db + transaction=True compatibility)
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create services
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))


class ContractsTransactionTestBase(TransactionTestCase):
    """Base test class for contracts tests requiring TransactionTestCase.

    Uses targeted cleanup instead of TRUNCATE CASCADE to avoid >60s timeouts
    from cascading FK deletes. Each test creates unique tenant/user via UUID,
    and tearDown deletes only that tenant's contracts.
    """

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE which causes >30s timeouts with many FK relationships.

        Isolation is maintained by unique UUID-based tenant/user names in setUp.
        The hub/conftest.py resilient teardown handler re-seeds plans after flush
        for classes that do run the default teardown.
        """

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        from django.db import connection as _conn

        # TransactionTestCase truncates tables in super().setUp(), which can
        # close the server-side TCP connection.  ``connect()`` forces a fresh
        # psycopg2 connection so Tenant.objects.create() doesn't hit
        # "connection already closed" from a dead pooled connection.
        _conn.connect()
        # The hub_test_test_shared database has lock_timeout=5s (production
        # setting).  In tests, each contract save triggers synchronous Redis
        # operations (cache invalidation + RQ enqueue) that can take 1-3s,
        # so a 5s lock_timeout causes spurious LockNotAvailable when tests
        # run back-to-back.  Raise to 30s (matching pytest-timeout) on this
        # connection so locks are released naturally rather than aborting.
        try:
            _conn.ensure_connection()
            with _conn.cursor() as cur:
                cur.execute("SET lock_timeout = '30s'")
        except Exception:
            pass

        uid = uuid.uuid4().hex[:8]
        # Create tenant with unique name (reuse-db compatibility)
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create services
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def tearDown(self):
        """Close all DB connections to release locks held by threads."""
        connections.close_all()
        super().tearDown()


class ContractsAPITestBase(ContractsTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Grant platform admin so API role-based permission checks
        # (e.g. AssetViewSet requires DATA_PROVIDER or TENANT_ADMIN) pass.
        if not self.user.is_platform_admin:
            self.user.is_platform_admin = True
            self.user.save(update_fields=["is_platform_admin"])
        # Active subscription required so TenantSuspensionMiddleware allows writes (POST/PATCH/DELETE).
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


def get_real_redis_client_or_none():
    """Get real Redis client or return None if unavailable.

    Shared across test files to avoid duplication.
    Used by test_ref_warming.py, test_odps_rate_limiting.py,
    test_odps_metrics.py, and test_caching_enhanced.py.
    """
    import redis as _redis
    from django.conf import settings

    try:
        redis_url = getattr(settings, "REDIS_URL", None) or "redis://redis-cache-test:6379/0"
        client = _redis.from_url(
            redis_url, decode_responses=False, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception:
        return None


def check_datacontract_cli_available():
    """Check if DataContract CLI service is available.

    Only catches transport exceptions — import errors and programming
    mistakes bubble up instead of being silently masked.

    Canonical definition; import from here in test files.
    """
    import httpx as _httpx

    from hub.apps.contracts.cli_client import DataContractCLIClient as _CLIClient

    try:
        client = _CLIClient()
        health = client.health_check()
        return isinstance(health, dict) and health.get("status") == "healthy"
    except (_httpx.ConnectError, _httpx.TimeoutException, ConnectionError, TimeoutError, OSError):
        return False


class ContractsAPITransactionTestBase(ContractsTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        # Grant platform admin so API role-based permission checks pass.
        if not self.user.is_platform_admin:
            self.user.is_platform_admin = True
            self.user.save(update_fields=["is_platform_admin"])
        # Active subscription required so TenantSuspensionMiddleware allows writes (POST/PATCH/DELETE).
        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
