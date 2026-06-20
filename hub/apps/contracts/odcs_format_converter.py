"""
ODCS Format Converter

Provides format conversion utilities for ODCS documents:
- YAML → JSON conversion
- JSON → YAML conversion
- Structure preservation (round-trip conversion)
- Comment preservation (where possible)

This module handles format conversion between YAML and JSON formats while
preserving the data structure. Note that YAML comments cannot be preserved
when converting to JSON, as JSON does not support comments.
"""

import json
from typing import Any

import structlog

from hub.apps.contracts.odcs_errors import ODCSExportError

logger = structlog.get_logger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


def convert_yaml_to_json(yaml_content: str, indent: int = 2, ensure_ascii: bool = False) -> str:
    """
    Convert YAML content to JSON format.

    Parses YAML content and converts it to JSON string, preserving the
    data structure. Note that YAML comments are not preserved in JSON
    as JSON does not support comments.

    Args:
        yaml_content: YAML content as string
        indent: JSON indentation level (default: 2)
        ensure_ascii: If True, escape non-ASCII characters (default: False)

    Returns:
        JSON string representation of the YAML content

    Raises:
        ODCSExportError: If YAML parsing fails, content is empty, or JSON
            serialization fails

    Example:
        >>> yaml_content = '''
        ... apiVersion: odcs.io/v3.0.2
        ... kind: DataContract
        ... id: test-contract
        ... name: Test Contract
        ... '''
        >>> json_result = convert_yaml_to_json(yaml_content)
        >>> print(json_result)
        {
          "apiVersion": "odcs.io/v3.0.2",
          "kind": "DataContract",
          "id": "test-contract",
          "name": "Test Contract"
        }
    """
    if not yaml_content or not yaml_content.strip():
        raise ODCSExportError(
            message="YAML content is empty or whitespace only",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "error_type": "EmptyContent",
            },
        )

    if not YAML_AVAILABLE:
        raise ODCSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML conversion.",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "expected": "yaml module available",
                "actual": "yaml module not installed",
            },
        )

    try:
        # Parse YAML content
        yaml_data = yaml.safe_load(yaml_content)

        # Validate that parsed data is a dictionary (ODCS documents are objects)
        if not isinstance(yaml_data, dict):
            raise ODCSExportError(
                message=f"YAML content must represent a dictionary/object, got {type(yaml_data).__name__}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "yaml_to_json",
                    "expected": "dict",
                    "actual": type(yaml_data).__name__,
                },
            )

        # Convert to JSON
        json_result = json.dumps(yaml_data, indent=indent, ensure_ascii=ensure_ascii)

        logger.debug(
            "yaml_to_json_conversion_success",
            content_length=len(yaml_content),
            json_length=len(json_result),
        )

        return json_result

    except yaml.YAMLError as e:
        # Handle YAML parsing errors
        raise ODCSExportError(
            message=f"Failed to parse YAML content: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except TypeError as e:
        # Handle non-serializable objects
        raise ODCSExportError(
            message=f"Failed to serialize YAML data to JSON: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "yaml_to_json_conversion_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSExportError(
            message=f"Unexpected error converting YAML to JSON: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def convert_json_to_yaml(
    json_content: str,
    default_flow_style: bool = False,
    allow_unicode: bool = True,
    sort_keys: bool = False,
) -> str:
    """
    Convert JSON content to YAML format.

    Parses JSON content and converts it to YAML string, preserving the
    data structure. The output YAML format can be customized with various
    options.

    Args:
        json_content: JSON content as string
        default_flow_style: If True, use flow style (default: False, uses block style)
        allow_unicode: If True, allow unicode characters (default: True)
        sort_keys: If True, sort dictionary keys (default: False)

    Returns:
        YAML string representation of the JSON content

    Raises:
        ODCSExportError: If JSON parsing fails, content is empty, YAML
            serialization fails, or PyYAML is not available

    Example:
        >>> json_content = '''
        ... {
        ...   "apiVersion": "odcs.io/v3.0.2",
        ...   "kind": "DataContract",
        ...   "id": "test-contract",
        ...   "name": "Test Contract"
        ... }
        ... '''
        >>> yaml_result = convert_json_to_yaml(json_content)
        >>> print(yaml_result)
        apiVersion: odcs.io/v3.0.2
        kind: DataContract
        id: test-contract
        name: Test Contract
    """
    if not json_content or not json_content.strip():
        raise ODCSExportError(
            message="JSON content is empty or whitespace only",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": "EmptyContent",
            },
        )

    if not YAML_AVAILABLE:
        raise ODCSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML conversion.",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "expected": "yaml module available",
                "actual": "yaml module not installed",
            },
        )

    try:
        # Parse JSON content
        json_data = json.loads(json_content)

        # Validate that parsed data is a dictionary (ODCS documents are objects)
        if not isinstance(json_data, dict):
            raise ODCSExportError(
                message=f"JSON content must represent a dictionary/object, got {type(json_data).__name__}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "json_to_yaml",
                    "expected": "dict",
                    "actual": type(json_data).__name__,
                },
            )

        # Convert to YAML
        yaml_result = yaml.dump(
            json_data,
            default_flow_style=default_flow_style,
            allow_unicode=allow_unicode,
            sort_keys=sort_keys,
        )

        logger.debug(
            "json_to_yaml_conversion_success",
            content_length=len(json_content),
            yaml_length=len(yaml_result),
        )

        return yaml_result

    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        raise ODCSExportError(
            message=f"Failed to parse JSON content: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "error_line": getattr(e, "lineno", None),
                "error_column": getattr(e, "colno", None),
            },
            cause=e,
        ) from e
    except yaml.YAMLError as e:
        # Handle YAML serialization errors
        raise ODCSExportError(
            message=f"Failed to serialize JSON data to YAML: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "json_to_yaml_conversion_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSExportError(
            message=f"Unexpected error converting JSON to YAML: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def format_odcs_as_json(
    odcs_doc: dict[str, Any], indent: int = 2, ensure_ascii: bool = False
) -> str:
    """
    Format ODCS document as JSON string (Task 9.5.4.1.3.1).

    Formats an ODCS document dictionary as a JSON string with proper indentation
    and UTF-8 encoding support. Validates that the input is a dictionary and
    that the output is valid JSON.

    Args:
        odcs_doc: ODCS document dictionary
        indent: JSON indentation level (default: 2)
        ensure_ascii: If True, escape non-ASCII characters (default: False, preserves UTF-8)

    Returns:
        ODCS document as JSON string with proper formatting

    Raises:
        ODCSExportError: If document is not a dictionary, JSON serialization fails,
            or output validation fails

    Example:
        >>> odcs_doc = {
        ...     "apiVersion": "odcs.io/v3.0.2",
        ...     "kind": "DataContract",
        ...     "id": "test-contract",
        ...     "name": "Test Contract"
        ... }
        >>> json_result = format_odcs_as_json(odcs_doc)
        >>> print(json_result)
        {
          "apiVersion": "odcs.io/v3.0.2",
          "kind": "DataContract",
          "id": "test-contract",
          "name": "Test Contract"
        }
    """
    try:
        if not isinstance(odcs_doc, dict):
            raise ODCSExportError(
                message=f"ODCS document must be a dictionary, got {type(odcs_doc).__name__}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "format_odcs_as_json",
                    "expected": "dict",
                    "actual": type(odcs_doc).__name__,
                },
            )

        # Format as JSON with proper indentation and UTF-8 encoding
        json_result = json.dumps(odcs_doc, indent=indent, ensure_ascii=ensure_ascii)

        # Validate output format correctness by parsing it back
        try:
            json.loads(json_result)
        except json.JSONDecodeError as e:
            raise ODCSExportError(
                message=f"Generated JSON is invalid: {e!s}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "format_odcs_as_json",
                    "error_type": "JSONValidationFailed",
                    "error_message": str(e),
                },
                cause=e,
            ) from e

        logger.debug(
            "odcs_json_formatting_success",
            document_id=odcs_doc.get("id"),
            json_length=len(json_result),
            indent=indent,
        )

        return json_result

    except ODCSExportError:
        # Re-raise ODCSExportError as-is
        raise
    except TypeError as e:
        # Handle non-serializable objects
        raise ODCSExportError(
            message=f"Failed to serialize ODCS document to JSON: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "format_odcs_as_json",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "odcs_json_formatting_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSExportError(
            message=f"Unexpected error formatting ODCS document as JSON: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "format_odcs_as_json",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def format_odcs_as_yaml(
    odcs_doc: dict[str, Any],
    default_flow_style: bool = False,
    allow_unicode: bool = True,
    sort_keys: bool = False,
) -> str:
    """
    Format ODCS document as YAML string (Task 9.5.4.1.3.1).

    Formats an ODCS document dictionary as a YAML string with proper formatting
    and UTF-8 encoding support. Validates that the input is a dictionary and
    that the output is valid YAML.

    Args:
        odcs_doc: ODCS document dictionary
        default_flow_style: If True, use flow style (default: False, uses block style)
        allow_unicode: If True, allow unicode characters (default: True, preserves UTF-8)
        sort_keys: If True, sort dictionary keys (default: False)

    Returns:
        ODCS document as YAML string with proper formatting

    Raises:
        ODCSExportError: If document is not a dictionary, PyYAML is not available,
            YAML serialization fails, or output validation fails

    Example:
        >>> odcs_doc = {
        ...     "apiVersion": "odcs.io/v3.0.2",
        ...     "kind": "DataContract",
        ...     "id": "test-contract",
        ...     "name": "Test Contract"
        ... }
        >>> yaml_result = format_odcs_as_yaml(odcs_doc)
        >>> print(yaml_result)
        apiVersion: odcs.io/v3.0.2
        kind: DataContract
        id: test-contract
        name: Test Contract
    """
    if not YAML_AVAILABLE:
        raise ODCSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML output format.",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "format_odcs_as_yaml",
                "expected": "yaml module available",
                "actual": "yaml module not installed",
            },
        )

    try:
        if not isinstance(odcs_doc, dict):
            raise ODCSExportError(
                message=f"ODCS document must be a dictionary, got {type(odcs_doc).__name__}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "format_odcs_as_yaml",
                    "expected": "dict",
                    "actual": type(odcs_doc).__name__,
                },
            )

        # Format as YAML with proper formatting and UTF-8 encoding
        yaml_result = yaml.dump(
            odcs_doc,
            default_flow_style=default_flow_style,
            allow_unicode=allow_unicode,
            sort_keys=sort_keys,
        )

        # Validate output format correctness by parsing it back
        try:
            yaml.safe_load(yaml_result)
        except yaml.YAMLError as e:
            raise ODCSExportError(
                message=f"Generated YAML is invalid: {e!s}",
                error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
                context={
                    "field_path": "/",
                    "operation": "format_odcs_as_yaml",
                    "error_type": "YAMLValidationFailed",
                    "error_message": str(e),
                },
                cause=e,
            ) from e

        logger.debug(
            "odcs_yaml_formatting_success",
            document_id=odcs_doc.get("id"),
            yaml_length=len(yaml_result),
            default_flow_style=default_flow_style,
        )

        return yaml_result

    except ODCSExportError:
        # Re-raise ODCSExportError as-is
        raise
    except yaml.YAMLError as e:
        # Handle YAML serialization errors
        raise ODCSExportError(
            message=f"Failed to serialize ODCS document to YAML: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "format_odcs_as_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "odcs_yaml_formatting_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSExportError(
            message=f"Unexpected error formatting ODCS document as YAML: {e!s}",
            error_code=ODCSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "format_odcs_as_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e
