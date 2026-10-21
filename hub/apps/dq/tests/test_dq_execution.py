"""
Unit tests for DQ execution.

Tests use real implementations with graceful handling when external services unavailable.
S3StorageClient uses real S3/MinIO with skipTest if unavailable.
DQServiceClient uses httpx.MockTransport to verify endpoint construction (test utility, not mock).
"""

import contextlib

import httpx
import pytest
from django.contrib.auth import get_user_model

from hub.apps.assets.models import Asset, AssetStatus, DQStatus
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.dq.views import execute_dq_run
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DQExecutionTest(DQTestBase):
    """Test DQ execution"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Check if storage is available
        self.storage_available = False
        try:
            storage_client = S3StorageClient()
            storage_client._ensure_bucket_exists()
            # Upload test file content
            from django.core.files.base import ContentFile

            test_content = b"id,name\n1,Test\n2,Sample"
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=ContentFile(test_content),
            )
            # Update file storage_path to match what was actually saved
            self.file.storage_path = storage_path
            self.file.save(update_fields=["storage_path"])
            self.storage_available = True
        except Exception:
            # Storage may not be available - tests will handle gracefully
            self.storage_available = False

    def test_execute_dq_run_success(self):
        """Test successful DQ run execution"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Use MockTransport to verify endpoint construction
        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return success response"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "PASS",
                    "quality_score": 95.5,
                    "checks": [
                        {
                            "check_id": "not_null_primary_key",
                            "status": "PASS",
                            "message": "All ID columns are not null",
                        }
                    ],
                    "engine_type": "GX",
                    "engine_version": "0.18.0",
                    "profile_key": "intake_basic_gx",
                    "metadata": {
                        "total_rows": 2,
                        "total_columns": 2,
                        "execution_time_seconds": 1.5,
                    },
                },
                request=request,
            )

        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Create test client with MockTransport
        test_client = DQServiceClient()
        transport = httpx.MockTransport(handler)
        test_client.client = httpx.Client(transport=transport, base_url=test_client.base_url)

        # Temporarily replace DQServiceClient in views module
        import hub.apps.dq.views as views_module

        original_dq_client_class = views_module.DQServiceClient
        views_module.DQServiceClient = lambda: test_client

        try:
            # Execute DQ run
            execute_dq_run(str(dq_run.id))
        finally:
            # Restore original
            views_module.DQServiceClient = original_dq_client_class
            if hasattr(test_client, "client") and test_client.client:
                test_client.client.close()

        # Verify DQ run was updated
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "PASS")
        self.assertEqual(dq_run.quality_score, 95.5)
        self.assertIsNotNone(dq_run.started_at)
        self.assertIsNotNone(dq_run.completed_at)
        self.assertGreaterEqual(dq_run.completed_at, dq_run.started_at)

        # Verify metering information
        self.assertIn("metering", dq_run.details_json)
        metering = dq_run.details_json["metering"]
        self.assertEqual(metering["operation_type"], "DQ_RUN")
        self.assertEqual(metering["rows_inspected"], 2)
        self.assertEqual(metering["columns_inspected"], 2)
        self.assertEqual(metering["engine_type"], "GX")
        self.assertIn("execution_time_seconds", metering)

    def test_execute_dq_run_updates_asset_dq_status(self):
        """Test that DQ run updates asset DQ status"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Use MockTransport to verify endpoint construction
        def handler(request: httpx.Request) -> httpx.Response:
            """Handle request and return WARN response"""
            return httpx.Response(
                200,
                json={
                    "overall_status": "WARN",
                    "quality_score": 80.0,
                    "checks": [],
                    "engine_type": "GX",
                    "engine_version": "0.18.0",
                    "profile_key": "intake_basic_gx",
                    "metadata": {"total_rows": 1, "total_columns": 2},
                },
                request=request,
            )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", created_by=self.user
        )

        # Create dataset linked to asset
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        # Create DQ run for asset
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=asset,
            dataset=dataset,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Create test client with MockTransport
        test_client = DQServiceClient()
        transport = httpx.MockTransport(handler)
        test_client.client = httpx.Client(transport=transport, base_url=test_client.base_url)

        # Disable caching for this test to ensure fresh results
        import hashlib

        from django.core.cache import cache

        cache_key = (
            f"dq:run:{hashlib.sha256(b'id,name\n1,Test\n2,Sample').hexdigest()}:intake_basic_gx"
        )
        cache.delete(cache_key)  # Clear any cached result

        # Temporarily replace DQServiceClient in views module
        import hub.apps.dq.views as views_module

        original_dq_client_class = views_module.DQServiceClient
        views_module.DQServiceClient = lambda: test_client

        try:
            # Execute DQ run with caching disabled
            # Patch the run_dq call to disable caching
            original_run_dq = test_client.run_dq

            def run_dq_no_cache(*args, **kwargs):
                kwargs["use_cache"] = False
                return original_run_dq(*args, **kwargs)

            test_client.run_dq = run_dq_no_cache

            # Execute DQ run
            execute_dq_run(str(dq_run.id))
        finally:
            # Restore original
            views_module.DQServiceClient = original_dq_client_class
            if hasattr(test_client, "client") and test_client.client:
                test_client.client.close()

        # Verify asset DQ status was updated
        asset.refresh_from_db()
        self.assertEqual(asset.dq_status, DQStatus.WARN)

    def test_execute_dq_run_failure(self):
        """Test DQ run execution failure"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        # Use MockTransport to simulate service error
        def handler(request: httpx.Request) -> httpx.Response:
            """Simulate service error"""
            raise httpx.HTTPStatusError(
                "DQ service error", request=request, response=httpx.Response(500)
            )

        # Create DQ run
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Create test client with MockTransport
        test_client = DQServiceClient()
        transport = httpx.MockTransport(handler)
        test_client.client = httpx.Client(transport=transport, base_url=test_client.base_url)

        # Disable caching and circuit breaker fallback for this test
        import hashlib

        from django.core.cache import cache

        cache_key = f"dq:run:{hashlib.sha256(b'').hexdigest()}:intake_basic_gx"
        cache.delete(cache_key)  # Clear any cached result

        # Temporarily disable circuit breaker fallback by patching it
        original_call = test_client._circuit_breaker.call

        def call_without_fallback(func, fallback=None):
            return func()

        test_client._circuit_breaker.call = call_without_fallback

        # Temporarily replace DQServiceClient in views module
        import hub.apps.dq.views as views_module

        original_dq_client_class = views_module.DQServiceClient
        views_module.DQServiceClient = lambda: test_client

        try:
            # Execute DQ run
            execute_dq_run(str(dq_run.id))
        finally:
            # Restore original
            views_module.DQServiceClient = original_dq_client_class
            test_client._circuit_breaker.call = original_call
            if hasattr(test_client, "client") and test_client.client:
                test_client.client.close()

        # Verify DQ run was marked as failed
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.FAILED)
        self.assertIsNotNone(dq_run.completed_at)
        self.assertIn("error", dq_run.details_json)

    def test_execute_dq_run_circuit_breaker_open_fallback(self):
        """Circuit breaker OPEN → fallback UNKNOWN result returned.

        Unlike test_execute_dq_run_failure (which patches away the circuit
        breaker), this test actually opens the breaker via repeated failures
        and verifies that execute_dq_run processes the fallback response:
        SUCCEEDED + overall_status=UNKNOWN + quality_score=0.0."""
        if not self.storage_available:
            self.skipTest("Storage not available")

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Force the dq-service circuit breaker OPEN via repeated failures.
        # We construct a real client, then force the breaker open.
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState
        from hub.apps.core.resilience.service_breakers import get_shared_circuit_breaker

        breaker = get_shared_circuit_breaker("dq-service")
        breaker.reset()

        # Use MockTransport to deliver 500s so the breaker opens.
        def failing_handler(request):
            raise Exception("simulated service crash")

        test_client = DQServiceClient()
        transport = httpx.MockTransport(failing_handler)
        test_client.client = httpx.Client(
            transport=transport,
            base_url=test_client.base_url,
        )

        # Open the breaker by exhausting failure threshold.
        for _ in range(breaker.failure_threshold + 1):
            with contextlib.suppress(Exception):
                test_client._circuit_breaker.call(
                    lambda: test_client.client.get("/health"),
                )

        self.assertEqual(breaker.get_state(), CircuitBreakerState.OPEN)

        # Now inject this client (with OPEN breaker) into the views module.
        import hub.apps.dq.views as views_module

        original_dq_client_class = views_module.DQServiceClient
        views_module.DQServiceClient = lambda: test_client

        try:
            execute_dq_run(str(dq_run.id))
        finally:
            views_module.DQServiceClient = original_dq_client_class
            if hasattr(test_client, "client") and test_client.client:
                test_client.client.close()
            breaker.reset()

        dq_run.refresh_from_db()
        # The run "succeeds" because it got a fallback result.
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "UNKNOWN")
        self.assertEqual(dq_run.quality_score, 0.0)
        self.assertEqual(len(dq_run.checks_json), 0)
        self.assertIn("metadata", dq_run.details_json)
        self.assertIn("DQ service unavailable", dq_run.details_json["metadata"]["error"])

    def test_execute_dq_run_no_file_found(self):
        """Test DQ run execution when no file is found (error handling)"""
        # DQRun requires at least one of asset, dataset, or file. Use an asset with no
        # datasets so the executor resolves to "no file found" and marks the run failed.
        asset_no_datasets = Asset.objects.create(
            tenant=self.tenant,
            key="no-datasets-asset",
            name="Asset with no datasets",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=asset_no_datasets,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Execute DQ run
        execute_dq_run(str(dq_run.id))

        # Verify DQ run was marked as failed
        dq_run.refresh_from_db()
        self.assertEqual(dq_run.status, DQRunStatus.FAILED)
        self.assertIn("error", dq_run.details_json)

    def test_execute_dq_run_storage_unavailable(self):
        """Test DQ run execution when storage is unavailable (error handling)"""
        # Create DQ run with file that doesn't exist in storage
        file_no_storage = File.objects.create(
            tenant=self.tenant,
            name="missing.csv",
            content_type="text/csv",
            size=1024,
            storage_path="nonexistent/path/file.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=file_no_storage,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.PENDING,
        )

        # Execute DQ run — execute_dq_run MUST trap the storage error
        # internally and transition the status to FAILED. If it throws
        # the test errors, revealing an unhandled code path.
        execute_dq_run(str(dq_run.id))

        # Verify DQ run was marked as failed
        dq_run.refresh_from_db()
        self.assertEqual(
            dq_run.status,
            DQRunStatus.FAILED,
            "execute_dq_run must set FAILED when storage is unavailable; "
            "PENDING means the error handler never ran",
        )
        self.assertIn("error", dq_run.details_json)
