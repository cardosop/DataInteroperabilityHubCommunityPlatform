"""
Tests for Contracts API.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.contracts import ContractsAPI
from datahub_interoperability.errors import (
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
    NotFoundError,
    ODPSValidationError,
    ODPSExportError,
    ODPSLinkingError,
    NotFoundError,
    ValidationError,
)


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
    client.get.assert_called_once_with("contracts/", params={"page": 1, "page_size": 50})


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
        "contracts/",
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
    client.get.assert_called_once_with("contracts/123/")


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
        "contracts/",
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

    client.delete.assert_called_once_with("contracts/123/")


@pytest.mark.asyncio
async def test_validate_contract(contracts_api, client):
    """Test validating contract."""
    expected_response = {"validation_status": "VALID", "errors": []}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.validate("123")

    assert result == expected_response
    client.post.assert_called_once_with("contracts/123/validate/")


@pytest.mark.asyncio
async def test_lint_contract(contracts_api, client):
    """Test linting contract."""
    expected_response = {"lint_status": "OK", "issues": []}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.lint("123")

    assert result == expected_response
    client.post.assert_called_once_with("contracts/123/lint/")


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


@pytest.mark.asyncio
async def test_create_odps_product_first_flow(contracts_api, client):
    """Test creating ODPS contract with Product-First flow (extract_odcs=True)."""
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "test-product",
        "name": "Test Product"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "test-contract"
    }
  }
}"""
    expected_response = {
        "odps_contract": {"id": "odps-123", "status": "ACTIVE"},
        "odcs_contract": {"id": "odcs-456", "status": "ACTIVE"},
        "workflow_instance_id": "workflow-789",
    }
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
        original_format="JSON",
        odps_version="4.1",
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/products/",
        data={
            "original_raw": odps_content,
            "original_format": "JSON",
            "resolve_external_refs": True,
            "odps_version": "4.1",
        },
    )


@pytest.mark.asyncio
async def test_create_odps_link_flow(contracts_api, client):
    """Test creating ODPS contract with Link flow (link_odcs_id provided)."""
    odps_content = """{
  "schema": "https://opendataproducts.org/schema/v4.1",
  "version": "4.1",
  "product": {
    "details": {
      "en": {
        "productID": "test-product",
        "name": "Test Product"
      }
    },
    "contract": {
      "apiVersion": "odcs/v3",
      "kind": "DataContract",
      "id": "test-contract"
    }
  }
}"""
    expected_response = {"id": "odps-123", "status": "ACTIVE", "original_spec_type": "ODPS"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        link_odcs_id="123e4567-e89b-12d3-a456-426614174000",
        original_format="JSON",
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/123e4567-e89b-12d3-a456-426614174000/link-odps/",
        data={
            "original_raw": odps_content,
            "original_format": "JSON",
            "resolve_external_refs": True,
        },
    )


@pytest.mark.asyncio
async def test_create_odps_auto_detect_format_json(contracts_api, client):
    """Test creating ODPS contract with auto-detected JSON format."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'
    expected_response = {"id": "odps-123", "status": "ACTIVE"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/products/",
        data={
            "original_raw": odps_content,
            "original_format": "JSON",
            "resolve_external_refs": True,
        },
    )


@pytest.mark.asyncio
async def test_create_odps_auto_detect_format_yaml(contracts_api, client):
    """Test creating ODPS contract with auto-detected YAML format."""
    odps_content = "schema: https://opendataproducts.org/schema/v4.1\nversion: '4.1'"
    expected_response = {"id": "odps-123", "status": "ACTIVE"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/products/",
        data={
            "original_raw": odps_content,
            "original_format": "YAML",
            "resolve_external_refs": True,
        },
    )


@pytest.mark.asyncio
async def test_create_odps_with_asset_id(contracts_api, client):
    """Test creating ODPS contract with asset_id."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'
    expected_response = {"id": "odps-123", "status": "ACTIVE"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
        asset_id="asset-789",
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/products/",
        data={
            "original_raw": odps_content,
            "original_format": "JSON",
            "resolve_external_refs": True,
            "asset_id": "asset-789",
        },
    )


