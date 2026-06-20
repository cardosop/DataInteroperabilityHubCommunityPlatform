"""
ODPS Parser Module

Parses ODPS (Open Data Product Standard) documents in YAML/JSON format.
Supports format detection, error handling with context, and validation.
"""

import json
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
    from jsonschema import Draft202012Validator, SchemaError
    from jsonschema import ValidationError as JSONSchemaValidationError

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    Draft202012Validator = None
    JSONSchemaValidationError = Exception
    SchemaError = Exception

from hub.apps.contracts.odps_schema import load_odps_schema


class ODPSValidationError(Exception):
    """
    Exception raised when ODPS parsing or validation fails.

    Attributes:
        message: Error message
        file_path: Optional file path where error occurred
        line_number: Optional line number where error occurred
        original_error: Optional original exception that caused this error
        validation_errors: Optional list of validation error details
        error_code: Optional error code for user-friendly error handling
    """

    def __init__(
        self,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
        original_error: Exception | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        error_code: str | None = None,
    ):
        """
        Initialize ODPSValidationError.

        Args:
            message: Error message
            file_path: Optional file path where error occurred
            line_number: Optional line number where error occurred
            original_error: Optional original exception that caused this error
            validation_errors: Optional list of validation error details with paths
            error_code: Optional error code for user-friendly error handling
        """
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        self.original_error = original_error
        self.validation_errors = validation_errors or []
        self.error_code = error_code

        # Build full error message with context
        error_parts = [message]
        if file_path:
            error_parts.append(f"File: {file_path}")
        if line_number:
            error_parts.append(f"Line: {line_number}")
        if error_code:
            error_parts.append(f"Code: {error_code}")
        if original_error:
            error_parts.append(f"Original error: {original_error!s}")

        super().__init__(" | ".join(error_parts))

    def __str__(self) -> str:
        """Return formatted error message with context."""
        error_parts = [self.message]
        if self.file_path:
            error_parts.append(f"File: {self.file_path}")
        if self.line_number:
            error_parts.append(f"Line: {self.line_number}")
        if self.error_code:
            error_parts.append(f"Code: {self.error_code}")
        if self.original_error:
            error_parts.append(f"Original error: {self.original_error!s}")
        if self.validation_errors:
            error_parts.append(f"Validation errors: {len(self.validation_errors)}")
        return " | ".join(error_parts)


