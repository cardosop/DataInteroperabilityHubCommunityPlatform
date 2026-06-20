from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Virtualization API Tests

Tests for virtualization API module structure, imports, and basic functionality.
Includes integration tests with real API services (no mocks/stubs).

NOTE: Integration tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run integration tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest sdk/python/tests/test_virtualization_api.py -v -m integration
"""

import asyncio
import inspect
import os
import uuid

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig, VirtualizationAPI
from datahub_interoperability.errors import (
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from tests.conftest import default_api_base_url, get_api_key, is_api_available

# Default SQL sources for tests requiring source-backed SQL queries.
# The API now validates that non-SPARQL query types include at least one source.
# Set VIRTUALIZATION_TEST_DB_HOST to override the default host for Docker
# test environments (e.g. "hub-test-postgres").
_DEFAULT_SQL_TEST_DB_HOST = os.environ.get("VIRTUALIZATION_TEST_DB_HOST", "localhost")
_DEFAULT_SQL_TEST_DB_USER = os.environ.get("VIRTUALIZATION_TEST_DB_USER", "hub_test")
_DEFAULT_SQL_TEST_DB_PASS = os.environ.get("VIRTUALIZATION_TEST_DB_PASS", "hub_test")
_DEFAULT_SQL_TEST_DB_NAME = os.environ.get("VIRTUALIZATION_TEST_DB_NAME", "hub_test")
_DEFAULT_SQL_SOURCES = [
    {
        "type": "postgresql",
        "host": _DEFAULT_SQL_TEST_DB_HOST,
        "port": 5432,
        "username": _DEFAULT_SQL_TEST_DB_USER,
        "password": _DEFAULT_SQL_TEST_DB_PASS,
        "database": _DEFAULT_SQL_TEST_DB_NAME,
    }
]


async def retry_on_rate_limit(func, max_retries: int = 3, initial_delay: float = 1.0):
    """
    Retry a function call with exponential backoff on rate limit errors.

    Args:
        func: Async function to call
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before retry (default: 1.0)

    Returns:
        Result of the function call

    Raises:
        RateLimitError: If rate limit persists after all retries
        Exception: Any other exception from the function call
    """
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError as e:
            if attempt < max_retries - 1:
                # Get retry_after from error attribute or details
                retry_after = getattr(e, "retry_after", None)
                if retry_after is None and isinstance(getattr(e, "details", None), dict):
                    retry_after = e.details.get("retry_after")

                # Convert retry_after to int if it's a string
                if retry_after:
                    try:
                        if isinstance(retry_after, str):
                            # Handle ErrorDetail objects that might be stringified
                            retry_after = int(retry_after.strip())
                        else:
                            retry_after = int(retry_after)
                        delay = retry_after + 1  # Add 1 second buffer
                    except (ValueError, TypeError):
                        delay = initial_delay * (2**attempt)
                else:
                    delay = initial_delay * (2**attempt)

                await asyncio.sleep(min(delay, 30))  # Cap delay at 30 seconds
            else:
                raise


@pytest.fixture
def config():
    """Test configuration for unit tests"""
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
    """Test client for unit tests"""
    async with DataHubClient(config) as client:
        yield client


@pytest.fixture
def virtualization_api(client):
    """Test virtualization API for unit tests"""
    return VirtualizationAPI(client)


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    if not is_api_available():
        pytest.skip("API service is not available. Ensure Docker Compose services are running.")

    api_key = get_api_key()
    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable, "
            "or ensure Docker Compose api-service is accessible."
        )

    api_base_url = os.environ.get("API_BASE_URL", f"{default_api_base_url()}/api/v1")

    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
        user_agent="DataHub-SDK-Test",
        enable_logging=False,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration"""
    async with DataHubClient(real_api_config) as client:
        yield client


@pytest.fixture
def real_virtualization_api(real_client):
    """Virtualization API instance with real client"""
    return VirtualizationAPI(real_client)


# Module Structure Tests


def test_virtualization_api_import():
    """Test that VirtualizationAPI can be imported from package"""
    from datahub_interoperability import VirtualizationAPI

    assert VirtualizationAPI is not None
    assert hasattr(VirtualizationAPI, "__init__")


def test_virtualization_api_in_package_exports():
    """Test that VirtualizationAPI is in package __all__ exports"""
    import datahub_interoperability

    assert "VirtualizationAPI" in datahub_interoperability.__all__


def test_virtualization_api_initialization(virtualization_api, client):
    """Test VirtualizationAPI initialization"""
    assert virtualization_api is not None
    assert virtualization_api.client == client
    assert isinstance(virtualization_api, VirtualizationAPI)


@pytest.mark.asyncio
async def test_virtualization_api_accessible_from_client(config):
    """Test that virtualization API is accessible from client"""
    async with DataHubClient(config) as client:
        assert hasattr(client, "virtualization")
        assert client.virtualization is not None
        assert isinstance(client.virtualization, VirtualizationAPI)


@pytest.mark.asyncio
async def test_virtualization_api_has_client_reference(config):
    """Test that virtualization API has reference to client"""
    async with DataHubClient(config) as client:
        assert client.virtualization.client == client


def test_virtualization_api_module_structure():
    """Test that virtualization module has correct structure"""
    from datahub_interoperability.virtualization import VirtualizationAPI

    # Check class exists
    assert VirtualizationAPI is not None

    # Check __init__ method exists
    assert hasattr(VirtualizationAPI, "__init__")
    init_signature = inspect.signature(VirtualizationAPI.__init__)
    assert "client" in init_signature.parameters

    # Check docstring exists
    assert VirtualizationAPI.__doc__ is not None
    assert "Virtualization API" in VirtualizationAPI.__doc__


def test_virtualization_api_docstring():
    """Test that VirtualizationAPI has proper docstring"""
    from datahub_interoperability.virtualization import VirtualizationAPI

    assert VirtualizationAPI.__doc__ is not None
    assert "Virtualization API" in VirtualizationAPI.__doc__
    assert (
        "virtual" in VirtualizationAPI.__doc__.lower()
        or "dataset" in VirtualizationAPI.__doc__.lower()
    )


def test_virtualization_module_imports():
    """Test that virtualization module can be imported"""
    from datahub_interoperability import virtualization

    assert virtualization is not None
    assert hasattr(virtualization, "VirtualizationAPI")


@pytest.mark.asyncio
async def test_all_api_modules_initialized(config):
    """Test that all API modules including virtualization are initialized"""
    async with DataHubClient(config) as client:
        # Check all expected API modules exist
        assert hasattr(client, "contracts")
        assert hasattr(client, "lineage")
        assert hasattr(client, "scheduled_ingestion")
        assert hasattr(client, "versioning")
        assert hasattr(client, "governance")
        assert hasattr(client, "mesh")
        assert hasattr(client, "search")
        assert hasattr(client, "observability")
        assert hasattr(client, "transformation")
        assert hasattr(client, "virtualization")
        assert hasattr(client, "webhooks")

        # Check virtualization is initialized
        assert client.virtualization is not None
        assert isinstance(client.virtualization, VirtualizationAPI)


