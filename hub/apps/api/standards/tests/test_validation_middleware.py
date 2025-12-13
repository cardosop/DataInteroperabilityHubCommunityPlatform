"""
Comprehensive tests for API validation middleware.
"""
import json

from django.http import HttpRequest, JsonResponse
from django.test import TestCase, RequestFactory
from rest_framework import status

from hub.apps.api.standards.error_codes import StandardErrorCodes
from hub.apps.api.standards.validation_middleware import APIValidationMiddleware


class TestAPIValidationMiddleware(TestCase):
    """Test APIValidationMiddleware class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = APIValidationMiddleware(lambda request: None)

    def test_process_request_non_api_path(self):
        """Test middleware skips non-API paths."""
        request = self.factory.get("/admin/")

        response = self.middleware.process_request(request)

        self.assertIsNone(response)

    def test_process_request_get_request(self):
        """Test middleware allows GET requests."""
        request = self.factory.get("/api/v1/resources/")

        response = self.middleware.process_request(request)

        self.assertIsNone(response)

    def test_process_request_post_with_valid_json(self):
        """Test middleware allows POST with valid JSON."""
        request = self.factory.post(
            "/api/v1/resources/",
            data=json.dumps({"name": "Test"}),
            content_type="application/json",
        )

        response = self.middleware.process_request(request)

        self.assertIsNone(response)

    def test_process_request_post_without_content_type(self):
        """Test middleware rejects POST without Content-Type."""
        request = self.factory.post("/api/v1/resources/", data={"name": "Test"})

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.INVALID_FORMAT)

    def test_process_request_post_with_invalid_json(self):
        """Test middleware rejects POST with invalid JSON."""
        request = self.factory.post(
            "/api/v1/resources/",
            data="invalid json{",
            content_type="application/json",
        )

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.INVALID_FORMAT)

    def test_process_request_post_with_empty_body(self):
        """Test middleware allows POST with empty body."""
        request = self.factory.post(
            "/api/v1/resources/", data="", content_type="application/json"
        )

        response = self.middleware.process_request(request)

        self.assertIsNone(response)

    def test_validate_query_params_valid_page(self):
        """Test validating valid page parameter."""
        request = self.factory.get("/api/v1/resources/?page=2")

        response = self.middleware._validate_query_params(request)

        self.assertIsNone(response)

    def test_validate_query_params_invalid_page_negative(self):
        """Test validating invalid negative page parameter."""
        request = self.factory.get("/api/v1/resources/?page=-1")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)

    def test_validate_query_params_invalid_page_non_integer(self):
        """Test validating invalid non-integer page parameter."""
        request = self.factory.get("/api/v1/resources/?page=invalid")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)

    def test_validate_query_params_valid_page_size(self):
        """Test validating valid page_size parameter."""
        request = self.factory.get("/api/v1/resources/?page_size=50")

        response = self.middleware._validate_query_params(request)

        self.assertIsNone(response)

    def test_validate_query_params_invalid_page_size_too_small(self):
        """Test validating invalid page_size parameter (too small)."""
        request = self.factory.get("/api/v1/resources/?page_size=0")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)

    def test_validate_query_params_invalid_page_size_too_large(self):
        """Test validating invalid page_size parameter (too large)."""
        request = self.factory.get("/api/v1/resources/?page_size=200")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)

    def test_validate_query_params_invalid_page_size_non_integer(self):
        """Test validating invalid non-integer page_size parameter."""
        request = self.factory.get("/api/v1/resources/?page_size=invalid")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)

    def test_validate_query_params_valid_ordering(self):
        """Test validating valid ordering parameter."""
        request = self.factory.get("/api/v1/resources/?ordering=-created_at,name")

        response = self.middleware._validate_query_params(request)

        self.assertIsNone(response)

    def test_validate_query_params_invalid_ordering_characters(self):
        """Test validating invalid ordering parameter with invalid characters."""
        request = self.factory.get("/api/v1/resources/?ordering=field;DROP TABLE")

        response = self.middleware._validate_query_params(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = json.loads(response.content)
        self.assertEqual(data["error"]["code"], StandardErrorCodes.VALIDATION_ERROR)
