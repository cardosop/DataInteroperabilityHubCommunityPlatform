"""279.I.2 — Token refresh tests for SDK DataHubClient.

Verifies that the token refresh callback is invoked correctly and
that concurrent refreshes do not corrupt client state.
These are unit-level tests of the refresh mechanism — they do not
simulate actual 401 HTTP responses (which requires a live server
or HTTP mocking not available in this test environment).
"""
import asyncio
import base64
import json
import time

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig


def _make_jwt(exp_offset: int) -> str:
    payload = {"sub": "u1", "exp": int(time.time()) + exp_offset}
    enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJIUzI1NiJ9.{enc}.sig"


class TestAsyncTokenRefreshRace:
    """Async race: two coroutines both encounter conditions that trigger
    a token refresh, verifying that the callback is invoked correctly
    and concurrent execution does not corrupt state."""

    @pytest.mark.asyncio
    async def test_concurrent_refresh_invokes_callback_at_least_once(self):
        """Two concurrent calls to _get_headers() each trigger a refresh
        check.  The refresh callback must be invoked at least once.
        """
        token = _make_jwt(-60)  # expired
        config = DataHubClientConfig(base_url="https://test.local", api_token=token)
        client = DataHubClient(config)

        refresh_calls = [0]
        new_token = _make_jwt(3600)

        async def refresh_cb():
            refresh_calls[0] += 1
            await asyncio.sleep(0.01)
            return new_token

        client.set_token_refresh_callback(refresh_cb)

        async def make_request():
            headers = await client._get_headers()
            return headers.get("Authorization", "")

        results = await asyncio.gather(make_request(), make_request())

        # Both results must contain a Bearer token with a non-empty value
        assert all(r.startswith("Bearer ") and len(r) > 7 for r in results), (
            f"Authorization headers invalid: {results}"
        )
        # The callback must have been called at least once
        assert refresh_calls[0] >= 1, (
            f"Refresh callback was never invoked ({refresh_calls[0]} calls)"
        )

    @pytest.mark.asyncio
    async def test_refresh_failure_preserves_existing_token(self):
        """When the refresh callback returns an empty token (failure),
        the client must preserve the existing token rather than
        replacing it with empty or corrupting internal state."""
        token = _make_jwt(-60)
        config = DataHubClientConfig(base_url="https://test.local", api_token=token)
        client = DataHubClient(config)

        async def bad_refresh():
            return ""  # Empty token = refresh failure

        client.set_token_refresh_callback(bad_refresh)

        headers = await client._get_headers()
        auth = headers.get("Authorization", "")

        # Must still have a Bearer header with the old (non-empty) token
        assert auth.startswith("Bearer ") and len(auth) > 7, (
            f"Authorization header invalid after failed refresh: {auth!r}"
        )
        # The client's stored token must be unchanged
        assert client.config.api_token == token, (
            "Client token was overwritten after failed refresh"
        )

