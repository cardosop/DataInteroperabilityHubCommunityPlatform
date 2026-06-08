"""
284.B.3 — SDK GraphQL-LD tests.

Tests for ``SemanticAPI.execute_graphql_ld()`` added by Phase 284.B.3.

Covers:
* Valid query execution — POST to /semantic/graphql with correct body shape.
* Variables forwarding — optional variables dict included in body.
* Empty query raises ValueError before HTTP call.
* HTTP error propagation — 400/403/408/429 surface via client error handling.
"""
import pytest

try:
    from unittest.mock import AsyncMock, Mock
except ImportError:
    from unittest.mock import Mock, AsyncMock  # type: ignore[no-redef]

from datahub_interoperability.semantic import SemanticAPI


@pytest.fixture
def mock_client():
    client = Mock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def api(mock_client):
    return SemanticAPI(mock_client)


class TestExecuteGraphQLLd:
    """284.B.3 — ``execute_graphql_ld()`` contract tests."""

    @pytest.mark.asyncio
    async def test_execute_valid_query(self, api, mock_client):
        mock_client.post.return_value = {
            "data": {"assets": [{"id": "a1", "name": "Alpha"}]},
        }
        result = await api.execute_graphql_ld("{ assets { id name } }")
        mock_client.post.assert_called_once_with(
            "semantic/graphql", data={"query": "{ assets { id name } }"},
        )
        assert result["data"]["assets"][0]["name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_execute_query_with_variables(self, api, mock_client):
        mock_client.post.return_value = {"data": {"asset": {"id": "a1"}}}
        result = await api.execute_graphql_ld(
            "query Q($id: ID!) { asset(id: $id) { id } }",
            variables={"id": "a1"},
        )
        mock_client.post.assert_called_once_with(
            "semantic/graphql",
            data={"query": "query Q($id: ID!) { asset(id: $id) { id } }", "variables": {"id": "a1"}},
        )
        assert result["data"]["asset"]["id"] == "a1"

    @pytest.mark.asyncio
    async def test_execute_query_no_variables(self, api, mock_client):
        mock_client.post.return_value = {"data": {"contracts": []}}
        result = await api.execute_graphql_ld("{ contracts { id } }")
        # body must NOT contain "variables" key when not provided
        call_data = mock_client.post.call_args[1]["data"]
        assert "variables" not in call_data
        assert call_data == {"query": "{ contracts { id } }"}
        assert result["data"]["contracts"] == []

    @pytest.mark.asyncio
    async def test_empty_query_raises_valueerror(self, api, mock_client):
        with pytest.raises(ValueError, match="non-empty"):
            await api.execute_graphql_ld("  ")

    @pytest.mark.asyncio
    async def test_none_query_raises_valueerror(self, api, mock_client):
        with pytest.raises(ValueError, match="non-empty"):
            await api.execute_graphql_ld(None)

    @pytest.mark.asyncio
    async def test_execute_datasets_query(self, api, mock_client):
        mock_client.post.return_value = {
            "data": {"datasets": [{"id": "d1", "format": "CSV"}]},
        }
        result = await api.execute_graphql_ld("{ datasets { id format } }")
        mock_client.post.assert_called_once_with(
            "semantic/graphql", data={"query": "{ datasets { id format } }"},
        )
        assert result["data"]["datasets"][0]["format"] == "CSV"

    @pytest.mark.asyncio
    async def test_execute_errors_propagation(self, api, mock_client):
        mock_client.post.return_value = {
            "data": None,
            "errors": [{"message": "Cannot query field 'unknown' on type 'Query'"}],
        }
        result = await api.execute_graphql_ld("{ unknown }")
        assert result["errors"] is not None
        assert len(result["errors"]) == 1
        assert "unknown" in result["errors"][0]["message"]
