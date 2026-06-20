"""
Tests for Marketplace Integration API.

Unit tests for validation logic and error handling.
"""

import uuid

import pytest

from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

from datahub_interoperability import DataHubClient, DataHubClientConfig, MarketplaceIntegrationAPI
from datahub_interoperability.errors import (
    MarketplaceConnectionError,
    MarketplaceValidationError,
    NotFoundError,
)


@pytest.fixture
def config():
    """Test configuration"""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        timeout=30.0,
        max_retries=3,
        user_agent="test-agent",
        enable_logging=False,
    )


@pytest.fixture
async def client(config):
    """Test client"""
    async with DataHubClient(config) as client:
        yield client


@pytest.fixture
def marketplace_api(client):
    """Test marketplace API"""
    return MarketplaceIntegrationAPI(client)


# Module Structure Tests


def test_marketplace_api_import():
    """Test that MarketplaceIntegrationAPI can be imported from package"""
    from datahub_interoperability import MarketplaceIntegrationAPI

    assert MarketplaceIntegrationAPI is not None
    assert hasattr(MarketplaceIntegrationAPI, "__init__")


def test_marketplace_api_in_package_exports():
    """Test that MarketplaceIntegrationAPI is in package __all__ exports"""
    import datahub_interoperability

    assert "MarketplaceIntegrationAPI" in datahub_interoperability.__all__


def test_marketplace_api_initialization(marketplace_api, client):
    """Test MarketplaceIntegrationAPI initialization"""
    assert marketplace_api is not None
    assert marketplace_api.client == client
    assert isinstance(marketplace_api, MarketplaceIntegrationAPI)


@pytest.mark.asyncio
async def test_marketplace_api_accessible_from_client(config):
    """Test that marketplace API is accessible from client"""
    async with DataHubClient(config) as client:
        assert hasattr(client, "marketplace")
        assert client.marketplace is not None
        assert isinstance(client.marketplace, MarketplaceIntegrationAPI)


@pytest.mark.asyncio
async def test_marketplace_api_has_client_reference(config):
    """Test that marketplace API has reference to client"""
    async with DataHubClient(config) as client:
        assert client.marketplace.client == client


# Connection Management Validation Tests


def test_create_connection_validation_marketplace_type_empty(marketplace_api):
    """Test create_connection validation: empty marketplace_type"""
    # Validation happens in the method, so we test the validation helper
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_marketplace_type("")
    assert "required" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_connection_validation_name_empty(marketplace_api):
    """Test create_connection validation: empty name"""
    # create_connection signature: (marketplace_type, name, config)
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.create_connection("SNOWFLAKE_DATA_MARKETPLACE", "", {"key": "value"})
    assert "name" in exc_info.value.message.lower()


def test_create_connection_validation_config_empty(marketplace_api):
    """Test create_connection validation: empty config"""
    # Validation happens in the method
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_config({})
    assert "required" in exc_info.value.message.lower()


def test_create_connection_validation_config_not_dict(marketplace_api):
    """Test create_connection validation: config not a dict"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_config("not-a-dict")
    assert "dictionary" in exc_info.value.message.lower()


def test_get_connection_validation_empty_id(marketplace_api):
    """Test get_connection validation: empty connection_id"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_uuid("", "connection_id")
    assert "required" in exc_info.value.message.lower()


def test_get_connection_validation_invalid_uuid(marketplace_api):
    """Test get_connection validation: invalid UUID format"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_uuid("not-a-uuid", "connection_id")
    assert "valid uuid" in exc_info.value.message.lower()


def test_get_connection_validation_valid_uuid(marketplace_api):
    """Test get_connection validation: valid UUID format"""
    valid_uuid = str(uuid.uuid4())
    # Should not raise
    marketplace_api._validate_uuid(valid_uuid, "connection_id")


@pytest.mark.asyncio
async def test_update_connection_validation_no_fields(marketplace_api):
    """Test update_connection validation: no update fields provided"""
    valid_uuid = str(uuid.uuid4())
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.update_connection(valid_uuid)
    assert exc_info.value.message is not None


@pytest.mark.asyncio
async def test_list_connections_validation_limit_negative(marketplace_api):
    """Test list_connections validation: negative limit"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.list_connections(limit=-1)
    assert "limit" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_list_connections_validation_offset_negative(marketplace_api):
    """Test list_connections validation: negative offset"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.list_connections(offset=-1)
    assert "offset" in exc_info.value.message.lower()


# Sync Job Validation Tests


def test_sync_assets_to_marketplace_validation_empty_asset_ids(marketplace_api):
    """Test sync_assets_to_marketplace validation: empty asset_ids"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_asset_ids([])
    assert (
        "required" in exc_info.value.message.lower()
        or "cannot be empty" in exc_info.value.message.lower()
    )


