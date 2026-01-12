"""
Snowflake Data Marketplace Connector

Connector implementation for Snowflake Data Marketplace.
Supports harvest (pull) operations for discovering and retrieving data from
Snowflake Data Marketplace listings.

Features:
- JWT token authentication (OAuth)
- Circuit breaker protection
- Connection pool management
- SQL execution with error handling
- Harvest-only operations (PULL only)

Snowflake Data Marketplace allows providers to share data products that can be
discovered and accessed through Snowflake's system views and shared databases.
"""
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import contextmanager

try:
    import snowflake.connector
    from snowflake.connector import DictCursor
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False
    snowflake = None
    DictCursor = None

from django.conf import settings

from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceListing,
    MarketplaceResource,
    SyncResult,
    MarketplaceAssetMapping,
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = logging.getLogger(__name__)


class SnowflakeConnector(DataMarketplaceConnector):
    """
    Connector for Snowflake Data Marketplace (Harvest-Only).

    Implements harvest (pull) operations for discovering and retrieving data from
    Snowflake Data Marketplace. This connector is read-only and does not support
    push operations (create, update, publish) as Snowflake Data Marketplace listings
    are managed through Snowflake's native interface.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from Snowflake to Hub)
    - Mapping: map_to_hub_asset (Snowflake shares → Hub assets)

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify Snowflake Data Marketplace listings

    Authentication:
    - Uses JWT Programmatic Access Token (OAuth)
    - Requires: account, user, token (JWT)
    - Optional: warehouse, role, database

    Snowflake Documentation: https://docs.snowflake.com/
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        token: Optional[str] = None,
        warehouse: Optional[str] = None,
        role: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize Snowflake connector.

        Args:
            account: Snowflake account identifier in orgname-accountname format
                     (e.g., 'WCGKMGD-XC16102') or account locator format
                     (e.g., 'xy12345.us-east-1'). See:
                     https://docs.snowflake.com/user-guide/gen-conn-config
            user: Snowflake username
            token: JWT Programmatic Access Token for OAuth authentication
            warehouse: Optional warehouse name to use
            role: Optional role to use
            database: Optional default database to use
        """
        if not SNOWFLAKE_AVAILABLE:
            raise ImportError(
                "snowflake-connector-python is not installed. "
                "Install it with: pip install snowflake-connector-python"
            )

        # Store connection parameters
        # Strip whitespace from token to avoid issues
        self.account = account
        self.user = user
        self.token = token.strip() if token else None
        self.warehouse = warehouse
        self.role = role
        self.database = database

        # Connection pool management
        self._connection = None
        self._connection_lock = threading.Lock()

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="snowflake-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client(),
        )

        # Track authentication state
        self._authenticated = False

    def _get_connection(self):
        """
        Get or create Snowflake connection.

        Creates a new connection if one doesn't exist or if the existing
        connection is closed. Reuses existing connection if available.

        Returns:
            Snowflake connection object

        Raises:
            ConnectionError: If unable to create connection
            ValueError: If required connection parameters are missing
        """
        if not self.account or not self.user or not self.token:
            raise ValueError(
                "account, user, and token are required for Snowflake connection"
            )

        # Check if connection exists and is valid
        if self._connection is not None:
            try:
                # Test connection by executing a simple query
                cursor = self._connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return self._connection
            except Exception:
                # Connection is invalid, close it
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None

        # Create new connection
        try:
            # Ensure token is clean (no leading/trailing whitespace)
            clean_token = self.token.strip() if self.token else None

            connection_params = {
                "account": self.account,
                "user": self.user,
                "authenticator": "oauth",
                "token": clean_token,
            }

            if self.warehouse:
                connection_params["warehouse"] = self.warehouse
            if self.role:
                connection_params["role"] = self.role
            if self.database:
                connection_params["database"] = self.database

            # Log connection attempt (without token for security)
            logger.debug(
                f"Attempting Snowflake connection: account={self.account}, user={self.user}, "
                f"role={self.role}, warehouse={self.warehouse}, token_length={len(clean_token) if clean_token else 0}"
            )

            self._connection = snowflake.connector.connect(**connection_params)
            logger.info(
                f"Successfully connected to Snowflake account: {self.account}, user: {self.user}"
            )
            return self._connection
        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Failed to create Snowflake connection: {error_msg}",
                extra={
                    "account": self.account,
                    "user": self.user,
                    "role": self.role,
                    "error_type": type(e).__name__,
                }
            )
            raise ConnectionError(f"Unable to connect to Snowflake: {e}") from e

    def _execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dictionaries.

        Args:
            sql: SQL query to execute
            params: Optional dictionary of parameters for parameterized queries

        Returns:
            List of dictionaries representing query results

        Raises:
            ConnectionError: If unable to connect to Snowflake
            ValueError: If SQL query is invalid
            PermissionError: If user lacks permission to execute query
        """
        def execute_query() -> List[Dict[str, Any]]:
            """Execute SQL query with error handling."""
            connection = self._get_connection()
            try:
                cursor = connection.cursor(DictCursor)
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                results = cursor.fetchall()
                cursor.close()
                return results
            except snowflake.connector.errors.ProgrammingError as e:
                error_msg = str(e)
                if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                    raise NotFoundError(f"Resource not found: {error_msg}") from e
                elif "insufficient privileges" in error_msg.lower() or "access denied" in error_msg.lower():
                    raise PermissionError(f"Permission denied: {error_msg}") from e
                else:
                    raise ValueError(f"SQL execution error: {error_msg}") from e
            except snowflake.connector.errors.DatabaseError as e:
                raise ConnectionError(f"Database error: {e}") from e
            except Exception as e:
                raise ConnectionError(f"Unexpected error executing SQL: {e}") from e

        # Execute with circuit breaker protection
        try:
            return self._circuit_breaker.call(execute_query)
        except Exception as e:
            logger.error(f"Snowflake SQL execution failed: {e}")
            raise

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        Snowflake connector is harvest-only (PULL only) as Snowflake Data Marketplace
        listings are managed through Snowflake's native interface.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Snowflake using provided credentials.

        Args:
            credentials: Dictionary containing:
                - account: Snowflake account identifier (required)
                - user: Snowflake username (required)
                - token or jwt_token: JWT Programmatic Access Token (required)
                - warehouse: Optional warehouse name
                - role: Optional role name
                - database: Optional database name

        Returns:
            True if authentication successful, False otherwise

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to Snowflake
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        # Extract credentials
        account = credentials.get("account")
        user = credentials.get("user")
        token = credentials.get("token") or credentials.get("jwt_token")

        if not account:
            raise ValueError("account is required in credentials")
        if not user:
            raise ValueError("user is required in credentials")
        if not token:
            raise ValueError("token or jwt_token is required in credentials")

        # Update connection parameters
        self.account = account
        self.user = user
        self.token = token
        self.warehouse = credentials.get("warehouse")
        self.role = credentials.get("role")
        self.database = credentials.get("database")

        # Test connection
        try:
            result = self.test_connection()
            if result:
                self._authenticated = True
                logger.info(f"Successfully authenticated with Snowflake account: {account}, user: {user}")
                return True
            else:
                self._authenticated = False
                return False
        except Exception as e:
            self._authenticated = False
            logger.error(f"Authentication test failed for Snowflake: {e}")
            raise ConnectionError(f"Unable to authenticate with Snowflake: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to Snowflake.

        Performs a lightweight operation (SELECT CURRENT_VERSION()) to verify
        that the connector can successfully communicate with Snowflake.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            results = self._execute_sql("SELECT CURRENT_VERSION()")
            if results and len(results) > 0:
                version = results[0].get("CURRENT_VERSION()", "")
                logger.info(f"Connection test successful. Snowflake version: {version}")
                return True
            else:
                logger.warning("Connection test failed: No version returned")
                return False
        except Exception as e:
            logger.error(f"Connection test failed for Snowflake: {e}")
            raise ConnectionError(f"Unable to connect to Snowflake: {e}") from e

    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[MarketplaceListing]:
        """
        List available listings from Snowflake Data Marketplace.

        Executes SHOW AVAILABLE LISTINGS SQL command to discover marketplace listings,
        then retrieves full metadata for each listing including ODPS and ODCS metadata.

        Args:
            filters: Optional dictionary of filters:
                - category: Filter by category
                - provider: Filter by provider name
                - tags: Filter by tags (list of strings)
            limit: Optional maximum number of listings to return
            offset: Optional offset for pagination

        Returns:
            List of MarketplaceListing objects with complete metadata

        Raises:
            ConnectionError: If unable to connect to Snowflake
            ValueError: If filters or pagination parameters are invalid
        """
        # Validate pagination parameters before any SQL execution
        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError("offset must be a non-negative integer")
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be a non-negative integer")

        try:
            # Try SHOW AVAILABLE LISTINGS first (Snowflake Data Marketplace command)
            # If that fails, fall back to querying shared databases
            try:
                # Execute SHOW AVAILABLE LISTINGS
                results = self._execute_sql("SHOW AVAILABLE LISTINGS")
            except Exception as e:
                logger.debug(f"SHOW AVAILABLE LISTINGS not available, falling back to shared databases: {e}")
                # Fallback: Query shared databases from SNOWFLAKE.ACCOUNT_USAGE
                sql = """
                    SELECT
                        DATABASE_NAME,
                        DATABASE_OWNER,
                        CREATED,
                        COMMENT
                    FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
                    WHERE IS_TRANSIENT = 'N'
                    AND DELETED IS NULL
                    AND DATABASE_NAME NOT LIKE 'SNOWFLAKE%'
                """
                results = self._execute_sql(sql)

            # Apply filters
            if filters:
                filtered_results = []
                for row in results:
                    # Extract listing name/identifier
                    listing_name = row.get("listing_name") or row.get("name") or row.get("DATABASE_NAME", "")
                    provider = row.get("provider") or row.get("DATABASE_OWNER", "")
                    category = row.get("category") or ""
                    tags = row.get("tags") or []

                    # Apply category filter
                    if filters.get("category") and category:
                        if filters["category"].lower() not in category.lower():
                            continue

                    # Apply provider filter
                    if filters.get("provider") and provider:
                        if filters["provider"].lower() not in provider.lower():
                            continue

                    # Apply tags filter
                    if filters.get("tags") and tags:
                        filter_tags = [t.lower() for t in filters["tags"]]
                        listing_tags = [str(t).lower() for t in tags] if isinstance(tags, list) else []
                        if not any(tag in listing_tags for tag in filter_tags):
                            continue

                    filtered_results.append(row)
                results = filtered_results

            # Apply pagination
            # Validate pagination parameters
            if offset is not None:
                if not isinstance(offset, int) or offset < 0:
                    raise ValueError("offset must be a non-negative integer")
                if offset > 0:
                    results = results[offset:]
            if limit is not None:
                if not isinstance(limit, int) or limit < 0:
                    raise ValueError("limit must be a non-negative integer")
                if limit > 0:
                    results = results[:limit]

            # Get full details for each listing and build MarketplaceListing objects
            listings = []
            for row in results:
                try:
                    # Extract listing identifier
                    listing_id = (
                        row.get("listing_name")
                        or row.get("name")
                        or row.get("DATABASE_NAME")
                        or row.get("identifier")
                        or ""
                    )

                    if not listing_id:
                        logger.warning(f"Skipping row without listing identifier: {row}")
                        continue

                    # Get full listing details
                    listing_details = self._get_listing_details(listing_id)

                    # Build MarketplaceListing with ODPS and ODCS metadata
                    listing = self._build_marketplace_listing(listing_id, listing_details, row)
                    listings.append(listing)
                except NotFoundError:
                    # Listing not found, skip it
                    logger.warning(f"Listing '{listing_id}' not found, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Failed to process listing: {e}")
                    continue

            return listings
        except Exception as e:
            logger.error(f"Failed to list Snowflake listings: {e}")
            raise ConnectionError(f"Unable to list Snowflake listings: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific listing by its marketplace ID.

        Executes DESCRIBE AVAILABLE LISTING SQL command to get detailed listing information
        including ODPS and ODCS metadata.

        Args:
            listing_id: Listing identifier (listing name or database name)

        Returns:
            MarketplaceListing object with complete metadata

        Raises:
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Get detailed listing information
            listing_details = self._get_listing_details(listing_id)

            # Build MarketplaceListing with ODPS and ODCS metadata
            return self._build_marketplace_listing(listing_id, listing_details)
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get Snowflake listing {listing_id}: {e}")
            raise ConnectionError(f"Unable to get Snowflake listing: {e}") from e

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources (databases/schemas/tables) associated with a marketplace listing.

        For Snowflake marketplace, resources are databases/schemas/tables created from listings.
        Queries INFORMATION_SCHEMA to discover all resources.

        Args:
            listing_id: Database name (Snowflake marketplace listing identifier)

        Returns:
            List of MarketplaceResource objects (DATABASE, SCHEMA, TABLE types)

        Raises:
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Validate listing_id to prevent SQL injection
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            # Sanitize listing_id (remove any SQL injection attempts)
            import re
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', listing_id):
                raise ValueError(f"Invalid listing_id format: {listing_id}")

            resources = []

            # First, verify the database exists
            try:
                verify_sql = """
                    SELECT DATABASE_NAME
                    FROM INFORMATION_SCHEMA.DATABASES
                    WHERE DATABASE_NAME = %(database_name)s
                """
                verify_results = self._execute_sql(verify_sql, {"database_name": listing_id})
                if not verify_results or len(verify_results) == 0:
                    raise NotFoundError(f"Listing '{listing_id}' not found in Snowflake Data Marketplace")
            except NotFoundError:
                raise
            except ValueError:
                raise
            except Exception as e:
                # If INFORMATION_SCHEMA.DATABASES doesn't work, try alternative approach
                logger.debug(f"Could not verify database via INFORMATION_SCHEMA.DATABASES: {e}")

            # Query INFORMATION_SCHEMA.SCHEMATA for schemas in the database
            try:
                schemas_sql = """
                    SELECT
                        SCHEMA_NAME,
                        SCHEMA_OWNER,
                        CREATED,
                        LAST_ALTERED,
                        COMMENT
                    FROM INFORMATION_SCHEMA.SCHEMATA
                    WHERE CATALOG_NAME = %(database_name)s
                    ORDER BY SCHEMA_NAME
                """
                schema_results = self._execute_sql(schemas_sql, {"database_name": listing_id})

                for row in schema_results:
                    try:
                        schema_name = row.get("SCHEMA_NAME", "")
                        resource_id = f"{listing_id}.{schema_name}"
                        resource = MarketplaceResource(
                            resource_id=resource_id,
                            resource_type="SCHEMA",
                            name=schema_name,
                            description=row.get("COMMENT") or f"Schema {schema_name} in database {listing_id}",
                            url=None,
                            format="SNOWFLAKE",
                            size_bytes=None,
                            metadata={
                                "snowflake_schema": row,
                                "database_name": listing_id,
                                "schema_owner": row.get("SCHEMA_OWNER"),
                            },
                        )
                        resources.append(resource)
                    except Exception as e:
                        logger.warning(f"Failed to convert schema to resource: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Could not query schemas: {e}")

            # Query INFORMATION_SCHEMA.TABLES for tables and views in the database
            try:
                tables_sql = """
                    SELECT
                        TABLE_SCHEMA,
                        TABLE_NAME,
                        TABLE_TYPE,
                        CREATED,
                        LAST_ALTERED,
                        COMMENT,
                        ROW_COUNT,
                        BYTES
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_CATALOG = %(database_name)s
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                table_results = self._execute_sql(tables_sql, {"database_name": listing_id})

                for row in table_results:
                    try:
                        resource = self._snowflake_table_to_resource(listing_id, row)
                        resources.append(resource)
                    except Exception as e:
                        logger.warning(f"Failed to convert table to resource: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Could not query tables: {e}")

            # If no resources found, create a database-level resource
            if not resources:
                try:
                    db_resource = MarketplaceResource(
                        resource_id=listing_id,
                        resource_type="DATABASE",
                        name=listing_id,
                        description=f"Database {listing_id} from Snowflake Data Marketplace",
                        url=None,
                        format="SNOWFLAKE",
                        size_bytes=None,
                        metadata={
                            "database_name": listing_id,
                            "resource_type": "DATABASE",
                        },
                    )
                    resources.append(db_resource)
                except Exception as e:
                    logger.warning(f"Failed to create database resource: {e}")

            return resources
        except NotFoundError:
            raise
        except ValueError:
            # Re-raise ValueError (input validation errors)
            raise
        except Exception as e:
            logger.error(f"Failed to list resources for listing {listing_id}: {e}")
            raise ConnectionError(f"Unable to list resources: {e}") from e

    def _get_listing_details(self, listing_id: str) -> Dict[str, Any]:
        """
        Get detailed listing information using DESCRIBE AVAILABLE LISTING.

        Args:
            listing_id: Listing identifier

        Returns:
            Dictionary with listing details

        Raises:
            NotFoundError: If listing not found
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Validate listing_id to prevent SQL injection
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            # Sanitize listing_id (remove any SQL injection attempts)
            # Snowflake identifiers are alphanumeric with underscores, hyphens, and dots
            import re
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', listing_id):
                raise ValueError(f"Invalid listing_id format: {listing_id}")

            # Try DESCRIBE AVAILABLE LISTING first (Snowflake Data Marketplace command)
            # Note: DESCRIBE commands don't support parameterized queries, so we sanitize the input
            try:
                # Escape single quotes in listing_id to prevent SQL injection
                sanitized_listing_id = listing_id.replace("'", "''")
                sql = f"DESCRIBE AVAILABLE LISTING '{sanitized_listing_id}'"
                results = self._execute_sql(sql)
                if results and len(results) > 0:
                    return results[0]
            except Exception as e:
                logger.debug(f"DESCRIBE AVAILABLE LISTING not available, falling back to database query: {e}")

            # Fallback: Query database information using parameterized query
            sql = """
                SELECT
                    DATABASE_NAME,
                    DATABASE_OWNER,
                    CREATED,
                    COMMENT,
                    RETENTION_TIME,
                    IS_TRANSIENT
                FROM SNOWFLAKE.ACCOUNT_USAGE.DATABASES
                WHERE DATABASE_NAME = %(database_name)s
                AND IS_TRANSIENT = 'N'
                AND DELETED IS NULL
            """
            results = self._execute_sql(sql, {"database_name": listing_id})

            if not results or len(results) == 0:
                raise NotFoundError(f"Listing '{listing_id}' not found in Snowflake Data Marketplace")

            return results[0]
        except NotFoundError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get listing details for {listing_id}: {e}")
            raise ConnectionError(f"Unable to get listing details: {e}") from e

    def _extract_odps_metadata(self, listing_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ODPS contract metadata from listing data.

        Args:
            listing_details: Dictionary containing listing details

        Returns:
            Structured ODPS metadata dictionary
        """
        odps_metadata = {}

        # Extract product details
        product_id = (
            listing_details.get("product_id")
            or listing_details.get("productID")
            or listing_details.get("DATABASE_NAME")
            or ""
        )
        product_name = (
            listing_details.get("product_name")
            or listing_details.get("title")
            or listing_details.get("name")
            or listing_details.get("DATABASE_NAME")
            or ""
        )
        product_description = (
            listing_details.get("product_description")
            or listing_details.get("description")
            or listing_details.get("COMMENT")
            or ""
        )
        product_version = listing_details.get("version") or listing_details.get("product_version")

        if product_id or product_name:
            odps_metadata["product_details"] = {
                "productID": product_id,
                "product_name": product_name,
                "product_description": product_description,
            }
            if product_version:
                odps_metadata["product_details"]["product_version"] = product_version

        # Extract pricing plans (if available in listing metadata)
        pricing_plans = listing_details.get("pricing_plans") or listing_details.get("pricing")
        if pricing_plans:
            odps_metadata["pricing_plans"] = pricing_plans if isinstance(pricing_plans, list) else [pricing_plans]

        # Extract access methods (Snowflake share access)
        access_methods = {
            "snowflake_share": {
                "type": "SNOWFLAKE_SHARE",
                "database": listing_details.get("DATABASE_NAME") or listing_details.get("database_name"),
                "description": "Access via Snowflake Data Share",
            }
        }
        odps_metadata["access_methods"] = access_methods

        # Extract payment gateways (if available)
        payment_gateways = listing_details.get("payment_gateways") or listing_details.get("payment")
        if payment_gateways:
            odps_metadata["payment_gateways"] = (
                payment_gateways if isinstance(payment_gateways, dict) else {"default": payment_gateways}
            )

        # Extract license information
        license_id = listing_details.get("license_id") or listing_details.get("license")
        if license_id:
            odps_metadata["license"] = license_id

        # Extract author/maintainer information
        author = listing_details.get("author") or listing_details.get("DATABASE_OWNER")
        maintainer = listing_details.get("maintainer") or listing_details.get("provider")
        if author or maintainer:
            odps_metadata["contact"] = {}
            if author:
                odps_metadata["contact"]["name"] = author
            if maintainer:
                odps_metadata["contact"]["maintainer"] = maintainer

        return odps_metadata

    def _extract_odcs_metadata(self, listing_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract ODCS contract metadata hints from listing.

        Args:
            listing_details: Dictionary containing listing details

        Returns:
            Structured ODCS metadata dictionary (will be enhanced after listing consumption)
        """
        odcs_metadata = {}

        # Extract schema hints (if available in listing metadata)
        schema_info = listing_details.get("schema") or listing_details.get("schema_hints")
        if schema_info:
            odcs_metadata["schema"] = schema_info if isinstance(schema_info, dict) else {"hints": schema_info}

        # Extract quality hints (if available)
        quality_info = listing_details.get("quality") or listing_details.get("quality_hints")
        if quality_info:
            odcs_metadata["quality"] = quality_info if isinstance(quality_info, dict) else {"hints": quality_info}

        # Extract SLA hints (if available)
        sla_info = listing_details.get("sla") or listing_details.get("sla_hints")
        if sla_info:
            odcs_metadata["sla"] = sla_info if isinstance(sla_info, dict) else {"hints": sla_info}

        # Extract lifecycle information
        lifecycle = {}
        created = listing_details.get("CREATED") or listing_details.get("created")
        if created:
            try:
                if isinstance(created, datetime):
                    lifecycle["created"] = created.isoformat()
                elif isinstance(created, str):
                    lifecycle["created"] = created
            except Exception:
                pass

        last_updated = listing_details.get("last_updated") or listing_details.get("updated")
        if last_updated:
            try:
                if isinstance(last_updated, datetime):
                    lifecycle["lastUpdated"] = last_updated.isoformat()
                elif isinstance(last_updated, str):
                    lifecycle["lastUpdated"] = last_updated
            except Exception:
                pass

        if lifecycle:
            odcs_metadata["lifecycle"] = lifecycle

        return odcs_metadata

    def _build_marketplace_listing(
        self, listing_id: str, listing_details: Dict[str, Any], summary_row: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        """
        Build MarketplaceListing object from listing details with ODPS and ODCS metadata.

        Args:
            listing_id: Listing identifier
            listing_details: Detailed listing information from _get_listing_details()
            summary_row: Optional summary row from list_listings() for additional context

        Returns:
            MarketplaceListing object with complete metadata
        """
        # Merge summary_row into listing_details if provided
        if summary_row:
            listing_details = {**listing_details, **summary_row}

        # Extract basic information
        title = (
            listing_details.get("title")
            or listing_details.get("name")
            or listing_details.get("product_name")
            or listing_details.get("DATABASE_NAME")
            or listing_id
        )
        description = (
            listing_details.get("description")
            or listing_details.get("product_description")
            or listing_details.get("COMMENT")
            or f"Snowflake Data Marketplace listing: {listing_id}"
        )
        category = (
            listing_details.get("category")
            or listing_details.get("provider")
            or listing_details.get("DATABASE_OWNER")
            or ""
        )
        provider = listing_details.get("provider") or listing_details.get("DATABASE_OWNER") or ""

        # Extract tags
        tags = listing_details.get("tags") or []
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif not isinstance(tags, list):
            tags = []

        # Extract timestamps
        created_at = None
        updated_at = None
        created = listing_details.get("CREATED") or listing_details.get("created") or listing_details.get("created_on")
        if created:
            try:
                if isinstance(created, datetime):
                    created_at = created
                elif isinstance(created, str):
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                pass

        updated = listing_details.get("updated") or listing_details.get("last_updated") or listing_details.get("updated_on")
        if updated:
            try:
                if isinstance(updated, datetime):
                    updated_at = updated
                elif isinstance(updated, str):
                    updated_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except Exception:
                pass

        # Extract ODPS metadata
        odps_metadata = self._extract_odps_metadata(listing_details)

        # Extract ODCS metadata
        odcs_metadata = self._extract_odcs_metadata(listing_details)

        # Build pricing plans from ODPS metadata
        pricing_plans = odps_metadata.get("pricing_plans", [])

        # Build access methods from ODPS metadata
        access_methods = odps_metadata.get("access_methods", {})

        # Build payment gateways from ODPS metadata
        payment_gateways = odps_metadata.get("payment_gateways", {})

        # Build comprehensive metadata
        metadata = {
            "snowflake_listing": listing_details,
            "provider": provider,
            "odps_metadata": odps_metadata,
            "odcs_metadata": odcs_metadata,
        }

        # Build URL (if available)
        url = None
        if listing_details.get("url"):
            url = listing_details["url"]
        elif listing_details.get("DATABASE_NAME"):
            # Construct Snowflake URL if possible
            url = f"https://app.snowflake.com/marketplace/listing/{listing_id}"

        return MarketplaceListing(
            marketplace_id=listing_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title=title,
            description=description,
            product_id=odps_metadata.get("product_details", {}).get("productID"),
            category=category,
            tags=tags,
            pricing_plans=pricing_plans,
            access_methods=access_methods,
            payment_gateways=payment_gateways,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            url=url,
        )

    def _snowflake_database_to_listing(self, database_row: Dict[str, Any]) -> MarketplaceListing:
        """
        Map Snowflake database row to MarketplaceListing.

        Args:
            database_row: Dictionary containing database information

        Returns:
            MarketplaceListing object
        """
        database_name = database_row.get("DATABASE_NAME", "")
        comment = database_row.get("COMMENT", "")
        created = database_row.get("CREATED")
        owner = database_row.get("DATABASE_OWNER", "")

        # Parse created timestamp
        created_at = None
        if created:
            try:
                if isinstance(created, datetime):
                    created_at = created
                elif isinstance(created, str):
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                pass

        # Extract metadata
        metadata = {
            "snowflake_database": database_row,
            "database_owner": owner,
            "comment": comment,
        }

        return MarketplaceListing(
            marketplace_id=database_name,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title=database_name,
            description=comment or f"Snowflake Data Marketplace listing: {database_name}",
            category=owner,  # Use owner as category/provider
            tags=[],
            metadata=metadata,
            created_at=created_at,
            updated_at=created_at,  # Use created as updated if no separate updated field
        )

    def _snowflake_table_to_resource(
        self, database_name: str, table_row: Dict[str, Any]
    ) -> MarketplaceResource:
        """
        Map Snowflake table/view row to MarketplaceResource.

        Args:
            database_name: Database name
            table_row: Dictionary containing table/view information

        Returns:
            MarketplaceResource object
        """
        schema_name = table_row.get("TABLE_SCHEMA", "")
        table_name = table_row.get("TABLE_NAME", "")
        table_type = table_row.get("TABLE_TYPE", "BASE TABLE")
        comment = table_row.get("COMMENT", "")
        row_count = table_row.get("ROW_COUNT", 0)
        bytes_size = table_row.get("BYTES", 0)
        created = table_row.get("CREATED")
        last_altered = table_row.get("LAST_ALTERED")

        # Build resource ID
        resource_id = f"{database_name}.{schema_name}.{table_name}"

        # Parse timestamps
        created_at = None
        updated_at = None
        if created:
            try:
                if isinstance(created, datetime):
                    created_at = created
                elif isinstance(created, str):
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                pass
        if last_altered:
            try:
                if isinstance(last_altered, datetime):
                    updated_at = last_altered
                elif isinstance(last_altered, str):
                    updated_at = datetime.fromisoformat(last_altered.replace("Z", "+00:00"))
            except Exception:
                pass

        # Determine resource type
        resource_type = "TABLE" if table_type == "BASE TABLE" else "VIEW"

        # Build metadata
        metadata = {
            "snowflake_table": table_row,
            "database_name": database_name,
            "schema_name": schema_name,
            "table_type": table_type,
            "row_count": row_count,
            "bytes": bytes_size,
        }

        return MarketplaceResource(
            resource_id=resource_id,
            resource_type=resource_type,
            name=table_name,
            description=comment or f"{table_type} in {database_name}.{schema_name}",
            url=None,  # Snowflake resources don't have direct URLs
            format="SNOWFLAKE",
            size_bytes=bytes_size,
            metadata=metadata,
        )

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        """
        Create a new listing in Snowflake Data Marketplace.

        **DEPRECATED**: Snowflake connector is harvest-only (PULL only).
        Snowflake Data Marketplace listings are managed through Snowflake's
        native interface. This method raises NotImplementedError.

        Args:
            listing: MarketplaceListing object with listing details

        Returns:
            Created MarketplaceListing object

        Raises:
            NotImplementedError: Snowflake connector does not support push operations
        """
        raise NotImplementedError(
            "Snowflake connector is harvest-only (PULL only). "
            "Snowflake Data Marketplace listings are managed through Snowflake's native interface. "
            "Use sync_pull() to harvest data from Snowflake Data Marketplace."
        )

    def update_listing(
        self, listing_id: str, listing: MarketplaceListing
    ) -> MarketplaceListing:
        """
        Update an existing listing in Snowflake Data Marketplace.

        **DEPRECATED**: Snowflake connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing_id: Unique identifier for the listing to update
            listing: MarketplaceListing object with updated details

        Returns:
            Updated MarketplaceListing object

        Raises:
            NotImplementedError: Snowflake connector does not support push operations
        """
        raise NotImplementedError(
            "Snowflake connector is harvest-only (PULL only). "
            "Snowflake Data Marketplace listings are managed through Snowflake's native interface."
        )

    def publish_resource(
        self, listing_id: str, resource: MarketplaceResource
    ) -> MarketplaceResource:
        """
        Publish a resource to a marketplace listing.

        **DEPRECATED**: Snowflake connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            listing_id: Database name
            resource: MarketplaceResource object with resource details

        Returns:
            Published MarketplaceResource object

        Raises:
            NotImplementedError: Snowflake connector does not support push operations
        """
        raise NotImplementedError(
            "Snowflake connector is harvest-only (PULL only). "
            "Snowflake Data Marketplace listings are managed through Snowflake's native interface."
        )

    def download_resource(self, resource_id: str, destination_path: str) -> str:
        """
        Download a resource from Snowflake Data Marketplace on-demand.

        **On-Demand Download Behavior**:
        This method handles on-demand resource downloads when `data_strategy != "METADATA_ONLY"`.
        It performs all marketplace-specific operations that were deferred from `sync_pull()`:
        1. Requests listing and waits for fulfillment (if not already requested)
        2. Accepts legal terms if required
        3. Creates database from listing (if not already created)
        4. Extracts schema metadata from created database
        5. Downloads data from the specified table/view

        **When This Method Is Called**:
        - Called by workflow when `data_strategy == "DOWNLOAD_SELECTIVE"` (specific resources)
        - Called by workflow when `data_strategy == "DOWNLOAD_ALL"` (all resources)
        - NOT called when `data_strategy == "METADATA_ONLY"` (default, metadata-only harvesting)

        Args:
            resource_id: Resource identifier. Can be either:
                - Listing ID (e.g., "SNOWFLAKE_SAMPLE_DATA"): Will request listing, create database, and download all tables
                - Database resource identifier (e.g., "DB_SAMPLE_DATA"): Will extract schema and download all tables
                - Table resource identifier (e.g., "DB_SAMPLE_DATA.SCHEMA.TABLE"): Will download specific table
            destination_path: Local filesystem path where resource should be saved.
                The directory will be created if it doesn't exist.

        Returns:
            Path to the downloaded file (may be same as destination_path or a modified path)

        Raises:
            NotFoundError: If resource not found in Snowflake
            ConnectionError: If unable to connect to Snowflake
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource or perform marketplace-specific operations
            ValueError: If resource_id format is invalid

        **Example**:
        ```python
        # Download from listing ID (will request, accept terms, create DB, extract schema, download)
        connector.download_resource("SNOWFLAKE_SAMPLE_DATA", "/tmp/sample_data.csv")

        # Download from specific table (assumes DB already exists)
        connector.download_resource("DB_SAMPLE_DATA.SCHEMA.TABLE", "/tmp/table.csv")
        ```
        """
        import os
        import csv
        import re

        try:
            # Ensure destination directory exists
            os.makedirs(
                os.path.dirname(destination_path) if os.path.dirname(destination_path) else ".",
                exist_ok=True,
            )

            # Determine file format from extension
            file_ext = os.path.splitext(destination_path)[1].lower()
            if file_ext == ".parquet":
                file_format = "PARQUET"
            elif file_ext == ".json":
                file_format = "JSON"
            else:
                file_format = "CSV"

            # Parse resource_id to determine type
            parts = resource_id.split(".")
            listing_id = None
            database_name = None
            schema_name = None
            table_name = None

            if len(parts) == 1:
                # Case 1: Listing ID (e.g., "SNOWFLAKE_SAMPLE_DATA")
                # Need to request listing, accept terms, create database, extract schema, download
                listing_id = resource_id
                logger.info(f"Downloading resource from listing ID: {listing_id}")

                # Step 1: Request listing and wait for fulfillment
                try:
                    self._request_listing(listing_id)
                except NotFoundError:
                    raise NotFoundError(f"Listing '{listing_id}' not available for request")
                except PermissionError as e:
                    raise PermissionError(f"Permission denied to request listing '{listing_id}': {e}")

                # Step 2: Accept legal terms if required
                try:
                    self._accept_legal_terms(listing_id)
                except Exception as e:
                    # Legal terms acceptance failure is not fatal
                    logger.debug(f"Legal terms acceptance failed for '{listing_id}': {e}")

                # Step 3: Create database from listing
                try:
                    database_name = self._create_database_from_listing(listing_id)
                    logger.info(f"Created database '{database_name}' from listing '{listing_id}'")
                except NotFoundError:
                    raise NotFoundError(f"Listing '{listing_id}' not available for database creation")
                except PermissionError as e:
                    raise PermissionError(f"Permission denied to create database from listing '{listing_id}': {e}")

                # Step 4: Extract schema metadata (for reference, but we'll download all tables)
                schema_metadata = None
                try:
                    schema_metadata = self._extract_schema_metadata(database_name)
                    logger.info(f"Extracted schema metadata from database '{database_name}'")
                except Exception as e:
                    logger.warning(f"Failed to extract schema metadata for database '{database_name}': {e}")
                    # Continue without schema metadata - we can still download data

                # Step 5: Download all tables from the database
                # Get list of tables from INFORMATION_SCHEMA
                tables_sql = f"""
                    SELECT TABLE_SCHEMA, TABLE_NAME
                    FROM {database_name}.INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_TYPE = 'BASE TABLE' OR TABLE_TYPE = 'VIEW'
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                tables_results = self._execute_sql(tables_sql)

                if not tables_results:
                    raise NotFoundError(f"No tables found in database '{database_name}'")

                # Download each table
                downloaded_files = []
                for table_row in tables_results:
                    schema = table_row.get("TABLE_SCHEMA", "")
                    table = table_row.get("TABLE_NAME", "")
                    full_table_name = f"{database_name}.{schema}.{table}"

                    # Generate filename for this table
                    table_filename = f"{table}.{file_ext.lstrip('.')}" if file_ext else f"{table}.csv"
                    table_path = os.path.join(
                        os.path.dirname(destination_path) if os.path.dirname(destination_path) else ".",
                        table_filename
                    )

                    # Download this table
                    downloaded_file = self._download_table(full_table_name, table_path, file_format)
                    downloaded_files.append(downloaded_file)

                # Return the first downloaded file path (or destination_path if single table)
                if len(downloaded_files) == 1:
                    return downloaded_files[0]
                else:
                    # Multiple tables downloaded - return directory path
                    return os.path.dirname(destination_path) if os.path.dirname(destination_path) else "."

            elif len(parts) == 2:
                # Case 2: Database name (e.g., "DB_SAMPLE_DATA")
                # Database already exists, extract schema, download all tables
                database_name = parts[0]
                raise ValueError(
                    f"Database-only resource_id not yet supported. "
                    f"Please specify table as 'database.schema.table' or use listing ID."
                )

            elif len(parts) == 3:
                # Case 3: Table identifier (e.g., "DB_SAMPLE_DATA.SCHEMA.TABLE")
                # Table already exists, download it
                database_name, schema_name, table_name = parts

                # Validate identifiers to prevent SQL injection
                for identifier in [database_name, schema_name, table_name]:
                    if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
                        raise ValueError(f"Invalid identifier format: {identifier}")

                # Download the specific table
                return self._download_table(resource_id, destination_path, file_format)

            else:
                raise ValueError(
                    f"Invalid resource_id format. Expected listing ID, 'database', or 'database.schema.table', got: {resource_id}"
                )

        except NotFoundError:
            raise
        except PermissionError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to download resource '{resource_id}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to download resource: {e}") from e

    def _download_table(self, table_identifier: str, destination_path: str, file_format: str) -> str:
        """
        Download data from a specific Snowflake table/view.

        Args:
            table_identifier: Full table identifier (database.schema.table)
            destination_path: Local filesystem path where data should be saved
            file_format: File format ("CSV", "JSON", or "PARQUET")

        Returns:
            Path to the downloaded file

        Raises:
            NotFoundError: If table not found
            ConnectionError: If unable to connect to Snowflake
            IOError: If unable to write to destination path
        """
        import csv
        import re

        try:
            # Parse table identifier
            parts = table_identifier.split(".")
            if len(parts) != 3:
                raise ValueError(f"Invalid table identifier format: {table_identifier}")

            database_name, schema_name, table_name = parts

            # Validate identifiers to prevent SQL injection
            for identifier in [database_name, schema_name, table_name]:
                if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
                    raise ValueError(f"Invalid identifier format: {identifier}")

            # Verify table exists
            verify_sql = f"""
                SELECT TABLE_NAME
                FROM {database_name}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = %(schema_name)s
                AND TABLE_NAME = %(table_name)s
            """
            verify_results = self._execute_sql(
                verify_sql,
                {"schema_name": schema_name, "table_name": table_name}
            )

            if not verify_results:
                raise NotFoundError(f"Table '{table_identifier}' not found")

            # Fetch data from table/view
            sql = f"SELECT * FROM {database_name}.{schema_name}.{table_name}"
            results = self._execute_sql(sql)

            if not results:
                raise NotFoundError(f"No data found in table '{table_identifier}'")

            # Write data to file based on format
            if file_format == "CSV":
                with open(destination_path, "w", newline="", encoding="utf-8") as csvfile:
                    if results:
                        # Get column names from first row
                        fieldnames = list(results[0].keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(results)
            elif file_format == "JSON":
                import json
                with open(destination_path, "w", encoding="utf-8") as jsonfile:
                    json.dump(results, jsonfile, indent=2, default=str)
            else:
                # For Parquet, we'd need pyarrow - fall back to CSV for now
                logger.warning(f"Parquet format not fully supported, using CSV instead")
                csv_path = destination_path.replace(".parquet", ".csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
                    if results:
                        fieldnames = list(results[0].keys())
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(results)
                destination_path = csv_path

            logger.info(f"Successfully downloaded table '{table_identifier}' to '{destination_path}'")
            return destination_path

        except NotFoundError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to download table '{table_identifier}': {e}", exc_info=True)
            raise ConnectionError(f"Unable to download table: {e}") from e

    def _request_listing(self, listing_id: str) -> bool:
        """
        Request a listing and wait for fulfillment.

        Executes SYSTEM$REQUEST_LISTING_AND_WAIT stored procedure which is a blocking
        call that waits for the listing to be ready for consumption.

        Args:
            listing_id: Listing identifier

        Returns:
            True if listing request successful

        Raises:
            NotFoundError: If listing not available
            PermissionError: If user lacks permission to request listing
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Validate listing_id
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            import re
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', listing_id):
                raise ValueError(f"Invalid listing_id format: {listing_id}")

            # Escape single quotes to prevent SQL injection
            sanitized_listing_id = listing_id.replace("'", "''")

            # Execute SYSTEM$REQUEST_LISTING_AND_WAIT stored procedure
            sql = f"CALL SYSTEM$REQUEST_LISTING_AND_WAIT('{sanitized_listing_id}')"
            results = self._execute_sql(sql)

            if results:
                logger.info(f"Successfully requested listing '{listing_id}'")
                return True
            else:
                logger.warning(f"Request listing returned no results for '{listing_id}'")
                return False
        except NotFoundError:
            raise
        except PermissionError:
            raise
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                raise NotFoundError(f"Listing '{listing_id}' not available") from e
            elif "permission" in error_msg or "access denied" in error_msg or "insufficient privileges" in error_msg:
                raise PermissionError(f"Permission denied to request listing '{listing_id}'") from e
            else:
                logger.error(f"Failed to request listing '{listing_id}': {e}")
                raise ConnectionError(f"Unable to request listing: {e}") from e

    def _accept_legal_terms(self, listing_id: str) -> bool:
        """
        Accept legal terms for a listing if required.

        Executes SYSTEM$ACCEPT_LEGAL_TERMS stored procedure to accept legal terms
        for DATA_EXCHANGE_LISTING type listings.

        Args:
            listing_id: Listing identifier

        Returns:
            True if legal terms accepted, False if not required

        Raises:
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Validate listing_id
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            import re
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', listing_id):
                raise ValueError(f"Invalid listing_id format: {listing_id}")

            # Escape single quotes to prevent SQL injection
            sanitized_listing_id = listing_id.replace("'", "''")

            # Execute SYSTEM$ACCEPT_LEGAL_TERMS stored procedure
            sql = f"CALL SYSTEM$ACCEPT_LEGAL_TERMS('DATA_EXCHANGE_LISTING', '{sanitized_listing_id}')"
            results = self._execute_sql(sql)

            if results:
                logger.info(f"Successfully accepted legal terms for listing '{listing_id}'")
                return True
            else:
                logger.debug(f"Legal terms acceptance returned no results for '{listing_id}' (may not be required)")
                return False
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            # Legal terms may not be required - this is not a fatal error
            if "not found" in error_msg or "does not exist" in error_msg or "not required" in error_msg:
                logger.debug(f"Legal terms not required for listing '{listing_id}': {e}")
                return False
            else:
                logger.warning(f"Failed to accept legal terms for listing '{listing_id}': {e}")
                # Don't raise exception - legal terms acceptance failure is not fatal
                return False

    def _create_database_from_listing(self, listing_id: str) -> str:
        """
        Create a database from a marketplace listing.

        Generates a sanitized database name and creates the database from the listing.

        Args:
            listing_id: Listing identifier

        Returns:
            Database name that was created

        Raises:
            NotFoundError: If listing not available
            PermissionError: If user lacks permission to create database
            ConnectionError: If unable to connect to Snowflake
            ValueError: If database name generation fails
        """
        try:
            # Validate listing_id
            if not listing_id or not isinstance(listing_id, str):
                raise ValueError("listing_id must be a non-empty string")

            import re
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', listing_id):
                raise ValueError(f"Invalid listing_id format: {listing_id}")

            # Generate database name: DB_{listing_id.replace('-', '_').upper()}
            # Sanitize: remove dots, replace hyphens with underscores, uppercase
            db_name = listing_id.replace("-", "_").replace(".", "_").upper()
            if not db_name.startswith("DB_"):
                db_name = f"DB_{db_name}"

            # Ensure database name is valid (Snowflake identifiers: alphanumeric + underscore, max 255 chars)
            db_name = re.sub(r'[^A-Z0-9_]', '_', db_name)
            if len(db_name) > 255:
                db_name = db_name[:255]

            # Escape single quotes to prevent SQL injection
            sanitized_listing_id = listing_id.replace("'", "''")
            sanitized_db_name = db_name.replace("'", "''")

            # Execute CREATE DATABASE FROM LISTING
            sql = f"CREATE DATABASE IF NOT EXISTS {sanitized_db_name} FROM LISTING '{sanitized_listing_id}'"
            self._execute_sql(sql)

            logger.info(f"Successfully created database '{db_name}' from listing '{listing_id}'")
            return db_name
        except NotFoundError:
            raise
        except PermissionError:
            raise
        except ValueError:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "does not exist" in error_msg:
                raise NotFoundError(f"Listing '{listing_id}' not available") from e
            elif "already exists" in error_msg:
                # Database already exists - this is okay, return the database name
                logger.info(f"Database '{db_name}' already exists for listing '{listing_id}'")
                return db_name
            elif "permission" in error_msg or "access denied" in error_msg or "insufficient privileges" in error_msg:
                raise PermissionError(f"Permission denied to create database from listing '{listing_id}'") from e
            else:
                logger.error(f"Failed to create database from listing '{listing_id}': {e}")
                raise ConnectionError(f"Unable to create database from listing: {e}") from e

    def _map_snowflake_type(self, snowflake_type: str) -> str:
        """
        Map Snowflake data type to ODCS field type.

        Args:
            snowflake_type: Snowflake data type (e.g., 'VARCHAR', 'NUMBER', 'TIMESTAMP_NTZ')

        Returns:
            ODCS field type (string, number, boolean, date, datetime, array, object)
        """
        if not snowflake_type:
            return "string"

        # Normalize to uppercase for comparison
        type_upper = snowflake_type.upper().strip()

        # String types
        if any(t in type_upper for t in ["VARCHAR", "CHAR", "STRING", "TEXT"]):
            return "string"

        # Integer and decimal number types
        if any(t in type_upper for t in ["NUMBER", "DECIMAL", "NUMERIC", "INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT"]):
            return "number"

        # Floating point number types
        if any(t in type_upper for t in ["FLOAT", "DOUBLE", "REAL", "DOUBLE_PRECISION"]):
            return "number"

        # Boolean type
        if "BOOLEAN" in type_upper or "BOOL" in type_upper:
            return "boolean"

        # Date type
        if type_upper == "DATE":
            return "date"

        # Timestamp types (all map to datetime)
        if any(t in type_upper for t in ["TIMESTAMP", "TIME"]):
            return "datetime"

        # Array type
        if "ARRAY" in type_upper:
            return "array"

        # Object/Variant types
        if any(t in type_upper for t in ["OBJECT", "VARIANT", "MAP"]):
            return "object"

        # Default to string for unknown types
        logger.debug(f"Unknown Snowflake type '{snowflake_type}', mapping to 'string'")
        return "string"

    def _extract_schema_metadata(self, database_name: str) -> Dict[str, Any]:
        """
        Extract schema metadata from a database created from a listing.

        Queries INFORMATION_SCHEMA.COLUMNS to get column information and builds
        ODCS schema structure with fields array.

        Args:
            database_name: Name of the database created from listing

        Returns:
            Structured schema metadata dictionary with fields array

        Raises:
            NotFoundError: If database not found
            ConnectionError: If unable to connect to Snowflake
        """
        try:
            # Validate database_name
            if not database_name or not isinstance(database_name, str):
                raise ValueError("database_name must be a non-empty string")

            import re
            if not re.match(r'^[a-zA-Z0-9_]+$', database_name):
                raise ValueError(f"Invalid database_name format: {database_name}")

            # Query INFORMATION_SCHEMA.COLUMNS for all tables in the database
            sql = """
                SELECT
                    TABLE_SCHEMA,
                    TABLE_NAME,
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_DEFAULT,
                    COMMENT,
                    ORDINAL_POSITION
                FROM {database}.INFORMATION_SCHEMA.COLUMNS
                ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
            """.format(database=database_name)

            results = self._execute_sql(sql)

            if not results:
                logger.warning(f"No columns found in database '{database_name}'")
                return {"fields": []}

            # Group columns by table
            tables = {}
            for row in results:
                schema_name = row.get("TABLE_SCHEMA", "")
                table_name = row.get("TABLE_NAME", "")
                table_key = f"{schema_name}.{table_name}" if schema_name else table_name

                if table_key not in tables:
                    tables[table_key] = {
                        "schema": schema_name,
                        "table": table_name,
                        "fields": [],
                    }

                # Map Snowflake type to ODCS type
                snowflake_type = row.get("DATA_TYPE", "")
                odcs_type = self._map_snowflake_type(snowflake_type)

                # Build field definition
                field = {
                    "name": row.get("COLUMN_NAME", ""),
                    "type": odcs_type,
                    "nullable": row.get("IS_NULLABLE", "YES") == "YES",
                }

                # Add description if available
                comment = row.get("COMMENT")
                if comment:
                    field["description"] = comment

                # Add default value if available
                default_value = row.get("COLUMN_DEFAULT")
                if default_value:
                    field["default"] = default_value

                tables[table_key]["fields"].append(field)

            # Build schema metadata structure
            # If single table, return its fields directly
            # If multiple tables, return structure with tables array
            if len(tables) == 1:
                table_data = list(tables.values())[0]
                return {
                    "fields": table_data["fields"],
                    "table": table_data["table"],
                    "schema": table_data["schema"],
                }
            else:
                # Multiple tables - return structure with tables array
                tables_list = []
                for table_key, table_data in tables.items():
                    tables_list.append({
                        "schema": table_data["schema"],
                        "table": table_data["table"],
                        "fields": table_data["fields"],
                    })
                return {
                    "tables": tables_list,
                    "field_count": sum(len(t["fields"]) for t in tables_list),
                }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract schema metadata from database '{database_name}': {e}")
            raise ConnectionError(f"Unable to extract schema metadata: {e}") from e

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Pull (harvest) datasets from Snowflake Data Marketplace to Hub following metadata-first pattern.

        **Metadata-First Behavior**:
        This method discovers listings and maps them to MarketplaceAssetMapping objects. It does
        NOT create databases, extract schema metadata, request listings, or accept legal terms.
        These operations are deferred to `download_resource()` when data is explicitly requested.

        **What This Method Does**:
        1. Discovers listings from Snowflake (by IDs or via filters)
        2. Fetches resources for each listing (if include_resources=True)
        3. Maps each listing to MarketplaceAssetMapping using `map_to_hub_asset()`
        4. Returns mappings in SyncResult.metadata["mappings"] for workflow processing

        **What This Method Does NOT Do**:
        - Request listings (deferred to `download_resource()`)
        - Accept legal terms (deferred to `download_resource()`)
        - Create databases (deferred to `download_resource()`)
        - Extract schema metadata (deferred to `download_resource()`)
        - Access external data sources (only stores references)

        Args:
            listing_ids: Optional list of specific listing IDs to sync.
                If None, syncs all listings matching filters.
            filters: Optional dictionary of filters to apply (passed to list_listings)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets (metadata-only, no effect)
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with:
            - status: SyncStatus (COMPLETED, PARTIAL, FAILED)
            - successful_items: Number of successfully mapped listings
            - failed_items: Number of failed mappings
            - metadata: Dictionary containing:
                - "mappings": List of MarketplaceAssetMapping objects (serialized as dicts)
                - "errors": List of error messages for failed mappings
            - started_at: Operation start timestamp
            - completed_at: Operation completion timestamp

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to Snowflake

        **Workflow Integration**:
        This method is called by the `marketplace_sync_pull` workflow:
        1. `discover_listings_task` calls `connector.list_listings()` or `connector.get_listing()`
        2. `map_listings_to_assets_task` calls `connector.map_to_hub_asset()` for each listing
        3. `create_federated_assets_task` calls `create_federated_asset_with_contracts()` for each mapping
        4. If `data_strategy != "METADATA_ONLY"`, workflow calls `connector.download_resource()` for each resource
        """
        options = options or {}
        limit = options.get("limit")
        include_resources = options.get("include_resources", True)
        started_at = datetime.now()

        successful_items = 0
        failed_items = 0
        skipped_items = 0
        errors = []
        mappings = []

        try:
            # Get listings to sync
            if listing_ids:
                # Fetch specific listings by ID
                listings = []
                for listing_id in listing_ids:
                    try:
                        listing = self.get_listing(listing_id)
                        listings.append(listing)
                    except NotFoundError:
                        skipped_items += 1
                        error_msg = f"Listing '{listing_id}' not found"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    except Exception as e:
                        failed_items += 1
                        error_msg = f"Failed to fetch listing '{listing_id}': {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
            else:
                # Fetch listings using filters
                listings = self.list_listings(filters=filters, limit=limit)

            total_items = len(listings)

            # Process each listing (metadata-first: only map, don't create databases)
            for listing in listings:
                listing_id = listing.marketplace_id

                try:
                    # Fetch resources if requested (metadata-only, no data download)
                    if include_resources:
                        try:
                            resources = self.list_resources(listing_id)
                            listing.resources = resources
                        except Exception as e:
                            logger.warning(
                                f"Failed to fetch resources for listing '{listing_id}': {e}"
                            )
                            # Continue without resources rather than failing the whole sync

                    # Map to Hub asset format (metadata-only, includes external resource references)
                    mapping = self.map_to_hub_asset(listing)

                    mappings.append(mapping)
                    successful_items += 1
                    logger.info(f"Successfully mapped listing '{listing_id}' (metadata-only)")
                except Exception as e:
                    failed_items += 1
                    error_msg = f"Failed to map listing '{listing_id}': {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg, exc_info=True)
                    continue

            status = SyncStatus.COMPLETED if failed_items == 0 else SyncStatus.PARTIAL
            if successful_items == 0:
                status = SyncStatus.FAILED

            return SyncResult(
                status=status,
                total_items=total_items,
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=errors,
                started_at=started_at,
                completed_at=datetime.now(),
                metadata={
                    "mappings": [mapping.__dict__ for mapping in mappings],
                    "include_resources": include_resources,
                },
            )
        except Exception as e:
            logger.error(f"Sync pull failed: {e}", exc_info=True)
            return SyncResult(
                status=SyncStatus.FAILED,
                total_items=0,
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now(),
            )

    def sync_push(self, asset_ids: List[str], options: Optional[Dict[str, Any]] = None) -> SyncResult:
        """
        Push Hub assets to Snowflake Data Marketplace.

        **DEPRECATED**: Snowflake connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            asset_ids: List of Hub asset IDs to push
            options: Optional dictionary of sync options

        Returns:
            SyncResult object

        Raises:
            NotImplementedError: Snowflake connector does not support push operations
        """
        raise NotImplementedError(
            "Snowflake connector is harvest-only (PULL only). "
            "Snowflake Data Marketplace listings are managed through Snowflake's native interface."
        )

    def map_to_hub_asset(
        self, listing: MarketplaceListing, sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map a Snowflake Data Marketplace listing to a Hub asset representation following metadata-first pattern.

        Converts a MarketplaceListing object to MarketplaceAssetMapping, extracting all metadata
        required for federated asset creation. This method does NOT access external data sources
        or download data - it only extracts metadata and stores external resource references.

        **What This Method Does**:
        1. Extracts asset metadata (name, description, domain, tags, status, visibility)
        2. Extracts ODPS contract metadata (product details, pricing plans, access methods, payment gateways)
        3. Extracts ODCS contract metadata (schema hints, quality hints, SLA hints) if available
        4. Builds source_metadata with marketplace connection and listing information
        5. Includes external resource references in `resources` list (does NOT download resources)

        **What This Method Does NOT Do**:
        - Access external data sources (only stores references)
        - Download data (only maps resources with external identifiers)
        - Create databases (deferred to `download_resource()`)
        - Extract schema metadata (deferred to `download_resource()`)
        - Request listings or accept legal terms (deferred to `download_resource()`)

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking synchronization operations.
                If provided, will be included in source_metadata for audit and tracking purposes.

        Returns:
            MarketplaceAssetMapping object containing:
            - asset_data: Dictionary with Hub asset fields (name, description, domain, tags, status, visibility)
            - source_type: AssetSourceType.FEDERATED (always FEDERATED for marketplace assets)
            - source_metadata: Dictionary with marketplace connection and listing information:
                - marketplace_type: SNOWFLAKE_DATA_MARKETPLACE
                - marketplace_id: Snowflake account identifier (connection ID)
                - listing_id: Listing identifier in Snowflake Data Marketplace
                - listing_url: URL to the listing (if available)
                - synced_at: Timestamp when sync occurred (ISO format)
                - sync_job_id: ID of the sync job (if provided)
                - database_name: Expected database name (for reference, not created yet)
            - odps_metadata: Optional dictionary with ODPS contract data (product details, pricing, access, payment)
            - odcs_metadata: Optional dictionary with ODCS contract data (schema hints, quality hints, SLA hints)
            - resources: List of MarketplaceResource objects with external references:
                - resource_id: Listing ID or table identifier (for on-demand download)
                - name: Resource name
                - resource_type: DATABASE, SCHEMA, or TABLE
                - format: SNOWFLAKE_DATABASE or table format
                - metadata.external: True flag indicating external resource
                - metadata.listing_id: Listing ID for on-demand download

        Raises:
            ValueError: If listing data cannot be mapped or is invalid
        """
        if not listing:
            raise ValueError("Listing is required")

        # Get Snowflake database data from metadata
        snowflake_db = listing.metadata.get("snowflake_database", {}) if listing.metadata else {}
        snowflake_listing = listing.metadata.get("snowflake_listing", {}) if listing.metadata else {}

        # Extract domain from owner/category
        domain = listing.category or snowflake_db.get("DATABASE_OWNER")

        # Build asset data
        asset_data: Dict[str, Any] = {
            "name": listing.title,
            "description": listing.description or "",
            "key": f"snowflake-{listing.marketplace_id}",
            "tags": listing.tags or [],
            "status": "ACTIVE",  # Snowflake listings are active by default
            "visibility": "PUBLIC",  # Snowflake Data Marketplace listings are public
        }

        if domain:
            asset_data["domain"] = domain

        # Resources are already in listing.resources (from list_resources call in sync_pull)
        # If no resources available, create a default external resource reference for the listing
        resources = listing.resources or []

        # Ensure at least one external resource reference exists (for on-demand download)
        if not resources:
            # Create a default resource reference pointing to the listing ID
            # This allows download_resource() to be called with the listing ID
            resources.append(MarketplaceResource(
                resource_id=listing.marketplace_id,
                resource_type="DATABASE",
                name=listing.marketplace_id,
                description=f"Snowflake Data Marketplace listing: {listing.title}",
                url=None,  # External resource, no direct URL
                format="SNOWFLAKE_DATABASE",
                metadata={
                    "external": True,
                    "download_url": None,  # Will be handled by download_resource()
                    "listing_id": listing.marketplace_id,
                }
            ))

        # Extract ODPS metadata from listing
        # First try to get from metadata, otherwise build from listing attributes
        odps_metadata = None
        if listing.metadata and listing.metadata.get("odps_metadata"):
            odps_metadata = listing.metadata["odps_metadata"]
        elif listing.pricing_plans or listing.access_methods or listing.payment_gateways:
            # Build ODPS metadata from listing attributes
            odps_metadata = {}
            if listing.pricing_plans:
                odps_metadata["pricing_plans"] = listing.pricing_plans
            if listing.access_methods:
                odps_metadata["access_methods"] = listing.access_methods
            if listing.payment_gateways:
                odps_metadata["payment_gateways"] = listing.payment_gateways
            if listing.product_id:
                odps_metadata["product_details"] = {
                    "productID": listing.product_id,
                    "product_name": listing.title,
                    "product_description": listing.description or "",
                }

        # Extract ODCS metadata from listing
        odcs_metadata = None
        if listing.metadata and listing.metadata.get("odcs_metadata"):
            odcs_metadata = listing.metadata["odcs_metadata"]

        # Build source metadata
        # Use account identifier as marketplace_id (connection ID)
        marketplace_id = self.account or "snowflake"
        source_metadata: Dict[str, Any] = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "marketplace_id": marketplace_id,
            "listing_id": listing.marketplace_id,
            "listing_url": listing.url,
            "synced_at": datetime.now().isoformat(),
            "database_name": listing.marketplace_id,
            "database_owner": snowflake_db.get("DATABASE_OWNER"),
            "comment": snowflake_db.get("COMMENT"),
        }

        if sync_job_id:
            source_metadata["sync_job_id"] = sync_job_id

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata,
            odcs_metadata=odcs_metadata,
            resources=resources,
        )

    def map_from_hub_asset(
        self, asset_data: Dict[str, Any], odps_metadata: Optional[Dict[str, Any]] = None, odcs_metadata: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        """
        Map a Hub asset to a Snowflake Data Marketplace listing representation.

        **DEPRECATED**: Snowflake connector is harvest-only (PULL only).
        This method raises NotImplementedError.

        Args:
            asset_data: Dictionary containing Hub asset fields
            odps_metadata: Optional ODPS contract data
            odcs_metadata: Optional ODCS contract data

        Returns:
            MarketplaceListing object

        Raises:
            NotImplementedError: Snowflake connector does not support push operations
        """
        raise NotImplementedError(
            "Snowflake connector is harvest-only (PULL only). "
            "Snowflake Data Marketplace listings are managed through Snowflake's native interface."
        )

    def close(self):
        """Close Snowflake connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Snowflake connection closed")
            except Exception as e:
                logger.warning(f"Error closing Snowflake connection: {e}")
            finally:
                self._connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

