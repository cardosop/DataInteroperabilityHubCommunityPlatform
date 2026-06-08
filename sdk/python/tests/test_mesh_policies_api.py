from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Mesh Policy Management API methods.

Tests policy application, listing, and removal operations with comprehensive error handling.
"""
import os
import pytest
import uuid
import asyncio
import subprocess
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
_POLICIES_TENANT_SLUG = "mesh-policies-sdk-test-tenant"
_POLICIES_TENANT_NAME = "Mesh Policies SDK Test Tenant"
_POLICIES_API_KEY_NAME = "mesh-policies-sdk-test-key"
_POLICIES_SCOPES = ["mesh:write", "mesh:read", "governance:read", "governance:write"]
_POLICIES_EXTRA_TENANT_SETUP = "tenant.data_mesh_enabled = True; tenant.save()"


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
        tenant_slug=_POLICIES_TENANT_SLUG,
        tenant_name=_POLICIES_TENANT_NAME,
        api_key_name=_POLICIES_API_KEY_NAME,
        scopes=_POLICIES_SCOPES,
        extra_tenant_setup=_POLICIES_EXTRA_TENANT_SETUP,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration."""
    import asyncio
    async with DataHubClient(real_api_config) as client:
        yield client
        await asyncio.sleep(0.1)  # Reduce server load between tests


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


async def _create_policy_for_test(tenant_slug: str) -> Optional[str]:
    """Create a test AccessPolicy via Django shell (same approach as
    test_mesh_api.py).  Returns the policy UUID or None on failure.

    Uses docker compose exec because the governance HTTP API endpoint
    is not reliably available on all test/staging deployments.
    """
    django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy

tenant = Tenant.objects.filter(slug='{tenant_slug}').first()
if not tenant:
    print("NO_TENANT")
    exit(1)

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

    # Create a test policy via Django shell
    policy_id = await _create_policy_for_test(_POLICIES_TENANT_SLUG)
    if not policy_id:
        pytest.skip("Could not create test policy via Django shell")

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

    # Create a test policy via Django shell
    policy_id = await _create_policy_for_test(_POLICIES_TENANT_SLUG)
    if not policy_id:
        pytest.skip("Could not create test policy via Django shell")

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

    # Create a test policy via Django shell
    policy_id = await _create_policy_for_test(_POLICIES_TENANT_SLUG)
    if not policy_id:
        pytest.skip("Could not create test policy via Django shell")

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

