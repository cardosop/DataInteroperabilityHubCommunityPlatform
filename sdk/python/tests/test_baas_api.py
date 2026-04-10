from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Unit tests for BaaS API.

Tests validation, error handling, and method signatures without making real API calls.
"""
import os
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datahub_interoperability import DataHubClient, DataHubClientConfig, BaaSAPI
from datahub_interoperability.errors import (
    BaaSValidationError,
    BaaSError,
    NotFoundError,
    ForbiddenError,
    ValidationError,
)


@pytest.fixture
def client():
    """Create a test client"""
    config = DataHubClientConfig(
        base_url=os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1"),
        api_token="test-token",
    )
    return DataHubClient(config)


@pytest.fixture
def baas_api(client):
    """Create a BaaSAPI instance"""
    return BaaSAPI(client)


class TestBaaSAPIInitialization:
    """Test BaaSAPI initialization"""

    def test_init(self, client):
        """Test BaaSAPI initialization"""
        baas_api = BaaSAPI(client)
        assert baas_api.client == client


class TestBaaSAPIValidation:
    """Test validation methods"""

    def test_validate_api_key_id_valid(self, baas_api):
        """Test validating a valid API key ID"""
        valid_id = str(uuid.uuid4())
        # Should not raise
        baas_api._validate_api_key_id(valid_id)

    def test_validate_api_key_id_empty(self, baas_api):
        """Test validating an empty API key ID"""
        with pytest.raises(BaaSValidationError) as exc_info:
            baas_api._validate_api_key_id("")
        assert "required" in exc_info.value.message.lower()

    def test_validate_api_key_id_none(self, baas_api):
        """Test validating None API key ID"""
        with pytest.raises(BaaSValidationError) as exc_info:
            baas_api._validate_api_key_id(None)
        assert "required" in exc_info.value.message.lower()

    def test_validate_api_key_id_invalid_format(self, baas_api):
        """Test validating an invalid API key ID format"""
        with pytest.raises(BaaSValidationError) as exc_info:
            baas_api._validate_api_key_id("not-a-uuid")
        assert "uuid" in exc_info.value.message.lower()

    def test_validate_date_format_valid(self, baas_api):
        """Test validating a valid ISO date"""
        # Should not raise
        baas_api._validate_date_format("2024-01-01T00:00:00Z")
        baas_api._validate_date_format("2024-01-01T00:00:00+00:00")

    def test_validate_date_format_invalid(self, baas_api):
        """Test validating an invalid date format"""
        with pytest.raises(BaaSValidationError) as exc_info:
            baas_api._validate_date_format("2024-01-01")
        assert "iso format" in exc_info.value.message.lower()

    def test_validate_tier_valid(self, baas_api):
        """Test validating valid tiers"""
        # Should not raise
        baas_api._validate_tier("FREE")
        baas_api._validate_tier("PRO")
        baas_api._validate_tier("ENTERPRISE")

    def test_validate_tier_invalid(self, baas_api):
        """Test validating an invalid tier"""
        with pytest.raises(BaaSValidationError) as exc_info:
            baas_api._validate_tier("INVALID")
        assert "tier" in exc_info.value.message.lower()


class TestBaaSAPICreateAPIKey:
    """Test create_api_key method"""

    @pytest.mark.asyncio
    async def test_create_api_key_success(self, baas_api):
        """Test successful API key creation"""
        mock_response = {
            "id": str(uuid.uuid4()),
            "name": "Test Key",
            "api_key": "test-api-key-value",
            "tier": "FREE",
            "created_at": "2024-01-01T00:00:00Z",
        }
        baas_api.client.post = AsyncMock(return_value=mock_response)

        result = await baas_api.create_api_key("Test Key", "FREE")

        assert result == mock_response
        baas_api.client.post.assert_called_once()
        call_args = baas_api.client.post.call_args
        assert call_args[0][0] == "baas/api-keys/"
        assert call_args[1]["data"]["name"] == "Test Key"
        assert call_args[1]["data"]["tier"] == "FREE"

    @pytest.mark.asyncio
    async def test_create_api_key_with_expires_at(self, baas_api):
        """Test API key creation with expiration"""
        mock_response = {
            "id": str(uuid.uuid4()),
            "name": "Test Key",
            "api_key": "test-api-key-value",
            "tier": "FREE",
            "expires_at": "2025-01-01T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
        }
        baas_api.client.post = AsyncMock(return_value=mock_response)

        result = await baas_api.create_api_key(
            "Test Key", "FREE", expires_at="2025-01-01T00:00:00Z"
        )

        assert result == mock_response
        call_args = baas_api.client.post.call_args
        assert call_args[1]["data"]["expires_at"] == "2025-01-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_create_api_key_empty_name(self, baas_api):
        """Test API key creation with empty name"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.create_api_key("", "FREE")
        assert "name" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_create_api_key_invalid_tier(self, baas_api):
        """Test API key creation with invalid tier"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.create_api_key("Test Key", "INVALID")
        assert "tier" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_create_api_key_invalid_date(self, baas_api):
        """Test API key creation with invalid expiration date"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.create_api_key("Test Key", "FREE", expires_at="invalid-date")
        assert "iso format" in exc_info.value.message.lower()


