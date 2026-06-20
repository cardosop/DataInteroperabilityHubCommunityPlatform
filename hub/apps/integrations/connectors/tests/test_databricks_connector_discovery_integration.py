"""
Integration tests for Databricks connector discovery operations.

Tests list_listings, get_listing, and list_resources with real Databricks API.
No mocks or stubs - uses real Unity Catalog API endpoints.
"""

import os
import unittest

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


@pytest.mark.integration
class TestDatabricksConnectorDiscoveryIntegration(TestCase):
    """
    Integration tests for Databricks connector discovery operations.

    Tests use real Databricks Unity Catalog API endpoints - no mocks or stubs.
    Requires DATABRICKS_HOST and DATABRICKS_TOKEN environment variables.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real Databricks connector."""
        # Check credentials BEFORE super().setUpClass() to avoid
        # _fixture_teardown() closing connections on the skip path.
        cls.host = os.getenv("DATABRICKS_HOST")
        cls.token = os.getenv("DATABRICKS_TOKEN")

        if not cls.host or not cls.token:
            raise unittest.SkipTest(
                "DATABRICKS_HOST and DATABRICKS_TOKEN not set - skipping integration tests"
            )

        super().setUpClass()

        # Create connector
        assert cls.host is not None
        assert cls.token is not None
        cls.connector = DatabricksConnector(host=cls.host, token=cls.token)

    def setUp(self):
        """Set up test fixtures"""
        if not self.host or not self.token:
            self.skipTest(
                "DATABRICKS_HOST and DATABRICKS_TOKEN not set - skipping integration tests"
            )

    def test_list_listings_basic(self):
        """Test list_listings with real Databricks Unity Catalog"""
        try:
            listings = self.connector.list_listings(limit=10)

            self.assertIsInstance(listings, list)
            # Note: Workspace may have no shares, which is valid
            for listing in listings:
                self.assertIsInstance(listing, MarketplaceListing)
                self.assertEqual(listing.marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)
                self.assertIsNotNone(listing.marketplace_id)
                self.assertIsNotNone(listing.title)
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"list_listings failed: {e}")

    def test_list_listings_with_limit(self):
        """Test list_listings with limit parameter"""
        try:
            listings = self.connector.list_listings(limit=5)

            self.assertIsInstance(listings, list)
            self.assertLessEqual(len(listings), 5)
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"list_listings failed: {e}")

    def test_list_listings_with_offset(self):
        """Test list_listings with offset parameter"""
        try:
            # Get first batch
            listings1 = self.connector.list_listings(limit=5, offset=0)

            # Get second batch
            listings2 = self.connector.list_listings(limit=5, offset=5)

            self.assertIsInstance(listings1, list)
            self.assertIsInstance(listings2, list)
            # If we have enough listings, verify offset works
            if len(listings1) == 5 and len(listings2) > 0:
                # Verify listings are different (if enough exist)
                ids1 = {l.marketplace_id for l in listings1}
                ids2 = {l.marketplace_id for l in listings2}
                self.assertTrue(ids1.isdisjoint(ids2), "Offset should return different listings")
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"list_listings failed: {e}")

    def test_get_listing_success(self):
        """Test get_listing with real share (if available)"""
        try:
            # First, try to get a listing
            listings = self.connector.list_listings(limit=1)

            if not listings:
                raise unittest.SkipTest("No shares available in workspace for testing get_listing")

            share_name = listings[0].marketplace_id
            listing = self.connector.get_listing(share_name)

            self.assertIsInstance(listing, MarketplaceListing)
            self.assertEqual(listing.marketplace_id, share_name)
            self.assertEqual(listing.marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)
            self.assertIsNotNone(listing.title)

            # Verify ODPS metadata if available
            if listing.metadata.get("odps_metadata"):
                odps = listing.metadata["odps_metadata"]
                self.assertIn("access_methods", odps)
                self.assertIn("databricks_delta_sharing", odps["access_methods"])
        except NotFoundError:
            raise unittest.SkipTest("Share not found - may have been deleted")
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"get_listing failed: {e}")

    def test_get_listing_not_found(self):
        """Test get_listing raises NotFoundError for non-existent share"""
        try:
            with self.assertRaises(NotFoundError):
                self.connector.get_listing("non_existent_share_12345")
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"get_listing failed: {e}")

    def test_list_resources_success(self):
        """Test list_resources with real share (if available)"""
        try:
            # First, try to get a listing
            listings = self.connector.list_listings(limit=1)

            if not listings:
                raise unittest.SkipTest(
                    "No shares available in workspace for testing list_resources"
                )

            share_name = listings[0].marketplace_id
            resources = self.connector.list_resources(share_name)

            self.assertIsInstance(resources, list)
            # Resources may be empty if share has no tables
            for resource in resources:
                self.assertIsInstance(resource, MarketplaceResource)
                self.assertEqual(resource.resource_type, "TABLE")
                self.assertIsNotNone(resource.resource_id)
                self.assertIsNotNone(resource.name)
                # Verify resource ID format (catalog.schema.table or schema.table)
                self.assertIn(".", resource.resource_id)
        except NotFoundError:
            raise unittest.SkipTest("Share not found - may have been deleted")
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"list_resources failed: {e}")

    def test_list_resources_not_found(self):
        """Test list_resources raises NotFoundError for non-existent share"""
        try:
            with self.assertRaises(NotFoundError):
                self.connector.list_resources("non_existent_share_12345")
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"list_resources failed: {e}")

    def test_listing_metadata_structure(self):
        """Test that listings have proper metadata structure"""
        try:
            listings = self.connector.list_listings(limit=1)

            if not listings:
                raise unittest.SkipTest(
                    "No shares available in workspace for testing metadata structure"
                )

            listing = listings[0]

            # Verify basic structure
            self.assertIsNotNone(listing.marketplace_id)
            self.assertIsNotNone(listing.title)
            self.assertEqual(listing.marketplace_type, MarketplaceType.DATABRICKS_MARKETPLACE)

            # Verify metadata contains Databricks share data
            self.assertIn("databricks_share", listing.metadata)

            # Verify ODPS metadata structure if available
            if listing.metadata.get("odps_metadata"):
                odps = listing.metadata["odps_metadata"]
                self.assertIn("access_methods", odps)
                self.assertIn("databricks_delta_sharing", odps["access_methods"])

            # Verify ODCS metadata structure if available
            if listing.metadata.get("odcs_metadata"):
                odcs = listing.metadata["odcs_metadata"]
                # ODCS metadata is optional and may contain schema, quality, sla hints
                self.assertIsInstance(odcs, dict)
        except ConnectionError as e:
            error_str = str(e).lower()
            if "authentication failed" in error_str or "unauthorized" in error_str:
                raise unittest.SkipTest(f"Databricks authentication failed: {e}")
            pytest.fail(f"Metadata structure test failed: {e}")