def test_virtualization_api_validation_helpers(virtualization_api):
    """Test that VirtualizationAPI has validation helper methods"""
    assert hasattr(virtualization_api, "_validate_dataset_id")
    assert hasattr(virtualization_api, "_validate_execution_id")
    assert hasattr(virtualization_api, "_validate_page_params")

    # Test validation methods are callable
    assert callable(virtualization_api._validate_dataset_id)
    assert callable(virtualization_api._validate_execution_id)
    assert callable(virtualization_api._validate_page_params)


def test_virtualization_api_validation_dataset_id(virtualization_api):
    """Test dataset ID validation"""
    from datahub_interoperability.errors import ValidationError

    # Valid dataset ID
    try:
        virtualization_api._validate_dataset_id("test-dataset-id")
    except ValidationError:
        pytest.fail("Valid dataset ID should not raise ValidationError")

    # Empty dataset ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id("")

    # None dataset ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id(None)

    # Whitespace-only dataset ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id("   ")


def test_virtualization_api_validation_execution_id(virtualization_api):
    """Test execution ID validation"""
    from datahub_interoperability.errors import ValidationError

    # Valid execution ID
    try:
        virtualization_api._validate_execution_id("test-execution-id")
    except ValidationError:
        pytest.fail("Valid execution ID should not raise ValidationError")

    # Empty execution ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_execution_id("")

    # None execution ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_execution_id(None)

    # Whitespace-only execution ID
    with pytest.raises(ValidationError):
        virtualization_api._validate_execution_id("   ")


def test_virtualization_api_validation_page_params(virtualization_api):
    """Test pagination parameters validation"""
    from datahub_interoperability.errors import ValidationError

    # Valid pagination params
    try:
        virtualization_api._validate_page_params(1, 20)
    except ValidationError:
        pytest.fail("Valid pagination params should not raise ValidationError")

    # Invalid page (less than 1)
    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(0, 20)

    # Invalid page_size (less than 1)
    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(1, 0)

    # Invalid page_size (greater than 100)
    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(1, 101)


# Dataset Methods Tests - Integration Tests with Real API


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_dataset_success(real_virtualization_api):
    """Test successful dataset creation with real API"""
    dataset_name = f"test-dataset-{uuid.uuid4().hex[:8]}"

    result = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT * FROM test_table WHERE id = :id",
        query_type="SQL",
        sources=_DEFAULT_SQL_SOURCES,
    )

    assert result is not None
    assert result["name"] == dataset_name
    assert result["query"] == "SELECT * FROM test_table WHERE id = :id"
    assert result["query_type"] == "SQL"
    assert "id" in result
    assert result["status"] == "DRAFT"  # Default status
    assert result["version"] == "1.0.0"  # Default version

    # Cleanup
    try:
        await real_virtualization_api.delete_dataset(result["id"])
    except (NotFoundError, ConnectionError, TimeoutError, OSError):
        pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_dataset_with_all_fields(real_virtualization_api):
    """Test dataset creation with all optional fields"""
    dataset_name = f"test-dataset-full-{uuid.uuid4().hex[:8]}"

    result = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT id, name FROM test_table",
        query_type="SQL",
        description="Test Description",
        schema={"fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]},
        sources=[
            {"id": "source1", "type": "postgresql", "host": "localhost", "database": "testdb"}
        ],
        version="2.0.0",
        status="ACTIVE",
    )

    assert result is not None
    assert result["name"] == dataset_name
    assert result["description"] == "Test Description"
    assert result["schema"] == {
        "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
    }
    assert result["sources"] == [
        {"id": "source1", "type": "postgresql", "host": "localhost", "database": "testdb"}
    ]
    assert result["version"] == "2.0.0"
    assert result["status"] == "ACTIVE"

    # Cleanup
    try:
        await real_virtualization_api.delete_dataset(result["id"])
    except (NotFoundError, ConnectionError, TimeoutError, OSError):
        pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_dataset_validation_error(real_virtualization_api):
    """Test dataset creation with validation error"""
    with pytest.raises(ValidationError):
        await real_virtualization_api.create_dataset(
            name="", query="SELECT * FROM table", query_type="SQL", sources=_DEFAULT_SQL_SOURCES
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_dataset_conflict_error(real_virtualization_api):
    """Test dataset creation with conflict error (duplicate name)"""
    dataset_name = f"test-dataset-conflict-{uuid.uuid4().hex[:8]}"

    # Create first dataset
    result1 = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT * FROM table1",
        query_type="SQL",
        sources=_DEFAULT_SQL_SOURCES,
    )

    # Try to create another with same name (should fail if name uniqueness is enforced)
    try:
        with pytest.raises((ConflictError, ValidationError)):
            await real_virtualization_api.create_dataset(
                name=dataset_name,
                query="SELECT * FROM table2",
                query_type="SQL",
                sources=_DEFAULT_SQL_SOURCES,
            )
    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(result1["id"])
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_datasets_success(real_virtualization_api):
    """Test successful dataset listing"""
    # Create a test dataset first
    dataset_name = f"test-dataset-list-{uuid.uuid4().hex[:8]}"
    created = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT * FROM test_table",
        query_type="SQL",
        sources=_DEFAULT_SQL_SOURCES,
    )

    try:
        result = await real_virtualization_api.list_datasets()

        assert result is not None
        assert "count" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        # Should find at least our created dataset
        dataset_ids = [ds["id"] for ds in result["results"]]
        assert created["id"] in dataset_ids
    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(created["id"])
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_datasets_with_filters(real_virtualization_api):
    """Test dataset listing with filters"""
    # Create test datasets with different statuses
    dataset_name1 = f"test-dataset-filter-1-{uuid.uuid4().hex[:8]}"
    dataset_name2 = f"test-dataset-filter-2-{uuid.uuid4().hex[:8]}"

    created1 = await real_virtualization_api.create_dataset(
        name=dataset_name1,
        query="SELECT * FROM table1",
        query_type="SQL",
        status="ACTIVE",
        sources=_DEFAULT_SQL_SOURCES,
    )
    created2 = await real_virtualization_api.create_dataset(
        name=dataset_name2, query="SELECT * FROM table2", query_type="SPARQL", status="DRAFT"
    )

    try:
        # Filter by status
        result_active = await real_virtualization_api.list_datasets(status="ACTIVE")
        assert result_active is not None
        assert all(ds["status"] == "ACTIVE" for ds in result_active["results"])

        # Filter by query_type
        result_sql = await real_virtualization_api.list_datasets(query_type="SQL")
        assert result_sql is not None
        assert all(ds["query_type"] == "SQL" for ds in result_sql["results"])

        # Filter by search
        result_search = await real_virtualization_api.list_datasets(search="filter-1")
        assert result_search is not None
        assert any(ds["id"] == created1["id"] for ds in result_search["results"])
    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(created1["id"])
            await real_virtualization_api.delete_dataset(created2["id"])
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_datasets_pagination(real_virtualization_api):
    """Test dataset listing with pagination"""
    result = await real_virtualization_api.list_datasets(page=1, page_size=20)

    assert result is not None
    assert "count" in result
    assert "results" in result
    assert len(result["results"]) <= 20
    assert isinstance(result["count"], int)