class TestBaaSAPIListAPIKeys:
    """Test list_api_keys method"""

    @pytest.mark.asyncio
    async def test_list_api_keys_success(self, baas_api):
        """Test successful API key listing"""
        mock_response = [
            {"id": str(uuid.uuid4()), "name": "Key 1", "tier": "FREE"},
            {"id": str(uuid.uuid4()), "name": "Key 2", "tier": "PRO"},
        ]
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.list_api_keys()

        assert result == mock_response
        baas_api.client.get.assert_called_once_with("baas/api-keys/", params={})

    @pytest.mark.asyncio
    async def test_list_api_keys_with_filters(self, baas_api):
        """Test API key listing with filters"""
        mock_response = [{"id": str(uuid.uuid4()), "name": "Key 1", "tier": "FREE"}]
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.list_api_keys(tier="FREE", limit=10, offset=0)

        assert result == mock_response
        call_args = baas_api.client.get.call_args
        assert call_args[1]["params"]["tier"] == "FREE"
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_api_keys_paginated(self, baas_api):
        """Test API key listing with paginated response"""
        mock_response = {"results": [{"id": str(uuid.uuid4()), "name": "Key 1"}]}
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.list_api_keys()

        assert result == mock_response["results"]

    @pytest.mark.asyncio
    async def test_list_api_keys_invalid_limit(self, baas_api):
        """Test API key listing with invalid limit"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.list_api_keys(limit=-1)
        assert "limit" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_list_api_keys_invalid_offset(self, baas_api):
        """Test API key listing with invalid offset"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.list_api_keys(offset=-1)
        assert "offset" in exc_info.value.message.lower()


class TestBaaSAPIGetAPIKey:
    """Test get_api_key method"""

    @pytest.mark.asyncio
    async def test_get_api_key_success(self, baas_api):
        """Test successful API key retrieval"""
        api_key_id = str(uuid.uuid4())
        mock_response = {
            "id": api_key_id,
            "name": "Test Key",
            "tier": "FREE",
        }
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_api_key(api_key_id)

        assert result == mock_response
        baas_api.client.get.assert_called_once_with(f"baas/api-keys/{api_key_id}/")

    @pytest.mark.asyncio
    async def test_get_api_key_invalid_id(self, baas_api):
        """Test API key retrieval with invalid ID"""
        with pytest.raises(BaaSValidationError):
            await baas_api.get_api_key("not-a-uuid")

    @pytest.mark.asyncio
    async def test_get_api_key_not_found(self, baas_api):
        """Test API key retrieval when not found"""
        api_key_id = str(uuid.uuid4())
        baas_api.client.get = AsyncMock(side_effect=NotFoundError("API key not found"))

        with pytest.raises(NotFoundError):
            await baas_api.get_api_key(api_key_id)


