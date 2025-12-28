"""
Tests for Mesh Domain Management API methods.

Tests domain CRUD operations with comprehensive error handling.
"""
import os
import pytest
import uuid
import subprocess
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from datahub_interoperability import DataHubClient, DataHubClientConfig, MeshAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
)


def setup_authentication_for_sdk_tests(api_base_url: str) -> Optional[str]:
    """
    Set up authentication for SDK tests.

    Tries multiple methods:
    1. Use TEST_API_KEY environment variable if available
    2. Use DATAHUB_API_KEY environment variable
    3. Try to create API key via Django shell (if Docker Compose is available)
    4. Return None if no key available

    Args:
        api_base_url: API base URL

    Returns:
        API key string or None
    """
    # Method 1: Use environment variables
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        return api_key

    # Method 2: Try to create API key via Django shell in Docker Compose
    try:
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey
import os

tenant, _ = Tenant.objects.get_or_create(
    slug='mesh-domains-sdk-test-tenant',
    defaults={'name': 'Mesh Domains SDK Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

user, _ = User.objects.get_or_create(
    email='mesh-domains-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign TENANT_ADMIN role to user
UserRole.objects.get_or_create(user=user, role=admin_role)

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='mesh-domains-sdk-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-domains-sdk-test-key',
    key_hash=api_key_hash,
    scopes=['mesh:write', 'mesh:read']
)
print(api_key_value)
"""
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            # Look for line starting with API key (long alphanumeric string)
            for line in reversed(output_lines):
                line = line.strip()
                # API keys are typically long strings (40+ characters)
                if line and len(line) > 40:
                    # Additional validation: check if it looks like an API key
                    cleaned = line.replace('-', '').replace('_', '')
                    if cleaned.isalnum() and ' ' not in line:
                        return line
    except Exception:
        pass

    return None


def check_api_available(api_base_url: str) -> bool:
    """Check if API service is available"""
    try:
        import requests
        response = requests.get(f"{api_base_url}/", timeout=2)
        return response.status_code < 600  # Any HTTP response means API is up
    except Exception:
        return False


@pytest.fixture
def config():
    """Test configuration for unit tests"""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        timeout=30.0,
        max_retries=3,
        user_agent="DataHub-SDK-Test",
        enable_logging=False,
    )


@pytest.fixture
def client(config):
    """Test client for unit tests"""
    return DataHubClient(config)


@pytest.fixture
def mesh_api(client):
    """Test Mesh API instance for unit tests"""
    return MeshAPI(client)


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')

    # Check if API is available
    if not check_api_available(api_base_url):
        pytest.skip("API service is not available. Ensure Docker Compose services are running.")

    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable, "
            "or ensure Docker Compose api-service is accessible."
        )

    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
        user_agent="DataHub-SDK-Test",
        enable_logging=False,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration"""
    async with DataHubClient(real_api_config) as client:
        yield client


# Unit Tests - Method Structure and Parameters

@pytest.mark.asyncio
async def test_create_domain_method_structure(mesh_api, client):
    """Test create_domain method structure and parameters"""
    expected_response = {
        "id": str(uuid.uuid4()),
        "name": "test-domain",
        "status": "ACTIVE",
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.create_domain(
        name="test-domain",
        description="Test description",
        status="ACTIVE"
    )

    assert result == expected_response
    client.post.assert_called_once()
    call_args = client.post.call_args
    assert call_args[0][0] == "mesh/domains/"
    assert call_args[1]["data"]["name"] == "test-domain"
    assert call_args[1]["data"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_create_domain_with_all_parameters(mesh_api, client):
    """Test create_domain with all optional parameters"""
    expected_response = {"id": str(uuid.uuid4()), "name": "test-domain"}
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.create_domain(
        name="test-domain",
        description="Test description",
        owner_id=str(uuid.uuid4()),
        boundaries={"key": "value"},
        capabilities={"cap": "ability"},
        resource_quota={"quota": 100},
        status="INACTIVE",
    )

    assert result == expected_response
    call_args = client.post.call_args
    data = call_args[1]["data"]
    assert data["name"] == "test-domain"
    assert data["description"] == "Test description"
    assert "owner_id" in data
    assert "boundaries" in data
    assert "capabilities" in data
    assert "resource_quota" in data
    assert data["status"] == "INACTIVE"


@pytest.mark.asyncio
async def test_list_domains_method_structure(mesh_api, client):
    """Test list_domains method structure and parameters"""
    expected_response = {
        "count": 10,
        "next": None,
        "previous": None,
        "results": [],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.list_domains()

    assert result == expected_response
    client.get.assert_called_once()
    call_args = client.get.call_args
    assert call_args[0][0] == "mesh/domains/"
    assert call_args[1]["params"]["page"] == 1
    assert call_args[1]["params"]["page_size"] == 20


@pytest.mark.asyncio
async def test_list_domains_with_filters(mesh_api, client):
    """Test list_domains with all filter parameters"""
    expected_response = {"count": 5, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.list_domains(
        status="ACTIVE",
        owner_id=str(uuid.uuid4()),
        search="test",
        ordering="-created_at",
        page=2,
        page_size=50,
    )

    assert result == expected_response
    call_args = client.get.call_args
    params = call_args[1]["params"]
    assert params["status"] == "ACTIVE"
    assert "owner_id" in params
    assert params["search"] == "test"
    assert params["ordering"] == "-created_at"
    assert params["page"] == 2
    assert params["page_size"] == 50


@pytest.mark.asyncio
async def test_list_domains_enforces_max_page_size(mesh_api, client):
    """Test that list_domains enforces max page size of 100"""
    expected_response = {"count": 0, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    await mesh_api.list_domains(page_size=200)

    call_args = client.get.call_args
    assert call_args[1]["params"]["page_size"] == 100  # Should be capped at 100


@pytest.mark.asyncio
async def test_get_domain_method_structure(mesh_api, client):
    """Test get_domain method structure"""
    domain_id = str(uuid.uuid4())
    expected_response = {"id": domain_id, "name": "test-domain"}
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_domain(domain_id)

    assert result == expected_response
    client.get.assert_called_once_with(f"mesh/domains/{domain_id}/")


@pytest.mark.asyncio
async def test_update_domain_method_structure(mesh_api, client):
    """Test update_domain method structure"""
    domain_id = str(uuid.uuid4())
    expected_response = {"id": domain_id, "name": "updated-name"}
    client.patch = AsyncMock(return_value=expected_response)

    result = await mesh_api.update_domain(domain_id, name="updated-name")

    assert result == expected_response
    client.patch.assert_called_once()
    call_args = client.patch.call_args
    assert call_args[0][0] == f"mesh/domains/{domain_id}/"
    assert call_args[1]["data"]["name"] == "updated-name"


@pytest.mark.asyncio
async def test_update_domain_with_all_parameters(mesh_api, client):
    """Test update_domain with all optional parameters"""
    domain_id = str(uuid.uuid4())
    expected_response = {"id": domain_id}
    client.patch = AsyncMock(return_value=expected_response)

    result = await mesh_api.update_domain(
        domain_id,
        name="updated-name",
        description="Updated description",
        owner_id=str(uuid.uuid4()),
        boundaries={"new": "boundaries"},
        capabilities={"new": "capabilities"},
        resource_quota={"new": 200},
        status="ARCHIVED",
    )

    assert result == expected_response
    call_args = client.patch.call_args
    data = call_args[1]["data"]
    assert data["name"] == "updated-name"
    assert data["description"] == "Updated description"
    assert "owner_id" in data
    assert "boundaries" in data
    assert "capabilities" in data
    assert "resource_quota" in data
    assert data["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_update_domain_requires_at_least_one_field(mesh_api):
    """Test that update_domain raises error if no fields provided"""
    domain_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="At least one field must be provided"):
        await mesh_api.update_domain(domain_id)


@pytest.mark.asyncio
async def test_update_domain_allows_empty_description(mesh_api, client):
    """Test that update_domain allows empty string for description"""
    domain_id = str(uuid.uuid4())
    expected_response = {"id": domain_id}
    client.patch = AsyncMock(return_value=expected_response)

    result = await mesh_api.update_domain(domain_id, description="")

    assert result == expected_response
    call_args = client.patch.call_args
    assert call_args[1]["data"]["description"] == ""


@pytest.mark.asyncio
async def test_delete_domain_method_structure(mesh_api, client):
    """Test delete_domain method structure"""
    domain_id = str(uuid.uuid4())
    client.delete = AsyncMock(return_value=None)

    await mesh_api.delete_domain(domain_id)

    client.delete.assert_called_once_with(f"mesh/domains/{domain_id}/")


# Integration Tests - Real API

@pytest.mark.asyncio
async def test_create_domain_integration(real_client):
    """Test creating domain with real API"""
    domain_name = f"test-domain-{uuid.uuid4().hex[:8]}"

    domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for SDK integration tests",
        status="ACTIVE"
    )

    assert domain is not None
    assert domain["name"] == domain_name
    assert domain["status"] == "ACTIVE"
    assert "id" in domain

    # Cleanup
    try:
        await real_client.mesh.delete_domain(domain["id"])
    except Exception:
        pass  # Ignore cleanup errors


@pytest.mark.asyncio
async def test_create_domain_with_all_fields_integration(real_client):
    """Test creating domain with all fields using real API"""
    domain_name = f"test-domain-full-{uuid.uuid4().hex[:8]}"

    domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Full test domain",
        boundaries={"data_source": "test"},
        capabilities={"processing": True},
        resource_quota={"storage_gb": 100},
        status="ACTIVE"
    )

    assert domain is not None
    assert domain["name"] == domain_name
    assert domain["description"] == "Full test domain"
    assert domain.get("boundaries") is not None
    assert domain.get("capabilities") is not None
    assert domain.get("resource_quota") is not None

    # Cleanup
    try:
        await real_client.mesh.delete_domain(domain["id"])
    except Exception:
        pass


@pytest.mark.asyncio
async def test_list_domains_integration(real_client):
    """Test listing domains with real API"""
    # Create a test domain first
    domain_name = f"test-list-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for listing"
    )

    try:
        # List domains
        result = await real_client.mesh.list_domains()

        assert result is not None
        assert "count" in result
        assert "results" in result
        assert isinstance(result["results"], list)

        # Verify our domain is in the list
        domain_ids = [d["id"] for d in result["results"]]
        assert created_domain["id"] in domain_ids
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_domains_with_filters_integration(real_client):
    """Test listing domains with filters using real API"""
    # Create test domains
    domain1_name = f"test-filter-1-{uuid.uuid4().hex[:8]}"
    domain2_name = f"test-filter-2-{uuid.uuid4().hex[:8]}"

    domain1 = await real_client.mesh.create_domain(name=domain1_name, status="ACTIVE")
    domain2 = await real_client.mesh.create_domain(name=domain2_name, status="INACTIVE")

    try:
        # Filter by status
        active_domains = await real_client.mesh.list_domains(status="ACTIVE")
        assert active_domains is not None
        assert all(d["status"] == "ACTIVE" for d in active_domains["results"])

        # Filter by search
        search_results = await real_client.mesh.list_domains(search="filter-1")
        assert search_results is not None
        assert any("filter-1" in d["name"] for d in search_results["results"])

        # Test pagination
        paginated = await real_client.mesh.list_domains(page=1, page_size=1)
        assert paginated is not None
        assert len(paginated["results"]) <= 1
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(domain1["id"])
            await real_client.mesh.delete_domain(domain2["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_domain_integration(real_client):
    """Test getting domain by ID with real API"""
    domain_name = f"test-get-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for get"
    )

    try:
        # Get domain
        domain = await real_client.mesh.get_domain(created_domain["id"])

        assert domain is not None
        assert domain["id"] == created_domain["id"]
        assert domain["name"] == domain_name
        assert domain["description"] == "Test domain for get"
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_domain_not_found_integration(real_client):
    """Test getting non-existent domain with real API"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain(fake_id)


@pytest.mark.asyncio
async def test_update_domain_integration(real_client):
    """Test updating domain with real API"""
    domain_name = f"test-update-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Original description"
    )

    try:
        # Update domain
        updated_domain = await real_client.mesh.update_domain(
            created_domain["id"],
            name=f"{domain_name}-updated",
            description="Updated description",
            status="INACTIVE"
        )

        assert updated_domain is not None
        assert updated_domain["name"] == f"{domain_name}-updated"
        assert updated_domain["description"] == "Updated description"
        assert updated_domain["status"] == "INACTIVE"
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_update_domain_not_found_integration(real_client):
    """Test updating non-existent domain with real API"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.update_domain(fake_id, name="updated-name")


@pytest.mark.asyncio
async def test_delete_domain_integration(real_client):
    """Test deleting domain with real API"""
    domain_name = f"test-delete-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(name=domain_name)

    # Delete domain
    await real_client.mesh.delete_domain(created_domain["id"])

    # Verify it's deleted
    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_delete_domain_not_found_integration(real_client):
    """Test deleting non-existent domain with real API"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.delete_domain(fake_id)


@pytest.mark.asyncio
async def test_create_domain_validation_error_integration(real_client):
    """Test creating domain with invalid data using real API"""
    # Try to create domain with empty name (should fail validation)
    with pytest.raises(ValidationError):
        await real_client.mesh.create_domain(name="")


@pytest.mark.asyncio
async def test_create_domain_duplicate_name_integration(real_client):
    """Test creating domain with duplicate name using real API"""
    domain_name = f"test-duplicate-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(name=domain_name)

    try:
        # Try to create another domain with same name (should fail)
        with pytest.raises((ConflictError, ValidationError)):
            await real_client.mesh.create_domain(name=domain_name)
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass

