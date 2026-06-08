"""
ODPS Error Handling for CLI

Provides comprehensive error handling for ODPS operations in the CLI,
mapping backend ODPS errors to user-friendly messages with actionable guidance.
"""
import json
import re
from typing import Optional, Dict, Any, List
import click

from ._mvp_detection import detect_mvp_gated_feature, extract_environment_url
from ._mvp_gates import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_MESSAGE_TEMPLATE,
)


class ODPSCLIError(click.ClickException):
    """
    Base exception class for ODPS CLI errors.

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
        Initialize ODPS CLI error.

        Args:
            message: User-friendly error message
            error_code: Machine-readable error code
            context: Additional context information
            suggestion: Actionable suggestion for resolving the error
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.error_code = error_code or "ODPS_CLI_ERROR"
        self.context = context or {}
        self.suggestion = suggestion
        self.original_error = original_error

    def format_message(self) -> str:
        """Format error message with context and suggestions"""
        lines = [self.message]

        if self.context:
            # Add context information
            if 'field_path' in self.context:
                lines.append(f"  Field: {self.context['field_path']}")
            if 'expected' in self.context and 'actual' in self.context:
                lines.append(f"  Expected: {self.context['expected']}")
                lines.append(f"  Actual: {self.context['actual']}")
            if 'file_path' in self.context:
                lines.append(f"  File: {self.context['file_path']}")
            if 'contract_id' in self.context:
                lines.append(f"  Contract ID: {self.context['contract_id']}")
            if 'ref_path' in self.context:
                lines.append(f"  Reference: {self.context['ref_path']}")

        if self.suggestion:
            lines.append(f"\n💡 Suggestion: {self.suggestion}")

        return "\n".join(lines)


class ODPSValidationError(ODPSCLIError):
    """Error for ODPS validation failures"""
    pass


class ODPSRefResolutionError(ODPSCLIError):
    """Error for ODPS reference resolution failures"""
    pass


class ODPSNormalizationError(ODPSCLIError):
    """Error for ODPS normalization failures"""
    pass


class ODPSExportError(ODPSCLIError):
    """Error for ODPS export failures"""
    pass


class ODPSLinkingError(ODPSCLIError):
    """Error for ODPS linking failures"""
    pass


class ODPSParameterError(ODPSCLIError):
    """Error for invalid ODPS command parameters"""
    pass


class ODPSFeatureGatedError(ODPSCLIError):
    """
    Raised when a CLI request hits an MVP-gated backend route.

    Carries the stable ``code='MVP_FEATURE_GATED'`` plus structured fields
    (``feature``, ``prefix``, ``endpoint``, ``environment_url``) so
    programmatic consumers can branch on ``error.code`` without parsing the
    rendered message.

    Subclasses :class:`ODPSCLIError` so existing ``except ODPSCLIError``
    handlers continue to catch these unchanged (backwards-compat contract).
    """

    def __init__(
        self,
        feature: str,
        prefix: str,
        endpoint: str,
        environment_url: str,
        original_error: Optional[Exception] = None,
    ):
        rendered = MVP_GATED_MESSAGE_TEMPLATE.format(
            feature=feature,
            endpoint=endpoint or "(unknown)",
            environment_url=environment_url or "(unknown)",
            code=MVP_FEATURE_GATED_CODE,
        )
        super().__init__(
            message=rendered,
            error_code=MVP_FEATURE_GATED_CODE,
            context={
                "feature": feature,
                "prefix": prefix,
                "endpoint": endpoint,
                "environment_url": environment_url,
            },
            suggestion=(
                f"'{feature}' is gated until the post-MVP release. Use "
                "'datahub --help' to see commands available in the current MVP."
            ),
            original_error=original_error,
        )
        # Promote structured fields to top-level attributes for ergonomic
        # programmatic access (``err.feature`` instead of ``err.context['feature']``).
        self.code = MVP_FEATURE_GATED_CODE
        self.feature = feature
        self.prefix = prefix
        self.endpoint = endpoint
        self.environment_url = environment_url


def parse_api_error_response(error_data: Dict[str, Any]) -> Optional[ODPSCLIError]:
    """
    Parse API error response and convert to appropriate ODPS CLI error.

    Args:
        error_data: Error data from API response

    Returns:
        ODPSCLIError instance or None if cannot parse
    """
    if not isinstance(error_data, dict):
        return None

    # Extract error information
    error_info = error_data.get('error', {})
    if isinstance(error_info, str):
        error_info = {'message': error_info}

    error_code = error_info.get('code') or error_info.get('error_code') or error_data.get('error_code')
    error_message = error_info.get('message') or error_info.get('user_message') or error_data.get('message', 'Unknown error')
    technical_message = error_info.get('technical_message') or error_data.get('technical_message')
    context_raw = error_info.get('context') or error_data.get('context', {})
    # Ensure context is a dict
    if not isinstance(context_raw, dict):
        context: Dict[str, Any] = {}
    else:
        context = context_raw
    recovery_strategy = error_info.get('recovery_strategy') or error_data.get('recovery_strategy')

    # Map error codes to specific error types
    if error_code:
        error_code_upper = error_code.upper()

        # Validation errors
        if any(error_code_upper.startswith(code) for code in [
            'VALIDATION', 'SCHEMA_VALIDATION', 'REQUIRED_FIELD',
            'INVALID_DATA_TYPE', 'INVALID_VALUE', 'VERSION_MISMATCH'
        ]):
            suggestion = _get_validation_suggestion(error_code, context)
            return ODPSValidationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Reference resolution errors
        if any(error_code_upper.startswith(code) for code in [
            'REF_RESOLUTION', 'RESOLUTION_FAILED', 'INVALID_REF',
            'CIRCULAR_REF', 'TIMEOUT', 'RATE_LIMIT', 'SECURITY_VIOLATION'
        ]):
            suggestion = _get_ref_resolution_suggestion(error_code, context)
            return ODPSRefResolutionError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Normalization errors
        if any(error_code_upper.startswith(code) for code in [
            'NORMALIZATION', 'FIELD_MAPPING', 'TYPE_CONVERSION',
            'MISSING_REQUIRED_FIELD'
        ]):
            suggestion = _get_normalization_suggestion(error_code, context)
            return ODPSNormalizationError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Export errors
        if any(error_code_upper.startswith(code) for code in [
            'EXPORT', 'SERIALIZATION', 'FORMAT_NOT_SUPPORTED', 'FILE_WRITE'
        ]):
            suggestion = _get_export_suggestion(error_code, context)
            return ODPSExportError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

        # Linking errors
        if any(error_code_upper.startswith(code) for code in [
            'LINKING', 'LINK_RESOLUTION', 'LINK_VALIDATION', 'CIRCULAR_REFERENCE', 'INVALID_LINK'
        ]):
            suggestion = _get_linking_suggestion(error_code, context)
            return ODPSLinkingError(
                message=error_message,
                error_code=error_code,
                context=context,
                suggestion=suggestion
            )

    # Default to generic ODPS error
    return ODPSCLIError(
        message=error_message,
        error_code=error_code or "ODPS_ERROR",
        context=context
    )


def handle_api_error(
    response_text: str,
    status_code: int,
    endpoint: Optional[str] = None,
    request_url: Optional[str] = None,
) -> ODPSCLIError:
    """
    Handle API error response and convert to ODPS CLI error.

    Args:
        response_text: Response text from API
        status_code: HTTP status code
        endpoint: API endpoint that failed (relative path under /api/v1/)
        request_url: Full request URL (used to derive ``environment_url`` and
            to detect MVP-gated routes when only the URL is available).

    Returns:
        ODPSCLIError instance. For HTTP 404 against an MVP-gated prefix this
        is an :class:`ODPSFeatureGatedError` (subclass of ODPSCLIError) so
        existing ``except ODPSCLIError:`` handlers keep working unchanged.
    """
    # Intercept MVP-gated 404s BEFORE any generic JSON-error fall-through.
    # We try ``endpoint`` first (which is already the post-/api/v1/ relative
    # path computed by the api_client) and fall back to ``request_url`` so
    # callers can pass either or both.
    if status_code == 404:
        detection_input = endpoint or request_url or ""
        detected = detect_mvp_gated_feature(detection_input)
        if detected is not None:
            prefix, feature = detected
            return ODPSFeatureGatedError(
                feature=feature,
                prefix=prefix,
                endpoint=endpoint or detection_input,
                environment_url=extract_environment_url(request_url or ""),
            )

    error_data = {}

    # Try to parse JSON error response
    try:
        error_data = json.loads(response_text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON, use raw text
        error_data = {'error': {'message': response_text or 'Unknown error'}}

    # Try to parse as ODPS error
    odps_error = parse_api_error_response(error_data)
    if odps_error:
        if endpoint:
            odps_error.context['endpoint'] = endpoint
        odps_error.context['status_code'] = status_code
        # Ensure suggestion is set if not already present
        if not odps_error.suggestion:
            odps_error.suggestion = _get_http_error_suggestion(status_code, endpoint)
        return odps_error

    # Fallback to generic error
    error_info = error_data.get('error', {})
    if isinstance(error_info, str):
        error_info = {'message': error_info}

    error_message = error_info.get('message', response_text or 'Unknown error')
    error_code = error_info.get('code') or error_data.get('error_code') or f'HTTP_{status_code}'

    suggestion = _get_http_error_suggestion(status_code, endpoint)

    context: Dict[str, Any] = {}
    if endpoint:
        context['endpoint'] = endpoint
    context['status_code'] = status_code

    return ODPSCLIError(
        message=error_message,
        error_code=error_code,
        context=context,
        suggestion=suggestion
    )


def validate_odps_version(version: Optional[str]) -> None:
    """
    Validate ODPS version format.

    Args:
        version: Version string (e.g., "4.1", "4.0")

    Raises:
        ODPSParameterError: If version format is invalid
    """
    if version is None:
        return

    # ODPS version format: major.minor (e.g., 4.1, 4.0)
    version_pattern = r'^\d+\.\d+$'
    if not re.match(version_pattern, version):
        raise ODPSParameterError(
            message=f"Invalid ODPS version format: {version}",
            error_code="INVALID_VERSION_FORMAT",
            context={'version': version},
            suggestion="ODPS version should be in format 'major.minor' (e.g., '4.1', '4.0')"
        )


def validate_odcs_version(version: Optional[str]) -> None:
    """
    Validate ODCS version format.

    Validates that the version string matches the expected format and is a supported version.
    ODCS versions follow the format: major.minor[.patch] or major.minor[-suffix]
    Supported versions: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

    Args:
        version: Version string to validate (e.g., "3.0.2", "3.0.1", "3.0.0-preview", "2.2.2")

    Raises:
        ODPSParameterError: If version format is invalid or version is not supported

    Example:
        >>> validate_odcs_version("3.0.2")  # Valid
        >>> validate_odcs_version("3.0.0-preview")  # Valid
        >>> validate_odcs_version("invalid")  # Raises ODPSParameterError
        >>> validate_odcs_version("99.99.99")  # Raises ODPSParameterError (not supported)
    """
    if version is None:
        return  # Optional parameter, None is valid

    if not isinstance(version, str):
        raise ODPSParameterError(
            message=f"ODCS version must be a string, got {type(version).__name__}",
            error_code="INVALID_VERSION_FORMAT",
            context={'version': version},
            suggestion="ODCS version should be a string (e.g., '3.0.2', '3.0.0-preview')"
        )

    version = version.strip()

    # ODCS version format: major.minor[.patch] or major.minor[-suffix]
    # Examples: "3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"
    version_pattern = r'^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9-]+)?$'
    if not re.match(version_pattern, version):
        raise ODPSParameterError(
            message=f"Invalid ODCS version format: {version}",
            error_code="INVALID_VERSION_FORMAT",
            context={'version': version},
            suggestion="ODCS version should be in format 'X.Y' or 'X.Y.Z' or 'X.Y-suffix' (e.g., '3.0.2', '3.0.0-preview')"
        )

    # Check if version is supported
    # Supported ODCS versions (must match backend supported versions)
    supported_versions = ['2.2.2', '3.0.0', '3.0.0-preview', '3.0.1', '3.0.2']
    if version not in supported_versions:
        raise ODPSParameterError(
            message=f"ODCS version '{version}' is not supported. Supported versions: {', '.join(supported_versions)}",
            error_code="UNSUPPORTED_VERSION",
            context={'version': version, 'supported_versions': supported_versions},
            suggestion=f"Use one of the supported versions: {', '.join(supported_versions)}"
        )


def validate_contract_id(contract_id: str, id_type: str = "contract") -> None:
    """
    Validate contract ID format.

    Args:
        contract_id: Contract ID string
        id_type: Type of ID (contract, odcs, odps)

    Raises:
        ODPSParameterError: If contract ID format is invalid
    """
    if not contract_id or not contract_id.strip():
        raise ODPSParameterError(
            message=f"{id_type.capitalize()} ID cannot be empty",
            error_code="EMPTY_ID",
            context={'id_type': id_type},
            suggestion=f"Provide a valid {id_type} ID"
        )

    # Basic validation: should not contain only whitespace
    if contract_id.strip() != contract_id:
        raise ODPSParameterError(
            message=f"{id_type.capitalize()} ID contains leading/trailing whitespace",
            error_code="INVALID_ID_FORMAT",
            context={'id_type': id_type, 'contract_id': contract_id},
            suggestion=f"Remove whitespace from {id_type} ID"
        )


def validate_file_format(file_path: str, allowed_formats: Optional[List[str]] = None) -> str:
    """
    Validate file format and return normalized format.

    Args:
        file_path: Path to file
        allowed_formats: List of allowed formats (default: ['JSON', 'YAML'])

    Returns:
        Normalized format string ('JSON' or 'YAML')

    Raises:
        ODPSParameterError: If file format is invalid or unsupported
    """
    if allowed_formats is None:
        allowed_formats = ['JSON', 'YAML']

    # Detect format from extension
    if file_path.endswith('.json'):
        format_type = 'JSON'
    elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
        format_type = 'YAML'
    else:
        # Try to detect from content (basic check)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_char = f.read(1)
                if first_char == '{':
                    format_type = 'JSON'
                elif first_char in ['-', 's']:  # YAML might start with --- or schema
                    format_type = 'YAML'
                else:
                    raise ODPSParameterError(
                        message=f"Cannot determine file format for: {file_path}",
                        error_code="UNKNOWN_FILE_FORMAT",
                        context={'file_path': file_path},
                        suggestion="Use .json or .yaml/.yml extension, or specify format with --format option"
                    )
        except FileNotFoundError:
            raise ODPSParameterError(
                message=f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND",
                context={'file_path': file_path},
                suggestion="Check that the file exists and the path is correct"
            )
        except (IOError, OSError) as e:
            raise ODPSParameterError(
                message=f"Cannot read file to detect format: {e}",
                error_code="FILE_READ_ERROR",
                context={'file_path': file_path},
                suggestion="Ensure file exists and is readable",
                original_error=e
            )

    if format_type not in allowed_formats:
        raise ODPSParameterError(
            message=f"Unsupported file format: {format_type}",
            error_code="UNSUPPORTED_FORMAT",
            context={'file_path': file_path, 'format': format_type, 'allowed_formats': allowed_formats},
            suggestion=f"Use one of: {', '.join(allowed_formats)}"
        )

    return format_type


def validate_mutually_exclusive_options(
    option1_name: str,
    option1_value: Any,
    option2_name: str,
    option2_value: Any
) -> None:
    """
    Validate that two options are mutually exclusive.

    Args:
        option1_name: Name of first option
        option1_value: Value of first option
        option2_name: Name of second option
        option2_value: Value of second option

    Raises:
        ODPSParameterError: If both options are provided
    """
    if option1_value and option2_value:
        raise ODPSParameterError(
            message=f"Cannot use both --{option1_name} and --{option2_name}",
            error_code="MUTUALLY_EXCLUSIVE_OPTIONS",
            context={
                'option1': option1_name,
                'option2': option2_name
            },
            suggestion=f"Choose either --{option1_name} or --{option2_name}, not both"
        )


def validate_required_option(option_name: str, option_value: Any, alternative: Optional[str] = None) -> None:
    """
    Validate that a required option is provided.

    Args:
        option_name: Name of option
        option_value: Value of option
        alternative: Alternative option name (if mutually exclusive)

    Raises:
        ODPSParameterError: If required option is not provided
    """
    if not option_value:
        if alternative:
            message = f"Must specify either --{option_name} or --{alternative}"
            suggestion = f"Provide either --{option_name} or --{alternative}"
        else:
            message = f"Required option --{option_name} is missing"
            suggestion = f"Provide --{option_name} option"

        raise ODPSParameterError(
            message=message,
            error_code="MISSING_REQUIRED_OPTION",
            context={'option': option_name, 'alternative': alternative},
            suggestion=suggestion
        )


# Helper functions for suggestions

def _get_validation_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for validation errors"""
    error_code_upper = error_code.upper()

    if 'REQUIRED_FIELD' in error_code_upper:
        field_path = context.get('field_path', 'field')
        return f"Add the required field '{field_path}' to your ODPS document"

    if 'SCHEMA_VALIDATION' in error_code_upper or 'INVALID_VALUE' in error_code_upper:
        field_path = context.get('field_path', 'field')
        expected = context.get('expected')
        actual = context.get('actual')
        if expected and actual:
            return f"Field '{field_path}' has invalid value. Expected: {expected}, Got: {actual}"
        return f"Check the value of field '{field_path}' against the ODPS schema"

    if 'VERSION_MISMATCH' in error_code_upper:
        return "Ensure the ODPS version in your document matches the schema version, or use --version to specify the correct version"

    return "Review your ODPS document against the ODPS schema specification"


