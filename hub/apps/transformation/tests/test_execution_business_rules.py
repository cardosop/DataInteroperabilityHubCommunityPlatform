"""
Unit tests for ExecutionBusinessRules.

Tests all execution business rules validation methods using real services and models (no mocks/stubs).
"""
import uuid
from django.test import TestCase
from django.core.cache import cache

from hub.apps.transformation.business_rules import (
    ExecutionBusinessRules,
    ValidationResult
)
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus,
    ExecutionMode
)
from hub.apps.transformation.exceptions import (
    TransformationValidationError,
    ResourceQuotaExceededError
)
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
from django.contrib.auth import get_user_model

User = get_user_model()


class ExecutionBusinessRulesTest(TestCase):
    """Test cases for ExecutionBusinessRules."""

    def setUp(self):
        """Set up test fixtures."""
        tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name=tenant_name,
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

        self.user = User.objects.create_user(
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.business_rules = ExecutionBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create test pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [{"name": "step1", "type": "task"}]
            },
            status=PipelineStatus.ACTIVE
        )

        # Create test asset with dataset
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path="test/test.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=100
        )

    def test_validate_resource_limits_success(self):
        """Test successful resource limit validation."""
        # Clear any existing counters
        running_key = f"job:tenant:{self.tenant.id}:running"
        queued_key = f"job:tenant:{self.tenant.id}:queued"
        cache.set(running_key, 0, timeout=3600)
        cache.set(queued_key, 0, timeout=3600)

        result = self.business_rules.validate_resource_limits(
            pipeline=self.pipeline,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("resource_checks", result.details)
        self.assertFalse(result.details["resource_checks"].get("resource_limit_exceeded", True))

    def test_validate_resource_limits_without_tenant_id(self):
        """Test resource limit validation fails without tenant_id."""
        rules = ExecutionBusinessRules(tenant_id=None)

        result = rules.validate_resource_limits(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_resource_limits_raises_on_error(self):
        """Test that validate_resource_limits raises exception when raise_on_error=True."""
        rules = ExecutionBusinessRules(tenant_id=None)

        with self.assertRaises(TransformationValidationError):
            rules.validate_resource_limits(raise_on_error=True)

    def test_select_execution_mode_sync_small_dataset(self):
        """Test execution mode selection for small dataset (should be SYNC)."""
        # Update dataset to have small row count
        self.dataset.row_count = 5000  # Below SYNC_ROW_THRESHOLD
        self.dataset.save(update_fields=['row_count'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id),
            pipeline=self.pipeline
        )

        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        self.assertEqual(mode, sync_value)

    def test_select_execution_mode_async_large_dataset(self):
        """Test execution mode selection for large dataset (should be ASYNC)."""
        # Update dataset to have large row count
        self.dataset.row_count = 50000  # Above SYNC_ROW_THRESHOLD
        self.dataset.save(update_fields=['row_count'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id),
            pipeline=self.pipeline
        )

        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        self.assertEqual(mode, async_value)

    def test_select_execution_mode_by_file_size(self):
        """Test execution mode selection based on file size."""
        # Set row_count to None to force file size check
        self.dataset.row_count = None
        self.dataset.save(update_fields=['row_count'])

        # Small file size (< 10MB)
        self.file.size = 5 * 1024 * 1024  # 5MB
        self.file.save(update_fields=['size'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )

        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        self.assertEqual(mode, sync_value)

        # Large file size (> 10MB)
        self.file.size = 20 * 1024 * 1024  # 20MB
        self.file.save(update_fields=['size'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )

        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        self.assertEqual(mode, async_value)

    def test_select_execution_mode_force_mode(self):
        """Test execution mode selection with forced mode."""
        # Force SYNC mode
        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id),
            force_mode="SYNC"
        )

        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        self.assertEqual(mode, sync_value)

        # Force ASYNC mode
        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id),
            force_mode="ASYNC"
        )

        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        self.assertEqual(mode, async_value)

    def test_select_execution_mode_no_dataset(self):
        """Test execution mode selection when no dataset exists (should default to ASYNC)."""
        # Delete dataset
        self.dataset.delete()

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )

        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        self.assertEqual(mode, async_value)

    def test_select_execution_mode_invalid_asset(self):
        """Test execution mode selection with invalid asset ID."""
        invalid_asset_id = str(uuid.uuid4())

        with self.assertRaises(TransformationValidationError):
            self.business_rules.select_execution_mode(
                asset_id=invalid_asset_id
            )

    def test_validate_timeout_success(self):
        """Test successful timeout validation."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=300,  # 5 minutes
            execution_mode=ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_timeout_below_minimum(self):
        """Test timeout validation fails when below minimum."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=30,  # Below MIN_TIMEOUT_SECONDS (60)
            raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("below minimum", result.errors[0].lower())

    def test_validate_timeout_above_maximum(self):
        """Test timeout validation fails when above maximum."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=10000,  # Above MAX_TIMEOUT_SECONDS (7200)
            raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeds maximum", result.errors[0].lower())

    def test_validate_timeout_default_for_sync(self):
        """Test timeout validation uses default for SYNC mode."""
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC

        result = self.business_rules.validate_timeout(
            timeout_seconds=None,
            execution_mode=sync_value,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)  # Warning about using default
        self.assertIn("default", result.warnings[0].lower())
        self.assertEqual(
            result.details["timeout_validation"]["timeout_seconds"],
            ExecutionBusinessRules.DEFAULT_SYNC_TIMEOUT
        )

    def test_validate_timeout_default_for_async(self):
        """Test timeout validation uses default for ASYNC mode."""
        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

        result = self.business_rules.validate_timeout(
            timeout_seconds=None,
            execution_mode=async_value,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)  # Warning about using default
        self.assertEqual(
            result.details["timeout_validation"]["timeout_seconds"],
            ExecutionBusinessRules.DEFAULT_ASYNC_TIMEOUT
        )

    def test_validate_timeout_sync_too_long_warning(self):
        """Test timeout validation warns when SYNC timeout is too long."""
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC

        result = self.business_rules.validate_timeout(
            timeout_seconds=4000,  # Longer than DEFAULT_ASYNC_TIMEOUT
            execution_mode=sync_value,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("sync", result.warnings[0].lower())

    def test_validate_timeout_sync_too_short_warning(self):
        """Test timeout validation warns when SYNC timeout is too short."""
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC

        result = self.business_rules.validate_timeout(
            timeout_seconds=60,  # Less than 2 minutes
            execution_mode=sync_value,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)  # Still valid, just warning
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("too short", result.warnings[0].lower())

    def test_validate_timeout_raises_on_error(self):
        """Test that validate_timeout raises exception when raise_on_error=True."""
        with self.assertRaises(TransformationValidationError):
            self.business_rules.validate_timeout(
                timeout_seconds=30,  # Below minimum
                raise_on_error=True
            )

    def test_validate_timeout_no_execution_mode(self):
        """Test timeout validation without execution mode."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=300,
            execution_mode=None,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


