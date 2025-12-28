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
import pytest
import uuid
from typing import Dict, Any
from django.db import transaction

from datahub_interoperability import DataHubClient
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ServerError,
    NetworkError,
)

# Import test base and factories
from tests.sdk_python.conftest import SDKTestBase
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineStatus,
    PipelineExecution,
    ExecutionStatus,
    ExecutionMode,
)
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, File, FileStatus, Dataset
from hub.apps.tenants.models import Tenant


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
                            "filter_expression": "status == 'active'"
                        }
                    },
                    {
                        "name": "transform_step",
                        "type": "task",
                        "node_config": {
                            "node_type": "transform",
                            "transform_expression": "value * 2"
                        }
                    }
                ]
            },
            status=PipelineStatus.ACTIVE,
            version="1.0.0"
        )

        # Create test asset with dataset
        asset_key = f"test-asset-{uuid.uuid4().hex[:8]}"
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=asset_key,
            name="Test Asset for Execution",
            description="Test asset for pipeline execution",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user
        )

        # Create file for dataset
        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path=f"test/test-{uuid.uuid4().hex[:8]}.csv",
            size=1000,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        # Create dataset
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            format="CSV",
            version=1,
            row_count=100
        )

        # Commit transaction to make data visible to API service
        transaction.commit()

        # Get SDK config with authentication
        import asyncio
        self.sdk_config = asyncio.run(self.get_sdk_config())

    def tearDown(self):
        """Clean up test data"""
        try:
            # Delete executions
            PipelineExecution.objects.filter(pipeline=self.pipeline).delete()
            # Delete pipeline
            if hasattr(self, 'pipeline') and self.pipeline:
                self.pipeline.delete()
            # Delete dataset
            if hasattr(self, 'dataset') and self.dataset:
                self.dataset.delete()
            # Delete file
            if hasattr(self, 'file') and self.file:
                self.file.delete()
            # Delete asset
            if hasattr(self, 'asset') and self.asset:
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
            execution = PipelineExecution.objects.get(id=execution_id)
            assert execution.pipeline_id == self.pipeline.id
            assert execution.asset_id == self.asset.id
            assert execution.execution_mode == ExecutionMode.ASYNC

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_sync_mode(self):
        """Test pipeline execution with SYNC mode"""
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

            # Verify execution was created
            execution = PipelineExecution.objects.get(id=execution_id)
            assert execution.execution_mode == ExecutionMode.SYNC

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_idempotency_key(self):
        """Test pipeline execution with idempotency key"""
        idempotency_key = f"test-key-{uuid.uuid4().hex[:8]}"

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                execution_mode="ASYNC",
                idempotency_key=idempotency_key,
            )

            assert result is not None
            execution_id = result.get("execution_id") or result.get("id")

            # Verify idempotency key was set
            execution = PipelineExecution.objects.get(id=execution_id)
            assert execution.idempotency_key == idempotency_key

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_error_empty_pipeline_id(self):
        """Test execute_pipeline with empty pipeline_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id="",
                    asset_id=str(self.asset.id),
                )
            assert "pipeline_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_execute_pipeline_validation_error_empty_asset_id(self):
        """Test execute_pipeline with empty asset_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id=str(self.pipeline.id),
                    asset_id="",
                )
            assert "asset_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_execute_pipeline_not_found_error(self):
        """Test execute_pipeline when pipeline not found"""
        fake_pipeline_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.execute_pipeline(
                    pipeline_id=fake_pipeline_id,
                    asset_id=str(self.asset.id),
                )
            assert "not found" in exc_info.value.message.lower()

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
        # Create a test execution first
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
        )
        transaction.commit()

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
            assert str(execution.id) in execution_ids

    @pytest.mark.asyncio
    async def test_list_executions_with_status_filter(self):
        """Test list_executions with status filter"""
        # Create executions with different statuses
        running_execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        completed_execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
        )
        transaction.commit()

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
        # Create multiple executions
        for i in range(5):
            PipelineExecution.objects.create(
                pipeline=self.pipeline,
                asset=self.asset,
                execution_mode=ExecutionMode.ASYNC,
                status=ExecutionStatus.COMPLETED,
            )
        transaction.commit()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.list_executions(
                pipeline_id=str(self.pipeline.id),
                page=1,
                page_size=2,
            )

            assert result is not None
            assert "results" in result
            assert len(result["results"]) <= 2
            assert result["count"] >= 5

    @pytest.mark.asyncio
    async def test_list_executions_validation_error_empty_pipeline_id(self):
        """Test list_executions with empty pipeline_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.list_executions(pipeline_id="")
            assert "pipeline_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_list_executions_validation_error_invalid_page(self):
        """Test list_executions with invalid page number"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.list_executions(
                    pipeline_id=str(self.pipeline.id),
                    page=0,
                )
            assert "page" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_list_executions_validation_error_invalid_page_size(self):
        """Test list_executions with invalid page_size"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.list_executions(
                    pipeline_id=str(self.pipeline.id),
                    page_size=0,
                )
            assert "page size" in exc_info.value.message.lower() or "page_size" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_list_executions_not_found_error(self):
        """Test list_executions when pipeline not found"""
        fake_pipeline_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError):
                await client.transformation.list_executions(pipeline_id=fake_pipeline_id)

    # get_execution() Tests

    @pytest.mark.asyncio
    async def test_get_execution_success(self):
        """Test successful execution retrieval"""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
        )
        transaction.commit()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.get_execution(
                execution_id=str(execution.id),
            )

            assert result is not None
            assert result.get("id") == str(execution.id) or result.get("execution_id") == str(execution.id)
            assert result.get("status") == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_execution_not_found_error(self):
        """Test get_execution when execution not found"""
        fake_execution_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.get_execution(execution_id=fake_execution_id)
            assert "not found" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_get_execution_validation_error_empty_id(self):
        """Test get_execution with empty execution_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.get_execution(execution_id="")
            assert "execution_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

    # cancel_execution() Tests

    @pytest.mark.asyncio
    async def test_cancel_execution_success(self):
        """Test successful execution cancellation"""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.RUNNING,
        )
        transaction.commit()

        async with DataHubClient(self.sdk_config) as client:
            result = await client.transformation.cancel_execution(
                execution_id=str(execution.id),
            )

            assert result is not None
            assert result.get("execution_id") == str(execution.id) or result.get("id") == str(execution.id)
            assert result.get("status") == "CANCELLED"

            # Verify execution was cancelled in database
            execution.refresh_from_db()
            assert execution.status == ExecutionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_execution_not_found_error(self):
        """Test cancel_execution when execution not found"""
        fake_execution_id = str(uuid.uuid4())

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.transformation.cancel_execution(execution_id=fake_execution_id)
            assert "not found" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_cancel_execution_validation_error_cannot_cancel(self):
        """Test cancel_execution when execution cannot be cancelled"""
        # Create a completed execution (cannot be cancelled)
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
        )
        transaction.commit()

        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.cancel_execution(execution_id=str(execution.id))
            assert "cancel" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_cancel_execution_validation_error_empty_id(self):
        """Test cancel_execution with empty execution_id"""
        async with DataHubClient(self.sdk_config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.transformation.cancel_execution(execution_id="")
            assert "execution_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()