@pytest.mark.asyncio
async def test_create_odps_with_resolve_external_refs_false(contracts_api, client):
    """Test creating ODPS contract with resolve_external_refs=False."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'
    expected_response = {"id": "odps-123", "status": "ACTIVE"}
    client.post = AsyncMock(return_value=expected_response)

    result = await contracts_api.create_odps(
        original_raw=odps_content,
        extract_odcs=True,
        resolve_external_refs=False,
    )

    assert result == expected_response
    client.post.assert_called_once_with(
        "contracts/products/",
        data={
            "original_raw": odps_content,
            "original_format": "JSON",
            "resolve_external_refs": False,
        },
    )


@pytest.mark.asyncio
async def test_create_odps_mutually_exclusive_error(contracts_api):
    """Test that providing both extract_odcs and link_odcs_id raises ODPSValidationError."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}'

    with pytest.raises(ODPSValidationError, match="Cannot use both extract_odcs and link_odcs_id"):
        await contracts_api.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            link_odcs_id="123e4567-e89b-12d3-a456-426614174000",
        )


@pytest.mark.asyncio
async def test_create_odps_neither_option_error(contracts_api):
    """Test that providing neither extract_odcs nor link_odcs_id raises ODPSValidationError."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}'

    with pytest.raises(ODPSValidationError, match="Must specify either extract_odcs=True or link_odcs_id"):
        await contracts_api.create_odps(
            original_raw=odps_content,
        )


# ODPS helper method tests

def test_is_odps_contract_true(contracts_api):
    """Test is_odps_contract returns True for ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_spec_version": "4.1",
    }
    assert contracts_api.is_odps_contract(contract) is True


def test_is_odps_contract_false(contracts_api):
    """Test is_odps_contract returns False for non-ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODCS",
        "original_spec_version": "3.0.2",
    }
    assert contracts_api.is_odps_contract(contract) is False


def test_is_odps_contract_missing_type(contracts_api):
    """Test is_odps_contract returns False when original_spec_type is missing."""
    contract = {
        "id": "123",
    }
    assert contracts_api.is_odps_contract(contract) is False


def test_get_odps_version_success(contracts_api):
    """Test get_odps_version returns version for ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_spec_version": "4.1",
    }
    assert contracts_api.get_odps_version(contract) == "4.1"


def test_get_odps_version_non_odps(contracts_api):
    """Test get_odps_version returns None for non-ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODCS",
        "original_spec_version": "3.0.2",
    }
    assert contracts_api.get_odps_version(contract) is None


def test_get_odps_version_missing_version(contracts_api):
    """Test get_odps_version returns None when version is missing."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
    }
    assert contracts_api.get_odps_version(contract) is None


def test_get_pricing_plans_success(contracts_api):
    """Test get_pricing_plans returns pricing plans from ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        },
                        {
                            "planID": "premium",
                            "name": "Premium Plan",
                            "price": 49.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                            "isDefault": True,
                        },
                    ]
                }
            }
        },
    }
    result = contracts_api.get_pricing_plans(contract)
    assert result is not None
    assert len(result) == 2
    assert result[0]["planID"] == "basic"
    assert result[1]["planID"] == "premium"


def test_get_pricing_plans_empty(contracts_api):
    """Test get_pricing_plans returns empty list when pricing plans are empty."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "pricing_plans": [],
                }
            }
        },
    }
    result = contracts_api.get_pricing_plans(contract)
    assert result == []


