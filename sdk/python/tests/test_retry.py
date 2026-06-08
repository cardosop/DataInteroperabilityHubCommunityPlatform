"""
Retry Logic Tests — 278.AA.18

Tests the client retry mechanism for transient errors,
rate limiting, network failures, and timeout behaviour.
Uses unittest.mock to simulate HTTP responses (project
convention — no additional mocking library required).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import DataHubError, NetworkError, RateLimitError


@pytest.fixture
def config():
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        max_retries=3,
        timeout=30.0,
    )


@pytest.fixture
async def client(config):
    async with DataHubClient(config) as c:
        yield c


# ── Transient error retries ────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code,message", [
    (502, "Bad Gateway"),
    (503, "Service Unavailable"),
    (504, "Gateway Timeout"),
])
async def test_retries_on_transient_server_error(client, status_code, message):
    """All 5xx server errors are retryable — first attempt fails, second succeeds."""
    mock_err = MagicMock()
    mock_err.status_code = status_code
    mock_err.is_error = True
    mock_err.json.return_value = {
        "error": {"code": "SERVER_ERROR", "message": message, "http_status": status_code}
    }

    mock_ok = MagicMock()
    mock_ok.json.return_value = {"status": "ok"}
    mock_ok.is_error = False

    err = httpx.HTTPStatusError(str(status_code), request=MagicMock(), response=mock_err)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = [err, mock_ok]
        result = await client.get("assets/123/")
        assert result == {"status": "ok"}
        assert req.call_count == 2


# ── Network error retries ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retries_on_network_error(client):
    mock_ok = MagicMock()
    mock_ok.json.return_value = {"status": "ok"}
    mock_ok.is_error = False

    net_err = httpx.ConnectError("Connection refused")

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = [net_err, mock_ok]
        result = await client.get("assets/123/")
        assert result == {"status": "ok"}
        assert req.call_count == 2


@pytest.mark.asyncio
async def test_retries_on_timeout(client):
    mock_ok = MagicMock()
    mock_ok.json.return_value = {"status": "ok"}
    mock_ok.is_error = False

    timeout_err = httpx.TimeoutException("Request timed out")

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = [timeout_err, mock_ok]
        result = await client.get("assets/123/")
        assert result == {"status": "ok"}
        assert req.call_count == 2


# ── Max retries exhaustion ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_raises_after_max_retries_exhausted(client):
    mock_err = MagicMock()
    mock_err.status_code = 503
    mock_err.is_error = True
    mock_err.json.return_value = {"error": {"code": "SERVER_ERROR", "message": "Service Unavailable", "http_status": 503}}
    err = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_err)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err  # Every call fails
        with pytest.raises(DataHubError):
            await client.get("assets/123/")
        # 1 initial + 3 retries = 4 attempts
        assert req.call_count == 4


@pytest.mark.asyncio
async def test_raises_after_max_retries_on_network_error(client):
    net_err = httpx.ConnectError("Connection refused")

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = net_err
        with pytest.raises(NetworkError):
            await client.get("assets/123/")
        assert req.call_count == 4


# ── Non-retryable errors ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_does_not_retry_on_400(client):
    from datahub_interoperability.errors import ValidationError

    mock_err = MagicMock()
    mock_err.status_code = 400
    mock_err.is_error = True
    mock_err.json.return_value = {
        "error": {"code": "VALIDATION_ERROR", "message": "Bad request", "http_status": 400}
    }
    err = httpx.HTTPStatusError("400", request=MagicMock(), response=mock_err)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(ValidationError):
            await client.get("assets/123/")
        assert req.call_count == 1  # No retry on 4xx


@pytest.mark.asyncio
async def test_does_not_retry_on_404(client):
    from datahub_interoperability.errors import NotFoundError

    mock_err = MagicMock()
    mock_err.status_code = 404
    mock_err.is_error = True
    mock_err.json.return_value = {
        "error": {"code": "NOT_FOUND", "message": "Not found", "http_status": 404}
    }
    err = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_err)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(NotFoundError):
            await client.get("assets/123/")
        assert req.call_count == 1
