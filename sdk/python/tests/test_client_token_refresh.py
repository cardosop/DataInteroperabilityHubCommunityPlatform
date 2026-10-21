"""Unit tests for SDK token handling — no backend needed (279.E.3).

W6.2 (oss-release-remediation R2-X2): the proactive-refresh path was
silently broken — ``DataHubClientConfig`` is ``frozen=True`` and
``_get_headers`` assigned ``config.api_token = new_token``, which raised
ValidationError inside a bare ``except Exception: pass``.  The token was
therefore NEVER updated proactively and every post-expiry request paid a
guaranteed 401 round-trip.  The real-server tests below pin the fix: the
NEW token must reach the wire on the FIRST request.
"""

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from tests.fixtures.test_data import unique_port


def _make_jwt(exp_offset: int, sub: str = "sdk-test") -> str:
    """Build an unsigned JWT-shaped token at runtime (no committed creds)."""
    payload = {"sub": sub, "exp": int(time.time()) + exp_offset}
    enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJIUzI1NiJ9.{enc}.sig"


class _RecordingHandler(BaseHTTPRequestHandler):
    """Real local HTTP server: records the Authorization header of every
    request so tests can assert exactly which token reached the wire."""

    seen_auth: ClassVar[list[str | None]] = []

    def do_GET(self):
        type(self).seen_auth.append(self.headers.get("Authorization"))
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def make_config(**overrides):
    return DataHubClientConfig(
        base_url="https://meshant-internal.example.com",
        api_token=overrides.pop("api_token", "test-jwt-token"),
        **overrides,
    )


class TestTokenDetection:
    """API key vs JWT detection in _get_headers."""

    @pytest.mark.asyncio
    async def test_api_key_uses_apikey_header(self):
        config = make_config(api_token="meshant_key_abc123noDots")
        client = DataHubClient(config)
        headers = await client._get_headers()
        assert headers["Authorization"] == "ApiKey meshant_key_abc123noDots"

    @pytest.mark.asyncio
    async def test_jwt_uses_bearer_header(self):
        config = make_config(api_token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dummy")
        client = DataHubClient(config)
        headers = await client._get_headers()
        assert (
            headers["Authorization"]
            == "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dummy"
        )

    @pytest.mark.asyncio
    async def test_no_token_has_no_auth_header(self):
        config = make_config(api_token="")
        client = DataHubClient(config)
        headers = await client._get_headers()
        assert "Authorization" not in headers


class TestTokenRefreshCallback:
    """Token refresh callback wiring."""

    @pytest.mark.asyncio
    async def test_callback_is_invoked_during_refresh(self):
        """The stored callback is actually invoked and its return value
        updates the client token."""
        config = make_config()
        client = DataHubClient(config)
        callback_invoked = False

        async def refresh():
            nonlocal callback_invoked
            callback_invoked = True
            return "refreshed-token"

        client.set_token_refresh_callback(refresh)
        assert client.token_refresh_callback is not None

        # Invoke the callback directly — verify contract: callback returns
        # the new token, which the client uses to update its config.
        new_token = await client.token_refresh_callback()
        assert callback_invoked is True
        assert new_token == "refreshed-token"
        client.set_api_token(new_token)
        assert client.config.api_token == "refreshed-token"


class TestClientCreation:
    """Client creation with valid config."""

    def test_valid_config_creates_client(self):
        config = make_config()
        client = DataHubClient(config)
        assert client.config.base_url == "https://meshant-internal.example.com"
        assert client.config.api_token == "test-jwt-token"


@pytest.fixture
def recording_server():
    """Spin a real local HTTP server (stdlib, no mocks) that records the
    Authorization header of every request it receives."""
    _RecordingHandler.seen_auth = []
    server = HTTPServer(("127.0.0.1", unique_port()), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


class TestProactiveRefreshRealServer:
    """W6.2 — proactive refresh must replace the token BEFORE the first
    wire round-trip, even though the config model is frozen (R2-X2)."""

    @pytest.mark.asyncio
    async def test_expired_jwt_is_refreshed_before_first_request(self, recording_server):
        """An expired JWT + refresh callback must result in the FIRST
        request already carrying the refreshed token — no 401 round-trip."""
        expired = _make_jwt(-60)
        fresh = _make_jwt(3600)
        config = DataHubClientConfig(base_url=recording_server, api_token=expired)
        client = DataHubClient(config)

        refresh_calls: list[int] = []

        async def refresh_cb() -> str:
            refresh_calls.append(1)
            return fresh

        client.set_token_refresh_callback(refresh_cb)

        result = await client.get("/probe/")
        assert result == {"ok": True}
        # The callback ran exactly once and the NEW token hit the wire.
        assert refresh_calls == [1]
        assert _RecordingHandler.seen_auth == [f"Bearer {fresh}"]
        # The client's stored token is the refreshed one…
        assert client.config.api_token == fresh
        # …but the ORIGINAL config object was replaced, not mutated
        # (the frozen contract holds: the caller's instance is untouched).
        assert config.api_token == expired
        assert config.model_config.get("frozen") is True
        await client.close()

    @pytest.mark.asyncio
    async def test_non_expired_token_sends_no_refresh_round_trip(self, recording_server):
        """A valid (non-expired) JWT must go out as-is; the refresh
        callback must NOT fire."""
        valid = _make_jwt(3600)
        config = DataHubClientConfig(base_url=recording_server, api_token=valid)
        client = DataHubClient(config)

        async def refresh_cb() -> str:
            raise AssertionError("refresh callback must not run for a valid token")

        client.set_token_refresh_callback(refresh_cb)

        result = await client.get("/probe/")
        assert result == {"ok": True}
        assert _RecordingHandler.seen_auth == [f"Bearer {valid}"]
        await client.close()

    @pytest.mark.asyncio
    async def test_failed_refresh_falls_through_with_old_token(self, recording_server):
        """A failing refresh must NOT corrupt state: the old token still
        goes out and no exception escapes _get_headers."""
        expired = _make_jwt(-60)
        config = DataHubClientConfig(base_url=recording_server, api_token=expired)
        client = DataHubClient(config)

        async def refresh_cb() -> str:
            raise RuntimeError("refresh backend down")

        client.set_token_refresh_callback(refresh_cb)

        result = await client.get("/probe/")
        assert result == {"ok": True}
        assert _RecordingHandler.seen_auth == [f"Bearer {expired}"]
        assert client.config.api_token == expired
        await client.close()