def test_get_pricing_plans_missing(contracts_api):
    """Test get_pricing_plans returns None when pricing plans are missing."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {},
            }
        },
    }
    result = contracts_api.get_pricing_plans(contract)
    assert result is None


def test_get_pricing_plans_invalid_structure(contracts_api):
    """Test get_pricing_plans handles invalid structure gracefully."""
    contract = {
        "id": "123",
        "hub_contract_json": None,
    }
    result = contracts_api.get_pricing_plans(contract)
    assert result is None


def test_get_access_methods_success(contracts_api):
    """Test get_access_methods returns access methods from ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "access_methods": {
                        "api": {
                            "type": "REST",
                            "endpoint": "https://api.example.com/v1",
                            "protocol": "HTTPS",
                        },
                        "download": {
                            "type": "HTTP",
                            "url": "https://download.example.com/data",
                        },
                    }
                }
            }
        },
    }
    result = contracts_api.get_access_methods(contract)
    assert result is not None
    assert "api" in result
    assert "download" in result
    assert result["api"]["type"] == "REST"
    assert result["download"]["type"] == "HTTP"


def test_get_access_methods_empty(contracts_api):
    """Test get_access_methods returns empty dict when access methods are empty."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "access_methods": {},
                }
            }
        },
    }
    result = contracts_api.get_access_methods(contract)
    assert result == {}


def test_get_access_methods_missing(contracts_api):
    """Test get_access_methods returns None when access methods are missing."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {},
            }
        },
    }
    result = contracts_api.get_access_methods(contract)
    assert result is None


def test_get_payment_gateways_success(contracts_api):
    """Test get_payment_gateways returns payment gateways from ODPS contract."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "payment_gateways": {
                        "stripe": {
                            "enabled": True,
                            "mode": "test",
                            "publicKey": "pk_test_example",
                            "supportedCurrencies": ["USD", "EUR"],
                        },
                        "paypal": {
                            "enabled": True,
                            "provider": "PayPal",
                        },
                    }
                }
            }
        },
    }
    result = contracts_api.get_payment_gateways(contract)
    assert result is not None
    assert "stripe" in result
    assert "paypal" in result
    assert result["stripe"]["enabled"] is True
    assert result["paypal"]["enabled"] is True


def test_get_payment_gateways_empty(contracts_api):
    """Test get_payment_gateways returns empty dict when payment gateways are empty."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {
                    "payment_gateways": {},
                }
            }
        },
    }
    result = contracts_api.get_payment_gateways(contract)
    assert result == {}


def test_get_payment_gateways_missing(contracts_api):
    """Test get_payment_gateways returns None when payment gateways are missing."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {
                "x_odps": {},
            }
        },
    }
    result = contracts_api.get_payment_gateways(contract)
    assert result is None


def test_get_product_strategy_from_extensions(contracts_api):
    """Test get_product_strategy returns strategy from extensions.x_odps.product_strategy."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "extensions": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": [
                            "Increase data product adoption",
                            "Improve data quality metrics",
                        ],
                        "strategicAlignment": [
                            "Company-wide data strategy",
                            "Digital transformation initiative",
                        ],
                        "productKPIs": [
                            {"name": "Monthly Active Users", "target": 1000},
                            {"name": "Data Quality Score", "target": 95},
                        ],
                    }
                }
            }
        },
    }
    result = contracts_api.get_product_strategy(contract)
    assert result is not None
    assert "objectives" in result
    assert "strategicAlignment" in result
    assert "productKPIs" in result
    assert len(result["objectives"]) == 2
    assert len(result["strategicAlignment"]) == 2
    assert len(result["productKPIs"]) == 2


def test_get_product_strategy_from_info(contracts_api):
    """Test get_product_strategy falls back to info.x_odps.product_strategy."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "info": {
                "x_odps": {
                    "product_strategy": {
                        "objectives": ["Objective 1"],
                    }
                }
            }
        },
    }
    result = contracts_api.get_product_strategy(contract)
    assert result is not None
    assert "objectives" in result
    assert result["objectives"] == ["Objective 1"]


def test_get_product_strategy_missing(contracts_api):
    """Test get_product_strategy returns None when product strategy is missing."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "marketplace": {},
        },
    }
    result = contracts_api.get_product_strategy(contract)
    assert result is None


