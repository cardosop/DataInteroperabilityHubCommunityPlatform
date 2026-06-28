"""
Comprehensive Unit Tests for API Versioning

Tests for version management, backward compatibility, deprecation warnings, and version negotiation.
Target: 100% coverage
"""

from datetime import timedelta

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from hub.apps.api.versioning import (
    APIVersion,
    APIVersionManager,
    APIVersionMiddleware,
    DeprecatedEndpoint,
)


class APIVersionTest(TestCase):
    """Comprehensive tests for APIVersion class"""

    def test_version_creation(self):
        """Test version creation with major, minor, patch"""
        v1 = APIVersion(1, 0, 0)
        self.assertEqual(v1.major, 1)
        self.assertEqual(v1.minor, 0)
        self.assertEqual(v1.patch, 0)

        v2_1_3 = APIVersion(2, 1, 3)
        self.assertEqual(v2_1_3.major, 2)
        self.assertEqual(v2_1_3.minor, 1)
        self.assertEqual(v2_1_3.patch, 3)

    def test_version_string_representation(self):
        """Test version string representation"""
        v1 = APIVersion(1, 0, 0)
        self.assertEqual(str(v1), "v1.0.0")

        v2 = APIVersion(2, 1, 3)
        self.assertEqual(str(v2), "v2.1.3")

    def test_version_parsing_v1(self):
        """Test parsing version string 'v1'"""
        v1 = APIVersion.parse("v1")
        self.assertIsNotNone(v1)
        self.assertEqual(v1.major, 1)
        self.assertEqual(v1.minor, 0)
        self.assertEqual(v1.patch, 0)

    def test_version_parsing_v1_0(self):
        """Test parsing version string 'v1.0'"""
        v1_0 = APIVersion.parse("v1.0")
        self.assertIsNotNone(v1_0)
        self.assertEqual(v1_0.major, 1)
        self.assertEqual(v1_0.minor, 0)
        self.assertEqual(v1_0.patch, 0)

    def test_version_parsing_v1_0_0(self):
        """Test parsing version string 'v1.0.0'"""
        v1_0_0 = APIVersion.parse("v1.0.0")
        self.assertIsNotNone(v1_0_0)
        self.assertEqual(v1_0_0.major, 1)
        self.assertEqual(v1_0_0.minor, 0)
        self.assertEqual(v1_0_0.patch, 0)

    def test_version_parsing_v2_1_3(self):
        """Test parsing version string 'v2.1.3'"""
        v2_1_3 = APIVersion.parse("v2.1.3")
        self.assertIsNotNone(v2_1_3)
        self.assertEqual(v2_1_3.major, 2)
        self.assertEqual(v2_1_3.minor, 1)
        self.assertEqual(v2_1_3.patch, 3)

    def test_version_parsing_without_v_prefix(self):
        """Test parsing version string without 'v' prefix"""
        v1 = APIVersion.parse("1")
        self.assertIsNotNone(v1)
        self.assertEqual(v1.major, 1)
        self.assertEqual(v1.minor, 0)
        self.assertEqual(v1.patch, 0)

        v2_0 = APIVersion.parse("2.0")
        self.assertIsNotNone(v2_0)
        self.assertEqual(v2_0.major, 2)
        self.assertEqual(v2_0.minor, 0)
        self.assertEqual(v2_0.patch, 0)

    def test_version_parsing_invalid(self):
        """Test parsing invalid version strings"""
        self.assertIsNone(APIVersion.parse("invalid"))
        self.assertIsNone(APIVersion.parse(""))
        self.assertIsNone(APIVersion.parse("v"))
        self.assertIsNone(APIVersion.parse("v."))
        self.assertIsNone(APIVersion.parse("v.a.b"))

    def test_version_equality(self):
        """Test version equality comparison"""
        v1 = APIVersion(1, 0, 0)
        v1_copy = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)

        self.assertEqual(v1, v1_copy)
        self.assertNotEqual(v1, v2)
        self.assertNotEqual(v1, "not a version")

    def test_version_less_than(self):
        """Test version less than comparison"""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)
        v1_1 = APIVersion(1, 1, 0)
        v1_0_1 = APIVersion(1, 0, 1)

        self.assertLess(v1, v2)
        self.assertLess(v1, v1_1)
        self.assertLess(v1, v1_0_1)
        self.assertLess(v1_0_1, v1_1)

    def test_version_less_than_or_equal(self):
        """Test version less than or equal comparison"""
        v1 = APIVersion(1, 0, 0)
        v1_copy = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)

        self.assertLessEqual(v1, v1_copy)
        self.assertLessEqual(v1, v2)

    def test_version_greater_than(self):
        """Test version greater than comparison"""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)
        v1_1 = APIVersion(1, 1, 0)

        self.assertGreater(v2, v1)
        self.assertGreater(v1_1, v1)

    def test_version_greater_than_or_equal(self):
        """Test version greater than or equal comparison"""
        v1 = APIVersion(1, 0, 0)
        v1_copy = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)

        self.assertGreaterEqual(v1, v1_copy)
        self.assertGreaterEqual(v2, v1)

    def test_version_comparison_with_non_version_returns_false(self):
        """Test that comparing with non-APIVersion objects returns False consistently"""
        v1 = APIVersion(1, 0, 0)
        # __eq__ and __lt__ already handle this via isinstance guards;
        # __gt__ and __ge__ must also reject non-APIVersion objects.
        self.assertFalse(v1 > "not a version")
        self.assertFalse(v1 >= "not a version")
        self.assertFalse(v1 > None)
        self.assertFalse(v1 >= None)

    def test_version_compatibility_same_major(self):
        """Test version compatibility with same major version"""
        v1_0 = APIVersion(1, 0, 0)
        v1_1 = APIVersion(1, 1, 0)
        v1_0_1 = APIVersion(1, 0, 1)

        self.assertTrue(v1_0.is_compatible_with(v1_1))
        self.assertTrue(v1_0.is_compatible_with(v1_0_1))
        self.assertTrue(v1_1.is_compatible_with(v1_0))

    def test_version_compatibility_different_major(self):
        """Test version compatibility with different major versions"""
        v1 = APIVersion(1, 0, 0)
        v2 = APIVersion(2, 0, 0)

        self.assertFalse(v1.is_compatible_with(v2))
        self.assertFalse(v2.is_compatible_with(v1))


