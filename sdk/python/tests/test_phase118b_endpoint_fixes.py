"""
Phase 118B — Python SDK Endpoint & Method Fixes (GF-22.8–22.13)

TDD tests verifying SDK methods send correct endpoint paths and parameters
to match the backend ViewSet implementations.
"""
import pytest
from unittest.mock import AsyncMock, Mock

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig


@pytest.fixture
def client():
    """Create test client with mocked HTTP."""
    config = DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )
    return DataHubClient(config)


# ---------------------------------------------------------------------------
# 118B.1 — client.py auth header: X-API-Key is accepted by backend
# ---------------------------------------------------------------------------
class TestClientAuthHeader:
    """Verify SDK auth header format matches backend middleware."""

    @pytest.mark.asyncio
    async def test_api_key_uses_x_api_key_header(self, client):
        """API key (no dots) should use X-API-Key header."""
        client.config = DataHubClientConfig(
            base_url="https://api.example.com/api/v1",
            api_token="sk_test_abc123def456",  # No dots = API key
        )
        headers = await client._get_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "sk_test_abc123def456"

    @pytest.mark.asyncio
    async def test_jwt_uses_bearer_header(self, client):
        """JWT (has dots) should use Authorization: Bearer header."""
        client.config = DataHubClientConfig(
            base_url="https://api.example.com/api/v1",
            api_token="eyJ.payload.signature",  # Has dots = JWT
        )
        headers = await client._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer eyJ.payload.signature"


# ---------------------------------------------------------------------------
# 118B.2 + 118B.3 — contracts.py: export() and download() methods
# ---------------------------------------------------------------------------
class TestContractsExportDownload:
    """Verify contracts export/download methods exist and hit correct endpoints."""

    @pytest.mark.asyncio
    async def test_export_method_exists_and_calls_correct_endpoint(self, client):
        """contracts.export() must GET contracts/{id}/export/."""
        from datahub_interoperability.contracts import ContractsAPI
        api = ContractsAPI(client)
        client.get = AsyncMock(return_value={"format": "hubcontract", "content": {}})

        result = await api.export("contract-1")

        client.get.assert_called_once()
        call_args = client.get.call_args
        assert call_args[0][0] == "contracts/contract-1/export/"

    @pytest.mark.asyncio
    async def test_export_with_format_param(self, client):
        """contracts.export() must pass format as query param."""
        from datahub_interoperability.contracts import ContractsAPI
        api = ContractsAPI(client)
        client.get = AsyncMock(return_value={"format": "odps", "content": {}})

        await api.export("contract-1", format="odps")

        call_args = client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("format") == "odps"

    @pytest.mark.asyncio
    async def test_download_method_exists_and_calls_correct_endpoint(self, client):
        """contracts.download() must GET contracts/{id}/download/."""
        from datahub_interoperability.contracts import ContractsAPI
        api = ContractsAPI(client)
        client.get = AsyncMock(return_value={"content": "yaml data"})

        result = await api.download("contract-1")

        client.get.assert_called_once()
        call_args = client.get.call_args
        assert call_args[0][0] == "contracts/contract-1/download/"

    @pytest.mark.asyncio
    async def test_download_with_format_param(self, client):
        """contracts.download() must pass format as query param."""
        from datahub_interoperability.contracts import ContractsAPI
        api = ContractsAPI(client)
        client.get = AsyncMock(return_value={"content": "yaml"})

        await api.download("contract-1", format="odcs")

        call_args = client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("format") == "odcs"


# ---------------------------------------------------------------------------
# 118B.4 — contracts.py list(): spec_version parameter
# ---------------------------------------------------------------------------
class TestContractsListSpecVersion:
    """Verify contracts.list() accepts spec_version parameter."""

    @pytest.mark.asyncio
    async def test_list_sends_spec_version_param(self, client):
        """contracts.list(spec_version='4.1') must send spec_version param."""
        from datahub_interoperability.contracts import ContractsAPI
        api = ContractsAPI(client)
        client.get = AsyncMock(return_value={"results": [], "count": 0})

        await api.list(spec_version="4.1")

        call_args = client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert params.get("spec_version") == "4.1"


# ---------------------------------------------------------------------------
# 118B.5 — lineage.py: field lineage must pass model_name as query param
# ---------------------------------------------------------------------------
class TestLineageFieldModelName:
    """Verify field lineage passes model_name as query param."""

    @pytest.mark.asyncio
    async def test_field_lineage_passes_model_name_as_param(self, client):
        """get_field_lineage() must pass model_name as query param."""
        from datahub_interoperability.lineage import LineageAPI
        api = LineageAPI(client)
        client.get = AsyncMock(return_value={"lineage": {"input_fields": []}})

        await api.get_field_lineage("c1", "model1", "field1")

        call_args = client.get.call_args
        url = call_args[0][0]
        assert url == "contracts/c1/fields/field1/lineage/"
        params = call_args[1].get("params", {})
        assert params.get("model_name") == "model1"

    @pytest.mark.asyncio
    async def test_field_lineage_url_has_no_model_name_segment(self, client):
        """Field lineage URL must NOT contain model_name as a path segment."""
        from datahub_interoperability.lineage import LineageAPI
        api = LineageAPI(client)
        client.get = AsyncMock(return_value={"lineage": {}})

        await api.get_field_lineage("c1", "mymodel", "myfield")

        url = client.get.call_args[0][0]
        assert "mymodel" not in url, f"model_name should not be in URL path: {url}"


