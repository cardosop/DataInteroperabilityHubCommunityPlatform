from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Mesh Policy Management API methods.

Tests policy application, listing, and removal operations with comprehensive error handling.
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
    slug='mesh-policies-sdk-test-tenant',
    defaults={'name': 'Mesh Policies SDK Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

user, _ = User.objects.get_or_create(
    email='mesh-policies-sdk-test@example.com',
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
APIKey.objects.filter(user=user, name='mesh-policies-sdk-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-policies-sdk-test-key',
    key_hash=api_key_hash,
    scopes=['mesh:write', 'mesh:read', 'governance:read', 'governance:write']
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
async def test_apply_policy_method_structure(mesh_api, client):
    """Test apply_policy method structure and parameters"""
    domain_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    expected_response = {
        "id": str(uuid.uuid4()),
        "domain_id": domain_id,
        "policy_id": policy_id,
        "status": "APPLIED",
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.apply_policy(domain_id, policy_id)

    assert result == expected_response
    client.post.assert_called_once()
    call_args = client.post.call_args
    assert call_args[0][0] == f"mesh/domains/{domain_id}/policies/apply/"
    assert call_args[1]["data"]["policy_id"] == policy_id


@pytest.mark.asyncio
async def test_apply_policy_with_overrides(mesh_api, client):
    """Test apply_policy with overrides parameter"""
    domain_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    overrides = {"priority": 50, "effect": "ALLOW"}
    expected_response = {"id": str(uuid.uuid4()), "status": "APPLIED"}
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.apply_policy(domain_id, policy_id, overrides=overrides)

    assert result == expected_response
    call_args = client.post.call_args
    assert call_args[1]["data"]["overrides"] == overrides


@pytest.mark.asyncio
async def test_list_policies_method_structure(mesh_api, client):
    """Test list_policies method structure and parameters"""
    domain_id = str(uuid.uuid4())
    expected_response = {
        "count": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "results": [],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.list_policies(domain_id)

    assert result == expected_response
    client.get.assert_called_once()
    call_args = client.get.call_args
    assert call_args[0][0] == f"mesh/domains/{domain_id}/policies/"
    assert call_args[1]["params"]["page"] == 1
    assert call_args[1]["params"]["page_size"] == 20


@pytest.mark.asyncio
async def test_list_policies_with_filters(mesh_api, client):
    """Test list_policies with all filter parameters"""
    domain_id = str(uuid.uuid4())
    expected_response = {"count": 5, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.list_policies(
        domain_id,
        status="APPLIED",
        page=2,
        page_size=50,
    )

    assert result == expected_response
    call_args = client.get.call_args
    params = call_args[1]["params"]
    assert params["status"] == "APPLIED"
    assert params["page"] == 2
    assert params["page_size"] == 50


@pytest.mark.asyncio
async def test_list_policies_enforces_max_page_size(mesh_api, client):
    """Test that list_policies enforces max page size of 100"""
    domain_id = str(uuid.uuid4())
    expected_response = {"count": 0, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    await mesh_api.list_policies(domain_id, page_size=200)

    call_args = client.get.call_args
    assert call_args[1]["params"]["page_size"] == 100  # Should be capped at 100


@pytest.mark.asyncio
async def test_remove_policy_method_structure(mesh_api, client):
    """Test remove_policy method structure"""
    domain_id = str(uuid.uuid4())
    policy_id = str(uuid.uuid4())
    expected_response = {"id": str(uuid.uuid4()), "status": "REVOKED"}
    client.delete = AsyncMock(return_value=expected_response)

    result = await mesh_api.remove_policy(domain_id, policy_id)

    assert result == expected_response
    client.delete.assert_called_once_with(f"mesh/domains/{domain_id}/policies/{policy_id}/")


# Integration Tests - Real API

@pytest.mark.asyncio
async def test_apply_policy_integration(real_client):
    """Test applying policy with real API"""
    # First create a test domain
    domain_name = f"test-policy-apply-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for policy application",
        status="ACTIVE"
    )

    # Create a test policy via API
    try:
        import requests
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')
        api_key = setup_authentication_for_sdk_tests(api_base_url)

        # Create a policy
        policy_response = requests.post(
            f"{api_base_url}/governance/policies/",
            json={
                "name": f"Test Policy {uuid.uuid4().hex[:8]}",
                "description": "Test policy for SDK tests",
                "conditions": {"user": {"tenant_id": "test"}},
                "effect": "ALLOW",
                "enabled": True,
            },
            headers={"X-API-Key": api_key},
            timeout=10
        )

        if policy_response.status_code == 201:
            policy_data = policy_response.json()
            policy_id = policy_data["id"]

            try:
                # Apply policy
                result = await real_client.mesh.apply_policy(
                    created_domain["id"],
                    policy_id
                )

                assert result is not None
                assert result["domain_id"] == created_domain["id"]
                assert result["policy_id"] == policy_id
                assert result["status"] in ["PENDING", "APPLIED"]
                assert "id" in result

                # Cleanup policy application
                try:
                    await real_client.mesh.remove_policy(created_domain["id"], policy_id)
                except Exception:
                    pass
            finally:
                # Cleanup policy
                try:
                    requests.delete(
                        f"{api_base_url}/governance/policies/{policy_id}/",
                        headers={"X-API-Key": api_key},
                        timeout=10
                    )
                except Exception:
                    pass
    finally:
        # Cleanup domain
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_apply_policy_with_overrides_integration(real_client):
    """Test applying policy with overrides using real API"""
    # First create a test domain
    domain_name = f"test-policy-overrides-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for policy overrides",
        status="ACTIVE"
    )

    # Create a test policy via API
    try:
        import requests
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')
        api_key = setup_authentication_for_sdk_tests(api_base_url)

        # Create a policy
        policy_response = requests.post(
            f"{api_base_url}/governance/policies/",
            json={
                "name": f"Test Policy Overrides {uuid.uuid4().hex[:8]}",
                "description": "Test policy for overrides",
                "conditions": {"user": {"tenant_id": "test"}},
                "effect": "ALLOW",
                "enabled": True,
            },
            headers={"X-API-Key": api_key},
            timeout=10
        )

        if policy_response.status_code == 201:
            policy_data = policy_response.json()
            policy_id = policy_data["id"]

            try:
                # Apply policy with overrides
                overrides = {"priority": 50, "effect": "ALLOW"}
                result = await real_client.mesh.apply_policy(
                    created_domain["id"],
                    policy_id,
                    overrides=overrides
                )

                assert result is not None
                assert result["domain_id"] == created_domain["id"]
                assert result["policy_id"] == policy_id
                assert result.get("overrides") == overrides

                # Cleanup policy application
                try:
                    await real_client.mesh.remove_policy(created_domain["id"], policy_id)
                except Exception:
                    pass
            finally:
                # Cleanup policy
                try:
                    requests.delete(
                        f"{api_base_url}/governance/policies/{policy_id}/",
                        headers={"X-API-Key": api_key},
                        timeout=10
                    )
                except Exception:
                    pass
    finally:
        # Cleanup domain
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_policies_integration(real_client):
    """Test listing policies with real API"""
    # First create a test domain
    domain_name = f"test-policy-list-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for listing policies",
        status="ACTIVE"
    )

    try:
        # List policies (should be empty initially)
        result = await real_client.mesh.list_policies(created_domain["id"])

        assert result is not None
        assert "count" in result
        assert "results" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert isinstance(result["results"], list)
        assert result["count"] >= 0
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_policies_with_filters_integration(real_client):
    """Test listing policies with filters using real API"""
    # First create a test domain
    domain_name = f"test-policy-filter-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for policy filters",
        status="ACTIVE"
    )

    try:
        # Filter by status
        result = await real_client.mesh.list_policies(
            created_domain["id"],
            status="APPLIED"
        )

        assert result is not None
        assert "results" in result
        # All results should have APPLIED status if any exist
        if result["results"]:
            assert all(p["status"] == "APPLIED" for p in result["results"])

        # Test pagination
        paginated = await real_client.mesh.list_policies(
            created_domain["id"],
            page=1,
            page_size=10
        )

        assert paginated is not None
        assert len(paginated["results"]) <= 10
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_remove_policy_integration(real_client):
    """Test removing policy with real API"""
    # First create a test domain
    domain_name = f"test-policy-remove-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for policy removal",
        status="ACTIVE"
    )

    # Create a test policy via API
    try:
        import requests
        api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')
        api_key = setup_authentication_for_sdk_tests(api_base_url)

        # Create a policy
        policy_response = requests.post(
            f"{api_base_url}/governance/policies/",
            json={
                "name": f"Test Policy Remove {uuid.uuid4().hex[:8]}",
                "description": "Test policy for removal",
                "conditions": {"user": {"tenant_id": "test"}},
                "effect": "ALLOW",
                "enabled": True,
            },
            headers={"X-API-Key": api_key},
            timeout=10
        )

        if policy_response.status_code == 201:
            policy_data = policy_response.json()
            policy_id = policy_data["id"]

            try:
                # Apply policy first
                applied = await real_client.mesh.apply_policy(
                    created_domain["id"],
                    policy_id
                )

                assert applied is not None

                # Remove policy
                result = await real_client.mesh.remove_policy(
                    created_domain["id"],
                    policy_id
                )

                assert result is not None
                assert result["status"] == "REVOKED"

                # Verify it's removed by listing policies
                policies = await real_client.mesh.list_policies(created_domain["id"])
                # The policy should still be in the list but with REVOKED status
                revoked_policies = [p for p in policies["results"] if p["id"] == applied["id"]]
                if revoked_policies:
                    assert revoked_policies[0]["status"] == "REVOKED"
            finally:
                # Cleanup policy
                try:
                    requests.delete(
                        f"{api_base_url}/governance/policies/{policy_id}/",
                        headers={"X-API-Key": api_key},
                        timeout=10
                    )
                except Exception:
                    pass
    finally:
        # Cleanup domain
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_apply_policy_not_found_integration(real_client):
    """Test applying policy to non-existent domain with real API"""
    fake_domain_id = str(uuid.uuid4())
    fake_policy_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.apply_policy(fake_domain_id, fake_policy_id)


@pytest.mark.asyncio
async def test_list_policies_not_found_integration(real_client):
    """Test listing policies for non-existent domain with real API"""
    fake_domain_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.list_policies(fake_domain_id)


@pytest.mark.asyncio
async def test_remove_policy_not_found_integration(real_client):
    """Test removing non-existent policy with real API"""
    # Create a test domain first
    domain_name = f"test-policy-notfound-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(name=domain_name)

    try:
        fake_policy_id = str(uuid.uuid4())

        with pytest.raises(NotFoundError):
            await real_client.mesh.remove_policy(created_domain["id"], fake_policy_id)
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass

