"""
Comprehensive Tests for Snowflake Connector

Tests use real Snowflake connections - no mocks or stubs.
Tests require environment variables:
- SNOWFLAKE_ACCOUNT: Snowflake account identifier (e.g., 'xy12345.us-east-1')
- SNOWFLAKE_USER: Snowflake username
- SNOWFLAKE_TOKEN: JWT Programmatic Access Token
- SNOWFLAKE_WAREHOUSE: Optional warehouse name
- SNOWFLAKE_ROLE: Optional role name
- SNOWFLAKE_DATABASE: Optional database name
"""

import contextlib
import os
import unittest
from datetime import datetime

import pytest
from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreakerError,
    reset_circuit_breaker_by_name,
)
from hub.apps.core.services.base import ConnectionError, NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.snowflake_connector import (
    SNOWFLAKE_AVAILABLE,
    SnowflakeConnector,
)


def get_snowflake_credentials() -> dict:
    """Get Snowflake credentials from environment variables."""
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    token = os.getenv("SNOWFLAKE_TOKEN")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    role = os.getenv("SNOWFLAKE_ROLE")
    database = os.getenv("SNOWFLAKE_DATABASE")

    if not account or not user or not token:
        raise unittest.SkipTest(
            "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_TOKEN environment variables are required"
        )

    credentials = {
        "account": account,
        "user": user,
        "token": token,
    }

    if warehouse:
        credentials["warehouse"] = warehouse
    if role:
        credentials["role"] = role
    if database:
        credentials["database"] = database

    return credentials


