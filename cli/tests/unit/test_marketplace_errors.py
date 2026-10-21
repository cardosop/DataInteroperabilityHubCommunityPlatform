"""
Unit tests for Marketplace error handling in CLI.

Tests verify:
1. Error parsing from API responses
2. Parameter validation
3. User-friendly error messages
4. Error context and suggestions
"""

import json

import pytest
from datahub_cli.marketplace_errors import (
    MarketplaceAuthenticationError,
    MarketplaceCLIError,
    MarketplaceConnectionError,
    MarketplaceSyncError,
    MarketplaceValidationError,
    handle_marketplace_api_error,
    parse_api_error_response,
    validate_connection_config,
    validate_connection_id,
    validate_marketplace_type,
    validate_sync_direction,
)


class TestMarketplaceCLIError:
    """Test base MarketplaceCLIError class"""

    def test_marketplace_cli_error_basic(self):
        """Test basic MarketplaceCLIError creation"""
        error = MarketplaceCLIError("Test error message")
        assert str(error) == "Test error message"
        assert error.error_code == "MARKETPLACE_CLI_ERROR"
        assert error.context == {}
        assert error.suggestion is None

    def test_marketplace_cli_error_with_context(self):
        """Test MarketplaceCLIError with context"""
        error = MarketplaceCLIError(
            "Test error",
            error_code="TEST_ERROR",
            context={
                "connection_id": "550e8400-e29b-41d4-a716-446655440000",
                "marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE",
            },
            suggestion="Fix the connection",
        )
        assert error.error_code == "TEST_ERROR"
        assert error.context["connection_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert error.suggestion == "Fix the connection"

    def test_marketplace_cli_error_format_message(self):
        """Test error message formatting"""
        error = MarketplaceCLIError(
            "Validation failed",
            context={
                "connection_id": "550e8400-e29b-41d4-a716-446655440000",
                "expected": "string",
                "actual": "number",
            },
            suggestion="Change the field type",
        )
        message = error.format_message()
        assert "Validation failed" in message
        assert "Connection ID: 550e8400-e29b-41d4-a716-446655440000" in message
        assert "Expected: string" in message
        assert "Actual: number" in message
        assert "Suggestion: Change the field type" in message


class TestMarketplaceErrorTypes:
    """Test specific Marketplace error types"""

    def test_marketplace_connection_error(self):
        """Test MarketplaceConnectionError"""
        error = MarketplaceConnectionError(
            "Connection failed",
            error_code="CONNECTION_FAILED",
            context={"connection_id": "550e8400-e29b-41d4-a716-446655440000"},
        )
        assert isinstance(error, MarketplaceCLIError)
        assert error.error_code == "CONNECTION_FAILED"

    def test_marketplace_authentication_error(self):
        """Test MarketplaceAuthenticationError"""
        error = MarketplaceAuthenticationError(
            "Authentication failed",
            error_code="AUTH_FAILED",
            context={"marketplace_type": "SNOWFLAKE_DATA_MARKETPLACE"},
        )
        assert isinstance(error, MarketplaceCLIError)
        assert error.error_code == "AUTH_FAILED"

    def test_marketplace_sync_error(self):
        """Test MarketplaceSyncError"""
        error = MarketplaceSyncError(
            "Sync failed",
            error_code="SYNC_FAILED",
            context={"connection_id": "550e8400-e29b-41d4-a716-446655440000"},
        )
        assert isinstance(error, MarketplaceCLIError)
        assert error.error_code == "SYNC_FAILED"

    def test_marketplace_validation_error(self):
        """Test MarketplaceValidationError"""
        error = MarketplaceValidationError(
            "Validation failed",
            error_code="VALIDATION_FAILED",
            context={"field_path": "/config/api_key"},
        )
        assert isinstance(error, MarketplaceCLIError)
        assert error.error_code == "VALIDATION_FAILED"


class TestParseAPIErrorResponse:
    """Test API error response parsing"""

    def test_parse_validation_error(self):
        """Test parsing validation error"""
        error_data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid marketplace type",
                "context": {"marketplace_type": "INVALID"},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceValidationError)
        assert error.error_code == "VALIDATION_ERROR"
        assert error.message == "Invalid marketplace type"

    def test_parse_authentication_error(self):
        """Test parsing authentication error"""
        error_data = {
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": "Invalid credentials",
                "context": {},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceAuthenticationError)
        assert error.error_code == "AUTHENTICATION_FAILED"

    def test_parse_connection_error(self):
        """Test parsing connection error"""
        error_data = {
            "error": {
                "code": "CONNECTION_TIMEOUT",
                "message": "Connection timed out",
                "context": {},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceConnectionError)
        assert error.error_code == "CONNECTION_TIMEOUT"

    def test_parse_sync_error(self):
        """Test parsing sync error"""
        error_data = {
            "error": {"code": "SYNC_FAILED", "message": "Synchronization failed", "context": {}}
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceSyncError)
        assert error.error_code == "SYNC_FAILED"

    def test_parse_generic_error(self):
        """Test parsing generic error"""
        error_data = {
            "error": {"code": "UNKNOWN_ERROR", "message": "Unknown error occurred", "context": {}}
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceCLIError)
        assert error.error_code == "UNKNOWN_ERROR"

    def test_parse_string_error(self):
        """Test parsing string error message"""
        error_data = {"error": "Simple error message"}
        error = parse_api_error_response(error_data)
        assert isinstance(error, MarketplaceCLIError)
        assert error.message == "Simple error message"


class TestHandleMarketplaceAPIError:
    """Test handle_marketplace_api_error function"""

    def test_handle_json_error(self):
        """Test handling JSON error response"""
        error_text = json.dumps(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "context": {}}}
        )
        error = handle_marketplace_api_error(
            error_text, 400, "integrations/marketplace/connections/"
        )
        assert isinstance(error, MarketplaceValidationError)
        assert error.context["status_code"] == 400
        assert error.context["endpoint"] == "integrations/marketplace/connections/"

    def test_handle_non_json_error(self):
        """Test handling non-JSON error response"""
        error_text = "Simple error message"
        error = handle_marketplace_api_error(
            error_text, 500, "integrations/marketplace/connections/"
        )
        assert isinstance(error, MarketplaceCLIError)
        assert error.context["status_code"] == 500


