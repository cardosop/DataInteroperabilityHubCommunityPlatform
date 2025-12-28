"""
Comprehensive tests for Transformation API execution methods.

Tests execute_pipeline, list_executions, get_execution, and cancel_execution methods
with proper error handling and edge cases.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datahub_interoperability import DataHubClient, DataHubClientConfig, TransformationAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ServerError,
    NetworkError,
)


@pytest.fixture
def config():
    """Test configuration"""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        timeout=30.0,
        max_retries=3,
        user_agent="test-agent",
        enable_logging=False,
    )


@pytest.fixture
async def client(config):
    """Test client"""
    async with DataHubClient(config) as client:
        yield client


@pytest.fixture
def transformation_api(client):
    """Test transformation API"""
    return TransformationAPI(client)


# execute_pipeline() Tests

@pytest.mark.asyncio
async def test_execute_pipeline_success(transformation_api):
    """Test successful pipeline execution"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    expected_response = {
        "execution_id": execution_id,
        "status": "PENDING",
        "pipeline_id": pipeline_id,
        "asset_id": asset_id,
    }

    transformation_api.client.post = AsyncMock(return_value=expected_response)

    result = await transformation_api.execute_pipeline(
        pipeline_id=pipeline_id,
        asset_id=asset_id,
    )

    assert result == expected_response
    transformation_api.client.post.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/execute/",
        data={"asset_id": asset_id, "execution_mode": "ASYNC"},
    )


@pytest.mark.asyncio
async def test_execute_pipeline_with_execution_mode(transformation_api):
    """Test pipeline execution with explicit execution mode"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    expected_response = {
        "execution_id": execution_id,
        "status": "RUNNING",
        "pipeline_id": pipeline_id,
        "asset_id": asset_id,
    }

    transformation_api.client.post = AsyncMock(return_value=expected_response)

    result = await transformation_api.execute_pipeline(
        pipeline_id=pipeline_id,
        asset_id=asset_id,
        execution_mode="SYNC",
    )

    assert result == expected_response
    transformation_api.client.post.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/execute/",
        data={"asset_id": asset_id, "execution_mode": "SYNC"},
    )


@pytest.mark.asyncio
async def test_execute_pipeline_with_additional_params(transformation_api):
    """Test pipeline execution with additional parameters"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    idempotency_key = "test-key-123"

    expected_response = {
        "execution_id": execution_id,
        "status": "PENDING",
        "pipeline_id": pipeline_id,
        "asset_id": asset_id,
    }

    transformation_api.client.post = AsyncMock(return_value=expected_response)

    result = await transformation_api.execute_pipeline(
        pipeline_id=pipeline_id,
        asset_id=asset_id,
        idempotency_key=idempotency_key,
    )

    assert result == expected_response
    transformation_api.client.post.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/execute/",
        data={
            "asset_id": asset_id,
            "execution_mode": "ASYNC",
            "idempotency_key": idempotency_key,
        },
    )


@pytest.mark.asyncio
async def test_execute_pipeline_validation_error_empty_pipeline_id(transformation_api):
    """Test execute_pipeline with empty pipeline_id"""
    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.execute_pipeline(
            pipeline_id="",
            asset_id=str(uuid.uuid4()),
        )
    assert "pipeline_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_execute_pipeline_validation_error_empty_asset_id(transformation_api):
    """Test execute_pipeline with empty asset_id"""
    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.execute_pipeline(
            pipeline_id=str(uuid.uuid4()),
            asset_id="",
        )
    assert "asset_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_execute_pipeline_not_found_error(transformation_api):
    """Test execute_pipeline when pipeline not found"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=NotFoundError("Pipeline not found")
    )

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.execute_pipeline(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
        )
    assert "not found" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_execute_pipeline_validation_error_invalid_mode(transformation_api):
    """Test execute_pipeline with invalid execution mode"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=ValidationError("Invalid execution mode")
    )

    with pytest.raises(ValidationError):
        await transformation_api.execute_pipeline(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            execution_mode="INVALID",
        )


