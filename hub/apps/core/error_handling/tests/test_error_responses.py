"""
Tests for Error Response Standardization
"""
from datetime import datetime
from uuid import uuid4

from django.test import TestCase
from rest_framework import status

from hub.apps.core.error_handling.error_responses import (
    ErrorResponse,
    ErrorResponseBuilder,
    format_error_response,
)


class ErrorResponseTest(TestCase):
    """Test ErrorResponse class."""
    
    def test_create_error_response(self):
        """Test creating error response."""
        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Invalid input",
            http_status=400,
        )
        
        self.assertEqual(error.code, "VALIDATION_ERROR")
        self.assertEqual(error.message, "Invalid input")
        self.assertEqual(error.http_status, 400)
        self.assertIsNotNone(error.request_id)
        self.assertIsNotNone(error.timestamp)
    
    def test_error_response_to_dict(self):
        """Test converting error response to dictionary."""
        error = ErrorResponse(
            code="NOT_FOUND",
            message="Resource not found",
            http_status=404,
            details={"resource_id": "123"},
        )
        
        error_dict = error.to_dict()
        
        self.assertIn("error", error_dict)
        self.assertEqual(error_dict["error"]["code"], "NOT_FOUND")
        self.assertEqual(error_dict["error"]["message"], "Resource not found")
        self.assertEqual(error_dict["error"]["http_status"], 404)
        self.assertIn("request_id", error_dict["error"])
        self.assertIn("timestamp", error_dict["error"])
        self.assertIn("details", error_dict["error"])
        self.assertEqual(error_dict["error"]["details"]["resource_id"], "123")
    
    def test_error_response_to_response(self):
        """Test converting error response to DRF Response."""
        error = ErrorResponse(
            code="INTERNAL_ERROR",
            message="Internal server error",
            http_status=500,
        )
        
        response = error.to_response()
        
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "INTERNAL_ERROR")


class ErrorResponseBuilderTest(TestCase):
    """Test ErrorResponseBuilder class."""
    
    def test_builder_fluent_interface(self):
        """Test builder fluent interface."""
        error = (
            ErrorResponseBuilder()
            .code("VALIDATION_ERROR")
            .message("Invalid input")
            .http_status(400)
            .add_detail("field", "email")
            .build()
        )
        
        self.assertEqual(error.code, "VALIDATION_ERROR")
        self.assertEqual(error.message, "Invalid input")
        self.assertEqual(error.http_status, 400)
        self.assertIn("field", error.details)
    
    def test_builder_field_error(self):
        """Test adding field-level errors."""
        error = (
            ErrorResponseBuilder()
            .code("VALIDATION_ERROR")
            .message("Validation failed")
            .field_error("email", "Invalid email format")
            .field_error("password", "Password too short", "PASSWORD_TOO_SHORT")
            .build()
        )
        
        self.assertIn("field_errors", error.details)
        self.assertEqual(len(error.details["field_errors"]), 2)
        self.assertEqual(error.details["field_errors"][0]["field"], "email")
        self.assertEqual(error.details["field_errors"][1]["code"], "PASSWORD_TOO_SHORT")
    
    def test_builder_auto_code_from_status(self):
        """Test auto-determining code from HTTP status."""
        error = (
            ErrorResponseBuilder()
            .http_status(404)
            .message("Not found")
            .build()
        )
        
        self.assertEqual(error.code, "NOT_FOUND")
    
    def test_builder_auto_message_from_status(self):
        """Test auto-determining message from HTTP status."""
        error = (
            ErrorResponseBuilder()
            .code("AUTH_UNAUTHORIZED")
            .http_status(401)
            .build()
        )
        
        self.assertEqual(error.message, "Authentication required")


class FormatErrorResponseTest(TestCase):
    """Test format_error_response function."""
    
    def test_format_with_exception(self):
        """Test formatting error response from exception."""
        class TestException(Exception):
            code = "TEST_ERROR"
            message = "Test error message"
        
        exc = TestException()
        response = format_error_response(
            exception=exc,
            http_status=400,
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "TEST_ERROR")
        self.assertEqual(response.data["error"]["message"], "Test error message")
    
    def test_format_with_code_and_message(self):
        """Test formatting error response with explicit code and message."""
        response = format_error_response(
            code="CUSTOM_ERROR",
            message="Custom error message",
            http_status=500,
        )
        
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["error"]["code"], "CUSTOM_ERROR")
        self.assertEqual(response.data["error"]["message"], "Custom error message")
    
    def test_format_with_details(self):
        """Test formatting error response with details."""
        response = format_error_response(
            code="VALIDATION_ERROR",
            message="Validation failed",
            http_status=400,
            details={"field_errors": [{"field": "email", "message": "Invalid"}]},
        )
        
        self.assertIn("details", response.data["error"])
        self.assertIn("field_errors", response.data["error"]["details"])
    
    def test_format_with_request_id(self):
        """Test formatting error response with request ID."""
        request_id = str(uuid4())
        response = format_error_response(
            code="ERROR",
            message="Error",
            request_id=request_id,
        )
        
        self.assertEqual(response.data["error"]["request_id"], request_id)
    
    def test_builder_without_details(self):
        """Test builder without details."""
        error = (
            ErrorResponseBuilder()
            .code("ERROR")
            .message("Error message")
            .http_status(500)
            .build()
        )
        
        # Details should be None if not set
        self.assertFalse(error.details)
    
    def test_builder_with_timestamp(self):
        """Test builder with custom timestamp."""
        from datetime import datetime
        timestamp = datetime(2025, 1, 15, 10, 30, 0)
        
        error = (
            ErrorResponseBuilder()
            .code("ERROR")
            .message("Error message")
            .timestamp(timestamp)
            .build()
        )
        
        self.assertEqual(error.timestamp, timestamp)

