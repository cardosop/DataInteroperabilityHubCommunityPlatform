from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive Integration Tests for Mesh API.

Tests all mesh API methods (domains, policies, topology, compliance) with real API service.
No mocks or stubs - all tests run against the real Docker Compose API service.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest sdk/python/tests/test_mesh_api.py -v
"""
import os
import pytest
import uuid
import asyncio
import subprocess
from typing import Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig, MeshAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
)
from tests._sdk_test_helpers import (
    check_api_available,
    create_real_api_config,
)

# File-specific tenant parameters
_MESH_TENANT_SLUG = "mesh-sdk-test-tenant"
_MESH_TENANT_NAME = "Mesh SDK Test Tenant"
_MESH_API_KEY_NAME = "mesh-sdk-test-key"
_MESH_SCOPES = ["mesh:write", "mesh:read", "governance:read", "governance:write"]
_MESH_EXTRA_TENANT_SETUP = "tenant.data_mesh_enabled = True; tenant.save()"


# ── Unit-test fixtures (no API calls) ───────────────────────────────

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


# ── Integration-test fixtures (real API) ────────────────────────────

@pytest.fixture(scope="module")
def real_api_config():
    """Fixture for real API configuration (module-scoped to avoid
    re-provisioning the API key for every test)."""
    return create_real_api_config(
        tenant_slug=_MESH_TENANT_SLUG,
        tenant_name=_MESH_TENANT_NAME,
        api_key_name=_MESH_API_KEY_NAME,
        scopes=_MESH_SCOPES,
        extra_tenant_setup=_MESH_EXTRA_TENANT_SETUP,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration."""
    async with DataHubClient(real_api_config) as client:
        yield client
        await asyncio.sleep(0.1)


# Module Structure Tests

def test_mesh_api_import():
    """Test that MeshAPI can be imported from package"""
    from datahub_interoperability import MeshAPI
    assert MeshAPI is not None
    assert hasattr(MeshAPI, '__init__')


def test_mesh_api_in_package_exports():
    """Test that MeshAPI is in package __all__ exports"""
    import datahub_interoperability
    assert 'MeshAPI' in datahub_interoperability.__all__


def test_mesh_api_initialization(mesh_api, client):
    """Test MeshAPI initialization"""
    assert mesh_api is not None
    assert mesh_api.client == client
    assert isinstance(mesh_api, MeshAPI)


@pytest.mark.asyncio
async def test_mesh_api_accessible_from_client(config):
    """Test that mesh API is accessible from client"""
    async with DataHubClient(config) as client:
        assert hasattr(client, 'mesh')
        assert client.mesh is not None
        assert isinstance(client.mesh, MeshAPI)


@pytest.mark.asyncio
async def test_mesh_api_has_client_reference(config):
    """Test that mesh API has reference to client"""
    async with DataHubClient(config) as client:
        assert client.mesh.client == client


def test_mesh_api_module_structure():
    """Test that mesh module has correct structure"""
    from datahub_interoperability.mesh import MeshAPI
    import inspect

    # Check class exists
    assert MeshAPI is not None

    # Check __init__ method exists
    assert hasattr(MeshAPI, '__init__')
    init_signature = inspect.signature(MeshAPI.__init__)
    assert 'client' in init_signature.parameters

    # Check docstring exists
    assert MeshAPI.__doc__ is not None
    assert 'Data Mesh API' in MeshAPI.__doc__


def test_mesh_api_docstring():
    """Test that MeshAPI has proper docstring"""
    from datahub_interoperability.mesh import MeshAPI

    assert MeshAPI.__doc__ is not None
    assert 'Data Mesh API' in MeshAPI.__doc__
    assert 'domain' in MeshAPI.__doc__.lower() or 'mesh' in MeshAPI.__doc__.lower()


def test_mesh_module_imports():
    """Test that mesh module can be imported directly"""
    from datahub_interoperability import mesh
    assert mesh is not None
    assert hasattr(mesh, 'MeshAPI')