# ---------------------------------------------------------------------------
# 118B.6 — governance.py: classification endpoints
# Backend has NO /assets/{id}/classification/ or /assets/{id}/classify/ endpoints.
# These methods should note they target asset-level paths (outside governance scope).
# No governance-level classification endpoints exist either.
# ---------------------------------------------------------------------------
class TestGovernanceClassification:
    """Verify governance classification methods use correct endpoint pattern."""

    @pytest.mark.asyncio
    async def test_governance_endpoints_use_governance_prefix(self, client):
        """Governance access-request/retention-policy use governance/ prefix."""
        from datahub_interoperability.governance import GovernanceAPI
        api = GovernanceAPI(client)
        client.get = AsyncMock(return_value={"results": []})

        await api.get_retention_policies()
        url = client.get.call_args[0][0]
        assert url.startswith("governance/"), f"Expected governance/ prefix, got: {url}"

    @pytest.mark.asyncio
    async def test_access_request_uses_governance_prefix(self, client):
        """Access request endpoints use governance/ prefix."""
        from datahub_interoperability.governance import GovernanceAPI
        api = GovernanceAPI(client)
        client.post = AsyncMock(return_value={"id": "req-1", "status": "PENDING"})

        await api.create_access_request("asset-1", "Need access")
        url = client.post.call_args[0][0]
        assert url == "governance/access-requests/"


# ---------------------------------------------------------------------------
# 118B.7 — search.py: fix doubled search/search/ paths
# Backend: search/ (api/urls.py) + router at "" + actions (search, suggestions, analytics)
# Correct: search/search/, search/suggestions/, search/analytics/
# ---------------------------------------------------------------------------
class TestSearchEndpoints:
    """Verify search endpoints use correct paths."""

    @pytest.mark.asyncio
    async def test_search_uses_correct_path(self, client):
        """search() must hit search/search/ (action name is 'search')."""
        from datahub_interoperability.search import SearchAPI
        api = SearchAPI(client)
        client.get = AsyncMock(return_value={"results": []})

        await api.search("test query")

        url = client.get.call_args[0][0]
        assert url == "search/search/", f"Expected 'search/search/', got: {url}"

    @pytest.mark.asyncio
    async def test_suggestions_uses_correct_path(self, client):
        """get_suggestions() must hit search/suggestions/ NOT search/search/suggestions/."""
        from datahub_interoperability.search import SearchAPI
        api = SearchAPI(client)
        client.get = AsyncMock(return_value={"suggestions": []})

        await api.get_suggestions("test")

        url = client.get.call_args[0][0]
        assert url == "search/suggestions/", f"Expected 'search/suggestions/', got: {url}"

    @pytest.mark.asyncio
    async def test_analytics_uses_correct_path(self, client):
        """get_analytics() must hit search/analytics/ NOT search/search/analytics/."""
        from datahub_interoperability.search import SearchAPI
        api = SearchAPI(client)
        client.get = AsyncMock(return_value={"analytics": {}})

        await api.get_analytics()

        url = client.get.call_args[0][0]
        assert url == "search/analytics/", f"Expected 'search/analytics/', got: {url}"


# ---------------------------------------------------------------------------
# 118B.8 — mesh.py: verified correct (no fix needed)
# ---------------------------------------------------------------------------
class TestMeshEndpointsCorrect:
    """Verify mesh endpoints are correct."""

    @pytest.mark.asyncio
    async def test_apply_policy_endpoint(self, client):
        """apply_policy() must hit mesh/domains/{id}/policies/apply/."""
        from datahub_interoperability.mesh import MeshAPI
        api = MeshAPI(client)
        client.post = AsyncMock(return_value={"id": "p1", "status": "APPLIED"})

        await api.apply_policy("d1", "policy-1")

        url = client.post.call_args[0][0]
        assert url == "mesh/domains/d1/policies/apply/"

    @pytest.mark.asyncio
    async def test_check_compliance_endpoint(self, client):
        """check_compliance() must hit mesh/domains/{id}/compliance/check/."""
        from datahub_interoperability.mesh import MeshAPI
        api = MeshAPI(client)
        client.post = AsyncMock(return_value={"compliance_status": "COMPLIANT"})

        await api.check_compliance("d1")

        url = client.post.call_args[0][0]
        assert url == "mesh/domains/d1/compliance/check/"


