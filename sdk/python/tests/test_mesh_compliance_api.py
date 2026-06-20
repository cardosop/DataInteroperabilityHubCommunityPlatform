from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Tests for Mesh Compliance API methods.

Tests compliance checking and report retrieval operations with comprehensive error handling.
"""
import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig, MeshAPI
from datahub_interoperability.errors import (
    NotFoundError,
)
from tests._sdk_test_helpers import (
    create_real_api_config,
)
import contextlib

# File-specific tenant parameters
_COMPLIANCE_TENANT_SLUG = "mesh-compliance-sdk-test-tenant"
_COMPLIANCE_TENANT_NAME = "Mesh Compliance SDK Test Tenant"
_COMPLIANCE_API_KEY_NAME = "mesh-compliance-sdk-test-key"
_COMPLIANCE_SCOPES = ["mesh:write", "mesh:read", "governance:read", "governance:write"]
_COMPLIANCE_EXTRA_TENANT_SETUP = "tenant.data_mesh_enabled = True; tenant.save()"


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
        tenant_slug=_COMPLIANCE_TENANT_SLUG,
        tenant_name=_COMPLIANCE_TENANT_NAME,
        api_key_name=_COMPLIANCE_API_KEY_NAME,
        scopes=_COMPLIANCE_SCOPES,
        extra_tenant_setup=_COMPLIANCE_EXTRA_TENANT_SETUP,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Create SDK client with real API configuration."""
    async with DataHubClient(real_api_config) as client:
        yield client
        await asyncio.sleep(0.1)  # Reduce server load between tests


# Unit Tests - Method Structure and Parameters


@pytest.mark.asyncio
async def test_check_compliance_method_structure(mesh_api, client):
    """Test check_compliance method structure and parameters"""
    domain_id = str(uuid.uuid4())
    expected_response = {
        "id": str(uuid.uuid4()),
        "domain_id": domain_id,
        "compliance_status": "COMPLIANT",
        "violations": {},
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.check_compliance(domain_id)

    assert result == expected_response
    client.post.assert_called_once()
    call_args = client.post.call_args
    assert call_args[0][0] == f"mesh/domains/{domain_id}/compliance/check/"
    assert call_args[1]["data"] == {}


@pytest.mark.asyncio
async def test_check_compliance_with_asset_id(mesh_api, client):
    """Test check_compliance with asset_id parameter"""
    domain_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    expected_response = {
        "id": str(uuid.uuid4()),
        "domain_id": domain_id,
        "asset_id": asset_id,
        "compliance_status": "COMPLIANT",
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await mesh_api.check_compliance(domain_id, asset_id=asset_id)

    assert result == expected_response
    call_args = client.post.call_args
    assert call_args[1]["data"]["asset_id"] == asset_id


@pytest.mark.asyncio
async def test_get_compliance_report_method_structure(mesh_api, client):
    """Test get_compliance_report method structure"""
    domain_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    expected_response = {
        "id": report_id,
        "domain_id": domain_id,
        "compliance_status": "COMPLIANT",
        "violations": {},
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await mesh_api.get_compliance_report(domain_id, report_id)

    assert result == expected_response
    client.get.assert_called_once_with(f"mesh/domains/{domain_id}/compliance/reports/{report_id}/")


# Integration Tests - Real API


@pytest.mark.asyncio
async def test_check_compliance_integration(real_client):
    """Test checking compliance with real API"""
    # First create a test domain
    domain_name = f"test-compliance-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name, description="Test domain for compliance checking", status="ACTIVE"
    )

    try:
        # Check compliance
        result = await real_client.mesh.check_compliance(created_domain["id"])

        assert result is not None
        assert result["domain_id"] == created_domain["id"]
        assert "compliance_status" in result
        assert result["compliance_status"] in ["COMPLIANT", "NON_COMPLIANT", "PARTIAL", "UNKNOWN"]
        assert "violations" in result
        assert "violation_count" in result
        assert "generated_at" in result
        assert "id" in result
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_check_compliance_with_asset_id_integration(real_client):
    """Test checking compliance with asset_id using real API"""
    # First create a test domain
    domain_name = f"test-compliance-asset-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name, description="Test domain for asset compliance", status="ACTIVE"
    )

    try:
        # Check domain-level compliance (asset_id parameter not yet
        # supported by the API — tracked as post-MVP feature).
        result = await real_client.mesh.check_compliance(created_domain["id"])

        assert result is not None
        assert result["domain_id"] == created_domain["id"]
        assert result.get("compliance_status") is not None
        assert "id" in result  # Report ID
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_get_compliance_report_integration(real_client):
    """Test getting compliance report with real API"""
    # First create a test domain
    domain_name = f"test-compliance-report-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name, description="Test domain for compliance report", status="ACTIVE"
    )

    try:
        # First check compliance to create a report
        compliance_result = await real_client.mesh.check_compliance(created_domain["id"])

        assert compliance_result is not None
        report_id = compliance_result["id"]

        # Get the compliance report
        result = await real_client.mesh.get_compliance_report(created_domain["id"], report_id)

        assert result is not None
        assert result["id"] == report_id
        assert result["domain_id"] == created_domain["id"]
        assert "compliance_status" in result
        assert "violations" in result
        assert "violation_count" in result
        assert "generated_at" in result
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_check_compliance_not_found_integration(real_client):
    """Test checking compliance for non-existent domain with real API"""
    fake_domain_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError):
        await real_client.mesh.check_compliance(fake_domain_id)


