"""
Tests for Lineage API.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.lineage import LineageAPI


@pytest.fixture
def client():
    """Create test client."""
    config = DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )
    return DataHubClient(config)


@pytest.fixture
def lineage_api(client):
    """Create Lineage API instance."""
    return LineageAPI(client)


@pytest.mark.asyncio
async def test_get_contract_lineage(lineage_api, client):
    """Test getting contract-level lineage."""
    expected_response = {"contracts": [{"namespace": "ns1", "name": "contract1"}]}
    client.get = AsyncMock(return_value=expected_response)
    
    result = await lineage_api.get_contract_lineage("123")
    
    assert result == expected_response
    client.get.assert_called_once_with("contracts/123/lineage/contracts/")


@pytest.mark.asyncio
async def test_get_model_lineage(lineage_api, client):
    """Test getting model-level lineage."""
    expected_response = {"model_name": "model1", "lineage": {}}
    client.get = AsyncMock(return_value=expected_response)
    
    result = await lineage_api.get_model_lineage("123", "model1")
    
    assert result == expected_response
    client.get.assert_called_once_with("contracts/123/models/model1/lineage/")


@pytest.mark.asyncio
async def test_get_field_lineage(lineage_api, client):
    """Test getting field-level lineage."""
    expected_response = {"field_name": "field1", "lineage": {}}
    client.get = AsyncMock(return_value=expected_response)
    
    result = await lineage_api.get_field_lineage("123", "model1", "field1")
    
    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/123/fields/field1/lineage/",
        params={"model_name": "model1"},
    )


@pytest.mark.asyncio
async def test_get_full_lineage(lineage_api, client):
    """Test getting full hierarchical lineage."""
    expected_response = {"upstream": {}, "downstream": {}}
    client.get = AsyncMock(return_value=expected_response)
    
    result = await lineage_api.get_full_lineage("123", max_contract_depth=5)
    
    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/123/lineage/full/",
        params={"max_contract_depth": 5, "max_model_depth": 10, "max_field_depth": 10},
    )


@pytest.mark.asyncio
async def test_get_visualization_json(lineage_api, client):
    """Test getting lineage visualization in JSON format."""
    expected_response = {"nodes": [], "edges": []}
    mock_response = MagicMock()
    mock_response.json.return_value = expected_response
    client.request = AsyncMock(return_value=mock_response)
    
    result = await lineage_api.get_visualization("123", format="json")
    
    assert result == expected_response
    client.request.assert_called_once_with(
        "GET",
        "contracts/123/lineage/visualization/",
        params={"format": "json"},
    )


@pytest.mark.asyncio
async def test_get_visualization_dot(lineage_api, client):
    """Test getting lineage visualization in DOT format."""
    expected_content = "digraph { ... }"
    mock_response = MagicMock()
    mock_response.text = expected_content
    client.request = AsyncMock(return_value=mock_response)
    
    result = await lineage_api.get_visualization("123", format="dot")
    
    assert result == {"format": "dot", "content": expected_content}


@pytest.mark.asyncio
async def test_get_impact_analysis(lineage_api, client):
    """Test getting impact analysis."""
    expected_response = {"impact_score": 0.8, "affected_assets": []}
    client.get = AsyncMock(return_value=expected_response)
    
    result = await lineage_api.get_impact_analysis("123", depth=5)
    
    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/123/impact-analysis/",
        params={"depth": 5, "include_fields": True},
    )

