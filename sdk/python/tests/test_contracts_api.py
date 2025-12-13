"""
Tests for Contracts API.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.contracts import ContractsAPI


@pytest.fixture
def client():
    """Create test client."""
    config = DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
    )
    return DataHubClient(config)


@pytest.fixture
def contracts_api(client):
    """Create Contracts API instance."""
    return ContractsAPI(client)


@pytest.mark.asyncio
async def test_list_contracts(contracts_api, client):
    """Test listing contracts."""
    expected_response = {
        "count": 100,
        "page": 1,
        "page_size": 50,
        "results": [{"id": "123", "status": "ACTIVE"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(page=1, page_size=50)

    assert result == expected_response
    client.get.assert_called_once_with("contracts/contracts/", params={"page": 1, "page_size": 50})


@pytest.mark.asyncio
async def test_list_contracts_with_filters(contracts_api, client):
    """Test listing contracts with filters."""
    expected_response = {"count": 10, "results": []}
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(
        owner_email="test@example.com",
        server_type="s3",
        min_availability=99.0,
    )

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/contracts/",
        params={
            "page": 1,
            "page_size": 50,
            "owner_email": "test@example.com",
            "server_type": "s3",
            "min_availability": 99.0,
        },
    )


@pytest.mark.asyncio
async def test_get_contract(contracts_api, client):
    """Test getting contract by ID."""
    expected_response = {"id": "123", "status": "ACTIVE"}
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.get("123")

    assert result == expected_response
    client.get.assert_called_once_with("contracts/contracts/123/")


@pytest.mark.asyncio
async def test_create_contract(contracts_api, client):
    """Test creating contract."""
    expected_response = {"id": "123", "status": "ACTIVE"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create(
        original_raw='{"apiVersion": "odcs/v3", "kind": "DataContract"}',
        original_format="JSON",
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/contracts/",
        data={
            "original_raw": '{"apiVersion": "odcs/v3", "kind": "DataContract"}',
            "original_format": "JSON",
        },
    )


@pytest.mark.asyncio
async def test_update_contract(contracts_api, client):
    """Test updating contract."""
    expected_response = {"id": "123", "status": "ACTIVE"}
    client.patch = AsyncMock(return_value=expected_response)

    result = await contracts_api.update("123", original_raw='{"updated": true}')

    assert result == expected_response
    client.patch.assert_called_once_with(
        "contracts/contracts/123/",
        data={"original_raw": '{"updated": true}'},
    )


@pytest.mark.asyncio
async def test_delete_contract(contracts_api, client):
    """Test deleting contract."""
    client.delete = AsyncMock(return_value=None)

    await contracts_api.delete("123")

    client.delete.assert_called_once_with("contracts/contracts/123/")


@pytest.mark.asyncio
async def test_validate_contract(contracts_api, client):
    """Test validating contract."""
    expected_response = {"validation_status": "VALID", "errors": []}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.validate("123")

    assert result == expected_response
    client.post.assert_called_once_with("contracts/contracts/123/validate/")


@pytest.mark.asyncio
async def test_lint_contract(contracts_api, client):
    """Test linting contract."""
    expected_response = {"lint_status": "OK", "issues": []}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.lint("123")

    assert result == expected_response
    client.post.assert_called_once_with("contracts/contracts/123/lint/")


def test_get_contact(contracts_api):
    """Test getting contact from contract."""
    contract = {
        "hub_contract_json": {
            "contact": [{"email": "test@example.com", "name": "Test"}],
        },
    }

    result = contracts_api.get_contact(contract)

    assert result == [{"email": "test@example.com", "name": "Test"}]


def test_get_servers(contracts_api):
    """Test getting servers from contract."""
    contract = {
        "hub_contract_json": {
            "servers": [{"type": "s3", "url": "s3://bucket"}],
        },
    }

    result = contracts_api.get_servers(contract)

    assert result == [{"type": "s3", "url": "s3://bucket"}]


def test_get_terms(contracts_api):
    """Test getting terms from contract."""
    contract = {
        "hub_contract_json": {
            "terms": {"usage": "Internal use only"},
        },
    }

    result = contracts_api.get_terms(contract)

    assert result == {"usage": "Internal use only"}


def test_get_definitions(contracts_api):
    """Test getting definitions from contract."""
    contract = {
        "hub_contract_json": {
            "definitions": [{"name": "def1", "type": "string"}],
        },
    }

    result = contracts_api.get_definitions(contract)

    assert result == [{"name": "def1", "type": "string"}]


def test_get_lineage(contracts_api):
    """Test getting lineage from contract."""
    contract = {
        "hub_contract_json": {
            "lineage": {"contracts": [{"namespace": "ns1", "name": "contract1"}]},
        },
    }

    result = contracts_api.get_lineage(contract)

    assert result == {"contracts": [{"namespace": "ns1", "name": "contract1"}]}


def test_get_servicelevels(contracts_api):
    """Test getting service levels from contract."""
    contract = {
        "hub_contract_json": {
            "servicelevels": [{"availability": 99.0}],
        },
    }

    result = contracts_api.get_servicelevels(contract)

    assert result == [{"availability": 99.0}]


def test_get_models(contracts_api):
    """Test getting models from contract."""
    contract = {
        "hub_contract_json": {
            "models": [{"name": "model1", "fields": []}],
        },
    }

    result = contracts_api.get_models(contract)

    assert result == [{"name": "model1", "fields": []}]
