"""
Utilities for virtualization source configuration.

Provides credential masking for API responses so sensitive fields
(password, connection_string, etc.) are never exposed.
"""
from typing import Any, Dict, List

# Fields to mask in source configs when returning via API
SENSITIVE_SOURCE_FIELDS = [
    "password",
    "pwd",
    "secret",
    "secret_key",
    "api_key",
    "token",
    "connection_string",
    "credentials",
    "credentials_json",
    "private_key",
]


def mask_source_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive fields in a source configuration for API response.

    Args:
        config: Source config dict (may contain password, connection_string, etc.)

    Returns:
        Copy of config with sensitive values replaced by "***masked***"
    """
    if not config or not isinstance(config, dict):
        return config

    masked = {}
    for key, value in config.items():
        key_lower = key.lower()
        is_sensitive = any(
            s in key_lower for s in SENSITIVE_SOURCE_FIELDS
        )
        if is_sensitive and value:
            masked[key] = "***masked***"
        else:
            masked[key] = value
    return masked


def mask_sources_for_api(
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Mask sensitive fields in all source configs for API response.

    Args:
        sources: List of source configuration dictionaries

    Returns:
        List of configs with sensitive values masked.
    """
    if not sources or not isinstance(sources, list):
        return sources or []
    return [mask_source_config(s) for s in sources]