def _get_ref_resolution_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for reference resolution errors"""
    error_code_upper = error_code.upper()

    if 'CIRCULAR_REF' in error_code_upper:
        return "Remove circular references in your ODPS document"

    if 'INVALID_REF' in error_code_upper:
        ref_path = context.get('ref_path', 'reference')
        return f"Check that the reference '{ref_path}' points to a valid location"

    if 'TIMEOUT' in error_code_upper:
        return "External reference resolution timed out. Check your network connection or use --no-resolve-external-refs to skip external references"

    if 'RATE_LIMIT' in error_code_upper:
        retry_after = context.get('retry_after_seconds')
        if retry_after:
            return f"Rate limit exceeded. Wait {retry_after} seconds before retrying, or use --no-resolve-external-refs to skip external references"
        return "Rate limit exceeded. Wait before retrying, or use --no-resolve-external-refs to skip external references"

    if 'SECURITY_VIOLATION' in error_code_upper:
        return "External reference is not allowed due to security restrictions. Use --no-resolve-external-refs to skip external references"

    return "Check that all references in your ODPS document are valid and accessible"


def _get_normalization_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for normalization errors"""
    field_path = context.get('field_path') or context.get('source_path', 'field')
    return f"Check the field '{field_path}' in your ODPS document. Normalization may require specific data types or formats"


