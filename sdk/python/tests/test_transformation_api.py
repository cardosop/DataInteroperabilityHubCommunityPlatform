"""
Transformation API Tests

Tests for transformation API module structure, imports, and basic functionality.
"""
import pytest
import inspect
from unittest.mock import AsyncMock, MagicMock
from datahub_interoperability import DataHubClient, DataHubClientConfig, TransformationAPI


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


# Module Structure Tests

def test_transformation_api_import():
    """Test that TransformationAPI can be imported from package"""
    from datahub_interoperability import TransformationAPI
    assert TransformationAPI is not None
    assert hasattr(TransformationAPI, '__init__')


def test_transformation_api_in_package_exports():
    """Test that TransformationAPI is in package __all__ exports"""
    import datahub_interoperability
    assert 'TransformationAPI' in datahub_interoperability.__all__


def test_transformation_api_initialization(transformation_api, client):
    """Test TransformationAPI initialization"""
    assert transformation_api is not None
    assert transformation_api.client == client
    assert isinstance(transformation_api, TransformationAPI)


@pytest.mark.asyncio
async def test_transformation_api_accessible_from_client(config):
    """Test that transformation API is accessible from client"""
    async with DataHubClient(config) as client:
        assert hasattr(client, 'transformation')
        assert client.transformation is not None
        assert isinstance(client.transformation, TransformationAPI)


@pytest.mark.asyncio
async def test_transformation_api_has_client_reference(config):
    """Test that transformation API has reference to client"""
    async with DataHubClient(config) as client:
        assert client.transformation.client == client


def test_transformation_api_module_structure():
    """Test that transformation module has correct structure"""
    from datahub_interoperability.transformation import TransformationAPI
    import inspect

    # Check class exists
    assert TransformationAPI is not None

    # Check __init__ method exists
    assert hasattr(TransformationAPI, '__init__')
    init_signature = inspect.signature(TransformationAPI.__init__)
    assert 'client' in init_signature.parameters

    # Check docstring exists
    assert TransformationAPI.__doc__ is not None
    assert 'Transformation API' in TransformationAPI.__doc__


def test_transformation_api_docstring():
    """Test that TransformationAPI has proper docstring"""
    from datahub_interoperability.transformation import TransformationAPI

    assert TransformationAPI.__doc__ is not None
    assert 'Transformation API' in TransformationAPI.__doc__
    assert 'pipeline' in TransformationAPI.__doc__.lower() or 'transformation' in TransformationAPI.__doc__.lower()


def test_transformation_module_imports():
    """Test that transformation module can be imported directly"""
    from datahub_interoperability import transformation
    assert transformation is not None
    assert hasattr(transformation, 'TransformationAPI')


@pytest.mark.asyncio
async def test_all_api_modules_initialized(config):
    """Test that all API modules including transformation are initialized"""
    async with DataHubClient(config) as client:
        # Check all expected API modules exist
        assert hasattr(client, 'contracts')
        assert hasattr(client, 'lineage')
        assert hasattr(client, 'scheduled_ingestion')
        assert hasattr(client, 'versioning')
        assert hasattr(client, 'governance')
        assert hasattr(client, 'mesh')
        assert hasattr(client, 'search')
        assert hasattr(client, 'observability')
        assert hasattr(client, 'transformation')
        assert hasattr(client, 'webhooks')

        # Check transformation is initialized
        assert client.transformation is not None
        assert isinstance(client.transformation, TransformationAPI)


