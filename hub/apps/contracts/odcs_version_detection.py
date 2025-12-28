"""
ODCS Version Detection

Detects ODCS version from contract data by:
1. Primary: Extracting version from apiVersion field
2. Fallback: Using version field if apiVersion is not available

Supports all ODCS versions: 3.0.2, 3.0.1, 3.0.0, 2.2.2, 2.2.1, 2.2.0, etc.
"""
import re
from typing import Dict, Any


def detect_odcs_version(contract_data: Dict[str, Any]) -> str:
    """
    Detect ODCS version from contract data.

    Detection strategy (in order):
    1. Primary: Extract version from apiVersion field
       - Supports: "odcs.io/v3.0.2", "odcs/v3.0.2", "odcs.io/v3", etc.
       - Supports: "datacontract.io/v3.0.2" (legacy format)
    2. Fallback: Use version field if present

    Version normalization:
    - Extracts version from apiVersion (e.g., "3.0.2" from "odcs.io/v3.0.2")
    - Returns "unknown" if version cannot be determined
    - Defaults to "3.0.2" for ODCS contracts without version info

    Args:
        contract_data: ODCS contract data dictionary

    Returns:
        Version string (e.g., "3.0.2", "3.0.1", "3.0.0", "2.2.2") or "unknown"

    Example:
        >>> detect_odcs_version({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"})
        '3.0.2'
        >>> detect_odcs_version({"apiVersion": "odcs/v3.0.1", "kind": "DataContract"})
        '3.0.1'
        >>> detect_odcs_version({"version": "2.2.2"})
        '2.2.2'
    """
    if not isinstance(contract_data, dict):
        return "unknown"

    # Primary: Try to detect from apiVersion field
    api_version = contract_data.get("apiVersion")
    if api_version and isinstance(api_version, str):
        version = _extract_version_from_api_version(api_version)
        if version and version != "unknown":
            return version

    # Fallback: Try to detect from version field
    version_field = contract_data.get("version")
    if version_field:
        version = _normalize_version_from_field(version_field)
        if version and version != "unknown":
            return version

    return "unknown"


def _extract_version_from_api_version(api_version: str) -> str:
    """
    Extract ODCS version from apiVersion field.

    Supports multiple formats:
    - "odcs.io/v3.0.2"
    - "odcs/v3.0.2"
    - "datacontract.io/v3.0.2" (legacy)
    - "odcs.io/v3" (major version only)

    Args:
        api_version: apiVersion field string

    Returns:
        Normalized version string or "unknown"
    """
    if not api_version or not isinstance(api_version, str):
        return "unknown"

    # Pattern 1: odcs.io/v{version} or datacontract.io/v{version}
    # Pattern 2: odcs/v{version}
    # Pattern 3: Generic /v{version} pattern as fallback

    patterns = [
        # odcs.io/v{version} or datacontract.io/v{version}
        r'(?:odcs|datacontract)\.io/v([\d.]+)',
        # odcs/v{version}
        r'odcs/v([\d.]+)',
        # Generic /v{version} pattern as fallback
        r'/v([\d.]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, api_version, re.IGNORECASE)
        if match:
            version_str = match.group(1)
            return _normalize_version_string(version_str)

    return "unknown"


def _normalize_version_from_field(version_field: Any) -> str:
    """
    Normalize version from version field.

    Handles various formats:
    - String: "3.0.2", "3.0.1", "3.0.0", etc.
    - Integer: 3 (treated as 3.0.0)
    - Float: 3.0 (treated as 3.0.0)

    Args:
        version_field: Version field value (string, int, or float)

    Returns:
        Normalized version string or "unknown"
    """
    if version_field is None:
        return "unknown"

    # Convert to string
    if isinstance(version_field, (int, float)):
        version_str = str(version_field)
    elif isinstance(version_field, str):
        version_str = version_field.strip()
    else:
        return "unknown"

    if not version_str:
        return "unknown"

    return _normalize_version_string(version_str)


def _normalize_version_string(version_str: str) -> str:
    """
    Normalize version string to supported format.

    Normalization rules:
    - "3.0.2" -> "3.0.2"
    - "3.0.1" -> "3.0.1"
    - "3.0.0" -> "3.0.0"
    - "3.0" -> "3.0.0"
    - "3" -> "3.0.0"
    - Invalid formats -> "unknown"

    Args:
        version_str: Version string to normalize

    Returns:
        Normalized version string or "unknown"
    """
    if not version_str or not isinstance(version_str, str):
        return "unknown"

    version_str = version_str.strip()

    # Remove "v" prefix if present
    if version_str.startswith('v') or version_str.startswith('V'):
        version_str = version_str[1:]

    # Parse version components
    parts = version_str.split('.')

    # Handle different version formats
    try:
        if len(parts) == 1:
            # Single number (e.g., "3" -> "3.0.0")
            major = int(parts[0])
            return f"{major}.0.0"
        elif len(parts) == 2:
            # Major.minor (e.g., "3.0" -> "3.0.0")
            major = int(parts[0])
            minor = int(parts[1])
            return f"{major}.{minor}.0"
        elif len(parts) >= 3:
            # Major.minor.patch (e.g., "3.0.2")
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            return f"{major}.{minor}.{patch}"
        else:
            return "unknown"
    except (ValueError, IndexError):
        return "unknown"


def get_supported_odcs_versions() -> list[str]:
    """
    Get list of supported ODCS versions.

    Returns:
        List of supported version strings
    """
    return [
        "3.0.2",
        "3.0.1",
        "3.0.0",
        "2.2.2",
        "2.2.1",
        "2.2.0",
    ]


def is_supported_odcs_version(version: str) -> bool:
    """
    Check if ODCS version is supported.

    Args:
        version: Version string to check

    Returns:
        True if version is supported, False otherwise
    """
    supported = get_supported_odcs_versions()
    return version in supported

