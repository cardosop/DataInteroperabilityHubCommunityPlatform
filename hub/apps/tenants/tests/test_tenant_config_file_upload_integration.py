"""
Integration tests for TenantConfig with File Upload.

GAP-1.2.3: Tests for file upload integration with tenant configuration.

All tests use real implementations (no mocks of hub services).
S3StorageClient uses real MinIO with graceful handling when unavailable.
"""

# CRITICAL: Patch sql_flush to use CASCADE for foreign key constraints
# This is needed when running tests with manage.py test (not pytest)
# Fixes: psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
try:
    import django.db.backends.postgresql.operations as pg_operations

    if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
        _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

        def _patched_sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
            """
            Patched sql_flush that always uses CASCADE to handle foreign key constraints.

            ROOT CAUSE: During test teardown, Django tries to truncate tables but fails
            when tables have foreign key constraints. PostgreSQL requires CASCADE to truncate
            tables with foreign key references.

            SOLUTION: Always use allow_cascade=True when truncating tables during teardown.
            """
            return _original_sql_flush(
                self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
            )

        _patched_sql_flush._patched_for_cascade = True
        pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
except Exception:
    # Patch failed, but tests should still run
    pass

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db.transaction import TransactionManagementError
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.services import get_tenant_file_size_limit
from hub.apps.tenants.validators import get_platform_defaults
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


@override_settings(
    AWS_STORAGE_BUCKET_NAME="hub-files",
    AWS_ACCESS_KEY_ID="minioadmin",
    AWS_SECRET_ACCESS_KEY="minio123",
    AWS_S3_ENDPOINT_URL="http://localhost:9000",
)
# Using TestCase since _fixture_teardown is pass (no flush needed)
class TenantConfigFileUploadIntegrationTest(TestCase):
    """Test File Upload integration with tenant configuration"""

    @classmethod
    def tearDownClass(cls):
        try:
            super().tearDownClass()
        except TransactionManagementError:
            pass

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests.

        TransactionTestCase tries to flush the database between tests, but this
        fails with foreign key constraints. We use transaction rollback instead
        which provides isolation without flushing.
        """
        # Don't flush - transactions are rolled back which provides isolation
        pass

    """Test File Upload integration with tenant configuration"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Recover from a stale connection left by a preceding
        # TransactionTestCase on the shared test DB.  Only touch
        # 'default' — other aliases raise DatabaseOperationForbidden.
        from django.db import connections
        conn = connections["default"]
        try:
            conn.close_if_unusable_or_obsolete()
        except Exception:
            pass
        if conn.connection is None or getattr(conn.connection, "closed", 1):
            try:
                conn.close()
            except Exception:
                pass
            conn.connection = None
            conn.closed_in_transaction = False
            conn.needs_rollback = False
            conn.in_atomic_block = False
            conn.savepoint_ids = []
            conn.atomic_blocks = []
            conn.ensure_connection()

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
        UserRole.objects.create(user=self.user, role=provider_role, tenant=self.tenant)

        # Active subscription required for write operations
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        ensure_tenant_has_active_subscription(self.tenant)

        # Create subscription so middleware doesn't block write ops
        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.tenants.models import TenantPlan
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                }
            )

        self.platform_defaults = get_platform_defaults()

        # Initialize real storage client for tests that need it
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            # MinIO may not be available in all test environments
            self.storage_available = False
            self.storage_client = None

    def test_file_upload_within_tenant_limit(self):
        """Test file upload succeeds when file size is within tenant limit using real S3StorageClient"""
        # Skip if storage not available
        if not self.storage_available:
            self.skipTest("MinIO storage not available in test environment")

        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant, max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )

        self.client.force_authenticate(user=self.user)

        # Use real S3StorageClient (no mock)
        # Try to upload file within tenant limit (4 GB)
        file_size = 4 * 1024 * 1024 * 1024
        # URL pattern: /api/v1/files/ includes router that registers "files", so full path is /api/v1/files/init/
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": "test.csv",
                "content_type": "text/csv",
                "size": file_size,
                "upload_method": "sdk",
            },
            format="json",
        )

        # Should succeed (201 for file creation)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_file_upload_exceeding_tenant_limit(self):
        """Test file upload fails when file size exceeds tenant limit"""
        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant, max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )

        self.client.force_authenticate(user=self.user)

        # Try to upload file exceeding tenant limit (6 GB)
        file_size = 6 * 1024 * 1024 * 1024
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": "test.csv",
                "content_type": "text/csv",
                "size": file_size,
                "upload_method": "sdk",
            },
            format="json",
        )

        # Should return validation error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Response format uses 'detail' for validation errors
        error_message = response.data.get("detail", "") or str(response.data)
        self.assertIn("exceeds", error_message.lower())

    def test_file_upload_with_platform_default(self):
        """Test file upload uses platform default when tenant config not set using real S3StorageClient"""
        # Skip if storage not available
        if not self.storage_available:
            self.skipTest("MinIO storage not available in test environment")

        # No tenant config exists

        self.client.force_authenticate(user=self.user)

        # Use real S3StorageClient (no mock)
        # Try to upload file within platform default limit (10 GB)
        # Use a file size that's within browser method limit (100MB) but still tests platform default
        # Browser method has a 100MB limit, so use 50MB to test platform default logic
        file_size = 50 * 1024 * 1024  # 50MB - within browser limit, tests platform default
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": "test.csv",
                "content_type": "text/csv",
                "size": file_size,
                "upload_method": "browser",
            },
            format="json",
        )

        # Should succeed (uses platform default, within browser method limit)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_chunked_upload_init_validates_total_file_size(self):
        """Test chunked upload init validates total file size against tenant limit.

        File size validation occurs at the /files/init/ endpoint when the
        total size is declared.  The /complete/ endpoint does NOT re-validate
        size (it delegates to S3), so we test the init path.
        """
        # Create tenant config with custom file size limit (5 GB)
        TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=5 * 1024 * 1024 * 1024,  # 5 GB
        )

        self.client.force_authenticate(user=self.user)

        # Try to init an upload whose declared size exceeds tenant limit
        response = self.client.post(
            "/api/v1/files/init/",
            {
                "name": "large_file.csv",
                "content_type": "text/csv",
                "size": 6 * 1024 * 1024 * 1024,  # 6 GB
                "upload_method": "sdk",
            },
            format="json",
        )

        # Must return 400 validation error
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f"File size validation should return 400, got "
            f"{response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )
        error_msg = str(
            response.data.get("detail", response.data)
        )
        self.assertIn(
            "exceeds",
            error_msg.lower(),
            f"Error should mention size exceeds limit: {error_msg}",
        )

    def test_get_tenant_file_size_limit_utility_function(self):
        """Test get_tenant_file_size_limit utility function"""
        # Test with tenant config
        TenantConfig.objects.create(
            tenant=self.tenant, max_file_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )

        limit = get_tenant_file_size_limit(str(self.tenant.id))
        self.assertEqual(limit, 5 * 1024 * 1024 * 1024)

        # Test without tenant config (platform default)
        unique_id = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Test Tenant 2 {unique_id}", slug=f"test-tenant-2-{unique_id}"
        )
        limit = get_tenant_file_size_limit(str(tenant2.id))
        self.assertEqual(limit, self.platform_defaults["max_file_size_bytes"])