@pytest.mark.asyncio
async def test_execute_pipeline_network_error(transformation_api):
    """Test execute_pipeline with network error"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=NetworkError("Network error occurred")
    )

    with pytest.raises(NetworkError):
        await transformation_api.execute_pipeline(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
        )


@pytest.mark.asyncio
async def test_execute_pipeline_server_error(transformation_api):
    """Test execute_pipeline with server error"""
    pipeline_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=ServerError("Internal server error", "INTERNAL_ERROR", 500)
    )

    with pytest.raises(ServerError):
        await transformation_api.execute_pipeline(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
        )


# list_executions() Tests

@pytest.mark.asyncio
async def test_list_executions_success(transformation_api):
    """Test successful execution listing"""
    pipeline_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    expected_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": execution_id,
                "status": "COMPLETED",
                "pipeline_id": pipeline_id,
            }
        ],
    }

    transformation_api.client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.list_executions(pipeline_id=pipeline_id)

    assert result == expected_response
    transformation_api.client.get.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/executions/",
        params={"page": 1, "page_size": 20},
    )


@pytest.mark.asyncio
async def test_list_executions_with_status_filter(transformation_api):
    """Test list_executions with status filter"""
    pipeline_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())

    expected_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": execution_id,
                "status": "RUNNING",
                "pipeline_id": pipeline_id,
            }
        ],
    }

    transformation_api.client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.list_executions(
        pipeline_id=pipeline_id,
        status="RUNNING",
    )

    assert result == expected_response
    transformation_api.client.get.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/executions/",
        params={"page": 1, "page_size": 20, "status": "RUNNING"},
    )


@pytest.mark.asyncio
async def test_list_executions_with_pagination(transformation_api):
    """Test list_executions with pagination"""
    pipeline_id = str(uuid.uuid4())

    expected_response = {
        "count": 50,
        "next": 2,
        "previous": None,
        "results": [],
    }

    transformation_api.client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.list_executions(
        pipeline_id=pipeline_id,
        page=1,
        page_size=25,
    )

    assert result == expected_response
    transformation_api.client.get.assert_called_once_with(
        f"transformation/pipelines/{pipeline_id}/executions/",
        params={"page": 1, "page_size": 25},
    )


@pytest.mark.asyncio
async def test_list_executions_validation_error_empty_pipeline_id(transformation_api):
    """Test list_executions with empty pipeline_id"""
    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.list_executions(pipeline_id="")
    assert "pipeline_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_list_executions_validation_error_invalid_page(transformation_api):
    """Test list_executions with invalid page number"""
    pipeline_id = str(uuid.uuid4())

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.list_executions(
            pipeline_id=pipeline_id,
            page=0,
        )
    assert "page" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_list_executions_validation_error_invalid_page_size(transformation_api):
    """Test list_executions with invalid page_size"""
    pipeline_id = str(uuid.uuid4())

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.list_executions(
            pipeline_id=pipeline_id,
            page_size=0,
        )
    assert "page size" in exc_info.value.message.lower() or "page_size" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_list_executions_validation_error_page_size_too_large(transformation_api):
    """Test list_executions with page_size exceeding maximum"""
    pipeline_id = str(uuid.uuid4())

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.list_executions(
            pipeline_id=pipeline_id,
            page_size=101,
        )
    assert "100" in exc_info.value.message or "exceed" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_list_executions_not_found_error(transformation_api):
    """Test list_executions when pipeline not found"""
    pipeline_id = str(uuid.uuid4())

    transformation_api.client.get = AsyncMock(
        side_effect=NotFoundError("Pipeline not found")
    )

    with pytest.raises(NotFoundError):
        await transformation_api.list_executions(pipeline_id=pipeline_id)


# get_execution() Tests

@pytest.mark.asyncio
async def test_get_execution_success(transformation_api):
    """Test successful execution retrieval"""
    execution_id = str(uuid.uuid4())
    pipeline_id = str(uuid.uuid4())

    expected_response = {
        "id": execution_id,
        "status": "COMPLETED",
        "pipeline_id": pipeline_id,
        "asset_id": str(uuid.uuid4()),
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:01:00Z",
    }

    transformation_api.client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.get_execution(execution_id=execution_id)

    assert result == expected_response
    transformation_api.client.get.assert_called_once_with(
        f"transformation/executions/{execution_id}/"
    )


@pytest.mark.asyncio
async def test_get_execution_not_found_error(transformation_api):
    """Test get_execution when execution not found"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.get = AsyncMock(
        side_effect=NotFoundError("Execution not found")
    )

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.get_execution(execution_id=execution_id)
    assert "not found" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_get_execution_validation_error_empty_id(transformation_api):
    """Test get_execution with empty execution_id"""
    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.get_execution(execution_id="")
    assert "execution_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_get_execution_network_error(transformation_api):
    """Test get_execution with network error"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.get = AsyncMock(
        side_effect=NetworkError("Network error occurred")
    )

    with pytest.raises(NetworkError):
        await transformation_api.get_execution(execution_id=execution_id)


# cancel_execution() Tests

@pytest.mark.asyncio
async def test_cancel_execution_success(transformation_api):
    """Test successful execution cancellation"""
    execution_id = str(uuid.uuid4())

    expected_response = {
        "execution_id": execution_id,
        "status": "CANCELLED",
        "message": "Execution cancelled successfully",
    }

    transformation_api.client.post = AsyncMock(return_value=expected_response)

    result = await transformation_api.cancel_execution(execution_id=execution_id)

    assert result == expected_response
    transformation_api.client.post.assert_called_once_with(
        f"transformation/executions/{execution_id}/cancel/"
    )


@pytest.mark.asyncio
async def test_cancel_execution_not_found_error(transformation_api):
    """Test cancel_execution when execution not found"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=NotFoundError("Execution not found")
    )

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.cancel_execution(execution_id=execution_id)
    assert "not found" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_cancel_execution_validation_error_cannot_cancel(transformation_api):
    """Test cancel_execution when execution cannot be cancelled"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=ValidationError("Execution cannot be cancelled (current status: COMPLETED)")
    )

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.cancel_execution(execution_id=execution_id)
    assert "cancel" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_cancel_execution_validation_error_empty_id(transformation_api):
    """Test cancel_execution with empty execution_id"""
    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.cancel_execution(execution_id="")
    assert "execution_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_cancel_execution_network_error(transformation_api):
    """Test cancel_execution with network error"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=NetworkError("Network error occurred")
    )

    with pytest.raises(NetworkError):
        await transformation_api.cancel_execution(execution_id=execution_id)


@pytest.mark.asyncio
async def test_cancel_execution_server_error(transformation_api):
    """Test cancel_execution with server error"""
    execution_id = str(uuid.uuid4())

    transformation_api.client.post = AsyncMock(
        side_effect=ServerError("Internal server error", "INTERNAL_ERROR", 500)
    )

    with pytest.raises(ServerError):
        await transformation_api.cancel_execution(execution_id=execution_id)

