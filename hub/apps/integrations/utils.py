"""
Marketplace Connector Utilities

Provides utility functions for marketplace connector implementations,
including configuration validation, metadata normalization, datetime parsing,
and ID sanitization.
"""
import re
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dateutil import parser as date_parser

from hub.apps.integrations.base import MarketplaceType
from hub.apps.core.services.base import ServiceError


class MarketplaceError(ServiceError):
    """
    Base exception class for all marketplace-related errors.

    Extends ServiceError with marketplace-specific error codes and context.

    Attributes:
        error_code: Machine-readable error code for programmatic handling
        message: Human-readable error message
        details: Additional context information (dict)
        http_status: HTTP status code for API responses
        tenant_id: Tenant ID (if applicable)
        user_id: User ID (if applicable)
        timestamp: Error timestamp (Unix timestamp)
        marketplace_type: Marketplace type (if applicable)
    """

    # Common error codes
    ERROR_CODE_UNKNOWN = "MARKETPLACE_UNKNOWN_ERROR"
    ERROR_CODE_INVALID_CONFIG = "MARKETPLACE_INVALID_CONFIG"
    ERROR_CODE_CONNECTION_FAILED = "MARKETPLACE_CONNECTION_FAILED"
    ERROR_CODE_AUTHENTICATION_FAILED = "MARKETPLACE_AUTHENTICATION_FAILED"
    ERROR_CODE_SYNC_FAILED = "MARKETPLACE_SYNC_FAILED"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 500,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        marketplace_type: Optional[MarketplaceType] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize MarketplaceError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (defaults to ERROR_CODE_UNKNOWN)
            details: Additional context information
            http_status: HTTP status code for API responses
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            marketplace_type: Marketplace type (if applicable)
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = MarketplaceError.ERROR_CODE_UNKNOWN

        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.http_status = http_status
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.marketplace_type = marketplace_type
        self.timestamp = int(time.time())
        self.cause = cause

        # Store cause in details for better error tracking
        if cause:
            self.details["cause_type"] = type(cause).__name__
            self.details["cause_message"] = str(cause)

        # Store marketplace type in details
        if marketplace_type:
            self.details["marketplace_type"] = marketplace_type.value

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for API responses and logging.

        Returns:
            Dictionary with error details
        """
        result = {
            "error": self.error_code,
            "message": self.message,
            "http_status": self.http_status,
            "timestamp": self.timestamp,
            "details": self.details,
        }

        if self.tenant_id:
            result["tenant_id"] = self.tenant_id

        if self.user_id:
            result["user_id"] = self.user_id

        if self.marketplace_type:
            result["marketplace_type"] = self.marketplace_type.value

        return result

    def __str__(self) -> str:
        """String representation of the error"""
        marketplace_str = f" [{self.marketplace_type.value}]" if self.marketplace_type else ""
        return f"{self.__class__.__name__}({self.error_code}){marketplace_str}: {self.message}"

    def __repr__(self) -> str:
        """Detailed representation of the error"""
        return (
            f"{self.__class__.__name__}("
            f"error_code={self.error_code!r}, "
            f"message={self.message!r}, "
            f"http_status={self.http_status}, "
            f"marketplace_type={self.marketplace_type.value if self.marketplace_type else None}, "
            f"details={self.details!r}"
            f")"
        )


class MarketplaceConnectionError(MarketplaceError):
    """
    Exception raised when marketplace connection fails.

    Used for network errors, timeout errors, and service unavailable errors.
    """

    ERROR_CODE_CONNECTION_TIMEOUT = "MARKETPLACE_CONNECTION_TIMEOUT"
    ERROR_CODE_SERVICE_UNAVAILABLE = "MARKETPLACE_SERVICE_UNAVAILABLE"
    ERROR_CODE_NETWORK_ERROR = "MARKETPLACE_NETWORK_ERROR"
    ERROR_CODE_INVALID_ENDPOINT = "MARKETPLACE_INVALID_ENDPOINT"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        marketplace_type: Optional[MarketplaceType] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize MarketplaceConnectionError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            endpoint: Marketplace API endpoint that failed
            timeout: Connection timeout value (if applicable)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            marketplace_type: Marketplace type
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = MarketplaceConnectionError.ERROR_CODE_CONNECTION_FAILED

        if details is None:
            details = {}

        if endpoint:
            details["endpoint"] = endpoint
        if timeout is not None:
            details["timeout"] = timeout

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=502,  # Bad Gateway
            tenant_id=tenant_id,
            user_id=user_id,
            marketplace_type=marketplace_type,
            cause=cause,
        )


class MarketplaceAuthenticationError(MarketplaceError):
    """
    Exception raised when marketplace authentication fails.

    Used for invalid credentials, expired tokens, and permission errors.
    """

    ERROR_CODE_INVALID_CREDENTIALS = "MARKETPLACE_INVALID_CREDENTIALS"
    ERROR_CODE_TOKEN_EXPIRED = "MARKETPLACE_TOKEN_EXPIRED"
    ERROR_CODE_TOKEN_INVALID = "MARKETPLACE_TOKEN_INVALID"
    ERROR_CODE_PERMISSION_DENIED = "MARKETPLACE_PERMISSION_DENIED"
    ERROR_CODE_ACCOUNT_SUSPENDED = "MARKETPLACE_ACCOUNT_SUSPENDED"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        credential_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        marketplace_type: Optional[MarketplaceType] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize MarketplaceAuthenticationError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            credential_type: Type of credentials that failed (api_key, oauth_token, etc.)
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            marketplace_type: Marketplace type
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = MarketplaceAuthenticationError.ERROR_CODE_AUTHENTICATION_FAILED

        if details is None:
            details = {}

        if credential_type:
            details["credential_type"] = credential_type

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=401,  # Unauthorized
            tenant_id=tenant_id,
            user_id=user_id,
            marketplace_type=marketplace_type,
            cause=cause,
        )


class MarketplaceSyncError(MarketplaceError):
    """
    Exception raised when marketplace synchronization fails.

    Used for sync operation failures, data mapping errors, and bulk operation errors.
    """

    ERROR_CODE_SYNC_TIMEOUT = "MARKETPLACE_SYNC_TIMEOUT"
    ERROR_CODE_SYNC_PARTIAL_FAILURE = "MARKETPLACE_SYNC_PARTIAL_FAILURE"
    ERROR_CODE_MAPPING_FAILED = "MARKETPLACE_MAPPING_FAILED"
    ERROR_CODE_VALIDATION_FAILED = "MARKETPLACE_VALIDATION_FAILED"
    ERROR_CODE_RATE_LIMIT_EXCEEDED = "MARKETPLACE_RATE_LIMIT_EXCEEDED"

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        sync_direction: Optional[str] = None,
        sync_job_id: Optional[str] = None,
        items_processed: Optional[int] = None,
        items_failed: Optional[int] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        marketplace_type: Optional[MarketplaceType] = None,
        cause: Optional[Exception] = None,
    ):
        """
        Initialize MarketplaceSyncError.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional context information
            sync_direction: Sync direction (PUSH, PULL, BIDIRECTIONAL)
            sync_job_id: Sync job ID (if applicable)
            items_processed: Number of items processed before failure
            items_failed: Number of items that failed
            tenant_id: Tenant ID (if applicable)
            user_id: User ID (if applicable)
            marketplace_type: Marketplace type
            cause: Original exception that caused this error
        """
        if error_code is None:
            error_code = MarketplaceSyncError.ERROR_CODE_SYNC_FAILED

        if details is None:
            details = {}

        if sync_direction:
            details["sync_direction"] = sync_direction
        if sync_job_id:
            details["sync_job_id"] = sync_job_id
        if items_processed is not None:
            details["items_processed"] = items_processed
        if items_failed is not None:
            details["items_failed"] = items_failed

        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            http_status=500,  # Internal Server Error
            tenant_id=tenant_id,
            user_id=user_id,
            marketplace_type=marketplace_type,
            cause=cause,
        )


def validate_marketplace_config(
    config: Dict[str, Any],
    required_fields: Optional[List[str]] = None,
    marketplace_type: Optional[MarketplaceType] = None
) -> Dict[str, Any]:
    """
    Validate marketplace connector configuration.

    Validates that the configuration dictionary contains all required fields
    and that field values are of the correct types. Raises MarketplaceError
    if validation fails.

    Args:
        config: Configuration dictionary to validate
        required_fields: List of required field names (defaults to common fields)
        marketplace_type: Optional marketplace type for error context

    Returns:
        Validated configuration dictionary

    Raises:
        MarketplaceError: If configuration is invalid

    Example:
        config = validate_marketplace_config(
            {"api_key": "key123", "endpoint": "https://api.example.com"},
            required_fields=["api_key", "endpoint"]
        )
    """
    if not isinstance(config, dict):
        raise MarketplaceError(
            "Marketplace configuration must be a dictionary",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            marketplace_type=marketplace_type,
            details={"config_type": type(config).__name__}
        )

    if required_fields is None:
        # Default required fields for most marketplace connectors
        required_fields = []

    # Validate required fields
    missing_fields = []
    for field in required_fields:
        if field not in config or config[field] is None:
            missing_fields.append(field)

    if missing_fields:
        raise MarketplaceError(
            f"Marketplace configuration missing required fields: {', '.join(missing_fields)}",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            marketplace_type=marketplace_type,
            details={
                "missing_fields": missing_fields,
                "provided_fields": list(config.keys())
            }
        )

    # Validate field types (common validations)
    if "endpoint" in config and not isinstance(config["endpoint"], str):
        raise MarketplaceError(
            "Marketplace configuration 'endpoint' must be a string",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            marketplace_type=marketplace_type,
            details={"field": "endpoint", "type": type(config["endpoint"]).__name__}
        )

    if "api_key" in config and not isinstance(config["api_key"], str):
        raise MarketplaceError(
            "Marketplace configuration 'api_key' must be a string",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            marketplace_type=marketplace_type,
            details={"field": "api_key", "type": type(config["api_key"]).__name__}
        )

    if "timeout" in config:
        timeout = config["timeout"]
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise MarketplaceError(
                "Marketplace configuration 'timeout' must be a positive number",
                error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
                marketplace_type=marketplace_type,
                details={"field": "timeout", "value": timeout}
            )

    return config


def normalize_marketplace_metadata(
    metadata: Dict[str, Any],
    marketplace_type: Optional[MarketplaceType] = None
) -> Dict[str, Any]:
    """
    Normalize marketplace metadata to a standard format.

    Normalizes metadata from different marketplace platforms to a consistent
    structure. Handles common field name variations and data type conversions.

    Args:
        metadata: Raw metadata dictionary from marketplace
        marketplace_type: Optional marketplace type for type-specific normalization

    Returns:
        Normalized metadata dictionary

    Example:
        normalized = normalize_marketplace_metadata({
            "Title": "My Product",
            "Description": "A great product",
            "Created": "2025-01-01T12:00:00Z"
        })
        # Returns: {
        #     "title": "My Product",
        #     "description": "A great product",
        #     "created": "2025-01-01T12:00:00Z"
        # }
    """
    if not isinstance(metadata, dict):
        return {}

    normalized = {}

    # Common field name mappings (case-insensitive)
    field_mappings = {
        "title": ["title", "name", "product_name", "product_title"],
        "description": ["description", "desc", "summary", "product_description"],
        "category": ["category", "categories", "product_category", "type"],
        "tags": ["tags", "tag", "keywords", "labels"],
        "created": ["created", "created_at", "created_date", "date_created"],
        "updated": ["updated", "updated_at", "updated_date", "date_updated", "modified"],
        "url": ["url", "link", "uri", "href", "listing_url"],
        "product_id": ["product_id", "productid", "id", "product_identifier"],
        "price": ["price", "cost", "amount", "pricing"],
        "currency": ["currency", "currency_code", "curr"],
    }

    # Normalize keys to lowercase for case-insensitive matching
    metadata_lower = {k.lower(): v for k, v in metadata.items()}

    # Map fields using the mappings
    for normalized_key, possible_keys in field_mappings.items():
        for possible_key in possible_keys:
            if possible_key.lower() in metadata_lower:
                value = metadata[possible_key] if possible_key in metadata else metadata_lower[possible_key.lower()]

                # Handle list/tags normalization
                if normalized_key == "tags":
                    if isinstance(value, str):
                        # Split comma-separated tags
                        normalized[normalized_key] = [tag.strip() for tag in value.split(",") if tag.strip()]
                    elif isinstance(value, list):
                        normalized[normalized_key] = [str(tag).strip() for tag in value if tag]
                    else:
                        normalized[normalized_key] = []
                else:
                    normalized[normalized_key] = value
                break

    # Copy any remaining fields that weren't mapped
    for key, value in metadata.items():
        key_lower = key.lower()
        if key_lower not in [k.lower() for k in normalized.keys()]:
            # Only copy if it's not already normalized
            if not any(key_lower == mapped_key.lower() for mapped_keys in field_mappings.values() for mapped_key in mapped_keys):
                normalized[key] = value

    return normalized


def parse_marketplace_datetime(
    datetime_str: Optional[str],
    default_timezone: Optional[timezone] = None
) -> Optional[datetime]:
    """
    Parse datetime string from marketplace metadata.

    Handles various datetime formats commonly used by marketplace platforms,
    including ISO 8601, RFC 3339, and common variations. Returns None if
    the input is None or empty.

    Args:
        datetime_str: Datetime string to parse (can be None or empty)
        default_timezone: Default timezone to use if datetime is timezone-naive
            (defaults to UTC)

    Returns:
        Parsed datetime object, or None if input is None/empty

    Raises:
        MarketplaceError: If datetime string cannot be parsed

    Example:
        dt = parse_marketplace_datetime("2025-01-01T12:00:00Z")
        dt = parse_marketplace_datetime("2025-01-01 12:00:00", default_timezone=timezone.utc)
    """
    if not datetime_str or not isinstance(datetime_str, str):
        return None

    datetime_str = datetime_str.strip()
    if not datetime_str:
        return None

    if default_timezone is None:
        default_timezone = timezone.utc

    try:
        # Try using dateutil parser (handles most formats)
        parsed_dt = date_parser.parse(datetime_str)

        # If timezone-naive, apply default timezone
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=default_timezone)

        return parsed_dt
    except (ValueError, TypeError) as e:
        # Try manual parsing for common formats
        try:
            # Try ISO format
            if 'T' in datetime_str or '+' in datetime_str or datetime_str.endswith('Z'):
                # ISO 8601 format
                if datetime_str.endswith('Z'):
                    datetime_str = datetime_str[:-1] + '+00:00'
                parsed_dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                return parsed_dt

            # Try common date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d']:
                try:
                    parsed_dt = datetime.strptime(datetime_str, fmt)
                    return parsed_dt.replace(tzinfo=default_timezone)
                except ValueError:
                    continue

            # If all parsing attempts fail, raise error
            raise MarketplaceError(
                f"Unable to parse datetime string: {datetime_str}",
                error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
                details={"datetime_string": datetime_str, "error": str(e)}
            )
        except Exception as parse_error:
            raise MarketplaceError(
                f"Unable to parse datetime string: {datetime_str}",
                error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
                details={"datetime_string": datetime_str, "error": str(parse_error)},
                cause=e
            )


def sanitize_marketplace_id(
    marketplace_id: str,
    max_length: int = 255,
    allow_unicode: bool = False
) -> str:
    """
    Sanitize marketplace ID to ensure it's safe for use in the system.

    Removes or replaces unsafe characters, normalizes whitespace, and ensures
    the ID meets length requirements. Marketplace IDs are often used in URLs,
    database queries, and file paths, so they must be sanitized.

    Args:
        marketplace_id: Raw marketplace ID to sanitize
        max_length: Maximum length for the sanitized ID (default: 255)
        allow_unicode: Whether to allow Unicode characters (default: False)

    Returns:
        Sanitized marketplace ID

    Raises:
        MarketplaceError: If marketplace_id is empty after sanitization

    Example:
        sanitized = sanitize_marketplace_id("My Product ID (2025)")
        # Returns: "My_Product_ID_2025"
    """
    if not isinstance(marketplace_id, str):
        raise MarketplaceError(
            "Marketplace ID must be a string",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            details={"marketplace_id_type": type(marketplace_id).__name__}
        )

    # Strip whitespace
    sanitized = marketplace_id.strip()

    if not sanitized:
        raise MarketplaceError(
            "Marketplace ID cannot be empty",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            details={"original_id": marketplace_id}
        )

    # Replace whitespace with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)

    # Remove or replace unsafe characters
    if allow_unicode:
        # Allow Unicode letters, numbers, underscores, hyphens, dots
        sanitized = re.sub(r'[^\w\-._]', '', sanitized, flags=re.UNICODE)
    else:
        # Only allow ASCII letters, numbers, underscores, hyphens, dots
        sanitized = re.sub(r'[^a-zA-Z0-9_\-.]', '', sanitized)

    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Remove leading/trailing underscores, hyphens, dots
    sanitized = sanitized.strip('_-.')

    if not sanitized:
        raise MarketplaceError(
            "Marketplace ID is empty after sanitization",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            details={"original_id": marketplace_id}
        )

    # Enforce max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('_-.')

    if not sanitized:
        raise MarketplaceError(
            f"Marketplace ID is empty after length truncation (max_length={max_length})",
            error_code=MarketplaceError.ERROR_CODE_INVALID_CONFIG,
            details={"original_id": marketplace_id, "max_length": max_length}
        )

    return sanitized