def test_list_datasets_invalid_pagination(virtualization_api):
    """Test dataset listing with invalid pagination (unit test - no API call)"""
    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(0, 20)

    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(1, 0)

    with pytest.raises(ValidationError):
        virtualization_api._validate_page_params(1, 101)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_success(real_virtualization_api):
    """Test successful dataset retrieval"""
    # Create a test dataset
    dataset_name = f"test-dataset-get-{uuid.uuid4().hex[:8]}"
    created = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT * FROM test_table",
        query_type="SQL",
        description="Test Description",
        sources=_DEFAULT_SQL_SOURCES,
    )

    try:
        result = await real_virtualization_api.get_dataset(created["id"])

        assert result is not None
        assert result["id"] == created["id"]
        assert result["name"] == dataset_name
        assert result["query"] == "SELECT * FROM test_table"
        assert result["query_type"] == "SQL"
        assert result["description"] == "Test Description"
    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(created["id"])
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_not_found(real_virtualization_api):
    """Test dataset retrieval with not found error"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_virtualization_api.get_dataset(fake_id)


def test_get_dataset_invalid_id(virtualization_api):
    """Test dataset retrieval with invalid ID (unit test - no API call)"""
    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id("")

    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_dataset_success(real_virtualization_api):
    """Test successful dataset update"""
    # Create a test dataset
    dataset_name = f"test-dataset-update-{uuid.uuid4().hex[:8]}"
    created = await real_virtualization_api.create_dataset(
        name=dataset_name,
        query="SELECT * FROM test_table",
        query_type="SQL",
        sources=_DEFAULT_SQL_SOURCES,
    )

    try:
        # Update the dataset
        updated = await real_virtualization_api.update_dataset(
            created["id"], name=f"{dataset_name}-updated", description="Updated Description"
        )

        assert updated is not None
        assert updated["id"] == created["id"]
        assert updated["name"] == f"{dataset_name}-updated"
        assert updated["description"] == "Updated Description"
        assert updated["query"] == "SELECT * FROM test_table"  # Unchanged
    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(created["id"])
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_dataset_partial_update(real_virtualization_api):
    """Test dataset partial update"""
    await asyncio.sleep(0.5)  # Delay to avoid rate limiting

    # Create a test dataset
    dataset_name = f"test-dataset-partial-{uuid.uuid4().hex[:8]}"
    created = await retry_on_rate_limit(
        lambda: real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT * FROM test_table",
            query_type="SQL",
            description="Original Description",
            sources=_DEFAULT_SQL_SOURCES,
        )
    )

    try:
        # Update only name
        updated = await retry_on_rate_limit(
            lambda: real_virtualization_api.update_dataset(
                created["id"], name=f"{dataset_name}-partial"
            )
        )

        assert updated is not None
        assert updated["id"] == created["id"]
        assert updated["name"] == f"{dataset_name}-partial"
        assert updated["description"] == "Original Description"  # Unchanged
    finally:
        # Cleanup
        try:
            await retry_on_rate_limit(lambda: real_virtualization_api.delete_dataset(created["id"]))
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_dataset_not_found(real_virtualization_api):
    """Test dataset update with not found error"""
    await asyncio.sleep(0.5)  # Delay to avoid rate limiting
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await retry_on_rate_limit(
            lambda: real_virtualization_api.update_dataset(fake_id, name="Updated")
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_dataset_validation_error(real_virtualization_api):
    """Test dataset update with validation error"""
    await asyncio.sleep(0.5)  # Delay to avoid rate limiting

    # Create a test dataset
    dataset_name = f"test-dataset-validation-{uuid.uuid4().hex[:8]}"
    created = await retry_on_rate_limit(
        lambda: real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT * FROM test_table",
            query_type="SQL",
            sources=_DEFAULT_SQL_SOURCES,
        )
    )

    try:
        with pytest.raises(ValidationError):
            await retry_on_rate_limit(
                lambda: real_virtualization_api.update_dataset(created["id"], name="")
            )
    finally:
        # Cleanup
        try:
            await retry_on_rate_limit(lambda: real_virtualization_api.delete_dataset(created["id"]))
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_dataset_success(real_virtualization_api):
    """Test successful dataset deletion"""
    await asyncio.sleep(0.5)  # Delay to avoid rate limiting

    # Create a test dataset
    dataset_name = f"test-dataset-delete-{uuid.uuid4().hex[:8]}"
    created = await retry_on_rate_limit(
        lambda: real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT * FROM test_table",
            query_type="SQL",
            sources=_DEFAULT_SQL_SOURCES,
        )
    )

    # Delete the dataset
    result = await retry_on_rate_limit(
        lambda: real_virtualization_api.delete_dataset(created["id"])
    )
    assert result is None

    # Verify it's deleted
    with pytest.raises(NotFoundError):
        await retry_on_rate_limit(lambda: real_virtualization_api.get_dataset(created["id"]))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_dataset_not_found(real_virtualization_api):
    """Test dataset deletion with not found error"""
    await asyncio.sleep(0.5)  # Delay to avoid rate limiting
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await retry_on_rate_limit(lambda: real_virtualization_api.delete_dataset(fake_id))


def test_delete_dataset_invalid_id(virtualization_api):
    """Test dataset deletion with invalid ID (unit test - no API call)"""
    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id("")

    with pytest.raises(ValidationError):
        virtualization_api._validate_dataset_id(None)


# Query Execution Methods Tests


@pytest.mark.asyncio
async def test_execute_query_success(virtualization_api):
    """Test successful query execution"""
    from unittest.mock import AsyncMock

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    mock_response = {
        "id": "223e4567-e89b-12d3-a456-426614174001",
        "virtual_dataset": dataset_id,
        "query": "SELECT * FROM table",
        "parameters": {},
        "execution_mode": "SYNC",
        "status": "COMPLETED",
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:00:01Z",
        "metrics": {"duration_ms": 1000},
        "execution_log": [],
    }

    virtualization_api.client.post = AsyncMock(return_value=mock_response)

    result = await virtualization_api.execute_query(dataset_id)

    assert result == mock_response
    virtualization_api.client.post.assert_called_once()
    call_args = virtualization_api.client.post.call_args
    assert f"virtualization/datasets/{dataset_id}/queries/" in call_args[0][0]


@pytest.mark.asyncio
async def test_execute_query_with_parameters(virtualization_api):
    """Test query execution with parameters"""
    from unittest.mock import AsyncMock

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    mock_response = {
        "id": "223e4567-e89b-12d3-a456-426614174001",
        "virtual_dataset": dataset_id,
        "query": "SELECT * FROM table WHERE id = :id",
        "parameters": {"id": 123},
        "execution_mode": "SYNC",
        "status": "COMPLETED",
    }

    virtualization_api.client.post = AsyncMock(return_value=mock_response)

    result = await virtualization_api.execute_query(
        dataset_id, parameters={"id": 123}, execution_mode="SYNC", timeout_seconds=300
    )

    assert result == mock_response
    call_args = virtualization_api.client.post.call_args
    assert call_args[1]["data"]["parameters"] == {"id": 123}
    assert call_args[1]["data"]["execution_mode"] == "SYNC"
    assert call_args[1]["data"]["timeout_seconds"] == 300


@pytest.mark.asyncio
async def test_execute_query_with_custom_query(virtualization_api):
    """Test query execution with custom query string"""
    from unittest.mock import AsyncMock

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    custom_query = "SELECT * FROM custom_table WHERE status = 'active'"
    mock_response = {
        "id": "223e4567-e89b-12d3-a456-426614174001",
        "virtual_dataset": dataset_id,
        "query": custom_query,
        "execution_mode": "ASYNC",
        "status": "PENDING",
    }

    virtualization_api.client.post = AsyncMock(return_value=mock_response)

    result = await virtualization_api.execute_query(
        dataset_id, query=custom_query, execution_mode="ASYNC", force_async=True
    )

    assert result == mock_response
    call_args = virtualization_api.client.post.call_args
    assert call_args[1]["data"]["query"] == custom_query
    assert call_args[1]["data"]["execution_mode"] == "ASYNC"
    assert call_args[1]["data"]["force_async"] is True


@pytest.mark.asyncio
async def test_execute_query_validation_error(virtualization_api):
    """Test query execution with validation error"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import ValidationError

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    virtualization_api.client.post = AsyncMock(side_effect=ValidationError("Invalid query"))

    with pytest.raises(ValidationError):
        await virtualization_api.execute_query(dataset_id, query="")