def _get_export_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for export errors"""
    error_code_upper = error_code.upper()

    if 'FORMAT_NOT_SUPPORTED' in error_code_upper:
        export_format = context.get('export_format', 'format')
        return f"Export format '{export_format}' is not supported. Use 'json' or 'yaml'"

    if 'FILE_WRITE' in error_code_upper:
        file_path = context.get('file_path', 'file')
        return f"Check that you have write permissions for '{file_path}'"

    return "Check that the contract exists and is in a valid state for export"


def _get_linking_suggestion(error_code: str, context: Dict[str, Any]) -> str:
    """Get suggestion for linking errors"""
    error_code_upper = error_code.upper()

    if 'INVALID_LINK' in error_code_upper:
        source_id = context.get('source_id')
        target_id = context.get('target_id')
        if source_id and target_id:
            return f"Check that both contracts exist: ODCS ID '{source_id}' and ODPS ID '{target_id}'"
        return "Check that the contracts you're trying to link exist and are of the correct types"

    if 'CIRCULAR_REFERENCE' in error_code_upper:
        return "Remove circular references in the contract links"

    return "Check that the contracts exist and are in a valid state for linking"


def _get_http_error_suggestion(status_code: int, endpoint: Optional[str] = None) -> str:
    """Get suggestion for HTTP errors"""
    if status_code == 400:
        return "Check your request parameters and ensure they are valid"
    elif status_code == 401:
        return "Authentication failed. Run 'datahub login' to authenticate"
    elif status_code == 403:
        return "You don't have permission to perform this operation"
    elif status_code == 404:
        if endpoint and 'contract' in endpoint.lower():
            return "Contract not found. Check that the contract ID is correct"
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

