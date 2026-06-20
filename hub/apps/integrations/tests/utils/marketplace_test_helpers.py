"""
Marketplace Connector Test Helper Utilities

Provides centralized, reusable utilities for marketplace connector tests (supports both CKAN and Swagger connectors).
Uses the marketplace instance configuration system for consistent test setup.

All utilities use real marketplace instances - no mocks or stubs.
"""

import logging
import os
import warnings
from pathlib import Path

# Sentinel to distinguish "caller did not pass instance_name" from "caller passed None"
_USE_DEFAULT_INSTANCE: object = object()

import httpx

from hub.apps.integrations.base import DataMarketplaceConnector
from hub.apps.integrations.config.marketplace_instances import (
    MarketplaceInstanceConfig,
    get_default_test_instance,
    get_marketplace_instance_config,
)
from hub.apps.integrations.connectors.ckan_connector import CKANConnector

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Load environment variables from .env.test.ckan if it exists."""
    # Get project root (3 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent.parent
    env_file = project_root / ".env.test.ckan"

    if env_file.exists():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Remove 'export ' prefix if present
                        key = key.replace("export ", "").strip()
                        value = value.strip().strip('"').strip("'")
                        # Support both CKAN_* (for actual CKAN instances) and DADOS_GOV_BR_* (for dados.gov.br Swagger API)
                        # Also support deprecated CKAN_DADOS_GOV_BR_API_KEY for backward compatibility
                        if key.startswith("CKAN_") or key.startswith("DADOS_GOV_BR_"):
                            os.environ[key] = value
                            logger.debug(f"Loaded marketplace env var from .env.test.ckan: {key}")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            logger.warning(f"Failed to load .env.test.ckan: {e}")


# Load environment file on module import
_load_env_file()


def get_test_marketplace_config(
    instance_name: str | None | object = _USE_DEFAULT_INSTANCE, prefer_production: bool = False
) -> MarketplaceInstanceConfig | None:
    """
    Get marketplace connector test configuration using the centralized config system.

    This function provides a unified way to get marketplace connector test configuration,
    using the instance registry and environment variable resolution. Supports both
    CKAN-standard APIs and custom Swagger APIs.

    Args:
        instance_name: Optional specific instance name (e.g., "dados.gov.br" for Swagger API, "demo.ckan.org" for CKAN API).
                      If None or empty string, returns None (no instance). If omitted, uses default test instance.
        prefer_production: If True and instance_name is omitted, prefer production instance.
                          Default: False (prefers test instances).

    Returns:
        MarketplaceInstanceConfig if available, None otherwise

    Priority order (when instance_name is omitted):
    1. CKAN_TEST_URL environment variable (if matches registered instance)
    2. Default test instance (demo.ckan.org)
    3. Production instance (if prefer_production=True)

    Example:
        >>> config = get_test_marketplace_config()
        >>> print(config.base_url)
        https://demo.ckan.org
        >>> print(config.connector_type)
        ckan

        >>> config = get_test_marketplace_config("dados.gov.br")
        >>> print(config.base_url)
        https://dados.gov.br
        >>> print(config.connector_type)
        swagger
    """
    # Explicit None or empty string means "no instance" (e.g. for error-path tests)
    if instance_name is None or (isinstance(instance_name, str) and not instance_name.strip()):
        return None
    # Omitted argument: use default logic
    if instance_name is _USE_DEFAULT_INSTANCE:
        instance_name = None  # will trigger env + default path below

    # If specific instance requested, use it (instance_name is str here)
    if instance_name:
        config = get_marketplace_instance_config(str(instance_name))
        if config:
            logger.debug(
                f"Using requested marketplace instance: {instance_name} (connector_type={config.connector_type})"
            )
            return config
        logger.warning(f"Requested marketplace instance not found: {instance_name}")
        return None

    # Check environment variable first
    test_url = os.getenv("CKAN_TEST_URL", "").strip()
    if test_url:
        # Try to match against registered instances
        # Extract hostname from URL
        try:
            from urllib.parse import urlparse

            parsed = urlparse(test_url)
            hostname = parsed.netloc or parsed.path.split("/")[0]

            # Try exact match first
            config = get_marketplace_instance_config(hostname)
            if config:
                logger.debug(
                    f"Using marketplace instance from CKAN_TEST_URL: {hostname} (connector_type={config.connector_type})"
                )
                return config

            # Try without port
            if ":" in hostname:
                hostname_no_port = hostname.split(":")[0]
                config = get_marketplace_instance_config(hostname_no_port)
                if config:
                    logger.debug(
                        f"Using marketplace instance from CKAN_TEST_URL (no port): {hostname_no_port} (connector_type={config.connector_type})"
                    )
                    return config
        except Exception as e:
            logger.debug(f"Failed to parse CKAN_TEST_URL: {e}")

    # Use default test instance
    if not prefer_production:
        config = get_default_test_instance()
        if config:
            logger.debug(
                f"Using default test marketplace instance: {config.name} (connector_type={config.connector_type})"
            )
            return config

    # Fallback to production instance if requested
    if prefer_production:
        config = get_marketplace_instance_config("dados.gov.br")
        if config:
            logger.debug(
                f"Using production marketplace instance: {config.name} (connector_type={config.connector_type})"
            )
            return config

    logger.warning("No marketplace test configuration available")
    return None


def create_test_connector(
    instance_name: str | None | object = _USE_DEFAULT_INSTANCE,
    api_key: str | None = None,
    prefer_production: bool = False,
    verify_connection: bool = True,
) -> DataMarketplaceConnector | None:
    """
    Create a marketplace connector instance for testing.

    Uses the centralized configuration system to create connectors
    with proper configuration and API key resolution. Supports both
    CKAN-standard APIs and custom Swagger APIs.

    Args:
        instance_name: Optional specific instance name. If None, uses default test instance.
        api_key: Optional API key/JWT token. If None, resolves from environment variables via config.
        prefer_production: If True and instance_name is None, prefer production instance.
        verify_connection: If True, verify connection before returning connector.

    Returns:
        DataMarketplaceConnector instance (CKANConnector or DadosGovBrConnector) if successful,
        None if configuration unavailable or connection fails

    Example:
        >>> connector = create_test_connector()
        >>> if connector:
        ...     listings = connector.list_listings(limit=1)

        >>> connector = create_test_connector("dados.gov.br", api_key="my-jwt-token")
        >>> if connector:
        ...     connector.test_connection()
    """
    # Get configuration
    config = get_test_marketplace_config(
        instance_name=instance_name, prefer_production=prefer_production
    )
    if not config:
        logger.warning("Cannot create test connector: no configuration available")
        return None

    # Resolve API key/JWT token
    resolved_api_key = api_key
    if not resolved_api_key and config.api_key_env_var:
        resolved_api_key = config.get_api_key()

    # Also check legacy environment variables for backward compatibility
    if not resolved_api_key:
        legacy_key = os.getenv("CKAN_TEST_API_KEY", "")
        if legacy_key:
            resolved_api_key = legacy_key
            logger.debug("Using API key from CKAN_TEST_API_KEY environment variable")

    # Create connector based on connector type
    try:
        if config.connector_type == "swagger":
            # Use DadosGovBrConnector for Swagger API instances
            from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

            swagger_spec_url = getattr(config, "swagger_spec_url", None)
            connector = DadosGovBrConnector(
                base_url=config.base_url,
                jwt_token=resolved_api_key or "",
                swagger_spec_url=swagger_spec_url,
            )
        else:
            # Use CKANConnector for CKAN API instances
            connector = CKANConnector(
                base_url=config.base_url, api_key=resolved_api_key if resolved_api_key else None
            )

        # Verify connection if requested.
        # Reset any stale circuit breaker state first — ``--reuse-db`` reuses
        # the Redis cache, and a circuit left OPEN from a previous test run
        # would cause the connection verification to fail spuriously.
        if verify_connection:
            try:
                from hub.apps.core.resilience.circuit_breaker import (
                    reset_circuit_breaker_by_name,
                )

                reset_circuit_breaker_by_name("ckan-connector")
            except Exception:
                pass

        if verify_connection and not verify_marketplace_connection(connector):
            logger.warning(f"Connection verification failed for {config.name}")
            return None

        logger.debug(
            f"Created test connector for {config.name} (connector_type={config.connector_type})"
        )
        return connector

    except (ImportError, ValueError, httpx.RequestError, HubConnectionError, KeyError) as e:
        logger.error(f"Failed to create test connector: {e}")
        return None


def verify_marketplace_connection(connector: DataMarketplaceConnector) -> bool:
    """
    Verify that a marketplace connector can successfully connect to its instance.

    Performs a lightweight connection test using the connector's test_connection() method.
    Supports both CKAN-standard APIs and custom Swagger APIs.

    Args:
        connector: DataMarketplaceConnector instance to verify (CKANConnector or DadosGovBrConnector)

    Returns:
        True if connection successful, False otherwise

    Raises:
        ValueError: If connector is None (invalid input).

    Example:
        >>> connector = CKANConnector(base_url="https://demo.ckan.org")
        >>> if verify_marketplace_connection(connector):
        ...     print("Connection verified")

        >>> connector = DadosGovBrConnector(base_url="https://dados.gov.br")
        >>> if verify_marketplace_connection(connector):
        ...     print("Connection verified")
    """
    if connector is None:
        raise ValueError("connector must not be None")

    try:
        result = connector.test_connection()
        base_url = getattr(connector, "base_url", "unknown")
        if result:
            logger.debug(f"Connection verified for {base_url}")
        else:
            logger.warning(f"Connection test returned False for {base_url}")
        return result
    except Exception as e:
        logger.warning(
            f"Connection verification failed for {getattr(connector, 'base_url', 'unknown')}: {e}"
        )
        return False


def marketplace_available(instance_name: str | None | object = _USE_DEFAULT_INSTANCE) -> bool:
    """
    Check if a marketplace connector instance is available for testing.

    Uses the configuration system to determine availability. Supports both
    CKAN-standard APIs and custom Swagger APIs.

    Args:
        instance_name: Optional specific instance name. If None or empty string, returns False.
                      If omitted, checks default test instance.

    Returns:
        True if marketplace instance is available, False otherwise

    Example:
        >>> if marketplace_available():
        ...     print("Marketplace connector is available for testing")
    """
    config = get_test_marketplace_config(instance_name=instance_name)
    if not config:
        return False

    # Try a quick connectivity check
    try:
        if config.connector_type == "swagger":
            # For Swagger API, try a simple GET request to base URL
            response = httpx.get(config.base_url, timeout=5)
            return response.status_code < 500
        else:
            # For CKAN API, use standard status endpoint
            response = httpx.get(f"{config.base_url}/api/3/action/status_show", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
    except Exception:
        pass

    return False


# Backward compatibility functions
# These maintain compatibility with existing test code


def get_test_ckan_url() -> str | None:
    """
    Get marketplace connector test URL from environment or use default public instance.

    This function is maintained for backward compatibility.
    New code should use get_test_marketplace_config() instead.

    Returns:
        Marketplace instance URL string if available, None otherwise
    """
    config = get_test_marketplace_config()
    if config:
        return config.base_url

    # Fallback to legacy behavior
    url = os.getenv("CKAN_TEST_URL", "").strip()
    if url:
        return url

    # Try public marketplace instances (including dados.gov.br Swagger API and CKAN instances)
    public_instances = [
        "https://demo.ckan.org",
        "https://dados.gov.br",
        "https://data.gov",
    ]

    for instance_url in public_instances:
        try:
            # Try CKAN status endpoint first
            response = httpx.get(f"{instance_url}/api/3/action/status_show", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return instance_url
        except Exception:
            # If CKAN endpoint fails, try basic connectivity (for Swagger API)
            try:
                response = httpx.get(instance_url, timeout=5)
                if response.status_code < 500:
                    return instance_url
            except Exception:
                continue

    return None


def get_test_api_key() -> str | None:
    """
    Get marketplace connector API key/JWT token for write operations.

    This function is maintained for backward compatibility.
    New code should use get_test_marketplace_config() and config.get_api_key() instead.

    Returns:
        API key/JWT token string if available, None otherwise
    """
    # Check environment variable first
    api_key = os.getenv("CKAN_TEST_API_KEY", "").strip()
    if api_key:
        return api_key

    # Check dados.gov.br specific env var (new name)
    dados_key = os.getenv("DADOS_GOV_BR_API_KEY", "").strip()
    if dados_key:
        return dados_key

    # Backward compatibility: check old env var name
    dados_key_old = os.getenv("CKAN_DADOS_GOV_BR_API_KEY", "").strip()
    if dados_key_old:
        return dados_key_old

    # Try to get from config system
    config = get_test_marketplace_config()
    if config and config.api_key_env_var:
        api_key = config.get_api_key()
        if api_key:
            return api_key

    return None


# Deprecated function aliases for backward compatibility
def get_test_ckan_config(
    instance_name: str | None | object = _USE_DEFAULT_INSTANCE, prefer_production: bool = False
) -> MarketplaceInstanceConfig | None:
    """
    Get marketplace connector test configuration using the centralized config system.

    DEPRECATED: Use get_test_marketplace_config() instead.
    This function is kept for backward compatibility and will be removed in a future version.

    Args:
        instance_name: Optional specific instance name. If None, uses default test instance.
        prefer_production: If True and instance_name is None, prefer production instance.

    Returns:
        MarketplaceInstanceConfig if available, None otherwise
    """
    warnings.warn(
        "get_test_ckan_config() is deprecated, use get_test_marketplace_config() instead. "
        "This function will be removed in a future version.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_test_marketplace_config(
        instance_name=instance_name, prefer_production=prefer_production
    )


def verify_ckan_connection(connector: DataMarketplaceConnector) -> bool:
    """
    Verify that a marketplace connector can successfully connect to its instance.

    DEPRECATED: Use verify_marketplace_connection() instead.
    This function is kept for backward compatibility and will be removed in a future version.

    Args:
        connector: DataMarketplaceConnector instance to verify

    Returns:
        True if connection successful, False otherwise. Returns False for None (backward compatible).
    """
    warnings.warn(
        "verify_ckan_connection() is deprecated, use verify_marketplace_connection() instead. "
        "This function will be removed in a future version.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Backward compatibility: deprecated API returns False for None instead of raising
    if connector is None:
        return False
    return verify_marketplace_connection(connector)


def ckan_available(instance_name: str | None | object = _USE_DEFAULT_INSTANCE) -> bool:
    """
    Check if a marketplace connector instance is available for testing.

    DEPRECATED: Use marketplace_available() instead.
    This function is kept for backward compatibility and will be removed in a future version.

    Args:
        instance_name: Optional specific instance name. If None, checks default test instance.

    Returns:
        True if marketplace instance is available, False otherwise
    """
    warnings.warn(
        "ckan_available() is deprecated, use marketplace_available() instead. "
        "This function will be removed in a future version.",
        DeprecationWarning,
        stacklevel=2,
    )
    return marketplace_available(instance_name=instance_name)