def test_sync_assets_to_marketplace_validation_invalid_asset_id(marketplace_api):
    """Test sync_assets_to_marketplace validation: invalid asset_id in list"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_asset_ids(["not-a-uuid"])
    assert "valid uuid" in exc_info.value.message.lower()


def test_sync_assets_to_marketplace_validation_valid_asset_ids(marketplace_api):
    """Test sync_assets_to_marketplace validation: valid asset_ids"""
    valid_uuids = [str(uuid.uuid4()), str(uuid.uuid4())]
    marketplace_api._validate_asset_ids(valid_uuids)  # should not raise


@pytest.mark.asyncio
async def test_sync_bidirectional_validation_empty_listing_ids(marketplace_api):
    """Test sync_bidirectional validation: empty listing_ids"""
    # sync_bidirectional signature: (connection_id, asset_ids, listing_ids)
    conn_id = str(uuid.uuid4())
    valid_asset_ids = [str(uuid.uuid4())]
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.sync_bidirectional(conn_id, valid_asset_ids, [])
    assert exc_info.value.message is not None


# Mapping Validation Tests


def test_create_mapping_validation_empty_external_listing_id(marketplace_api):
    """Test create_mapping validation: empty external_listing_id"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_uuid("", "external_listing_id")
    assert "required" in exc_info.value.message.lower()


def test_create_mapping_validation_external_listing_id_not_string(marketplace_api):
    """Test create_mapping validation: external_listing_id not a string"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        marketplace_api._validate_uuid(123, "external_listing_id")
    assert "string" in exc_info.value.message.lower()


# Connector Validation Tests


@pytest.mark.asyncio
async def test_get_connector_info_validation_empty_type(marketplace_api):
    """Test get_connector_info validation: empty connector_type"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.get_connector_info("")
    assert (
        "connector_type" in exc_info.value.message.lower()
        or "required" in exc_info.value.message.lower()
    )


@pytest.mark.asyncio
async def test_get_connector_info_validation_type_not_string(marketplace_api):
    """Test get_connector_info validation: connector_type not a string"""
    with pytest.raises(MarketplaceValidationError) as exc_info:
        await marketplace_api.get_connector_info(123)
    assert exc_info.value.message is not None


# Error Handling Tests


def test_handle_marketplace_error_preserves_not_found(marketplace_api):
    """Test that NotFoundError is preserved in error handling"""
    not_found = NotFoundError("Resource not found", "req-123")
    result = marketplace_api._handle_marketplace_error(not_found, "test")
    assert isinstance(result, NotFoundError)
    assert result.message == "Resource not found"


def test_handle_marketplace_error_preserves_validation_error(marketplace_api):
    """Test that MarketplaceValidationError is preserved in error handling"""
    validation_error = MarketplaceValidationError(
        "Validation failed",
        field_path="/test",
        expected="string",
        actual="int",
    )
    result = marketplace_api._handle_marketplace_error(validation_error, "test")
    assert isinstance(result, MarketplaceValidationError)
    assert result.message == "Validation failed"


def test_handle_marketplace_error_wraps_generic_error(marketplace_api):
    """Test that generic errors are wrapped in MarketplaceConnectionError"""
    from datahub_interoperability.errors import DataHubError

    generic_error = DataHubError("Generic error", "GENERIC_ERROR", 500)
    result = marketplace_api._handle_marketplace_error(generic_error, "test")
    assert isinstance(result, MarketplaceConnectionError)
    assert "test" in result.message.lower()


# Method Existence Tests


def test_marketplace_api_methods_exist(marketplace_api):
    """Test that MarketplaceIntegrationAPI has expected methods"""
    # Connection methods
    assert hasattr(marketplace_api, "create_connection")
    assert hasattr(marketplace_api, "list_connections")
    assert hasattr(marketplace_api, "get_connection")
    assert hasattr(marketplace_api, "update_connection")
    assert hasattr(marketplace_api, "delete_connection")
    assert hasattr(marketplace_api, "test_connection")

    # Sync job methods
    assert hasattr(marketplace_api, "sync_assets_to_marketplace")
    assert hasattr(marketplace_api, "sync_from_marketplace")
    assert hasattr(marketplace_api, "sync_bidirectional")
    assert hasattr(marketplace_api, "get_sync_job")
    assert hasattr(marketplace_api, "list_sync_jobs")
    assert hasattr(marketplace_api, "cancel_sync_job")

    # Mapping methods
    assert hasattr(marketplace_api, "create_mapping")
    assert hasattr(marketplace_api, "get_mapping")
    assert hasattr(marketplace_api, "list_mappings")
    assert hasattr(marketplace_api, "update_mapping")
    assert hasattr(marketplace_api, "delete_mapping")

    # Connector methods
    assert hasattr(marketplace_api, "list_connectors")
    assert hasattr(marketplace_api, "get_connector_info")


def test_marketplace_api_validation_helpers_exist(marketplace_api):
    """Test that MarketplaceIntegrationAPI has validation helper methods"""
    assert hasattr(marketplace_api, "_validate_uuid")
    assert hasattr(marketplace_api, "_validate_marketplace_type")
    assert hasattr(marketplace_api, "_validate_config")
    assert hasattr(marketplace_api, "_validate_asset_ids")
    assert hasattr(marketplace_api, "_handle_marketplace_error")