@pytest.mark.asyncio
async def test_all_api_modules_initialized(config):
    """Test that all API modules including mesh are initialized"""
    async with DataHubClient(config) as client:
        # Check all expected API modules exist
        assert hasattr(client, 'contracts')
        assert hasattr(client, 'lineage')
        assert hasattr(client, 'scheduled_ingestion')
        assert hasattr(client, 'versioning')
        assert hasattr(client, 'governance')
        assert hasattr(client, 'mesh')  # New mesh API
        assert hasattr(client, 'search')
        assert hasattr(client, 'observability')
        assert hasattr(client, 'webhooks')

        # Verify mesh is MeshAPI instance
        assert isinstance(client.mesh, MeshAPI)


# Integration Tests - Domain Management

@pytest.mark.asyncio
async def test_create_domain_integration(real_client):
    """Test creating a domain with real API"""
    domain_name = f"test-domain-{uuid.uuid4().hex[:8]}"

    domain = await real_client.mesh.create_domain(
        name=domain_name,
        description="Test domain for integration tests",
        status="ACTIVE"
    )

    try:
        assert domain is not None
        assert domain.get('id') is not None
        assert domain.get('name') == domain_name
        assert domain.get('status') == 'ACTIVE'
    finally:
        try:
            await real_client.mesh.delete_domain(domain['id'])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_domains_integration(real_client):
    """Test listing domains with real API"""
    # Create a test domain first
    domain_name = f"test-domain-{uuid.uuid4().hex[:8]}"
    domain = await real_client.mesh.create_domain(name=domain_name)

    try:
        # List domains
        result = await real_client.mesh.list_domains()

        assert result is not None
        assert 'results' in result
        assert isinstance(result['results'], list)
        assert 'count' in result

        # Verify our domain is in the list
        domain_names = [d.get('name') for d in result['results']]
        assert domain_name in domain_names
    finally:
        try:
            await real_client.mesh.delete_domain(domain['id'])
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_domains_with_filters_integration(real_client):
    """Test listing domains with filters"""
    # Create test domains
    domain_name1 = f"test-domain-active-{uuid.uuid4().hex[:8]}"
    domain_name2 = f"test-domain-inactive-{uuid.uuid4().hex[:8]}"

    domain1 = await real_client.mesh.create_domain(name=domain_name1, status="ACTIVE")
    domain2 = await real_client.mesh.create_domain(name=domain_name2, status="INACTIVE")

    try:
        # Filter by status
        result = await real_client.mesh.list_domains(status="ACTIVE")

        assert result is not None
        assert all(d.get('status') == 'ACTIVE' for d in result['results'])
    finally:
        for d_id in [domain1['id'], domain2['id']]:
            try:
                await real_client.mesh.delete_domain(d_id)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_get_domain_integration(real_client):
    """Test getting a domain by ID with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}",
        description="Test domain"
    )
    domain_id = domain['id']

    try:
        # Get domain
        retrieved = await real_client.mesh.get_domain(domain_id)

        assert retrieved is not None
        assert retrieved['id'] == domain_id
        assert retrieved['name'] == domain['name']
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_update_domain_integration(real_client):
    """Test updating a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}",
        description="Original description"
    )
    domain_id = domain['id']

    try:
        # Update domain
        updated = await real_client.mesh.update_domain(
            domain_id,
            description="Updated description",
            status="INACTIVE"
        )

        assert updated is not None
        assert updated['id'] == domain_id
        assert updated['description'] == "Updated description"
        assert updated['status'] == "INACTIVE"
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_delete_domain_integration(real_client):
    """Test deleting a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    # Delete domain
    await real_client.mesh.delete_domain(domain_id)

    # Verify domain is deleted
    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain(domain_id)


# Integration Tests - Policy Management

@pytest.mark.asyncio
async def test_apply_policy_integration(real_client):
    """Test applying a policy to a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Create a test policy via Django shell
        policy_id = await _create_test_policy(real_client, _MESH_TENANT_SLUG)

        if not policy_id:
            pytest.skip("Could not create test policy")

        # Apply policy
        result = await real_client.mesh.apply_policy(
            domain_id=domain_id,
            policy_id=policy_id
        )

        assert result is not None
        assert result.get('domain_id') == domain_id
        assert result.get('policy_id') == policy_id
        assert result.get('status') in ['PENDING', 'APPLIED']
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_list_policies_integration(real_client):
    """Test listing policies for a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Create and apply a test policy
        policy_id = await _create_test_policy(real_client, _MESH_TENANT_SLUG)
        if policy_id:
            await real_client.mesh.apply_policy(domain_id, policy_id)

        # List policies
        result = await real_client.mesh.list_policies(domain_id)

        assert result is not None
        assert 'results' in result
        assert isinstance(result['results'], list)
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_remove_policy_integration(real_client):
    """Test removing a policy from a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Create and apply a test policy
        policy_id = await _create_test_policy(real_client, _MESH_TENANT_SLUG)
        if not policy_id:
            pytest.skip("Could not create test policy")

        await real_client.mesh.apply_policy(domain_id, policy_id)

        # Remove policy
        result = await real_client.mesh.remove_policy(domain_id, policy_id)

        # Verify removal: the API keeps the association record but sets
        # status to REVOKED.  Check the policy status in the listing.
        if result is not None:
            assert result.get('status') == 'REVOKED', (
                f"Expected REVOKED status after removal, got {result.get('status')}"
            )
        # Confirm the policy appears with REVOKED status in the domain listing
        policies_after = await real_client.mesh.list_policies(domain_id)
        revoked = [
            p for p in policies_after.get('results', [])
            if (p.get('policy_id') or p.get('id')) == policy_id
        ]
        assert len(revoked) > 0, f"Policy {policy_id} not found in listing after removal"
        assert revoked[0].get('status') == 'REVOKED', (
            f"Policy {policy_id} should be REVOKED, got {revoked[0].get('status')}"
        )
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