class TestBaaSAPIUpdateAPIKey:
    """Test update_api_key method"""

    @pytest.mark.asyncio
    async def test_update_api_key_success(self, baas_api):
        """Test successful API key update"""
        api_key_id = str(uuid.uuid4())
        mock_response = {
            "id": api_key_id,
            "name": "Updated Key",
            "tier": "FREE",
        }
        baas_api.client.patch = AsyncMock(return_value=mock_response)

        result = await baas_api.update_api_key(api_key_id, name="Updated Key")

        assert result == mock_response
        call_args = baas_api.client.patch.call_args
        assert call_args[0][0] == f"baas/api-keys/{api_key_id}/"
        assert call_args[1]["data"]["name"] == "Updated Key"

    @pytest.mark.asyncio
    async def test_update_api_key_no_fields(self, baas_api):
        """Test API key update with no fields"""
        api_key_id = str(uuid.uuid4())
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.update_api_key(api_key_id)
        assert "at least one field" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_update_api_key_invalid_id(self, baas_api):
        """Test API key update with invalid ID"""
        with pytest.raises(BaaSValidationError):
            await baas_api.update_api_key("not-a-uuid", name="New Name")


class TestBaaSAPIRevokeAPIKey:
    """Test revoke_api_key method"""

    @pytest.mark.asyncio
    async def test_revoke_api_key_success(self, baas_api):
        """Test successful API key revocation"""
        api_key_id = str(uuid.uuid4())
        baas_api.client.delete = AsyncMock(return_value=None)

        await baas_api.revoke_api_key(api_key_id)

        baas_api.client.delete.assert_called_once_with(f"baas/api-keys/{api_key_id}/")

    @pytest.mark.asyncio
    async def test_revoke_api_key_invalid_id(self, baas_api):
        """Test API key revocation with invalid ID"""
        with pytest.raises(BaaSValidationError):
            await baas_api.revoke_api_key("not-a-uuid")


class TestBaaSAPIGetUsageStats:
    """Test get_usage_stats method"""

    @pytest.mark.asyncio
    async def test_get_usage_stats_success(self, baas_api):
        """Test successful usage stats retrieval"""
        mock_response = {
            "total_requests": 1000,
            "success_count": 950,
            "error_count": 50,
            "success_rate": 95.0,
            "avg_response_time_ms": 120.5,
        }
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_usage_stats()

        assert result == mock_response
        baas_api.client.get.assert_called_once_with("baas/usage/stats/", params={})

    @pytest.mark.asyncio
    async def test_get_usage_stats_with_filters(self, baas_api):
        """Test usage stats with filters"""
        api_key_id = str(uuid.uuid4())
        mock_response = {"total_requests": 100}
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_usage_stats(
            api_key_id=api_key_id,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
        )

        assert result == mock_response
        call_args = baas_api.client.get.call_args
        assert call_args[1]["params"]["api_key_id"] == api_key_id

    @pytest.mark.asyncio
    async def test_get_usage_stats_invalid_date(self, baas_api):
        """Test usage stats with invalid date"""
        with pytest.raises(BaaSValidationError):
            await baas_api.get_usage_stats(start_date="invalid-date")


class TestBaaSAPIGetUsageByEndpoint:
    """Test get_usage_by_endpoint method"""

    @pytest.mark.asyncio
    async def test_get_usage_by_endpoint_success(self, baas_api):
        """Test successful usage by endpoint retrieval"""
        mock_response = [
            {
                "endpoint": "/api/v1/test",
                "method": "GET",
                "total_requests": 100,
                "success_count": 95,
                "error_count": 5,
            }
        ]
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_usage_by_endpoint()

        assert result == mock_response
        baas_api.client.get.assert_called_once_with("baas/usage/by-endpoint/", params={})

    @pytest.mark.asyncio
    async def test_get_usage_by_endpoint_paginated(self, baas_api):
        """Test usage by endpoint with paginated response"""
        mock_response = {
            "results": [{"endpoint": "/api/v1/test", "method": "GET", "total_requests": 100}]
        }
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_usage_by_endpoint()

        assert result == mock_response["results"]


