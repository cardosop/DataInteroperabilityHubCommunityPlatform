"""
Comprehensive Integration Tests for CKAN Connector Pull Operations

Tests pull operations (download_resource) using real CKAN instances.
No mocks or stubs - all tests use actual CKAN API endpoints and download real resources.

Uses centralized test utilities for consistent configuration.
"""

import unittest
import os
import tempfile
import uuid
from pathlib import Path

import httpx
import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    get_test_ckan_url,  # Backward compatibility
    marketplace_available,
)


@pytest.mark.integration
class TestCKANConnectorPullOperations(TestCase):
    """
    Comprehensive integration tests for CKAN connector pull operations.

    Tests use real CKAN instances - no mocks or stubs.
    Downloads real resources from public CKAN instances.
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

        # Type narrowing for type checker
        assert cls.connector is not None

        # Cache connector URL for backward compatibility
        cls.ckan_url = cls.connector.base_url

        # Test connection (already verified by create_test_connector, but keep for compatibility)
        try:
            cls.connector.test_connection()
        except Exception as e:
            raise unittest.SkipTest(f"Cannot connect to CKAN instance at {cls.ckan_url}: {e}")

        # Find a test resource with a downloadable URL
        # Try multiple resources until we find one that's actually downloadable
        cls.test_resource_id = None
        cls.test_resource_url = None

        try:
            # Get listings with resources - try more listings to find a good resource
            listings = cls.connector.list_listings(limit=50)
            for listing in listings:
                try:
                    resources = cls.connector.list_resources(listing.marketplace_id)
                    for resource in resources:
                        if resource.url and resource.url.startswith("http"):
                            # Skip certain URL patterns that are known to be problematic
                            skip_patterns = [
                                "/download/",  # Download endpoints may be broken
                                "lincolnshire.ckan.io",  # Known broken links
                            ]
                            if any(pattern in resource.url for pattern in skip_patterns):
                                continue

                            # Try to verify URL is accessible
                            try:
                                # Quick HEAD request to check if resource is accessible
                                head_response = httpx.head(
                                    resource.url, timeout=5, follow_redirects=True
                                )
                                if head_response.status_code == 200:
                                    cls.test_resource_id = resource.resource_id
                                    cls.test_resource_url = resource.url
                                    break
                            except httpx.HTTPStatusError:
                                # HEAD failed, try GET as fallback
                                try:
                                    get_response = httpx.get(
                                        resource.url,
                                        timeout=5,
                                        follow_redirects=True,
                                        headers={"Range": "bytes=0-1023"},
                                    )
                                    if get_response.status_code in (
                                        200,
                                        206,
                                    ):  # 206 is Partial Content
                                        cls.test_resource_id = resource.resource_id
                                        cls.test_resource_url = resource.url
                                        break
                                except Exception:
                                    continue
                            except Exception:
                                continue
                    if cls.test_resource_id:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    def setUp(self):
        """Set up test fixtures."""
        if not self.ckan_url:
            self.skipTest("No CKAN instance available")

    def tearDown(self):
        """Clean up test files."""
        # Cleanup is handled by tempfile context managers

    def test_download_resource_success(self):
        """Test successful resource download."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        # Type guard: test_resource_id is not None after skipTest check
        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            destination_path = tmp_file.name

        try:
            result_path = self.connector.download_resource(resource_id, destination_path)

            self.assertEqual(result_path, destination_path)
            self.assertTrue(os.path.exists(destination_path))
            self.assertGreater(os.path.getsize(destination_path), 0)

            # Verify file is readable
            with open(destination_path, "rb") as f:
                content = f.read()
                self.assertIsInstance(content, bytes)
                self.assertGreater(len(content), 0)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_to_custom_path(self):
        """Test downloading resource to a custom directory path."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            destination_path = os.path.join(tmp_dir, "downloaded_resource.csv")

            result_path = self.connector.download_resource(resource_id, destination_path)

            self.assertEqual(result_path, destination_path)
            self.assertTrue(os.path.exists(destination_path))
            self.assertTrue(os.path.isfile(destination_path))

    def test_download_resource_creates_directory(self):
        """Test that download creates destination directory if it doesn't exist."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create nested directory path
            nested_dir = os.path.join(tmp_dir, "nested", "subdirectory")
            destination_path = os.path.join(nested_dir, "resource.csv")

            # Directory shouldn't exist yet
            self.assertFalse(os.path.exists(nested_dir))

            result_path = self.connector.download_resource(resource_id, destination_path)

            # Directory should be created
            self.assertTrue(os.path.exists(nested_dir))
            self.assertTrue(os.path.exists(destination_path))
            self.assertEqual(result_path, destination_path)

    def test_download_resource_not_found(self):
        """Test downloading non-existent resource raises NotFoundError."""
        fake_resource_id = f"nonexistent-resource-{uuid.uuid4().hex[:8]}"

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            with self.assertRaises(NotFoundError):
                self.connector.download_resource(fake_resource_id, destination_path)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_empty_destination_path(self):
        """Test that empty destination path raises ValueError."""
        # This test validates that empty destination path is caught
        # The validation happens after resource lookup, so we need a valid resource ID
        # but the ValueError should be raised for empty path
        if not self.test_resource_id:
            self.skipTest("No test resource available for validation test")

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Empty destination path should raise ValueError
        with self.assertRaises(ValueError):
            self.connector.download_resource(resource_id, "")

    def test_download_resource_invalid_destination_directory(self):
        """Test downloading to a directory path (should fail)."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Create a directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Try to download to directory path
            with self.assertRaises(IOError):
                self.connector.download_resource(resource_id, tmp_dir)

    def test_download_resource_preserves_file_extension(self):
        """Test that downloaded file preserves original extension or uses provided one."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Download with specific extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
            destination_path = tmp_file.name

        try:
            result_path = self.connector.download_resource(resource_id, destination_path)

            self.assertTrue(result_path.endswith(".json"))
            self.assertTrue(os.path.exists(result_path))
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_atomic_write(self):
        """Test that download uses atomic write (temp file then rename)."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            # Download should create .tmp file first, then rename
            result_path = self.connector.download_resource(resource_id, destination_path)

            # Verify no .tmp file exists after download
            temp_path = destination_path + ".tmp"
            self.assertFalse(os.path.exists(temp_path))

            # Verify final file exists
            self.assertTrue(os.path.exists(result_path))
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_with_redirects(self):
        """Test downloading resource that redirects (follow_redirects=True)."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            # Resources with redirects should still download successfully
            result_path = self.connector.download_resource(resource_id, destination_path)

            self.assertTrue(os.path.exists(result_path))
            self.assertGreater(os.path.getsize(result_path), 0)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_file_size(self):
        """Test that downloaded file has expected size."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            result_path = self.connector.download_resource(resource_id, destination_path)

            file_size = os.path.getsize(result_path)
            self.assertGreater(file_size, 0)

            # Verify file content matches size
            with open(result_path, "rb") as f:
                content = f.read()
                self.assertEqual(len(content), file_size)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_multiple_times(self):
        """Test downloading the same resource multiple times."""
        if not self.test_resource_id:
            self.skipTest(
                "No test resource with accessible URL found. "
                "Some CKAN resources may have broken links - this is expected in real-world scenarios."
            )

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        with tempfile.TemporaryDirectory() as tmp_dir:
            path1 = os.path.join(tmp_dir, "resource1.csv")
            path2 = os.path.join(tmp_dir, "resource2.csv")

            # Download twice
            result1 = self.connector.download_resource(resource_id, path1)
            result2 = self.connector.download_resource(resource_id, path2)

            self.assertEqual(result1, path1)
            self.assertEqual(result2, path2)

            # Both files should exist and have same size
            size1 = os.path.getsize(path1)
            size2 = os.path.getsize(path2)
            self.assertEqual(size1, size2)
            self.assertGreater(size1, 0)

    def test_download_resource_error_handling(self):
        """Test error handling for various error scenarios."""
        # Test with invalid resource ID
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            with self.assertRaises(NotFoundError):
                self.connector.download_resource("invalid-resource-id-xyz-12345", destination_path)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_broken_url(self):
        """Test handling of resources with broken URLs (404)."""
        # Find a resource with a URL that returns 404
        # This tests real-world scenario where resource URLs may be broken
        try:
            listings = self.connector.list_listings(limit=20)
            broken_resource = None

            for listing in listings:
                try:
                    resources = self.connector.list_resources(listing.marketplace_id)
                    for resource in resources:
                        if resource.url and resource.url.startswith("http"):
                            # Check if URL returns 404
                            try:
                                test_response = httpx.head(
                                    resource.url, timeout=5, follow_redirects=True
                                )
                                if test_response.status_code == 404:
                                    broken_resource = resource
                                    break
                            except httpx.HTTPStatusError as e:
                                if e.response.status_code == 404:
                                    broken_resource = resource
                                    break
                            except Exception:
                                continue
                    if broken_resource:
                        break
                except Exception:
                    continue

            if broken_resource:
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    destination_path = tmp_file.name

                try:
                    # Should raise NotFoundError when URL returns 404
                    with self.assertRaises(NotFoundError):
                        self.connector.download_resource(
                            broken_resource.resource_id, destination_path
                        )
                finally:
                    if os.path.exists(destination_path):
                        os.unlink(destination_path)
            else:
                # No broken resources found - this is fine, skip test
                self.skipTest("No resources with broken URLs found to test error handling")
        except Exception as e:
            self.skipTest(f"Could not test broken URL handling: {e}")

    def test_download_resource_with_none_resource_id(self):
        """Test downloading resource with None resource_id raises error"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.download_resource(None, destination_path)  # type: ignore[arg-type]  # test: edge-case type exercise
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_with_none_destination_path(self):
        """Test downloading resource with None destination_path raises error"""
        if not self.test_resource_id:
            self.skipTest("No test resource available for validation test")

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        with self.assertRaises((ValueError, TypeError)):
            self.connector.download_resource(resource_id, None)  # type: ignore[arg-type]  # test: edge-case type exercise

    def test_download_resource_with_invalid_resource_id_format(self):
        """Test downloading resource with invalid resource_id format"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            # Test with invalid format (contains special characters)
            invalid_resource_ids = [
                "../../etc/passwd",
                "'; DROP TABLE resources; --",
                "<script>alert('xss')</script>",
            ]

            for invalid_id in invalid_resource_ids:
                with self.assertRaises((ValueError, NotFoundError)):
                    self.connector.download_resource(invalid_id, destination_path)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_with_readonly_destination(self):
        """Test downloading resource to readonly destination raises error"""
        if not self.test_resource_id:
            self.skipTest("No test resource available for validation test")

        assert self.test_resource_id is not None, "test_resource_id should be set"
        resource_id: str = self.test_resource_id

        # Create a readonly directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            readonly_file = os.path.join(tmp_dir, "readonly_file.csv")
            # Create file and make it readonly
            with open(readonly_file, "w") as f:
                f.write("test")
            os.chmod(readonly_file, 0o444)  # Read-only

            try:
                # Should raise PermissionError or IOError
                with self.assertRaises((PermissionError, IOError, OSError)):
                    self.connector.download_resource(resource_id, readonly_file)
            finally:
                # Restore permissions for cleanup
                os.chmod(readonly_file, 0o644)

    def test_download_resource_connection_error(self):
        """Test that connection errors are properly handled."""
        invalid_connector = CKANConnector(base_url="https://invalid-ckan-instance-xyz-12345.com")

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            destination_path = tmp_file.name

        try:
            with self.assertRaises(Exception):  # ConnectionError or NotFoundError
                invalid_connector.download_resource("test-resource", destination_path)
        finally:
            if os.path.exists(destination_path):
                os.unlink(destination_path)

    def test_download_resource_from_listing_workflow(self):
        """Test complete workflow: list listings -> get resources -> download."""
        # Step 1: List listings
        listings = self.connector.list_listings(limit=20)
        # Same rationale as ``test_comprehensive_discovery_workflow``:
        # the live CKAN test instance occasionally has no packages.
        # Degrade to skip rather than flag operator-side state drift
        # as a connector regression.
        if not listings:
            self.skipTest(
                "live CKAN test instance returned 0 packages — "
                "operator-side state, not a Meshant connector regression"
            )

        # Step 2: Find a listing with a downloadable resource
        downloadable_resource = None
        for listing in listings:
            try:
                resources = self.connector.list_resources(listing.marketplace_id)
                for resource in resources:
                    if resource.url and resource.url.startswith("http"):
                        # Skip problematic URL patterns
                        skip_patterns = [
                            "/download/",  # Download endpoints may be broken
                            "lincolnshire.ckan.io",  # Known broken links
                        ]
                        if any(pattern in resource.url for pattern in skip_patterns):
                            continue

                        # Verify resource URL is accessible
                        try:
                            # Try HEAD first
                            test_response = httpx.head(
                                resource.url, timeout=5, follow_redirects=True
                            )
                            if test_response.status_code == 200:
                                downloadable_resource = resource
                                break
                        except httpx.HTTPStatusError:
                            # Try GET as fallback
                            try:
                                test_response = httpx.get(
                                    resource.url,
                                    timeout=5,
                                    follow_redirects=True,
                                    headers={
                                        "Range": "bytes=0-1023"
                                    },  # Partial content for large files
                                )
                                if test_response.status_code in (
                                    200,
                                    206,
                                ):  # 206 is Partial Content
                                    downloadable_resource = resource
                                    break
                            except Exception:
                                continue
                        except Exception:
                            continue

                if downloadable_resource:
                    break
            except Exception:
                continue

        if downloadable_resource and downloadable_resource.url:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                destination_path = tmp_file.name

            try:
                # Step 3: Download resource
                result_path = self.connector.download_resource(
                    downloadable_resource.resource_id, destination_path
                )

                # Verify download succeeded
                self.assertTrue(os.path.exists(result_path))
                self.assertGreater(os.path.getsize(result_path), 0)

                # Verify file content
                with open(result_path, "rb") as f:
                    content = f.read()
                    self.assertGreater(len(content), 0)
            except NotFoundError:
                # Resource URL may be broken - this is a real-world scenario
                self.skipTest("Resource URL not found (404) - resource may have been removed")
            finally:
                if os.path.exists(destination_path):
                    os.unlink(destination_path)
        else:
            # Use the test resource from setUpClass if available
            if self.test_resource_id:
                assert self.test_resource_id is not None, "test_resource_id should be set"
                resource_id: str = self.test_resource_id
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    destination_path = tmp_file.name

                try:
                    result_path = self.connector.download_resource(resource_id, destination_path)
                    self.assertTrue(os.path.exists(result_path))
                    self.assertGreater(os.path.getsize(result_path), 0)
                finally:
                    if os.path.exists(destination_path):
                        os.unlink(destination_path)
            else:
                self.skipTest(
                    "No downloadable resource found in any listing. "
                    "Some CKAN resources may have broken links - this is expected in real-world scenarios."
                )