# ---------------------------------------------------------------------------
# 118B.9 — observability.py: fix doubled observability/observability/ paths
# Backend: api/urls.py includes at root "" + router registers at "observability"
# Correct: observability/freshness/, NOT observability/observability/freshness/
# ---------------------------------------------------------------------------
class TestObservabilityEndpoints:
    """Verify observability endpoints use correct paths (no doubling)."""

    @pytest.mark.asyncio
    async def test_freshness_uses_correct_path(self, client):
        """get_freshness() must hit observability/freshness/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"metrics": []})

        await api.get_freshness()

        url = client.get.call_args[0][0]
        assert url == "observability/freshness/", f"Expected 'observability/freshness/', got: {url}"

    @pytest.mark.asyncio
    async def test_volume_uses_correct_path(self, client):
        """get_volume() must hit observability/volume/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"metrics": []})

        await api.get_volume()

        url = client.get.call_args[0][0]
        assert url == "observability/volume/"

    @pytest.mark.asyncio
    async def test_schema_drift_uses_correct_path(self, client):
        """get_schema_drift() must hit observability/schema-drift/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"drifts": []})

        await api.get_schema_drift()

        url = client.get.call_args[0][0]
        assert url == "observability/schema-drift/"

    @pytest.mark.asyncio
    async def test_pipelines_uses_correct_path(self, client):
        """get_pipelines() must hit observability/pipelines/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"pipelines": []})

        await api.get_pipelines()

        url = client.get.call_args[0][0]
        assert url == "observability/pipelines/"

    @pytest.mark.asyncio
    async def test_slas_uses_correct_path(self, client):
        """get_slas() must hit observability/slas/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"slas": []})

        await api.get_slas()

        url = client.get.call_args[0][0]
        assert url == "observability/slas/"

    @pytest.mark.asyncio
    async def test_incidents_uses_correct_path(self, client):
        """list_incidents() must hit observability/incidents/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.get = AsyncMock(return_value={"results": []})

        await api.list_incidents()

        url = client.get.call_args[0][0]
        assert url == "observability/incidents/"

    @pytest.mark.asyncio
    async def test_create_incident_uses_correct_path(self, client):
        """create_incident() must POST to observability/incidents/."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.post = AsyncMock(return_value={"id": "inc-1"})

        await api.create_incident("ds-1", "HIGH", "Data freshness SLA breach")

        url = client.post.call_args[0][0]
        assert url == "observability/incidents/"

    @pytest.mark.asyncio
    async def test_update_incident_uses_correct_path_and_data(self, client):
        """update_incident() must PATCH to observability/incidents/update/ with incident_id in body."""
        from datahub_interoperability.observability import ObservabilityAPI
        api = ObservabilityAPI(client)
        client.patch = AsyncMock(return_value={"id": "inc-1", "status": "RESOLVED"})

        await api.update_incident("inc-1", status="RESOLVED")

        call_args = client.patch.call_args
        url = call_args[0][0]
        assert url == "observability/incidents/update/", (
            f"Expected 'observability/incidents/update/', got: {url}"
        )
        data = call_args[1].get("data", {})
        assert data.get("incident_id") == "inc-1"
        assert data.get("status") == "RESOLVED"


# ---------------------------------------------------------------------------
# 118B.10 — versioning.py: verify endpoint paths and compare params
# Backend datasets app has: datasets/{id}/versions/, datasets/{id}/versions/compare
# Compare uses query params: version1, version2 (not version1_id, version2_id)
# ---------------------------------------------------------------------------
class TestVersioningEndpoints:
    """Verify versioning endpoint paths and parameters."""

    @pytest.mark.asyncio
    async def test_version_history_path(self, client):
        """get_version_history() must hit datasets/{id}/versions/."""
        from datahub_interoperability.versioning import VersioningAPI
        api = VersioningAPI(client)
        client.get = AsyncMock(return_value={"results": []})

        await api.get_version_history("ds-1")

        url = client.get.call_args[0][0]
        assert url == "datasets/ds-1/versions/"

    @pytest.mark.asyncio
    async def test_compare_versions_uses_correct_params(self, client):
        """compare_versions() must send version1/version2 params (not version1_id)."""
        from datahub_interoperability.versioning import VersioningAPI
        api = VersioningAPI(client)
        client.get = AsyncMock(return_value={"diff": {}})

        await api.compare_versions("ds-1", "v1-uuid", "v2-uuid")

        call_args = client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        # Backend expects 'version1' and 'version2', NOT 'version1_id' and 'version2_id'
        assert "version1" in params, f"Expected 'version1' in params, got: {params}"
        assert "version2" in params, f"Expected 'version2' in params, got: {params}"
        assert params["version1"] == "v1-uuid"
        assert params["version2"] == "v2-uuid"

    @pytest.mark.asyncio
    async def test_compare_versions_endpoint_path(self, client):
        """compare_versions() must hit datasets/{id}/versions/compare/."""
        from datahub_interoperability.versioning import VersioningAPI
        api = VersioningAPI(client)
        client.get = AsyncMock(return_value={"diff": {}})

        await api.compare_versions("ds-1", "v1", "v2")

        url = client.get.call_args[0][0]
        assert url == "datasets/ds-1/versions/compare/", f"Expected 'datasets/ds-1/versions/compare/', got: {url}"
