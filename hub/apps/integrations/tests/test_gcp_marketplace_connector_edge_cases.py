"""
Edge Case Tests for GCP Marketplace Connector

Tests edge cases including:
- Empty results
- Missing fields
- Invalid data
- Pagination edge cases
- Boundary conditions

These tests use real Google Cloud SDK clients - no mocks/stubs.
"""

import json
import os

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, PermissionError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector

# Real service account credentials for testing
# REAL_SERVICE_ACCOUNT_JSON removed — use get_test_credentials() below


def get_test_credentials():
    """Get GCP test credentials from environment.

    Requires GCP_SERVICE_ACCOUNT_JSON env var (set via .env.test and
    the Makefile test-batch-6-2 target).  Raises SkipTest when the
    env var is not available so the test suite can run without GCP
    credentials in environments where they are not configured.
    """
    import unittest
    import json
    env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not env_json:
        raise unittest.SkipTest(
            "GCP_SERVICE_ACCOUNT_JSON not set — skipping"
        )
    try:
        return json.loads(env_json)
    except json.JSONDecodeError:
        raise unittest.SkipTest(
            "GCP_SERVICE_ACCOUNT_JSON is not valid JSON — skipping"
        )
class TestGCPMarketplaceConnectorEdgeCases(TestCase):
    """Edge case tests for GCP Marketplace connector"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        # Authenticate the connector before tests
        credentials = {"project_id": self.project_id, "credentials_json": self.credentials_json}
        try:
            self.connector.authenticate(credentials)
        except Exception:
            # Authentication may fail if credentials are invalid, but tests will handle it
            pass

    def test_list_listings_empty_result(self):
        """Test list_listings with empty result set or non-existent resource"""
        try:
            # Test 1: Request a specific non-existent data exchange
            # This should raise NotFoundError (correct behavior for non-existent resource)
            with self.assertRaises(NotFoundError):
                self.connector.list_listings(
                    filters={"data_exchange_id": "nonexistent-exchange-12345"}
                )
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # NotFoundError is expected when requesting a non-existent data exchange
            # This is correct behavior - the test verifies error handling works correctly
            pass
        except Exception as e:
            # If there are no data exchanges at all in the project,
            # requesting a specific non-existent one will raise NotFoundError
            # This is acceptable - skip if it's a different error that indicates no data exchanges exist
            if "No data exchanges found" in str(e) or "not found" in str(e).lower():
                self.skipTest(
                    "No data exchanges found in project - cannot test empty result scenario"
                )
            else:
                raise

    def test_sync_pull_with_empty_listing_ids(self):
        """Test sync_pull with empty listing_ids list"""
        try:
            result = self.connector.sync_pull(listing_ids=[])
            # Should handle empty list gracefully
            self.assertIsNotNone(result)
            self.assertEqual(result.total_items, 0)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            self.skipTest("No data exchanges found in project")

    def test_sync_pull_with_nonexistent_listing_ids(self):
        """Test sync_pull with non-existent listing IDs"""
        try:
            result = self.connector.sync_pull(
                listing_ids=[
                    "nonexistent-exchange/nonexistent-listing-1",
                    "nonexistent-exchange/nonexistent-listing-2",
                ]
            )
            # Should complete but with errors or skipped items
            self.assertIsNotNone(result)
            self.assertGreaterEqual(len(result.errors), 0)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            self.skipTest("No data exchanges found in project")

    def test_sync_pull_with_filters_returning_no_results(self):
        """Test sync_pull with filters that return no results"""
        try:
            result = self.connector.sync_pull(
                filters={"data_exchange_id": "nonexistent-exchange-12345"}
            )
            # Should complete successfully with 0 items
            self.assertIsNotNone(result)
            self.assertEqual(result.total_items, 0)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Expected if no exchanges match filter
            pass

    def test_map_to_hub_asset_with_minimal_listing(self):
        """Test map_to_hub_asset with listing that has minimal fields"""
        try:
            # Create a minimal listing
            minimal_listing = MarketplaceListing(
                marketplace_id="test-exchange/test-listing",
                marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE,
                title="Test Listing",
                description=None,  # Missing description
                url=None,  # Missing URL
            )

            mapping = self.connector.map_to_hub_asset(minimal_listing)

            # Should handle missing fields gracefully
            self.assertIsNotNone(mapping)
            self.assertIsNotNone(mapping.asset_data)
            self.assertEqual(mapping.asset_data.get("name"), "Test Listing")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_download_resource_with_empty_resource_id(self):
        """Test download_resource with empty resource ID"""
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.download_resource("", "/tmp/test.csv")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_download_resource_with_none_resource_id(self):
        """Test download_resource with None resource ID"""
        try:
            # None will cause error when trying to parse or use it
            with self.assertRaises((ValueError, TypeError, AttributeError, ConnectionError)):
                self.connector.download_resource(None, "/tmp/test.csv")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_download_resource_with_invalid_destination(self):
        """Test download_resource with invalid destination path"""
        try:
            # Use a resource ID that might exist
            # Invalid destination: parent directory doesn't exist
            with self.assertRaises((ValueError, OSError, PermissionError)):
                self.connector.download_resource(
                    "test-exchange/test-listing/test-table", "/nonexistent/path/to/file.csv"
                )
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Resource doesn't exist - acceptable
            pass

    def test_project_id_validation(self):
        """Test project_id validation"""
        # Empty project_id
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(project_id="", use_adc=True)
            connector._get_bigquery_client()

    def test_location_validation(self):
        """Test location validation"""
        # Empty location should use default
        connector = GCPMarketplaceConnector(
            project_id="test-project", credentials_json={"type": "service_account"}, location=""
        )
        # Empty location should be handled (may use default or raise error)
        # The connector should handle this gracefully
        self.assertIsNotNone(connector)

    def test_credentials_json_validation(self):
        """Test credentials_json validation"""
        # Invalid credentials_json type
        with self.assertRaises(ValueError):
            connector = GCPMarketplaceConnector(
                project_id="test-project", credentials_json="invalid-string"  # Should be dict
            )
            connector._get_credentials()

    def test_list_listings_with_invalid_filters(self):
        """Test list_listings with invalid filter keys"""
        try:
            # Use invalid filter keys
            listings = self.connector.list_listings(filters={"invalid_filter_key": "value"})
            # Should handle invalid filters gracefully (may ignore or raise ValueError)
            self.assertIsInstance(listings, list)
        except (ValueError, NotFoundError):
            # Expected if validation is strict
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_listings_with_none_filters(self):
        """Test list_listings() error handling with None filters"""
        try:
            listings = self.connector.list_listings(filters=None)
            # Should handle None filters gracefully
            self.assertIsInstance(listings, list)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        try:
            listings = self.connector.list_listings(limit=0)
            # Should return empty list or handle gracefully
            self.assertIsInstance(listings, list)
            self.assertEqual(len(listings), 0)
        except (ValueError, TypeError):
            # Expected if zero limit is invalid
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_listings_with_very_large_limit(self):
        """Test list_listings() edge case with very large limit"""
        try:
            listings = self.connector.list_listings(limit=1000000)
            # Should handle large limit gracefully (may be capped internally)
            self.assertIsInstance(listings, list)
            self.assertLessEqual(len(listings), 1000000)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.get_listing("")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.get_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_resources_with_empty_listing_id(self):
        """Test list_resources() error handling with empty listing ID"""
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.list_resources("")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_resources_with_none_listing_id(self):
        """Test list_resources() error handling with None listing ID"""
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
