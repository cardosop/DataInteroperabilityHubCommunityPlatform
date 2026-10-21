"""
Marketplace Instance Configuration System

Provides centralized configuration management for marketplace connector instances.
Supports multiple connector types (CKAN-standard APIs and custom Swagger APIs) with
metadata, environment variable-based API key resolution, and helper functions for
instance lookup.

Configuration includes:
- dados.gov.br as primary production Swagger API instance
- demo.ckan.org and data.gov as CKAN API test/fallback instances
- Environment variable-based API key configuration
"""

import logging
import os
import warnings
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketplaceInstanceConfig:
    """
    Configuration for a marketplace connector instance (supports CKAN and Swagger APIs).

    Attributes:
        name: Unique identifier for the instance (e.g., "dados.gov.br", "demo.ckan.org")
        base_url: Base URL of the marketplace instance (e.g., "https://dados.gov.br")
        country: ISO country code (e.g., "BR", "US")
        language: Language code (e.g., "pt-BR", "en-US")
        organization: Organization name (e.g., "Brazilian Government")
        swagger_url: URL to Swagger/OpenAPI documentation (optional)
        swagger_spec_url: URL to Swagger JSON specification (optional)
        api_key_env_var: Environment variable name for API key (optional)
        connector_type: Connector type - "ckan" for standard CKAN connector, "swagger" for Swagger-based connector (default: "ckan")
        is_production: Whether this is a production instance (default: False)
        is_test_default: Whether this is the default test instance (default: False)
    """

    name: str
    base_url: str
    country: str | None = None
    language: str | None = None
    organization: str | None = None
    swagger_url: str | None = None
    swagger_spec_url: str | None = None
    api_key_env_var: str | None = None
    connector_type: str = "ckan"  # "ckan" or "swagger"
    is_production: bool = False
    is_test_default: bool = False

    def get_api_key(self) -> str | None:
        """
        Get API key/JWT token from environment variable if configured.

        For dados.gov.br, supports backward compatibility by checking both:
        - DADOS_GOV_BR_API_KEY (new name, preferred)
        - CKAN_DADOS_GOV_BR_API_KEY (deprecated, for backward compatibility)

        Returns:
            API key/JWT token string if environment variable is set, None otherwise
        """
        if not self.api_key_env_var:
            return None

        # Check primary environment variable
        api_key = os.getenv(self.api_key_env_var)

        # For dados.gov.br, also check deprecated environment variable for backward compatibility
        if not api_key and self.api_key_env_var == "DADOS_GOV_BR_API_KEY":
            deprecated_var = "CKAN_DADOS_GOV_BR_API_KEY"
            api_key = os.getenv(deprecated_var)
            if api_key:
                logger.debug(
                    f"Resolved API key from deprecated environment variable for instance {self.name} "
                    f"(deprecated_env_var={deprecated_var}). Please use {self.api_key_env_var} instead."
                )

        if api_key:
            logger.debug(
                f"Resolved API key from environment variable for instance {self.name} "
                f"(env_var={self.api_key_env_var})"
            )
        else:
            logger.debug(
                f"API key environment variable not set for instance {self.name} "
                f"(env_var={self.api_key_env_var})"
            )

        return api_key


# Marketplace Instance Registry
# Register all known marketplace connector instances with their configuration
MARKETPLACE_INSTANCES: dict[str, MarketplaceInstanceConfig] = {
    "dados.gov.br": MarketplaceInstanceConfig(
        name="dados.gov.br",
        base_url="https://dados.gov.br",
        country="BR",
        language="pt-BR",
        organization="Brazilian Government",
        swagger_url="https://dados.gov.br/swagger-ui/index.html",
        swagger_spec_url="https://dados.gov.br/v3/api-docs",
        api_key_env_var="DADOS_GOV_BR_API_KEY",  # JWT Bearer token for dados.gov.br Swagger API
        connector_type="swagger",  # Use Swagger-based connector (NOT CKAN)
        is_production=True,
        is_test_default=False,
    ),
    "demo.ckan.org": MarketplaceInstanceConfig(
        name="demo.ckan.org",
        base_url="https://demo.ckan.org",
        country=None,
        language=None,
        organization="CKAN Demo",
        swagger_url="https://demo.ckan.org/api/3/swagger.json",
        api_key_env_var=None,
        connector_type="ckan",  # Standard CKAN API
        is_production=False,
        is_test_default=False,
    ),
    "ckan-test": MarketplaceInstanceConfig(
        name="ckan-test",
        base_url=os.getenv("CKAN_TEST_URL", "http://ckan-test:5000"),
        country=None,
        language=None,
        organization="Local CKAN Test",
        api_key_env_var="CKAN_TEST_API_KEY",
        connector_type="ckan",  # Standard CKAN API
        is_production=False,
        is_test_default=True,
    ),
    "data.gov": MarketplaceInstanceConfig(
        name="data.gov",
        base_url="https://data.gov",
        country="US",
        language="en-US",
        organization="U.S. Government",
        swagger_url="https://data.gov/api/3/swagger.json",
        api_key_env_var=None,
        connector_type="ckan",  # Standard CKAN API
        is_production=False,
        is_test_default=False,
    ),
}