class TestBaaSAPIGetUsageByTenant:
    """Test get_usage_by_tenant method"""

    @pytest.mark.asyncio
    async def test_get_usage_by_tenant_success(self, baas_api):
        """Test successful usage by tenant retrieval"""
        mock_response = [
            {
                "tenant_id": str(uuid.uuid4()),
                "tenant_name": "Test Tenant",
                "total_requests": 1000,
            }
        ]
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_usage_by_tenant()

        assert result == mock_response
        baas_api.client.get.assert_called_once_with("baas/usage/by-tenant/", params={})

    @pytest.mark.asyncio
    async def test_get_usage_by_tenant_forbidden(self, baas_api):
        """Test usage by tenant when not admin"""
        baas_api.client.get = AsyncMock(side_effect=ForbiddenError("Admin only"))

        with pytest.raises(ForbiddenError):
            await baas_api.get_usage_by_tenant()


class TestBaaSAPICheckQuota:
    """Test check_quota method"""

    @pytest.mark.asyncio
    async def test_check_quota_success(self, baas_api):
        """Test successful quota check"""
        api_key_id = str(uuid.uuid4())
        mock_response = {
            "api_key_id": api_key_id,
            "tier": "FREE",
            "rate_limit_per_hour": 1000,
            "current_usage_hour": 100,
            "remaining_hour": 900,
        }
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.check_quota(api_key_id)

        assert result == mock_response
        baas_api.client.get.assert_called_once_with(f"baas/api-keys/{api_key_id}/quota/")

    @pytest.mark.asyncio
    async def test_check_quota_invalid_id(self, baas_api):
        """Test quota check with invalid ID"""
        with pytest.raises(BaaSValidationError):
            await baas_api.check_quota("not-a-uuid")


class TestBaaSAPIDeveloperPortal:
    """Test developer portal methods"""

    @pytest.mark.asyncio
    async def test_get_api_docs_success(self, baas_api):
        """Test successful API docs retrieval"""
        mock_response = {"title": "API Documentation", "version": "1.0.0"}
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_api_docs()

        assert isinstance(result, str)
        baas_api.client.get.assert_called_once_with("baas/docs/")

    @pytest.mark.asyncio
    async def test_get_api_docs_json_format(self, baas_api):
        """Test API docs in JSON format"""
        mock_response = {"title": "API Documentation"}
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_api_docs(format="json")

        assert isinstance(result, str)
        assert "title" in result

    @pytest.mark.asyncio
    async def test_get_api_docs_invalid_format(self, baas_api):
        """Test API docs with invalid format"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.get_api_docs(format="invalid")
        assert "format" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_get_openapi_schema_success(self, baas_api):
        """Test successful OpenAPI schema retrieval"""
        mock_response = {"openapi": "3.0.0", "info": {"title": "API"}}
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_openapi_schema()

        assert isinstance(result, dict)
        assert result == mock_response
        baas_api.client.get.assert_called_once_with("baas/docs/openapi.json/")

    @pytest.mark.asyncio
    async def test_get_openapi_schema_invalid_format(self, baas_api):
        """Test OpenAPI schema with invalid format"""
        with pytest.raises(BaaSValidationError) as exc_info:
            await baas_api.get_openapi_schema(format="invalid")
        assert "format" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_get_sdk_download_links_success(self, baas_api):
        """Test successful SDK download links retrieval"""
        mock_response = {
            "python": {"download_url": "https://example.com/python-sdk"},
            "javascript": {"download_url": "https://example.com/js-sdk"},
        }
        baas_api.client.get = AsyncMock(return_value=mock_response)

        result = await baas_api.get_sdk_download_links()

        assert isinstance(result, dict)
        baas_api.client.get.assert_called_once_with("baas/docs/sdks/")
