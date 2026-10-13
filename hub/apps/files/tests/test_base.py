"""
Base test classes for files tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.services import FileService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


def _ensure_tenant_has_active_subscription(tenant):
    """
    Ensure the tenant has an active subscription so write operations
    (POST/PUT/PATCH/DELETE) are allowed by TenantSuspensionMiddleware.
    Delegates to the core facade (hub.apps.testing.billing_support) —
    the paid billing app registers the real factory; core-only mode has
    no factory and the helper is a no-op (the middleware fails open there).
    """
    from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

    return ensure_tenant_has_active_subscription(tenant)


class FilesTestBase(TestCase):
    """Base test class for files tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure tenant has active subscription with storage limits
        # (required because FileService.create_file enforces plan limits)
        _ensure_tenant_has_active_subscription(self.tenant)

        # Create service
        self.service = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class FilesTransactionTestBase(TestCase):
    """Base test class for files tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure tenant has active subscription with storage limits
        _ensure_tenant_has_active_subscription(self.tenant)

        # Create service
        self.service = FileService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create file
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/test.csv",
            created_by=self.user,
        )


class FilesAPITestBase(FilesTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        _ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class FilesAPITransactionTestBase(FilesTransactionTestBase):
    """Base test class for API tests requiring TransactionTestCase."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        _ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


# ── Redis-availability guard ───────────────────────────────────────────
# Memoized per-session so multiple ``setUp`` / test-method calls share
# one connection probe.

import logging as _logging

_redis_log = _logging.getLogger(__name__)
_redis_available: bool | None = None


def redis_or_skip() -> None:
    """Skip the current test if Redis is unavailable.

    Used by management-command tests that require Redis for
    distributed locking.  Call at the top of ``setUp`` or the test
    method body.  The first call probes and caches the result per
    session; subsequent calls are zero-cost.

    Only connection-level failures trigger a skip — unexpected
    errors (e.g. import errors, misconfiguration) are NOT silenced.
    """
    global _redis_available  # probe-result cache: module global is deliberately mutated once per session

    if _redis_available is not None:
        if not _redis_available:
            import unittest

            raise unittest.SkipTest("Redis unavailable (cached from earlier probe)")
        return

    import redis as _redis

    try:
        from hub.apps.api.middleware.idempotency_utils import get_redis_client

        get_redis_client().ping()
        _redis_available = True
    except (_redis.ConnectionError, _redis.TimeoutError, OSError) as exc:
        _redis_available = False
        _redis_log.info("redis_or_skip: Redis unavailable — tests will skip. %s", exc)
        import unittest

        raise unittest.SkipTest(f"Redis required: {exc}") from exc
    # Any other exception (ImportError, SyntaxError, …) is a real bug
    # and must fail the test, not silently skip.