def test_transformation_api_methods_exist(transformation_api):
    """Test that TransformationAPI has expected methods"""
    # Pipeline methods
    assert hasattr(transformation_api, 'create_pipeline')
    assert hasattr(transformation_api, 'list_pipelines')
    assert hasattr(transformation_api, 'get_pipeline')
    assert hasattr(transformation_api, 'update_pipeline')
    assert hasattr(transformation_api, 'delete_pipeline')

    # Execution methods
    assert hasattr(transformation_api, 'create_execution')
    assert hasattr(transformation_api, 'list_executions')
    assert hasattr(transformation_api, 'get_execution')
    assert hasattr(transformation_api, 'cancel_execution')

    # Preview methods
    assert hasattr(transformation_api, 'generate_preview')
    assert hasattr(transformation_api, 'get_preview')

    # Wrangling methods
    assert hasattr(transformation_api, 'start_wrangling')
    assert hasattr(transformation_api, 'apply_wrangling_operation')
    assert hasattr(transformation_api, 'undo_wrangling')
    assert hasattr(transformation_api, 'redo_wrangling')
    assert hasattr(transformation_api, 'get_wrangling_session')


def test_transformation_api_methods_are_async(transformation_api):
    """Test that TransformationAPI methods are async"""
    import inspect

    # Check that methods are coroutine functions
    assert inspect.iscoroutinefunction(transformation_api.create_pipeline)
    assert inspect.iscoroutinefunction(transformation_api.list_pipelines)
    assert inspect.iscoroutinefunction(transformation_api.get_pipeline)
    assert inspect.iscoroutinefunction(transformation_api.update_pipeline)
    assert inspect.iscoroutinefunction(transformation_api.delete_pipeline)
    assert inspect.iscoroutinefunction(transformation_api.create_execution)
    assert inspect.iscoroutinefunction(transformation_api.list_executions)
    assert inspect.iscoroutinefunction(transformation_api.get_execution)
    assert inspect.iscoroutinefunction(transformation_api.cancel_execution)
    assert inspect.iscoroutinefunction(transformation_api.generate_preview)
    assert inspect.iscoroutinefunction(transformation_api.get_preview)
    assert inspect.iscoroutinefunction(transformation_api.start_wrangling)
    assert inspect.iscoroutinefunction(transformation_api.apply_wrangling_operation)
    assert inspect.iscoroutinefunction(transformation_api.undo_wrangling)
    assert inspect.iscoroutinefunction(transformation_api.redo_wrangling)
    assert inspect.iscoroutinefunction(transformation_api.get_wrangling_session)


def test_transformation_api_method_signatures(transformation_api):
    """Test that TransformationAPI methods have correct signatures"""
    import inspect

    # Test create_pipeline signature
    create_pipeline_sig = inspect.signature(transformation_api.create_pipeline)
    assert 'name' in create_pipeline_sig.parameters
    assert 'description' in create_pipeline_sig.parameters
    assert 'pipeline_definition' in create_pipeline_sig.parameters

    # Test list_pipelines signature
    list_pipelines_sig = inspect.signature(transformation_api.list_pipelines)
    assert 'page' in list_pipelines_sig.parameters
    assert 'page_size' in list_pipelines_sig.parameters

    # Test get_pipeline signature
    get_pipeline_sig = inspect.signature(transformation_api.get_pipeline)
    assert 'pipeline_id' in get_pipeline_sig.parameters

    # Test create_execution signature
    create_execution_sig = inspect.signature(transformation_api.create_execution)
    assert 'pipeline_id' in create_execution_sig.parameters
    assert 'asset_id' in create_execution_sig.parameters

    # Test start_wrangling signature
    start_wrangling_sig = inspect.signature(transformation_api.start_wrangling)
    assert 'asset_id' in start_wrangling_sig.parameters

    # Test apply_wrangling_operation signature
    apply_wrangling_sig = inspect.signature(transformation_api.apply_wrangling_operation)
    assert 'session_id' in apply_wrangling_sig.parameters
    assert 'operation' in apply_wrangling_sig.parameters

    # Test generate_preview signature
    generate_preview_sig = inspect.signature(transformation_api.generate_preview)
    assert 'pipeline_id' in generate_preview_sig.parameters
    assert 'asset_id' in generate_preview_sig.parameters
    assert 'sample_size' in generate_preview_sig.parameters
    assert 'sampling_method' in generate_preview_sig.parameters

    # Test get_preview signature
    get_preview_sig = inspect.signature(transformation_api.get_preview)
    assert 'preview_id' in get_preview_sig.parameters

    # Test undo_wrangling signature
    undo_wrangling_sig = inspect.signature(transformation_api.undo_wrangling)
    assert 'session_id' in undo_wrangling_sig.parameters

    # Test redo_wrangling signature
    redo_wrangling_sig = inspect.signature(transformation_api.redo_wrangling)
    assert 'session_id' in redo_wrangling_sig.parameters

    # Test get_wrangling_session signature
    get_wrangling_sig = inspect.signature(transformation_api.get_wrangling_session)
    assert 'session_id' in get_wrangling_sig.parameters


