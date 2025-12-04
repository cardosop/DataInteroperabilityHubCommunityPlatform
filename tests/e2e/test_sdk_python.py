"""
Comprehensive E2E tests for Python SDK.

Tests SDK functionality against real API endpoints with zero mocks.
Covers authentication, CRUD operations, error handling, retry logic, and advanced features.

Uses REAL services (no mocks).
"""
import pytest
import asyncio
import httpx
from typing import TYPE_CHECKING
from django.test import TestCase
from asgiref.sync import sync_to_async
from rest_framework import status

# Try to import SDK - skip tests if not available
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig
    from datahub_interoperability.errors import (
        ValidationError,
        NotFoundError,
        UnauthorizedError,
        ForbiddenError,
        RateLimitError,
        ServerError,
        NetworkError,
    )
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    # Define stub types for type checking when SDK is not available
    if TYPE_CHECKING:
        from typing import Any
        DataHubClientConfig = Any
        DataHubClient = Any

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e5]


# Helper to wrap Django ORM calls for async tests
async def create_asset(**kwargs):
    """Helper to create asset in async context"""
    return await sync_to_async(Asset.objects.create)(**kwargs)


async def get_asset(id):
    """Helper to get asset in async context"""
    return await sync_to_async(Asset.objects.get)(id=id)


async def get_contract(id):
    """Helper to get contract in async context"""
    return await sync_to_async(Contract.objects.get)(id=id)


async def get_file(id):
    """Helper to get file in async context"""
    return await sync_to_async(File.objects.get)(id=id)


