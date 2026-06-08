"""
Unit tests for APIClient.

Tests the core HTTP layer: _request() retry/auth/timeout logic and
_handle_response() status-code routing.  Only ``requests.request`` is
mocked at the module level — the real ``APIClient`` instance is used
with a controlled ``auth_manager`` injected directly.
"""
import pytest
import requests
from unittest.mock import Mock, patch

from datahub_cli.api_client import APIClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code=200, json_body=None, content=b"{}", url="",
                   text_body=None):
    """Build a realistic ``requests.Response`` for use with mocked requests."""
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    resp._content = content
    resp.url = url or "http://localhost:8000/api/v1/test/endpoint"
    resp.headers = {"Content-Type": "application/json"}
    resp.encoding = "utf-8"
    # ``response.text`` is computed from bytes content in the real Response;
    # ``handle_api_error`` reads ``response.text`` so we must set it.
    resp.text = text_body if text_body is not None else content.decode("utf-8")
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.return_value = {}
    return resp


def _auth_manager_mock(*, authenticated=True, headers=None, api_key=None):
    """Return a Mock that quacks like AuthManager for APIClient injection."""
    am = Mock()
    am.ensure_authenticated.return_value = authenticated
    am.get_auth_headers.return_value = headers or {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
    }
    # Config sub-mock for the 401 / API-key check path
    cfg = Mock()
    cfg.get_api_key.return_value = api_key  # None = JWT path; non-None = API-key path
    am.config = cfg
    return am


# ---------------------------------------------------------------------------
# _request() tests
# ---------------------------------------------------------------------------

