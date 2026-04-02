"""
ODPS Version Detection

Detects ODPS version from contract data by:
1. Bitol ODPS: Checking for bitol-io.github.io schema URL or kind: DataProduct discriminator
2. Primary: Extracting version from schema URL (pre-Bitol ODPS)
3. Fallback: Using version field if schema URL is not available

Supports:
- Pre-Bitol ODPS (Niilahti et al.): 1.x, 2.x, 3.x, 4.0, 4.1, 4.2
- Bitol/LF ODPS: bitol-0.9.0, bitol-1.0.0
"""
import re
from typing import Dict, Any

# Pattern to extract version from Bitol ODPS schema URL
_BITOL_VERSION_PATTERN = re.compile(
    r"bitol-io\.github\.io/open-data-product-standard/v([\d.]+)"
)


def detect_odps_version(contract_data: Dict[str, Any]) -> str:
    """
    Detect ODPS version from contract data.

    Detection strategy (in order):
    1. Bitol ODPS: Check for bitol-io.github.io schema URL
       (returns "bitol-X.Y.Z" prefix to distinguish from pre-Bitol)
    2. Primary: Extract version from pre-Bitol schema URL
       - Supports: https://opendataproducts.org/schema/v{version}
       - Supports: https://schemas.opendataproducts.io/spec/v{version}/product.json
    3. Fallback: Use version field if present

    Version normalization:
    - Bitol ODPS: "bitol-1.0.0", "bitol-0.9.0" (prefixed)
    - Pre-Bitol: "4.1", "4.0", "3.x", "2.x", "1.x"
    - Returns "unknown" if version cannot be determined

    Args:
        contract_data: ODPS contract data dictionary

    Returns:
        Version string or "unknown"

    Example:
        >>> detect_odps_version({"schema": "https://opendataproducts.org/schema/v4.1"})
        '4.1'
        >>> detect_odps_version({"schema": "https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json"})
        'bitol-1.0.0'
    """
    if not isinstance(contract_data, dict):
        return "unknown"

    # 1. Bitol ODPS detection (check first — more specific)
    bitol_version = _detect_bitol_odps_version(contract_data)
    if bitol_version:
        return bitol_version

    # 2. Primary: Try to detect from pre-Bitol schema URL
    schema_url = contract_data.get("schema")
    if schema_url and isinstance(schema_url, str):
        version = _extract_version_from_schema_url(schema_url)
        if version and version != "unknown":
            return version

    # 3. Fallback: Try to detect from version field
    version_field = contract_data.get("version")
    if version_field:
        version = _normalize_version_from_field(version_field)
        if version and version != "unknown":
            return version

    return "unknown"


def _detect_bitol_odps_version(contract_data: Dict[str, Any]) -> str:
    """
    Detect Bitol ODPS version from contract data.

    Bitol ODPS discriminators:
    1. Schema URL containing bitol-io.github.io/open-data-product-standard
    2. kind: DataProduct + apiVersion with Bitol pattern

    Returns:
        "bitol-X.Y.Z" version string, or empty string if not Bitol ODPS
    """
    # Check schema URL for Bitol pattern
    schema_url = contract_data.get("schema")
    if schema_url and isinstance(schema_url, str):
        match = _BITOL_VERSION_PATTERN.search(schema_url)
        if match:
            return f"bitol-{match.group(1)}"

    # Check kind: DataProduct + apiVersion pattern
    # Bitol ODPS uses apiVersion like "v1.0.0" with kind: DataProduct
    kind = contract_data.get("kind")
    api_version = contract_data.get("apiVersion")
    if (
        kind == "DataProduct"
        and isinstance(api_version, str)
        and not api_version.startswith("odcs")  # Exclude ODCS
    ):
        # Extract version from apiVersion (e.g., "v1.0.0" → "1.0.0")
        ver = api_version.lstrip("vV").strip()
        if ver and re.match(r"^\d+\.\d+\.\d+$", ver):
            return f"bitol-{ver}"

    return ""


def _extract_version_from_schema_url(schema_url: str) -> str:
    """
    Extract ODPS version from schema URL.

    Supports multiple URL formats:
    - https://opendataproducts.org/schema/v{version}
    - https://schemas.opendataproducts.io/spec/v{version}/product.json

    Args:
        schema_url: Schema URL string

    Returns:
        Normalized version string or "unknown"
    """
    if not schema_url or not isinstance(schema_url, str):
        return "unknown"

    # Pattern 1: https://opendataproducts.org/schema/v{version}
    # Pattern 2: https://schemas.opendataproducts.io/spec/v{version}/product.json
    # Pattern 3: https://schemas.opendataproducts.io/spec/v{version}/...

    patterns = [
        # opendataproducts.org/schema/v{version}
        r'opendataproducts\.org/schema/v([\d.]+)',
        # schemas.opendataproducts.io/spec/v{version}
        r'schemas\.opendataproducts\.io/spec/v([\d.]+)',
        # Generic v{version} pattern as fallback
        r'/v([\d.]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, schema_url, re.IGNORECASE)
        if match:
            version_str = match.group(1)
            return _normalize_version_string(version_str)

    return "unknown"


def _normalize_version_from_field(version_field: Any) -> str:
    """
    Normalize version from version field.

    Handles various formats:
    - String: "4.1", "4.0", "3.9", etc.
    - Integer: 4 (treated as 4.0)
    - Float: 4.1

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
    - "4.1" -> "4.1"
    - "4.0" -> "4.0"
    - "3.9", "3.8", "3.7", etc. -> "3.x"
    - "2.9", "2.8", "2.7", etc. -> "2.x"
    - "1.9", "1.8", "1.7", etc. -> "1.x"
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
    if len(parts) < 2:
        # Try to parse as single number (e.g., "4" -> "4.0")
        try:
            major = int(parts[0])
            return f"{major}.0"
        except (ValueError, IndexError):
            return "unknown"

    try:
        major = int(parts[0])
        minor_str = parts[1]

        # Check if minor is a number or "x"
        if minor_str.lower() == 'x':
            return f"{major}.x"

        minor = int(minor_str)

        # Normalize to supported versions
        if major == 4:
            # 4.2, 4.1, and 4.0 are exact versions
            if minor == 2:
                return "4.2"
            elif minor == 1:
                return "4.1"
            elif minor == 0:
                return "4.0"
            else:
                # Other 4.x versions -> "4.2" (latest supported)
                return "4.2"
        elif major == 3:
            # All 3.x versions -> "3.x"
            return "3.x"
        elif major == 2:
            # All 2.x versions -> "2.x"
            return "2.x"
        elif major == 1:
            # All 1.x versions -> "1.x"
            return "1.x"
        else:
            # Unsupported major version
            return "unknown"

    except (ValueError, IndexError):
        return "unknown"