class ExecutionModeSelectionTest(TestCase):
    """Test cases specifically for execution mode selection logic."""

    def setUp(self):
        """Set up test fixtures."""
        tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name=tenant_name,
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

        self.user = User.objects.create_user(
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.business_rules = ExecutionBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create test asset
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path="test/test.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1
        )

    def test_execution_mode_selection_at_threshold(self):
        """Test execution mode selection at threshold boundaries."""
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

        # Just below threshold (should be SYNC)
        self.dataset.row_count = ExecutionBusinessRules.SYNC_ROW_THRESHOLD - 1
        self.dataset.save(update_fields=['row_count'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, sync_value)

        # At threshold (should be ASYNC)
        self.dataset.row_count = ExecutionBusinessRules.SYNC_ROW_THRESHOLD
        self.dataset.save(update_fields=['row_count'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, async_value)

        # Just above threshold (should be ASYNC)
        self.dataset.row_count = ExecutionBusinessRules.SYNC_ROW_THRESHOLD + 1
        self.dataset.save(update_fields=['row_count'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, async_value)

    def test_execution_mode_selection_file_size_threshold(self):
        """Test execution mode selection based on file size thresholds."""
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC

        # Set row_count to None to force file size check
        self.dataset.row_count = None
        self.dataset.save(update_fields=['row_count'])

        # Just below threshold (should be SYNC)
        self.file.size = ExecutionBusinessRules.SYNC_SIZE_THRESHOLD - 1
        self.file.save(update_fields=['size'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, sync_value)

        # At threshold (should be ASYNC)
        self.file.size = ExecutionBusinessRules.SYNC_SIZE_THRESHOLD
        self.file.save(update_fields=['size'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, async_value)

        # Just above threshold (should be ASYNC)
        self.file.size = ExecutionBusinessRules.SYNC_SIZE_THRESHOLD + 1
        self.file.save(update_fields=['size'])

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )
        self.assertEqual(mode, async_value)

    def test_execution_mode_selection_resources_unavailable(self):
        """Test execution mode selection when resources are unavailable (should prefer ASYNC)."""
        # Set up small dataset that would normally be SYNC
        self.dataset.row_count = 1000  # Small, would normally be SYNC
        self.dataset.save(update_fields=['row_count'])

        # Simulate resource limits exceeded by setting high counters
        from django.core.cache import cache
        from hub.apps.tenants.services import get_tenant_job_limits

        limits = get_tenant_job_limits(str(self.tenant.id))
        running_key = f"job:tenant:{self.tenant.id}:running"
        queued_key = f"job:tenant:{self.tenant.id}:queued"

        # Set counters to max to simulate resource exhaustion
        cache.set(running_key, limits["max_job_concurrency"], timeout=3600)
        cache.set(queued_key, limits["max_queued_jobs"], timeout=3600)

        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id)
        )

        # Should prefer ASYNC even for small dataset when resources are limited
        async_value = ExecutionMode.ASYNC[0] if isinstance(ExecutionMode.ASYNC, tuple) else ExecutionMode.ASYNC
        self.assertEqual(mode, async_value)

        # Clean up
        cache.set(running_key, 0, timeout=3600)
        cache.set(queued_key, 0, timeout=3600)

    def test_execution_mode_selection_invalid_force_mode(self):
        """Test execution mode selection with invalid force mode (should ignore and auto-select)."""
        # Set up small dataset
        self.dataset.row_count = 1000
        self.dataset.save(update_fields=['row_count'])

        # Try invalid force mode
        mode = self.business_rules.select_execution_mode(
            asset_id=str(self.asset.id),
            force_mode="INVALID_MODE"
        )

        # Should auto-select based on dataset size (SYNC for small dataset)
        sync_value = ExecutionMode.SYNC[0] if isinstance(ExecutionMode.SYNC, tuple) else ExecutionMode.SYNC
        self.assertEqual(mode, sync_value)


class ExecutionBusinessRulesQuotaValidationTest(TestCase):
    """Test cases for ExecutionBusinessRules quota validation methods."""

    def setUp(self):
        """Set up test fixtures."""
        tenant_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant = Tenant.objects.create(
            name=tenant_name,
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

        self.user = User.objects.create_user(
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.business_rules = ExecutionBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Clear any existing counters
        running_key = f"job:tenant:{self.tenant.id}:running"
        queued_key = f"job:tenant:{self.tenant.id}:queued"
        cache.set(running_key, 0, timeout=3600)
        cache.set(queued_key, 0, timeout=3600)

    def test_validate_compute_quota_success(self):
        """Test successful compute quota validation."""
        result = self.business_rules.validate_compute_quota(raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("quota_checks", result.details)
        self.assertFalse(result.details["quota_checks"].get("quota_exceeded", True))
        self.assertIn("max_job_concurrency", result.details["quota_checks"])
        self.assertIn("max_queued_jobs", result.details["quota_checks"])

    def test_validate_compute_quota_without_tenant_id(self):
        """Test compute quota validation fails without tenant_id."""
        rules = ExecutionBusinessRules(tenant_id=None)

        result = rules.validate_compute_quota(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_compute_quota_raises_on_error(self):
        """Test that validate_compute_quota raises exception when raise_on_error=True."""
        rules = ExecutionBusinessRules(tenant_id=None)

        with self.assertRaises(ResourceQuotaExceededError):
            rules.validate_compute_quota(raise_on_error=True)

    def test_validate_compute_quota_concurrency_limit_exceeded(self):
        """Test compute quota validation when concurrency limit is exceeded."""
        from hub.apps.tenants.services import get_tenant_job_limits

        limits = get_tenant_job_limits(str(self.tenant.id))
        running_key = f"job:tenant:{self.tenant.id}:running"

        # Set running count to max to exceed limit
        cache.set(running_key, limits["max_job_concurrency"], timeout=3600)

        result = self.business_rules.validate_compute_quota(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(result.details["quota_checks"].get("quota_exceeded", False))
        self.assertTrue(result.details["quota_checks"].get("concurrency_limit_exceeded", False))
        self.assertIn("concurrent job limit", result.errors[0])

        # Clean up
        cache.set(running_key, 0, timeout=3600)

    def test_validate_compute_quota_queue_limit_exceeded(self):
        """Test compute quota validation when queue limit is exceeded."""
        from hub.apps.tenants.services import get_tenant_job_limits

        limits = get_tenant_job_limits(str(self.tenant.id))
        queued_key = f"job:tenant:{self.tenant.id}:queued"

        # Set queued count to max to exceed limit
        cache.set(queued_key, limits["max_queued_jobs"], timeout=3600)

        result = self.business_rules.validate_compute_quota(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(result.details["quota_checks"].get("quota_exceeded", False))
        self.assertTrue(result.details["quota_checks"].get("queue_limit_exceeded", False))
        self.assertIn("queued job limit", result.errors[0])

        # Clean up
        cache.set(queued_key, 0, timeout=3600)

    def test_validate_compute_quota_raises_resource_quota_exceeded_error(self):
        """Test that validate_compute_quota raises ResourceQuotaExceededError when quota exceeded."""
        from hub.apps.tenants.services import get_tenant_job_limits

        limits = get_tenant_job_limits(str(self.tenant.id))
        running_key = f"job:tenant:{self.tenant.id}:running"

        # Set running count to max to exceed limit
        cache.set(running_key, limits["max_job_concurrency"], timeout=3600)

        with self.assertRaises(ResourceQuotaExceededError) as cm:
            self.business_rules.validate_compute_quota(raise_on_error=True)

        self.assertEqual(
            cm.exception.error_code,
            ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT
        )
        self.assertEqual(cm.exception.details.get("quota_type"), "concurrency")
        self.assertEqual(cm.exception.details.get("limit"), limits["max_job_concurrency"])

        # Clean up
        cache.set(running_key, 0, timeout=3600)

    def test_validate_storage_quota_success(self):
        """Test successful storage quota validation."""
        result = self.business_rules.validate_storage_quota(
            required_storage_bytes=1024 * 1024,  # 1MB
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("quota_checks", result.details)
        self.assertIn("max_file_size_bytes", result.details["quota_checks"])

    def test_validate_storage_quota_without_tenant_id(self):
        """Test storage quota validation fails without tenant_id."""
        rules = ExecutionBusinessRules(tenant_id=None)

        result = rules.validate_storage_quota(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_storage_quota_raises_on_error(self):
        """Test that validate_storage_quota raises exception when raise_on_error=True."""
        rules = ExecutionBusinessRules(tenant_id=None)

        with self.assertRaises(ResourceQuotaExceededError):
            rules.validate_storage_quota(raise_on_error=True)

    def test_validate_storage_quota_file_size_limit_exceeded(self):
        """Test storage quota validation when file size limit is exceeded."""
        from hub.apps.tenants.services import get_tenant_file_size_limit

        max_file_size = get_tenant_file_size_limit(str(self.tenant.id))
        # Request storage that exceeds the limit
        required_storage = max_file_size + 1

        result = self.business_rules.validate_storage_quota(
            required_storage_bytes=required_storage,
            raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(result.details["quota_checks"].get("file_size_limit_exceeded", False))
        self.assertIn("exceeds maximum file size limit", result.errors[0])

    def test_validate_storage_quota_within_limit(self):
        """Test storage quota validation when within limit."""
        from hub.apps.tenants.services import get_tenant_file_size_limit

        max_file_size = get_tenant_file_size_limit(str(self.tenant.id))
        # Request storage within the limit
        required_storage = max_file_size - 1

        result = self.business_rules.validate_storage_quota(
            required_storage_bytes=required_storage,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertFalse(result.details["quota_checks"].get("file_size_limit_exceeded", True))

    def test_validate_storage_quota_no_required_storage(self):
        """Test storage quota validation without required storage (should pass)."""
        result = self.business_rules.validate_storage_quota(
            required_storage_bytes=None,
            raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_storage_quota_raises_resource_quota_exceeded_error(self):
        """Test that validate_storage_quota raises ResourceQuotaExceededError when quota exceeded."""
        from hub.apps.tenants.services import get_tenant_file_size_limit

        max_file_size = get_tenant_file_size_limit(str(self.tenant.id))
        required_storage = max_file_size + 1

        with self.assertRaises(ResourceQuotaExceededError) as cm:
            self.business_rules.validate_storage_quota(
                required_storage_bytes=required_storage,
                raise_on_error=True
            )

        self.assertEqual(
            cm.exception.error_code,
            ResourceQuotaExceededError.ERROR_CODE_STORAGE_LIMIT
        )
        self.assertEqual(cm.exception.details.get("quota_type"), "storage")
        self.assertEqual(cm.exception.details.get("limit"), max_file_size)

    def test_validate_query_quota_success(self):
        """Test successful query quota validation."""
        result = self.business_rules.validate_query_quota(raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("quota_checks", result.details)
        self.assertIn("sparql_query", result.details["quota_checks"])
        self.assertIn("catalog_read", result.details["quota_checks"])

    def test_validate_query_quota_without_tenant_id(self):
        """Test query quota validation fails without tenant_id."""
        rules = ExecutionBusinessRules(tenant_id=None)

        result = rules.validate_query_quota(raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant_id is required", result.errors[0])

    def test_validate_query_quota_raises_on_error(self):
        """Test that validate_query_quota raises exception when raise_on_error=True."""
        rules = ExecutionBusinessRules(tenant_id=None)

        with self.assertRaises(ResourceQuotaExceededError):
            rules.validate_query_quota(raise_on_error=True)

    def test_validate_query_quota_integrates_with_tenant_service(self):
        """Test that validate_query_quota integrates with TenantService quota checking."""
        from hub.apps.rate_limiting.quota import QuotaManager
        from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow

        # Get quota info directly from QuotaManager
        has_sparql_quota, sparql_quota_info = QuotaManager.check_quota(
            tenant_id=str(self.tenant.id),
            category=EndpointCategory.SPARQL_QUERY,
            window=TimeWindow.DAILY
        )

        # Validate using business rules
        result = self.business_rules.validate_query_quota(raise_on_error=False)

        # Check that the quota info matches
        self.assertEqual(
            result.details["quota_checks"]["sparql_query"]["limit"],
            sparql_quota_info.get("limit")
        )
        self.assertEqual(
            result.details["quota_checks"]["sparql_query"]["used"],
            sparql_quota_info.get("used")
        )
        self.assertEqual(
            result.details["quota_checks"]["sparql_query"]["has_quota"],
            has_sparql_quota
        )

    def test_validate_query_quota_checks_both_categories(self):
        """Test that validate_query_quota checks both SPARQL_QUERY and CATALOG_READ categories."""
        result = self.business_rules.validate_query_quota(raise_on_error=False)

        self.assertIn("sparql_query", result.details["quota_checks"])
        self.assertIn("catalog_read", result.details["quota_checks"])
        self.assertIn("limit", result.details["quota_checks"]["sparql_query"])
        self.assertIn("limit", result.details["quota_checks"]["catalog_read"])

    def test_validate_query_quota_raises_resource_quota_exceeded_error(self):
        """Test that validate_query_quota raises ResourceQuotaExceededError when quota exceeded."""
        from hub.apps.rate_limiting.quota import QuotaManager
        from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow

        # Exceed quota by incrementing it beyond the limit
        limit = QuotaManager.check_quota(
            tenant_id=str(self.tenant.id),
            category=EndpointCategory.SPARQL_QUERY,
            window=TimeWindow.DAILY
        )[1].get("limit")

        # Increment quota to exceed limit
        for _ in range(limit + 1):
            QuotaManager.increment_quota(
                tenant_id=str(self.tenant.id),
                category=EndpointCategory.SPARQL_QUERY,
                window=TimeWindow.DAILY
            )

        with self.assertRaises(ResourceQuotaExceededError) as cm:
            self.business_rules.validate_query_quota(raise_on_error=True)

        self.assertEqual(
            cm.exception.error_code,
            ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED
        )
        self.assertEqual(cm.exception.details.get("quota_type"), "query")

        # Clean up - reset quota
        QuotaManager.reset_quota(
            tenant_id=str(self.tenant.id),
            category=EndpointCategory.SPARQL_QUERY,
            window=TimeWindow.DAILY
        )