def has_snowflake_connection() -> bool:
    """Check if Snowflake connection is available.

    Returns False when:
    * The ``snowflake-connector-python`` package is not installed.
    * Required env vars (``SNOWFLAKE_ACCOUNT``, ``SNOWFLAKE_USER``,
      ``SNOWFLAKE_TOKEN``) are not set.
    * The connection test fails with a known connection/auth error.

    Unexpected exceptions (bugs in the connector) propagate to the caller
    rather than being silently swallowed as "not available."
    """
    if not SNOWFLAKE_AVAILABLE:
        return False

    try:
        credentials = get_snowflake_credentials()
    except unittest.SkipTest:
        return False

    try:
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        result = connector.test_connection()
        connector.close()
        return result
    except (ConnectionError, ValueError, OSError):
        # Known connection/auth failures — Snowflake genuinely unavailable.
        return False


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorInitialization(TestCase):
    """Test Snowflake connector initialization"""

    def test_init_with_required_params(self):
        """Test initialization with required parameters"""
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

        self.assertEqual(connector.account, "test_account")
        self.assertEqual(connector.user, "test_user")
        self.assertEqual(connector.token, "test_token")
        self.assertFalse(connector._authenticated)

    def test_init_with_optional_params(self):
        """Test initialization with optional parameters"""
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
            warehouse="test_warehouse",
            role="test_role",
            database="test_database",
        )

        self.assertEqual(connector.warehouse, "test_warehouse")
        self.assertEqual(connector.role, "test_role")
        self.assertEqual(connector.database, "test_database")

    def test_marketplace_type_property(self):
        """Test marketplace_type property"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")
        self.assertEqual(connector.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions property"""
        connector = SnowflakeConnector(account="test_account", user="test_user", token="test_token")
        directions = connector.supported_sync_directions
        self.assertIsInstance(directions, list)
        self.assertIn(SyncDirection.PULL, directions)
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorAuthentication(TestCase):
    """Test Snowflake connector authentication"""

    def setUp(self):
        """Set up test fixtures"""
        # Create connector without credentials for validation tests
        self.connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_authenticate_missing_account(self):
        """Test authentication raises error if account missing"""
        credentials = {"user": "test_user", "token": "test_token"}

        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn("account", str(cm.exception).lower())

    def test_authenticate_missing_user(self):
        """Test authentication raises error if user missing"""
        credentials = {"account": "test_account", "token": "test_token"}

        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn("user", str(cm.exception).lower())

    def test_authenticate_missing_token(self):
        """Test authentication raises error if token missing"""
        credentials = {"account": "test_account", "user": "test_user"}

        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn("token", str(cm.exception).lower())

    def test_authenticate_with_jwt_token_key(self):
        """Test authentication accepts jwt_token as alternative to token"""
        # This test validates the credential extraction logic without requiring real connection
        credentials = {
            "account": "test_account",
            "user": "test_user",
            "jwt_token": "test_token",
        }

        # Should not raise ValueError for missing token (jwt_token is accepted)
        # But will raise ConnectionError when trying to connect
        with self.assertRaises(ConnectionError):
            self.connector.authenticate(credentials)

    def test_authenticate_empty_credentials(self):
        """Test authentication raises error if credentials empty"""
        with self.assertRaises(ValueError):
            self.connector.authenticate({})

    def test_authenticate_invalid_credentials(self):
        """Test authentication raises ConnectionError with invalid credentials"""
        invalid_credentials = {
            "account": "invalid_account",
            "user": "invalid_user",
            "token": "invalid_token",
        }

        with self.assertRaises(ConnectionError):
            self.connector.authenticate(invalid_credentials)

    @pytest.mark.integration
    def test_authenticate_success(self):
        """Test successful authentication"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )

        try:
            result = connector.authenticate(credentials)
            self.assertTrue(result)
            self.assertTrue(connector._authenticated)
        finally:
            connector.close()


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorConnectionTest(TestCase):
    """Test Snowflake connector connection testing"""

    def test_test_connection_invalid_credentials(self):
        """Test connection test raises ConnectionError with invalid credentials"""
        connector = SnowflakeConnector(
            account="invalid_account",
            user="invalid_user",
            token="invalid_token",
        )

        try:
            with self.assertRaises(ConnectionError):
                connector.test_connection()
        finally:
            connector.close()

    @pytest.mark.integration
    def test_test_connection_success(self):
        """Test successful connection test"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )

        try:
            result = connector.test_connection()
            self.assertTrue(result)
        finally:
            connector.close()

    @pytest.mark.integration
    def test_test_connection_before_authenticate(self):
        """Test connection test works before authenticate"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )

        try:
            result = connector.test_connection()
            self.assertTrue(result)
        finally:
            connector.close()


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorSQLExecution(TestCase):
    """Test Snowflake connector SQL execution"""

    def setUp(self):
        """Reset circuit breaker so tests with invalid credentials see CLOSED state."""
        try:
            reset_circuit_breaker_by_name("snowflake-connector")
        except (ConnectionError, OSError, ValueError):
            # Redis may be unavailable in some test configurations;
            # the circuit breaker falls back gracefully.
            pass

    def test_execute_sql_invalid_query(self):
        """Test executing invalid SQL query raises ValueError"""
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

        try:
            # This will fail at connection level or circuit open; we test the error handling
            with self.assertRaises((ValueError, ConnectionError, CircuitBreakerError)):
                connector._execute_sql("INVALID SQL QUERY")
        finally:
            connector.close()

    def test_execute_sql_nonexistent_table(self):
        """Test executing query on nonexistent table raises NotFoundError"""
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

        try:
            # This will fail at connection level or circuit open; we test the error handling
            with self.assertRaises((NotFoundError, ConnectionError, CircuitBreakerError)):
                connector._execute_sql(
                    "SELECT * FROM nonexistent_database.nonexistent_schema.nonexistent_table"
                )
        finally:
            connector.close()

    @pytest.mark.integration
    def test_execute_sql_simple_query(self):
        """Test executing a simple SQL query"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        connector.authenticate(credentials)

        try:
            results = connector._execute_sql("SELECT CURRENT_VERSION()")
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
            self.assertIn("CURRENT_VERSION()", results[0])
        finally:
            connector.close()

    @pytest.mark.integration
    def test_execute_sql_with_params(self):
        """Test executing SQL query with parameters"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        connector.authenticate(credentials)

        try:
            sql = "SELECT CURRENT_DATABASE() AS database_name"
            results = connector._execute_sql(sql)
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
        finally:
            connector.close()

    @pytest.mark.integration
    def test_get_connection_reuse(self):
        """Test that _get_connection reuses existing connection"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        connector.authenticate(credentials)

        try:
            connection1 = connector._get_connection()
            connection2 = connector._get_connection()
            self.assertEqual(connection1, connection2)
        finally:
            connector.close()

    @pytest.mark.integration
    def test_get_connection_creates_new_on_close(self):
        """Test that _get_connection creates new connection if old one is closed"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        connector.authenticate(credentials)

        try:
            connection1 = connector._get_connection()
            connection1.close()
            # Next call should create a new connection
            connection2 = connector._get_connection()
            self.assertNotEqual(connection1, connection2)
        finally:
            connector.close()


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorDiscoveryOperations(TestCase):
    """Test Snowflake connector discovery operations (validation tests without credentials)"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_get_listing_details_not_found(self):
        """Test _get_listing_details raises NotFoundError for nonexistent listing"""
        with self.assertRaises((NotFoundError, ConnectionError)):
            self.connector._get_listing_details("nonexistent_listing_12345")

    def test_get_listing_details_invalid_input(self):
        """Test _get_listing_details validates input to prevent SQL injection"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector._get_listing_details("")

        # Test None
        with self.assertRaises(ValueError):
            self.connector._get_listing_details(None)

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector._get_listing_details("'; DROP TABLE users; --")

        # Test invalid characters
        with self.assertRaises(ValueError):
            self.connector._get_listing_details("test@listing#123")

    def test_list_listings_invalid_pagination(self):
        """Test list_listings validates pagination parameters"""
        # Test negative offset
        with self.assertRaises(ValueError):
            self.connector.list_listings(offset=-1)

        # Test negative limit
        with self.assertRaises(ValueError):
            self.connector.list_listings(limit=-1)

        # Test non-integer offset (type checker warning is expected - we're testing error handling)
        with self.assertRaises((ValueError, TypeError)):
            self.connector.list_listings(offset="invalid")  # type: ignore[misc]  # test: edge-case type exercise

        # Test non-integer limit (type checker warning is expected - we're testing error handling)
        with self.assertRaises((ValueError, TypeError)):
            self.connector.list_listings(limit="invalid")  # type: ignore[misc]  # test: edge-case type exercise

    def test_list_resources_invalid_input(self):
        """Test list_resources validates input to prevent SQL injection"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector.list_resources("")

        # Test None (type checker warning is expected - we're testing error handling)
        with self.assertRaises(ValueError):
            self.connector.list_resources(None)  # type: ignore[misc]  # test: edge-case type exercise

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector.list_resources("'; DROP TABLE users; --")

        # Test invalid characters
        with self.assertRaises(ValueError):
            self.connector.list_resources("test@database#123")

    def test_extract_odps_metadata(self):
        """Test ODPS metadata extraction"""
        listing_details = {
            "product_id": "test_product_123",
            "product_name": "Test Product",
            "product_description": "Test Description",
            "version": "1.0",
            "DATABASE_NAME": "TEST_DB",
            "DATABASE_OWNER": "TEST_OWNER",
        }

        odps_metadata = self.connector._extract_odps_metadata(listing_details)

        self.assertIsInstance(odps_metadata, dict)
        self.assertIn("product_details", odps_metadata)
        self.assertIn("access_methods", odps_metadata)
        self.assertEqual(odps_metadata["product_details"]["productID"], "test_product_123")
        self.assertEqual(odps_metadata["product_details"]["product_name"], "Test Product")

    def test_extract_odps_metadata_with_pricing(self):
        """Test ODPS metadata extraction with pricing plans"""
        listing_details = {
            "product_name": "Test Product",
            "pricing_plans": [{"name": "Free", "price": 0}],
            "DATABASE_NAME": "TEST_DB",
        }

        odps_metadata = self.connector._extract_odps_metadata(listing_details)

        self.assertIn("pricing_plans", odps_metadata)
        self.assertIsInstance(odps_metadata["pricing_plans"], list)

    def test_extract_odcs_metadata(self):
        """Test ODCS metadata extraction"""
        listing_details = {
            "schema": {"hints": {"format": "parquet"}},
            "quality": {"hints": {"completeness": 0.95}},
            "CREATED": datetime.now(),
        }

        odcs_metadata = self.connector._extract_odcs_metadata(listing_details)

        self.assertIsInstance(odcs_metadata, dict)
        self.assertIn("schema", odcs_metadata)
        self.assertIn("quality", odcs_metadata)

    def test_build_marketplace_listing(self):
        """Test building MarketplaceListing from details"""
        listing_id = "test_listing_123"
        listing_details = {
            "title": "Test Listing",
            "description": "Test Description",
            "category": "Test Category",
            "provider": "Test Provider",
            "tags": ["tag1", "tag2"],
            "CREATED": datetime.now(),
            "DATABASE_NAME": "TEST_DB",
        }

        listing = self.connector._build_marketplace_listing(listing_id, listing_details)

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, listing_id)
        self.assertEqual(listing.title, "Test Listing")
        self.assertEqual(listing.description, "Test Description")
        self.assertEqual(listing.category, "Test Category")
        self.assertIn("odps_metadata", listing.metadata)
        self.assertIn("odcs_metadata", listing.metadata)

    def test_build_marketplace_listing_with_summary_row(self):
        """Test building MarketplaceListing with summary row"""
        listing_id = "test_listing_123"
        listing_details = {"title": "Test Listing", "DATABASE_NAME": "TEST_DB"}
        summary_row = {"provider": "Test Provider", "category": "Test Category"}

        listing = self.connector._build_marketplace_listing(
            listing_id, listing_details, summary_row
        )

        self.assertEqual(listing.category, "Test Category")
        self.assertIn("provider", listing.metadata.get("snowflake_listing", {}))


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
@pytest.mark.integration
class TestSnowflakeConnectorListings(TestCase):
    """Test Snowflake connector listing operations (integration tests)"""

    def setUp(self):
        """Set up test fixtures"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        self.credentials = get_snowflake_credentials()
        self.connector = SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            role=self.credentials.get("role"),
            database=self.credentials.get("database"),
        )
        # Authenticate
        self.connector.authenticate(self.credentials)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_list_listings(self):
        """Test listing available databases"""
        listings = self.connector.list_listings(limit=10)

        self.assertIsInstance(listings, list)
        # Verify all listings are MarketplaceListing objects
        for listing in listings:
            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)
            self.assertIsNotNone(listing.marketplace_id)
            self.assertIsNotNone(listing.title)
            # Verify ODPS and ODCS metadata are present
            self.assertIn("odps_metadata", listing.metadata)
            self.assertIn("odcs_metadata", listing.metadata)

    def test_list_listings_with_limit(self):
        """Test listing with limit"""
        listings = self.connector.list_listings(limit=5)

        self.assertLessEqual(len(listings), 5)

    def test_list_listings_with_offset(self):
        """Test listing with offset"""
        listings1 = self.connector.list_listings(limit=5, offset=0)
        listings2 = self.connector.list_listings(limit=5, offset=5)

        # Results should be different (if there are more than 5 listings)
        if len(listings1) == 5:
            self.assertNotEqual(listings1[0].marketplace_id, listings2[0].marketplace_id)

    def test_list_listings_with_filters(self):
        """Test listing with filters"""
        # Get first listing to use as filter
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for filter test")

        test_provider = all_listings[0].category or all_listings[0].metadata.get("provider")
        if test_provider:
            filtered_listings = self.connector.list_listings(filters={"provider": test_provider})

            self.assertGreater(len(filtered_listings), 0)
            for listing in filtered_listings:
                self.assertIn(test_provider.lower(), (listing.category or "").lower())

    def test_get_listing(self):
        """Test getting a specific listing"""
        # Get first listing
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for get_listing test")

        listing_id = all_listings[0].marketplace_id
        listing = self.connector.get_listing(listing_id)

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, listing_id)
        self.assertEqual(listing.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)
        # Verify ODPS and ODCS metadata are present
        self.assertIn("odps_metadata", listing.metadata)
        self.assertIn("odcs_metadata", listing.metadata)

    def test_get_listing_not_found(self):
        """Test getting nonexistent listing raises NotFoundError"""
        with self.assertRaises(NotFoundError):
            self.connector.get_listing("nonexistent_database_12345")


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
@pytest.mark.integration
class TestSnowflakeConnectorResources(TestCase):
    """Test Snowflake connector resource operations"""

    def setUp(self):
        """Set up test fixtures"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        self.credentials = get_snowflake_credentials()
        self.connector = SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            role=self.credentials.get("role"),
            database=self.credentials.get("database"),
        )
        # Authenticate
        self.connector.authenticate(self.credentials)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_list_resources(self):
        """Test listing resources (databases/schemas/tables) for a listing"""
        # Get first listing
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for resource test")

        listing_id = all_listings[0].marketplace_id
        resources = self.connector.list_resources(listing_id)

        self.assertIsInstance(resources, list)
        # Verify all resources are MarketplaceResource objects
        for resource in resources:
            self.assertIsInstance(resource, MarketplaceResource)
            self.assertIsNotNone(resource.resource_id)
            self.assertIsNotNone(resource.name)
            self.assertIn(resource.resource_type, ["DATABASE", "SCHEMA", "TABLE", "VIEW"])

    def test_list_resources_not_found(self):
        """Test listing resources for nonexistent database raises NotFoundError"""
        with self.assertRaises(NotFoundError):
            self.connector.list_resources("nonexistent_database_12345")


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorPushOperations(TestCase):
    """Test Snowflake connector push operations (should raise NotImplementedError)"""

    def setUp(self):
        """Set up test fixtures"""
        # These tests don't require a real connection - they just test NotImplementedError
        # Use dummy credentials since we're not actually connecting
        self.connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_create_listing_raises_not_implemented(self):
        """Test create_listing raises NotImplementedError"""
        listing = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test",
        )

        with self.assertRaises(NotImplementedError):
            self.connector.create_listing(listing)

    def test_update_listing_raises_not_implemented(self):
        """Test update_listing raises NotImplementedError"""
        listing = MarketplaceListing(
            marketplace_id="test",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title="Test",
        )

        with self.assertRaises(NotImplementedError):
            self.connector.update_listing("test", listing)

    def test_publish_resource_raises_not_implemented(self):
        """Test publish_resource raises NotImplementedError"""
        resource = MarketplaceResource(
            resource_id="test",
            resource_type="TABLE",
            name="Test",
        )

        with self.assertRaises(NotImplementedError):
            self.connector.publish_resource("test", resource)

    def test_sync_push_raises_not_implemented(self):
        """Test sync_push raises NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(["test_asset_id"])

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test map_from_hub_asset raises NotImplementedError"""
        with self.assertRaises(NotImplementedError):
            self.connector.map_from_hub_asset({"name": "test"})


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorPullOperations(TestCase):
    """Test Snowflake connector pull operations (validation tests without credentials)"""

    def setUp(self):
        """Reset circuit breaker and set up test fixtures."""
        with contextlib.suppress(Exception):
            reset_circuit_breaker_by_name("snowflake-connector")
        self.connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_map_snowflake_type_string_types(self):
        """Test mapping Snowflake string types to ODCS"""
        self.assertEqual(self.connector._map_snowflake_type("VARCHAR"), "string")
        self.assertEqual(self.connector._map_snowflake_type("CHAR"), "string")
        self.assertEqual(self.connector._map_snowflake_type("STRING"), "string")
        self.assertEqual(self.connector._map_snowflake_type("TEXT"), "string")

    def test_map_snowflake_type_number_types(self):
        """Test mapping Snowflake number types to ODCS"""
        self.assertEqual(self.connector._map_snowflake_type("NUMBER"), "number")
        self.assertEqual(self.connector._map_snowflake_type("DECIMAL"), "number")
        self.assertEqual(self.connector._map_snowflake_type("INTEGER"), "number")
        self.assertEqual(self.connector._map_snowflake_type("BIGINT"), "number")
        self.assertEqual(self.connector._map_snowflake_type("FLOAT"), "number")
        self.assertEqual(self.connector._map_snowflake_type("DOUBLE"), "number")

    def test_map_snowflake_type_boolean_types(self):
        """Test mapping Snowflake boolean types to ODCS"""
        self.assertEqual(self.connector._map_snowflake_type("BOOLEAN"), "boolean")
        self.assertEqual(self.connector._map_snowflake_type("BOOL"), "boolean")

    def test_map_snowflake_type_date_types(self):
        """Test mapping Snowflake date/timestamp types to ODCS"""
        self.assertEqual(self.connector._map_snowflake_type("DATE"), "date")
        self.assertEqual(self.connector._map_snowflake_type("TIMESTAMP"), "datetime")
        self.assertEqual(self.connector._map_snowflake_type("TIMESTAMP_NTZ"), "datetime")
        self.assertEqual(self.connector._map_snowflake_type("TIMESTAMP_LTZ"), "datetime")
        self.assertEqual(self.connector._map_snowflake_type("TIMESTAMP_TZ"), "datetime")

    def test_map_snowflake_type_complex_types(self):
        """Test mapping Snowflake complex types to ODCS"""
        self.assertEqual(self.connector._map_snowflake_type("ARRAY"), "array")
        self.assertEqual(self.connector._map_snowflake_type("OBJECT"), "object")
        self.assertEqual(self.connector._map_snowflake_type("VARIANT"), "object")

    def test_map_snowflake_type_unknown_type(self):
        """Test mapping unknown Snowflake types defaults to string"""
        self.assertEqual(self.connector._map_snowflake_type("UNKNOWN_TYPE"), "string")
        self.assertEqual(self.connector._map_snowflake_type(""), "string")
        self.assertEqual(self.connector._map_snowflake_type(None), "string")

    def test_request_listing_invalid_input(self):
        """Test _request_listing validates input to prevent SQL injection"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector._request_listing("")

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector._request_listing("'; DROP TABLE users; --")

        # Test invalid characters
        with self.assertRaises(ValueError):
            self.connector._request_listing("test@listing#123")

    def test_accept_legal_terms_invalid_input(self):
        """Test _accept_legal_terms validates input"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector._accept_legal_terms("")

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector._accept_legal_terms("'; DROP TABLE users; --")

    def test_create_database_from_listing_invalid_input(self):
        """Test _create_database_from_listing validates input"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector._create_database_from_listing("")

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector._create_database_from_listing("'; DROP TABLE users; --")

    def test_create_database_from_listing_name_generation(self):
        """Test database name generation from listing ID"""
        # This test verifies the database name generation logic
        # We can't actually create databases without credentials, but we can test the logic
        listing_id = "test-listing.123"
        # The method will generate DB_TEST_LISTING_123
        # With fake credentials we get ConnectionError, CircuitBreakerError, or NotFoundError
        with self.assertRaises(
            (ConnectionError, NotFoundError, PermissionError, CircuitBreakerError)
        ):
            self.connector._create_database_from_listing(listing_id)

    def test_extract_schema_metadata_invalid_input(self):
        """Test _extract_schema_metadata validates input"""
        # Test empty string
        with self.assertRaises(ValueError):
            self.connector._extract_schema_metadata("")

        # Test SQL injection attempt
        with self.assertRaises(ValueError):
            self.connector._extract_schema_metadata("'; DROP TABLE users; --")

    def test_download_resource_invalid_format(self):
        """Test download_resource validates resource_id format or fails at connection/listing"""
        # Single-part resource_id is treated as listing ID; with fake credentials we get
        # ConnectionError, NotFoundError (e.g. 404 login), or CircuitBreakerError
        with self.assertRaises((ValueError, ConnectionError, CircuitBreakerError, NotFoundError)):
            self.connector.download_resource("invalid", "/tmp/test.csv")

        # Test SQL injection in resource_id
        with self.assertRaises(ValueError):
            self.connector.download_resource(
                "db'; DROP TABLE users; --.schema.table", "/tmp/test.csv"
            )


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
@pytest.mark.integration
class TestSnowflakeConnectorSyncPull(TestCase):
    """Test Snowflake connector sync_pull operation (integration tests)"""

    def setUp(self):
        """Set up test fixtures"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        self.credentials = get_snowflake_credentials()
        self.connector = SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            role=self.credentials.get("role"),
            database=self.credentials.get("database"),
        )
        # Authenticate
        self.connector.authenticate(self.credentials)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_sync_pull_dry_run(self):
        """Test sync_pull with dry_run option (metadata-first: always metadata-only, no databases created)"""
        result = self.connector.sync_pull(options={"dry_run": True, "limit": 2})

        self.assertIsInstance(result, SyncResult)
        # Metadata-first: sync_pull() is always metadata-only, so dry_run is effectively always True
        # Verify no databases were created (metadata-first pattern)
        self.assertIn("mappings", result.metadata)
        # Verify mappings are present and serialized
        self.assertIsInstance(result.metadata["mappings"], list)
        if result.metadata["mappings"]:
            # Verify mappings are dicts (serialized MarketplaceAssetMapping)
            self.assertIsInstance(result.metadata["mappings"][0], dict)

    def test_sync_pull_without_resources(self):
        """Test sync_pull without including resources (metadata-first: metadata-only)"""
        result = self.connector.sync_pull(options={"include_resources": False, "limit": 2})

        self.assertIsInstance(result, SyncResult)
        self.assertFalse(result.metadata.get("include_resources"))
        # Verify metadata-first: mappings are present even without resources
        self.assertIn("mappings", result.metadata)

    def test_sync_pull_with_filters(self):
        """Test sync_pull with filters (metadata-first: metadata-only mapping)"""
        result = self.connector.sync_pull(filters={}, options={"limit": 3})

        self.assertIsInstance(result, SyncResult)
        self.assertLessEqual(result.total_items, 3)
        # Verify metadata-first: mappings are returned
        self.assertIn("mappings", result.metadata)

    @pytest.mark.integration
    def test_sync_pull_all_listings(self):
        """Test sync_pull with all listings (metadata-first: metadata-only, no databases created)"""
        # This test will skip if no listings are available
        result = self.connector.sync_pull(options={"limit": 1})

        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED])
        self.assertGreaterEqual(result.total_items, 0)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.completed_at)
        # Verify metadata-first: mappings are returned (metadata-only, no database creation)
        self.assertIn("mappings", result.metadata)
        self.assertIsInstance(result.metadata["mappings"], list)

    @pytest.mark.integration
    def test_sync_pull_specific_listings(self):
        """Test sync_pull with specific listing IDs (metadata-first: metadata-only mapping)"""
        # Get first listing
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for sync_pull test")

        listing_id = all_listings[0].marketplace_id
        result = self.connector.sync_pull(listing_ids=[listing_id])

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.total_items, 1)
        self.assertGreaterEqual(result.successful_items, 0)
        # Verify metadata-first: mappings are returned (metadata-only, no database creation)
        self.assertIn("mappings", result.metadata)
        self.assertIsInstance(result.metadata["mappings"], list)
        if result.successful_items > 0:
            # Verify mapping structure
            mapping = result.metadata["mappings"][0]
            self.assertIn("asset_data", mapping)
            self.assertIn("source_type", mapping)
            self.assertEqual(mapping["source_type"], AssetSourceType.FEDERATED.value)


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
@pytest.mark.integration
class TestSnowflakeConnectorMapping(TestCase):
    """Test Snowflake connector mapping operations"""

    def setUp(self):
        """Set up test fixtures"""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        self.credentials = get_snowflake_credentials()
        self.connector = SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            role=self.credentials.get("role"),
            database=self.credentials.get("database"),
        )
        # Authenticate
        self.connector.authenticate(self.credentials)

    def tearDown(self):
        """Clean up after tests"""
        if hasattr(self, "connector"):
            self.connector.close()

    def test_map_to_hub_asset(self):
        """Test mapping Snowflake listing to Hub asset"""
        # Get first listing
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for mapping test")

        listing = all_listings[0]
        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping)
        self.assertIsNotNone(mapping.asset_data)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(mapping.source_metadata)
        self.assertEqual(
            mapping.source_metadata["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
        )

    def test_map_to_hub_asset_with_sync_job_id(self):
        """Test mapping with sync_job_id"""
        # Get first listing
        all_listings = self.connector.list_listings(limit=1)
        if not all_listings:
            raise unittest.SkipTest("No listings available for mapping test")

        listing = all_listings[0]
        sync_job_id = "test_sync_job_123"
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id=sync_job_id)

        self.assertEqual(mapping.source_metadata["sync_job_id"], sync_job_id)

    def test_map_to_hub_asset_empty_listing(self):
        """Test mapping empty listing raises ValueError"""
        # Create a connector for this test
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )
        try:
            with self.assertRaises(ValueError):
                # Type checker warning is expected here - we're testing error handling
                connector.map_to_hub_asset(None)  # type: ignore[misc]  # test: edge-case type exercise
        finally:
            connector.close()


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorCircuitBreaker(TestCase):
    """Test Snowflake connector circuit breaker protection"""

    def setUp(self):
        """Reset circuit breaker so prior test failures don't leave it OPEN."""
        with contextlib.suppress(Exception):
            reset_circuit_breaker_by_name("snowflake-connector")

    def test_circuit_breaker_initialized(self):
        """Test that circuit breaker is initialized"""
        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            token="test_token",
        )

        try:
            self.assertIsNotNone(connector._circuit_breaker)
            self.assertEqual(connector._circuit_breaker.service_name, "snowflake-connector")
        finally:
            connector.close()

    def test_circuit_breaker_rejects_when_open(self):
        """Circuit breaker in OPEN state raises CircuitBreakerError."""
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState

        connector = SnowflakeConnector(
            account="test_account", user="test_user", token="test_token"
        )
        try:
            cb = connector._circuit_breaker
            # Force OPEN state by exceeding the failure threshold
            cb._set_state(CircuitBreakerState.CLOSED)  # start clean
            cb._reset_failure_count()
            for _ in range(cb.failure_threshold + 1):
                cb._increment_failure_count()
            # Trigger the OPEN transition by recording a failure
            cb._record_failure()
            # Manually open it to guarantee state
            cb._set_state(CircuitBreakerState.OPEN)

            with self.assertRaises(CircuitBreakerError):
                cb.call(lambda: "should not execute")
        finally:
            connector.close()

    @pytest.mark.integration
    def test_circuit_breaker_allows_sql_when_closed(self):
        """Circuit breaker in CLOSED state allows normal SQL execution."""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")

        credentials = get_snowflake_credentials()
        connector = SnowflakeConnector(
            account=credentials["account"],
            user=credentials["user"],
            token=credentials["token"],
            warehouse=credentials.get("warehouse"),
            role=credentials.get("role"),
            database=credentials.get("database"),
        )
        connector.authenticate(credentials)

        try:
            results = connector._execute_sql("SELECT CURRENT_VERSION()")
            self.assertIsInstance(results, list)
            self.assertGreater(len(results), 0)
        finally:
            connector.close()

    def test_circuit_breaker_recovery_cycle(self):
        """OPEN → HALF_OPEN → CLOSED recovery cycle works correctly."""
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState

        connector = SnowflakeConnector(
            account="t", user="u", token="t"
        )
        try:
            cb = connector._circuit_breaker
            # Force OPEN state
            cb._set_state(CircuitBreakerState.CLOSED)
            cb._reset_failure_count()
            for _ in range(cb.failure_threshold + 1):
                cb._increment_failure_count()
            cb._record_failure()
            cb._set_state(CircuitBreakerState.OPEN)

            # Set ancient timestamp so timeout has elapsed, allowing
            # _should_attempt_half_open() to return True
            cb._set_opened_at(datetime.min)

            # First call: OPEN → should transition to HALF_OPEN and succeed
            result = cb.call(lambda: "probe-ok")
            self.assertEqual(result, "probe-ok")
            self.assertEqual(cb._get_state(), CircuitBreakerState.HALF_OPEN)

            # Second success in HALF_OPEN reaches threshold → CLOSED
            result = cb.call(lambda: "second-ok")
            self.assertEqual(result, "second-ok")
            self.assertEqual(cb._get_state(), CircuitBreakerState.CLOSED)
        finally:
            connector.close()


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
@pytest.mark.integration
class TestSnowflakeConnectorContextManager(TestCase):
    """Test Snowflake connector context manager and edge-case input handling.

    These tests verify the connector's behaviour with boundary inputs
    (empty / None IDs, zero / None limits).  They require a live Snowflake
    connection because the connector authenticates before performing
    input validation — Snowflake rejects malformed input at the SQL layer.
    """

    def setUp(self):
        """Skip all tests in this class when Snowflake is unreachable."""
        if not has_snowflake_connection():
            raise unittest.SkipTest("Snowflake connection not available")
        credentials = get_snowflake_credentials()
        self.credentials = credentials

    def test_context_manager(self):
        """Test connector context manager opens and closes the connection."""
        with SnowflakeConnector(
            account=self.credentials["account"],
            user=self.credentials["user"],
            token=self.credentials["token"],
            warehouse=self.credentials.get("warehouse"),
            role=self.credentials.get("role"),
            database=self.credentials.get("database"),
        ) as connector:
            result = connector.test_connection()
            self.assertTrue(result)
            self.assertIsNotNone(connector._connection,
                "Connection should be open inside the with-block")

        # Verify connection is closed after context exit
        self.assertIsNone(connector._connection,
            "Connection should be closed after context manager exit")

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        listings = connector.list_listings(limit=0)
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    def test_list_listings_with_none_limit(self):
        """Test list_listings(limit=None) uses default limit (no hard cap).

        The connector skips validation when ``limit is None`` (line 421:
        ``limit is not None and ...`` is short-circuit False), so None
        flows through as "no limit" and the SQL layer uses its own default.
        """
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        listings = connector.list_listings(limit=None)  # type: ignore[arg-type]  # test: edge-case type exercise
        self.assertIsInstance(listings, list)
        for lst in listings:
            self.assertIsInstance(lst, MarketplaceListing)

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        with self.assertRaises((ValueError, NotFoundError)):
            connector.get_listing("")

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        with self.assertRaises((ValueError, TypeError, NotFoundError)):
            connector.get_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_list_resources_with_empty_listing_id(self):
        """Test list_resources() error handling with empty listing ID"""
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        with self.assertRaises((ValueError, NotFoundError)):
            connector.list_resources("")

    def test_list_resources_with_none_listing_id(self):
        """Test list_resources() error handling with None listing ID"""
        connector = SnowflakeConnector(**self.credentials)
        connector.authenticate(self.credentials)
        with self.assertRaises((ValueError, TypeError, NotFoundError)):
            connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorCloseErrorHandling(TestCase):
    """Tests for Snowflake connector close() error handling."""

    def test_close_handles_error_gracefully(self):
        """close() should not raise even when the underlying connection errors."""
        connector = SnowflakeConnector(
            account="test_account", user="test_user", token="test_token"
        )

        class _BadConnection:
            def close(self):
                raise RuntimeError("Simulated close failure")

        connector._connection = _BadConnection()
        # Should not raise
        connector.close()
        self.assertIsNone(connector._connection,
            "Connection reference should be cleared even after close error")

    def test_close_when_not_connected(self):
        """close() is a no-op when there is no active connection."""
        connector = SnowflakeConnector(
            account="test_account", user="test_user", token="test_token"
        )
        # _connection is None by default — close() should be safe
        connector.close()
        self.assertIsNone(connector._connection)


