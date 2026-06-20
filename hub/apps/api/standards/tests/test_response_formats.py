"""
Comprehensive tests for standardized response formats.
"""

import uuid

from django.test import TestCase
from rest_framework import status

from hub.apps.api.standards.response_formats import (
    StandardResponseFormatter,
    format_error_response,
    format_list_response,
    format_success_response,
)


class TestStandardResponseFormatter(TestCase):
    """Test StandardResponseFormatter class."""

    def test_format_success_with_dict_data(self):
        """Test formatting success response with dict data."""
        data = {"id": "123", "name": "Test"}
        response = StandardResponseFormatter.format_success(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], "123")
        self.assertEqual(response.data["name"], "Test")

    def test_format_success_with_list_data(self):
        """Test formatting success response with list data."""
        data = [1, 2, 3]
        response = StandardResponseFormatter.format_success(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"], [1, 2, 3])

    def test_format_success_with_message(self):
        """Test formatting success response with message."""
        data = {"id": "123"}
        response = StandardResponseFormatter.format_success(data, message="Success")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Success")
        self.assertEqual(response.data["id"], "123")

    def test_format_success_with_metadata(self):
        """Test formatting success response with metadata."""
        data = {"id": "123"}
        metadata = {"version": "1.0", "timestamp": "2025-01-15T10:00:00Z"}
        response = StandardResponseFormatter.format_success(data, metadata=metadata)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"], metadata)

    def test_format_success_with_custom_status_code(self):
        """Test formatting success response with custom status code."""
        data = {"id": "123"}
        response = StandardResponseFormatter.format_success(
            data, status_code=status.HTTP_201_CREATED
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_format_list_with_page_based(self):
        """Test formatting list response with page-based pagination."""
        items = [{"id": "1"}, {"id": "2"}]
        response = StandardResponseFormatter.format_list(
            items=items, count=100, page=1, page_size=50
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 100)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 50)
        self.assertEqual(response.data["results"], items)

    def test_format_list_with_cursor_based(self):
        """Test formatting list response with cursor-based pagination."""
        items = [{"id": "1"}, {"id": "2"}]
        response = StandardResponseFormatter.format_list(
            items=items,
            count=100,
            next_cursor="cursor123",
            previous_cursor="cursor456",
            page_size=50,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 100)
        self.assertEqual(response.data["next_cursor"], "cursor123")
        self.assertEqual(response.data["previous_cursor"], "cursor456")
        self.assertEqual(response.data["page_size"], 50)
        self.assertEqual(response.data["results"], items)

    def test_format_list_with_metadata(self):
        """Test formatting list response with metadata."""
        items = [{"id": "1"}]
        metadata = {"filter": "active"}
        response = StandardResponseFormatter.format_list(items=items, count=1, metadata=metadata)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metadata"], metadata)

    def test_format_error_basic(self):
        """Test formatting error response (basic)."""
        response = StandardResponseFormatter.format_error(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            http_status=status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["message"], "Invalid input")
        self.assertEqual(response.data["error"]["http_status"], 400)
        self.assertIn("request_id", response.data["error"])
        self.assertIn("timestamp", response.data["error"])

    def test_format_error_with_details(self):
        """Test formatting error response with details."""
        details = {"field_errors": [{"field": "email", "message": "Invalid email"}]}
        response = StandardResponseFormatter.format_error(
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            http_status=status.HTTP_400_BAD_REQUEST,
            details=details,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["details"], details)

    def test_format_error_with_request_id(self):
        """Test formatting error response with custom request ID."""
        request_id = str(uuid.uuid4())
        response = StandardResponseFormatter.format_error(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            http_status=status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
        )

        self.assertEqual(response.data["error"]["request_id"], request_id)

    def test_format_created_basic(self):
        """Test formatting 201 Created response (basic)."""
        data = {"id": "123", "name": "Test"}
        response = StandardResponseFormatter.format_created(data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["id"], "123")
        self.assertEqual(response.data["name"], "Test")

    def test_format_created_with_message(self):
        """Test formatting 201 Created response with message."""
        data = {"id": "123"}
        response = StandardResponseFormatter.format_created(data, message="Created")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Created")

    def test_format_created_with_location(self):
        """Test formatting 201 Created response with Location header."""
        data = {"id": "123"}
        response = StandardResponseFormatter.format_created(data, location="/api/v1/resources/123")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response["Location"], "/api/v1/resources/123")

    def test_format_no_content(self):
        """Test formatting 204 No Content response."""
        response = StandardResponseFormatter.format_no_content()

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(response.data)


class TestConvenienceFunctions(TestCase):
    """Test convenience functions."""

    def test_format_success_response(self):
        """Test format_success_response convenience function."""
        data = {"id": "123"}
        response = format_success_response(data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], "123")

    def test_format_list_response(self):
        """Test format_list_response convenience function."""
        items = [{"id": "1"}]
        response = format_list_response(items=items, count=1)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], items)

    def test_format_error_response(self):
        """Test format_error_response convenience function."""
        response = format_error_response(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            http_status=status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
