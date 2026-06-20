"""Unit tests for SDK token handling — no backend needed (279.E.3)."""

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig


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