# Preview Methods Validation Tests (Unit Tests - No API Calls)


@pytest.mark.asyncio
async def test_generate_preview_validation_pipeline_id_empty(transformation_api):
    """Test that empty pipeline_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="",
            asset_id="asset-456"
        )
    assert "pipeline_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_generate_preview_validation_pipeline_id_none(transformation_api):
    """Test that None pipeline_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.generate_preview(
            pipeline_id=None,  # type: ignore
            asset_id="asset-456"
        )


@pytest.mark.asyncio
async def test_generate_preview_validation_asset_id_empty(transformation_api):
    """Test that empty asset_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="pipeline-123",
            asset_id=""
        )
    assert "asset_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_generate_preview_validation_sample_size_invalid_type(transformation_api):
    """Test that non-integer sample_size raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="pipeline-123",
            asset_id="asset-456",
            sample_size="100"  # type: ignore
        )
    assert "sample_size" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_generate_preview_validation_sample_size_too_small(transformation_api):
    """Test that sample_size < 1 raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="pipeline-123",
            asset_id="asset-456",
            sample_size=0
        )
    assert "sample_size" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_generate_preview_validation_sample_size_too_large(transformation_api):
    """Test that sample_size > 10000 raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="pipeline-123",
            asset_id="asset-456",
            sample_size=10001
        )
    assert "sample_size" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_generate_preview_validation_sampling_method_invalid(transformation_api):
    """Test that invalid sampling_method raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.generate_preview(
            pipeline_id="pipeline-123",
            asset_id="asset-456",
            sampling_method="invalid_method"
        )
    assert "sampling_method" in str(exc_info.value.message).lower()




@pytest.mark.asyncio
async def test_get_preview_validation_preview_id_empty(transformation_api):
    """Test that empty preview_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.get_preview("")
    assert "preview_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_get_preview_validation_preview_id_none(transformation_api):
    """Test that None preview_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.get_preview(None)  # type: ignore


@pytest.mark.asyncio
async def test_get_preview_validation_preview_id_whitespace(transformation_api):
    """Test that whitespace-only preview_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.get_preview("   ")


# Wrangling Methods Tests

@pytest.mark.asyncio
async def test_start_wrangling_success(transformation_api):
    """Test successful wrangling session start"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "asset_id": "asset-456",
        "asset_name": "Test Asset",
        "current_state": {"rows": 100, "columns": 5},
        "operation_history": [],
        "applied_operations_count": 0,
        "can_undo": False,
        "can_redo": False,
        "wrangling_script": "",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

    transformation_api.client.post = AsyncMock(return_value=mock_response)

    result = await transformation_api.start_wrangling(asset_id="asset-456")

    assert result == mock_response
    transformation_api.client.post.assert_called_once()
    call_args = transformation_api.client.post.call_args
    assert call_args[0][0] == "transformation/wrangling/"
    assert call_args[1]["data"]["asset_id"] == "asset-456"


@pytest.mark.asyncio
async def test_start_wrangling_with_operation(transformation_api):
    """Test starting wrangling session with initial operation"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "asset_id": "asset-456",
        "applied_operations_count": 1
    }

    transformation_api.client.post = AsyncMock(return_value=mock_response)

    operation = {
        "type": "FILTER",
        "parameters": {"condition": "age > 18"}
    }

    result = await transformation_api.start_wrangling(
        asset_id="asset-456",
        operation=operation
    )

    assert result == mock_response
    call_args = transformation_api.client.post.call_args
    assert call_args[1]["data"]["operation"] == operation