# Integration Tests - Topology Operations

@pytest.mark.asyncio
async def test_get_topology_integration(real_client):
    """Test getting complete topology with real API"""
    # Create some test domains
    domain1 = await real_client.mesh.create_domain(name=f"test-domain-1-{uuid.uuid4().hex[:8]}")
    domain2 = await real_client.mesh.create_domain(name=f"test-domain-2-{uuid.uuid4().hex[:8]}")

    try:
        # Get topology
        topology = await real_client.mesh.get_topology(include_health_metrics=True)

        assert topology is not None
        assert 'nodes' in topology, f"Missing 'nodes' in topology: {list(topology.keys())}"
        assert 'metadata' in topology, f"Missing 'metadata' in topology: {list(topology.keys())}"
        assert 'summary' in topology, f"Missing 'summary' in topology: {list(topology.keys())}"
    finally:
        for d_id in [domain1['id'], domain2['id']]:
            try:
                await real_client.mesh.delete_domain(d_id)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_get_domain_topology_integration(real_client):
    """Test getting domain-specific topology with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Get domain topology
        topology = await real_client.mesh.get_domain_topology(domain_id)

        assert topology is not None
        assert 'domain' in topology, (
            f"Missing 'domain' key in topology response. Keys: {list(topology.keys())}"
        )
        assert topology['domain']['id'] == domain_id, (
            f"Expected domain id={domain_id}, got {topology.get('domain', {}).get('id')}"
        )
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


# Integration Tests - Compliance Operations

@pytest.mark.asyncio
async def test_check_compliance_integration(real_client):
    """Test checking compliance for a domain with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Check compliance
        report = await real_client.mesh.check_compliance(domain_id)

        assert report is not None
        assert report.get('domain_id') == domain_id
        assert report.get('compliance_status') is not None
        assert report.get('id') is not None  # Report ID
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_get_compliance_report_integration(real_client):
    """Test getting a compliance report with real API"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']

    try:
        # Check compliance to create a report
        report = await real_client.mesh.check_compliance(domain_id)
        report_id = report['id']

        # Get the report
        retrieved = await real_client.mesh.get_compliance_report(domain_id, report_id)

        assert retrieved is not None
        assert retrieved['id'] == report_id
        assert retrieved['domain_id'] == domain_id
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


# Error Handling Tests

@pytest.mark.asyncio
async def test_get_domain_not_found_error(real_client):
    """Test error handling for non-existent domain"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain(fake_id)


