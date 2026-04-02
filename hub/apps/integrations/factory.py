"""
Marketplace Connector Factory

Factory for creating marketplace connectors based on marketplace type.
Follows the same pattern as SourceConnectorFactory for consistency.
"""
import logging
from typing import Dict, List, Type, Optional, Any
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
)
from hub.apps.integrations.config.marketplace_instances import (
    get_marketplace_instance_config,
    MARKETPLACE_INSTANCES,
    # Backward compatibility (deprecated)
    get_ckan_instance_config,
    CKAN_INSTANCES,
)

logger = logging.getLogger(__name__)

# Sentinel object to detect if api_key was not provided
_NOT_PROVIDED = object()


class MarketplaceConnectorFactory:
    """
    Factory for creating marketplace connectors.

    Provides a centralized registry for marketplace connector implementations,
    allowing dynamic registration and retrieval of connectors by marketplace type.

    The factory follows a singleton-like pattern where connector classes are
    registered once and can be retrieved multiple times. Each call to
    get_connector() creates a new instance of the connector class.

    Example:
        # Register a connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            SnowflakeConnector
        )

        # Get a connector instance
        connector = MarketplaceConnectorFactory.get_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
        )

        # Get all supported types
        types = MarketplaceConnectorFactory.get_supported_types()
    """

    # Class-level registry of connector classes
    # Maps MarketplaceType enum values to connector class types
    _connectors: Dict[str, Type[DataMarketplaceConnector]] = {}

    @classmethod
    def register_connector(
        cls,
        marketplace_type: MarketplaceType,
        connector_class: Type[DataMarketplaceConnector]
    ) -> None:
        """
        Register a marketplace connector class.

        Registers a connector implementation for a specific marketplace type.
        The connector class must inherit from DataMarketplaceConnector and
        implement all abstract methods.

        Args:
            marketplace_type: MarketplaceType enum value for the connector
            connector_class: Connector class (must inherit from DataMarketplaceConnector)

        Raises:
            ValueError: If connector_class does not inherit from DataMarketplaceConnector
            TypeError: If marketplace_type is not a MarketplaceType enum value

        Example:
            MarketplaceConnectorFactory.register_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                SnowflakeMarketplaceConnector
            )
        """
        # Validate marketplace_type is a MarketplaceType enum
        if not isinstance(marketplace_type, MarketplaceType):
            raise TypeError(
                f"marketplace_type must be a MarketplaceType enum value, "
                f"got {type(marketplace_type).__name__}"
            )

        # Validate connector_class inherits from DataMarketplaceConnector
        if not issubclass(connector_class, DataMarketplaceConnector):
            raise ValueError(
                f"Connector class must inherit from DataMarketplaceConnector: "
                f"{connector_class.__name__}"
            )

        # Register the connector using the enum value as the key
        cls._connectors[marketplace_type.value] = connector_class

    @classmethod
    def get_connector(
        cls,
        marketplace_type: MarketplaceType
    ) -> DataMarketplaceConnector:
        """
        Get a connector instance for the given marketplace type.

        Creates and returns a new instance of the connector class registered
        for the specified marketplace type. Each call creates a new instance,
        allowing multiple independent connector instances.

        Args:
            marketplace_type: MarketplaceType enum value for the connector

        Returns:
            DataMarketplaceConnector instance

        Raises:
            ValueError: If marketplace type is not supported (no connector registered)
            TypeError: If marketplace_type is not a MarketplaceType enum value

        Example:
            connector = MarketplaceConnectorFactory.get_connector(
                MarketplaceType.AWS_DATA_EXCHANGE
            )
            listings = connector.list_listings()
        """
        # Validate marketplace_type is a MarketplaceType enum
        if not isinstance(marketplace_type, MarketplaceType):
            raise TypeError(
                f"marketplace_type must be a MarketplaceType enum value, "
                f"got {type(marketplace_type).__name__}"
            )

        # Check if connector is registered for this marketplace type
        if marketplace_type.value not in cls._connectors:
            supported_types = ", ".join(sorted(cls._connectors.keys()))
            raise ValueError(
                f"Unsupported marketplace type: {marketplace_type.value}. "
                f"Supported types: {supported_types if supported_types else 'none registered'}"
            )

        # Get the connector class and create a new instance
        connector_class = cls._connectors[marketplace_type.value]
        return connector_class()

    @classmethod
    def create_connector(
        cls,
        marketplace_type: MarketplaceType,
        config: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DataMarketplaceConnector:
        """
        Create a connector instance with configuration.

        Creates and returns a new instance of the connector class registered
        for the specified marketplace type, initialized with the provided config.

        Args:
            marketplace_type: MarketplaceType enum value for the connector
            config: Optional configuration dictionary for the connector
            tenant_id: Optional tenant ID for context
            user_id: Optional user ID for context

        Returns:
            DataMarketplaceConnector instance initialized with config

        Raises:
            ValueError: If marketplace type is not supported (no connector registered)
            TypeError: If marketplace_type is not a MarketplaceType enum value

        Example:
            connector = MarketplaceConnectorFactory.create_connector(
                MarketplaceType.AWS_DATA_EXCHANGE,
                config={"api_key": "key", "endpoint": "https://api.example.com"},
                tenant_id="tenant-123",
                user_id="user-456"
            )
        """
        # Validate marketplace_type is a MarketplaceType enum
        if not isinstance(marketplace_type, MarketplaceType):
            raise TypeError(
                f"marketplace_type must be a MarketplaceType enum value, "
                f"got {type(marketplace_type).__name__}"
            )

        # Check if connector is registered for this marketplace type
        if marketplace_type.value not in cls._connectors:
            supported_types = ", ".join(sorted(cls._connectors.keys()))
            raise ValueError(
                f"Unsupported marketplace type: {marketplace_type.value}. "
                f"Supported types: {supported_types if supported_types else 'none registered'}"
            )

        # Get the connector class
        connector_class = cls._connectors[marketplace_type.value]

        # Try to create connector with config if __init__ accepts it
        # Connectors may have different __init__ signatures, so we try common patterns
        try:
            # Try with config if provided
            if config is not None:
                import inspect
                sig = inspect.signature(connector_class.__init__)
                params = sig.parameters

                # Check if __init__ accepts config parameter
                if 'config' in params:
                    # Try with config, tenant_id, user_id if they're in signature
                    kwargs = {'config': config}
                    if 'tenant_id' in params and tenant_id:
                        kwargs['tenant_id'] = tenant_id
                    if 'user_id' in params and user_id:
                        kwargs['user_id'] = user_id
                    try:
                        return connector_class(**kwargs)
                    except TypeError:
                        # Try with just config
                        return connector_class(config=config)
                # Special handling for CKANConnector which expects base_url and api_key
                elif 'base_url' in params:
                    kwargs = {}
                    # Check if instance_id is provided - use instance config if available
                    if 'instance_id' in config and marketplace_type == MarketplaceType.CKAN_INSTANCE:
                        instance_config = get_marketplace_instance_config(config['instance_id'])
                        if instance_config:
                            # Check connector type and use appropriate connector class
                            connector_type = getattr(instance_config, 'connector_type', 'ckan')

                            if connector_type == 'swagger':
                                # Use DadosGovBrConnector for Swagger-based instances
                                try:
                                    from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
                                except ImportError:
                                    raise ValueError(
                                        "DadosGovBrConnector not available. "
                                        "Ensure dados_gov_br_connector.py is properly installed."
                                    )
                                connector_class = DadosGovBrConnector

                                # Use instance configuration for Swagger connector
                                kwargs['base_url'] = instance_config.base_url
                                # Resolve JWT token: override > config api_key > instance env var
                                if 'api_key' in config:
                                    kwargs['jwt_token'] = config['api_key']
                                else:
                                    kwargs['jwt_token'] = instance_config.get_api_key() or ''
                                swagger_spec_url = getattr(instance_config, 'swagger_spec_url', None)
                                if swagger_spec_url:
                                    kwargs['swagger_spec_url'] = swagger_spec_url

                                logger.debug(
                                    f"Using instance configuration for Swagger instance "
                                    f"{instance_config.name} (base_url={instance_config.base_url})"
                                )
                            else:
                                # Use standard CKAN connector
                                # Use instance configuration
                                kwargs['base_url'] = instance_config.base_url
                                # Resolve API key: override > config api_key > instance env var
                                if 'api_key' in config:
                                    kwargs['api_key'] = config['api_key']
                                else:
                                    kwargs['api_key'] = instance_config.get_api_key()

                                logger.debug(
                                    f"Using instance configuration for CKAN instance "
                                    f"{instance_config.name} (base_url={instance_config.base_url})"
                                )
                        else:
                            # Instance not found, fall back to direct config
                            if 'base_url' in config:
                                kwargs['base_url'] = config['base_url']
                            elif 'endpoint' in config:
                                kwargs['base_url'] = config['endpoint']
                            # DadosGovBrConnector expects jwt_token, not api_key
                            if 'jwt_token' in params and 'api_key' not in params:
                                kwargs['jwt_token'] = config.get('jwt_token') or config.get('api_key') or ''
                            elif 'api_key' in config:
                                kwargs['api_key'] = config['api_key']
                    else:
                        # No instance_id, use direct config
                        if 'base_url' in config:
                            kwargs['base_url'] = config['base_url']
                        elif 'endpoint' in config:
                            kwargs['base_url'] = config['endpoint']
                        # DadosGovBrConnector expects jwt_token, not api_key
                        if 'jwt_token' in params and 'api_key' not in params:
                            kwargs['jwt_token'] = config.get('jwt_token') or config.get('api_key') or ''
                        elif 'api_key' in config:
                            kwargs['api_key'] = config['api_key']
                    if 'tenant_id' in params and tenant_id:
                        kwargs['tenant_id'] = tenant_id
                    if 'user_id' in params and user_id:
                        kwargs['user_id'] = user_id
                    try:
                        return connector_class(**kwargs)
                    except TypeError:
                        # Try with just base_url and api_key/jwt_token
                        if 'jwt_token' in kwargs:
                            return connector_class(
                                base_url=kwargs.get('base_url'),
                                jwt_token=kwargs.get('jwt_token', ''),
                                swagger_spec_url=kwargs.get('swagger_spec_url')
                            )
                        else:
                            return connector_class(
                                base_url=kwargs.get('base_url'),
                                api_key=kwargs.get('api_key')
                            )
                # Special handling for SnowflakeConnector which expects account, user, token, etc.
                elif marketplace_type == MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE:
                    # SnowflakeConnector expects: account, user, token, warehouse (optional), role (optional), database (optional)
                    kwargs = {}
                    if 'account' in config:
                        kwargs['account'] = config['account']
                    if 'user' in config:
                        kwargs['user'] = config['user']
                    if 'token' in config:
                        kwargs['token'] = config['token']
                    if 'warehouse' in config:
                        kwargs['warehouse'] = config['warehouse']
                    if 'role' in config:
                        kwargs['role'] = config['role']
                    if 'database' in config:
                        kwargs['database'] = config['database']
                    return connector_class(**kwargs)
                # Special handling for AWSDataExchangeConnector which expects AWS credentials
                elif marketplace_type == MarketplaceType.AWS_DATA_EXCHANGE:
                    # AWSDataExchangeConnector expects: aws_access_key_id, aws_secret_access_key,
                    # aws_session_token (optional), region_name (optional), role_arn (optional)
                    kwargs = {}
                    if 'aws_access_key_id' in config:
                        kwargs['aws_access_key_id'] = config['aws_access_key_id']
                    if 'aws_secret_access_key' in config:
                        kwargs['aws_secret_access_key'] = config['aws_secret_access_key']
                    if 'aws_session_token' in config:
                        kwargs['aws_session_token'] = config['aws_session_token']
                    if 'region_name' in config:
                        kwargs['region_name'] = config['region_name']
                    if 'role_arn' in config:
                        kwargs['role_arn'] = config['role_arn']
                    return connector_class(**kwargs)
                # Special handling for GCPMarketplaceConnector which expects GCP credentials
                elif marketplace_type == MarketplaceType.GOOGLE_CLOUD_MARKETPLACE:
                    # GCPMarketplaceConnector expects: project_id (required), credentials_json (optional),
                    # location (optional, default 'US'), use_adc (optional, default False)
                    kwargs = {}
                    if 'project_id' in config:
                        kwargs['project_id'] = config['project_id']
                    if 'credentials_json' in config:
                        kwargs['credentials_json'] = config['credentials_json']
                    if 'location' in config:
                        kwargs['location'] = config['location']
                    if 'use_adc' in config:
                        kwargs['use_adc'] = config['use_adc']
                    return connector_class(**kwargs)
                # Special handling for DatabricksConnector which expects host, token, cluster_id (optional)
                elif marketplace_type == MarketplaceType.DATABRICKS_MARKETPLACE:
                    # DatabricksConnector expects: host (required), token (required), cluster_id (optional)
                    kwargs = {}
                    if 'host' in config:
                        kwargs['host'] = config['host']
                    if 'token' in config:
                        kwargs['token'] = config['token']
                    if 'cluster_id' in config:
                        kwargs['cluster_id'] = config['cluster_id']
                    return connector_class(**kwargs)
                # Special handling for AzureMarketplaceConnector: base_url, api_key, api_version
                elif marketplace_type == MarketplaceType.AZURE_MARKETPLACE:
                    kwargs = {}
                    if 'base_url' in config:
                        kwargs['base_url'] = config['base_url']
                    if 'api_key' in config:
                        kwargs['api_key'] = config['api_key']
                    if 'api_version' in config:
                        kwargs['api_version'] = config['api_version']
                    return connector_class(**kwargs)
                elif len(params) > 1:  # Has parameters beyond self
                    # Try config as positional argument
                    try:
                        return connector_class(config)
                    except TypeError:
                        # Fall back to no-arg constructor
                        connector = connector_class()
                        # Try to set config via attribute or method
                        if hasattr(connector, 'set_config'):
                            connector.set_config(config)
                        elif hasattr(connector, 'config'):
                            connector.config = config
                        return connector
                else:
                    # No parameters, use default constructor and set config after
                    connector = connector_class()
                    if hasattr(connector, 'set_config'):
                        connector.set_config(config)
                    elif hasattr(connector, 'config'):
                        connector.config = config
                    return connector
            else:
                # No config provided, use default constructor
                return connector_class()
        except Exception as e:
            raise ValueError(
                f"Failed to create connector instance for {marketplace_type.value}: {str(e)}"
            ) from e

    @classmethod
    def get_supported_types(cls) -> List[MarketplaceType]:
        """
        Get a list of all supported marketplace types.

        Returns a list of MarketplaceType enum values for which connectors
        have been registered. The list is sorted alphabetically by enum value.

        Returns:
            List of MarketplaceType enum values that have registered connectors

        Example:
            supported = MarketplaceConnectorFactory.get_supported_types()
            for marketplace_type in supported:
                connector = MarketplaceConnectorFactory.get_connector(marketplace_type)
        """
        # Convert registered keys back to MarketplaceType enum values
        supported_types = []
        for marketplace_value in sorted(cls._connectors.keys()):
            try:
                # Find the MarketplaceType enum member with this value
                marketplace_type = MarketplaceType(marketplace_value)
                supported_types.append(marketplace_type)
            except ValueError:
                # Skip invalid enum values (shouldn't happen, but handle gracefully)
                continue

        return supported_types

    @classmethod
    def is_supported(cls, marketplace_type: MarketplaceType) -> bool:
        """
        Check if a marketplace type is supported.

        Args:
            marketplace_type: MarketplaceType enum value to check

        Returns:
            True if a connector is registered for this marketplace type, False otherwise
        """
        if not isinstance(marketplace_type, MarketplaceType):
            return False

        return marketplace_type.value in cls._connectors

    @classmethod
    def get_capability_matrix(cls) -> Dict[str, Dict[str, Any]]:
        """Return the capability matrix for all registered connectors.

        Returns a dict keyed by marketplace type with each entry
        containing:
          - ``sync_directions``: list of supported SyncDirection values
          - ``supports_push``: bool
          - ``supports_pull``: bool
          - ``connector_class``: fully-qualified class name

        This is the **single source of truth** for connector
        capabilities and can be serialised directly to JSON for
        the frontend capabilities service.
        """
        from hub.apps.integrations.base import SyncDirection

        matrix: Dict[str, Dict[str, Any]] = {}
        for mtype_value, connector_cls in sorted(cls._connectors.items()):
            # Read the property from a bare instance.  Connectors
            # return a static list so no credentials are needed.
            try:
                inst = connector_cls()
                dirs = inst.supported_sync_directions
            except Exception:
                dirs = []
            dir_values = [
                d.value if hasattr(d, "value") else str(d)
                for d in dirs
            ]
            matrix[mtype_value] = {
                "sync_directions": dir_values,
                "supports_push": (
                    SyncDirection.PUSH.value in dir_values
                    or SyncDirection.BIDIRECTIONAL.value in dir_values
                ),
                "supports_pull": (
                    SyncDirection.PULL.value in dir_values
                    or SyncDirection.BIDIRECTIONAL.value in dir_values
                ),
                "connector_class": (
                    f"{connector_cls.__module__}."
                    f"{connector_cls.__qualname__}"
                ),
            }
        return matrix

    @classmethod
    def unregister_connector(cls, marketplace_type: MarketplaceType) -> None:
        """
        Unregister a marketplace connector.

        Removes the connector registration for the specified marketplace type.
        Useful for testing or dynamic connector management.

        Args:
            marketplace_type: MarketplaceType enum value to unregister

        Raises:
            ValueError: If marketplace type is not registered
        """
        if not isinstance(marketplace_type, MarketplaceType):
            raise TypeError(
                f"marketplace_type must be a MarketplaceType enum value, "
                f"got {type(marketplace_type).__name__}"
            )

        if marketplace_type.value not in cls._connectors:
            raise ValueError(
                f"Marketplace type not registered: {marketplace_type.value}"
            )

        del cls._connectors[marketplace_type.value]

    @classmethod
    def create_ckan_connector_from_instance(
        cls,
        instance_id: str,
        api_key: Any = _NOT_PROVIDED
    ) -> DataMarketplaceConnector:
        """
        Create a marketplace connector from a registered instance configuration.

        Looks up the marketplace instance configuration by instance_id and creates the
        appropriate connector based on the instance's connector_type:
        - For connector_type="swagger": Creates DadosGovBrConnector (e.g., dados.gov.br)
        - For connector_type="ckan": Creates CKANConnector (e.g., demo.ckan.org, data.gov)

        Resolves the API key/JWT token from the instance's environment variable
        (if configured) or uses the provided override.

        Note: This method name is kept for backward compatibility. For new code,
        consider using create_marketplace_connector_from_instance() for clarity.

        Args:
            instance_id: Instance identifier (e.g., 'dados.gov.br' for Swagger API,
                        'demo.ckan.org' for CKAN API). Case-insensitive, whitespace is stripped.
            api_key: Optional API key/JWT token override. If provided (including None),
                    takes precedence over environment variable. If not provided
                    and instance has api_key_env_var, resolves from environment.
                    If not provided and instance has no api_key_env_var,
                    connector is created without API key.

        Returns:
            DataMarketplaceConnector instance:
            - DadosGovBrConnector for Swagger API instances (e.g., dados.gov.br)
            - CKANConnector for CKAN API instances (e.g., demo.ckan.org, data.gov)
            Configured with instance's base_url and API key/JWT token

        Raises:
            ValueError: If instance_id is invalid or instance not found in registry
            ValueError: If connector is not registered in factory

        Example:
            # Create connector for dados.gov.br (Swagger API) using environment API key
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id='dados.gov.br'
            )

            # Create connector for demo.ckan.org (CKAN API)
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id='demo.ckan.org'
            )

            # Create connector with API key override
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id='dados.gov.br',
                api_key='custom-api-key-12345'
            )

            # Create connector with explicit None API key (clears env var)
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                instance_id='dados.gov.br',
                api_key=None
            )
        """
        # Validate instance_id
        if not instance_id or not isinstance(instance_id, str):
            raise ValueError(
                f"instance_id must be a non-empty string, got {type(instance_id).__name__}"
            )

        # Get instance configuration (use new function, fallback to deprecated for compatibility)
        instance_config = get_marketplace_instance_config(instance_id)
        if not instance_config:
            available_instances = ", ".join(sorted(MARKETPLACE_INSTANCES.keys()))
            raise ValueError(
                f"Marketplace instance '{instance_id}' not found in registry. "
                f"Available instances: {available_instances if available_instances else 'none'}"
            )

        # Check connector type and import appropriate connector class.
        # Use instance config to choose the class (not the single registry entry), so
        # demo.ckan.org and data.gov get CKANConnector and dados.gov.br gets DadosGovBrConnector.
        connector_type = getattr(instance_config, 'connector_type', 'ckan')

        if connector_type == 'swagger':
            # Import DadosGovBrConnector for Swagger-based instances
            try:
                from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
            except ImportError:
                raise ValueError(
                    "DadosGovBrConnector not available. "
                    "Ensure dados_gov_br_connector.py is properly installed."
                )
            connector_class = DadosGovBrConnector
        else:
            # Use CKANConnector explicitly for CKAN instances (demo.ckan.org, data.gov).
            # Do not use the registry here, as it may hold DadosGovBrConnector for CKAN_INSTANCE.
            try:
                from hub.apps.integrations.connectors.ckan_connector import CKANConnector
            except ImportError:
                raise ValueError(
                    "CKANConnector not available. "
                    "Ensure ckan_connector.py is properly installed."
                )
            connector_class = CKANConnector

        # Resolve API key/JWT token
        # Check if api_key was provided using sentinel
        if api_key is _NOT_PROVIDED:
            # api_key was not provided, resolve from instance configuration
            resolved_api_key = instance_config.get_api_key()
            if resolved_api_key:
                logger.debug(
                    f"Resolved API key/JWT token from environment variable for instance "
                    f"{instance_config.name} "
                    f"(env_var={instance_config.api_key_env_var})"
                )
            else:
                logger.debug(
                    f"No API key/JWT token available for instance {instance_config.name} "
                    f"(env_var={instance_config.api_key_env_var or 'not configured'})"
                )
        else:
            # api_key was explicitly provided (even if None), use it
            resolved_api_key = api_key
            if api_key is not None:
                logger.debug(
                    f"Using API key/JWT token override for instance "
                    f"{instance_config.name}"
                )
            else:
                logger.debug(
                    f"API key/JWT token explicitly set to None for instance "
                    f"{instance_config.name}, clearing environment API key"
                )

        # Create connector with instance configuration
        try:
            if connector_type == 'swagger':
                # DadosGovBrConnector uses jwt_token parameter
                swagger_spec_url = getattr(instance_config, 'swagger_spec_url', None)
                connector = connector_class(
                    base_url=instance_config.base_url,
                    jwt_token=resolved_api_key or '',
                    swagger_spec_url=swagger_spec_url
                )
                logger.debug(
                    f"Created DadosGovBrConnector (Swagger) for instance {instance_config.name} "
                    f"(base_url={instance_config.base_url})"
                )
            else:
                # Standard CKANConnector uses api_key parameter
                connector = connector_class(
                    base_url=instance_config.base_url,
                    api_key=resolved_api_key
                )
                logger.debug(
                    f"Created CKANConnector for instance {instance_config.name} "
                    f"(base_url={instance_config.base_url})"
                )
            return connector
        except Exception as e:
            raise ValueError(
                f"Failed to create connector for instance '{instance_id}': {str(e)}"
            ) from e

    @classmethod
    def create_marketplace_connector_from_instance(
        cls,
        instance_id: str,
        api_key: Any = _NOT_PROVIDED
    ) -> DataMarketplaceConnector:
        """
        Create a marketplace connector from a registered instance configuration.

        This is an alias for create_ckan_connector_from_instance() with a more
        accurate name that reflects support for both CKAN and Swagger connectors.

        Looks up the marketplace instance configuration by instance_id and creates the
        appropriate connector based on the instance's connector_type:
        - For connector_type="swagger": Creates DadosGovBrConnector (e.g., dados.gov.br)
        - For connector_type="ckan": Creates CKANConnector (e.g., demo.ckan.org, data.gov)

        Args:
            instance_id: Instance identifier (e.g., 'dados.gov.br' for Swagger API,
                        'demo.ckan.org' for CKAN API). Case-insensitive, whitespace is stripped.
            api_key: Optional API key/JWT token override. If provided (including None),
                    takes precedence over environment variable. If not provided
                    and instance has api_key_env_var, resolves from environment.
                    If not provided and instance has no api_key_env_var,
                    connector is created without API key.

        Returns:
            DataMarketplaceConnector instance:
            - DadosGovBrConnector for Swagger API instances (e.g., dados.gov.br)
            - CKANConnector for CKAN API instances (e.g., demo.ckan.org, data.gov)
            Configured with instance's base_url and API key/JWT token

        Raises:
            ValueError: If instance_id is invalid or instance not found in registry
            ValueError: If connector is not registered in factory

        Example:
            # Create connector for dados.gov.br (Swagger API) using environment API key
            connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance(
                instance_id='dados.gov.br'
            )

            # Create connector for demo.ckan.org (CKAN API)
            connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance(
                instance_id='demo.ckan.org'
            )
        """
        return cls.create_ckan_connector_from_instance(instance_id, api_key)


