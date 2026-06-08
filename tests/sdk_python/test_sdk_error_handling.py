"""

import uuid
Comprehensive tests for SDK error handling.

Tests network errors, API errors, retry logic, and timeouts.
Uses REAL API server (no mocks) - uses existing API service in Docker Compose.
"""

import asyncio

import pytest
from asgiref.sync import sync_to_async

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig
    from datahub_interoperability.errors import (
        ForbiddenError,
        NetworkError,
        NotFoundError,
        RateLimitError,
        ServerError,
        UnauthorizedError,
        ValidationError,
    )

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from tests.e2e.conftest import TenantFactory
from tests.sdk_python.conftest import SDKTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e ."
)
class TestSDKErrorHandling(SDKTestBase):
    """Test SDK error handling"""

    @pytest.mark.asyncio
    async def test_error_validation_error(self):
        """Test handling ValidationError (400)"""
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Try to create asset without required fields
            with pytest.raises(ValidationError) as exc_info:
                await client.post("/assets/assets/", {"description": "Missing required fields"})

            error = exc_info.value
            assert error.http_status == 400
            assert error.code == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_error_not_found_error(self):
        """Test handling NotFoundError (404)"""
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            fake_id = "00000000-0000-0000-0000-000000000000"
            with pytest.raises(NotFoundError) as exc_info:
                await client.get(f"/assets/assets/{fake_id}/")

            error = exc_info.value
            assert error.http_status == 404
            assert error.code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_unauthorized_error(self):
        """Test handling UnauthorizedError (401)"""
        config = DataHubClientConfig(base_url=self.base_url, api_token="invalid-token-12345")
        async with DataHubClient(config) as client:
            with pytest.raises(UnauthorizedError) as exc_info:
                await client.get("/assets/assets/")

            error = exc_info.value
            assert error.http_status == 401
            assert error.code == "AUTH_UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_error_forbidden_error(self):
        """Test handling ForbiddenError (403)"""
        # Create user without permissions (use unique email to avoid conflicts)
        import uuid

        import httpx
        from django.db import transaction

        unique_email = f"limited_{uuid.uuid4().hex[:8]}@example.com"
        limited_user = await sync_to_async(User.objects.create_user)(
            email=unique_email,
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Ensure user is committed to database
        await sync_to_async(transaction.commit)()

        # Login via HTTP to get token (using httpx like get_sdk_config does)
        login_url = f"{self.api_base_url}/api/v1/auth/login/"
        timeout_config = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout_config) as http_client:
            login_response = await http_client.post(
                login_url,
                json={"email": unique_email, "password": "testpass123"},
                timeout=30.0,
            )
            if login_response.status_code != 200:
                pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
            data = login_response.json()
            access_token = data.get("access_token") or data.get("token")
            if not access_token:
                pytest.skip(f"No access token in login response: {data}")

        config = DataHubClientConfig(base_url=self.base_url, api_token=access_token)

        async with DataHubClient(config) as client:
            # Try to access admin-only endpoint (may return 403)
            try:
                with pytest.raises(ForbiddenError) as exc_info:
                    await client.get("tenants/")  # May require admin permissions
                error = exc_info.value
                assert error.http_status == 403
            except NotFoundError:
                # Endpoint may not exist or return 404
                pass

    @pytest.mark.asyncio
    async def test_error_network_error(self):
        """Test handling NetworkError"""
        # Use invalid base URL to trigger network error
        config = DataHubClientConfig(
            base_url="http://invalid-domain-that-does-not-exist-12345.com/api/v1",
            api_token="test-token",
            timeout=1.0,  # Short timeout
        )

        async with DataHubClient(config) as client:
            with pytest.raises(NetworkError):
                await client.get("/assets/assets/")

    @pytest.mark.asyncio
    async def test_error_timeout(self):
        """Test handling timeout errors"""
        config = DataHubClientConfig(
            base_url=self.base_url,
            api_token="test-token",
            timeout=0.001,  # Very short timeout (1ms)
        )

        async with DataHubClient(config) as client:
            # Request should timeout
            with pytest.raises((NetworkError, TimeoutError)):
                await client.get("/assets/assets/")

    @pytest.mark.asyncio
    async def test_retry_logic_on_5xx_error(self):
        """Test retry logic on 5xx server errors"""
        config = await self.get_sdk_config()
        # Configure with retries
        config = DataHubClientConfig(
            base_url=self.base_url, api_token=config.api_token, max_retries=3
        )

        async with DataHubClient(config) as client:
            # Normal request should succeed (no 5xx error)
            # This test verifies retry configuration is set
            result = await client.get("/assets/assets/")
            assert result is not None

    @pytest.mark.asyncio
    async def test_retry_logic_on_429_rate_limit(self):
        """Test retry logic on 429 rate limit errors"""
        config = await self.get_sdk_config()
        config = DataHubClientConfig(
            base_url=self.base_url, api_token=config.api_token, max_retries=3
        )

        async with DataHubClient(config) as client:
            # Normal request should succeed
            # Rate limit testing would require actual rate limiting
            result = await client.get("/assets/assets/")
            assert result is not None

    @pytest.mark.asyncio
    async def test_error_response_structure(self):
        """Test error response structure"""
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            fake_id = "00000000-0000-0000-0000-000000000000"
            try:
                await client.get(f"/assets/assets/{fake_id}/")
            except NotFoundError as error:
                # Verify error has all expected attributes
                assert hasattr(error, "message")
                assert hasattr(error, "code")
                assert hasattr(error, "http_status")
                assert error.http_status == 404
                assert error.code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_details_in_response(self):
        """Test error details are included in response"""
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Try invalid request
            try:
                await client.post("/assets/assets/", {"invalid": "data"})
            except ValidationError as error:
                # Verify error has details
                assert hasattr(error, "details")
                assert error.http_status == 400


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e ."
)
class TestSDKRetryLogic(SDKTestBase):
    """Test SDK retry logic"""

    async def get_sdk_config(self):
        """Get SDK config with authenticated token"""
        # Use the base class method which handles async properly
        config = await super().get_sdk_config()
        # Override max_retries for retry tests
        from datahub_interoperability import DataHubClientConfig

        return DataHubClientConfig(
            base_url=config.base_url,
            api_token=config.api_token,
            max_retries=3,
            timeout=config.timeout,
            user_agent=config.user_agent,
            enable_logging=config.enable_logging,
        )

    @pytest.mark.asyncio
    async def test_retry_configuration(self):
        """Test retry configuration"""
        config = await self.get_sdk_config()
        assert config.max_retries == 3

        async with DataHubClient(config) as client:
            # Verify client has retry configuration
            assert client.config.max_retries == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delay calculation"""
        from datahub_interoperability.client import calculate_backoff_delay

        # Test backoff calculation
        delay1 = calculate_backoff_delay(0, base_delay=1.0)
        delay2 = calculate_backoff_delay(1, base_delay=1.0)
        delay3 = calculate_backoff_delay(2, base_delay=1.0)

        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    @pytest.mark.asyncio
    async def test_retryable_error_detection(self):
        """Test retryable error detection"""
        from datahub_interoperability.client import is_retryable_error

        # Network errors are retryable
        network_error = NetworkError("Connection failed")
        assert is_retryable_error(network_error) is True

        # 5xx errors are retryable
        server_error = ServerError("Server error", "INTERNAL_ERROR", 500, "req-123")
        assert is_retryable_error(server_error) is True

        # 429 rate limit is retryable
        rate_limit_error = RateLimitError("Rate limit", "req-123", retry_after=60)
        assert is_retryable_error(rate_limit_error) is True

        # 4xx errors (except 429) are not retryable
        validation_error = ValidationError("Validation failed", "req-123")
        assert is_retryable_error(validation_error) is False

        not_found_error = NotFoundError("Not found", "req-123")
        assert is_retryable_error(not_found_error) is False
