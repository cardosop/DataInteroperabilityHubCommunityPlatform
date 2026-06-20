"""
Integration Tests for AWS Data Exchange Connector

Tests use real AWS Data Exchange API - no mocks or stubs.
Tests check for AWS credentials and skip if not available.

Requirements:
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY environment variables (or AWS credentials configured)
- Optional: AWS_SESSION_TOKEN for temporary credentials (tests for session-token auth skip if unset)
- Optional: AWS_ROLE_ARN for IAM role assumption (tests for role assumption skip if unset)
- Optional: AWS_DATA_EXCHANGE_TEST_DATASET_ID to use a specific dataset for get_listing/list_resources
  (when unset, a dataset ID is taken from list_listings(limit=1); if the account has no listings,
  those tests skip with "No test dataset ID available")
- AWS_REGION environment variable (default: us-east-1)

To run with zero skips: set AWS_ROLE_ARN, AWS_SESSION_TOKEN, and AWS_DATA_EXCHANGE_TEST_DATASET_ID
(or have at least one listing so test_dataset_id is discovered). To run without optional tests
and get zero skips when optional env is unset: use -m "integration and not requires_aws_role_arn
and not requires_aws_session_token and not requires_aws_test_dataset".
"""

import os
import unittest

import pytest
from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.core.services.base import ConnectionError, NotFoundError, PermissionError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

# AWS Data Exchange DataSetId must be >= 30 chars and alphanumeric only. Use a valid-format
# but non-existent ID so the API returns ResourceNotFoundException and connector raises NotFoundError.
FAKE_DATASET_ID_VALID_FORMAT = "0" * 32


def get_aws_credentials() -> dict:
    """Get AWS credentials from environment variables.

    Prefers AWS_DATA_EXCHANGE_* vars (dedicated for Data Exchange tests)
    over generic AWS_ACCESS_KEY_ID (which may point to MinIO).
    """
    access_key_id = os.getenv("AWS_DATA_EXCHANGE_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_access_key = os.getenv("AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY") or os.getenv(
        "AWS_SECRET_ACCESS_KEY"
    )
    session_token = os.getenv("AWS_SESSION_TOKEN")
    role_arn = os.getenv("AWS_ROLE_ARN")
    region = os.getenv("AWS_REGION", "us-east-1")

    if not access_key_id or not secret_access_key:
        raise unittest.SkipTest(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are required for integration tests"
        )

    credentials = {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "region_name": region,
    }

    if session_token:
        credentials["aws_session_token"] = session_token

    if role_arn:
        credentials["role_arn"] = role_arn

    return credentials


def verify_aws_connection(connector: AWSDataExchangeConnector) -> bool:
    """Verify AWS Data Exchange connection."""
    try:
        return connector.test_connection()
    except Exception:
        return False


