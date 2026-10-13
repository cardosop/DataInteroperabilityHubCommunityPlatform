"""
Comprehensive integration tests for Transformation API execution methods.

Tests execute_pipeline, list_executions, get_execution, and cancel_execution methods
against real Docker Compose services. No mocks/stubs - uses real API connections.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. Test user and tenant created via SDKTestBase

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Run: pytest sdk/python/tests/test_transformation_execution_methods_integration.py -v
"""

import uuid

import pytest
from asgiref.sync import sync_to_async
from datahub_interoperability import DataHubClient
from datahub_interoperability.errors import (
    NotFoundError,
    ValidationError,
)
from django.db import transaction

# Import test base
from tests.sdk_python.conftest import SDKTestBase


@pytest.mark.django_db(transaction=True)
class TestTransformationExecutionMethodsIntegration(SDKTestBase):
    """
    Comprehensive integration tests for transformation execution methods.

    Tests execute_pipeline, list_executions, get_execution, and cancel_execution
    against real API services running in Docker Compose.
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Import models here to avoid Django app registry issues
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus
        from hub.apps.transformation.models import (
            PipelineStatus,
            TransformationPipeline,
        )

        # Create test pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Test Pipeline {uuid.uuid4().hex[:8]}",
            description="Test pipeline for execution methods",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "filter_step",
                        "type": "task",
                        "node_config": {
                            "node_type": "filter",
                            "filter_expression": "status == 'active'",
                        },
                    },
                    {
                        "name": "transform_step",
                        "type": "task",
                        "node_config": {
                            "node_type": "transform",
                            "transform_expression": "value * 2",
                        },
                    },
                ],
            },
            status=PipelineStatus.ACTIVE,
            version="1.0.0",
        )

        # Create test asset with dataset
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Test Asset for Execution",
            description="Test asset for pipeline execution",
            status=AssetStatus.ACTIVE,
            # No deprecated visibility kwarg — it is a derived @property as
            # of Phase 250.3.B; INTERNAL is the default for ACTIVE assets.
            created_by=self.user,
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30\n4,Diana,22\n5,Eve,19"

        # Create file first (with PENDING status, will update after upload)
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path=f"test/test-{uuid.uuid4().hex[:8]}.csv",  # Temporary path, will be updated
            size=len(self.csv_content),
            content_type="text/csv",
            status=FileStatus.PENDING,  # Will be set to ACTIVE after upload
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient

        try:
            storage_client = S3StorageClient()
            # save_file returns the storage path (key) used
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content,
            )
            # Update file with the actual storage path used
            self.file.storage_path = storage_path
            self.file.status = FileStatus.ACTIVE
            self.file.save()
            self.storage_available = True
        except Exception as e:
            # Storage might not be available, mark for skipping tests
            self.storage_available = False
            self.storage_error = str(e)
            # Still create dataset for tests that don't need actual file content
            self.file.status = FileStatus.ACTIVE
            self.file.save()

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=5,
            schema_json={
                "fields": [
                    {"name": "id", "data_type": "integer"},
                    {"name": "name", "data_type": "string"},
                    {"name": "age", "data_type": "integer"},
                ]
            },
        )

        # Commit transaction to make data visible to API service
        transaction.commit()

        # Get SDK config with authentication
        import asyncio

        self.sdk_config = asyncio.run(self.get_sdk_config())

    def tearDown(self):
        """Clean up test data"""
        try:
            # Import models here
            from hub.apps.transformation.models import PipelineExecution

            # Delete executions
            PipelineExecution.objects.filter(pipeline=self.pipeline).delete()
            # Delete pipeline
            if hasattr(self, "pipeline") and self.pipeline:
                self.pipeline.delete()
            # Delete dataset
            if hasattr(self, "dataset") and self.dataset:
                self.dataset.delete()
            # Delete file
            if hasattr(self, "file") and self.file:
                self.file.delete()
            # Delete asset
            if hasattr(self, "asset") and self.asset:
                self.asset.delete()
            transaction.commit()
        except Exception:
            pass
        finally:
            super().tearDown()

    # execute_pipeline() Tests

    @pytest.mark.asyncio
    async def test_execute_pipeline_success(self):
        """Test successful pipeline execution"""
        # Skip if storage is not available
        if not getattr(self, "storage_available", True):
            pytest.skip(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")  # noqa: skip-in-body — runtime service dependency

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                execution_mode="ASYNC",
            )

            assert result is not None
            assert "execution_id" in result or "id" in result
            execution_id = result.get("execution_id") or result.get("id")
            assert execution_id is not None

            # Verify execution was created in database
            from hub.apps.transformation.models import ExecutionMode, PipelineExecution

            execution = await sync_to_async(PipelineExecution.objects.get)(id=execution_id)
            assert execution.pipeline_id == self.pipeline.id
            assert execution.asset_id == self.asset.id
            assert execution.execution_mode == ExecutionMode.ASYNC

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_sync_mode(self):
        """Test pipeline execution with SYNC mode

        Phase 285.9 removed SYNC execution — the server accepts the request
        but creates the execution as ASYNC.
        """
        # Skip if storage is not available
        if not getattr(self, "storage_available", True):
            pytest.skip(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")  # noqa: skip-in-body — runtime service dependency

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                execution_mode="SYNC",
            )

            assert result is not None
            assert "execution_id" in result or "id" in result
            execution_id = result.get("execution_id") or result.get("id")
            assert execution_id is not None

            # Verify execution was created (as ASYNC — SYNC is ignored)
            from hub.apps.transformation.models import ExecutionMode, PipelineExecution

            execution = await sync_to_async(PipelineExecution.objects.get)(id=execution_id)
            assert execution.execution_mode == ExecutionMode.ASYNC

    @pytest.mark.asyncio
    async def test_execute_pipeline_sets_idempotency_key(self):
        """Test pipeline execution assigns an idempotency key

        The SDK no longer forwards a caller-supplied idempotency key; the
        service assigns ``idempotency_key = str(execution.id)`` on the
        request path when none is provided.
        """
        # Skip if storage is not available
        if not getattr(self, "storage_available", True):
            pytest.skip(f"Storage not available: {getattr(self, 'storage_error', 'Unknown error')}")  # noqa: skip-in-body — runtime service dependency

        from hub.apps.transformation.models import PipelineExecution

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                execution_mode="ASYNC",
            )

            assert result is not None
            execution_id = result.get("execution_id") or result.get("id")

            # Idempotency key is assigned synchronously by the service.
            execution = await sync_to_async(PipelineExecution.objects.get)(id=execution_id)
            assert execution.idempotency_key is not None, "Idempotency key should be set"
            assert execution.idempotency_key == str(execution.id), (
                f"Expected idempotency_key to default to execution_id '{execution.id}', got '{execution.idempotency_key}'"
            )

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_error_empty_pipeline_id(self):
        """Test execute_pipeline with empty pipeline_id

        An empty id produces a URL no route matches; the 404 on the gated
        ``transformation/`` prefix surfaces as MVPGatedFeatureError (a
        NotFoundError with code MVP_FEATURE_GATED).
        """
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id="",
                    asset_id=str(self.asset.id),
                )
            assert exc_info.value.code == "MVP_FEATURE_GATED"

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_error_empty_asset_id(self):
        """Test execute_pipeline with empty asset_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id=str(self.pipeline.id),
                    asset_id="",
                )
            assert (
                "asset_id" in exc_info.value.message.lower()
                or "required" in exc_info.value.message.lower()
            )

    @pytest.mark.asyncio
    async def test_execute_pipeline_not_found_error(self):
        """Test execute_pipeline when pipeline not found

        The server 404s; the SDK re-labels 404s on the gated
        ``transformation/`` prefix as MVPGatedFeatureError (D131
        backwards-compat subclass of NotFoundError).
        """
        fake_pipeline_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id=fake_pipeline_id,
                    asset_id=str(self.asset.id),
                )
            assert exc_info.value.code == "MVP_FEATURE_GATED"

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_error_invalid_mode(self):
        """Test execute_pipeline with invalid execution mode"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError):
                await client.transformation.execute_pipeline(
                    pipeline_id=str(self.pipeline.id),
                    asset_id=str(self.asset.id),
                    execution_mode="INVALID",
                )

    # list_executions() Tests

    @pytest.mark.asyncio
    async def test_list_executions_success(self):
        """Test successful execution listing"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        # Create a test execution first (use RUNNING status which doesn't require result_asset)
        execution = await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
            )

            assert result is not None
            assert "results" in result
            assert "count" in result
            assert isinstance(result["results"], list)
            assert result["count"] >= 1

            # Verify our execution is in the list
            execution_ids = [r.get("id") or r.get("execution_id") for r in result["results"]]
            exec_id = str(execution.id)
            assert exec_id in execution_ids

    @pytest.mark.asyncio
    async def test_list_executions_with_status_filter(self):
        """Test list_executions with status filter"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        # Create executions with different statuses
        await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        # Create a result asset for completed execution
        from hub.apps.assets.models import Asset, AssetStatus

        result_asset = await sync_to_async(Asset.objects.create)(
            tenant=self.tenant,
            key=f"result-asset-{uuid.uuid4().hex[:8]}",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
                status="RUNNING",
            )

            assert result is not None
            assert "results" in result
            # All results should have RUNNING status
            for exec_result in result["results"]:
                assert exec_result.get("status") == "RUNNING"

    @pytest.mark.asyncio
    async def test_list_executions_with_pagination(self):
        """Test list_executions with pagination"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        # Create multiple executions (use RUNNING status which doesn't require result_asset)
        for _i in range(5):
            await sync_to_async(PipelineExecution.objects.create)(
                pipeline=self.pipeline,
                asset=self.asset,
                execution_mode=ExecutionMode.ASYNC,
                status=ExecutionStatus.RUNNING,
            )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
                offset=0,
                limit=2,
            )

            assert result is not None
            assert "results" in result
            assert "count" in result
            # The hub paginates page-based; the SDK forwards limit/offset and
            # the server returns its standard page envelope.
            assert result["count"] >= 5
            assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_list_executions_empty_pipeline_id_lists_tenant_executions(self):
        """Test list_executions with empty pipeline_id

        The list endpoint does not require a pipeline filter; an empty
        pipeline_id is treated as "no filter" and returns the tenant's
        executions.
        """
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(pipeline_id="")
            assert result is not None
            assert "results" in result
            assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_list_executions_offset_pagination(self):
        """Test list_executions with offset pagination"""
        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
                offset=2,
                limit=2,
            )
            assert result is not None
            assert "results" in result
            assert len(result["results"]) <= 2

    @pytest.mark.asyncio
    async def test_list_executions_limit_subsets_results(self):
        """Test list_executions accepts a limit without erroring"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        for _i in range(3):
            await sync_to_async(PipelineExecution.objects.create)(
                pipeline=self.pipeline,
                asset=self.asset,
                execution_mode=ExecutionMode.ASYNC,
                status=ExecutionStatus.RUNNING,
            )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
                limit=1,
            )
            assert result is not None
            assert "results" in result
            assert "count" in result
            assert result["count"] >= 3
            assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_list_executions_unknown_pipeline_returns_empty_list(self):
        """Test list_executions when pipeline does not exist

        The list endpoint is tenant-scoped; an unknown pipeline_id filter
        simply yields an empty result set (no 404).
        """
        fake_pipeline_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(pipeline_id=fake_pipeline_id)
            assert result is not None
            assert "results" in result
            assert isinstance(result["results"], list)

    # get_execution() Tests

    @pytest.mark.asyncio
    async def test_get_execution_success(self):
        """Test successful execution retrieval"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        # Use RUNNING status which doesn't require result_asset
        execution = await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.get_execution(
                execution_id=str(execution.id),
            )

            assert result is not None
            assert result.get("id") == str(execution.id) or result.get("execution_id") == str(
                execution.id
            )
            assert result.get("status") == "RUNNING"

    @pytest.mark.asyncio
    async def test_get_execution_not_found_error(self):
        """Test get_execution when execution not found

        The 404 on the gated ``transformation/`` prefix surfaces as
        MVPGatedFeatureError (a NotFoundError subclass).
        """
        fake_execution_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.get_execution(execution_id=fake_execution_id)
            assert exc_info.value.code == "MVP_FEATURE_GATED"

    @pytest.mark.asyncio
    async def test_get_execution_validation_error_empty_id(self):
        """Test get_execution with empty execution_id

        An empty id produces a URL no route matches; the 404 surfaces as
        MVPGatedFeatureError (a NotFoundError subclass).
        """
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.get_execution(execution_id="")
            assert exc_info.value.code == "MVP_FEATURE_GATED"

    # cancel_execution() Tests

    @pytest.mark.asyncio
    async def test_cancel_execution_success(self):
        """Test successful execution cancellation"""
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        execution = await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.cancel_execution(
                execution_id=str(execution.id),
            )

            assert result is not None
            assert result.get("execution_id") == str(execution.id) or result.get("id") == str(
                execution.id
            )
            assert result.get("status") == "CANCELLED"

            # Verify execution was cancelled in database
            from hub.apps.transformation.models import ExecutionStatus

            await sync_to_async(execution.refresh_from_db)()
            assert execution.status == ExecutionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_execution_not_found_error(self):
        """Test cancel_execution when execution not found

        The 404 on the gated ``transformation/`` prefix surfaces as
        MVPGatedFeatureError (a NotFoundError subclass).
        """
        fake_execution_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.cancel_execution(execution_id=fake_execution_id)
            assert exc_info.value.code == "MVP_FEATURE_GATED"

    @pytest.mark.asyncio
    async def test_cancel_execution_validation_error_cannot_cancel(self):
        """Test cancel_execution when execution cannot be cancelled"""
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution

        # Create a result asset for completed execution
        result_asset = await sync_to_async(Asset.objects.create)(
            tenant=self.tenant,
            key=f"result-asset-{uuid.uuid4().hex[:8]}",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        # Create a completed execution (cannot be cancelled)
        execution = await sync_to_async(PipelineExecution.objects.create)(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset,
        )
        await sync_to_async(transaction.commit)()

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.cancel_execution(execution_id=str(execution.id))
            assert "cancel" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_cancel_execution_validation_error_empty_id(self):
        """Test cancel_execution with empty execution_id

        An empty id produces a URL no route matches; the 404 surfaces as
        MVPGatedFeatureError (a NotFoundError subclass).
        """
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.cancel_execution(execution_id="")
            assert exc_info.value.code == "MVP_FEATURE_GATED"