class ODPSParser:
    """
    ODPS (Open Data Product Standard) parser.

    Supports both YAML and JSON formats with automatic format detection.
    Provides detailed error messages with file path and line number context.
    """

    @classmethod
    def parse(
        cls, content: str, file_path: str | None = None, format: str | None = None
    ) -> dict[str, Any]:
        """
        Parse ODPS content from string.

        Automatically detects format if not specified.
        Supports both YAML and JSON formats.

        Args:
            content: ODPS content as string (YAML or JSON)
            file_path: Optional file path for error context
            format: Optional format hint ("yaml" or "json"). If None, auto-detects.

        Returns:
            Parsed ODPS document as dictionary

        Raises:
            ODPSValidationError: If parsing fails or content is invalid
        """
        if not content or not isinstance(content, str):
            raise ODPSValidationError("Content must be a non-empty string", file_path=file_path)

        # Detect format if not specified
        if format is None:
            format = cls._detect_format(content)

        # Parse based on format
        try:
            if format.lower() == "json":
                return cls._parse_json(content, file_path)
            elif format.lower() == "yaml":
                return cls._parse_yaml(content, file_path)
            else:
                raise ODPSValidationError(
                    f"Unsupported format: {format}. Supported formats: json, yaml",
                    file_path=file_path,
                )
        except ODPSValidationError:
            # Re-raise ODPSValidationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSValidationError(
                f"Unexpected error parsing ODPS content: {e!s}",
                file_path=file_path,
                original_error=e,
            )

    @classmethod
    def parse_file(cls, file_path: str, format: str | None = None) -> dict[str, Any]:
        """
        Parse ODPS content from file.

        Args:
            file_path: Path to ODPS file
            format: Optional format hint ("yaml" or "json"). If None, auto-detects.

        Returns:
            Parsed ODPS document as dictionary

        Raises:
            ODPSValidationError: If file cannot be read or parsing fails
            FileNotFoundError: If file does not exist
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"ODPS file not found: {file_path}")

        if not path.is_file():
            raise ODPSValidationError(f"Path is not a file: {file_path}", file_path=file_path)

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            raise ODPSValidationError(
                f"File encoding error: {e!s}", file_path=file_path, original_error=e
            )
        except OSError as e:
            raise ODPSValidationError(
                f"Error reading file: {e!s}", file_path=file_path, original_error=e
            )

        return cls.parse(content, file_path=str(path), format=format)

    @classmethod
    def _parse_json(cls, content: str, file_path: str | None = None) -> dict[str, Any]:
        """
        Parse JSON content.

        Args:
            content: JSON content as string
            file_path: Optional file path for error context

        Returns:
            Parsed JSON as dictionary

        Raises:
            ODPSValidationError: If JSON parsing fails
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Extract line number from JSON error
            line_number = None
            if hasattr(e, "lineno") and e.lineno:
                line_number = e.lineno
            elif hasattr(e, "pos"):
                # Estimate line number from position
                line_number = content[: e.pos].count("\n") + 1

            raise ODPSValidationError(
                f"Invalid JSON format: {e.msg}",
                file_path=file_path,
                line_number=line_number,
                original_error=e,
            )

        # Validate that parsed data is a dictionary
        if not isinstance(data, dict):
            raise ODPSValidationError(
                f"ODPS document must be a JSON object, got {type(data).__name__}",
                file_path=file_path,
            )

        return data

    @classmethod
    def _parse_yaml(cls, content: str, file_path: str | None = None) -> dict[str, Any]:
        """
        Parse YAML content.

        Args:
            content: YAML content as string
            file_path: Optional file path for error context

        Returns:
            Parsed YAML as dictionary

        Raises:
            ODPSValidationError: If YAML parsing fails
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            # Extract line number from YAML error
            line_number = None
            if hasattr(e, "problem_mark") and e.problem_mark:
                line_number = e.problem_mark.line + 1  # YAML line numbers are 0-based
            elif hasattr(e, "context_mark") and e.context_mark:
                line_number = e.context_mark.line + 1

            error_msg = str(e)
            if hasattr(e, "problem"):
                error_msg = e.problem

            raise ODPSValidationError(
                f"Invalid YAML format: {error_msg}",
                file_path=file_path,
                line_number=line_number,
                original_error=e,
            )

        # Handle case where YAML is None or not a dict
        if data is None:
            raise ODPSValidationError(
                "ODPS document is empty or contains no data", file_path=file_path
            )

        if not isinstance(data, dict):
            raise ODPSValidationError(
                f"ODPS document must be a YAML object/mapping, got {type(data).__name__}",
                file_path=file_path,
            )

        return data

    @classmethod
    def _detect_format(cls, content: str) -> str:
        """
        Detect format (YAML or JSON) from content.

        Detection strategy:
        1. Try to parse as JSON first (faster, more strict)
        2. If JSON fails, assume YAML

        Args:
            content: Content to analyze

        Returns:
            Detected format ("json" or "yaml")
        """
        if content is None:
            return "yaml"  # Default when content is missing (e.g. for optional detection)
        # Strip whitespace for detection
        stripped = content.strip()

        # JSON typically starts with { or [
        # YAML can start with various characters
        if stripped.startswith("{") or stripped.startswith("["):
            # Try JSON first
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                # Not valid JSON, try YAML
                pass

        # Default to YAML (more flexible format)
        # YAML can also parse JSON, so this is safe
        return "yaml"

    @classmethod
    def detect_format(cls, content: str) -> str:
        """
        Detect format (YAML or JSON) from content.

        Public method for format detection without parsing.

        Args:
            content: Content to analyze

        Returns:
            Detected format ("json" or "yaml")
        """
        return cls._detect_format(content)

    @classmethod
    def validate(
        cls, odps_document: dict[str, Any], version: str | None = None, file_path: str | None = None
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Validate ODPS document against JSON Schema.

        Args:
            odps_document: Parsed ODPS document dictionary
            version: ODPS version (e.g., "4.1", "4.0"). If None, attempts to detect from document.
            file_path: Optional file path for error context

        Returns:
            Tuple of (is_valid, validation_errors)
            - is_valid: True if document is valid, False otherwise
            - validation_errors: List of validation error dictionaries with paths and messages

        Raises:
            ODPSValidationError: If schema cannot be loaded or validation fails critically
        """
        if not JSONSCHEMA_AVAILABLE:
            raise ODPSValidationError(
                "jsonschema library is required for ODPS validation. "
                "Install it with: pip install jsonschema",
                file_path=file_path,
                error_code="JSONSCHEMA_NOT_AVAILABLE",
            )

        # Detect version from document if not provided
        if version is None:
            version = cls._detect_version(odps_document)

        if not version:
            raise ODPSValidationError(
                "ODPS version could not be determined. "
                "Please specify version or ensure document contains 'schema' or 'version' field.",
                file_path=file_path,
                error_code="VERSION_NOT_FOUND",
            )

        # Load schema for the version
        try:
            schema = load_odps_schema(version)
        except FileNotFoundError as e:
            raise ODPSValidationError(
                f"ODPS schema not found for version '{version}': {e!s}",
                file_path=file_path,
                original_error=e,
                error_code="SCHEMA_NOT_FOUND",
            )
        except (OSError, json.JSONDecodeError, ValueError) as e:
            raise ODPSValidationError(
                f"Error loading ODPS schema for version '{version}': {e!s}",
                file_path=file_path,
                original_error=e,
                error_code="SCHEMA_LOAD_ERROR",
            )

        # Validate schema itself
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            raise ODPSValidationError(
                f"ODPS schema for version '{version}' is invalid: {e!s}",
                file_path=file_path,
                original_error=e,
                error_code="SCHEMA_INVALID",
            )

        # Validate document against schema
        validator = Draft202012Validator(schema)
        validation_errors = []

        try:
            validator.validate(odps_document)
            return True, []
        except JSONSchemaValidationError:
            # Collect all validation errors
            errors = validator.iter_errors(odps_document)

            for error in errors:
                error_path = (
                    ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                )

                # Build user-friendly error message
                error_message = error.message
                if error_path != "root":
                    error_message = f"{error_path}: {error_message}"

                # Determine error code based on error type
                error_code = cls._get_error_code(error)

                validation_errors.append(
                    {
                        "path": error_path,
                        "message": error_message,
                        "error": error.message,
                        "schema_path": list(error.absolute_schema_path)
                        if hasattr(error, "absolute_schema_path")
                        else [],
                        "code": error_code,
                    }
                )

            return False, validation_errors
        except Exception as e:
            raise ODPSValidationError(
                f"Unexpected error during ODPS validation: {e!s}",
                file_path=file_path,
                original_error=e,
                error_code="VALIDATION_ERROR",
            )

    @classmethod
    def parse_and_validate(
        cls,
        content: str,
        version: str | None = None,
        file_path: str | None = None,
        format: str | None = None,
    ) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
        """
        Parse and validate ODPS content in one step.

        Args:
            content: ODPS content as string (YAML or JSON)
            version: ODPS version (e.g., "4.1", "4.0"). If None, attempts to detect from document.
            file_path: Optional file path for error context
            format: Optional format hint ("yaml" or "json"). If None, auto-detects.

        Returns:
            Tuple of (parsed_document, is_valid, validation_errors)
            - parsed_document: Parsed ODPS document dictionary
            - is_valid: True if document is valid, False otherwise
            - validation_errors: List of validation error dictionaries with paths and messages

        Raises:
            ODPSValidationError: If parsing fails or schema cannot be loaded
        """
        # Parse first
        parsed_document = cls.parse(content, file_path=file_path, format=format)

        # Then validate
        is_valid, validation_errors = cls.validate(
            parsed_document, version=version, file_path=file_path
        )

        return parsed_document, is_valid, validation_errors

    @classmethod
    def _detect_version(cls, odps_document: dict[str, Any]) -> str | None:
        """
        Detect ODPS version from document.

        Args:
            odps_document: Parsed ODPS document dictionary

        Returns:
            Detected version string (e.g., "4.1", "4.0") or None if not found
        """
        # Check schema field (most reliable)
        schema = odps_document.get("schema", "")
        if isinstance(schema, str):
            # Extract version from schema URL
            # e.g., "https://opendataproducts.org/schema/v4.1" -> "4.1"
            if "opendataproducts.org/schema/v" in schema:
                version_part = schema.split("opendataproducts.org/schema/v")[-1]
                # Remove any trailing path or query
                version = version_part.split("/")[0].split("?")[0].split("#")[0]
                if version:
                    return version

        # Check version field
        version = odps_document.get("version")
        if isinstance(version, str):
            # Normalize version (remove "v" prefix if present)
            version = version.strip()
            if version.startswith("v"):
                version = version[1:]
            return version

        return None

    @classmethod
    def _get_error_code(cls, error: JSONSchemaValidationError) -> str:
        """
        Get user-friendly error code from jsonschema validation error.

        Args:
            error: jsonschema ValidationError instance

        Returns:
            Error code string
        """
        # Map common jsonschema error types to error codes
        error_type = error.validator if hasattr(error, "validator") else None

        if error_type == "required":
            return "REQUIRED_FIELD_MISSING"
        elif error_type == "type":
            return "INVALID_TYPE"
        elif error_type == "enum":
            return "INVALID_ENUM_VALUE"
        elif error_type == "format":
            return "INVALID_FORMAT"
        elif error_type == "pattern":
            return "PATTERN_MISMATCH"
        elif error_type == "minLength" or error_type == "maxLength":
            return "INVALID_LENGTH"
        elif error_type == "minimum" or error_type == "maximum":
            return "INVALID_RANGE"
        elif error_type == "additionalProperties":
            return "UNEXPECTED_PROPERTY"
        elif error_type == "oneOf" or error_type == "anyOf" or error_type == "allOf":
            return "SCHEMA_CONDITION_FAILED"
        else:
            return "VALIDATION_ERROR"