class TestAPIClientRequest:
    """Unit tests for APIClient._request()."""

    # -- dry-run -----------------------------------------------------------

    def test_dry_run_write_method_returns_synthetic_response(self):
        client = APIClient()
        client.dry_run = True
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            resp = client._request("POST", "test/endpoint", json_data={"key": "val"})

        assert resp.status_code == 200
        assert resp._content == b"{}"
        mock_request.assert_not_called()

    def test_dry_run_read_method_does_real_request(self):
        client = APIClient()
        client.dry_run = True
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(200, {"items": []})
            client._request("GET", "test/endpoint")

        mock_request.assert_called_once()

    # -- authentication ----------------------------------------------------

    def test_authentication_failure_raises_click_exception(self):
        from click import ClickException

        client = APIClient()
        client.auth_manager = _auth_manager_mock(authenticated=False)

        with pytest.raises(ClickException, match="Not authenticated"):
            with patch("datahub_cli.api_client.requests.request") as mock_request:
                client._request("GET", "test")
        mock_request.assert_not_called()

    # -- retry on connection error ----------------------------------------

    def test_retry_on_connection_error_then_succeeds(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.side_effect = [
                requests.exceptions.ConnectionError("refused"),
                requests.exceptions.ConnectionError("refused"),
                _make_response(200, {"ok": True}),
            ]
            resp = client._request("GET", "test")

        assert resp.status_code == 200
        assert mock_request.call_count == 3

    def test_retry_exhausted_raises_click_exception(self):
        from click import ClickException

        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.side_effect = [
                requests.exceptions.ConnectionError("refused"),
                requests.exceptions.ConnectionError("refused"),
                requests.exceptions.ConnectionError("refused"),
            ]
            with pytest.raises(ClickException, match="after 3 attempts"):
                client._request("GET", "test")

    def test_timeout_retry_then_succeeds(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.side_effect = [
                requests.exceptions.Timeout("timed out"),
                _make_response(200, {"ok": True}),
            ]
            resp = client._request("GET", "test")

        assert resp.status_code == 200
        assert mock_request.call_count == 2

    # -- timeout detection -------------------------------------------------

    def test_workflow_endpoint_gets_120s_timeout(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(200, {})
            client._request("POST", "contracts/products/something")

        assert mock_request.call_args[1]["timeout"] == 120

    def test_regular_endpoint_gets_30s_timeout(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(200, {})
            client._request("GET", "assets/list")

        assert mock_request.call_args[1]["timeout"] == 30

    def test_custom_timeout_overrides_detection(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(200, {})
            client._request("POST", "contracts/products/", timeout=60)

        assert mock_request.call_args[1]["timeout"] == 60

    # -- 401 handling -----------------------------------------------------

    def test_401_with_api_key_does_not_refresh(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock(api_key="some-api-key")

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(401)
            resp = client._request("GET", "test")

        assert resp.status_code == 401
        client.auth_manager.refresh_access_token.assert_not_called()

    def test_401_with_jwt_refreshes_and_retries(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock(api_key=None)  # no API key → JWT
        client.auth_manager.refresh_access_token.return_value = True
        new_headers = {"Authorization": "Bearer new-token"}
        client.auth_manager.get_auth_headers.side_effect = [
            {"Authorization": "Bearer old-token"},
            new_headers,
        ]

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.side_effect = [
                _make_response(401),
                _make_response(200, {"ok": True}),
            ]
            resp = client._request("GET", "test")

        assert resp.status_code == 200
        client.auth_manager.refresh_access_token.assert_called_once()
        assert mock_request.call_count == 2
        # Second call must use the refreshed headers
        assert mock_request.call_args_list[1][1]["headers"] == new_headers

    def test_401_with_jwt_refresh_fails_raises_click_exception(self):
        from click import ClickException

        client = APIClient()
        client.auth_manager = _auth_manager_mock(api_key=None)
        client.auth_manager.refresh_access_token.return_value = False

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(401)
            with pytest.raises(ClickException, match="Authentication failed"):
                client._request("GET", "test")

    # -- misc --------------------------------------------------------------

    def test_stream_parameter_is_passed_through(self):
        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.return_value = _make_response(200)
            client._request("GET", "test", stream=True)

        assert mock_request.call_args[1]["stream"] is True

    def test_response_none_after_retry_raises(self):
        from click import ClickException

        client = APIClient()
        client.auth_manager = _auth_manager_mock()

        with patch("datahub_cli.api_client.requests.request") as mock_request:
            mock_request.side_effect = [
                requests.exceptions.ConnectionError("refused"),
                requests.exceptions.ConnectionError("refused"),
                None,  # should not happen, but line 114-115 handles it
            ]
            with pytest.raises(ClickException, match="No response received"):
                client._request("GET", "test")


# ---------------------------------------------------------------------------
# _handle_response() tests
# ---------------------------------------------------------------------------

class TestAPIClientHandleResponse:
    """Unit tests for APIClient._handle_response()."""

    def test_400_raises_via_handle_api_error(self):
        from click import ClickException

        client = APIClient()
        resp = _make_response(400, json_body={"error": "bad request"},
                              text_body='{"error":"bad request"}')

        with pytest.raises(ClickException):
            client._handle_response(resp)

    def test_500_raises_via_handle_api_error(self):
        from click import ClickException

        client = APIClient()
        resp = _make_response(500, json_body={"error": "server error"},
                              text_body='{"error":"server error"}')

        with pytest.raises(ClickException):
            client._handle_response(resp)

    def test_204_no_content_returns_empty_dict(self):
        client = APIClient()
        resp = _make_response(204, content=b"")

        result = client._handle_response(resp)
        assert result == {}

    def test_200_valid_json_returns_dict(self):
        client = APIClient()
        resp = _make_response(200, json_body={"key": "val"})

        result = client._handle_response(resp)
        assert result == {"key": "val"}

    def test_200_none_json_returns_empty_dict(self):
        client = APIClient()
        resp = _make_response(200, json_body=None)

        result = client._handle_response(resp)
        assert result == {}

    def test_200_non_json_returns_empty_dict(self):
        client = APIClient()
        resp = _make_response(200)
        resp.json.side_effect = ValueError("not JSON")

        result = client._handle_response(resp)
        assert result == {}
