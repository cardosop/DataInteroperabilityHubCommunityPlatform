"""
Custom exception handler for REST API

Provides standardized error response format across all API endpoints.
"""
import uuid
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import structlog

logger = structlog.get_logger(__name__)


# Error code mappings
ERROR_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: 'VALIDATION_ERROR',
    status.HTTP_401_UNAUTHORIZED: 'AUTH_UNAUTHORIZED',
    status.HTTP_403_FORBIDDEN: 'AUTH_FORBIDDEN',
    status.HTTP_404_NOT_FOUND: 'NOT_FOUND',
    status.HTTP_409_CONFLICT: 'CONFLICT_ERROR',
    status.HTTP_429_TOO_MANY_REQUESTS: 'RATE_LIMIT_EXCEEDED',
    status.HTTP_500_INTERNAL_SERVER_ERROR: 'INTERNAL_ERROR',
    status.HTTP_502_BAD_GATEWAY: 'SERVICE_UNAVAILABLE',
    status.HTTP_503_SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE',
}


def get_error_code(exc, http_status):
    """
    Get error code from exception or HTTP status.

    Args:
        exc: Exception instance
        http_status: HTTP status code

    Returns:
        Error code string
    """
    # Check if exception has a code attribute
    if hasattr(exc, 'code') and exc.code:
        return exc.code

    # Map HTTP status to error code
    return ERROR_CODE_MAP.get(http_status, 'UNKNOWN_ERROR')


def get_error_message(exc, http_status):
    """
    Get user-friendly error message.

    Args:
        exc: Exception instance
        http_status: HTTP status code

    Returns:
        Error message string
    """
    # Check if exception has a message attribute
    if hasattr(exc, 'message') and exc.message:
        return exc.message

    # Use exception string representation
    message = str(exc)

    # Remove stack traces and internal details
    if 'Traceback' in message:
        message = message.split('Traceback')[0].strip()

    # Default messages for common status codes
    if not message or message == 'None':
        default_messages = {
            status.HTTP_400_BAD_REQUEST: 'Invalid request',
            status.HTTP_401_UNAUTHORIZED: 'Authentication required',
            status.HTTP_403_FORBIDDEN: 'Permission denied',
            status.HTTP_404_NOT_FOUND: 'Resource not found',
            status.HTTP_409_CONFLICT: 'Resource conflict',
            status.HTTP_429_TOO_MANY_REQUESTS: 'Rate limit exceeded',
            status.HTTP_500_INTERNAL_SERVER_ERROR: 'Internal server error',
        }
        message = default_messages.get(http_status, 'An error occurred')

    return message


