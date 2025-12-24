"""
ODPS Format Converter (Task 2.2.3)

Provides format conversion utilities for ODPS documents:
- YAML → JSON conversion
- JSON → YAML conversion
- Structure preservation (round-trip conversion)
- Comment preservation (where possible)

This module handles format conversion between YAML and JSON formats while
preserving the data structure. Note that YAML comments cannot be preserved
when converting to JSON, as JSON does not support comments.
"""
import json
import structlog
from typing import Dict, Any

from hub.apps.contracts.odps_errors import ODPSExportError

logger = structlog.get_logger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


def convert_yaml_to_json(
    yaml_content: str,
    indent: int = 2,
    ensure_ascii: bool = False
) -> str:
    """
    Convert YAML content to JSON format (Task 2.2.3).

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
        ODPSExportError: If YAML parsing fails, content is empty, or JSON
            serialization fails

    Example:
        >>> yaml_content = '''
        ... schema: https://opendataproducts.org/schema/v4.1
        ... version: "4.1"
        ... product:
        ...   details:
        ...     en:
        ...       name: Test Product
        ... '''
        >>> json_result = convert_yaml_to_json(yaml_content)
        >>> print(json_result)
        {
          "schema": "https://opendataproducts.org/schema/v4.1",
          "version": "4.1",
          "product": {
            "details": {
              "en": {
                "name": "Test Product"
              }
            }
          }
        }
    """
    if not yaml_content or not yaml_content.strip():
        raise ODPSExportError(
            message="YAML content is empty or whitespace only",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "yaml_to_json",
                "error_type": "EmptyContent",
            },
        )

    if not YAML_AVAILABLE:
        raise ODPSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML conversion.",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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

        # Validate that parsed data is a dictionary (ODPS documents are objects)
        if not isinstance(yaml_data, dict):
            raise ODPSExportError(
                message=f"YAML content must represent a dictionary/object, got {type(yaml_data).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
        raise ODPSExportError(
            message=f"Failed to parse YAML content: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
        raise ODPSExportError(
            message=f"Failed to serialize YAML data to JSON: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
        raise ODPSExportError(
            message=f"Unexpected error converting YAML to JSON: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
    sort_keys: bool = False
) -> str:
    """
    Convert JSON content to YAML format (Task 2.2.3).

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
        ODPSExportError: If JSON parsing fails, content is empty, YAML
            serialization fails, or PyYAML is not available

    Example:
        >>> json_content = '''
        ... {
        ...   "schema": "https://opendataproducts.org/schema/v4.1",
        ...   "version": "4.1",
        ...   "product": {
        ...     "details": {
        ...       "en": {
        ...         "name": "Test Product"
        ...       }
        ...     }
        ...   }
        ... }
        ... '''
        >>> yaml_result = convert_json_to_yaml(json_content)
        >>> print(yaml_result)
        schema: https://opendataproducts.org/schema/v4.1
        version: '4.1'
        product:
          details:
            en:
              name: Test Product
    """
    if not json_content or not json_content.strip():
        raise ODPSExportError(
            message="JSON content is empty or whitespace only",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": "EmptyContent",
            },
        )

    if not YAML_AVAILABLE:
        raise ODPSExportError(
            message="PyYAML is not available. Install PyYAML to use YAML conversion.",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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

        # Validate that parsed data is a dictionary (ODPS documents are objects)
        if not isinstance(json_data, dict):
            raise ODPSExportError(
                message=f"JSON content must represent a dictionary/object, got {type(json_data).__name__}",
                error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
            sort_keys=sort_keys
        )

        logger.debug(
            "json_to_yaml_conversion_success",
            content_length=len(json_content),
            yaml_length=len(yaml_result),
        )

        return yaml_result

    except json.JSONDecodeError as e:
        # Handle JSON parsing errors
        raise ODPSExportError(
            message=f"Failed to parse JSON content: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
        raise ODPSExportError(
            message=f"Failed to serialize JSON data to YAML: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
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
        raise ODPSExportError(
            message=f"Unexpected error converting JSON to YAML: {str(e)}",
            error_code=ODPSExportError.ERROR_CODE_EXPORT_FAILED,
            context={
                "field_path": "/",
                "operation": "json_to_yaml",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e