@pytest.mark.asyncio
async def test_start_wrangling_validation_asset_id_empty(transformation_api):
    """Test that empty asset_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.start_wrangling(asset_id="")
    assert "asset_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_start_wrangling_validation_asset_id_none(transformation_api):
    """Test that None asset_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.start_wrangling(asset_id=None)  # type: ignore


@pytest.mark.asyncio
async def test_start_wrangling_validation_operation_invalid_type(transformation_api):
    """Test that invalid operation type raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.start_wrangling(
            asset_id="asset-456",
            operation="not a dict"  # type: ignore
        )


@pytest.mark.asyncio
async def test_start_wrangling_validation_operation_missing_type(transformation_api):
    """Test that operation without type raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.start_wrangling(
            asset_id="asset-456",
            operation={"parameters": {}}
        )
    assert "type" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_start_wrangling_validation_operation_missing_parameters(transformation_api):
    """Test that operation without parameters raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.start_wrangling(
            asset_id="asset-456",
            operation={"type": "FILTER"}
        )
    assert "parameters" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_start_wrangling_not_found_error(transformation_api):
    """Test that 404 error raises NotFoundError"""
    from datahub_interoperability.errors import NotFoundError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Asset not found",
        "NOT_FOUND",
        404,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.start_wrangling(asset_id="asset-456")
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_apply_wrangling_operation_success(transformation_api):
    """Test successful wrangling operation application"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "operation_id": "op-456",
        "asset_id": "asset-456",
        "current_state": {"rows": 95, "columns": 5},
        "applied_operations_count": 1,
        "can_undo": True,
        "can_redo": False
    }

    transformation_api.client.post = AsyncMock(return_value=mock_response)

    operation = {
        "type": "FILTER",
        "parameters": {"condition": "age > 18"}
    }

    result = await transformation_api.apply_wrangling_operation(
        session_id="session-123",
        operation=operation
    )

    assert result == mock_response
    call_args = transformation_api.client.post.call_args
    assert call_args[0][0] == "transformation/wrangling/"
    assert call_args[1]["data"]["session_id"] == "session-123"
    assert call_args[1]["data"]["operation"] == operation


@pytest.mark.asyncio
async def test_apply_wrangling_operation_validation_session_id_empty(transformation_api):
    """Test that empty session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.apply_wrangling_operation(
            session_id="",
            operation={"type": "FILTER", "parameters": {}}
        )
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_apply_wrangling_operation_validation_operation_invalid(transformation_api):
    """Test that invalid operation raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.apply_wrangling_operation(
            session_id="session-123",
            operation={"type": "FILTER"}  # Missing parameters
        )