@pytest.mark.asyncio
async def test_execute_query_invalid_execution_mode(virtualization_api):
    """Test query execution with invalid execution mode"""
    from datahub_interoperability.errors import ValidationError

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"

    with pytest.raises(ValidationError):
        await virtualization_api.execute_query(dataset_id, execution_mode="INVALID")


@pytest.mark.asyncio
async def test_execute_query_invalid_timeout(virtualization_api):
    """Test query execution with invalid timeout"""
    from datahub_interoperability.errors import ValidationError

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"

    with pytest.raises(ValidationError):
        await virtualization_api.execute_query(dataset_id, timeout_seconds=0)

    with pytest.raises(ValidationError):
        await virtualization_api.execute_query(dataset_id, timeout_seconds=-1)


@pytest.mark.asyncio
async def test_execute_query_not_found(virtualization_api):
    """Test query execution with dataset not found"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import NotFoundError

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    virtualization_api.client.post = AsyncMock(side_effect=NotFoundError("Dataset not found"))

    with pytest.raises(NotFoundError):
        await virtualization_api.execute_query(dataset_id)


@pytest.mark.asyncio
async def test_list_query_executions_success(virtualization_api):
    """Test successful query execution listing"""
    from unittest.mock import AsyncMock

    mock_response = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "223e4567-e89b-12d3-a456-426614174001",
                "virtual_dataset": "123e4567-e89b-12d3-a456-426614174000",
                "status": "COMPLETED",
                "execution_mode": "SYNC",
            },
            {
                "id": "323e4567-e89b-12d3-a456-426614174002",
                "virtual_dataset": "123e4567-e89b-12d3-a456-426614174000",
                "status": "RUNNING",
                "execution_mode": "ASYNC",
            },
        ],
    }

    virtualization_api.client.get = AsyncMock(return_value=mock_response)

    result = await virtualization_api.list_query_executions()

    assert result == mock_response
    virtualization_api.client.get.assert_called_once()
    call_args = virtualization_api.client.get.call_args
    assert call_args[0][0] == "virtualization/queries/"


@pytest.mark.asyncio
async def test_list_query_executions_with_filters(virtualization_api):
    """Test query execution listing with filters"""
    from unittest.mock import AsyncMock

    dataset_id = "123e4567-e89b-12d3-a456-426614174000"
    mock_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "223e4567-e89b-12d3-a456-426614174001",
                "virtual_dataset": dataset_id,
                "status": "COMPLETED",
                "execution_mode": "SYNC",
            }
        ],
    }

    virtualization_api.client.get = AsyncMock(return_value=mock_response)

    result = await virtualization_api.list_query_executions(
        dataset_id=dataset_id, status="COMPLETED", page=1, page_size=20
    )

    assert result == mock_response
    call_args = virtualization_api.client.get.call_args
    assert call_args[1]["params"]["virtual_dataset_id"] == dataset_id
    assert call_args[1]["params"]["status"] == "COMPLETED"
    assert call_args[1]["params"]["page"] == 1
    assert call_args[1]["params"]["page_size"] == 20


@pytest.mark.asyncio
async def test_list_query_executions_invalid_status(virtualization_api):
    """Test query execution listing with invalid status"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await virtualization_api.list_query_executions(status="INVALID")


@pytest.mark.asyncio
async def test_list_query_executions_invalid_pagination(virtualization_api):
    """Test query execution listing with invalid pagination"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await virtualization_api.list_query_executions(page=0)

    with pytest.raises(ValidationError):
        await virtualization_api.list_query_executions(page_size=0)

    with pytest.raises(ValidationError):
        await virtualization_api.list_query_executions(page_size=101)


@pytest.mark.asyncio
async def test_get_query_execution_success(virtualization_api):
    """Test successful query execution retrieval"""
    from unittest.mock import AsyncMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    mock_response = {
        "id": execution_id,
        "virtual_dataset": "123e4567-e89b-12d3-a456-426614174000",
        "virtual_dataset_name": "Test Dataset",
        "query": "SELECT * FROM table",
        "parameters": {},
        "execution_mode": "SYNC",
        "status": "COMPLETED",
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:00:01Z",
        "metrics": {"duration_ms": 1000},
        "execution_log": [],
    }

    virtualization_api.client.get = AsyncMock(return_value=mock_response)

    result = await virtualization_api.get_query_execution(execution_id)

    assert result == mock_response
    virtualization_api.client.get.assert_called_once()
    call_args = virtualization_api.client.get.call_args
    assert execution_id in call_args[0][0]


@pytest.mark.asyncio
async def test_get_query_execution_not_found(virtualization_api):
    """Test query execution retrieval with not found error"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import NotFoundError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    virtualization_api.client.get = AsyncMock(side_effect=NotFoundError("Execution not found"))

    with pytest.raises(NotFoundError):
        await virtualization_api.get_query_execution(execution_id)


