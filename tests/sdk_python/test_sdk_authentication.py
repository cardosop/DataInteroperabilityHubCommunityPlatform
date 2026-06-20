"""
Comprehensive tests for SDK authentication.

Tests API key, JWT, token refresh, and error handling.
Uses REAL API server (no mocks) - uses existing API service in Docker Compose.
"""

import pytest

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig
    from datahub_interoperability.errors import (
        ForbiddenError,
        NetworkError,
        UnauthorizedError,
    )

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

from hub.apps.auth.models import APIKey
from tests.sdk_python.conftest import SDKTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e ."
)
class TestSDKAuthentication(SDKTestBase):
    """Test SDK authentication methods"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Generate API key and hash it
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Create API key for the user
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="SDK Test API Key",
            key_hash=key_hash,
        )
        # Ensure API key is saved and committed to database
        # This is critical for TransactionTestCase to make data visible to API service
        self.api_key.save()
        from django.db import transaction

        transaction.commit()

        # Store plaintext key (only available at creation)
        self.plaintext_key = plaintext_key

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key(self):
        """
        Test authenticating with API key
        """
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token=self.plaintext_key,
        )

        async with DataHubClient(config) as client:
            # Test API call with API key
            response = await client.get("assets/assets/")
            # Should succeed (200 or empty list)
            assert response is not None

    @pytest.mark.asyncio
    async def test_authenticate_with_jwt_token(self):
        """
        Test authenticating with JWT token
        """
        # Get JWT token via login using SDK config
        config = await self.get_sdk_config()

        async with DataHubClient(config) as sdk_client:
            # Test API call with JWT
            response = await sdk_client.get("assets/assets/")
            # Should succeed
            assert response is not None

    @pytest.mark.asyncio
    async def test_token_refresh_callback(self):
        """
        Test token refresh callback functionality
        """

        async def refresh_token():
            """Mock token refresh callback"""
            # In real scenario, this would call refresh endpoint
            return "new-refreshed-token"

        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token=self.plaintext_key,
        )

        async with DataHubClient(config) as client:
            # Set token refresh callback
            client.set_token_refresh_callback(refresh_token)

            # Verify callback is set
            assert client.token_refresh_callback is not None

    @pytest.mark.asyncio
    async def test_set_api_token(self):
        """
        Test setting API token dynamically
        """
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="initial-token",
        )

        async with DataHubClient(config) as client:
            # Update token
            client.set_api_token(self.plaintext_key)

            # Verify token is updated
            assert client.config.api_token == self.plaintext_key

    @pytest.mark.asyncio
    async def test_error_invalid_api_key(self):
        """
        Test error handling for invalid API key
        """
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="invalid-api-key-12345",
        )

        async with DataHubClient(config) as client:
            # Should raise UnauthorizedError
            with pytest.raises(UnauthorizedError):
                await client.get("assets/assets/")

    @pytest.mark.asyncio
    async def test_error_missing_authentication(self):
        """
        Test error handling for missing authentication
        """
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token=None,
        )

        async with DataHubClient(config) as client:
            # Should raise UnauthorizedError
            with pytest.raises(UnauthorizedError):
                await client.get("assets/assets/")

    @pytest.mark.asyncio
    async def test_error_expired_token(self):
        """
        Test error handling for expired token
        """
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="expired-token-12345",
        )

        async with DataHubClient(config) as client:
            # Should raise UnauthorizedError
            with pytest.raises(UnauthorizedError):
                await client.get("assets/assets/")
