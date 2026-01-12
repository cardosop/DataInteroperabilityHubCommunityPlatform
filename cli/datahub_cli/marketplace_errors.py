"""
Marketplace Error Handling for CLI

Provides comprehensive error handling for marketplace operations in the CLI,
mapping backend marketplace errors to user-friendly messages with actionable guidance.
"""
import json
import re
from typing import Optional, Dict, Any
import click


class MarketplaceCLIError(click.ClickException):
    """
    Base exception class for Marketplace CLI errors.

    Provides structured error information with user-friendly messages
    and actionable guidance.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize Marketplace CLI error.

        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            context: Additional context information
            suggestion: Actionable suggestion for resolving the error
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.error_code = error_code or "MARKETPLACE_CLI_ERROR"
        self.context = context or {}
        self.suggestion = suggestion
        self.original_error = original_error

    def format_message(self) -> str:
        """Format error message with context and suggestions"""
        lines = [self.message]

        if self.context:
            # Add context information
            if 'connection_id' in self.context:
                lines.append(f"  Connection ID: {self.context['connection_id']}")
            if 'marketplace_type' in self.context:
                lines.append(f"  Marketplace Type: {self.context['marketplace_type']}")
            if 'expected' in self.context and 'actual' in self.context:
                lines.append(f"  Expected: {self.context['expected']}")
                lines.append(f"  Actual: {self.context['actual']}")
            if 'endpoint' in self.context:
                lines.append(f"  Endpoint: {self.context['endpoint']}")

        if self.suggestion:
            lines.append(f"\n💡 Suggestion: {self.suggestion}")

        return "\n".join(lines)


class MarketplaceConnectionError(MarketplaceCLIError):
    """Error for marketplace connection failures"""
    pass


class MarketplaceAuthenticationError(MarketplaceCLIError):
    """Error for marketplace authentication failures"""
    pass


class MarketplaceSyncError(MarketplaceCLIError):
    """Error for marketplace synchronization failures"""
    pass


class MarketplaceValidationError(MarketplaceCLIError):
    """Error for marketplace validation failures"""
    pass


def parse_api_error_response(error_data: Dict[str, Any]) -> Optional[MarketplaceCLIError]:
    """
    Parse API error response and convert to appropriate Marketplace CLI error.

    Args:
        error_data: Error data from API response

    Returns:
        MarketplaceCLIError instance or None if cannot parse
    """
    if not isinstance(error_data, dict):
        return None

    # Extract error information
    error_info = error_data.get('error', {})
    if isinstance(error_info, str):
        error_info = {'message': error_info}

    error_code = error_info.get('code') or error_info.get('error_code') or error_data.get('error_code')
    error_message = error_info.get('message') or error_info.get('user_message') or error_data.get('message', 'Unknown error')
    context_raw = error_info.get('context') or error_data.get('context', {})
    # Ensure context is a dict
    if not isinstance(context_raw, dict):
        context: Dict[str, Any] = {}
    else:
        context = context_raw

    # Map error codes to specific error types
    if error_code:
        error_code_upper = error_code.upper()

        # Validation errors
        if any(code in error_code_upper for code in [
            'VALIDATION', 'INVALID', 'REQUIRED_FIELD', 'INVALID_DATA_TYPE', 'INVALID_VALUE'
        ]):
            suggestion = _get_validation_suggestion(error_code, context)
            return MarketplaceValidationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Authentication errors
        if any(code in error_code_upper for code in [
            'AUTHENTICATION', 'AUTH_FAILED', 'UNAUTHORIZED', 'INVALID_CREDENTIALS'
        ]):
            suggestion = _get_authentication_suggestion(error_code, context)
            return MarketplaceAuthenticationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Connection errors
        if any(code in error_code_upper for code in [
            'CONNECTION', 'CONNECT_FAILED', 'TIMEOUT', 'NETWORK_ERROR'
        ]):
            suggestion = _get_connection_suggestion(error_code, context)
            return MarketplaceConnectionError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Sync errors
        if any(code in error_code_upper for code in [
            'SYNC', 'SYNCHRONIZATION', 'SYNC_FAILED'
        ]):
            suggestion = _get_sync_suggestion(error_code, context)
            return MarketplaceSyncError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

    # Default to generic marketplace error
    return MarketplaceCLIError(
        message=error_message,
        error_code=error_code or "MARKETPLACE_ERROR",
        context=context
    )


def handle_marketplace_api_error(
    response_text: str,
    status_code: int,
    endpoint: Optional[str] = None
) -> MarketplaceCLIError:
    """
    Handle API error response and convert to Marketplace CLI error.

    Args:
        response_text: Response text from API
        status_code: HTTP status code
        endpoint: API endpoint that failed

    Returns:
        MarketplaceCLIError instance
    """
    error_data = {}

    # Try to parse JSON error response
    try:
        error_data = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON, use raw text
        error_data = {'error': {'message': response_text or 'Unknown error'}}

    # Try to parse as marketplace error
    marketplace_error = parse_api_error_response(error_data)
    if marketplace_error:
        if endpoint:
            marketplace_error.context['endpoint'] = endpoint
        marketplace_error.context['status_code'] = status_code
        # Ensure suggestion is set if not already present
        if not marketplace_error.suggestion:
            marketplace_error.suggestion = _get_http_error_suggestion(status_code, endpoint)
        return marketplace_error

    # Fallback to generic error
    error_info = error_data.get('error', {})
    if isinstance(error_info, str):
        error_info = {'message': error_info}

    error_message = error_info.get('message', response_text or 'Unknown error')
    error_code_raw = error_info.get('code') or error_data.get('error_code') or f'HTTP_{status_code}'
    # Ensure error_code is always a string
    error_code = str(error_code_raw) if error_code_raw is not None else f'HTTP_{status_code}'

    suggestion = _get_http_error_suggestion(status_code, endpoint)

    context: Dict[str, Any] = {}
    if endpoint:
        context['endpoint'] = endpoint
    context['status_code'] = status_code

    return MarketplaceCLIError(
        message=error_message,
        error_code=error_code,
        context=context,
        suggestion=suggestion
    )


def validate_marketplace_type(marketplace_type: str) -> None:
    """
    Validate marketplace type format.

    Args:
        marketplace_type: Marketplace type string

    Raises:
        MarketplaceValidationError: If marketplace type is invalid
    """
    if not marketplace_type or not marketplace_type.strip():
        raise MarketplaceValidationError(
            message="Marketplace type cannot be empty",
            error_code="EMPTY_MARKETPLACE_TYPE",
            context={'marketplace_type': marketplace_type},
            suggestion="Provide a valid marketplace type"
        )

    # Valid marketplace types (from MarketplaceType enum)
    valid_types = [
        'SNOWFLAKE_DATA_MARKETPLACE',
        'AWS_DATA_EXCHANGE',
        'DATABRICKS_MARKETPLACE',
        'GOOGLE_CLOUD_MARKETPLACE',
        'AZURE_MARKETPLACE',
        'DATA_WORLD',
        'KAGGLE',
        'QUANDL',
        'APIS_GURU',
        'RAPIDAPI',
        'PROGRAMMABLE_WEB',
        'DATA_GOV',
        'EUROPEAN_DATA_PORTAL',
        'CKAN_INSTANCE',
        'CUSTOM',
    ]

    if marketplace_type.upper() not in [t.upper() for t in valid_types]:
        raise MarketplaceValidationError(
            message=f"Invalid marketplace type: {marketplace_type}",
            error_code="INVALID_MARKETPLACE_TYPE",
            context={'marketplace_type': marketplace_type, 'valid_types': valid_types},
            suggestion=f"Use one of: {', '.join(valid_types)}"
        )


def validate_sync_direction(sync_direction: Optional[str]) -> None:
    """
    Validate sync direction format.

    Args:
        sync_direction: Sync direction string (PUSH, PULL, BIDIRECTIONAL)

    Raises:
        MarketplaceValidationError: If sync direction is invalid
    """
    if sync_direction is None:
        return

    valid_directions = ['PUSH', 'PULL', 'BIDIRECTIONAL']
    if sync_direction.upper() not in [d.upper() for d in valid_directions]:
        raise MarketplaceValidationError(
            message=f"Invalid sync direction: {sync_direction}",
            error_code="INVALID_SYNC_DIRECTION",
            context={'sync_direction': sync_direction, 'valid_directions': valid_directions},
            suggestion=f"Use one of: {', '.join(valid_directions)}"
        )


def validate_connection_config(config: Any) -> None:
    """
    Validate connection configuration.

    Args:
        config: Configuration dictionary or JSON string

    Raises:
        MarketplaceValidationError: If configuration is invalid
    """
    if config is None:
        raise MarketplaceValidationError(
            message="Connection configuration cannot be None",
            error_code="EMPTY_CONFIG",
            context={},
            suggestion="Provide a valid configuration dictionary"
        )

    # If config is a string, try to parse as JSON
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except json.JSONDecodeError as e:
            raise MarketplaceValidationError(
                message=f"Invalid JSON in configuration: {str(e)}",
                error_code="INVALID_JSON_CONFIG",
                context={'config': config},
                suggestion="Ensure configuration is valid JSON"
            )

    # Validate config is a dictionary
    if not isinstance(config, dict):
        raise MarketplaceValidationError(
            message="Configuration must be a dictionary",
            error_code="INVALID_CONFIG_TYPE",
            context={'config_type': type(config).__name__},
            suggestion="Provide configuration as a JSON object (dictionary)"
        )


def validate_connection_id(connection_id: str) -> None:
    """
    Validate connection ID format (UUID).

    Args:
        connection_id: Connection ID string

    Raises:
        MarketplaceValidationError: If connection ID format is invalid
    """
    if not connection_id or not connection_id.strip():
        raise MarketplaceValidationError(
            message="Connection ID cannot be empty",
            error_code="EMPTY_CONNECTION_ID",
            context={},
            suggestion="Provide a valid connection ID"
        )

    # Basic UUID format validation (8-4-4-4-12 hex digits)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, connection_id.lower()):
        raise MarketplaceValidationError(
            message=f"Invalid connection ID format: {connection_id}",
            error_code="INVALID_CONNECTION_ID_FORMAT",
            context={'connection_id': connection_id},
            suggestion="Connection ID must be a valid UUID (e.g., 550e8400-e29b-41d4-a716-446655440000)"
        )


def validate_mapping_id(mapping_id: str) -> None:
    """
    Validate mapping ID format (UUID).

    Args:
        mapping_id: Mapping ID string

    Raises:
        MarketplaceValidationError: If mapping ID format is invalid
    """
    if not mapping_id or not mapping_id.strip():
        raise MarketplaceValidationError(
            message="Mapping ID cannot be empty",
            error_code="EMPTY_MAPPING_ID",
            context={},
            suggestion="Provide a valid mapping ID"
        )

    # Basic UUID format validation (8-4-4-4-12 hex digits)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, mapping_id.lower()):
        raise MarketplaceValidationError(
            message=f"Invalid mapping ID format: {mapping_id}",
            error_code="INVALID_MAPPING_ID_FORMAT",
            context={'mapping_id': mapping_id},
            suggestion="Mapping ID must be a valid UUID (e.g., 770e8400-e29b-41d4-a716-446655440000)"
        )


def validate_asset_id(asset_id: str) -> None:
    """
    Validate asset ID format (UUID).

    Args:
        asset_id: Asset ID string

    Raises:
        MarketplaceValidationError: If asset ID format is invalid
    """
    if not asset_id or not asset_id.strip():
        raise MarketplaceValidationError(
            message="Asset ID cannot be empty",
            error_code="EMPTY_ASSET_ID",
            context={},
            suggestion="Provide a valid asset ID"
        )

    # Basic UUID format validation (8-4-4-4-12 hex digits)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, asset_id.lower()):
        raise MarketplaceValidationError(
            message=f"Invalid asset ID format: {asset_id}",
            error_code="INVALID_ASSET_ID_FORMAT",
            context={'asset_id': asset_id},
            suggestion="Asset ID must be a valid UUID (e.g., 880e8400-e29b-41d4-a716-446655440000)"
        )


# Helper functions for suggestions

def _get_validation_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for validation errors"""
    error_code_upper = error_code.upper()

    if 'REQUIRED_FIELD' in error_code_upper:
        field_path = context.get('field_path', 'field')
        return f"Add the required field '{field_path}' to your request"

    if 'INVALID_VALUE' in error_code_upper or 'INVALID_DATA_TYPE' in error_code_upper:
        field_path = context.get('field_path', 'field')
        expected = context.get('expected')
        actual = context.get('actual')
        if expected and actual:
            return f"Field '{field_path}' has invalid value. Expected: {expected}, Got: {actual}"
        return f"Check the value of field '{field_path}'"

    if 'INVALID_MARKETPLACE_TYPE' in error_code_upper:
        valid_types = context.get('valid_types', [])
        if valid_types:
            return f"Use one of the supported marketplace types: {', '.join(valid_types)}"
        return "Check the marketplace type against the supported types"

    return "Review your request parameters and ensure they are valid"