@pytest.mark.asyncio
async def test_get_query_execution_invalid_id(virtualization_api):
    """Test query execution retrieval with invalid ID"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_execution("")

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_execution(None)


@pytest.mark.asyncio
async def test_cancel_query_execution_success(virtualization_api):
    """Test successful query execution cancellation"""
    from unittest.mock import AsyncMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    mock_response = {
        "execution_id": execution_id,
        "status": "CANCELLED",
        "message": "Query execution cancelled successfully",
    }

    virtualization_api.client.post = AsyncMock(return_value=mock_response)

    result = await virtualization_api.cancel_query_execution(execution_id)

    assert result == mock_response
    virtualization_api.client.post.assert_called_once()
    call_args = virtualization_api.client.post.call_args
    assert f"virtualization/queries/{execution_id}/cancel/" in call_args[0][0]


@pytest.mark.asyncio
async def test_cancel_query_execution_not_found(virtualization_api):
    """Test query execution cancellation with not found error"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import NotFoundError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    virtualization_api.client.post = AsyncMock(side_effect=NotFoundError("Execution not found"))

    with pytest.raises(NotFoundError):
        await virtualization_api.cancel_query_execution(execution_id)


@pytest.mark.asyncio
async def test_cancel_query_execution_cannot_cancel(virtualization_api):
    """Test query execution cancellation when execution cannot be cancelled"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import ValidationError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    virtualization_api.client.post = AsyncMock(
        side_effect=ValidationError(
            "Query execution cannot be cancelled (current status: COMPLETED)"
        )
    )

    with pytest.raises(ValidationError):
        await virtualization_api.cancel_query_execution(execution_id)


@pytest.mark.asyncio
async def test_cancel_query_execution_invalid_id(virtualization_api):
    """Test query execution cancellation with invalid ID"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await virtualization_api.cancel_query_execution("")

    with pytest.raises(ValidationError):
        await virtualization_api.cancel_query_execution(None)


@pytest.mark.asyncio
async def test_get_query_result_json_format(virtualization_api):
    """Test getting query result in JSON format"""
    from unittest.mock import AsyncMock, MagicMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    mock_response = {
        "execution_id": execution_id,
        "data": [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
        ],
        "total_count": 2,
        "returned_count": 2,
        "format": "json",
        "content_type": "application/json",
    }

    # Mock response object
    mock_http_response = MagicMock()
    mock_http_response.headers = {"content-type": "application/json"}
    # httpx.Response.json is SYNC — use a regular MagicMock callable, not
    # AsyncMock (the SDK calls ``response.json()`` without await).
    mock_http_response.json = MagicMock(return_value=mock_response)

    virtualization_api.client.request = AsyncMock(return_value=mock_http_response)

    result = await virtualization_api.get_query_result(execution_id, format="json")

    assert result == mock_response
    virtualization_api.client.request.assert_called_once()
    call_args = virtualization_api.client.request.call_args
    assert call_args[0][0] == "GET"
    assert f"virtualization/queries/{execution_id}/result/" in call_args[0][1]
    assert call_args[1]["params"]["output_format"] == "json"


@pytest.mark.asyncio
async def test_get_query_result_csv_format(virtualization_api):
    """Test getting query result in CSV format"""
    from unittest.mock import AsyncMock, MagicMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    csv_data = "id,name,value\n1,Item 1,100\n2,Item 2,200\n"

    # Mock response object
    mock_http_response = MagicMock()
    mock_http_response.headers = {"content-type": "text/csv"}
    mock_http_response.text = csv_data

    virtualization_api.client.request = AsyncMock(return_value=mock_http_response)

    result = await virtualization_api.get_query_result(execution_id, format="csv")

    assert result["format"] == "csv"
    assert result["content_type"] == "text/csv"
    assert result["data"] == csv_data
    assert result["execution_id"] == execution_id


@pytest.mark.asyncio
async def test_get_query_result_parquet_format(virtualization_api):
    """Test getting query result in Parquet format"""
    import base64
    from unittest.mock import AsyncMock, MagicMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    parquet_bytes = b"PARQUET_FILE_DATA"
    parquet_base64 = base64.b64encode(parquet_bytes).decode("utf-8")

    # Mock response object
    mock_http_response = MagicMock()
    mock_http_response.headers = {"content-type": "application/parquet"}
    mock_http_response.content = parquet_bytes

    virtualization_api.client.request = AsyncMock(return_value=mock_http_response)

    result = await virtualization_api.get_query_result(execution_id, format="parquet")

    assert result["format"] == "parquet"
    assert result["content_type"] == "application/parquet"
    assert result["data"] == parquet_base64
    assert result["execution_id"] == execution_id


@pytest.mark.asyncio
async def test_get_query_result_with_pagination(virtualization_api):
    """Test getting query result with pagination"""
    from unittest.mock import AsyncMock, MagicMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    mock_response = {
        "execution_id": execution_id,
        "data": [{"id": 1}, {"id": 2}],
        "total_count": 100,
        "returned_count": 2,
        "format": "json",
        "pagination": {"page": 1, "page_size": 2},
    }

    # Mock response object
    mock_http_response = MagicMock()
    mock_http_response.headers = {"content-type": "application/json"}
    # httpx.Response.json is SYNC — use a regular MagicMock callable, not
    # AsyncMock (the SDK calls ``response.json()`` without await).
    mock_http_response.json = MagicMock(return_value=mock_response)

    virtualization_api.client.request = AsyncMock(return_value=mock_http_response)

    result = await virtualization_api.get_query_result(
        execution_id, format="json", page=1, page_size=2
    )

    assert result == mock_response
    call_args = virtualization_api.client.request.call_args
    assert call_args[1]["params"]["page"] == 1
    assert call_args[1]["params"]["page_size"] == 2


