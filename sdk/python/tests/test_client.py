"""
Client Tests
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    NetworkError,
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


@pytest.mark.asyncio
async def test_client_initialization(config):
    """Test client initialization"""
    async with DataHubClient(config) as client:
        assert client.config.base_url == "https://api.example.com/api/v1"
        assert client.config.api_token == "test-token"


@pytest.mark.asyncio
async def test_client_requires_base_url():
    """Test that base_url is required"""
    with pytest.raises(ValueError, match="base_url is required"):
        config = DataHubClientConfig(base_url="")
        async with DataHubClient(config):
            pass


@pytest.mark.asyncio
async def test_get_request(client):
    """Test GET request"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "123", "name": "Test Asset"}
    mock_response.is_error = False

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        result = await client.get("/assets/123/")

        assert result == {"id": "123", "name": "Test Asset"}
        mock_request.assert_called_once()
        call_method, call_url = mock_request.call_args[0]
        assert call_method == "GET"
        assert call_url == "/assets/123/"


@pytest.mark.asyncio
async def test_post_request(client):
    """Test POST request"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "123", "name": "New Asset"}
    mock_response.is_error = False

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        result = await client.post("/assets/", data={"name": "New Asset"})

        assert result == {"id": "123", "name": "New Asset"}
        mock_request.assert_called_once()
        call_method, call_url = mock_request.call_args[0]
        assert call_method == "POST"
        assert call_url == "/assets/"
        # Payload is sent as json; verify it reaches the request
        assert mock_request.call_args[1]["json"] == {"name": "New Asset"}


@pytest.mark.asyncio
async def test_error_handling_404(client):
    """Test 404 error handling"""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
            "http_status": 404,
            "request_id": "req-123",
        }
    }
    mock_response.is_error = True
    
    error = httpx.HTTPStatusError(
        "404 Not Found",
        request=MagicMock(),
        response=mock_response,
    )
    
    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = error
        
        with pytest.raises(NotFoundError) as exc_info:
            await client.get("/assets/123/")
        
        assert exc_info.value.http_status == 404
        assert exc_info.value.request_id == "req-123"


@pytest.mark.asyncio
async def test_error_handling_400(client):
    """Test 400 error handling"""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid input",
            "http_status": 400,
            "request_id": "req-123",
            "details": {"field_errors": []},
        }
    }
    mock_response.is_error = True
    
    error = httpx.HTTPStatusError(
        "400 Bad Request",
        request=MagicMock(),
        response=mock_response,
    )
    
    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = error
        
        with pytest.raises(ValidationError) as exc_info:
            await client.post("/assets/", {})
        
        assert exc_info.value.http_status == 400
        assert exc_info.value.details == {"field_errors": []}


@pytest.mark.asyncio
async def test_token_refresh(client):
    """Test token refresh on 401"""
    async def refresh_token():
        return "new-token"
    
    client.set_token_refresh_callback(refresh_token)
    
    # First request fails with 401
    mock_response_401 = MagicMock()
    mock_response_401.status_code = 401
    mock_response_401.is_error = True
    
    # Second request succeeds
    mock_response_200 = MagicMock()
    mock_response_200.json.return_value = {"id": "123"}
    mock_response_200.is_error = False
    
    error_401 = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=mock_response_401,
    )
    
    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [error_401, mock_response_200]

        result = await client.get("/assets/123/")

        assert result == {"id": "123"}
        assert client.config.api_token == "new-token"
        assert mock_request.call_count == 2
        # Both calls target the same URL; second succeeds after token refresh
        assert mock_request.call_args_list[0][0][0] == "GET"
        assert mock_request.call_args_list[0][0][1] == "/assets/123/"
        assert mock_request.call_args_list[1][0][0] == "GET"
        assert mock_request.call_args_list[1][0][1] == "/assets/123/"


@pytest.mark.asyncio
async def test_set_api_token(client):
    """Test setting API token"""
    client.set_api_token("new-token")
    assert client.config.api_token == "new-token"

