"""
ODH ML Model Registry Error Handling for CLI

Provides comprehensive error handling for ODH ML model registry operations in the CLI,
mapping backend errors to user-friendly messages with actionable guidance.
"""

import json
import re
from typing import Any

from .odps_errors import ODPSCLIError, handle_api_error


class ODHMLModelError(ODPSCLIError):
    """
    Base exception class for ODH ML Model Registry CLI errors.

    Provides structured error information with user-friendly messages
    and actionable guidance.
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        suggestion: str | None = None,
        original_error: Exception | None = None,
    ):
        """
        Initialize ODH ML Model Registry CLI error.

        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            context: Additional context information
            suggestion: Actionable suggestion for resolving the error
            original_error: Original exception that caused this error
        """
        super().__init__(message, error_code, context, suggestion, original_error)


class ODHMLModelValidationError(ODHMLModelError):
    """Error for ODH ML model validation failures"""


class ODHMLModelNotFoundError(ODHMLModelError):
    """Error for ODH ML model not found"""


class ODHMLModelConflictError(ODHMLModelError):
    """Error for ODH ML model conflicts (e.g., duplicate model versions)"""


class ODHMLModelParameterError(ODHMLModelError):
    """Error for invalid ODH ML model command parameters"""


def validate_uuid(uuid_string: str, field_name: str = "ID") -> None:
    """
    Validate UUID format.

    Args:
        uuid_string: UUID string to validate
        field_name: Name of the field for error messages

    Raises:
        ODHMLModelParameterError: If UUID format is invalid
    """
    if not uuid_string or not uuid_string.strip():
        raise ODHMLModelParameterError(
            message=f"{field_name} cannot be empty",
            error_code="EMPTY_UUID",
            context={"field_name": field_name},
            suggestion=f"Provide a valid {field_name}",
        )

    # Basic UUID format validation (8-4-4-4-12 hex digits)
    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    if not re.match(uuid_pattern, uuid_string.strip()):
        raise ODHMLModelParameterError(
            message=f"Invalid {field_name} format: {uuid_string}",
            error_code="INVALID_UUID_FORMAT",
            context={"field_name": field_name, "uuid": uuid_string},
            suggestion=f"{field_name} must be a valid UUID (e.g., 123e4567-e89b-12d3-a456-426614174000)",
        )


def validate_model_type(model_type: str) -> None:
    """
    Validate model type.

    Args:
        model_type: Model type string to validate

    Raises:
        ODHMLModelParameterError: If model type is invalid
    """
    valid_types = [
        "CLASSIFICATION",
        "REGRESSION",
        "CLUSTERING",
        "NLP",
        "COMPUTER_VISION",
        "RECOMMENDATION",
        "TIME_SERIES",
        "ANOMALY_DETECTION",
        "OTHER",
    ]
    if model_type not in valid_types:
        raise ODHMLModelParameterError(
            message=f"Invalid model type: {model_type}",
            error_code="INVALID_MODEL_TYPE",
            context={"model_type": model_type, "valid_types": valid_types},
            suggestion=f"Use one of: {', '.join(valid_types)}",
        )


def validate_model_status(status: str) -> None:
    """
    Validate model status.

    Args:
        status: Model status string to validate

    Raises:
        ODHMLModelParameterError: If model status is invalid
    """
    valid_statuses = ["TRAINING", "TRAINED", "DEPLOYED", "FAILED", "ARCHIVED"]
    if status not in valid_statuses:
        raise ODHMLModelParameterError(
            message=f"Invalid model status: {status}",
            error_code="INVALID_MODEL_STATUS",
            context={"status": status, "valid_statuses": valid_statuses},
            suggestion=f"Use one of: {', '.join(valid_statuses)}",
        )


def handle_ml_api_error(
    response_text: str, status_code: int, endpoint: str | None = None
) -> ODHMLModelError:
    """
    Handle API error response and convert to ODH ML Model Registry CLI error.

    Args:
        response_text: Response text from API
        status_code: HTTP status code
        endpoint: API endpoint that failed

    Returns:
        ODHMLModelError instance
    """
    error_data = {}

    # Try to parse JSON error response
    try:
        error_data = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON, use raw text
        error_data = {"error": {"message": response_text or "Unknown error"}}

    # Try to parse as ODPS error first (for consistency)
    try:
        odps_error = handle_api_error(response_text, status_code, endpoint)
        # Convert to ODH ML Model error
        if status_code == 404:
            return ODHMLModelNotFoundError(
                message=odps_error.message,
                error_code=odps_error.error_code or "MODEL_NOT_FOUND",
                context=odps_error.context,
                suggestion=odps_error.suggestion or "Check that the model ID is correct",
                original_error=odps_error.original_error,
            )
        elif status_code == 409:
            return ODHMLModelConflictError(
                message=odps_error.message,
                error_code=odps_error.error_code or "MODEL_CONFLICT",
                context=odps_error.context,
                suggestion=odps_error.suggestion
                or "Model may already exist or be in an invalid state",
                original_error=odps_error.original_error,
            )
        elif status_code == 422:
            return ODHMLModelValidationError(
                message=odps_error.message,
                error_code=odps_error.error_code or "MODEL_VALIDATION_ERROR",
                context=odps_error.context,
                suggestion=odps_error.suggestion or "Check your input data",
                original_error=odps_error.original_error,
            )
        else:
            return ODHMLModelError(
                message=odps_error.message,
                error_code=odps_error.error_code or "ML_MODEL_ERROR",
                context=odps_error.context,
                suggestion=odps_error.suggestion,
                original_error=odps_error.original_error,
            )
    except Exception:
        # Fallback to generic error
        error_info = error_data.get("error", {})
        if isinstance(error_info, str):
            error_info = {"message": error_info}

        error_message = error_info.get("message", response_text or "Unknown error")
        error_code = error_info.get("code") or error_data.get("error_code") or f"HTTP_{status_code}"

        context: dict[str, Any] = {}
        if endpoint:
            context["endpoint"] = endpoint
        context["status_code"] = status_code

        suggestion = _get_ml_error_suggestion(status_code, endpoint)

        if status_code == 404:
            return ODHMLModelNotFoundError(
                message=error_message, error_code=error_code, context=context, suggestion=suggestion
            )
        elif status_code == 409:
            return ODHMLModelConflictError(
                message=error_message, error_code=error_code, context=context, suggestion=suggestion
            )
        elif status_code == 422:
            return ODHMLModelValidationError(
                message=error_message, error_code=error_code, context=context, suggestion=suggestion
            )
        else:
            return ODHMLModelError(
                message=error_message, error_code=error_code, context=context, suggestion=suggestion
            )


def validate_json(json_string: str, field_name: str = "JSON") -> dict:
    """
    Validate and parse JSON string.

    Args:
        json_string: JSON string to validate
        field_name: Name of the field for error messages

    Returns:
        Parsed JSON dictionary

    Raises:
        ODHMLModelParameterError: If JSON is invalid
    """
    if not json_string or not json_string.strip():
        raise ODHMLModelParameterError(
            message=f"{field_name} cannot be empty",
            error_code="EMPTY_JSON",
            context={"field_name": field_name},
            suggestion=f"Provide a valid {field_name} string",
        )

    try:
        import json

        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ODHMLModelParameterError(
            message=f"Invalid {field_name} format: {e!s}",
            error_code="INVALID_JSON_FORMAT",
            context={"field_name": field_name, "json_string": json_string[:100]},
            suggestion=f"{field_name} must be valid JSON. Check syntax and formatting.",
        )


def _get_ml_error_suggestion(status_code: int, endpoint: str | None = None) -> str:
    """Get suggestion for ML model registry errors"""
    if status_code == 400:
        return "Check your request parameters and ensure they are valid"
    elif status_code == 401:
        return "Authentication failed. Run 'datahub login' to authenticate"
    elif status_code == 403:
        return "You don't have permission to perform this operation"
    elif status_code == 404:
        if endpoint and "model" in endpoint.lower():
            return "Model not found. Check that the model ID is correct"
        return "Resource not found. Check that the ID is correct"
    elif status_code == 409:
        return "Conflict: The model may already exist or be in an invalid state"
    elif status_code == 422:
        return "Validation failed. Check your input data (ODH model ID, version, model type, etc.)"
    elif status_code == 429:
        return "Rate limit exceeded. Wait before retrying"
    elif status_code >= 500:
        return "Server error. Please try again later or contact support"
    return "Check your request and try again"
