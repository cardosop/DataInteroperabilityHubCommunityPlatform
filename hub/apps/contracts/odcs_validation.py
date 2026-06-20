"""
ODCS Validation Utilities

Provides validation functions for ODCS (Open Data Contract Standard) operations.
"""

import re

from hub.apps.contracts.odcs_errors import ODCSValidationError
from hub.apps.contracts.odcs_generator import get_supported_odcs_versions


def validate_odcs_version(version: str | None) -> None:
    """
    Validate ODCS version format.

    Validates that the version string matches the expected format and is a supported version.
    ODCS versions follow the format: major.minor[.patch] or major.minor[-suffix]
    Supported versions: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

    Args:
        version: Version string to validate (e.g., "3.0.2", "3.0.1", "3.0.0-preview", "2.2.2")

    Raises:
        ODCSValidationError: If version format is invalid or version is not supported

    Example:
        >>> validate_odcs_version("3.0.2")  # Valid
        >>> validate_odcs_version("3.0.0-preview")  # Valid
        >>> validate_odcs_version("invalid")  # Raises ODCSValidationError
        >>> validate_odcs_version("99.99.99")  # Raises ODCSValidationError (not supported)
    """
    if version is None:
        return  # Optional parameter, None is valid

    if not isinstance(version, str):
        raise ODCSValidationError(
            message=f"ODCS version must be a string, got {type(version).__name__}",
            error_code=ODCSValidationError.ERROR_CODE_INVALID_VALUE,
            context={
                "field_path": "/version",
                "expected": "string (e.g., '3.0.2', '3.0.0-preview')",
                "actual": type(version).__name__,
            },
        )

    version = version.strip()

    # ODCS version format: major.minor[.patch] or major.minor[-suffix]
    # Examples: "3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"
    version_pattern = r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9-]+)?$"
    if not re.match(version_pattern, version):
        raise ODCSValidationError(
            message=f"Invalid ODCS version format: {version}",
            error_code=ODCSValidationError.ERROR_CODE_INVALID_VALUE,
            context={
                "field_path": "/version",
                "expected": "version string in format 'X.Y' or 'X.Y.Z' or 'X.Y-suffix' (e.g., '3.0.2', '3.0.0-preview')",
                "actual": version,
            },
        )

    # Check if version is supported
    supported_versions = get_supported_odcs_versions()
    if version not in supported_versions:
        raise ODCSValidationError(
            message=f"ODCS version '{version}' is not supported. Supported versions: {', '.join(supported_versions)}",
            error_code=ODCSValidationError.ERROR_CODE_VERSION_MISMATCH,
            context={
                "field_path": "/version",
                "expected": f"one of: {', '.join(supported_versions)}",
                "actual": version,
                "supported_versions": supported_versions,
            },
        )
