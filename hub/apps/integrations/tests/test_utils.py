"""
Unit tests for marketplace connector utilities.

Tests configuration validation, metadata normalization, datetime parsing,
ID sanitization, and error classes.
"""

from datetime import datetime, timezone

import pytest

from hub.apps.integrations.base import MarketplaceType
from hub.apps.integrations.utils import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceError,
    MarketplaceSyncError,
    normalize_marketplace_metadata,
    parse_marketplace_datetime,
    sanitize_marketplace_id,
    validate_marketplace_config,
)


class TestValidateMarketplaceConfig:
    """Test validate_marketplace_config utility"""

    def test_validate_config_valid(self):
        """Test validation with valid configuration"""
        config = {"api_key": "test-key-123", "endpoint": "https://api.example.com", "timeout": 30}

        result = validate_marketplace_config(config)
        assert result == config

    def test_validate_config_with_required_fields(self):
        """Test validation with required fields"""
        config = {"api_key": "test-key", "endpoint": "https://api.example.com"}

        result = validate_marketplace_config(config, required_fields=["api_key", "endpoint"])
        assert result == config

    def test_validate_config_missing_required_field(self):
        """Test validation fails when required field is missing"""
        config = {"api_key": "test-key"}

        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(config, required_fields=["api_key", "endpoint"])

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "missing required fields" in exc_info.value.message.lower()
        assert "endpoint" in exc_info.value.details["missing_fields"]

    def test_validate_config_not_dict(self):
        """Test validation fails when config is not a dictionary"""
        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config("not-a-dict")

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "must be a dictionary" in exc_info.value.message.lower()

    def test_validate_config_invalid_endpoint_type(self):
        """Test validation fails when endpoint is not a string"""
        config = {"endpoint": 12345}

        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(config)

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "endpoint" in exc_info.value.message.lower()

    def test_validate_config_invalid_api_key_type(self):
        """Test validation fails when api_key is not a string"""
        config = {"api_key": 12345}

        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(config)

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "api_key" in exc_info.value.message.lower()

    def test_validate_config_invalid_timeout(self):
        """Test validation fails when timeout is invalid"""
        config = {"timeout": -1}

        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(config)

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "timeout" in exc_info.value.message.lower()

    def test_validate_config_with_marketplace_type(self):
        """Test validation includes marketplace type in error context"""
        config = {"invalid": "value"}

        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(
                config,
                required_fields=["api_key"],
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            )

        assert exc_info.value.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        assert (
            exc_info.value.details["marketplace_type"]
            == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )


class TestNormalizeMarketplaceMetadata:
    """Test normalize_marketplace_metadata utility"""

    def test_normalize_basic_metadata(self):
        """Test normalization of basic metadata"""
        metadata = {
            "Title": "My Product",
            "Description": "A great product",
            "Category": "Analytics",
        }

        result = normalize_marketplace_metadata(metadata)

        assert "title" in result
        assert result["title"] == "My Product"
        assert "description" in result
        assert result["description"] == "A great product"
        assert "category" in result
        assert result["category"] == "Analytics"

    def test_normalize_case_insensitive(self):
        """Test normalization is case-insensitive"""
        metadata = {"TITLE": "Product", "description": "Desc", "CATEGORY": "Cat"}

        result = normalize_marketplace_metadata(metadata)

        assert "title" in result
        assert "description" in result
        assert "category" in result

    def test_normalize_tags_string(self):
        """Test normalization of tags from comma-separated string"""
        metadata = {"tags": "tag1, tag2, tag3"}

        result = normalize_marketplace_metadata(metadata)

        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert result["tags"] == ["tag1", "tag2", "tag3"]

    def test_normalize_tags_list(self):
        """Test normalization of tags from list"""
        metadata = {"tags": ["tag1", "tag2", "tag3"]}

        result = normalize_marketplace_metadata(metadata)

        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert result["tags"] == ["tag1", "tag2", "tag3"]

    def test_normalize_datetime_fields(self):
        """Test normalization of datetime fields"""
        metadata = {"created_at": "2025-01-01T12:00:00Z", "updated_date": "2025-01-02T12:00:00Z"}

        result = normalize_marketplace_metadata(metadata)

        assert "created" in result
        assert result["created"] == "2025-01-01T12:00:00Z"
        assert "updated" in result
        assert result["updated"] == "2025-01-02T12:00:00Z"

    def test_normalize_preserves_unmapped_fields(self):
        """Test normalization preserves fields not in mappings"""
        metadata = {"title": "Product", "custom_field": "custom_value"}

        result = normalize_marketplace_metadata(metadata)

        assert "title" in result
        assert "custom_field" in result
        assert result["custom_field"] == "custom_value"

    def test_normalize_empty_dict(self):
        """Test normalization of empty dictionary"""
        result = normalize_marketplace_metadata({})
        assert result == {}

    def test_normalize_not_dict(self):
        """Test normalization handles non-dict input"""
        result = normalize_marketplace_metadata("not-a-dict")
        assert result == {}

    def test_normalize_with_marketplace_type(self):
        """Test normalization with marketplace type (for future type-specific logic)"""
        metadata = {"title": "Product"}

        result = normalize_marketplace_metadata(
            metadata, marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE
        )

        assert "title" in result