def get_error_details(exc, response):
    """
    Extract error details from exception.

    Args:
        exc: Exception instance
        response: DRF response object

    Returns:
        Tuple of (details_dict, original_data_dict) for field-level access
    """
    details = {}
    original_data = {}

    # Check if exception has detail attribute
    if hasattr(exc, 'detail'):
        if isinstance(exc.detail, dict):
            details = exc.detail
            original_data = exc.detail.copy()
        elif isinstance(exc.detail, list):
            details = {'errors': exc.detail}
            original_data = {'errors': exc.detail}
        else:
            details = {'message': str(exc.detail)}
            original_data = {'message': str(exc.detail)}

    # Check response data for validation errors
    elif response and hasattr(response, 'data'):
        if isinstance(response.data, dict):
            # Preserve original data for field-level access
            original_data = response.data.copy()

            # DRF validation errors
            if 'non_field_errors' in response.data:
                details['non_field_errors'] = response.data['non_field_errors']

            # Field-specific errors
            field_errors = []
            for field, errors in response.data.items():
                if field != 'non_field_errors':
                    if isinstance(errors, list):
                        for error in errors:
                            field_errors.append({
                                'field': field,
                                'message': str(error),
                                'code': 'VALIDATION_ERROR'
                            })
                    else:
                        field_errors.append({
                            'field': field,
                            'message': str(errors),
                            'code': 'VALIDATION_ERROR'
                        })

            if field_errors:
                details['field_errors'] = field_errors
        elif isinstance(response.data, list):
            details = {'errors': response.data}
            original_data = {'errors': response.data}

    return details if details else None, original_data


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error format.

    Returns error responses in the format:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "http_status": 400,
            "request_id": "uuid",
            "timestamp": "2025-01-15T10:30:00Z",
            "details": {}
        }
    }
    """
    response = exception_handler(exc, context)
    request = context.get('request')

    # Generate request ID if not present
    request_id = getattr(request, 'id', None) if request else None
    if not request_id:
        request_id = str(uuid.uuid4())
        if request:
            request.id = request_id

    # Get HTTP status code
    if response is not None:
        http_status = response.status_code
        # Capture original response data BEFORE we modify it (for field-level access)
        original_response_data = response.data.copy() if hasattr(response, 'data') and isinstance(response.data, dict) else {}
    else:
        # Unhandled exception, default to 500
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        response = Response(status=http_status)
        original_response_data = {}

    # Build standardized error response
    error_code = get_error_code(exc, http_status)
    error_message = get_error_message(exc, http_status)
    error_details, original_data = get_error_details(exc, response)

    custom_response_data = {
        'error': {
            'code': error_code,
            'message': error_message,
            'http_status': http_status,
            'request_id': request_id,
            'timestamp': timezone.now().isoformat(),
        }
    }

    # Add details if available
    if error_details:
        custom_response_data['error']['details'] = error_details

        # For rate limit errors, ensure retry_after is in details
        if http_status == status.HTTP_429_TOO_MANY_REQUESTS:
            if isinstance(error_details, dict) and 'retry_after' not in error_details:
                # Try to get retry_after from exception detail if available
                if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
                    retry_after = exc.detail.get('retry_after')
                    if retry_after is not None:
                        custom_response_data['error']['details']['retry_after'] = retry_after

    # For validation errors (400), also preserve field-level access for backward compatibility
    # This allows tests to access response.data['email'] while still providing standardized format
    if http_status == status.HTTP_400_BAD_REQUEST:
        # Use captured original response data (before our handler modified it) - this has the actual field errors
        source_data = original_response_data if original_response_data else original_data
        if source_data:
            # Preserve original field-level errors at top level
            for field_name, field_value in source_data.items():
                if field_name not in ['error']:  # Don't overwrite our error structure
                    # Extract message from ErrorDetail if needed
                    if hasattr(field_value, 'string'):
                        custom_response_data[field_name] = field_value.string
                    elif isinstance(field_value, list) and len(field_value) > 0:
                        # Handle list of errors - take first error message
                        if hasattr(field_value[0], 'string'):
                            custom_response_data[field_name] = field_value[0].string
                        else:
                            custom_response_data[field_name] = str(field_value[0])
                    else:
                        custom_response_data[field_name] = str(field_value)

            # Also handle non_field_errors - extract field names from error messages
            if 'non_field_errors' in source_data:
                non_field_errors = source_data['non_field_errors']
                if isinstance(non_field_errors, list):
                    for error in non_field_errors:
                        error_str = str(error) if not hasattr(error, 'string') else error.string
                        # Try to extract field name from error message (e.g., "File size (X) exceeds limit")
                        if 'size' in error_str.lower() and 'size' not in custom_response_data:
                            custom_response_data['size'] = error_str
                        elif 'file' in error_str.lower() and 'file' not in custom_response_data:
                            custom_response_data['file'] = error_str

    # Log error using enhanced error logger
    from hub.apps.core.error_handling.error_logging import ErrorLogger
    from hub.apps.core.error_handling.error_tracking import get_error_tracker

    error_logger = ErrorLogger()
    error_tracker = get_error_tracker()

    # Get tenant and user IDs from request
    tenant_id = None
    user_id = None
    if request:
        if hasattr(request, 'tenant_id'):
            tenant_id = str(request.tenant_id)
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)

    # Log error
    error_logger.log_error(
        error=exc,
        error_code=error_code,
        message=error_message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        additional_context={
            "path": request.path if request else None,
            "method": request.method if request else None,
        },
        level="error",
    )

    # Track error in Sentry
    error_tracker.track_error(
        error=exc,
        error_code=error_code,
        message=error_message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        context={
            "path": request.path if request else None,
            "method": request.method if request else None,
        },
        level="error",
    )

    # Set user context for Sentry
    if user_id:
        error_tracker.set_user(user_id)
    if tenant_id:
        error_tracker.set_tenant(tenant_id)

    response.data = custom_response_data
    return response

