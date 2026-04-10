from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Mesh Topology API methods.

Tests topology operations with comprehensive error handling.
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
    slug='mesh-topology-sdk-test-tenant',
    defaults={'name': 'Mesh Topology SDK Test Tenant'}
)

# Get or create TENANT_ADMIN role
admin_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='TENANT_ADMIN',
    defaults={'description': 'Tenant Administrator'}
)

user, _ = User.objects.get_or_create(
    email='mesh-topology-sdk-test@example.com',
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
APIKey.objects.filter(user=user, name='mesh-topology-sdk-test-key').delete()

# Create new API key with mesh:write and mesh:read scopes
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='mesh-topology-sdk-test-key',
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
async def test_get_topology_method_structure(mesh_api, client):
    """Test get_topology method structure and parameters"""
    expected_response = {
        "nodes": [],
        "edges": [],
        "metadata": {},
        "summary": {},
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_topology()

    assert result == expected_response
    client.get.assert_called_once()
    call_args = client.get.call_args
    assert call_args[0][0] == "mesh/topology/"
    assert call_args[1]["params"]["include_health_metrics"] == "true"


@pytest.mark.asyncio
async def test_get_topology_with_health_metrics(mesh_api, client):
    """Test get_topology with include_health_metrics=True"""
    expected_response = {
        "nodes": [{"id": "domain-1", "name": "Test Domain"}],
        "edges": [],
        "metadata": {"tenant_id": "tenant-1"},
        "summary": {"total_domains": 1},
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_topology(include_health_metrics=True)

    assert result == expected_response
    call_args = client.get.call_args
    assert call_args[1]["params"]["include_health_metrics"] == "true"


@pytest.mark.asyncio
async def test_get_topology_without_health_metrics(mesh_api, client):
    """Test get_topology with include_health_metrics=False"""
    expected_response = {
        "nodes": [],
        "edges": [],
        "metadata": {},
        "summary": {},
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_topology(include_health_metrics=False)

    assert result == expected_response
    call_args = client.get.call_args
    assert call_args[1]["params"]["include_health_metrics"] == "false"


@pytest.mark.asyncio
async def test_get_domain_topology_method_structure(mesh_api, client):
    """Test get_domain_topology method structure"""
    domain_id = str(uuid.uuid4())
    expected_response = {
        "domain": {"id": domain_id, "name": "Test Domain"},
        "relationships": [],
        "health_metrics": {},
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_domain_topology(domain_id)

    assert result == expected_response
    client.get.assert_called_once_with(f"mesh/topology/{domain_id}/")


# Integration Tests - Real API

@pytest.mark.asyncio
async def test_get_topology_integration(real_client):
    """Test getting topology with real API"""
    result = await real_client.mesh.get_topology()

    assert result is not None
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert "summary" in result
    assert isinstance(result["nodes"], list)
    assert isinstance(result["edges"], list)
    assert isinstance(result["metadata"], dict)
    assert isinstance(result["summary"], dict)


@pytest.mark.asyncio
async def test_get_topology_with_health_metrics_integration(real_client):
    """Test getting topology with health metrics using real API"""
    result = await real_client.mesh.get_topology(include_health_metrics=True)

    assert result is not None
    assert "nodes" in result
    assert "edges" in result
    assert "summary" in result
    # Verify summary has expected fields
    summary = result.get("summary", {})
    assert "total_domains" in summary
    assert "active_domains" in summary
    assert "total_relationships" in summary


@pytest.mark.asyncio
async def test_get_topology_without_health_metrics_integration(real_client):
    """Test getting topology without health metrics using real API"""
    result = await real_client.mesh.get_topology(include_health_metrics=False)

    assert result is not None
    assert "nodes" in result
    assert "edges" in result
    assert "metadata" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_get_domain_topology_integration(real_client):
    """Test getting domain topology with real API"""
    # First create a test domain
    domain_name = f"test-topology-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for topology"
    )

    try:
        # Get domain topology
        topology = await real_client.mesh.get_domain_topology(created_domain["id"])

        assert topology is not None
        assert "domain" in topology
        assert "relationships" in topology
        assert "health_metrics" in topology
        assert topology["domain"]["id"] == created_domain["id"]
        assert isinstance(topology["relationships"], list)
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_domain_topology_not_found_integration(real_client):
    """Test getting topology for non-existent domain with real API"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain_topology(fake_id)


@pytest.mark.asyncio
async def test_get_topology_with_domains_integration(real_client):
    """Test getting topology when domains exist using real API"""
    # Create test domains
    domain1_name = f"topology-test-1-{uuid.uuid4().hex[:8]}"
    domain2_name = f"topology-test-2-{uuid.uuid4().hex[:8]}"

    domain1 = await real_client.mesh.create_domain(name=domain1_name)
    domain2 = await real_client.mesh.create_domain(name=domain2_name)

    try:
        # Wait a bit for topology to update
        import asyncio
        await asyncio.sleep(2)

        # Get topology
        topology = await real_client.mesh.get_topology()

        assert topology is not None
        assert "nodes" in topology
        assert "edges" in topology

        # Verify our domains are in the topology
        node_ids = [str(node.get("id", "")) for node in topology.get("nodes", [])]
        assert domain1["id"] in node_ids or domain2["id"] in node_ids

        # Verify summary
        summary = topology.get("summary", {})
        assert summary.get("total_domains", 0) >= 2
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(domain1["id"])
            await real_client.mesh.delete_domain(domain2["id"])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_topology_structure_integration(real_client):
    """Test topology response structure with real API"""
    result = await real_client.mesh.get_topology()

    # Verify nodes structure
    if result.get("nodes"):
        node = result["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "status" in node

    # Verify edges structure
    if result.get("edges"):
        edge = result["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge
        assert "weight" in edge

    # Verify metadata structure
    metadata = result.get("metadata", {})
    assert "tenant_id" in metadata
    assert "domain_count" in metadata
    assert "relationship_count" in metadata
    assert "generated_at" in metadata

    # Verify summary structure
    summary = result.get("summary", {})
    assert "total_domains" in summary
    assert "active_domains" in summary
    assert "total_relationships" in summary


@pytest.mark.asyncio
async def test_get_domain_topology_structure_integration(real_client):
    """Test domain topology response structure with real API"""
    # Create a test domain
    domain_name = f"topology-structure-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for structure validation"
    )

    try:
        # Get domain topology
        topology = await real_client.mesh.get_domain_topology(created_domain["id"])

        # Verify domain structure
        domain = topology.get("domain", {})
        assert "id" in domain
        assert "name" in domain
        assert domain["id"] == created_domain["id"]
        assert domain["name"] == domain_name

        # Verify relationships is a list
        assert isinstance(topology.get("relationships"), list)

        # Verify health_metrics exists (may be None)
        assert "health_metrics" in topology
    finally:
        # Cleanup
        try:
            await real_client.mesh.delete_domain(created_domain["id"])
        except Exception:
            pass

