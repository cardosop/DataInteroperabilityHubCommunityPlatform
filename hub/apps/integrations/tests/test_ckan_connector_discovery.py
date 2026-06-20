"""
Comprehensive Integration Tests for CKAN Connector Discovery Operations

Tests discovery operations (list_listings, get_listing, list_resources) using
real CKAN instances. No mocks or stubs - all tests use actual CKAN API endpoints.

Uses centralized test utilities for consistent configuration.
"""

import logging
import time
import unittest
import uuid
from datetime import datetime

import httpx
import pytest
from django.test import TestCase

from hub.apps.core.services.base import (
    ConnectionError as HubConnectionError,
)
from hub.apps.core.services.base import (
    NotFoundError,
)
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    marketplace_available,
)


@pytest.mark.integration
class TestCKANConnectorDiscoveryOperations(TestCase):
    """
    Comprehensive integration tests for CKAN connector discovery operations.

    Tests use real CKAN instances - no mocks or stubs.
    """

    # Names/IDs of packages created on the CKAN instance during setUpClass
    # so tearDownClass can clean them up.  Stored as a list of package names.
    _seeded_package_names: list[str] = []
    _seeded_tagged_package_name: str | None = None
    _seeded_empty_package_name: str | None = None

    @classmethod
    def setUpClass(cls):
        """Set up test class with real CKAN instance.

        Creates two test fixtures on the CKAN instance when write access
        (API key) is available:

        * A package with tags — so ``test_listing_tags_extraction`` has
          guaranteed data to verify tag structure.
        * A package with zero resources — so ``test_list_resources_empty_package``
          can verify that the empty-resource path returns ``[]``.

        Both are removed in ``tearDownClass``.  If the API key is unavailable
        the fixtures are skipped and the dependent tests fall back to their
        existing search-based approach (which may skip when the CKAN instance
        has no matching data).
        """
        # Check skip conditions BEFORE super().setUpClass() so that if we
        # raise SkipTest, no class-level atomics are opened and the PG
        # connection is not left in a stale transaction for the next class.
        if not marketplace_available():
            raise unittest.SkipTest("No CKAN instance available for testing")

        super().setUpClass()

        # Wrap post-super code in try/except with explicit atomics rollback,
        # following Django's own pattern for setUpTestData().  If any
        # exception (including SkipTest) is raised after atomics are opened,
        # tearDownClass is never called — we must roll back atomics here.
        try:
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
            except (HubConnectionError, ValueError) as e:
                # CKAN instance unreachable or returned malformed response —
                # leave test_package_id as None so dependent tests will skip.
                logger = logging.getLogger(__name__)
                logger.debug(
                    "Could not fetch initial listing for test fixture: %s", e
                )

            # --- Seed test data on the CKAN instance ---
            cls._seed_ckan_test_fixtures()
        except Exception:
            cls._rollback_atomics(cls.cls_atomics)
            raise

    @classmethod
    def tearDownClass(cls):
        """Clean up packages created on the CKAN instance during setUpClass."""
        cls._remove_ckan_test_fixtures()
        super().tearDownClass()

    @classmethod
    def _seed_ckan_test_fixtures(cls):
        """Create tagged + empty packages on the CKAN instance for the
        data-dependent tests, when the connector has a write-capable API key."""
        cls._seeded_package_names = []
        cls._seeded_tagged_package_name = None
        cls._seeded_empty_package_name = None

        api_key = getattr(cls.connector, "api_key", None)
        if not api_key:
            return  # read-only access — tests will use search-based fallback

        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        base = cls.connector.base_url
        suffix = uuid.uuid4().hex[:8]
        logger = logging.getLogger(__name__)

        # 1. Package with tags
        tagged_name = f"hub-test-tagged-{suffix}"
        try:
            resp = httpx.post(
                f"{base}/api/3/action/package_create",
                json={
                    "name": tagged_name,
                    "title": f"Hub Test Tagged Package {suffix}",
                    "owner_org": "meshant-test-org",
                    "tags": [
                        {"name": "hub-test-tag-alpha"},
                        {"name": "hub-test-tag-beta"},
                    ],
                    "notes": "Auto-created by hub integration test — has tags.",
                },
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                cls._seeded_tagged_package_name = tagged_name
                cls._seeded_package_names.append(tagged_name)
                logger.debug("Seeded tagged CKAN package: %s", tagged_name)
            else:
                logger.debug(
                    "Could not seed tagged CKAN package (%s): %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.debug("Could not seed tagged CKAN package: %s", e)

        # 2. Empty package (no resources)
        empty_name = f"hub-test-empty-{suffix}"
        try:
            resp = httpx.post(
                f"{base}/api/3/action/package_create",
                json={
                    "name": empty_name,
                    "title": f"Hub Test Empty Package {suffix}",
                    "owner_org": "meshant-test-org",
                    "notes": "Auto-created by hub integration test — zero resources.",
                },
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200 and resp.json().get("success"):
                cls._seeded_empty_package_name = empty_name
                cls._seeded_package_names.append(empty_name)
                logger.debug("Seeded empty CKAN package: %s", empty_name)
            else:
                logger.debug(
                    "Could not seed empty CKAN package (%s): %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.debug("Could not seed empty CKAN package: %s", e)

    @classmethod
    def _remove_ckan_test_fixtures(cls):
        """Delete the packages created by ``_seed_ckan_test_fixtures``."""
        if not cls._seeded_package_names:
            return

        api_key = getattr(cls.connector, "api_key", None)
        if not api_key:
            return

        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        base = cls.connector.base_url
        logger = logging.getLogger(__name__)

        for pkg_name in cls._seeded_package_names:
            try:
                resp = httpx.post(
                    f"{base}/api/3/action/package_delete",
                    json={"id": pkg_name},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 200 and resp.json().get("success"):
                    logger.debug("Removed seeded CKAN package: %s", pkg_name)
                else:
                    logger.debug(
                        "Could not remove seeded CKAN package %s (%s): %s",
                        pkg_name,
                        resp.status_code,
                        resp.text[:200],
                    )
            except (httpx.HTTPError, OSError, ValueError) as e:
                logger.debug("Could not remove seeded CKAN package %s: %s", pkg_name, e)

        cls._seeded_package_names = []
        cls._seeded_tagged_package_name = None
        cls._seeded_empty_package_name = None

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
        """Test listing retrieval with filter that returns no results.

        Uses ``fq=name:`` (filter query on the exact package-name field)
        rather than the full-text ``q`` parameter.  CKAN / Solr does
        partial matching on ``q`` which can produce false-positive hits
        on unrelated packages as the instance grows.
        """
        ghost_term = f"zzz-no-match-{uuid.uuid4().hex}"
        listings = self.connector.list_listings(
            filters={"fq": f"name:{ghost_term}"}, limit=10
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
        """Test that a package with no resources returns an empty list.

        Uses the empty package created in ``setUpClass`` when write access is
        available; otherwise searches the CKAN instance for a suitable package."""
        empty_name = type(self)._seeded_empty_package_name
        if empty_name is not None:
            # Use the fixture we created in setUpClass — guaranteed empty.
            resources = self.connector.list_resources(empty_name)
            self.assertEqual(resources, [], "Seeded empty package should return empty list")
            return

        # Fallback: search the CKAN instance for an empty package.
        all_listings = self.connector.list_listings(limit=20)

        empty_package_found = False
        for listing in all_listings:
            try:
                resources = self.connector.list_resources(listing.marketplace_id)
                if len(resources) == 0:
                    empty_package_found = True
                    self.assertEqual(resources, [], "Empty package should return empty list")
                    break
            except (httpx.HTTPStatusError, httpx.RequestError, HubConnectionError):
                continue  # Transient CKAN errors — skip this listing

        if not empty_package_found:
            self.skipTest(
                "No empty packages found in CKAN instance — "
                "cannot verify empty-package resource behavior"
            )

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
            self.assertIn(resource.resource_type, ["FILE", "API", "DATABASE"])

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
        """Test that tags are properly extracted from CKAN packages.

        Uses the tagged package created in ``setUpClass`` when write access is
        available; otherwise searches the CKAN instance for a suitable package."""
        tagged_name = type(self)._seeded_tagged_package_name
        if tagged_name is not None:
            # Use the fixture we created in setUpClass — guaranteed to have tags.
            listing = self.connector.get_listing(tagged_name)
            self.assertIsInstance(listing, MarketplaceListing)
            self.assertIsInstance(
                listing.tags, list,
                f"Tags should be a list, got {type(listing.tags)}"
            )
            self.assertGreater(len(listing.tags), 0,
                "Seeded tagged package should have at least one tag")
            for tag in listing.tags:
                self.assertIsInstance(
                    tag, str,
                    f"Each tag should be a string, got {type(tag)}: {tag!r}"
                )
            return

        # Fallback: search the CKAN instance for a listing with tags.
        all_listings = self.connector.list_listings(limit=20)

        # Find a listing with tags and verify tag structure
        tag_found = False
        for listing in all_listings:
            if listing.tags:
                tag_found = True
                self.assertIsInstance(
                    listing.tags, list,
                    f"Tags should be a list, got {type(listing.tags)}"
                )
                for tag in listing.tags:
                    self.assertIsInstance(
                        tag, str,
                        f"Each tag should be a string, got {type(tag)}: {tag!r}"
                    )
                break

        if not tag_found:
            self.skipTest(
                "No listings with tags found in CKAN instance — "
                "cannot verify tag extraction structure"
            )

    def test_listing_timestamps(self):
        """Test that timestamps are properly parsed from CKAN packages.

        Timestamps come from ``metadata_created`` / ``metadata_modified``
        in the CKAN package (source: ckan_connector.py lines 497-506).
        They should be timezone-aware datetime objects.
        """
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        if listing.created_at is not None:
            self.assertIsInstance(
                listing.created_at, datetime,
                f"created_at should be a datetime, got {type(listing.created_at)}"
            )
        if listing.updated_at is not None:
            self.assertIsInstance(
                listing.updated_at, datetime,
                f"updated_at should be a datetime, got {type(listing.updated_at)}"
            )

    def test_listing_url_generation(self):
        """Test that listing URLs are properly generated.

        Source ckan_connector.py line 508-511 constructs urls from
        base_url + dataset/{package_id}, so URL should always be non-None.
        """
        if not self.test_package_id:
            self.skipTest("No test package available")

        listing = self.connector.get_listing(self.test_package_id)

        self.assertIsNotNone(
            listing.url,
            f"Listing URL should not be None for package {self.test_package_id}"
        )
        assert listing.url is not None  # type narrow for type checker
        self.assertIsInstance(listing.url, str)
        self.assertTrue(
            listing.url.startswith("http"),
            f"URL should start with http, got: {listing.url!r}"
        )
        self.assertIn(
            listing.marketplace_id, listing.url,
            f"URL should contain marketplace_id '{listing.marketplace_id}', got: {listing.url!r}"
        )

    def test_pagination_consistency(self):
        """Test that pagination returns consistent results."""
        # Get first page
        page1 = self.connector.list_listings(limit=5, offset=0)

        # Small delay to ensure consistency
        time.sleep(0.5)  # noqa: sleep-needed  # INTENTIONAL: test-specific timing requirement

        # Get first page again
        page1_again = self.connector.list_listings(limit=5, offset=0)

        # Results should be consistent (same IDs)
        if len(page1) > 0 and len(page1_again) > 0:
            ids1 = {listing.marketplace_id for listing in page1}
            ids1_again = {listing.marketplace_id for listing in page1_again}
            # Should have same IDs (order may differ)
            self.assertEqual(ids1, ids1_again)

    def test_error_handling_invalid_limit(self):
        """Test connector behavior with negative limit.

        The CKANConnector passes negative limit through to CKAN as rows=-1
        (_list_listings_via_search, line 389: ``limit or 100``).
        Different CKAN versions handle this differently — some reject with
        an HTTP error, others treat as 0 and return empty results.
        The connector should handle either outcome without crashing.
        """
        handled = False
        try:
            listings = self.connector.list_listings(limit=-1)
            self.assertIsInstance(listings, list)
            if len(listings) > 0:
                for lst in listings[:5]:
                    self.assertIsInstance(lst, MarketplaceListing)
            handled = True
        except HubConnectionError:
            handled = True
        except Exception as e:
            self.fail(
                f"Unexpected exception for negative limit: "
                f"{type(e).__name__}: {e}"
            )
        self.assertTrue(handled, "Should get result or HubConnectionError")

    def test_error_handling_invalid_offset(self):
        """Test connector behavior with negative offset.

        Same rationale as test_error_handling_invalid_limit — negative
        offset is passed through to CKAN, behavior varies by CKAN version.
        """
        handled = False
        try:
            listings = self.connector.list_listings(offset=-1)
            self.assertIsInstance(listings, list)
            if len(listings) > 0:
                for lst in listings[:5]:
                    self.assertIsInstance(lst, MarketplaceListing)
            handled = True
        except HubConnectionError:
            handled = True
        except Exception as e:
            self.fail(
                f"Unexpected exception for negative offset: "
                f"{type(e).__name__}: {e}"
            )
        self.assertTrue(handled, "Should get result or HubConnectionError")

    def test_connection_resilience(self):
        """Test that connector handles connection issues gracefully."""
        # Create connector with invalid URL
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector

        invalid_connector = CKANConnector(base_url="https://invalid-ckan-instance-xyz-12345.com")

        with self.assertRaises(HubConnectionError):
            invalid_connector.list_listings(limit=1)

    def test_comprehensive_discovery_workflow(self):
        """Test complete discovery workflow: list -> get -> list_resources."""
        # Step 1: List packages
        listings = self.connector.list_listings(limit=5)
        # The test CKAN instance is externally hosted and operators
        # occasionally clear/rotate its package catalogue. An empty
        # response is operationally indistinguishable from "harness
        # is up but the instance has no listings yet" — degrade to
        # a skip so we don't flag external-state drift as a Meshant
        # regression. The list-listings invariant (returns ``list``)
        # is already pinned by ``test_list_listings_basic``.
        if not listings:
            self.skipTest(
                "live CKAN test instance returned 0 packages — "
                "operator-side state, not a Meshant connector regression"
            )

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
        """get_listing('') raises ValueError (source line 454)."""
        with self.assertRaises(ValueError):
            self.connector.get_listing("")

    def test_get_listing_with_none_id(self):
        """get_listing(None) raises ValueError (source line 452)."""
        with self.assertRaises(ValueError):
            self.connector.get_listing(None)  # type: ignore[arg-type]

    def test_list_resources_with_empty_id(self):
        """list_resources('') raises ValueError (via get_listing validation)."""
        with self.assertRaises(ValueError):
            self.connector.list_resources("")

    def test_list_resources_with_none_id(self):
        """list_resources(None) raises ValueError (via get_listing validation)."""
        with self.assertRaises(ValueError):
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
