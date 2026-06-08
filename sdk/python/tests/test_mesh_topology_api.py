from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Mesh Topology API methods.

Tests topology operations with comprehensive error handling.
"""
import os
import pytest
import uuid
import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from datahub_interoperability import DataHubClient, DataHubClientConfig, MeshAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
)
from tests._sdk_test_helpers import (
    check_api_available,
    create_real_api_config,
)

# File-specific tenant parameters
_TOPOLOGY_TENANT_SLUG = "mesh-topology-sdk-test-tenant"
_TOPOLOGY_TENANT_NAME = "Mesh Topology SDK Test Tenant"
_TOPOLOGY_API_KEY_NAME = "mesh-topology-sdk-test-key"
_TOPOLOGY_SCOPES = ["mesh:write", "mesh:read"]
_TOPOLOGY_EXTRA_TENANT_SETUP = "tenant.data_mesh_enabled = True; tenant.save()"


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
    """Fixture for real API configuration (module-scoped)."""
    return create_real_api_config(
        tenant_slug=_TOPOLOGY_TENANT_SLUG,
        tenant_name=_TOPOLOGY_TENANT_NAME,
        api_key_name=_TOPOLOGY_API_KEY_NAME,
        scopes=_TOPOLOGY_SCOPES,
        extra_tenant_setup=_TOPOLOGY_EXTRA_TENANT_SETUP,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration."""
    import asyncio
    async with DataHubClient(real_api_config) as client:
        yield client
        # Longer delay for topology tests — the get_topology polling
        # in structure tests generates heavy server load.
        await asyncio.sleep(0.5)


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

    # Verify health metrics are actually excluded
    assert "health_metrics" not in result.get("summary", {}), (
        "Health metrics should be excluded when include_health_metrics=False"
    )
    for node in result.get("nodes", []):
        assert "health_status" not in node, (
            f"Node {node.get('id')} has health_status despite include_health_metrics=False"
        )


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
        # Poll until both domains appear in topology (up to 15s)
        import asyncio
        import time as _time
        topology = None
        deadline = _time.monotonic() + 15
        while _time.monotonic() < deadline:
            topology = await real_client.mesh.get_topology()
            node_ids = [str(node.get("id", "")) for node in topology.get("nodes", [])]
            if domain1["id"] in node_ids and domain2["id"] in node_ids:
                break
            await asyncio.sleep(0.5)
        else:
            # Timeout — use whatever topology we have
            pass

        assert topology is not None
        assert "nodes" in topology
        assert "edges" in topology

        # Verify our domains are in the topology
        node_ids = [str(node.get("id", "")) for node in topology.get("nodes", [])]
        assert domain1["id"] in node_ids, (
            f"Domain {domain1['id']} not found in topology nodes: {node_ids}"
        )
        assert domain2["id"] in node_ids, (
            f"Domain {domain2['id']} not found in topology nodes: {node_ids}"
        )

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
    """Test topology response structure with real API.

    Creates test domains first to guarantee non-empty topology for
    node/edge structure validation.
    """
    import asyncio
    import time as _time

    # Create test domains to guarantee non-empty topology
    domain1 = await real_client.mesh.create_domain(
        name=f"topology-structure-1-{uuid.uuid4().hex[:8]}"
    )
    domain2 = await real_client.mesh.create_domain(
        name=f"topology-structure-2-{uuid.uuid4().hex[:8]}"
    )

    try:
        # Poll until domains appear in topology (up to 15s, 1s intervals
        # to avoid overwhelming the server with rapid get_topology calls).
        result = None
        deadline = _time.monotonic() + 15
        while _time.monotonic() < deadline:
            result = await real_client.mesh.get_topology()
            if len(result.get("nodes", [])) >= 2:
                break
            await asyncio.sleep(1.0)

        assert result is not None
        assert len(result.get("nodes", [])) >= 2, (
            f"Expected at least 2 nodes in topology, got {len(result.get('nodes', []))}"
        )

        # Verify nodes structure
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
    finally:
        for d_id in [domain1["id"], domain2["id"]]:
            try:
                await real_client.mesh.delete_domain(d_id)
            except Exception:
                pass


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

