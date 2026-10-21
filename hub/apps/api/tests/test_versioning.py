"""
Unit tests for API Versioning

Tests for version management, backward compatibility, and deprecation warnings.
"""

import pytest
from django.test import RequestFactory, TestCase

from hub.apps.api.versioning import (
    APIVersion,
    APIVersionManager,
    APIVersionMiddleware,
    DeprecatedEndpoint,
)

pytestmark = pytest.mark.django_db(transaction=True)


class APIVersionTest(TestCase):
    """Test APIVersion class"""

    def test_version_parsing(self):
        """Test version string parsing"""
        v1 = APIVersion.parse("v1")
        self.assertIsNotNone(v1)
        self.assertEqual(v1.major, 1)
        self.assertEqual(v1.minor, 0)
        self.assertEqual(v1.patch, 0)

        v2_0 = APIVersion.parse("v2.0")
        self.assertIsNotNone(v2_0)
        self.assertEqual(v2_0.major, 2)
        self.assertEqual(v2_0.minor, 0)

        v1_0_0 = APIVersion.parse("v1.0.0")
        self.assertIsNotNone(v1_0_0)
        self.assertEqual(v1_0_0.major, 1)
        self.assertEqual(v1_0_0.minor, 0)
        self.assertEqual(v1_0_0.patch, 0)

    def test_version_comparison(self):
        """Test version comparison"""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)

        self.assertLess(v1, v2)
        self.assertGreater(v2, v1)
        self.assertEqual(v1, APIVersion(1, 0, 0))

    def test_version_compatibility(self):
        """Test version compatibility"""
        v1_0 = APIVersion(1, 0, 0)
        v1_1 = APIVersion(1, 1, 0)
        v2_0 = APIVersion(2, 0, 0)

        self.assertTrue(v1_0.is_compatible_with(v1_1))
        self.assertFalse(v1_0.is_compatible_with(v2_0))


class APIVersionManagerTest(TestCase):
    """Test APIVersionManager"""

    def test_get_version_from_path(self):
        """Test extracting version from URL path"""
        version = APIVersionManager.get_version_from_path("/api/v1/assets/")
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)

        version = APIVersionManager.get_version_from_path("/api/v2/contracts/")
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 2)

    def test_get_version_from_header(self):
        """Test extracting version from Accept header"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/", HTTP_ACCEPT="application/vnd.idh.v1+json")

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)

    def test_deprecated_endpoint(self):
        """Test deprecated endpoint registration"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date="2024-07-01",
            replacement="/api/v1/new-endpoint/",
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)
        key = "GET:/api/v1/old-endpoint/"
        self.addCleanup(lambda k=key: APIVersionManager.DEPRECATED_ENDPOINTS.pop(k, None))

        retrieved = APIVersionManager.get_deprecated_endpoint("/api/v1/old-endpoint/", "GET")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.path, endpoint.path)


class APIVersionMiddlewareTest(TestCase):
    """Test APIVersionMiddleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = APIVersionMiddleware(lambda request: None)

    def test_version_header_added(self):
        """Test that version header is added to response"""
        from django.http import HttpResponse

        request = self.factory.get("/api/v1/assets/")
        # Root cause fix: Must call process_request first to extract and store version
        self.middleware.process_request(request)
        # Now process_response with HttpResponse
        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Version header should be added
        self.assertIn("X-API-Version", response.headers)
        self.assertIn("X-API-Supported-Versions", response.headers)

        # Version should be extracted and stored (from process_request)
        self.assertIsNotNone(getattr(request, "api_version", None))