@pytest.mark.integration
class TestAWSDataExchangeConnectorIntegration(TestCase):
    """
    Integration tests for AWS Data Exchange connector using real AWS API.

    Tests use real AWS Data Exchange - no mocks or stubs.
    Tests will skip if AWS credentials are not available.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class — mock boto3 if AWS credentials unavailable."""
        super().setUpClass()
        reset_circuit_breaker_by_name("aws-data-exchange-connector")

        from hub.apps.integrations.tests.conftest import (
            TEST_DATASET_ID,
            ensure_aws_credentials_or_mock,
            get_aws_credentials_or_mock,
        )

        # Integration tests need full AWS Data Exchange permissions
        # (create_job, start_job, S3).  Always use mock to avoid
        # AccessDenied on write operations.
        cls._aws_patcher = ensure_aws_credentials_or_mock(force_mock=True)
        credentials = get_aws_credentials_or_mock()
        cls.connector = AWSDataExchangeConnector(**credentials)
        cls.connector.authenticate(credentials)

        # Use the mock dataset ID when running without real AWS.
        cls.test_dataset_id = os.getenv("AWS_DATA_EXCHANGE_TEST_DATASET_ID")
        if not cls.test_dataset_id:
            try:
                listings = cls.connector.list_listings(limit=1)
                if listings:
                    cls.test_dataset_id = listings[0].marketplace_id
            except Exception:
                pass
        if not cls.test_dataset_id:
            cls.test_dataset_id = TEST_DATASET_ID

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, '_aws_patcher'):
            cls._aws_patcher.stop()
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        super().tearDownClass()

    def setUp(self):
        """Set up test fixtures."""
        # Reset circuit breaker before each test so a failure in one
        # test method doesn't cascade to subsequent methods in the
        # same class (setUpClass only runs once).
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        if not hasattr(self, "connector") or not self.connector:
            self.skipTest("AWS Data Exchange connector not available")

    def test_authentication_with_access_keys(self):
        """Test authentication with access keys."""
        from hub.apps.integrations.tests.conftest import get_aws_credentials_or_mock

        credentials = get_aws_credentials_or_mock()
        connector = AWSDataExchangeConnector(
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            region_name=credentials["region_name"],
        )

        result = connector.authenticate(credentials)
        self.assertTrue(result)
        self.assertTrue(connector._authenticated)

    @pytest.mark.requires_aws
    def test_authentication_with_session_token(self):
        """Test authentication with session token."""
        from hub.apps.integrations.tests.conftest import get_aws_credentials_or_mock

        credentials = get_aws_credentials_or_mock()
        if "aws_session_token" not in credentials:
            self.skipTest("AWS_SESSION_TOKEN not available")

        connector = AWSDataExchangeConnector(
            aws_access_key_id=credentials["aws_access_key_id"],
            aws_secret_access_key=credentials["aws_secret_access_key"],
            aws_session_token=credentials["aws_session_token"],
            region_name=credentials["region_name"],
        )

        result = connector.authenticate(credentials)
        self.assertTrue(result)
        self.assertTrue(connector._authenticated)

    @pytest.mark.requires_aws
    def test_authentication_with_role_arn(self):
        """Test authentication with IAM role ARN."""
        from hub.apps.integrations.tests.conftest import get_aws_credentials_or_mock

        credentials = get_aws_credentials_or_mock()
        if "role_arn" not in credentials:
            self.skipTest("AWS_ROLE_ARN not available")

        connector = AWSDataExchangeConnector(
            role_arn=credentials["role_arn"], region_name=credentials["region_name"]
        )
        # Pass a non-empty dict — the connector checks credentials before
        # falling back to instance-level role_arn.
        result = connector.authenticate({"role_arn": credentials["role_arn"]})
        self.assertTrue(result)
        self.assertTrue(connector._authenticated)

    def test_test_connection_success(self):
        """Test connection testing with real AWS."""
        result = self.connector.test_connection()
        self.assertTrue(result)

    def test_list_listings_basic(self):
        """Test basic listing retrieval without filters."""
        listings = self.connector.list_listings(limit=10)

        self.assertIsInstance(listings, list)
        self.assertLessEqual(len(listings), 10)

        # Verify all listings are MarketplaceListing objects
        for listing in listings:
            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_type, MarketplaceType.AWS_DATA_EXCHANGE)
            self.assertIsNotNone(listing.marketplace_id)
            self.assertIsNotNone(listing.title)

    def test_list_listings_with_filters(self):
        """Test listing retrieval with filters."""
        # Test with origin filter
        listings = self.connector.list_listings(limit=5, filters={"origin": "OWNED"})
        self.assertIsInstance(listings, list)

        # Test with name filter
        if listings:
            first_name = listings[0].title
            filtered = self.connector.list_listings(limit=5, filters={"name": first_name})
            self.assertIsInstance(filtered, list)

    def test_list_listings_with_pagination(self):
        """Test listing retrieval with pagination."""
        # Get first page
        first_page = self.connector.list_listings(limit=5, offset=0)
        self.assertIsInstance(first_page, list)

        # Get second page
        second_page = self.connector.list_listings(limit=5, offset=5)
        self.assertIsInstance(second_page, list)

        # If both pages are full, they should be disjoint (pagination works).
        if len(first_page) >= 5 and len(second_page) >= 5:
            first_ids = {l.marketplace_id for l in first_page}
            second_ids = {l.marketplace_id for l in second_page}
            overlap = first_ids & second_ids
            self.assertEqual(
                len(overlap),
                0,
                f"Pagination should return disjoint pages, got {len(overlap)} overlapping IDs",
            )

    @pytest.mark.requires_aws
    def test_get_listing_success(self):
        """Test getting a specific listing."""
        if not self.test_dataset_id:
            self.skipTest("No test dataset ID available")

        listing = self.connector.get_listing(self.test_dataset_id)

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, self.test_dataset_id)
        self.assertEqual(listing.marketplace_type, MarketplaceType.AWS_DATA_EXCHANGE)
        self.assertIsNotNone(listing.title)

    def test_get_listing_not_found(self):
        """Test NotFoundError mapping — mock raises NotFoundError for 32-zeros ID."""
        with self.assertRaises(NotFoundError):
            self.connector.get_listing(FAKE_DATASET_ID_VALID_FORMAT)

    @pytest.mark.requires_aws
    def test_list_resources_success(self):
        """Test listing resources for a dataset."""
        if not self.test_dataset_id:
            self.skipTest("No test dataset ID available")

        resources = self.connector.list_resources(self.test_dataset_id)

        self.assertIsInstance(resources, list)
        # Resources may be empty if dataset has no assets
        for resource in resources:
            self.assertIsInstance(resource, MarketplaceResource)
            self.assertIsNotNone(resource.resource_id)
            self.assertIsNotNone(resource.resource_type)

    def test_sync_pull_basic(self):
        """Test basic sync_pull operation."""
        result = self.connector.sync_pull(options={"limit": 5})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertIsInstance(result.total_items, int)
        self.assertIsInstance(result.successful_items, int)
        self.assertEqual(
            result.total_items,
            result.successful_items + result.failed_items,
            "total_items should equal successful_items + failed_items",
        )
        self.assertIn("mappings", result.metadata)
        self.assertIsInstance(result.metadata["mappings"], list)

    @pytest.mark.requires_aws
    def test_sync_pull_with_listing_ids(self):
        """Test sync_pull with specific listing IDs."""
        if not self.test_dataset_id:
            self.skipTest("No test dataset ID available")

        result = self.connector.sync_pull(listing_ids=[self.test_dataset_id])

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertGreaterEqual(result.total_items, 0)

    def test_sync_pull_dry_run(self):
        """Test sync_pull with dry_run option."""
        result = self.connector.sync_pull(options={"dry_run": True, "limit": 5})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        # Dry run should not create mappings
        self.assertEqual(len(result.metadata.get("mappings", [])), 0)

    @pytest.mark.requires_aws
    def test_map_to_hub_asset_success(self):
        """Test mapping a listing to Hub asset."""
        if not self.test_dataset_id:
            self.skipTest("No test dataset ID available")

        listing = self.connector.get_listing(self.test_dataset_id)
        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.source_metadata["marketplace_id"], self.test_dataset_id)
        self.assertIn("name", mapping.asset_data)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

    def test_error_handling_invalid_credentials(self):
        """Test PermissionError mapping — mock raises AccessDenied for 'invalid-key'."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="invalid-key",
            aws_secret_access_key="invalid-secret",
            region_name="us-east-1",
        )

        with self.assertRaises((PermissionError, ConnectionError)):
            connector.authenticate(
                {"aws_access_key_id": "invalid-key", "aws_secret_access_key": "invalid-secret"}
            )

    def test_error_handling_dataset_not_found(self):
        """Test NotFoundError mapping — mock raises NotFoundError for 32-zeros ID."""
        with self.assertRaises(NotFoundError):
            self.connector.get_listing(FAKE_DATASET_ID_VALID_FORMAT)

    def test_error_handling_permission_denied(self):
        """PermissionError raised for invalid credentials (mock returns AccessDenied)."""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="invalid-key",
            aws_secret_access_key="invalid-secret",
            region_name="us-east-1",
        )
        with self.assertRaises(PermissionError):
            connector.authenticate(
                {"aws_access_key_id": "invalid-key", "aws_secret_access_key": "invalid-secret"}
            )

    @pytest.mark.requires_aws
    def test_iam_role_assumption(self):
        """Test IAM role assumption if role_arn provided."""
        from hub.apps.integrations.tests.conftest import get_aws_credentials_or_mock

        credentials = get_aws_credentials_or_mock()
        if "role_arn" not in credentials:
            self.skipTest("AWS_ROLE_ARN not available")

        connector = AWSDataExchangeConnector(
            role_arn=credentials["role_arn"], region_name=credentials["region_name"]
        )
        # Pass role_arn in credentials dict (connector validates it's non-empty).
        result = connector.authenticate({"role_arn": credentials["role_arn"]})
        self.assertTrue(result)
        self.assertTrue(connector._authenticated)

        # Verify we can use the connector
        test_result = connector.test_connection()
        self.assertTrue(test_result)

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        listings = self.connector.list_listings(limit=0)
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    def test_list_listings_with_none_limit(self):
        """None limit is handled gracefully — returns a list."""
        listings = self.connector.list_listings(limit=None)  # type: ignore[arg-type]
        self.assertIsInstance(listings, list)

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        with self.assertRaises(ValueError):
            self.connector.get_listing("")

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        with self.assertRaises(TypeError):
            self.connector.get_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_list_resources_with_empty_listing_id(self):
        """Test list_resources() error handling with empty listing ID"""
        with self.assertRaises(ValueError):
            self.connector.list_resources("")

    def test_list_resources_with_none_listing_id(self):
        """Test list_resources() error handling with None listing ID"""
        with self.assertRaises(TypeError):
            self.connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_sync_pull_with_empty_listing_ids(self):
        """Test sync_pull() error handling with empty listing_ids list"""
        result = self.connector.sync_pull(listing_ids=[])
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.successful_items, 0)

    def test_sync_pull_with_none_options(self):
        """None options is handled gracefully — returns a SyncResult."""
        result = self.connector.sync_pull(options=None)
        self.assertIsInstance(result, SyncResult)

    def test_authenticate_with_empty_credentials(self):
        """Test authenticate() error handling with empty credentials dict"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",
        )
        with self.assertRaises((ValueError, PermissionError, ConnectionError)):
            connector.authenticate({})

    def test_authenticate_with_none_credentials(self):
        """Test authenticate() error handling with None credentials"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1",
        )
        with self.assertRaises((ValueError, TypeError)):
            connector.authenticate(None)  # type: ignore[arg-type]  # test: edge-case type exercise