def get_marketplace_instance_config(instance_name: str | None) -> MarketplaceInstanceConfig | None:
    """
    Get configuration for a marketplace connector instance by name.

    Args:
        instance_name: Name of the marketplace instance (e.g., "dados.gov.br", "demo.ckan.org")
                      Case-insensitive, whitespace is stripped.

    Returns:
        MarketplaceInstanceConfig if instance is registered, None otherwise

    Example:
        >>> config = get_marketplace_instance_config("dados.gov.br")
        >>> print(config.base_url)
        https://dados.gov.br
        >>> print(config.connector_type)
        swagger
    """
    if not instance_name or not isinstance(instance_name, str):
        return None

    # Normalize instance name: strip whitespace and convert to lowercase
    normalized_name = instance_name.strip().lower()

    # Look up in registry
    config = MARKETPLACE_INSTANCES.get(normalized_name)

    if config:
        logger.debug(
            f"Retrieved marketplace instance configuration for {normalized_name} "
            f"(base_url={config.base_url}, connector_type={config.connector_type})"
        )
    else:
        logger.debug(
            f"Marketplace instance {normalized_name} not found in registry. "
            f"Available instances: {list(MARKETPLACE_INSTANCES.keys())}"
        )

    return config


def get_default_test_instance() -> MarketplaceInstanceConfig | None:
    """
    Get the default test marketplace connector instance configuration.

    Returns the first instance marked as is_test_default=True.
    Falls back to demo.ckan.org if no instance is marked as test default.

    Returns:
        MarketplaceInstanceConfig for the default test instance, or None if not found

    Example:
        >>> config = get_default_test_instance()
        >>> print(config.name)
        demo.ckan.org
    """
    # Find instance marked as test default
    for name, config in MARKETPLACE_INSTANCES.items():
        if config.is_test_default:
            logger.debug(
                f"Retrieved default test marketplace instance: {name} "
                f"(base_url={config.base_url}, connector_type={config.connector_type})"
            )
            return config

    # Fallback to demo.ckan.org if no instance is marked as test default
    fallback_config = MARKETPLACE_INSTANCES.get("demo.ckan.org")
    if fallback_config:
        logger.debug(
            f"Using demo.ckan.org as fallback default test instance "
            f"(base_url={fallback_config.base_url})"
        )
        return fallback_config

    logger.warning("No default test marketplace instance found in registry")
    return None


# Backward compatibility aliases with deprecation warnings
def _deprecated_alias(old_name: str, new_name: str, obj):
    """Create a deprecated alias that warns when accessed."""
    import functools

    @functools.wraps(obj)
    def wrapper(*args, **kwargs):
        warnings.warn(
            f"{old_name} is deprecated, use {new_name} instead. "
            f"This alias will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )
        return obj(*args, **kwargs)

    return wrapper


# Deprecated aliases for backward compatibility
CKANInstanceConfig = MarketplaceInstanceConfig
CKAN_INSTANCES = MARKETPLACE_INSTANCES


# Deprecated function alias with warning
def get_ckan_instance_config(instance_name: str | None) -> MarketplaceInstanceConfig | None:
    """
    Get configuration for a CKAN instance by name.

    DEPRECATED: Use get_marketplace_instance_config() instead.
    This function is kept for backward compatibility and will be removed in a future version.

    Args:
        instance_name: Name of the marketplace instance (e.g., "dados.gov.br")
                      Case-insensitive, whitespace is stripped.

    Returns:
        MarketplaceInstanceConfig if instance is registered, None otherwise
    """
    warnings.warn(
        "get_ckan_instance_config() is deprecated, use get_marketplace_instance_config() instead. "
        "This function will be removed in a future version.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_marketplace_instance_config(instance_name)