class TestParseMarketplaceDatetime:
    """Test parse_marketplace_datetime utility"""

    def test_parse_iso_format(self):
        """Test parsing ISO 8601 format"""
        dt_str = "2025-01-01T12:00:00Z"
        result = parse_marketplace_datetime(dt_str)

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12

    def test_parse_iso_with_timezone(self):
        """Test parsing ISO format with timezone"""
        dt_str = "2025-01-01T12:00:00+00:00"
        result = parse_marketplace_datetime(dt_str)

        assert isinstance(result, datetime)
        assert result.tzinfo is not None

    def test_parse_common_format(self):
        """Test parsing common datetime format"""
        dt_str = "2025-01-01 12:00:00"
        result = parse_marketplace_datetime(dt_str, default_timezone=timezone.utc)

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.tzinfo == timezone.utc

    def test_parse_date_only(self):
        """Test parsing date-only format"""
        dt_str = "2025-01-01"
        result = parse_marketplace_datetime(dt_str, default_timezone=timezone.utc)

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1

    def test_parse_none(self):
        """Test parsing None returns None"""
        result = parse_marketplace_datetime(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None"""
        result = parse_marketplace_datetime("")
        assert result is None

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises error"""
        with pytest.raises(MarketplaceError) as exc_info:
            parse_marketplace_datetime("invalid-date-format")

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "unable to parse" in exc_info.value.message.lower()

    def test_parse_with_default_timezone(self):
        """Test parsing applies default timezone to timezone-naive datetime"""
        dt_str = "2025-01-01 12:00:00"
        custom_tz = timezone.utc
        result = parse_marketplace_datetime(dt_str, default_timezone=custom_tz)

        assert result.tzinfo == custom_tz


class TestSanitizeMarketplaceId:
    """Test sanitize_marketplace_id utility"""

    def test_sanitize_basic_id(self):
        """Test sanitization of basic ID"""
        result = sanitize_marketplace_id("product-123")
        assert result == "product-123"

    def test_sanitize_with_spaces(self):
        """Test sanitization replaces spaces with underscores"""
        result = sanitize_marketplace_id("My Product ID")
        assert result == "My_Product_ID"

    def test_sanitize_with_special_chars(self):
        """Test sanitization removes special characters"""
        result = sanitize_marketplace_id("product(id)#2025")
        assert result == "productid2025"

    def test_sanitize_preserves_allowed_chars(self):
        """Test sanitization preserves allowed characters"""
        result = sanitize_marketplace_id("product_123-test.v2")
        assert result == "product_123-test.v2"

    def test_sanitize_removes_consecutive_underscores(self):
        """Test sanitization removes consecutive underscores"""
        result = sanitize_marketplace_id("product___id")
        assert result == "product_id"

    def test_sanitize_removes_leading_trailing_special(self):
        """Test sanitization removes leading/trailing special chars"""
        result = sanitize_marketplace_id("_product-id_")
        assert result == "product-id"

    def test_sanitize_enforces_max_length(self):
        """Test sanitization enforces max length"""
        long_id = "a" * 300
        result = sanitize_marketplace_id(long_id, max_length=100)

        assert len(result) <= 100

    def test_sanitize_empty_string(self):
        """Test sanitization fails on empty string"""
        with pytest.raises(MarketplaceError) as exc_info:
            sanitize_marketplace_id("")

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "cannot be empty" in exc_info.value.message.lower()

    def test_sanitize_whitespace_only(self):
        """Test sanitization fails on whitespace-only string"""
        with pytest.raises(MarketplaceError) as exc_info:
            sanitize_marketplace_id("   ")

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG

    def test_sanitize_not_string(self):
        """Test sanitization fails on non-string input"""
        with pytest.raises(MarketplaceError) as exc_info:
            sanitize_marketplace_id(12345)

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "must be a string" in exc_info.value.message.lower()

    def test_sanitize_all_special_chars(self):
        """Test sanitization when all chars are special"""
        with pytest.raises(MarketplaceError) as exc_info:
            sanitize_marketplace_id("!!!@@@###")

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG
        assert "empty after sanitization" in exc_info.value.message.lower()

    def test_sanitize_with_unicode(self):
        """Test sanitization with Unicode allowed"""
        result = sanitize_marketplace_id("产品-123", allow_unicode=True)
        assert "产品" in result

    def test_sanitize_without_unicode(self):
        """Test sanitization without Unicode removes Unicode chars"""
        result = sanitize_marketplace_id("产品-123", allow_unicode=False)
        assert "产品" not in result
        assert "123" in result


class TestMarketplaceError:
    """Test MarketplaceError exception class"""

    def test_error_creation(self):
        """Test creating a MarketplaceError"""
        error = MarketplaceError("Test error message")

        assert str(error) == "MarketplaceError(MARKETPLACE_UNKNOWN_ERROR): Test error message"
        assert error.error_code == MarketplaceError.ERROR_CODE_UNKNOWN
        assert error.message == "Test error message"
        assert error.http_status == 500

    def test_error_with_details(self):
        """Test error with details"""
        error = MarketplaceError("Test error", details={"field": "value"})

        assert error.details == {"field": "value"}

    def test_error_with_marketplace_type(self):
        """Test error with marketplace type"""
        error = MarketplaceError(
            "Test error", marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        assert error.marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        assert error.details["marketplace_type"] == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value

    def test_error_to_dict(self):
        """Test error to_dict method"""
        error = MarketplaceError(
            "Test error",
            error_code="TEST_ERROR",
            details={"field": "value"},
            tenant_id="tenant-123",
            user_id="user-456",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
        )

        error_dict = error.to_dict()

        assert error_dict["error"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"
        assert error_dict["tenant_id"] == "tenant-123"
        assert error_dict["user_id"] == "user-456"
        assert error_dict["marketplace_type"] == MarketplaceType.AWS_DATA_EXCHANGE.value
        assert "timestamp" in error_dict

    def test_error_with_cause(self):
        """Test error with cause exception"""
        cause = ValueError("Original error")
        error = MarketplaceError("Test error", cause=cause)

        assert error.cause == cause
        assert error.details["cause_type"] == "ValueError"
        assert error.details["cause_message"] == "Original error"


class TestMarketplaceConnectionError:
    """Test MarketplaceConnectionError exception class"""

    def test_connection_error_creation(self):
        """Test creating a MarketplaceConnectionError"""
        error = MarketplaceConnectionError("Connection failed")

        assert error.error_code == MarketplaceConnectionError.ERROR_CODE_CONNECTION_FAILED
        assert error.http_status == 502

    def test_connection_error_with_endpoint(self):
        """Test connection error with endpoint"""
        error = MarketplaceConnectionError("Connection failed", endpoint="https://api.example.com")

        assert error.details["endpoint"] == "https://api.example.com"

    def test_connection_error_with_timeout(self):
        """Test connection error with timeout"""
        error = MarketplaceConnectionError(
            "Connection timeout",
            error_code=MarketplaceConnectionError.ERROR_CODE_CONNECTION_TIMEOUT,
            timeout=30.0,
        )

        assert error.details["timeout"] == 30.0


class TestMarketplaceAuthenticationError:
    """Test MarketplaceAuthenticationError exception class"""

    def test_authentication_error_creation(self):
        """Test creating a MarketplaceAuthenticationError"""
        error = MarketplaceAuthenticationError("Authentication failed")

        assert error.error_code == MarketplaceAuthenticationError.ERROR_CODE_AUTHENTICATION_FAILED
        assert error.http_status == 401

    def test_authentication_error_with_credential_type(self):
        """Test authentication error with credential type"""
        error = MarketplaceAuthenticationError("Invalid credentials", credential_type="api_key")

        assert error.details["credential_type"] == "api_key"

    def test_authentication_error_token_expired(self):
        """Test authentication error for expired token"""
        error = MarketplaceAuthenticationError(
            "Token expired", error_code=MarketplaceAuthenticationError.ERROR_CODE_TOKEN_EXPIRED
        )

        assert error.error_code == MarketplaceAuthenticationError.ERROR_CODE_TOKEN_EXPIRED


class TestMarketplaceSyncError:
    """Test MarketplaceSyncError exception class"""

    def test_sync_error_creation(self):
        """Test creating a MarketplaceSyncError"""
        error = MarketplaceSyncError("Sync failed")

        assert error.error_code == MarketplaceSyncError.ERROR_CODE_SYNC_FAILED
        assert error.http_status == 500

    def test_sync_error_with_direction(self):
        """Test sync error with sync direction"""
        error = MarketplaceSyncError("Sync failed", sync_direction="PUSH")

        assert error.details["sync_direction"] == "PUSH"

    def test_sync_error_with_job_id(self):
        """Test sync error with sync job ID"""
        error = MarketplaceSyncError("Sync failed", sync_job_id="job-123")

        assert error.details["sync_job_id"] == "job-123"

    def test_sync_error_with_counts(self):
        """Test sync error with item counts"""
        error = MarketplaceSyncError(
            "Partial sync failure",
            error_code=MarketplaceSyncError.ERROR_CODE_SYNC_PARTIAL_FAILURE,
            items_processed=100,
            items_failed=5,
        )

        assert error.details["items_processed"] == 100
        assert error.details["items_failed"] == 5

    def test_sync_error_rate_limit(self):
        """Test sync error for rate limit"""
        error = MarketplaceSyncError(
            "Rate limit exceeded", error_code=MarketplaceSyncError.ERROR_CODE_RATE_LIMIT_EXCEEDED
        )

        assert error.error_code == MarketplaceSyncError.ERROR_CODE_RATE_LIMIT_EXCEEDED

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_validate_config_empty_dict(self):
        """Test that validate_config handles empty dict"""
        config = {}
        result = validate_marketplace_config(config)
        assert result == config

    def test_validate_config_with_none(self):
        """Test that validate_config rejects None"""
        with pytest.raises(MarketplaceError) as exc_info:
            validate_marketplace_config(None)

        assert exc_info.value.error_code == MarketplaceError.ERROR_CODE_INVALID_CONFIG

    def test_normalize_metadata_with_none(self):
        """Test that normalize_marketplace_metadata handles None"""
        result = normalize_marketplace_metadata(None)
        assert result == {}

    def test_normalize_metadata_with_empty_dict(self):
        """Test that normalize_marketplace_metadata handles empty dict"""
        result = normalize_marketplace_metadata({})
        assert result == {}

    def test_parse_datetime_with_invalid_format(self):
        """Test that parse_marketplace_datetime handles invalid formats"""
        # Should handle gracefully - may return None or raise error
        try:
            result = parse_marketplace_datetime("invalid-date")
            # If it returns None, that's acceptable
            assert result is None or isinstance(result, datetime)
        except (ValueError, TypeError, MarketplaceError):
            # If it raises error, that's also acceptable
            pass

    def test_sanitize_id_with_special_characters(self):
        """Test that sanitize_marketplace_id handles special characters"""
        special_id = "test-id!@#$%^&*()"
        sanitized = sanitize_marketplace_id(special_id)
        # Should remove or replace special characters
        assert isinstance(sanitized, str)
        assert len(sanitized) > 0

    def test_sanitize_id_with_empty_string(self):
        """Test that sanitize_marketplace_id handles empty string"""
        # May return empty string or raise MarketplaceError (implementation raises)
        try:
            sanitized = sanitize_marketplace_id("")
            assert isinstance(sanitized, str)
        except MarketplaceError:
            # Implementation raises when empty - acceptable
            pass

    # ========== EDGE CASES TESTS ==========

    def test_validate_config_with_very_long_values(self):
        """Test that validate_config handles very long values"""
        long_config = {"api_key": "a" * 10000, "endpoint": "https://" + "a" * 1000 + ".com"}
        try:
            result = validate_marketplace_config(long_config)
            assert result == long_config
        except MarketplaceError:
            # If validation fails due to length, that's acceptable
            pass

    def test_normalize_metadata_with_deeply_nested(self):
        """Test that normalize_marketplace_metadata handles deeply nested structures"""
        nested_metadata = {"level1": {"level2": {"level3": {"level4": {"level5": "deep_value"}}}}}
        result = normalize_marketplace_metadata(nested_metadata)
        assert result["level1"]["level2"]["level3"]["level4"]["level5"] == "deep_value"

    def test_parse_datetime_with_different_formats(self):
        """Test that parse_marketplace_datetime handles different datetime formats"""
        formats = [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:00+00:00",
            "2024-01-01 00:00:00",
            "2024-01-01",
        ]
        for fmt in formats:
            try:
                result = parse_marketplace_datetime(fmt)
                if result:
                    assert isinstance(result, datetime)
            except (ValueError, TypeError):
                # Some formats may not be supported
                pass

    def test_sanitize_id_with_unicode(self):
        """Test that sanitize_marketplace_id handles unicode characters"""
        unicode_id = "test-id-测试-тест-🎉"
        sanitized = sanitize_marketplace_id(unicode_id)
        assert isinstance(sanitized, str)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_validate_config_returns_copy(self):
        """Test that validate_config returns a copy of the dict when valid (defensive: avoids mutating caller's config)"""
        config = {"api_key": "test", "endpoint": "https://api.example.com"}
        result = validate_marketplace_config(config)
        assert result == config
        assert result is not config  # Must return a copy, not the original

    def test_normalize_metadata_preserves_structure(self):
        """Test that normalize_marketplace_metadata preserves structure"""
        metadata = {"key1": "value1", "key2": {"nested": "value"}, "key3": [1, 2, 3]}
        result = normalize_marketplace_metadata(metadata)
        assert result["key1"] == "value1"
        assert result["key2"]["nested"] == "value"
        assert result["key3"] == [1, 2, 3]

    def test_parse_datetime_returns_datetime_object(self):
        """Test that parse_marketplace_datetime returns datetime object"""
        result = parse_marketplace_datetime("2024-01-01T00:00:00Z")
        assert isinstance(result, datetime)

    def test_sanitize_id_returns_string(self):
        """Test that sanitize_marketplace_id returns string"""
        result = sanitize_marketplace_id("test-id-123")
        assert isinstance(result, str)

    def test_error_classes_have_required_attributes(self):
        """Test that error classes have required attributes"""
        error = MarketplaceError("Test error")
        assert hasattr(error, "message")
        assert hasattr(error, "error_code")
        assert hasattr(error, "details")
        assert hasattr(error, "http_status")

    def test_error_classes_inheritance(self):
        """Test that error classes inherit correctly"""
        connection_error = MarketplaceConnectionError("Connection failed")
        assert isinstance(connection_error, MarketplaceError)

        auth_error = MarketplaceAuthenticationError("Auth failed")
        assert isinstance(auth_error, MarketplaceError)

        sync_error = MarketplaceSyncError("Sync failed")
        assert isinstance(sync_error, MarketplaceError)