def _get_authentication_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for authentication errors"""
    return "Check your marketplace connection credentials. Verify API keys, tokens, or authentication settings are correct"


def _get_connection_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for connection errors"""
    error_code_upper = error_code.upper()

    if 'TIMEOUT' in error_code_upper:
        return "Connection timed out. Check your network connection and marketplace service availability"

    if 'NETWORK_ERROR' in error_code_upper:
        return "Network error occurred. Check your network connection and firewall settings"

    return "Unable to connect to marketplace. Verify connection settings and network connectivity"


def _get_sync_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for sync errors"""
    return "Synchronization failed. Check connection status, marketplace service availability, and sync job details"


def _get_http_error_suggestion(status_code: int, endpoint: Optional[str] = None) -> str:
    """Get suggestion for HTTP errors"""
    if status_code == 400:
        return "Check your request parameters and ensure they are valid"
    elif status_code == 401:
        return "Authentication failed. Run 'datahub login' to authenticate"
    elif status_code == 403:
        return "You don't have permission to perform this operation. Check your role and permissions"
    elif status_code == 404:
        if endpoint and 'connection' in endpoint.lower():
            return "Connection not found. Check that the connection ID is correct"
        return "Resource not found. Check that the ID is correct"
    elif status_code == 409:
        return "Conflict: The resource may already exist or be in an invalid state (e.g., connection has active sync jobs)"
    elif status_code == 422:
        return "Validation failed. Check your input data"
    elif status_code == 429:
        return "Rate limit exceeded. Wait before retrying"
    elif status_code >= 500:
        return "Server error. Please try again later or contact support"
    return "Check your request and try again"