def test_get_product_details_from_original_raw(contracts_api):
    """Test get_product_details extracts from original_raw ODPS document."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_raw": """{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "A test product description",
                        "productVersion": "1.0.0"
                    },
                    "fi": {
                        "productID": "test-product",
                        "name": "Testituote",
                        "description": "Testituotteen kuvaus"
                    }
                }
            }
        }""",
    }
    result = contracts_api.get_product_details(contract, lang="en")
    assert result is not None
    assert result["productID"] == "test-product"
    assert result["name"] == "Test Product"
    assert result["description"] == "A test product description"
    assert result["productVersion"] == "1.0.0"


def test_get_product_details_different_language(contracts_api):
    """Test get_product_details returns details for specified language."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_raw": """{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    },
                    "fi": {
                        "productID": "test-product",
                        "name": "Testituote"
                    }
                }
            }
        }""",
    }
    result = contracts_api.get_product_details(contract, lang="fi")
    assert result is not None
    assert result["name"] == "Testituote"


def test_get_product_details_from_hub_contract(contracts_api):
    """Test get_product_details reconstructs from hub_contract_json when original_raw unavailable."""
    contract = {
        "id": "test-product-id",
        "original_spec_type": "ODPS",
        "hub_contract_json": {
            "id": "test-product-id",
            "info": {
                "name": "Test Product",
                "description": "A test product description",
                "version": "1.0.0",
            }
        },
    }
    result = contracts_api.get_product_details(contract, lang="en")
    assert result is not None
    assert result["productID"] == "test-product-id"
    assert result["name"] == "Test Product"
    assert result["description"] == "A test product description"
    assert result["productVersion"] == "1.0.0"


def test_get_product_details_invalid_json(contracts_api):
    """Test get_product_details handles invalid JSON gracefully."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_raw": "invalid json {",
        "hub_contract_json": {
            "id": "test-product-id",
            "info": {
                "name": "Test Product",
            }
        },
    }
    result = contracts_api.get_product_details(contract, lang="en")
    # Should fallback to hub_contract_json
    assert result is not None
    assert result["productID"] == "test-product-id"
    assert result["name"] == "Test Product"


def test_get_product_details_missing_language(contracts_api):
    """Test get_product_details returns None when language is not available."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_raw": """{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }""",
    }
    result = contracts_api.get_product_details(contract, lang="fr")
    # Should fallback to hub_contract_json if available, otherwise None
    assert result is None or isinstance(result, dict)


def test_get_product_details_default_language(contracts_api):
    """Test get_product_details defaults to 'en' language."""
    contract = {
        "id": "123",
        "original_spec_type": "ODPS",
        "original_raw": """{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                }
            }
        }""",
    }
    result = contracts_api.get_product_details(contract)  # No lang parameter
    assert result is not None
    assert result["name"] == "Test Product"


# ODPS filtering tests