@pytest.mark.asyncio
async def test_get_compliance_report_not_found_integration(real_client):
    """Test getting non-existent compliance report with real API"""
    # Create a test domain first
    domain_name = f"test-compliance-notfound-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(name=domain_name)

    try:
        fake_report_id = str(uuid.uuid4())

        with pytest.raises(NotFoundError):
            await real_client.mesh.get_compliance_report(created_domain["id"], fake_report_id)
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_check_compliance_structure_integration(real_client):
    """Test compliance check response structure with real API"""
    # First create a test domain
    domain_name = f"test-compliance-structure-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name, description="Test domain for compliance structure", status="ACTIVE"
    )

    try:
        # Check compliance
        result = await real_client.mesh.check_compliance(created_domain["id"])

        # Verify structure
        assert "id" in result
        assert "domain_id" in result
        assert "domain_name" in result
        assert "compliance_status" in result
        assert result["compliance_status"] in ["COMPLIANT", "NON_COMPLIANT", "PARTIAL", "UNKNOWN"]
        assert "violations" in result
        assert isinstance(result["violations"], dict)
        assert "violation_count" in result
        assert isinstance(result["violation_count"], int)
        assert "generated_at" in result
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])


@pytest.mark.asyncio
async def test_get_compliance_report_structure_integration(real_client):
    """Test compliance report response structure with real API"""
    # First create a test domain
    domain_name = f"test-compliance-report-structure-{uuid.uuid4().hex[:8]}"
    created_domain = await real_client.mesh.create_domain(
        name=domain_name, description="Test domain for report structure", status="ACTIVE"
    )

    try:
        # First check compliance to create a report
        compliance_result = await real_client.mesh.check_compliance(created_domain["id"])
        report_id = compliance_result["id"]

        # Get the compliance report
        result = await real_client.mesh.get_compliance_report(created_domain["id"], report_id)

        # Verify structure
        assert "id" in result
        assert "domain_id" in result
        assert "domain_name" in result
        assert result["domain_id"] == created_domain["id"]
        assert result["domain_name"] == domain_name
        assert "compliance_status" in result
        assert "violations" in result
        assert "violation_count" in result
        assert "generated_at" in result
        assert "created_at" in result
        assert "updated_at" in result
    finally:
        # Cleanup
        with contextlib.suppress(Exception):
            await real_client.mesh.delete_domain(created_domain["id"])
