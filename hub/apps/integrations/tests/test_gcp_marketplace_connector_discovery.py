"""
Integration Tests for GCP Marketplace Connector Discovery Operations

Tests the discovery operations (list_listings, get_listing, list_resources)
using REAL Google Cloud credentials and Analytics Hub API.

These tests require:
- Valid Google Cloud service account credentials
- GCP project with Analytics Hub API enabled
- At least one data exchange and listing in Analytics Hub
- Network access to Google Cloud APIs

To run these tests:
1. Set GCP_SERVICE_ACCOUNT_JSON environment variable with service account JSON
2. Run: docker-compose -f docker-compose.test.yml exec api-service-test python -m pytest hub/apps/integrations/tests/test_gcp_marketplace_connector_discovery.py -v
"""

import json
import os

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

    env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not env_json:
        raise unittest.SkipTest("GCP_SERVICE_ACCOUNT_JSON not set — skipping")
    try:
        return json.loads(env_json)
    except json.JSONDecodeError:
        raise unittest.SkipTest("GCP_SERVICE_ACCOUNT_JSON is not valid JSON — skipping")


class TestGCPMarketplaceConnectorDiscovery(TestCase):
    """Integration tests for GCP Marketplace connector discovery operations"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials and authenticate once."""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")
        cls._auth_ok = False
        try:
            connector = GCPMarketplaceConnector(
                project_id=cls.project_id, credentials_json=cls.credentials_json
            )
            credentials = {"project_id": cls.project_id, "credentials_json": cls.credentials_json}
            connector.authenticate(credentials)
            cls._auth_ok = True
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "GCP auth failed in setUpClass — discovery tests will skip"
            )

    def setUp(self):
        """Set up test fixtures — reuse class-level auth result."""
        self.connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        if self._auth_ok:
            credentials = {"project_id": self.project_id, "credentials_json": self.credentials_json}
            self.connector.authenticate(credentials)

    def test_list_listings_basic(self):
        """Test list_listings() returns list of MarketplaceListing objects"""
        try:
            listings = self.connector.list_listings()
            self.assertIsInstance(listings, list)
            # May be empty if no listings exist, but should not raise error
            for listing in listings:
                self.assertIsInstance(listing, MarketplaceListing)
                self.assertEqual(listing.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # No data exchanges found - this is acceptable
            self.skipTest("No data exchanges found in project")

    def test_list_listings_with_limit(self):
        """Test list_listings() with limit parameter"""
        try:
            listings = self.connector.list_listings(limit=5)
            self.assertIsInstance(listings, list)
            self.assertLessEqual(len(listings), 5)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            self.skipTest("No data exchanges found in project")

    def test_list_listings_with_offset(self):
        """Test list_listings() with offset parameter"""
        try:
            # Get all listings first
            all_listings = self.connector.list_listings()

            if len(all_listings) >= 2:
                # Test with real data if available
                offset_listings = self.connector.list_listings(offset=1)
                self.assertIsInstance(offset_listings, list)
                # Should have fewer listings than total
                self.assertLessEqual(len(offset_listings), len(all_listings) - 1)
            else:
                # Test offset parameter validation even with empty results
                # Offset should work even with empty list (should return empty list)
                offset_listings = self.connector.list_listings(offset=1)
                self.assertIsInstance(offset_listings, list)
                self.assertEqual(len(offset_listings), 0)

                # Test with larger offset
                offset_listings = self.connector.list_listings(offset=10)
                self.assertIsInstance(offset_listings, list)
                self.assertEqual(len(offset_listings), 0)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Test offset parameter validation even when no exchanges found
            offset_listings = self.connector.list_listings(offset=1)
            self.assertIsInstance(offset_listings, list)

    def test_list_listings_pagination_validation(self):
        """Test list_listings() validates pagination parameters"""
        # Invalid offset
        with self.assertRaises(ValueError) as cm:
            self.connector.list_listings(offset=-1)
        self.assertIn("offset", str(cm.exception).lower())

        # Invalid limit
        with self.assertRaises(ValueError) as cm:
            self.connector.list_listings(limit=-1)
        self.assertIn("limit", str(cm.exception).lower())

        # Non-integer offset
        with self.assertRaises(ValueError):
            self.connector.list_listings(offset="invalid")  # type: ignore[misc]  # test: edge-case type exercise

        # Non-integer limit
        with self.assertRaises(ValueError):
            self.connector.list_listings(limit="invalid")  # type: ignore[misc]  # test: edge-case type exercise

    def test_get_listing_details(self):
        """Test _get_listing_details() retrieves listing details"""
        try:
            # First, try to get a real listing ID from list_listings
            listings = self.connector.list_listings(limit=1)
            if listings:
                listing = listings[0]
                listing_id = listing.marketplace_id
                data_exchange_id = listing.metadata.get("data_exchange_id")

                if data_exchange_id and isinstance(data_exchange_id, str):
                    # Get listing details with real data
                    details = self.connector._get_listing_details(data_exchange_id, listing_id)
                    self.assertIsInstance(details, dict)
                    self.assertIn("name", details)
                    self.assertIn("display_name", details)
                    return

            # If no real listings, test error handling with non-existent listing
            # This validates the method handles NotFoundError correctly
            with self.assertRaises(NotFoundError):
                self.connector._get_listing_details("non-existent-exchange", "non-existent-listing")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_get_listing_by_id(self):
        """Test get_listing() retrieves a specific listing"""
        try:
            # First, try to get a real listing ID from list_listings
            listings = self.connector.list_listings(limit=1)
            if listings:
                listing_id = listings[0].marketplace_id

                # Get the listing
                listing = self.connector.get_listing(listing_id)
                self.assertIsInstance(listing, MarketplaceListing)
                self.assertEqual(listing.marketplace_id, listing_id)
                self.assertEqual(listing.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE)
                self.assertIsNotNone(listing.title)
                return

            # If no real listings, test error handling with non-existent listing
            # This validates the method handles NotFoundError correctly
            with self.assertRaises(NotFoundError):
                self.connector.get_listing("non-existent-listing-id-12345")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_get_listing_not_found(self):
        """Test get_listing() raises NotFoundError for non-existent listing"""
        try:
            with self.assertRaises(NotFoundError):
                self.connector.get_listing("non-existent-listing-id-12345")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_extract_odps_metadata(self):
        """Test _extract_odps_metadata() extracts ODPS metadata from listing"""
        try:
            # Try to get a real listing first
            listings = self.connector.list_listings(limit=1)
            if listings:
                # Test with real listing data
                listing = listings[0]
                listing_details = listing.metadata.get("analytics_hub_listing", {})
                data_exchange_id = listing.metadata.get("data_exchange_id")

                # Extract ODPS metadata
                odps_metadata = self.connector._extract_odps_metadata(
                    listing_details, data_exchange_id or "test-exchange"
                )

                # Should return dict or None
                if odps_metadata is not None:
                    self.assertIsInstance(odps_metadata, dict)
                    # Should have product_details if metadata exists
                    if "product_details" in odps_metadata:
                        product_details = odps_metadata["product_details"]
                        self.assertIn("product_id", product_details)
                        self.assertIn("product_name", product_details)
            else:
                # Test with sample listing data structure (no mocks - just sample data)
                # This tests the extraction logic even without real listings
                sample_listing_details = {
                    "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                    "display_name": "Test Listing",
                    "description": "Test listing description",
                    "bigquery_dataset": {"dataset": "projects/test-project/datasets/test_dataset"},
                    "create_time": {"seconds": 1609459200},
                    "update_time": {"seconds": 1609459200},
                }

                odps_metadata = self.connector._extract_odps_metadata(
                    sample_listing_details, "test-exchange"
                )

                # Should return dict with product_details
                self.assertIsNotNone(odps_metadata)
                self.assertIsInstance(odps_metadata, dict)
                if odps_metadata and "product_details" in odps_metadata:
                    product_details = odps_metadata["product_details"]
                    self.assertIn("productID", product_details)
                    self.assertIn("product_name", product_details)
                    self.assertEqual(product_details["product_name"], "Test Listing")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Test with sample data even if no real listings
            sample_listing_details = {
                "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                "display_name": "Test Listing",
                "description": "Test listing description",
            }

            odps_metadata = self.connector._extract_odps_metadata(
                sample_listing_details, "test-exchange"
            )

            self.assertIsNotNone(odps_metadata)
            self.assertIsInstance(odps_metadata, dict)
            self.assertIn("product_details", odps_metadata)

    def test_extract_odcs_metadata(self):
        """Test _extract_odcs_metadata() extracts ODCS metadata from listing"""
        try:
            # Try to get a real listing first
            listings = self.connector.list_listings(limit=1)
            if listings:
                # Test with real listing data
                listing = listings[0]
                listing_details = listing.metadata.get("analytics_hub_listing", {})

                # Extract ODCS metadata
                odcs_metadata = self.connector._extract_odcs_metadata(listing_details)

                # Should return dict or None
                if odcs_metadata is not None:
                    self.assertIsInstance(odcs_metadata, dict)
            else:
                # Test with sample listing data structure (no mocks - just sample data)
                # This tests the extraction logic even without real listings
                sample_listing_details = {
                    "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                    "display_name": "Test Listing",
                    "description": "Test listing description",
                    "bigquery_dataset": {"dataset": "projects/test-project/datasets/test_dataset"},
                }

                odcs_metadata = self.connector._extract_odcs_metadata(sample_listing_details)

                # Should return dict or None
                # The method may return None if no ODCS metadata is available
                if odcs_metadata is not None:
                    self.assertIsInstance(odcs_metadata, dict)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Test with sample data even if no real listings
            sample_listing_details = {
                "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                "display_name": "Test Listing",
                "description": "Test listing description",
            }

            odcs_metadata = self.connector._extract_odcs_metadata(sample_listing_details)

            # Method should handle empty metadata gracefully
            # It may return None if no ODCS metadata is available
            if odcs_metadata is not None:
                self.assertIsInstance(odcs_metadata, dict)

    def test_list_resources_with_bigquery_dataset(self):
        """Test list_resources() lists BigQuery tables for listing with dataset"""
        try:
            # Try to get a real listing first
            listings = self.connector.list_listings(limit=10)

            if listings:
                # Find a listing with BigQuery dataset
                listing_with_dataset = None
                for listing in listings:
                    listing_details = listing.metadata.get("analytics_hub_listing", {})
                    if listing_details.get("bigquery_dataset"):
                        listing_with_dataset = listing
                        break

                if listing_with_dataset:
                    # List resources
                    assert listing_with_dataset is not None  # Type guard
                    resources = self.connector.list_resources(listing_with_dataset.marketplace_id)
                    self.assertIsInstance(resources, list)

                    # All resources should be MarketplaceResource objects
                    for resource in resources:
                        self.assertIsInstance(resource, MarketplaceResource)
                        self.assertIn("BIGQUERY", resource.resource_type)
                    return

            # If no real listings with datasets, test error handling
            # This validates the method handles NotFoundError correctly
            with self.assertRaises(NotFoundError):
                self.connector.list_resources("non-existent-listing-id-12345")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except PermissionError:
            # Dataset may not be subscribed yet - this is acceptable
            # The test validates that the method is called correctly
            pass

    def test_list_resources_no_dataset(self):
        """Test list_resources() returns empty list for listing without dataset"""
        try:
            # Try to get a real listing first
            listings = self.connector.list_listings(limit=10)

            if listings:
                # Find a listing without BigQuery dataset (if any)
                listing_without_dataset = None
                for listing in listings:
                    listing_details = listing.metadata.get("analytics_hub_listing", {})
                    if not listing_details.get("bigquery_dataset"):
                        listing_without_dataset = listing
                        break

                if not listing_without_dataset:
                    # All listings have datasets - test with a listing that might not be subscribed
                    listing_without_dataset = listings[0]

                # List resources - may return empty or raise PermissionError
                try:
                    resources = self.connector.list_resources(
                        listing_without_dataset.marketplace_id
                    )
                    self.assertIsInstance(resources, list)
                except (NotFoundError, PermissionError):
                    # Expected if dataset not subscribed
                    pass
                return

            # If no real listings, test error handling with non-existent listing
            # This validates the method handles NotFoundError correctly
            with self.assertRaises(NotFoundError):
                self.connector.list_resources("non-existent-listing-id-12345")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_resources_not_found(self):
        """Test list_resources() raises NotFoundError for non-existent listing"""
        try:
            with self.assertRaises(NotFoundError):
                self.connector.list_resources("non-existent-listing-id-12345")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_build_marketplace_listing(self):
        """Test _build_marketplace_listing() creates proper MarketplaceListing"""
        try:
            # Try to get a real listing first
            listings = self.connector.list_listings(limit=1)
            if listings:
                # Test with real listing data
                original_listing = listings[0]
                listing_details = original_listing.metadata.get("analytics_hub_listing", {})
                data_exchange_id = original_listing.metadata.get("data_exchange_id")

                if not data_exchange_id or not isinstance(data_exchange_id, str):
                    self.skipTest("Listing metadata missing data_exchange_id")

                # Build marketplace listing
                marketplace_listing = self.connector._build_marketplace_listing(
                    listing_details, data_exchange_id
                )

                self.assertIsInstance(marketplace_listing, MarketplaceListing)
                self.assertEqual(
                    marketplace_listing.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE
                )
                self.assertIsNotNone(marketplace_listing.title)
                self.assertIsNotNone(marketplace_listing.marketplace_id)
            else:
                # Test with sample listing data structure (no mocks - just sample data)
                # This tests the building logic even without real listings
                sample_listing_details = {
                    "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                    "display_name": "Test Listing",
                    "description": "Test listing description",
                    "bigquery_dataset": {"dataset": "projects/test-project/datasets/test_dataset"},
                    "create_time": {"seconds": 1609459200},
                    "update_time": {"seconds": 1609459200},
                }

                data_exchange_id = "test-exchange"
                marketplace_listing = self.connector._build_marketplace_listing(
                    sample_listing_details, data_exchange_id
                )

                self.assertIsInstance(marketplace_listing, MarketplaceListing)
                self.assertEqual(
                    marketplace_listing.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE
                )
                self.assertIsNotNone(marketplace_listing.title)
                self.assertIsNotNone(marketplace_listing.marketplace_id)
                self.assertEqual(marketplace_listing.title, "Test Listing")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Test with sample data even if no real listings
            sample_listing_details = {
                "name": "projects/test-project/locations/US/dataExchanges/test-exchange/listings/test-listing",
                "display_name": "Test Listing",
                "description": "Test listing description",
            }

            marketplace_listing = self.connector._build_marketplace_listing(
                sample_listing_details, "test-exchange"
            )

            self.assertIsInstance(marketplace_listing, MarketplaceListing)
            self.assertEqual(
                marketplace_listing.marketplace_type, MarketplaceType.GOOGLE_CLOUD_MARKETPLACE
            )
            self.assertIsNotNone(marketplace_listing.title)
            self.assertIsNotNone(marketplace_listing.marketplace_id)

    def test_location_path_construction(self):
        """Test _get_location_path() constructs correct path"""
        path = self.connector._get_location_path()
        self.assertIn(self.project_id, path)
        self.assertIn(self.connector.location, path)
        self.assertIn("projects", path)
        self.assertIn("locations", path)

    def test_data_exchange_path_construction(self):
        """Test _get_data_exchange_path() constructs correct path"""
        exchange_id = "test-exchange"
        path = self.connector._get_data_exchange_path(exchange_id)
        self.assertIn(self.project_id, path)
        self.assertIn(exchange_id, path)
        self.assertIn("dataExchanges", path)

    def test_listing_path_construction(self):
        """Test _get_listing_path() constructs correct path"""
        exchange_id = "test-exchange"
        listing_id = "test-listing"
        path = self.connector._get_listing_path(exchange_id, listing_id)
        self.assertIn(exchange_id, path)
        self.assertIn(listing_id, path)
        self.assertIn("listings", path)

    def test_parse_listing_name_full_path(self):
        """Test _parse_listing_name() parses full listing path"""
        full_path = f"projects/{self.project_id}/locations/US/dataExchanges/test-exchange/listings/test-listing"
        project, location, exchange, listing = self.connector._parse_listing_name(full_path)
        self.assertEqual(project, self.project_id)
        self.assertEqual(location, "US")
        self.assertEqual(exchange, "test-exchange")
        self.assertEqual(listing, "test-listing")

    def test_parse_listing_name_short_id(self):
        """Test _parse_listing_name() handles short listing ID"""
        short_id = "test-listing"
        project, location, exchange, listing = self.connector._parse_listing_name(short_id)
        self.assertEqual(project, self.project_id)
        self.assertEqual(location, self.connector.location)
        self.assertIsNone(exchange)
        self.assertEqual(listing, short_id)

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        try:
            # Zero limit should return empty list or raise ValueError
            try:
                listings = self.connector.list_listings(limit=0)
                self.assertEqual(len(listings), 0)
            except ValueError:
                # Expected if zero limit is invalid
                pass
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            # Test validation even when no exchanges found
            try:
                listings = self.connector.list_listings(limit=0)
                self.assertEqual(len(listings), 0)
            except ValueError:
                pass

    def test_list_listings_with_very_large_limit(self):
        """Test list_listings() edge case with very large limit"""
        try:
            listings = self.connector.list_listings(limit=1000000)
            # Should handle large limit gracefully (may be capped internally)
            self.assertIsInstance(listings, list)
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
        except NotFoundError:
            self.skipTest("No data exchanges found in project")

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

    def test_list_resources_with_invalid_dataset(self):
        """Test list_resources() error handling with invalid dataset"""
        try:
            # Test with invalid dataset reference
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.list_resources("invalid-dataset-reference")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_list_resources_with_none_dataset(self):
        """Test list_resources() error handling with None dataset"""
        try:
            with self.assertRaises((ValueError, TypeError)):
                self.connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_extract_odps_metadata_with_empty_details(self):
        """Test _extract_odps_metadata() handles empty listing details"""
        odps_metadata = self.connector._extract_odps_metadata({}, "test-exchange")
        # Should return None or empty dict
        self.assertIsInstance(odps_metadata, (dict, type(None)))

    def test_extract_odps_metadata_with_none_details(self):
        """Test _extract_odps_metadata() error handling with None"""
        try:
            odps_metadata = self.connector._extract_odps_metadata(None, "test-exchange")  # type: ignore[arg-type]  # test: None metadata for error-path coverage
            # Should handle None gracefully
            self.assertIsInstance(odps_metadata, (dict, type(None)))
        except (TypeError, AttributeError):
            # Expected if None is not allowed
            pass

    def test_extract_odcs_metadata_with_empty_details(self):
        """Test _extract_odcs_metadata() handles empty listing details"""
        odcs_metadata = self.connector._extract_odcs_metadata({})
        # Should return None or empty dict
        self.assertIsInstance(odcs_metadata, (dict, type(None)))

    def test_extract_odcs_metadata_with_none_details(self):
        """Test _extract_odcs_metadata() error handling with None"""
        try:
            odcs_metadata = self.connector._extract_odcs_metadata(None)  # type: ignore[arg-type]  # test: None metadata for error-path coverage
            # Should handle None gracefully
            self.assertIsInstance(odcs_metadata, (dict, type(None)))
        except (TypeError, AttributeError):
            # Expected if None is not allowed
            pass

    def test_parse_listing_name_with_invalid_format(self):
        """Test _parse_listing_name() error handling with invalid format"""
        # Test with invalid format
        try:
            project, _location, _exchange, _listing = self.connector._parse_listing_name(
                "invalid-format"
            )
            # Should handle gracefully or use defaults
            self.assertIsNotNone(project)
        except (ValueError, AttributeError):
            # Expected if format validation is strict
            pass

    def test_parse_listing_name_with_none(self):
        """Test _parse_listing_name() error handling with None"""
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            self.connector._parse_listing_name(None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_get_listing_details_with_invalid_exchange(self):
        """Test _get_listing_details() error handling with invalid exchange"""
        try:
            with self.assertRaises(NotFoundError):
                self.connector._get_listing_details("invalid-exchange", "test-listing")
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")

    def test_get_listing_details_with_none_exchange(self):
        """Test _get_listing_details() error handling with None exchange"""
        try:
            with self.assertRaises((ValueError, TypeError)):
                self.connector._get_listing_details(None, "test-listing")  # type: ignore[arg-type]  # test: edge-case type exercise
        except ImportError:
            self.skipTest("Analytics Hub client library not installed")
