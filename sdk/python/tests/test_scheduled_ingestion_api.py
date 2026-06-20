from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Scheduled Ingestion API.
"""
from unittest.mock import AsyncMock

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.scheduled_ingestion import ScheduledIngestionAPI


@pytest.fixture
def client():
    """Create test client."""
    config = DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )
    return DataHubClient(config)


@pytest.fixture
def ingestion_api(client):
    """Create Scheduled Ingestion API instance."""
    return ScheduledIngestionAPI(client)


@pytest.mark.asyncio
async def test_create_ingestion(ingestion_api, client):
    """Test creating scheduled ingestion."""
    expected_response = {"id": "123", "name": "test-ingestion"}
    client.post = AsyncMock(return_value=expected_response)

    result = await ingestion_api.create(
        name="test-ingestion",
        source_type="s3",
        source_config={"bucket": "test-bucket"},
        schedule="0 0 * * *",
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "scheduled-ingestions/",
        data={
            "name": "test-ingestion",
            "source_type": "s3",
            "source_config": {"bucket": "test-bucket"},
            "schedule": "0 0 * * *",
        },
    )


@pytest.mark.asyncio
async def test_list_ingestions(ingestion_api, client):
    """Test listing scheduled ingestions."""
    expected_response = {"count": 10, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await ingestion_api.list()

    assert result == expected_response
    client.get.assert_called_once_with("scheduled-ingestions/", params={"page": 1, "page_size": 50})


@pytest.mark.asyncio
async def test_get_ingestion(ingestion_api, client):
    """Test getting scheduled ingestion."""
    expected_response = {"id": "123", "name": "test-ingestion"}
    client.get = AsyncMock(return_value=expected_response)

    result = await ingestion_api.get("123")

    assert result == expected_response
    client.get.assert_called_once_with("scheduled-ingestions/123/")


@pytest.mark.asyncio
async def test_trigger_ingestion(ingestion_api, client):
    """Test triggering scheduled ingestion."""
    expected_response = {"run_id": "run-123"}
    client.post = AsyncMock(return_value=expected_response)

    result = await ingestion_api.trigger("123")

    assert result == expected_response
    client.post.assert_called_once_with("scheduled-ingestions/123/trigger/")


@pytest.mark.asyncio
async def test_get_run_history(ingestion_api, client):
    """Test getting run history."""
    expected_response = {"count": 5, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await ingestion_api.get_run_history("123")

    assert result == expected_response
    client.get.assert_called_once_with(
        "scheduled-ingestions/123/runs/",
        params={"page": 1, "page_size": 50},
    )