class DeprecatedEndpointTest(TestCase):
    """Comprehensive tests for DeprecatedEndpoint class"""

    def test_deprecated_endpoint_creation(self):
        """Test deprecated endpoint creation"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date="2024-07-01",
            replacement="/api/v2/new-endpoint/",
            migration_guide="https://docs.example.com/migration",
        )

        self.assertEqual(endpoint.path, "/api/v1/old-endpoint/")
        self.assertEqual(endpoint.method, "GET")
        self.assertEqual(endpoint.deprecated_since, "2024-01-01")
        self.assertEqual(endpoint.sunset_date, "2024-07-01")
        self.assertEqual(endpoint.replacement, "/api/v2/new-endpoint/")
        self.assertEqual(endpoint.migration_guide, "https://docs.example.com/migration")

    def test_deprecated_endpoint_minimal(self):
        """Test deprecated endpoint creation with minimal fields"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/", method="GET", deprecated_since="2024-01-01"
        )

        self.assertEqual(endpoint.path, "/api/v1/old-endpoint/")
        self.assertIsNone(endpoint.sunset_date)
        self.assertIsNone(endpoint.replacement)
        self.assertIsNone(endpoint.migration_guide)

    def test_is_sunset_future_date(self):
        """Test is_sunset with future sunset date"""
        future_date = (timezone.now() + timedelta(days=30)).isoformat()
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=future_date,
        )

        self.assertFalse(endpoint.is_sunset())

    def test_is_sunset_past_date(self):
        """Test is_sunset with past sunset date"""
        past_date = (timezone.now() - timedelta(days=30)).isoformat()
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=past_date,
        )

        self.assertTrue(endpoint.is_sunset())

    def test_is_sunset_no_date(self):
        """Test is_sunset with no sunset date"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/", method="GET", deprecated_since="2024-01-01"
        )

        self.assertFalse(endpoint.is_sunset())

    def test_is_sunset_invalid_date(self):
        """Test is_sunset with invalid date format"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date="invalid-date",
        )

        # Should not raise error, just return False
        self.assertFalse(endpoint.is_sunset())

    def test_get_warning_header_basic(self):
        """Test warning header generation (basic)"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/", method="GET", deprecated_since="2024-01-01"
        )

        warning = endpoint.get_warning_header()
        self.assertIn('299 - "Deprecated API"', warning)

    def test_get_warning_header_with_sunset(self):
        """Test warning header generation with sunset date"""
        sunset_date = "2024-07-01T00:00:00Z"
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=sunset_date,
        )

        warning = endpoint.get_warning_header()
        self.assertIn('299 - "Deprecated API"', warning)
        self.assertIn(f'sunset="{sunset_date}"', warning)

    def test_get_warning_header_with_replacement(self):
        """Test warning header generation with replacement"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            replacement="/api/v2/new-endpoint/",
        )

        warning = endpoint.get_warning_header()
        self.assertIn('299 - "Deprecated API"', warning)
        self.assertIn('link="/api/v2/new-endpoint/"', warning)

    def test_get_warning_header_complete(self):
        """Test warning header generation with all fields"""
        sunset_date = "2024-07-01T00:00:00Z"
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=sunset_date,
            replacement="/api/v2/new-endpoint/",
        )

        warning = endpoint.get_warning_header()
        self.assertIn('299 - "Deprecated API"', warning)
        self.assertIn(f'sunset="{sunset_date}"', warning)
        self.assertIn('link="/api/v2/new-endpoint/"', warning)