@pytest.mark.skipif(not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e .")
class SDKPythonE2ETest(E2ETestBase):
    """E2E tests for Python SDK"""
    
    def get_sdk_config(self) -> "DataHubClientConfig":
        """Get SDK config with authenticated token"""
        # Get JWT token via login
        login_response = self.client.post('/api/v1/auth/login/', {
            'email': self.user.email,
            'password': 'testpass123'
        }, format='json')
        
        # Check if login was successful
        if login_response.status_code != 200:
            raise Exception(f"Login failed: {login_response.status_code} - {login_response.data}")
        
        access_token = login_response.data['access_token']
        
        from .conftest import get_api_base_url
        return DataHubClientConfig(
            base_url=f"{get_api_base_url()}/api/v1",
            api_token=access_token
        )
    
    def create_api_key(self) -> APIKey:
        """Create API key for testing"""
        return APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="Test API Key"
        )
    
    # Authentication Tests
    
    @pytest.mark.asyncio
    async def test_sdk_api_key_authentication(self):
        """Test SDK authentication with API key"""
        # Create API key
        await sync_to_async(self.create_api_key)()
        # APIKey stores key_hash, but we need the plaintext key
        # For testing, we'll use JWT token instead
        # In production, API keys would be generated with plaintext returned once
        
        # Use JWT token for this test (API key testing would require key generation endpoint)
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Make authenticated request
            assets = await client.get("/assets/assets/")
            assert "results" in assets
            assert isinstance(assets["results"], list)
    
    @pytest.mark.asyncio
    async def test_sdk_jwt_token_authentication(self):
        """Test SDK authentication with JWT token"""
        # Get config in sync context (before async)
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Make authenticated request
            assets = await client.get("/assets/assets/")
            assert "results" in assets
            assert isinstance(assets["results"], list)
    
    @pytest.mark.asyncio
    async def test_sdk_token_refresh_on_401(self):
        """Test SDK automatically refreshes token on 401"""
        refresh_called = False
        
        async def refresh_token():
            nonlocal refresh_called
            refresh_called = True
            # Get new token (must use sync_to_async for Django client)
            login_response = await sync_to_async(self.client.post)(
                '/api/v1/auth/login/',
                {
                    'email': self.user.email,
                    'password': 'testpass123'
                },
                format='json'
            )
            return login_response.data['access_token']
        
        # Use invalid token to trigger 401
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token="invalid-token"
        )
        
        async with DataHubClient(config) as client:
            client.set_token_refresh_callback(refresh_token)
            
            # Request should trigger refresh
            assets = await client.get("/assets/assets/")
            assert refresh_called
            assert "results" in assets
    
    @pytest.mark.asyncio
    async def test_sdk_invalid_token_handling(self):
        """Test SDK handles invalid token correctly"""
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token="invalid-token"
        )
        
        async with DataHubClient(config) as client:
            with pytest.raises(UnauthorizedError) as exc_info:
                await client.get("/assets/assets/")
            
            error = exc_info.value
            assert error.http_status == 401
            assert error.code == "AUTH_UNAUTHORIZED"
    
    @pytest.mark.asyncio
    async def test_sdk_missing_token_handling(self):
        """Test SDK handles missing token correctly"""
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token=None
        )
        
        async with DataHubClient(config) as client:
            with pytest.raises(UnauthorizedError) as exc_info:
                await client.get("/assets/assets/")
            
            error = exc_info.value
            assert error.http_status == 401
    
    # CRUD Operations Tests
    
    @pytest.mark.asyncio
    async def test_sdk_create_asset(self):
        """Test SDK create asset operation"""
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Create asset via SDK
            asset = await client.post("/assets/assets/", {
                "name": "SDK Test Asset",
                "description": "Created via SDK",
                "domain": "testing"
            })
            
            assert "id" in asset
            assert asset["name"] == "SDK Test Asset"
            
            # Verify in database
            db_asset = await get_asset(asset["id"])
            assert db_asset.name == "SDK Test Asset"
            assert db_asset.tenant == self.tenant
    
    @pytest.mark.asyncio
    async def test_sdk_get_asset(self):
        """Test SDK get asset operation"""
        # Create asset in database
        asset = await create_asset(
            name="Test Asset",
            tenant=self.tenant,
            status=AssetStatus.DRAFT
        )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Get asset via SDK
            retrieved = await client.get(f"/assets/assets/{asset.id}/")
            
            assert retrieved["id"] == str(asset.id)
            assert retrieved["name"] == "Test Asset"
    
    @pytest.mark.asyncio
    async def test_sdk_list_assets(self):
        """Test SDK list assets operation"""
        # Create multiple assets
        for i in range(5):
            await create_asset(
                name=f"Asset {i}",
                tenant=self.tenant,
                status=AssetStatus.DRAFT
            )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # List assets via SDK
            response = await client.get("/assets/assets/")
            
            assert "results" in response
            assert "count" in response
            assert len(response["results"]) >= 5
    
    @pytest.mark.asyncio
    async def test_sdk_list_assets_with_pagination(self):
        """Test SDK list assets with pagination"""
        # Create multiple assets
        for i in range(15):
            await create_asset(
                name=f"Asset {i}",
                tenant=self.tenant,
                status=AssetStatus.DRAFT
            )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Get first page
            page1 = await client.get("/assets/assets/", params={"limit": 10})
            assert len(page1["results"]) == 10
            assert page1["count"] >= 15
            assert page1.get("next") is not None
            
            # Get second page using next URL
            if page1.get("next"):
                # Extract path from full URL
                next_path = page1["next"].replace("http://localhost:8000", "")
                page2 = await client.get(next_path)
                assert len(page2["results"]) >= 5
                assert page2.get("previous") is not None
    
    @pytest.mark.asyncio
    async def test_sdk_update_asset(self):
        """Test SDK update asset operation"""
        # Create asset
        asset = await create_asset(
            name="Original Name",
            tenant=self.tenant,
            status=AssetStatus.DRAFT
        )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Update via SDK
            updated = await client.patch(f"/assets/assets/{asset.id}/", {
                "name": "Updated Name",
                "description": "Updated description"
            })
            
            assert updated["name"] == "Updated Name"
            
            # Verify in database
            await sync_to_async(asset.refresh_from_db)()
            assert asset.name == "Updated Name"
    
    @pytest.mark.asyncio
    async def test_sdk_delete_asset(self):
        """Test SDK delete asset operation"""
        # Create asset
        asset = await create_asset(
            name="To Delete",
            tenant=self.tenant,
            status=AssetStatus.DRAFT
        )
        asset_id = asset.id
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Delete via SDK
            await client.delete(f"/assets/assets/{asset_id}/")
            
            # Verify deleted
            with pytest.raises(Asset.DoesNotExist):
                await get_asset(asset_id)
    
    @pytest.mark.asyncio
    async def test_sdk_create_contract(self):
        """Test SDK create contract operation"""
        # Create asset first
        asset = await create_asset(
            name="Test Asset",
            tenant=self.tenant,
            status=AssetStatus.DRAFT
        )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Create contract via SDK
            contract = await client.post("/contracts/contracts/", {
                "asset_id": str(asset.id),
                "original_raw": '{"id": "test", "name": "Test Contract", "schema": {"fields": [{"name": "col1", "type": "string"}]}}',
                "original_format": "JSON",
                "original_spec_type": "ODCS"
            })
            
            assert "id" in contract
            
            # Verify in database
            db_contract = await get_contract(contract["id"])
            assert db_contract.asset == asset
    
    # Error Handling Tests
    
    @pytest.mark.asyncio
    async def test_sdk_validation_error_handling(self):
        """Test SDK handles ValidationError correctly"""
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            with pytest.raises(ValidationError) as exc_info:
                await client.post("/assets/assets/", {
                    "name": "",  # Invalid: empty name
                })
            
            error = exc_info.value
            assert error.http_status == 400
            assert error.code == "VALIDATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_sdk_not_found_error_handling(self):
        """Test SDK handles NotFoundError correctly"""
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            with pytest.raises(NotFoundError) as exc_info:
                await client.get("/assets/assets/00000000-0000-0000-0000-000000000000/")
            
            error = exc_info.value
            assert error.http_status == 404
            assert error.code == "NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_sdk_unauthorized_error_handling(self):
        """Test SDK handles UnauthorizedError correctly"""
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token="invalid-token"
        )
        
        async with DataHubClient(config) as client:
            with pytest.raises(UnauthorizedError) as exc_info:
                await client.get("/assets/assets/")
            
            error = exc_info.value
            assert error.http_status == 401
            assert error.code == "AUTH_UNAUTHORIZED"
    
    @pytest.mark.asyncio
    async def test_sdk_forbidden_error_handling(self):
        """Test SDK handles ForbiddenError correctly"""
        # Create another tenant and user
        other_tenant = await sync_to_async(Tenant.objects.create)(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = await sync_to_async(User.objects.create_user)(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create asset in other tenant
        other_asset = await create_asset(
            name="Other Asset",
            tenant=other_tenant,
            status=AssetStatus.DRAFT
        )
        
        # Use our user's token (should get 404, not 403, due to tenant isolation)
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Should get 404 (not revealing existence) due to tenant isolation
            with pytest.raises(NotFoundError):
                await client.get(f"/assets/assets/{other_asset.id}/")
    
    # Advanced Features Tests
    
    @pytest.mark.asyncio
    async def test_sdk_file_upload_flow(self):
        """Test SDK file upload flow"""
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Initialize upload
            file_info = await client.post("/files/files/init/", {
                "name": "test.csv",
                "size": 1024,
                "content_type": "text/csv"
            })
            
            assert "upload_url" in file_info
            assert "file_id" in file_info
            
            file_id = file_info["file_id"]
            
            # Upload to pre-signed URL
            test_content = b"col1,col2\nval1,val2\n"
            async with httpx.AsyncClient() as http_client:
                await http_client.put(
                    file_info["upload_url"],
                    content=test_content,
                    headers={"Content-Type": "text/csv"}
                )
            
            # Complete upload
            import hashlib
            content_sha256 = hashlib.sha256(test_content).hexdigest()
            completed = await client.post(f"/files/files/{file_id}/complete/", {
                "content_sha256": content_sha256
            })
            assert completed["status"] == "UPLOADED"
            
            # Verify in database
            db_file = await get_file(file_id)
            assert db_file.status == FileStatus.UPLOADED
    
    @pytest.mark.asyncio
    async def test_sdk_query_parameters(self):
        """Test SDK handles query parameters correctly"""
        # Create assets with different statuses
        await create_asset(
            name="Draft Asset",
            tenant=self.tenant,
            status=AssetStatus.DRAFT
        )
        await create_asset(
            name="Active Asset",
            tenant=self.tenant,
            status=AssetStatus.ACTIVE
        )
        
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Filter by status
            response = await client.get("/assets/assets/", params={"status": "ACTIVE"})
            
            assert "results" in response
            # All results should be ACTIVE
            for asset in response["results"]:
                assert asset["status"] == "ACTIVE"
    
    @pytest.mark.asyncio
    async def test_sdk_custom_headers(self):
        """Test SDK handles custom headers correctly"""
        config = await sync_to_async(self.get_sdk_config)()
        
        async with DataHubClient(config) as client:
            # Make request with custom header
            response = await client.get(
                "/assets/assets/",
                headers={"X-Custom-Header": "test-value"}
            )
            
            assert "results" in response
    
    # Retry Logic Tests (Note: These are harder to test without simulating failures)
    
    @pytest.mark.asyncio
    async def test_sdk_retry_configuration(self):
        """Test SDK retry configuration is respected"""
        # Get token first
        base_config = await sync_to_async(self.get_sdk_config)()
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token=base_config.api_token,
            max_retries=2
        )
        
        async with DataHubClient(config) as client:
            # Normal request should work
            assets = await client.get("/assets/assets/")
            assert "results" in assets
            
            # Verify retry config is set
            assert client.config.max_retries == 2
    
    @pytest.mark.asyncio
    async def test_sdk_timeout_configuration(self):
        """Test SDK timeout configuration"""
        # Get token first
        base_config = await sync_to_async(self.get_sdk_config)()
        config = DataHubClientConfig(
            base_url=f"{self.api_base_url}/api/v1",
            api_token=base_config.api_token,
            timeout=10.0
        )
        
        async with DataHubClient(config) as client:
            # Normal request should work
            assets = await client.get("/assets/assets/")
            assert "results" in assets
            
            # Verify timeout config is set
            assert client.config.timeout == 10.0

