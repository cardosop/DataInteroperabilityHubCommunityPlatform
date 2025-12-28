"""
Transformation Pipelines API Tests

Tests for transformation pipeline management methods including CRUD operations,
error handling, and validation.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from datahub_interoperability import DataHubClient, DataHubClientConfig, TransformationAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
)


@pytest.fixture
def config():
    """Test configuration"""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
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


# Unit Tests - Method Structure and Parameters

@pytest.mark.asyncio
async def test_create_pipeline_method_structure(transformation_api, client):
    """Test create_pipeline method structure and parameters"""
    expected_response = {
        "id": str(uuid.uuid4()),
        "name": "test-pipeline",
        "status": "DRAFT",
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await transformation_api.create_pipeline(
        name="test-pipeline",
        description="Test description",
        status="DRAFT"
    )

    assert result == expected_response
    client.post.assert_called_once()
    call_args = client.post.call_args
    assert call_args[0][0] == "transformation/pipelines/"
    assert call_args[1]["data"]["name"] == "test-pipeline"
    assert call_args[1]["data"]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_create_pipeline_with_all_parameters(transformation_api, client):
    """Test create_pipeline with all optional parameters"""
    expected_response = {"id": str(uuid.uuid4()), "name": "test-pipeline"}
    client.post = AsyncMock(return_value=expected_response)

    pipeline_definition = {
        "version": "1.0",
        "steps": [{"name": "step1", "type": "filter"}]
    }

    result = await transformation_api.create_pipeline(
        name="test-pipeline",
        description="Test description",
        pipeline_definition=pipeline_definition,
        version="1.0.0",
        status="ACTIVE",
    )

    assert result == expected_response
    call_args = client.post.call_args
    data = call_args[1]["data"]
    assert data["name"] == "test-pipeline"
    assert data["description"] == "Test description"
    assert data["pipeline_definition"] == pipeline_definition
    assert data["version"] == "1.0.0"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_list_pipelines_method_structure(transformation_api, client):
    """Test list_pipelines method structure and parameters"""
    expected_response = {
        "count": 10,
        "next": None,
        "previous": None,
        "results": [],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.list_pipelines()

    assert result == expected_response
    client.get.assert_called_once()
    call_args = client.get.call_args
    assert call_args[0][0] == "transformation/pipelines/"
    assert call_args[1]["params"]["page"] == 1
    assert call_args[1]["params"]["page_size"] == 20


@pytest.mark.asyncio
async def test_list_pipelines_with_filters(transformation_api, client):
    """Test list_pipelines with all filter parameters"""
    expected_response = {"count": 5, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.list_pipelines(
        status="ACTIVE",
        version="1.0.0",
        search="test",
        ordering="-created_at",
        page=2,
        page_size=50,
    )

    assert result == expected_response
    call_args = client.get.call_args
    params = call_args[1]["params"]
    assert params["status"] == "ACTIVE"
    assert params["version"] == "1.0.0"
    assert params["search"] == "test"
    assert params["ordering"] == "-created_at"
    assert params["page"] == 2
    assert params["page_size"] == 50


@pytest.mark.asyncio
async def test_list_pipelines_enforces_max_page_size(transformation_api, client):
    """Test that list_pipelines enforces max page size of 100"""
    expected_response = {"count": 0, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    await transformation_api.list_pipelines(page_size=200)

    call_args = client.get.call_args
    assert call_args[1]["params"]["page_size"] == 100  # Should be capped at 100


@pytest.mark.asyncio
async def test_get_pipeline_method_structure(transformation_api, client):
    """Test get_pipeline method structure"""
    pipeline_id = str(uuid.uuid4())
    expected_response = {"id": pipeline_id, "name": "test-pipeline"}
    client.get = AsyncMock(return_value=expected_response)

    result = await transformation_api.get_pipeline(pipeline_id)

    assert result == expected_response
    client.get.assert_called_once_with(f"transformation/pipelines/{pipeline_id}/")


@pytest.mark.asyncio
async def test_update_pipeline_method_structure(transformation_api, client):
    """Test update_pipeline method structure"""
    pipeline_id = str(uuid.uuid4())
    expected_response = {"id": pipeline_id, "name": "updated-name"}
    client.patch = AsyncMock(return_value=expected_response)

    result = await transformation_api.update_pipeline(pipeline_id, name="updated-name")

    assert result == expected_response
    client.patch.assert_called_once()
    call_args = client.patch.call_args
    assert call_args[0][0] == f"transformation/pipelines/{pipeline_id}/"
    assert call_args[1]["data"]["name"] == "updated-name"


@pytest.mark.asyncio
async def test_update_pipeline_with_all_parameters(transformation_api, client):
    """Test update_pipeline with all optional parameters"""
    pipeline_id = str(uuid.uuid4())
    expected_response = {"id": pipeline_id, "name": "updated-name"}
    client.patch = AsyncMock(return_value=expected_response)

    pipeline_definition = {
        "version": "1.1",
        "steps": [{"name": "step1", "type": "transform"}]
    }

    result = await transformation_api.update_pipeline(
        pipeline_id,
        name="updated-name",
        description="Updated description",
        pipeline_definition=pipeline_definition,
        version="1.1.0",
        status="ACTIVE",
    )

    assert result == expected_response
    call_args = client.patch.call_args
    data = call_args[1]["data"]
    assert data["name"] == "updated-name"
    assert data["description"] == "Updated description"
    assert data["pipeline_definition"] == pipeline_definition
    assert data["version"] == "1.1.0"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_delete_pipeline_method_structure(transformation_api, client):
    """Test delete_pipeline method structure"""
    pipeline_id = str(uuid.uuid4())
    client.delete = AsyncMock(return_value=None)

    await transformation_api.delete_pipeline(pipeline_id)

    client.delete.assert_called_once_with(f"transformation/pipelines/{pipeline_id}/")


# Error Handling Tests

@pytest.mark.asyncio
async def test_create_pipeline_validation_error_empty_name(transformation_api):
    """Test create_pipeline raises ValidationError for empty name"""
    with pytest.raises(ValidationError, match="name"):
        await transformation_api.create_pipeline(name="")


@pytest.mark.asyncio
async def test_create_pipeline_validation_error_whitespace_name(transformation_api):
    """Test create_pipeline raises ValidationError for whitespace-only name"""
    with pytest.raises(ValidationError, match="name"):
        await transformation_api.create_pipeline(name="   ")


@pytest.mark.asyncio
async def test_create_pipeline_validation_error_invalid_status(transformation_api):
    """Test create_pipeline raises ValidationError for invalid status"""
    with pytest.raises(ValidationError, match="Status"):
        await transformation_api.create_pipeline(name="test", status="INVALID")


@pytest.mark.asyncio
async def test_create_pipeline_validation_error_invalid_description_type(transformation_api):
    """Test create_pipeline raises ValidationError for invalid description type"""
    with pytest.raises(ValidationError, match="Description must be a string"):
        await transformation_api.create_pipeline(name="test", description=123)


@pytest.mark.asyncio
async def test_create_pipeline_validation_error_invalid_pipeline_definition_type(transformation_api):
    """Test create_pipeline raises ValidationError for invalid pipeline_definition type"""
    with pytest.raises(ValidationError, match="Pipeline definition must be a dictionary"):
        await transformation_api.create_pipeline(name="test", pipeline_definition="invalid")


@pytest.mark.asyncio
async def test_create_pipeline_conflict_error(transformation_api, client):
    """Test create_pipeline raises ConflictError when pipeline name exists"""
    conflict_error = ConflictError(
        "Pipeline with name 'test' already exists",
        request_id="req-123",
    )
    client.post = AsyncMock(side_effect=conflict_error)

    with pytest.raises(ConflictError):
        await transformation_api.create_pipeline(name="test")


@pytest.mark.asyncio
async def test_list_pipelines_validation_error_invalid_page(transformation_api):
    """Test list_pipelines raises ValidationError for invalid page"""
    with pytest.raises(ValidationError, match="Page number"):
        await transformation_api.list_pipelines(page=0)


@pytest.mark.asyncio
async def test_list_pipelines_validation_error_invalid_page_size(transformation_api):
    """Test list_pipelines raises ValidationError for invalid page_size"""
    with pytest.raises(ValidationError, match="Page size"):
        await transformation_api.list_pipelines(page_size=0)


@pytest.mark.asyncio
async def test_list_pipelines_validation_error_page_size_too_large(transformation_api, client):
    """Test list_pipelines caps page_size at 100 instead of raising error"""
    expected_response = {"count": 0, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    await transformation_api.list_pipelines(page_size=101)

    # Should cap at 100, not raise error
    call_args = client.get.call_args
    assert call_args[1]["params"]["page_size"] == 100


@pytest.mark.asyncio
async def test_list_pipelines_validation_error_invalid_status(transformation_api):
    """Test list_pipelines raises ValidationError for invalid status"""
    with pytest.raises(ValidationError, match="Status"):
        await transformation_api.list_pipelines(status="INVALID")


@pytest.mark.asyncio
async def test_list_pipelines_validation_error_invalid_version_type(transformation_api):
    """Test list_pipelines raises ValidationError for invalid version type"""
    with pytest.raises(ValidationError, match="Version must be a string"):
        await transformation_api.list_pipelines(version=123)


@pytest.mark.asyncio
async def test_get_pipeline_validation_error_empty_id(transformation_api):
    """Test get_pipeline raises ValidationError for empty ID"""
    with pytest.raises(ValidationError, match="pipeline_id"):
        await transformation_api.get_pipeline("")


@pytest.mark.asyncio
async def test_get_pipeline_validation_error_whitespace_id(transformation_api):
    """Test get_pipeline raises ValidationError for whitespace-only ID"""
    with pytest.raises(ValidationError, match="pipeline_id"):
        await transformation_api.get_pipeline("   ")


@pytest.mark.asyncio
async def test_get_pipeline_not_found_error(transformation_api, client):
    """Test get_pipeline raises NotFoundError when pipeline not found"""
    not_found_error = NotFoundError(
        "Pipeline not found",
        request_id="req-123",
    )
    client.get = AsyncMock(side_effect=not_found_error)

    with pytest.raises(NotFoundError):
        await transformation_api.get_pipeline("non-existent-id")


@pytest.mark.asyncio
async def test_update_pipeline_validation_error_empty_id(transformation_api):
    """Test update_pipeline raises ValidationError for empty ID"""
    with pytest.raises(ValidationError, match="pipeline_id"):
        await transformation_api.update_pipeline("", name="test")


@pytest.mark.asyncio
async def test_update_pipeline_validation_error_empty_name(transformation_api):
    """Test update_pipeline raises ValidationError for empty name"""
    pipeline_id = str(uuid.uuid4())
    with pytest.raises(ValidationError, match="name"):
        await transformation_api.update_pipeline(pipeline_id, name="")


@pytest.mark.asyncio
async def test_update_pipeline_validation_error_invalid_status(transformation_api):
    """Test update_pipeline raises ValidationError for invalid status"""
    pipeline_id = str(uuid.uuid4())
    with pytest.raises(ValidationError, match="Status"):
        await transformation_api.update_pipeline(pipeline_id, status="INVALID")


@pytest.mark.asyncio
async def test_update_pipeline_validation_error_no_fields(transformation_api):
    """Test update_pipeline raises ValidationError when no fields provided"""
    pipeline_id = str(uuid.uuid4())
    with pytest.raises(ValidationError, match="At least one field"):
        await transformation_api.update_pipeline(pipeline_id)


@pytest.mark.asyncio
async def test_update_pipeline_not_found_error(transformation_api, client):
    """Test update_pipeline raises NotFoundError when pipeline not found"""
    not_found_error = NotFoundError(
        "Pipeline not found",
        request_id="req-123",
    )
    client.patch = AsyncMock(side_effect=not_found_error)

    with pytest.raises(NotFoundError):
        await transformation_api.update_pipeline("non-existent-id", name="test")


@pytest.mark.asyncio
async def test_delete_pipeline_validation_error_empty_id(transformation_api):
    """Test delete_pipeline raises ValidationError for empty ID"""
    with pytest.raises(ValidationError, match="pipeline_id"):
        await transformation_api.delete_pipeline("")


@pytest.mark.asyncio
async def test_delete_pipeline_not_found_error(transformation_api, client):
    """Test delete_pipeline raises NotFoundError when pipeline not found"""
    not_found_error = NotFoundError(
        "Pipeline not found",
        request_id="req-123",
    )
    client.delete = AsyncMock(side_effect=not_found_error)

    with pytest.raises(NotFoundError):
        await transformation_api.delete_pipeline("non-existent-id")


# Edge Cases and Additional Tests

@pytest.mark.asyncio
async def test_create_pipeline_strips_name_whitespace(transformation_api, client):
    """Test that create_pipeline strips whitespace from name"""
    expected_response = {"id": str(uuid.uuid4()), "name": "test-pipeline"}
    client.post = AsyncMock(return_value=expected_response)

    await transformation_api.create_pipeline(name="  test-pipeline  ")

    call_args = client.post.call_args
    assert call_args[1]["data"]["name"] == "test-pipeline"


@pytest.mark.asyncio
async def test_create_pipeline_handles_none_description(transformation_api, client):
    """Test that create_pipeline handles None description correctly"""
    expected_response = {"id": str(uuid.uuid4()), "name": "test"}
    client.post = AsyncMock(return_value=expected_response)

    await transformation_api.create_pipeline(name="test", description=None)

    call_args = client.post.call_args
    # Description should not be in data if None
    assert "description" not in call_args[1]["data"]


@pytest.mark.asyncio
async def test_list_pipelines_default_parameters(transformation_api, client):
    """Test list_pipelines uses correct default parameters"""
    expected_response = {"count": 0, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    await transformation_api.list_pipelines()

    call_args = client.get.call_args
    params = call_args[1]["params"]
    assert params["page"] == 1
    assert params["page_size"] == 20


@pytest.mark.asyncio
async def test_update_pipeline_partial_update(transformation_api, client):
    """Test that update_pipeline allows partial updates"""
    pipeline_id = str(uuid.uuid4())
    expected_response = {"id": pipeline_id, "name": "updated"}
    client.patch = AsyncMock(return_value=expected_response)

    await transformation_api.update_pipeline(pipeline_id, name="updated")

    call_args = client.patch.call_args
    data = call_args[1]["data"]
    assert data["name"] == "updated"
    # Only name should be in data
    assert len(data) == 1


@pytest.mark.asyncio
async def test_delete_pipeline_returns_none(transformation_api, client):
    """Test that delete_pipeline returns None on success"""
    pipeline_id = str(uuid.uuid4())
    client.delete = AsyncMock(return_value=None)

    result = await transformation_api.delete_pipeline(pipeline_id)

    assert result is None
    client.delete.assert_called_once()

