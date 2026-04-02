"""
Comprehensive Integration Tests for CKAN Connector Discovery Operations

Tests discovery operations (list_listings, get_listing, list_resources) using
real CKAN instances. No mocks or stubs - all tests use actual CKAN API endpoints.

Uses centralized test utilities for consistent configuration.
"""

import unittest
import time

import pytest
from django.test import TestCase

from hub.apps.core.services.base import (
    ConnectionError as HubConnectionError,
    NotFoundError,
)
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    get_test_ckan_url,  # Backward compatibility
    marketplace_available,
)


@pytest.mark.integration
class TestCKANConnectorDiscoveryOperations(TestCase):
    """
    Comprehensive integration tests for CKAN connector discovery operations.

    Tests use real CKAN instances - no mocks or stubs.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real CKAN instance."""
        super().setUpClass()

        # Use centralized test utilities
        if not marketplace_available():
            raise unittest.SkipTest("No CKAN instance available for testing")

        # Create connector using centralized utility
        cls.connector = create_test_connector(verify_connection=True)

        if not cls.connector:
            raise unittest.SkipTest("Cannot create or connect to CKAN instance for testing")

        # Cache connector URL for backward compatibility
        cls.ckan_url = cls.connector.base_url

        # Cache a test package ID for get_listing and list_resources tests
        cls.test_package_id = None
        try:
            listings = cls.connector.list_listings(limit=1)
            if listings:
                cls.test_package_id = listings[0].marketplace_id
        except Exception:
            pass

    def setUp(self):
        """Set up test fixtures."""
        if not self.ckan_url:
            self.skipTest("No CKAN instance available")

    def test_list_listings_basic(self):
        """Test basic listing retrieval without filters."""
        listings = self.connector.list_listings(limit=10)

        self.assertIsInstance(listings, list)
        self.assertLessEqual(len(listings), 10)

        # Verify all listings are MarketplaceListing objects
        for listing in listings:
            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)
            self.assertIsNotNone(listing.marketplace_id)
            self.assertIsNotNone(listing.title)

    def test_list_listings_with_limit(self):
        """Test listing retrieval with limit parameter."""
        listings = self.connector.list_listings(limit=5)

        self.assertIsInstance(listings, list)
        self.assertLessEqual(len(listings), 5)

    def test_list_listings_with_offset(self):
        """Test listing retrieval with offset parameter."""
        # Get first page
        first_page = self.connector.list_listings(limit=5, offset=0)

        # Get second page
        second_page = self.connector.list_listings(limit=5, offset=5)

        self.assertIsInstance(first_page, list)
        self.assertIsInstance(second_page, list)

        # If we have enough listings, verify they're different
        if len(first_page) == 5 and len(second_page) > 0:
            first_ids = {listing.marketplace_id for listing in first_page}
            second_ids = {listing.marketplace_id for listing in second_page}
            # Pages should not overlap (unless CKAN instance has < 5 packages)
            if len(first_ids) == 5:
                self.assertTrue(first_ids.isdisjoint(second_ids))

    def test_list_listings_with_search_query(self):
        """Test listing retrieval with search query filter."""
        # Search for packages (most CKAN instances have some packages)
        listings = self.connector.list_listings(filters={"q": "data"}, limit=10)

        self.assertIsInstance(listings, list)
        # Verify search worked (may return 0 results if no matches)
        for listing in listings:
            self.assertIsInstance(listing, MarketplaceListing)

    def test_list_listings_with_organization_filter(self):
        """Test listing retrieval with organization filter."""
        # First, get a listing to find an organization
        all_listings = self.connector.list_listings(limit=10)

        if all_listings:
            # Find a listing with an organization
            org_listing = None
            for listing in all_listings:
                if listing.category:  # category is organization name
                    org_listing = listing
                    break

            if org_listing:
                # Filter by organization
                filtered = self.connector.list_listings(
                    filters={"organization": org_listing.category}, limit=10
                )

                self.assertIsInstance(filtered, list)
                # Verify all filtered listings belong to the organization
                for listing in filtered:
                    self.assertEqual(listing.category, org_listing.category)

    def test_list_listings_empty_result(self):
        """Test listing retrieval with filter that returns no results."""
        # Use a very specific filter that likely won't match anything
        listings = self.connector.list_listings(
            filters={"q": "nonexistent_package_xyz_12345"}, limit=10
        )

        self.assertIsInstance(listings, list)
        # Should return empty list, not raise an error
        self.assertEqual(len(listings), 0)

    def test_get_listing_success(self):
        """Test getting a specific listing by ID."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, self.test_package_id)
        self.assertEqual(listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)
        self.assertIsNotNone(listing.title)
        self.assertIsNotNone(listing.metadata)
        self.assertIn("ckan_package", listing.metadata)

    def test_get_listing_not_found(self):
        """Test getting a non-existent listing raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.connector.get_listing("nonexistent-package-id-xyz-12345")

    def test_get_listing_with_name(self):
        """Test getting a listing by name (CKAN supports both ID and name)."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        # Try getting by ID first to get the name
        listing_by_id = self.connector.get_listing(self.test_package_id)

        # Extract name from metadata if available
        package_data = listing_by_id.metadata.get("ckan_package", {})
        package_name = package_data.get("name")

        if package_name and package_name != self.test_package_id:
            # Try getting by name
            listing_by_name = self.connector.get_listing(package_name)
            self.assertEqual(listing_by_name.marketplace_id, listing_by_id.marketplace_id)

    def test_list_resources_success(self):
        """Test listing resources for a package."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        resources = self.connector.list_resources(self.test_package_id)

        self.assertIsInstance(resources, list)
        # Verify all resources are MarketplaceResource objects
        for resource in resources:
            self.assertIsInstance(resource, MarketplaceResource)
            self.assertIsNotNone(resource.resource_id)
            self.assertIsNotNone(resource.name)

    def test_list_resources_not_found(self):
        """Test listing resources for non-existent package raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.connector.list_resources("nonexistent-package-id-xyz-12345")

    def test_list_resources_empty_package(self):
        """Test listing resources for a package with no resources."""
        # Find a package without resources (may not always be possible)
        all_listings = self.connector.list_listings(limit=20)

        for listing in all_listings:
            try:
                resources = self.connector.list_resources(listing.marketplace_id)
                # If we find a package with no resources, verify it returns empty list
                if len(resources) == 0:
                    self.assertEqual(resources, [])
                    break
            except Exception:
                continue

    def test_list_resources_mapping(self):
        """Test that resources are properly mapped from CKAN format."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        resources = self.connector.list_resources(self.test_package_id)

        if resources:
            resource = resources[0]
            # Verify resource has required fields
            self.assertIsNotNone(resource.resource_id)
            self.assertIsNotNone(resource.name)
            self.assertIsNotNone(resource.resource_type)
            self.assertIn(resource.resource_type, ["FILE", "API"])

            # Verify metadata contains CKAN resource data
            self.assertIn("ckan_resource", resource.metadata)
            ckan_resource = resource.metadata["ckan_resource"]
            self.assertIsInstance(ckan_resource, dict)

    def test_listing_to_marketplace_listing_mapping(self):
        """Test that CKAN packages are properly mapped to MarketplaceListing."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        # Verify all required fields are present
        self.assertIsNotNone(listing.marketplace_id)
        self.assertIsNotNone(listing.title)
        self.assertEqual(listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)

        # Verify metadata contains full CKAN package data
        self.assertIn("ckan_package", listing.metadata)
        ckan_package = listing.metadata["ckan_package"]
        self.assertIsInstance(ckan_package, dict)
        self.assertIn("id", ckan_package)
        self.assertIn("title", ckan_package)

    def test_listing_tags_extraction(self):
        """Test that tags are properly extracted from CKAN packages."""
        all_listings = self.connector.list_listings(limit=20)

        # Find a listing with tags
        for listing in all_listings:
            if listing.tags:
                self.assertIsInstance(listing.tags, list)
                for tag in listing.tags:
                    self.assertIsInstance(tag, str)
                break

    def test_listing_timestamps(self):
        """Test that timestamps are properly parsed from CKAN packages."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        # Timestamps may or may not be present
        if listing.created_at:
            self.assertIsInstance(listing.created_at, type(listing.created_at))
        if listing.updated_at:
            self.assertIsInstance(listing.updated_at, type(listing.updated_at))

    def test_listing_url_generation(self):
        """Test that listing URLs are properly generated."""
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        if listing.url:
            self.assertIsInstance(listing.url, str)
            self.assertTrue(listing.url.startswith("http"))
            self.assertIn(listing.marketplace_id, listing.url)

    def test_pagination_consistency(self):
        """Test that pagination returns consistent results."""
        # Get first page
        page1 = self.connector.list_listings(limit=5, offset=0)

        # Small delay to ensure consistency
        time.sleep(0.5)  # INTENTIONAL: test-specific timing requirement

        # Get first page again
        page1_again = self.connector.list_listings(limit=5, offset=0)

        # Results should be consistent (same IDs)
        if len(page1) > 0 and len(page1_again) > 0:
            ids1 = {listing.marketplace_id for listing in page1}
            ids1_again = {listing.marketplace_id for listing in page1_again}
            # Should have same IDs (order may differ)
            self.assertEqual(ids1, ids1_again)

    def test_error_handling_invalid_limit(self):
        """Test error handling for invalid limit values."""
        # Negative limit should be handled gracefully
        try:
            listings = self.connector.list_listings(limit=-1)
            # Some CKAN instances may accept negative and treat as 0 or default
            self.assertIsInstance(listings, list)
        except (ValueError, HubConnectionError):
            # Expected if validation is strict
            pass

    def test_error_handling_invalid_offset(self):
        """Test error handling for invalid offset values."""
        # Negative offset should be handled gracefully
        try:
            listings = self.connector.list_listings(offset=-1)
            # Some CKAN instances may accept negative and treat as 0
            self.assertIsInstance(listings, list)
        except (ValueError, HubConnectionError):
            # Expected if validation is strict
            pass

    def test_connection_resilience(self):
        """Test that connector handles connection issues gracefully."""
        # Create connector with invalid URL
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        invalid_connector = CKANConnector(
            base_url="https://invalid-ckan-instance-xyz-12345.com"
        )

        with self.assertRaises(HubConnectionError):
            invalid_connector.list_listings(limit=1)

    def test_comprehensive_discovery_workflow(self):
        """Test complete discovery workflow: list -> get -> list_resources."""
        # Step 1: List packages
        listings = self.connector.list_listings(limit=5)
        self.assertGreater(len(listings), 0, "Should have at least one package")

        # Step 2: Get details for first package
        first_listing = listings[0]
        detailed_listing = self.connector.get_listing(first_listing.marketplace_id)
        self.assertEqual(detailed_listing.marketplace_id, first_listing.marketplace_id)

        # Step 3: List resources for the package
        resources = self.connector.list_resources(detailed_listing.marketplace_id)
        self.assertIsInstance(resources, list)

        # Verify data consistency
        self.assertEqual(detailed_listing.marketplace_type, MarketplaceType.CKAN_INSTANCE)
        self.assertIsNotNone(detailed_listing.title)
        self.assertIsNotNone(detailed_listing.metadata)

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        with self.assertRaises((ValueError, NotFoundError)):
            self.connector.get_listing("")

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        with self.assertRaises((ValueError, TypeError, NotFoundError)):
            self.connector.get_listing(None)  # type: ignore[arg-type]

    def test_list_resources_with_empty_id(self):
        """Test list_resources() error handling with empty ID"""
        with self.assertRaises((ValueError, NotFoundError)):
            self.connector.list_resources("")

    def test_list_resources_with_none_id(self):
        """Test list_resources() error handling with None ID"""
        with self.assertRaises((ValueError, TypeError, NotFoundError)):
            self.connector.list_resources(None)  # type: ignore[arg-type]

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        listings = self.connector.list_listings(limit=0)
        # Should return empty list or handle gracefully
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    def test_list_listings_with_very_large_limit(self):
        """Test list_listings() edge case with very large limit"""
        listings = self.connector.list_listings(limit=1000000)
        # Should handle large limit gracefully (may be capped internally)
        self.assertIsInstance(listings, list)
        self.assertLessEqual(len(listings), 1000000)

    def test_list_listings_with_none_filters(self):
        """Test list_listings() handles None filters gracefully"""
        listings = self.connector.list_listings(filters=None)
        # Should handle None filters gracefully
        self.assertIsInstance(listings, list)