@pytest.mark.asyncio
async def test_update_domain_not_found_error(real_client):
    """Test error handling for updating non-existent domain"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.update_domain(fake_id, name="Test")


@pytest.mark.asyncio
async def test_delete_domain_not_found_error(real_client):
    """Test error handling for deleting non-existent domain"""
    fake_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.delete_domain(fake_id)


@pytest.mark.asyncio
async def test_create_domain_validation_error(real_client):
    """Test error handling for invalid domain data"""
    # Try to create domain without required name
    with pytest.raises((ValidationError, ValueError)):
        await real_client.mesh.create_domain(name="")


@pytest.mark.asyncio
async def test_apply_policy_not_found_error(real_client):
    """Test error handling for applying policy to non-existent domain"""
    fake_domain_id = str(uuid.uuid4())
    fake_policy_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.apply_policy(fake_domain_id, fake_policy_id)


@pytest.mark.asyncio
async def test_list_policies_not_found_error(real_client):
    """Test error handling for listing policies for non-existent domain"""
    fake_domain_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.list_policies(fake_domain_id)


@pytest.mark.asyncio
async def test_get_domain_topology_not_found_error(real_client):
    """Test error handling for getting topology of non-existent domain"""
    fake_domain_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.get_domain_topology(fake_domain_id)


@pytest.mark.asyncio
async def test_check_compliance_not_found_error(real_client):
    """Test error handling for checking compliance of non-existent domain"""
    fake_domain_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.check_compliance(fake_domain_id)


@pytest.mark.asyncio
async def test_get_compliance_report_not_found_error(real_client):
    """Test error handling for getting non-existent compliance report"""
    # Create a test domain
    domain = await real_client.mesh.create_domain(
        name=f"test-domain-{uuid.uuid4().hex[:8]}"
    )
    domain_id = domain['id']
    fake_report_id = str(uuid.uuid4())

    try:
        with pytest.raises(NotFoundError):
            await real_client.mesh.get_compliance_report(domain_id, fake_report_id)
    finally:
        try:
            await real_client.mesh.delete_domain(domain_id)
        except Exception:
            pass


# Helper Functions

async def _create_test_policy(client: DataHubClient, tenant_slug: str) -> Optional[str]:
    """Create a test policy via Django shell for the given tenant.

    Tries the test Docker Compose stack first (api-service-test /
    hub/manage.py), then the main stack (api-service / manage.py).
    """
    django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy

tenant = Tenant.objects.filter(slug='{tenant_slug}').first()
if not tenant:
    print("NO_TENANT")
    exit(1)

# Create a test policy
policy = AccessPolicy.objects.create(
    tenant=tenant,
    name='Test Policy for SDK',
    description='Test policy for SDK integration tests',
    enabled=True,
    effect='ALLOW',
    conditions={{}},
    priority=100
)
print(policy.id)
"""

    _compose_attempts = [
        (["docker", "compose", "-f", "docker-compose.test.yml",
          "exec", "-T", "api-service-test"], "hub/manage.py"),
        (["docker", "compose", "exec", "-T", "api-service"], "manage.py"),
    ]

    for compose_cmd, manage_py in _compose_attempts:
        try:
            result = subprocess.run(
                compose_cmd + ["python", manage_py, "shell"],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/home/ph/Desktop/DataInteroperabilityHub',
            )
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                for line in reversed(output_lines):
                    line = line.strip()
                    if line and len(line) == 36 and '-' in line:
                        return line
        except Exception:
            pass

    return None
