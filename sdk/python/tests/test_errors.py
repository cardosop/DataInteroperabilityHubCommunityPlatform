"""
Error Tests
"""
import pytest
from datahub_interoperability.errors import (
    DataHubError,
    ValidationError,
    UnauthorizedError,
    NotFoundError,
    RateLimitError,
    parse_error,
)


def test_datahub_error():
    """Test DataHubError creation"""
    error = DataHubError(
        "Test error",
        "TEST_ERROR",
        400,
        "req-123",
        "2025-01-15T10:00:00Z",
        {"field": "value"},
    )
    
    assert error.message == "Test error"
    assert error.code == "TEST_ERROR"
    assert error.http_status == 400
    assert error.request_id == "req-123"
    assert error.timestamp == "2025-01-15T10:00:00Z"
    assert error.details == {"field": "value"}


def test_datahub_error_to_dict():
    """Test error to_dict conversion"""
    error = DataHubError(
        "Test error",
        "TEST_ERROR",
        400,
        "req-123",
    )
    
    error_dict = error.to_dict()
    assert error_dict["error"]["code"] == "TEST_ERROR"
    assert error_dict["error"]["message"] == "Test error"
    assert error_dict["error"]["http_status"] == 400
    assert error_dict["error"]["request_id"] == "req-123"


def test_validation_error():
    """Test ValidationError"""
    error = ValidationError("Invalid input", "req-123", {"field_errors": []})
    
    assert isinstance(error, ValidationError)
    assert error.http_status == 400
    assert error.code == "VALIDATION_ERROR"
    assert error.details == {"field_errors": []}


def test_unauthorized_error():
    """Test UnauthorizedError"""
    error = UnauthorizedError("Auth required", "req-123")
    
    assert isinstance(error, UnauthorizedError)
    assert error.http_status == 401
    assert error.code == "AUTH_UNAUTHORIZED"


def test_not_found_error():
    """Test NotFoundError"""
    error = NotFoundError("Not found", "req-123")
    
    assert isinstance(error, NotFoundError)
    assert error.http_status == 404
    assert error.code == "NOT_FOUND"


def test_rate_limit_error():
    """Test RateLimitError with retry_after"""
    error = RateLimitError("Rate limit exceeded", "req-123", 60)
    
    assert isinstance(error, RateLimitError)
    assert error.http_status == 429
    assert error.retry_after == 60


def test_parse_error_validation():
    """Test parse_error for ValidationError"""
    response = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid input",
            "http_status": 400,
            "request_id": "req-123",
        }
    }
    
    error = parse_error(response)
    assert isinstance(error, ValidationError)
    assert error.http_status == 400


def test_parse_error_unauthorized():
    """Test parse_error for UnauthorizedError"""
    response = {
        "error": {
            "code": "AUTH_UNAUTHORIZED",
            "message": "Auth required",
            "http_status": 401,
        }
    }
    
    error = parse_error(response)
    assert isinstance(error, UnauthorizedError)


def test_parse_error_server_error():
    """Test parse_error for ServerError"""
    response = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Server error",
            "http_status": 500,
        }
    }
    
    error = parse_error(response)
    assert error.http_status == 500