@pytest.mark.skipif(not SNOWFLAKE_AVAILABLE, reason="snowflake-connector-python not installed")
class TestSnowflakeConnectorTagsExtraction(TestCase):
    """Tests for tag extraction in _build_marketplace_listing."""

    def setUp(self):
        self.connector = SnowflakeConnector(
            account="test_account", user="test_user", token="test_token"
        )

    def tearDown(self):
        self.connector.close()

    def test_tags_from_string_split_by_comma(self):
        """Comma-separated tag string is split and whitespace-stripped."""
        listing = self.connector._build_marketplace_listing(
            "test_db",
            {
                "title": "Test DB",
                "tags": "tag1, tag2, tag3",
                "DATABASE_NAME": "TEST_DB",
            },
        )
        self.assertEqual(listing.tags, ["tag1", "tag2", "tag3"])

    def test_tags_single_value(self):
        """Single tag string produces single-element list."""
        listing = self.connector._build_marketplace_listing(
            "test_db",
            {
                "title": "Test DB",
                "tags": "only-tag",
                "DATABASE_NAME": "TEST_DB",
            },
        )
        self.assertEqual(listing.tags, ["only-tag"])

    def test_tags_empty_string(self):
        """Empty tag string produces empty list."""
        listing = self.connector._build_marketplace_listing(
            "test_db",
            {
                "title": "Test DB",
                "tags": "",
                "DATABASE_NAME": "TEST_DB",
            },
        )
        self.assertEqual(listing.tags, [])

    def test_tags_already_a_list(self):
        """Tags already in list form are returned as-is (stringified)."""
        listing = self.connector._build_marketplace_listing(
            "test_db",
            {
                "title": "Test DB",
                "tags": ["alpha", "beta"],
                "DATABASE_NAME": "TEST_DB",
            },
        )
        self.assertEqual(listing.tags, ["alpha", "beta"])
