"""
ODPS Schema Loading Utilities

Provides functions for loading and managing ODPS JSON Schema files.
Includes in-memory caching for performance optimization.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache

# In-memory cache for loaded schemas (per-version)
# Key: normalized version string (e.g., "4.1", "3.x")
# Value: loaded schema dictionary
_schema_cache: Dict[str, Dict[str, Any]] = {}


def load_odps_schema(version: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    Load ODPS JSON Schema for given version.

    This function loads the JSON Schema file for the specified ODPS version
    from the schemas directory. It handles version normalization, provides
    clear error messages for missing or invalid schema files, and includes
    in-memory caching for performance optimization.

    Args:
        version: ODPS version string (e.g., "4.1", "4.0", "3.x", "2.x", "1.x")
                 Can also accept versions with "v" prefix (e.g., "v4.1")
        use_cache: Whether to use in-memory cache (default: True).
                   Set to False to force reload from disk.

    Returns:
        JSON Schema dictionary loaded from the schema file

    Raises:
        FileNotFoundError: If schema file not found for the specified version
        json.JSONDecodeError: If schema file contains invalid JSON
        ValueError: If version format is invalid
        IOError: If there's an error reading the schema file

    Example:
        >>> schema = load_odps_schema("4.1")
        >>> schema = load_odps_schema("v4.1")
        >>> schema = load_odps_schema("3.x")
        >>> schema = load_odps_schema("4.1", use_cache=False)  # Force reload
    """
    if not version or not isinstance(version, str):
        raise ValueError(f"Version must be a non-empty string, got: {type(version)}")

    # Normalize version: remove "v" prefix if present and strip whitespace
    normalized_version = version.strip()
    if normalized_version.startswith('v'):
        normalized_version = normalized_version[1:]

    # Check cache first (if caching is enabled)
    if use_cache and normalized_version in _schema_cache:
        return _schema_cache[normalized_version]

    # Determine version directory name
    # All version directories have "v" prefix: v4.1, v4.0, v3.x, v2.x, v1.x
    version_dir = f"v{normalized_version}"

    # Get the base directory (hub/apps/contracts)
    # This file is in hub/apps/contracts/, so parent is the contracts app directory
    base_dir = Path(__file__).parent
    schema_path = base_dir / "schemas" / "odps" / version_dir / "odps-schema.json"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"ODPS schema not found for version '{version}' (normalized: '{normalized_version}', dir: '{version_dir}'). "
            f"Expected path: {schema_path}"
        )

    if not schema_path.is_file():
        raise FileNotFoundError(
            f"ODPS schema path exists but is not a file for version '{version}': {schema_path}"
        )

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in ODPS schema file for version '{version}': {schema_path}",
            e.doc,
            e.pos
        ) from e
    except Exception as e:
        raise IOError(
            f"Error reading ODPS schema file for version '{version}': {schema_path}. "
            f"Error: {e}"
        ) from e

    # Validate that loaded data is a dictionary (JSON Schema should be an object)
    if not isinstance(schema_data, dict):
        raise ValueError(
            f"ODPS schema file for version '{version}' does not contain a JSON object. "
            f"Got type: {type(schema_data)}"
        )

    # Cache the loaded schema (if caching is enabled)
    if use_cache:
        _schema_cache[normalized_version] = schema_data

    return schema_data


def get_available_odps_versions() -> list[str]:
    """
    Get list of available ODPS schema versions.

    Scans the schemas/odps directory to find all available version directories
    and returns a list of normalized version strings.

    Returns:
        List of available ODPS version strings (e.g., ["4.1", "4.0", "3.x", "2.x", "1.x"])

    Example:
        >>> versions = get_available_odps_versions()
        >>> print(versions)
        ['4.1', '4.0', '3.x', '2.x', '1.x']
    """
    base_dir = Path(__file__).parent
    odps_schemas_dir = base_dir / "schemas" / "odps"

    if not odps_schemas_dir.exists():
        return []

    versions = []
    for version_dir in odps_schemas_dir.iterdir():
        if not version_dir.is_dir():
            continue

        schema_file = version_dir / "odps-schema.json"
        if not schema_file.exists():
            continue

        # Normalize version directory name back to version string
        # All directories have "v" prefix, so remove it
        version_name = version_dir.name
        if version_name.startswith('v'):
            version = version_name[1:]
        else:
            # If somehow no "v" prefix, use as-is
            version = version_name

        versions.append(version)

    # Sort versions: numeric versions first (descending), then .x versions (descending)
    def version_sort_key(v: str) -> tuple:
        if v.endswith('.x'):
            # .x versions go last, sorted by major version (descending)
            major = int(v.split('.')[0]) if v.split('.')[0].isdigit() else 0
            return (1, -major)  # 1 means .x version, negative for descending
        else:
            # Numeric versions, sorted descending
            parts = v.split('.')
            major = int(parts[0]) if parts[0].isdigit() else 0
            minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return (0, -major, -minor)  # 0 means numeric version, negative for descending

    return sorted(versions, key=version_sort_key)


def clear_schema_cache() -> None:
    """
    Clear the in-memory schema cache.

    This function clears all cached schemas, forcing them to be reloaded
    from disk on the next call to load_odps_schema().

    Useful for:
    - Testing (to ensure fresh schema loads)
    - Development (when schema files are updated)
    - Memory management (if needed)

    Example:
        >>> clear_schema_cache()
        >>> schema = load_odps_schema("4.1")  # Will reload from disk
    """
    global _schema_cache
    _schema_cache.clear()


def get_cached_schema_versions() -> list[str]:
    """
    Get list of versions currently cached in memory.

    Returns:
        List of normalized version strings that are currently cached

    Example:
        >>> load_odps_schema("4.1")
        >>> load_odps_schema("3.x")
        >>> cached = get_cached_schema_versions()
        >>> print(cached)
        ['4.1', '3.x']
    """
    return list(_schema_cache.keys())