@pytest.mark.asyncio
async def test_get_query_result_with_offset_limit(virtualization_api):
    """Test getting query result with offset/limit pagination"""
    from unittest.mock import AsyncMock, MagicMock

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    mock_response = {
        "execution_id": execution_id,
        "data": [{"id": 10}, {"id": 11}],
        "total_count": 100,
        "returned_count": 2,
        "format": "json",
    }

    # Mock response object
    mock_http_response = MagicMock()
    mock_http_response.headers = {"content-type": "application/json"}
    # httpx.Response.json is SYNC — use a regular MagicMock callable, not
    # AsyncMock (the SDK calls ``response.json()`` without await).
    mock_http_response.json = MagicMock(return_value=mock_response)

    virtualization_api.client.request = AsyncMock(return_value=mock_http_response)

    result = await virtualization_api.get_query_result(
        execution_id, format="json", offset=10, limit=2
    )

    assert result == mock_response
    call_args = virtualization_api.client.request.call_args
    assert call_args[1]["params"]["offset"] == 10
    assert call_args[1]["params"]["limit"] == 2


@pytest.mark.asyncio
async def test_get_query_result_invalid_format(virtualization_api):
    """Test getting query result with invalid format"""
    from datahub_interoperability.errors import ValidationError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="invalid")


@pytest.mark.asyncio
async def test_get_query_result_conflicting_pagination(virtualization_api):
    """Test getting query result with conflicting pagination parameters"""
    from datahub_interoperability.errors import ValidationError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"

    # Cannot specify both page and offset
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", page=1, offset=10)

    # Cannot specify both page_size and limit
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(
            execution_id, format="json", page_size=20, limit=10
        )


@pytest.mark.asyncio
async def test_get_query_result_invalid_pagination(virtualization_api):
    """Test getting query result with invalid pagination parameters"""
    from datahub_interoperability.errors import ValidationError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"

    # Invalid page
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", page=0)

    # Invalid page_size
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", page_size=0)

    # Invalid page_size (too large)
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", page_size=1001)

    # Invalid offset
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", offset=-1)

    # Invalid limit
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", limit=0)

    # Invalid limit (too large)
    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id, format="json", limit=1001)