class APIVersionManagerTest(TestCase):
    """Comprehensive tests for APIVersionManager"""

    def setUp(self):
        super().setUp()
        # Save and isolate the global deprecated-endpoint registry so
        # test ordering doesn't affect results.
        self._saved_deprecated = dict(APIVersionManager.DEPRECATED_ENDPOINTS)
        APIVersionManager.DEPRECATED_ENDPOINTS = {}

    def tearDown(self):
        APIVersionManager.DEPRECATED_ENDPOINTS = self._saved_deprecated
        super().tearDown()

    def test_get_version_from_path_v1(self):
        """Test extracting version v1 from URL path"""
        version = APIVersionManager.get_version_from_path("/api/v1/assets/")
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_get_version_from_path_v2(self):
        """Test extracting version v2 from URL path"""
        version = APIVersionManager.get_version_from_path("/api/v2/contracts/")
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 2)

    def test_get_version_from_path_v1_0_0(self):
        """Test extracting version v1.0.0 from URL path"""
        version = APIVersionManager.get_version_from_path("/api/v1.0.0/assets/")
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)
        self.assertEqual(version.minor, 0)
        self.assertEqual(version.patch, 0)

    def test_get_version_from_path_no_version(self):
        """Test extracting version from path without version"""
        version = APIVersionManager.get_version_from_path("/assets/")
        self.assertIsNone(version)

    def test_get_version_from_path_invalid(self):
        """Test extracting version from invalid path"""
        version = APIVersionManager.get_version_from_path("/api/invalid/")
        self.assertIsNone(version)

    def test_get_version_from_header_v1(self):
        """Test extracting version v1 from Accept header"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/", HTTP_ACCEPT="application/vnd.idh.v1+json")

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)

    def test_get_version_from_header_v2(self):
        """Test extracting version v2 from Accept header"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/", HTTP_ACCEPT="application/vnd.idh.v2+json")

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 2)

    def test_get_version_from_header_with_quality(self):
        """Test extracting version from Accept header with quality value"""
        factory = RequestFactory()
        request = factory.get(
            "/api/v1/assets/",
            HTTP_ACCEPT="application/vnd.idh.v1+json;q=0.9, application/json;q=0.8",
        )

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNotNone(version)
        self.assertEqual(version.major, 1)

    def test_get_version_from_header_no_version(self):
        """Test extracting version from header without version"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/", HTTP_ACCEPT="application/json")

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNone(version)

    def test_get_version_from_header_empty(self):
        """Test extracting version from empty Accept header"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")

        version = APIVersionManager.get_version_from_header(request)
        self.assertIsNone(version)

    def test_get_request_version_from_path(self):
        """Test getting version from request path"""
        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")

        version = APIVersionManager.get_request_version(request)
        self.assertEqual(version.major, 1)

    def test_get_request_version_from_header(self):
        """Test getting version from request header when path has no version"""
        factory = RequestFactory()
        request = factory.get("/assets/", HTTP_ACCEPT="application/vnd.idh.v1+json")

        version = APIVersionManager.get_request_version(request)
        self.assertEqual(version.major, 1)

    def test_get_request_version_path_priority(self):
        """Test that path version takes priority over header"""
        factory = RequestFactory()
        request = factory.get("/api/v2/assets/", HTTP_ACCEPT="application/vnd.idh.v1+json")

        version = APIVersionManager.get_request_version(request)
        # Path version should be used (v2)
        self.assertEqual(version.major, 2)

    def test_get_request_version_default(self):
        """Test getting default version when no version specified"""
        factory = RequestFactory()
        request = factory.get("/assets/")

        version = APIVersionManager.get_request_version(request)
        self.assertEqual(version, APIVersionManager.CURRENT_VERSION)

    def test_is_version_supported_v1(self):
        """Test checking if v1 is supported"""
        v1 = APIVersion(1, 0, 0)
        self.assertTrue(APIVersionManager.is_version_supported(v1))

    def test_is_version_supported_v2(self):
        """Test checking if v2 is supported (should be False)"""
        v2 = APIVersion(2, 0, 0)
        self.assertFalse(APIVersionManager.is_version_supported(v2))

    def test_register_deprecated_endpoint(self):
        """Test registering deprecated endpoint"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/", method="GET", deprecated_since="2024-01-01"
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)

        retrieved = APIVersionManager.get_deprecated_endpoint("/api/v1/old-endpoint/", "GET")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.path, endpoint.path)

    def test_get_deprecated_endpoint_not_found(self):
        """Test getting non-existent deprecated endpoint"""
        endpoint = APIVersionManager.get_deprecated_endpoint("/api/v1/nonexistent/", "GET")
        self.assertIsNone(endpoint)

    def test_get_deprecated_endpoint_different_method(self):
        """Test getting deprecated endpoint with different method"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/", method="GET", deprecated_since="2024-01-01"
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)

        # Different method should not match
        retrieved = APIVersionManager.get_deprecated_endpoint("/api/v1/old-endpoint/", "POST")
        self.assertIsNone(retrieved)

    def test_add_deprecation_warning_not_deprecated(self):
        """Test adding deprecation warning for non-deprecated endpoint"""
        response = HttpResponse()
        APIVersionManager.add_deprecation_warning(response, "/api/v1/normal-endpoint/", "GET")

        self.assertNotIn("Warning", response)

    def test_add_deprecation_warning_deprecated(self):
        """Test adding deprecation warning for deprecated endpoint"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=(timezone.now() + timedelta(days=30)).isoformat(),
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)

        response = HttpResponse()
        APIVersionManager.add_deprecation_warning(response, "/api/v1/old-endpoint/", "GET")

        self.assertIn("Warning", response)

    def test_add_deprecation_warning_sunset(self):
        """Test that sunset endpoints don't get warning"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=(timezone.now() - timedelta(days=30)).isoformat(),
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)

        response = HttpResponse()
        APIVersionManager.add_deprecation_warning(response, "/api/v1/old-endpoint/", "GET")

        # Sunset endpoints should not get warning
        self.assertNotIn("Warning", response)

    def test_add_deprecation_warning_json_response(self):
        """Test adding deprecation warning to JSON response"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=(timezone.now() + timedelta(days=30)).isoformat(),
            replacement="/api/v2/new-endpoint/",
            migration_guide="https://docs.example.com/migration",
        )

        APIVersionManager.register_deprecated_endpoint(endpoint)

        # Create mock response with data attribute
        class MockResponse:
            def __init__(self):
                self.headers = {}
                self.data = {"result": "data"}

            def __setitem__(self, key, value):
                self.headers[key] = value

        response = MockResponse()
        APIVersionManager.add_deprecation_warning(response, "/api/v1/old-endpoint/", "GET")

        self.assertIn("Warning", response.headers)
        self.assertIn("meta", response.data)
        self.assertTrue(response.data["meta"]["deprecated"])
        self.assertEqual(response.data["meta"]["deprecated_since"], "2024-01-01")
        self.assertIn("replacement", response.data["meta"])
        self.assertIn("migration_guide", response.data["meta"])

    def test_check_backward_compatibility_same_major(self):
        """Test backward compatibility check with same major version"""
        request_version = APIVersion(1, 0, 0)
        endpoint_version = APIVersion(1, 1, 0)

        is_compatible, error = APIVersionManager.check_backward_compatibility(
            request_version, endpoint_version
        )

        self.assertTrue(is_compatible)
        self.assertIsNone(error)

    def test_check_backward_compatibility_different_major(self):
        """Test backward compatibility check with different major versions"""
        request_version = APIVersion(1, 0, 0)
        endpoint_version = APIVersion(2, 0, 0)

        is_compatible, error = APIVersionManager.check_backward_compatibility(
            request_version, endpoint_version
        )

        self.assertFalse(is_compatible)
        self.assertIsNotNone(error)
        self.assertIn("not compatible", error)


class APIVersionMiddlewareTest(TestCase):
    """Comprehensive tests for APIVersionMiddleware"""

    def setUp(self):
        super().setUp()
        # Isolate the global deprecated-endpoint registry.
        self._saved_deprecated = dict(APIVersionManager.DEPRECATED_ENDPOINTS)
        APIVersionManager.DEPRECATED_ENDPOINTS = {}

        self.factory = RequestFactory()

        def mock_get_response(request):
            """Mock get_response function"""
            response = HttpResponse()
            response.status_code = 200
            return response

        self.middleware = APIVersionMiddleware(mock_get_response)

    def test_middleware_non_api_request(self):
        """Test middleware ignores non-API requests"""
        request = self.factory.get("/admin/")
        response = self.middleware.process_request(request)

        # Should return None (no early response)
        self.assertIsNone(response)

    def test_middleware_api_request_supported_version(self):
        """Test middleware processes API request with supported version"""
        request = self.factory.get("/api/v1/assets/")
        response = self.middleware.process_request(request)

        # Should return None (no early response)
        self.assertIsNone(response)
        # Version should be stored in request
        self.assertIsNotNone(getattr(request, "api_version", None))
        self.assertEqual(request.api_version.major, 1)

    def test_middleware_api_request_unsupported_version(self):
        """Test middleware rejects API request with an unsupported version.

        Uses v999 (a version that will practically never be supported) so the
        test survives when v2 is eventually introduced.
        """
        request = self.factory.get("/api/v999/assets/")
        response = self.middleware.process_request(request)

        # Should return error response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 400)

        # Check response content

        content = response.data
        self.assertEqual(content["error"]["code"], "UNSUPPORTED_API_VERSION")
        self.assertIn("supported_versions", content["error"])

    def test_middleware_response_adds_version_header(self):
        """Test middleware adds version header to response"""
        request = self.factory.get("/api/v1/assets/")
        request.api_version = APIVersion(1, 0, 0)

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        self.assertIn("X-API-Version", response)
        self.assertEqual(response["X-API-Version"], "v1.0.0")

    def test_middleware_response_adds_deprecation_warning(self):
        """Test middleware adds deprecation warning to response"""
        # Register deprecated endpoint
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint/",
            method="GET",
            deprecated_since="2024-01-01",
            sunset_date=(timezone.now() + timedelta(days=30)).isoformat(),
        )
        APIVersionManager.register_deprecated_endpoint(endpoint)

        request = self.factory.get("/api/v1/old-endpoint/")
        request.api_version = APIVersion(1, 0, 0)

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        # Root cause fix: Check Warning header is present (RFC 7234 deprecation warning)
        # Middleware now calls add_deprecation_warning which adds Warning header
        self.assertIn("Warning", response.headers)
        # Verify Warning header contains deprecation info
        warning_value = response.headers.get("Warning", "")
        self.assertIn("Deprecated API", warning_value)

    def test_middleware_response_non_api(self):
        """Test middleware ignores non-API responses"""
        request = self.factory.get("/admin/")
        response = HttpResponse()
        processed_response = self.middleware.process_response(request, response)

        # Should return response unchanged
        self.assertEqual(processed_response, response)
        self.assertNotIn("X-API-Version", response)

    def test_middleware_full_cycle(self):
        """Test middleware full request/response cycle"""
        request = self.factory.get("/api/v1/assets/")

        # Process request
        early_response = self.middleware.process_request(request)
        self.assertIsNone(early_response)
        self.assertIsNotNone(getattr(request, "api_version", None))

        # Process response
        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        self.assertIn("X-API-Version", response)

    def test_middleware_version_negotiation_path_header_match(self):
        """Test version negotiation when path and header match"""
        request = self.factory.get("/api/v1/assets/", HTTP_ACCEPT="application/vnd.idh.v1+json")

        version = APIVersionManager.get_request_version(request)
        self.assertEqual(version.major, 1)

        response = self.middleware.process_request(request)
        self.assertIsNone(response)  # Should succeed

    def test_middleware_version_negotiation_default(self):
        """Test version negotiation defaults to current version"""
        # Request without version in path or header
        request = self.factory.get("/api/assets/")

        version = APIVersionManager.get_request_version(request)
        self.assertEqual(version, APIVersionManager.CURRENT_VERSION)

        response = self.middleware.process_request(request)
        # Should succeed (current version is supported)
        self.assertIsNone(response)

    def tearDown(self):
        APIVersionManager.DEPRECATED_ENDPOINTS = self._saved_deprecated
        super().tearDown()
