"""
BaaS Error Handling for CLI

Provides comprehensive error handling for BaaS operations in the CLI,
mapping backend BaaS errors to user-friendly messages with actionable guidance.
"""
import json
from typing import Optional, Dict, Any
import click


class BaaSCLIError(click.ClickException):
    """
    Base exception class for BaaS CLI errors.

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
        Initialize BaaS CLI error.

        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            context: Additional context information
            suggestion: Actionable suggestion for resolving the error
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.error_code = error_code or "BAAS_CLI_ERROR"
        self.context = context or {}
        self.suggestion = suggestion
        self.original_error = original_error

    def format_message(self) -> str:
        """Format error message with context and suggestions"""
        lines = [self.message]

        if self.context:
            # Add context information
            if 'api_key_id' in self.context:
                lines.append(f"  API Key ID: {self.context['api_key_id']}")
            if 'name' in self.context:
                lines.append(f"  Name: {self.context['name']}")
            if 'tier' in self.context:
                lines.append(f"  Tier: {self.context['tier']}")
            if 'endpoint' in self.context:
                lines.append(f"  Endpoint: {self.context['endpoint']}")

        if self.suggestion:
            lines.append(f"\n💡 Suggestion: {self.suggestion}")

        return "\n".join(lines)


class BaaSValidationError(BaaSCLIError):
    """Error for BaaS validation failures"""
    pass


class BaaSAuthenticationError(BaaSCLIError):
    """Error for BaaS authentication failures"""
    pass


class BaaSAuthorizationError(BaaSCLIError):
    """Error for BaaS authorization failures"""
    pass


class BaaSQuotaError(BaaSCLIError):
    """Error for BaaS quota/limit exceeded"""
    pass


class BaaSNotFoundError(BaaSCLIError):
    """Error for BaaS resource not found"""
    pass


class BaaSConflictError(BaaSCLIError):
    """Error for BaaS resource conflicts"""
    pass


def parse_baas_api_error_response(error_data: Dict[str, Any]) -> Optional[BaaSCLIError]:
    """
    Parse API error response and convert to appropriate BaaS CLI error.

    Args:
        error_data: Error data from API response

    Returns:
        BaaSCLIError instance or None if cannot parse
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
            'VALIDATION', 'INVALID', 'REQUIRED', 'BAD_REQUEST'
        ]):
            suggestion = _get_validation_suggestion(error_code, context)
            return BaaSValidationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Authentication errors
        if any(code in error_code_upper for code in [
            'AUTHENTICATION', 'UNAUTHORIZED', 'INVALID_CREDENTIALS'
        ]):
            return BaaSAuthenticationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion="Run 'datahub login' to authenticate or check your API key"
            )

        # Authorization errors
        if any(code in error_code_upper for code in [
            'AUTHORIZATION', 'FORBIDDEN', 'PERMISSION_DENIED'
        ]):
            return BaaSAuthorizationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion="You don't have permission to perform this operation"
            )

        # Quota errors
        if any(code in error_code_upper for code in [
            'QUOTA', 'LIMIT_EXCEEDED', 'RATE_LIMIT'
        ]):
            return BaaSQuotaError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion="Quota or rate limit exceeded. Wait before retrying or upgrade your tier"
            )

        # Not found errors
        if any(code in error_code_upper for code in [
            'NOT_FOUND', 'RESOURCE_NOT_FOUND'
        ]):
            return BaaSNotFoundError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion="Check that the API key ID is correct"
            )

        # Conflict errors
        if any(code in error_code_upper for code in [
            'CONFLICT', 'ALREADY_EXISTS', 'DUPLICATE'
        ]):
            return BaaSConflictError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion="A resource with this name may already exist. Use a different name"
            )

    # Default to generic BaaS error
    return BaaSCLIError(
        message=error_message,
        error_code=error_code or "BAAS_ERROR",
        context=context
    )


def handle_baas_api_error(
    response_text: str,
    status_code: int,
    endpoint: Optional[str] = None
) -> BaaSCLIError:
    """
    Handle API error response and convert to BaaS CLI error.

    Args:
        response_text: Response text from API
        status_code: HTTP status code
        endpoint: API endpoint that failed

    Returns:
        BaaSCLIError instance
    """
    error_data = {}

    # Try to parse JSON error response
    try:
        error_data = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON, use raw text
        error_data = {'error': {'message': response_text or 'Unknown error'}}

    # Try to parse as BaaS error
    baas_error = parse_baas_api_error_response(error_data)
    if baas_error:
        if endpoint:
            baas_error.context['endpoint'] = endpoint
        baas_error.context['status_code'] = status_code
        # Ensure suggestion is set if not already present
        if not baas_error.suggestion:
            baas_error.suggestion = _get_http_error_suggestion(status_code, endpoint)
        return baas_error

    # Fallback to generic error
    error_info = error_data.get('error', {})
    if isinstance(error_info, str):
        error_info = {'message': error_info}

    error_message = error_info.get('message', response_text or 'Unknown error')
    error_code_raw = error_info.get('code') or error_data.get('error_code') or f'HTTP_{status_code}'
    # Ensure error_code is a string (handle case where it might be a dict or other type)
    if isinstance(error_code_raw, str):
        error_code = error_code_raw
    else:
        error_code = f'HTTP_{status_code}'

    suggestion = _get_http_error_suggestion(status_code, endpoint)

    context: Dict[str, Any] = {}
    if endpoint:
        context['endpoint'] = endpoint
    context['status_code'] = status_code

    return BaaSCLIError(
        message=error_message,
        error_code=error_code,
        context=context,
        suggestion=suggestion
    )


# Helper functions for suggestions

def _get_validation_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for validation errors"""
    error_code_upper = error_code.upper()

    if 'REQUIRED' in error_code_upper or 'MISSING' in error_code_upper:
        field = context.get('field', 'field')
        return f"Provide the required field '{field}'"

    if 'INVALID_TIER' in error_code_upper:
        return "Tier must be one of: FREE, PRO, ENTERPRISE"

    if 'INVALID_DATE' in error_code_upper or 'EXPIRES_AT' in error_code_upper:
        return "Expiration date must be in the future and in ISO format (e.g., 2025-12-31T23:59:59Z)"

    if 'DUPLICATE_NAME' in error_code_upper:
        return "API key name must be unique. Use a different name"

    return "Check your input parameters and ensure they are valid"


def _get_http_error_suggestion(status_code: int, endpoint: Optional[str] = None) -> str:
    """Get suggestion for HTTP errors"""
    if status_code == 400:
        return "Check your request parameters and ensure they are valid"
    elif status_code == 401:
        return "Authentication failed. Run 'datahub login' to authenticate"
    elif status_code == 403:
        return "You don't have permission to perform this operation"
    elif status_code == 404:
        if endpoint and 'api-keys' in endpoint:
            return "API key not found. Check that the API key ID is correct"
        return "Resource not found. Check that the ID is correct"
    elif status_code == 409:
        return "Conflict: The resource may already exist or be in an invalid state"
    elif status_code == 422:
        return "Validation failed. Check your input data"
    elif status_code == 429:
        return "Rate limit exceeded. Wait before retrying"
    elif status_code >= 500:
        return "Server error. Please try again later or contact support"
    return "Check your request and try again"