@pytest.mark.asyncio
async def test_apply_wrangling_operation_not_found_error(transformation_api):
    """Test that 404 error raises NotFoundError"""
    from datahub_interoperability.errors import NotFoundError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Session not found",
        "NOT_FOUND",
        404,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.apply_wrangling_operation(
            session_id="session-123",
            operation={"type": "FILTER", "parameters": {}}
        )
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_undo_wrangling_success(transformation_api):
    """Test successful wrangling undo"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "undone_operation": {"type": "FILTER", "parameters": {}},
        "can_undo": False,
        "can_redo": True,
        "applied_operations_count": 0
    }

    transformation_api.client.post = AsyncMock(return_value=mock_response)

    result = await transformation_api.undo_wrangling("session-123")

    assert result == mock_response
    transformation_api.client.post.assert_called_once_with(
        "transformation/wrangling/session-123/undo/"
    )


@pytest.mark.asyncio
async def test_undo_wrangling_validation_session_id_empty(transformation_api):
    """Test that empty session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.undo_wrangling("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_undo_wrangling_validation_cannot_undo(transformation_api):
    """Test that 400 error when cannot undo raises ValidationError"""
    from datahub_interoperability.errors import ValidationError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Cannot undo: no operations to undo",
        "VALIDATION_ERROR",
        400,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.undo_wrangling("session-123")
    assert "cannot undo" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_undo_wrangling_not_found_error(transformation_api):
    """Test that 404 error raises NotFoundError"""
    from datahub_interoperability.errors import NotFoundError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Session not found",
        "NOT_FOUND",
        404,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.undo_wrangling("session-123")
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_redo_wrangling_success(transformation_api):
    """Test successful wrangling redo"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "redone_operation": {"type": "FILTER", "parameters": {}},
        "can_undo": True,
        "can_redo": False,
        "applied_operations_count": 1
    }

    transformation_api.client.post = AsyncMock(return_value=mock_response)

    result = await transformation_api.redo_wrangling("session-123")

    assert result == mock_response
    transformation_api.client.post.assert_called_once_with(
        "transformation/wrangling/session-123/redo/"
    )


@pytest.mark.asyncio
async def test_redo_wrangling_validation_session_id_empty(transformation_api):
    """Test that empty session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.redo_wrangling("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_redo_wrangling_validation_cannot_redo(transformation_api):
    """Test that 400 error when cannot redo raises ValidationError"""
    from datahub_interoperability.errors import ValidationError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Cannot redo: no operations to redo",
        "VALIDATION_ERROR",
        400,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.redo_wrangling("session-123")
    assert "cannot redo" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_redo_wrangling_not_found_error(transformation_api):
    """Test that 404 error raises NotFoundError"""
    from datahub_interoperability.errors import NotFoundError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Session not found",
        "NOT_FOUND",
        404,
        request_id="req-123"
    )
    transformation_api.client.post = AsyncMock(side_effect=error)

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.redo_wrangling("session-123")
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_get_wrangling_session_success(transformation_api):
    """Test successful wrangling session retrieval"""
    from unittest.mock import AsyncMock

    mock_response = {
        "session_id": "session-123",
        "asset_id": "asset-456",
        "asset_name": "Test Asset",
        "name": "Wrangling Session",
        "description": "Test session",
        "current_state": {"rows": 100, "columns": 5},
        "operation_history": [],
        "history_position": -1,
        "applied_operations_count": 0,
        "can_undo": False,
        "can_redo": False,
        "wrangling_script": "",
        "metadata": {},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

    transformation_api.client.get = AsyncMock(return_value=mock_response)

    result = await transformation_api.get_wrangling_session("session-123")

    assert result == mock_response
    transformation_api.client.get.assert_called_once_with(
        "transformation/wrangling/session-123/"
    )


@pytest.mark.asyncio
async def test_get_wrangling_session_validation_session_id_empty(transformation_api):
    """Test that empty session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        await transformation_api.get_wrangling_session("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_get_wrangling_session_validation_session_id_none(transformation_api):
    """Test that None session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.get_wrangling_session(None)  # type: ignore


@pytest.mark.asyncio
async def test_get_wrangling_session_validation_session_id_whitespace(transformation_api):
    """Test that whitespace-only session_id raises ValidationError"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await transformation_api.get_wrangling_session("   ")


@pytest.mark.asyncio
async def test_get_wrangling_session_not_found_error(transformation_api):
    """Test that 404 error raises NotFoundError"""
    from datahub_interoperability.errors import NotFoundError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Session not found",
        "NOT_FOUND",
        404,
        request_id="req-123"
    )
    transformation_api.client.get = AsyncMock(side_effect=error)

    with pytest.raises(NotFoundError) as exc_info:
        await transformation_api.get_wrangling_session("session-123")
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_get_wrangling_session_server_error(transformation_api):
    """Test that 500+ error raises ServerError"""
    from datahub_interoperability.errors import ServerError, DataHubError
    from unittest.mock import AsyncMock

    error = DataHubError(
        "Internal server error",
        "INTERNAL_ERROR",
        500,
        request_id="req-123"
    )
    transformation_api.client.get = AsyncMock(side_effect=error)

    with pytest.raises(ServerError) as exc_info:
        await transformation_api.get_wrangling_session("session-123")
    assert "server error" in str(exc_info.value.message).lower()