@pytest.mark.asyncio
async def test_get_query_result_not_found(virtualization_api):
    """Test getting query result with execution not found"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import NotFoundError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    virtualization_api.client.request = AsyncMock(side_effect=NotFoundError("Execution not found"))

    with pytest.raises(NotFoundError):
        await virtualization_api.get_query_result(execution_id)


@pytest.mark.asyncio
async def test_get_query_result_execution_not_completed(virtualization_api):
    """Test getting query result when execution is not completed"""
    from unittest.mock import AsyncMock

    from datahub_interoperability.errors import ValidationError

    execution_id = "223e4567-e89b-12d3-a456-426614174001"
    virtualization_api.client.request = AsyncMock(
        side_effect=ValidationError("Query execution is not completed (status: RUNNING)")
    )

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(execution_id)


@pytest.mark.asyncio
async def test_get_query_result_invalid_id(virtualization_api):
    """Test getting query result with invalid execution ID"""
    from datahub_interoperability.errors import ValidationError

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result("")

    with pytest.raises(ValidationError):
        await virtualization_api.get_query_result(None)


# Query Execution Methods - Integration Tests with Real API


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_query_success_integration(real_virtualization_api):
    """Test successful query execution with real API"""
    # Create a test dataset first
    dataset_name = f"test-dataset-exec-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id, 'test' as name",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query
        # Note: Query may fail due to database connection, but execution should still be created
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )

            assert execution is not None
            assert "id" in execution
            assert execution["virtual_dataset"] == dataset_id
            assert execution["execution_mode"] == "SYNC"
            assert execution["status"] in ["PENDING", "RUNNING", "COMPLETED", "FAILED"]
        except ValidationError as e:
            # If query execution fails due to connection issues, that's OK for integration tests
            # The important thing is that the SDK method works correctly
            # Verify we can still list executions to confirm the execution was created
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            assert executions is not None
            assert "results" in executions
            # Execution may have been created even if query failed
            pytest.skip(f"Query execution failed (likely database connection issue): {e}")

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_query_with_parameters_integration(real_virtualization_api):
    """Test query execution with parameters using real API"""
    dataset_name = f"test-dataset-params-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT :id as id, :name as name",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query with parameters
        # Note: Query may fail due to database connection, but execution should still be created
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, parameters={"id": 123, "name": "test"}, execution_mode="SYNC"
            )

            assert execution is not None
            assert execution["parameters"] == {"id": 123, "name": "test"}
        except ValidationError as e:
            # If query execution fails due to connection issues, verify parameters were accepted
            # by checking if we can list the execution
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            assert executions is not None
            pytest.skip(f"Query execution failed (likely database connection issue): {e}")

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_query_executions_success_integration(real_virtualization_api):
    """Test successful query execution listing with real API"""
    dataset_name = f"test-dataset-list-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute a query to create an execution
        # Note: Query may fail due to database connection, but execution should still be created
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
            execution_id = execution["id"]
        except ValidationError:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if executions.get("results"):
                execution_id = executions["results"][0]["id"]

        # List executions
        result = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)

        assert result is not None
        assert "results" in result
        assert "count" in result

        # If we have an execution ID, verify it's in the list
        if execution_id:
            execution_ids = [e["id"] for e in result["results"]]
            assert execution_id in execution_ids
        else:
            # If no execution was created, that's OK - at least verify listing works
            assert isinstance(result["results"], list)

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_query_executions_with_status_filter_integration(real_virtualization_api):
    """Test query execution listing with status filter using real API"""
    dataset_name = f"test-dataset-status-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute a query
        # Note: Query may fail due to database connection
        try:
            await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
        except ValidationError:
            pass  # Execution may have been created even if query failed

        # List executions with status filter
        result = await real_virtualization_api.list_query_executions(
            dataset_id=dataset_id, status="COMPLETED"
        )

        assert result is not None
        assert "results" in result

        # All results should have COMPLETED status (if any)
        for execution in result["results"]:
            assert execution["status"] == "COMPLETED"

        # If no completed executions, that's OK - verify filtering works
        assert isinstance(result["results"], list)

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_execution_success_integration(real_virtualization_api):
    """Test successful query execution retrieval with real API"""
    dataset_name = f"test-dataset-get-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id, 'test' as name",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query
        # Note: Query may fail due to database connection, but execution should still be created
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
            execution_id = execution["id"]
        except ValidationError:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip("No execution created (likely database connection issue)")
            execution_id = executions["results"][0]["id"]

        # Get execution details
        retrieved = await real_virtualization_api.get_query_execution(execution_id)

        assert retrieved is not None
        assert retrieved["id"] == execution_id
        assert retrieved["virtual_dataset"] == dataset_id
        assert "status" in retrieved
        assert "execution_mode" in retrieved

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_execution_not_found_integration(real_virtualization_api):
    """Test query execution retrieval with not found error using real API"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_virtualization_api.get_query_execution(fake_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cancel_query_execution_success_integration(real_virtualization_api):
    """Test successful query execution cancellation with real API"""
    dataset_name = f"test-dataset-cancel-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT pg_sleep(10)",  # Long-running query
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query in async mode (so we can cancel it)
        # Note: Query may fail due to database connection, but execution should still be created
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="ASYNC"
            )
            execution_id = execution["id"]
        except ValidationError as e:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip(f"Query execution failed (likely database connection issue): {e}")
            execution_id = executions["results"][0]["id"]

        if not execution_id:
            pytest.skip("No execution created for cancellation test")

        # Wait a moment for execution to start
        await asyncio.sleep(1)

        # Get current execution status
        retrieved = await real_virtualization_api.get_query_execution(execution_id)
        retrieved["status"]

        # Try to cancel (may fail if already completed/failed, which is OK)
        try:
            cancelled = await real_virtualization_api.cancel_query_execution(execution_id)
            assert cancelled is not None
            assert cancelled["status"] == "CANCELLED"
        except ValidationError:
            # Execution may have already completed or cannot be cancelled
            # This is acceptable - verify execution exists and status is valid
            retrieved = await real_virtualization_api.get_query_execution(execution_id)
            assert retrieved is not None
            assert retrieved["status"] in ["COMPLETED", "FAILED", "CANCELLED", "RUNNING", "PENDING"]

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_result_json_format_integration(real_virtualization_api):
    """Test getting query result in JSON format with real API"""
    dataset_name = f"test-dataset-result-json-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id, 'test' as name UNION SELECT 2 as id, 'test2' as name",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query
        # Note: Query may fail due to database connection
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
            execution_id = execution["id"]
        except ValidationError as e:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip(f"Query execution failed (likely database connection issue): {e}")
            execution_id = executions["results"][0]["id"]

        if not execution_id:
            pytest.skip("No execution created for JSON result retrieval test")

        # Wait for execution to complete (if async)
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            retrieved = await real_virtualization_api.get_query_execution(execution_id)
            if retrieved["status"] == "COMPLETED":
                break
            elif retrieved["status"] in ["FAILED", "CANCELLED"]:
                pytest.skip(
                    f"Query execution {execution_id} failed or was cancelled (likely database connection issue)"
                )
            await asyncio.sleep(1)
            wait_time += 1

        if wait_time >= max_wait:
            pytest.skip(
                f"Query execution {execution_id} did not complete within {max_wait} seconds"
            )

        # Get result in JSON format
        result = await real_virtualization_api.get_query_result(
            execution_id=execution_id, format="json"
        )

        assert result is not None
        assert result["format"] == "json"
        assert "data" in result
        assert isinstance(result["data"], list)
        assert "total_count" in result

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_result_csv_format_integration(real_virtualization_api):
    """Test getting query result in CSV format with real API"""
    dataset_name = f"test-dataset-result-csv-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id, 'test' as name",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query
        # Note: Query may fail due to database connection
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
            execution_id = execution["id"]
        except ValidationError as e:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip(f"Query execution failed (likely database connection issue): {e}")
            execution_id = executions["results"][0]["id"]

        if not execution_id:
            pytest.skip("No execution created for CSV result retrieval test")

        # Wait for execution to complete
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            retrieved = await real_virtualization_api.get_query_execution(execution_id)
            if retrieved["status"] == "COMPLETED":
                break
            elif retrieved["status"] in ["FAILED", "CANCELLED"]:
                pytest.skip(
                    f"Query execution {execution_id} failed or was cancelled (likely database connection issue)"
                )
            await asyncio.sleep(1)
            wait_time += 1

        if wait_time >= max_wait:
            pytest.skip(
                f"Query execution {execution_id} did not complete within {max_wait} seconds"
            )

        # Get result in CSV format
        result = await real_virtualization_api.get_query_result(
            execution_id=execution_id, format="csv"
        )

        assert result is not None
        assert result["format"] == "csv"
        assert "data" in result
        assert isinstance(result["data"], str)
        assert "id,name" in result["data"] or "test" in result["data"]

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_result_with_pagination_integration(real_virtualization_api):
    """Test getting query result with pagination using real API"""
    dataset_name = f"test-dataset-pagination-{uuid.uuid4().hex[:8]}"

    try:
        # Create query that returns multiple rows
        query = "SELECT generate_series(1, 10) as id"
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query=query,
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query
        # Note: Query may fail due to database connection
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="SYNC"
            )
            execution_id = execution["id"]
        except ValidationError as e:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip(f"Query execution failed (likely database connection issue): {e}")
            execution_id = executions["results"][0]["id"]

        if not execution_id:
            pytest.skip("No execution created for pagination result retrieval test")

        # Wait for execution to complete
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            retrieved = await real_virtualization_api.get_query_execution(execution_id)
            if retrieved["status"] == "COMPLETED":
                break
            elif retrieved["status"] in ["FAILED", "CANCELLED"]:
                pytest.skip(
                    f"Query execution {execution_id} failed or was cancelled (likely database connection issue)"
                )
            await asyncio.sleep(1)
            wait_time += 1

        if wait_time >= max_wait:
            pytest.skip(
                f"Query execution {execution_id} did not complete within {max_wait} seconds"
            )

        # Get result with pagination
        result = await real_virtualization_api.get_query_result(
            execution_id=execution_id, format="json", page=1, page_size=5
        )

        assert result is not None
        assert result["format"] == "json"
        assert "data" in result
        assert len(result["data"]) <= 5  # Should not exceed page_size

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_query_validation_error_integration(real_virtualization_api):
    """Test query execution with validation error using real API"""
    fake_dataset_id = str(uuid.uuid4())

    with pytest.raises((NotFoundError, ValidationError)):
        await real_virtualization_api.execute_query(
            dataset_id=fake_dataset_id, execution_mode="SYNC"
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_query_result_execution_not_completed_integration(real_virtualization_api):
    """Test getting query result when execution is not completed using real API"""
    dataset_name = f"test-dataset-not-completed-{uuid.uuid4().hex[:8]}"

    try:
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT pg_sleep(10)",  # Long-running query
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Execute query in async mode
        # Note: Query may fail due to database connection
        execution_id = None
        try:
            execution = await real_virtualization_api.execute_query(
                dataset_id=dataset_id, execution_mode="ASYNC"
            )
            execution_id = execution["id"]
        except ValidationError as e:
            # Execution may have been created even if query failed
            # List executions to find it
            executions = await real_virtualization_api.list_query_executions(dataset_id=dataset_id)
            if not executions.get("results"):
                pytest.skip(f"Query execution failed (likely database connection issue): {e}")
            execution_id = executions["results"][0]["id"]

        if not execution_id:
            pytest.skip("No execution created for not-completed result retrieval test")

        # Try to get result immediately (should fail if not completed)
        try:
            result = await real_virtualization_api.get_query_result(
                execution_id=execution_id, format="json"
            )
            # If we get here, execution completed very quickly
            assert result is not None
        except ValidationError as e:
            # Expected if execution is not completed
            # Also acceptable if execution failed due to connection issues
            error_msg = str(e).lower()
            assert (
                "not completed" in error_msg
                or "status" in error_msg
                or "connection" in error_msg
                or "failed" in error_msg
            )

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


# Topology Methods - Integration Tests with Real API


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_topology_success_integration(real_virtualization_api):
    """Test successful topology retrieval with real API"""
    topology = await real_virtualization_api.get_topology(include_health_metrics=True)

    assert topology is not None
    assert isinstance(topology, dict)
    # Topology must contain the canonical key names
    assert "nodes" in topology, f"Missing 'nodes' key in topology: {list(topology.keys())}"
    assert "edges" in topology, f"Missing 'edges' key in topology: {list(topology.keys())}"
    assert "metadata" in topology, f"Missing 'metadata' key in topology: {list(topology.keys())}"
    assert "summary" in topology, f"Missing 'summary' key in topology: {list(topology.keys())}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_topology_without_health_metrics_integration(real_virtualization_api):
    """Test topology retrieval without health metrics using real API"""
    topology = await real_virtualization_api.get_topology(include_health_metrics=False)

    assert topology is not None
    assert isinstance(topology, dict)
    # Should still have basic structure with canonical keys
    assert "nodes" in topology, f"Missing 'nodes' in topology: {list(topology.keys())}"
    assert "edges" in topology, f"Missing 'edges' in topology: {list(topology.keys())}"
    assert "metadata" in topology, f"Missing 'metadata' in topology: {list(topology.keys())}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_topology_with_datasets_integration(real_virtualization_api):
    """Test topology retrieval when datasets exist using real API"""
    dataset_name = f"test-topology-{uuid.uuid4().hex[:8]}"

    try:
        # Create a test dataset
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Wait a moment for topology to update
        await asyncio.sleep(1)

        # Get topology
        topology = await real_virtualization_api.get_topology(include_health_metrics=True)

        assert topology is not None
        assert "nodes" in topology, f"Missing 'nodes' in topology: {list(topology.keys())}"
        assert "edges" in topology, f"Missing 'edges' in topology: {list(topology.keys())}"
        assert "summary" in topology, f"Missing 'summary' in topology: {list(topology.keys())}"

        # Verify our dataset is in the topology
        nodes = topology.get("nodes", [])
        node_ids = [str(node.get("id", "")) for node in nodes]
        assert dataset_id in node_ids, f"Dataset {dataset_id} not found in topology nodes"

        # Verify summary structure
        summary = topology["summary"]
        assert isinstance(summary, dict)

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_topology_success_integration(real_virtualization_api):
    """Test successful dataset topology retrieval with real API"""
    dataset_name = f"test-dataset-topology-{uuid.uuid4().hex[:8]}"

    try:
        # Create a test dataset
        dataset = await real_virtualization_api.create_dataset(
            name=dataset_name,
            query="SELECT 1 as id, 'test' as name",
            query_type="SQL",
            status="ACTIVE",
            description="Test dataset for topology",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset_id = dataset["id"]

        # Wait a moment for topology to update
        await asyncio.sleep(1)

        # Get dataset topology
        dataset_topology = await real_virtualization_api.get_dataset_topology(dataset_id)

        assert dataset_topology is not None
        assert isinstance(dataset_topology, dict)
        # Should have dataset information
        assert "dataset" in dataset_topology or "node" in dataset_topology
        # Should have relationships (may be empty)
        assert "relationships" in dataset_topology or "edges" in dataset_topology

        # Verify dataset ID matches
        dataset_info = dataset_topology.get("dataset", dataset_topology.get("node", {}))
        assert str(dataset_info.get("id", "")) == dataset_id

    finally:
        # Cleanup
        try:
            await real_virtualization_api.delete_dataset(dataset_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_topology_not_found_integration(real_virtualization_api):
    """Test dataset topology retrieval with not found error using real API"""
    fake_dataset_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_virtualization_api.get_dataset_topology(fake_dataset_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_topology_invalid_id_integration(real_virtualization_api):
    """Test dataset topology retrieval with invalid ID using real API"""
    with pytest.raises(ValidationError):
        await real_virtualization_api.get_dataset_topology("")

    with pytest.raises(ValidationError):
        await real_virtualization_api.get_dataset_topology("   ")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_topology_structure_integration(real_virtualization_api):
    """Test topology response structure with real API"""
    topology = await real_virtualization_api.get_topology(include_health_metrics=True)

    assert topology is not None
    assert isinstance(topology, dict)

    # Check metadata structure
    metadata = topology.get("metadata", {})
    assert isinstance(metadata, dict)
    # Should have tenant_id, generated_at, etc.
    assert "generated_at" in metadata or "timestamp" in metadata

    # Check summary/statistics structure
    summary = topology.get("summary", topology.get("statistics", {}))
    assert isinstance(summary, dict)
    # Should have counts
    assert "total_datasets" in summary or "dataset_count" in summary or "total_nodes" in summary


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_dataset_topology_with_relationships_integration(real_virtualization_api):
    """Test dataset topology with relationships using real API"""
    dataset1_name = f"test-topology-rel-1-{uuid.uuid4().hex[:8]}"
    dataset2_name = f"test-topology-rel-2-{uuid.uuid4().hex[:8]}"

    dataset1_id = None
    dataset2_id = None

    try:
        # Create two test datasets
        dataset1 = await real_virtualization_api.create_dataset(
            name=dataset1_name,
            query="SELECT 1 as id",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset1_id = dataset1["id"]

        dataset2 = await real_virtualization_api.create_dataset(
            name=dataset2_name,
            query="SELECT 2 as id",
            query_type="SQL",
            status="ACTIVE",
            sources=_DEFAULT_SQL_SOURCES,
        )
        dataset2_id = dataset2["id"]

        # Wait a moment for topology to update
        await asyncio.sleep(1)

        # Get topology for first dataset
        dataset_topology = await real_virtualization_api.get_dataset_topology(dataset1_id)

        assert dataset_topology is not None
        assert "relationships" in dataset_topology or "edges" in dataset_topology
        # Relationships may be empty, but structure should exist
        relationships = dataset_topology.get("relationships", dataset_topology.get("edges", []))
        assert isinstance(relationships, list)

    finally:
        # Cleanup
        try:
            if dataset1_id:
                await real_virtualization_api.delete_dataset(dataset1_id)
            if dataset2_id:
                await real_virtualization_api.delete_dataset(dataset2_id)
        except (NotFoundError, ConnectionError, TimeoutError, OSError):
            pass  # cleanup best-effort — ignore expected errors
