"""
Error Handling Tests — 278.AA.18

Tests the SDK error handling for: API errors (422, 409, 429),
network errors, response parsing edge cases, and error code mapping.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    DataHubError,
    ValidationError,
    UnauthorizedError,
    NotFoundError,
    RateLimitError,
    NetworkError,
    ConflictError,
    parse_error,
)


@pytest.fixture
def config():
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        max_retries=3,
    )


@pytest.fixture
async def client(config):
    async with DataHubClient(config) as c:
        yield c


# ── API error parsing ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parses_422_validation_error(client):
    from datahub_interoperability.errors import UnprocessableEntityError

    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.is_error = True
    mock_resp.json.return_value = {
        "error": {
            "code": "UNPROCESSABLE_ENTITY",
            "message": "name: This field is required.",
            "http_status": 422,
            "request_id": "req-abc",
            "details": {"field_errors": [{"field": "name", "message": "required"}]},
        }
    }
    err = httpx.HTTPStatusError("422", request=MagicMock(), response=mock_resp)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(UnprocessableEntityError) as exc:
            await client.post("assets/", {"name": ""})
        assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_parses_409_conflict(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 409
    mock_resp.is_error = True
    mock_resp.json.return_value = {
        "error": {
            "code": "CONFLICT",
            "message": "Version conflict — resource was modified",
            "http_status": 409,
            "request_id": "req-409",
        }
    }
    err = httpx.HTTPStatusError("409", request=MagicMock(), response=mock_resp)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(ConflictError) as exc:
            await client.post("assets/123/activate/", {"version": 1})
        assert exc.value.http_status == 409


@pytest.mark.asyncio
async def test_parses_429_rate_limit(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.is_error = True
    mock_resp.json.return_value = {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests",
            "http_status": 429,
            "request_id": "req-429",
        }
    }
    err = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(RateLimitError) as exc:
            await client.get("assets/")
        assert exc.value.http_status == 429


# ── Network error parsing ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handles_connection_error(client):
    err = httpx.ConnectError("DNS resolution failed for api.example.com")

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(NetworkError) as exc:
            await client.get("assets/123/")
        assert "Connection" in str(exc.value) or "DNS" in str(exc.value)


@pytest.mark.asyncio
async def test_handles_timeout_error(client):
    err = httpx.TimeoutException("Request to api.example.com timed out after 30s")

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(NetworkError):
            await client.get("assets/")


# ── Error response edge cases ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_handles_malformed_error_response(client):
    """Error response body is not valid JSON — should still raise."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.is_error = True
    mock_resp.json.side_effect = ValueError("not JSON")

    err = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_resp)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(DataHubError):
            await client.get("assets/")


@pytest.mark.asyncio
async def test_handles_empty_error_body(client):
    """Error response has no JSON body."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.is_error = True
    mock_resp.json.return_value = {}

    err = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_resp)

    with patch.object(client.client, "request", new_callable=AsyncMock) as req:
        req.side_effect = err
        with pytest.raises(DataHubError):
            await client.get("assets/")


# ── Error code mapping ─────────────────────────────────────────────────

def test_parse_error_validation():
    body = {"error": {"code": "VALIDATION_ERROR", "message": "Bad input", "http_status": 400}}
    err = parse_error(body)
    assert isinstance(err, ValidationError)
    assert err.http_status == 400


def test_parse_error_not_found():
    body = {"error": {"code": "NOT_FOUND", "message": "Missing", "http_status": 404}}
    err = parse_error(body)
    assert isinstance(err, NotFoundError)


def test_parse_error_unauthorized():
    body = {"error": {"code": "UNAUTHORIZED", "message": "No access", "http_status": 401}}
    err = parse_error(body)
    assert isinstance(err, UnauthorizedError)


def test_parse_error_rate_limit():
    body = {"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Slow down", "http_status": 429}}
    err = parse_error(body)
    assert isinstance(err, RateLimitError)


def test_parse_error_unknown_code():
    body = {"error": {"code": "SOME_FUTURE_CODE", "message": "Unknown", "http_status": 418}}
    err = parse_error(body)
    assert isinstance(err, DataHubError)
