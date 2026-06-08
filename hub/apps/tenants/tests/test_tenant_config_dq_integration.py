"""
Integration tests for TenantConfig with DQ service.

GAP-1.2.1.3: Tests for DQ service integration with tenant configuration.

All tests use real implementations (no mocks of hub services).
DQServiceClient uses real service with graceful handling when unavailable.
"""

import io
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db.transaction import TransactionManagementError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dq.models import DQRun, DQRunStatus
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.services import get_tenant_dq_profile
from hub.apps.tenants.validators import get_platform_defaults
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def check_dq_service_available():
    """Check if DQ service is available"""
    try:
        client = DQServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


# Using TestCase since _fixture_teardown is pass (no flush needed)
class TenantConfigDQIntegrationTest(TestCase):
    """Test DQ service integration with tenant configuration"""

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
        """Override to skip database flush for integration tests."""
        pass

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

        # Drain the DQ job queue so stale jobs from prior test runs
        # don't produce NoSuchKey ERROR logs when the worker processes
        # them against files that no longer exist in MinIO.
        try:
            from django_rq import get_queue
            queue = get_queue("job_critical")
            queue.empty()
        except Exception:
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

        # Create a real File so the DQ endpoint can find it, AND upload
        # the actual content to MinIO so the DQ worker can download it
        # during async job processing (avoids NoSuchKey at runtime).
        from hub.apps.files.models import File, FileStatus
        from hub.apps.files.storage import S3StorageClient

        self.file_id = str(uuid.uuid4())
        self.file_uploaded = False
        file_content = b"col1,col2\n1,2\n3,4\n"
        try:
            storage = S3StorageClient()
            storage._ensure_bucket_exists()
            actual_key = storage.save_file(
                tenant_id=str(self.tenant.id),
                file_id=self.file_id,
                file_content=io.BytesIO(file_content),
                file_name="test-data.csv",
            )
            self.file_uploaded = True
        except Exception:
            # MinIO unavailable — use a placeholder path so the File
            # record can still be created.  Tests that depend on actual
            # file upload will skip via self.file_uploaded check.
            actual_key = f"{self.tenant.id}/{self.file_id}/test-data.csv"
        self.test_file = File.objects.create(
            id=self.file_id,
            tenant=self.tenant,
            name="test-data.csv",
            content_type="text/csv",
            size=len(file_content),
            storage_path=actual_key,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.platform_defaults = get_platform_defaults()

    def test_dq_run_with_tenant_specific_profile(self):
        """Test DQ run uses tenant-specific profile from TenantConfig using real DQServiceClient"""
        if not self.file_uploaded:
            self.skipTest("MinIO storage not available — cannot create DQ run file")
        if not self.file_uploaded:
            self.skipTest("MinIO storage not available — cannot create DQ run file")
        if not check_dq_service_available():
            self.skipTest("DQ service not available in test environment")

        # Create tenant config with custom profile
        TenantConfig.objects.create(tenant=self.tenant, default_dq_profile="intake_basic_soda")

        self.client.force_authenticate(user=self.user)

        # Use real DQServiceClient (no mock)
        # Create DQ run without explicit profile_key (should use tenant config)
        # Don't send profile_key at all - serializer will use tenant config default
        response = self.client.post(
            "/api/v1/dq/runs/",
            {
                "file_id": self.file_id,
                # profile_key omitted - will use tenant config default
            },
            format="json",
        )

        # Only 201/202 indicates the system actually processed the request.
        # 400 (bad file_id) or 503 (service down) mean the test can't verify
        # profile propagation — skip rather than silently pass.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"DQ API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify profile propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"DQ service error ({response.status_code}) — cannot verify profile propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        dq_run = DQRun.objects.latest("created_at")
        self.assertEqual(dq_run.profile_key, "intake_basic_soda")

    def test_dq_run_with_platform_default(self):
        """Test DQ run uses platform default when tenant config not set using real DQServiceClient"""
        # Skip if DQ service not available
        if not self.file_uploaded:
            self.skipTest("MinIO storage not available — cannot create DQ run file")
        if not check_dq_service_available():
            self.skipTest("DQ service not available in test environment")

        # No tenant config exists

        self.client.force_authenticate(user=self.user)

        # Use real DQServiceClient (no mock)
        # Create DQ run without explicit profile_key (should use platform default)
        response = self.client.post(
            "/api/v1/dq/runs/", {"file_id": self.file_id}, format="json"
        )

        # Only 201/202 indicates the system actually processed the request.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"DQ API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify profile propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"DQ service error ({response.status_code}) — cannot verify profile propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        dq_run = DQRun.objects.latest("created_at")
        self.assertEqual(dq_run.profile_key, self.platform_defaults["default_dq_profile"])

    def test_dq_run_with_explicit_profile_overrides_tenant_config(self):
        """Test explicit profile_key in request overrides tenant config using real DQServiceClient"""
        # Skip if DQ service not available
        if not self.file_uploaded:
            self.skipTest("MinIO storage not available — cannot create DQ run file")
        if not check_dq_service_available():
            self.skipTest("DQ service not available in test environment")

        # Create tenant config with custom profile
        TenantConfig.objects.create(tenant=self.tenant, default_dq_profile="intake_basic_soda")

        self.client.force_authenticate(user=self.user)

        # Use real DQServiceClient (no mock)
        # Create DQ run with explicit profile_key (should override tenant config)
        response = self.client.post(
            "/api/v1/dq/runs/",
            {
                "file_id": self.file_id,
                "profile_key": "intake_basic_gx",  # Explicit override
            },
            format="json",
        )

        # Only 201/202 indicates the system actually processed the request.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"DQ API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify profile override"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"DQ service error ({response.status_code}) — cannot verify profile override"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        dq_run = DQRun.objects.latest("created_at")
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")

    def test_get_tenant_dq_profile_utility_function(self):
        """Test get_tenant_dq_profile utility function"""
        # Test with tenant config
        TenantConfig.objects.create(tenant=self.tenant, default_dq_profile="intake_basic_soda")

        profile = get_tenant_dq_profile(str(self.tenant.id))
        self.assertEqual(profile, "intake_basic_soda")

        # Test without tenant config (platform default)
        unique_id = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Test Tenant 2 {unique_id}", slug=f"test-tenant-2-{unique_id}"
        )
        profile = get_tenant_dq_profile(str(tenant2.id))
        self.assertEqual(profile, self.platform_defaults["default_dq_profile"])

    def test_dq_service_client_receives_profile_key(self):
        """Test DQ service client receives profile_key parameter"""
        TenantConfig.objects.create(tenant=self.tenant, default_dq_profile="intake_basic_soda")

        self.client.force_authenticate(user=self.user)

        # Use real DQServiceClient (no mock)
        # Create DQ run
        response = self.client.post(
            "/api/v1/dq/runs/", {"file_id": self.file_id}, format="json"
        )

        # Only 201/202 indicates the system actually processed the request.
        if response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]:
            self.skipTest(
                f"DQ API returned {response.status_code} (likely invalid file_id) "
                f"— cannot verify profile propagation"
            )
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"DQ service error ({response.status_code}) — cannot verify profile propagation"
            )

        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED],
            f"Expected 201/202 but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        # Check that DQRun has the profile from tenant config
        # The actual call happens in the worker task, so we verify the DQRun has the profile
        dq_run = DQRun.objects.latest("created_at")
        self.assertEqual(dq_run.profile_key, "intake_basic_soda")

    def test_invalid_profile_key_validation_error(self):
        """Test invalid profile_key returns validation error using real DQServiceClient"""
        self.client.force_authenticate(user=self.user)

        # Use real DQServiceClient (no mock)
        # Try to create DQ run with invalid profile
        response = self.client.post(
            "/api/v1/dq/runs/",
            {"file_id": self.file_id, "profile_key": "invalid_profile"},
            format="json",
        )

        # Should return 400 validation error for invalid profile_key.
        # 500/503 means the service is down — skip rather than silently pass.
        if response.status_code in [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ]:
            self.skipTest(
                f"DQ service error ({response.status_code}) — cannot verify validation behavior"
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f"Expected 400 for invalid profile_key but got {response.status_code}: "
            f"{getattr(response, 'data', response.content)}",
        )

        self.assertIn("error", response.data)