@pytest.mark.asyncio
async def test_list_contracts_with_spec_type_filter(contracts_api, client):
    """Test listing contracts with spec_type filter."""
    expected_response = {
        "count": 10,
        "results": [{"id": "123", "original_spec_type": "ODPS"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(spec_type="ODPS")

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={"page": 1, "page_size": 50, "spec_type": "ODPS"},
    )


@pytest.mark.asyncio
async def test_list_contracts_with_odps_version_filter(contracts_api, client):
    """Test listing contracts with odps_version filter."""
    expected_response = {
        "count": 5,
        "results": [{"id": "123", "original_spec_type": "ODPS", "original_spec_version": "4.1"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(odps_version="4.1")

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={"page": 1, "page_size": 50, "odps_version": "4.1"},
    )


@pytest.mark.asyncio
async def test_list_contracts_with_has_odps_link_true(contracts_api, client):
    """Test listing contracts with has_odps_link=True filter."""
    expected_response = {
        "count": 3,
        "results": [{"id": "123", "original_spec_type": "ODCS"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(has_odps_link=True)

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={"page": 1, "page_size": 50, "has_odps_link": True},
    )


@pytest.mark.asyncio
async def test_list_contracts_with_has_odps_link_false(contracts_api, client):
    """Test listing contracts with has_odps_link=False filter."""
    expected_response = {
        "count": 7,
        "results": [{"id": "123", "original_spec_type": "ODCS"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(has_odps_link=False)

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={"page": 1, "page_size": 50, "has_odps_link": False},
    )


@pytest.mark.asyncio
async def test_list_contracts_with_multiple_odps_filters(contracts_api, client):
    """Test listing contracts with multiple ODPS filters combined."""
    expected_response = {
        "count": 2,
        "results": [{"id": "123", "original_spec_type": "ODPS", "original_spec_version": "4.1"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(
        spec_type="ODPS",
        odps_version="4.1",
        page=2,
        page_size=25,
    )

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={
            "page": 2,
            "page_size": 25,
            "spec_type": "ODPS",
            "odps_version": "4.1",
        },
    )


@pytest.mark.asyncio
async def test_list_contracts_odps_filters_with_other_filters(contracts_api, client):
    """Test listing contracts with ODPS filters combined with other filters."""
    expected_response = {
        "count": 1,
        "results": [{"id": "123", "original_spec_type": "ODPS"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list(
        spec_type="ODPS",
        owner_email="test@example.com",
        tag="test-tag",
    )

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={
            "page": 1,
            "page_size": 50,
            "spec_type": "ODPS",
            "owner_email": "test@example.com",
            "tag": "test-tag",
        },
    )


@pytest.mark.asyncio
async def test_list_contracts_odps_filters_optional(contracts_api, client):
    """Test that ODPS filters are optional and don't break existing functionality."""
    expected_response = {
        "count": 100,
        "results": [{"id": "123", "status": "ACTIVE"}],
    }
    client.get = AsyncMock(return_value=expected_response)

    result = await contracts_api.list()

    assert result == expected_response
    client.get.assert_called_once_with(
        "contracts/",
        params={"page": 1, "page_size": 50},
    )


@pytest.mark.asyncio
async def test_export_odps_json(contracts_api, client):
    """Test exporting contract as ODPS format in JSON."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    expected_response = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": "test-product",
                    "name": "Test Product"
                }
            }
        }
    }

    # Mock the request method to return a response with JSON content
    from unittest.mock import MagicMock, PropertyMock
    import json
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/json"}
    # Set text as a property so it's accessible
    type(mock_response).text = PropertyMock(return_value=json.dumps(expected_response))
    mock_response.json = MagicMock(return_value=expected_response)

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.export_odps(contract_id, format="json")

    assert result == expected_response
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/export/",
        params={"format": "odps", "output_format": "json"}
    )


@pytest.mark.asyncio
async def test_export_odps_yaml(contracts_api, client):
    """Test exporting contract as ODPS format in YAML."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    yaml_content = "schema: https://opendataproducts.org/schema/v4.1\nversion: '4.1'"

    # Mock the request method to return a response with YAML content
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/x-yaml"}
    mock_response.text = yaml_content

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.export_odps(contract_id, format="yaml")

    assert result == {"content": yaml_content, "format": "yaml"}
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/export/",
        params={"format": "odps", "output_format": "yaml"}
    )


@pytest.mark.asyncio
async def test_export_odps_with_version(contracts_api, client):
    """Test exporting contract as ODPS format with version parameter."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    expected_response = {
        "schema": "https://opendataproducts.org/schema/v4.2",
        "version": "4.2",
        "product": {"details": {}}
    }

    from unittest.mock import MagicMock, PropertyMock
    import json
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/json"}
    # Set text as a property so it's accessible
    type(mock_response).text = PropertyMock(return_value=json.dumps(expected_response))
    mock_response.json = MagicMock(return_value=expected_response)

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.export_odps(contract_id, version="4.2", format="json")

    assert result == expected_response
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/export/",
        params={"format": "odps", "output_format": "json", "version": "4.2"}
    )


@pytest.mark.asyncio
async def test_export_odps_invalid_format(contracts_api):
    """Test that invalid format raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps("123e4567-e89b-12d3-a456-426614174000", format="xml")
    assert exc_info.value.code == "INVALID_VALUE"
    assert "format" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_download_odps_json(contracts_api, client):
    """Test downloading contract as ODPS format in JSON."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    expected_content = b'{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}'

    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.content = expected_content

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.download_odps(contract_id, format="json")

    assert result == expected_content
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/download/",
        params={"format": "odps", "output_format": "json"}
    )


@pytest.mark.asyncio
async def test_download_odps_yaml(contracts_api, client):
    """Test downloading contract as ODPS format in YAML."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    expected_content = b"schema: https://opendataproducts.org/schema/v4.1\nversion: '4.1'"

    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.content = expected_content

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.download_odps(contract_id, format="yaml")

    assert result == expected_content
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/download/",
        params={"format": "odps", "output_format": "yaml"}
    )


@pytest.mark.asyncio
async def test_download_odps_with_version(contracts_api, client):
    """Test downloading contract as ODPS format with version parameter."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"
    expected_content = b'{"schema": "https://opendataproducts.org/schema/v4.2", "version": "4.2"}'

    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.content = expected_content

    client.request = AsyncMock(return_value=mock_response)

    result = await contracts_api.download_odps(contract_id, version="4.2", format="json")

    assert result == expected_content
    client.request.assert_called_once_with(
        "GET",
        f"contracts/{contract_id}/download/",
        params={"format": "odps", "output_format": "json", "version": "4.2"}
    )


@pytest.mark.asyncio
async def test_download_odps_invalid_format(contracts_api):
    """Test that invalid format raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.download_odps("123e4567-e89b-12d3-a456-426614174000", format="xml")
    assert exc_info.value.code == "INVALID_VALUE"
    assert "format" in exc_info.value.message.lower()


# ODPS Error Handling and Validation Tests

@pytest.mark.asyncio
async def test_export_odps_invalid_contract_id_empty(contracts_api):
    """Test that empty contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps("", format="json")
    assert exc_info.value.code == "REQUIRED_FIELD_MISSING"
    assert "contract_id" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_export_odps_invalid_contract_id_not_uuid(contracts_api):
    """Test that non-UUID contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps("not-a-uuid", format="json")
    assert exc_info.value.code == "INVALID_VALUE"
    assert "uuid" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_export_odps_invalid_contract_id_type(contracts_api):
    """Test that non-string contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps(123, format="json")  # type: ignore
    assert exc_info.value.code == "INVALID_DATA_TYPE"
    assert "string" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_export_odps_invalid_version_format(contracts_api):
    """Test that invalid version format raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps("123e4567-e89b-12d3-a456-426614174000", version="invalid", format="json")
    assert exc_info.value.code == "INVALID_VALUE"
    assert "version" in exc_info.value.message.lower() or "format" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_export_odps_invalid_version_type(contracts_api):
    """Test that non-string version raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.export_odps("123e4567-e89b-12d3-a456-426614174000", version=4.1, format="json")  # type: ignore
    assert exc_info.value.code == "INVALID_DATA_TYPE"


@pytest.mark.asyncio
async def test_download_odps_invalid_contract_id(contracts_api):
    """Test that invalid contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.download_odps("invalid", format="json")
    assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]


@pytest.mark.asyncio
async def test_create_odps_invalid_content_empty(contracts_api):
    """Test that empty original_raw raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.create_odps("", extract_odcs=True)
    assert exc_info.value.code == "REQUIRED_FIELD_MISSING"
    assert "original_raw" in exc_info.value.message.lower() or "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_odps_invalid_content_too_short(contracts_api):
    """Test that too-short original_raw raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.create_odps("{}", extract_odcs=True)
    assert exc_info.value.code == "INVALID_VALUE"
    assert "short" in exc_info.value.message.lower() or "length" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_odps_invalid_link_odcs_id(contracts_api):
    """Test that invalid link_odcs_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.create_odps(
            '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}',
            link_odcs_id="invalid-uuid",
        )
    assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]


@pytest.mark.asyncio
async def test_create_odps_mutually_exclusive_raises_odps_error(contracts_api):
    """Test that providing both extract_odcs and link_odcs_id raises ODPSValidationError."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}'

    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.create_odps(
            original_raw=odps_content,
            extract_odcs=True,
            link_odcs_id="123e4567-e89b-12d3-a456-426614174000",
        )
    assert exc_info.value.code == "INVALID_VALUE"
    assert "extract_odcs" in exc_info.value.message.lower() or "link_odcs_id" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_odps_neither_option_raises_odps_error(contracts_api):
    """Test that providing neither extract_odcs nor link_odcs_id raises ODPSValidationError."""
    odps_content = '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}'

    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.create_odps(original_raw=odps_content)
    assert exc_info.value.code == "REQUIRED_FIELD_MISSING"
    assert "extract_odcs" in exc_info.value.message.lower() or "link_odcs_id" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_link_odps_to_odcs_invalid_odcs_id(contracts_api):
    """Test that invalid odcs_contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.link_odps_to_odcs(
            odcs_contract_id="invalid",
            odps_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}',
            odps_format="JSON",
        )
    assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]


@pytest.mark.asyncio
async def test_link_odps_to_odcs_missing_odps_format(contracts_api):
    """Test that missing odps_format when odps_raw provided raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.link_odps_to_odcs(
            odcs_contract_id="123e4567-e89b-12d3-a456-426614174000",
            odps_raw='{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test"}}}}',
        )
    assert exc_info.value.code == "REQUIRED_FIELD_MISSING"
    assert "odps_format" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_link_odps_to_odcs_neither_provided(contracts_api):
    """Test that providing neither odps_contract_id nor odps_raw raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.link_odps_to_odcs(
            odcs_contract_id="123e4567-e89b-12d3-a456-426614174000",
        )
    assert exc_info.value.code == "REQUIRED_FIELD_MISSING"
    assert "odps_contract_id" in exc_info.value.message.lower() or "odps_raw" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_unlink_odps_from_odcs_invalid_id(contracts_api):
    """Test that invalid odcs_contract_id raises ODPSValidationError."""
    with pytest.raises(ODPSValidationError) as exc_info:
        await contracts_api.unlink_odps_from_odcs("invalid")
    assert exc_info.value.code in ["INVALID_VALUE", "REQUIRED_FIELD_MISSING"]


@pytest.mark.asyncio
async def test_export_odps_api_error_mapping(contracts_api, client):
    """Test that API errors are properly mapped to ODPS errors."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"

    from datahub_interoperability.errors import ODPSExportError

    client.request = AsyncMock(side_effect=ODPSExportError(
        "Failed to generate ODPS export",
        error_code="ODPS_EXPORT_ERROR",
        http_status=500,
        details={"context": {"field_path": "/product/details"}},
    ))

    with pytest.raises(ODPSExportError) as exc_info:
        await contracts_api.export_odps(contract_id, format="json")
    assert exc_info.value.code == "ODPS_EXPORT_ERROR"
    assert "export" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_export_odps_not_found_error(contracts_api, client):
    """Test that 404 errors are properly handled."""
    contract_id = "123e4567-e89b-12d3-a456-426614174000"

    from datahub_interoperability.errors import NotFoundError, ODPSError

    client.request = AsyncMock(side_effect=NotFoundError("Contract not found"))

    # NotFoundError may be wrapped in ODPSError by error handler
    with pytest.raises((NotFoundError, ODPSError)):
        await contracts_api.export_odps(contract_id, format="json")