class TestValidateMarketplaceType:
    """Test validate_marketplace_type function"""

    def test_validate_valid_type(self):
        """Test validating valid marketplace type"""
        validate_marketplace_type("SNOWFLAKE_DATA_MARKETPLACE")
        validate_marketplace_type("AWS_DATA_EXCHANGE")
        validate_marketplace_type("CKAN_INSTANCE")

    def test_validate_empty_type(self):
        """Test validating empty marketplace type"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_marketplace_type("")
        assert exc_info.value.error_code == "EMPTY_MARKETPLACE_TYPE"

    def test_validate_invalid_type(self):
        """Test validating invalid marketplace type"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_marketplace_type("INVALID_TYPE")
        assert exc_info.value.error_code == "INVALID_MARKETPLACE_TYPE"
        assert "valid_types" in exc_info.value.context


class TestValidateSyncDirection:
    """Test validate_sync_direction function"""

    def test_validate_valid_direction(self):
        """Test validating valid sync direction"""
        validate_sync_direction("PUSH")
        validate_sync_direction("PULL")
        validate_sync_direction("BIDIRECTIONAL")
        validate_sync_direction(None)  # None is valid

    def test_validate_invalid_direction(self):
        """Test validating invalid sync direction"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_sync_direction("INVALID")
        assert exc_info.value.error_code == "INVALID_SYNC_DIRECTION"


class TestValidateConnectionConfig:
    """Test validate_connection_config function"""

    def test_validate_valid_dict(self):
        """Test validating valid config dictionary"""
        config = {"api_key": "test_key", "endpoint": "https://example.com"}
        validate_connection_config(config)

    def test_validate_valid_json_string(self):
        """Test validating valid JSON string"""
        config = '{"api_key": "test_key", "endpoint": "https://example.com"}'
        validate_connection_config(config)

    def test_validate_none(self):
        """Test validating None config"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_config(None)
        assert exc_info.value.error_code == "EMPTY_CONFIG"

    def test_validate_invalid_type(self):
        """Test validating invalid config type"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_config("not a dict")
        assert exc_info.value.error_code in ["INVALID_CONFIG_TYPE", "INVALID_JSON_CONFIG"]

    def test_validate_invalid_json_string(self):
        """Test validating invalid JSON string"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_config("{invalid json}")
        assert exc_info.value.error_code == "INVALID_JSON_CONFIG"


class TestValidateConnectionID:
    """Test validate_connection_id function"""

    def test_validate_valid_uuid(self):
        """Test validating valid UUID"""
        validate_connection_id("550e8400-e29b-41d4-a716-446655440000")
        validate_connection_id("550E8400-E29B-41D4-A716-446655440000")  # Uppercase

    def test_validate_empty_id(self):
        """Test validating empty connection ID"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_id("")
        assert exc_info.value.error_code == "EMPTY_CONNECTION_ID"

    def test_validate_invalid_format(self):
        """Test validating invalid UUID format"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_id("invalid-uuid")
        assert exc_info.value.error_code == "INVALID_CONNECTION_ID_FORMAT"

    def test_validate_too_short(self):
        """Test validating too short UUID"""
        with pytest.raises(MarketplaceValidationError) as exc_info:
            validate_connection_id("550e8400")
        assert exc_info.value.error_code == "INVALID_CONNECTION_ID_FORMAT"
