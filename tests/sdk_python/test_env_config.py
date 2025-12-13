"""
Test Environment Configuration for Python SDK Tests

This module provides utilities for configuring the test environment
for Python SDK tests, including API URL detection and service health checks.
"""

import os
from typing import Optional


def get_test_api_url() -> str:
    """
    Get the test API URL from environment variables or defaults.

    Priority:
    1. TEST_API_URL environment variable
    2. API_SERVICE_URL environment variable
    3. API_TEST_PORT environment variable (constructs URL)
    4. Default: http://localhost:8001 (test environment default)

    Returns:
        API base URL for testing
    """
    # Check explicit test API URL
    api_url = os.getenv("TEST_API_URL") or os.getenv("API_SERVICE_URL")
    if api_url:
        return api_url.rstrip("/")

    # Check if we're in Docker test environment
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER"):
        # In container, API service is at localhost:8000
        return "http://localhost:8000"

    # Check for test port configuration
    test_port = os.getenv("API_TEST_PORT", "8001")
    return f"http://localhost:{test_port}"


def get_test_api_base_url() -> str:
    """
    Get the full API base URL including /api/v1 prefix.

    Returns:
        Full API base URL (e.g., http://localhost:8001/api/v1)
    """
    base_url = get_test_api_url()
    if not base_url.endswith("/api/v1"):
        base_url = f"{base_url}/api/v1"
    return base_url


def is_test_environment() -> bool:
    """
    Check if we're running in a test environment.

    Returns:
        True if test environment is detected
    """
    return (
        os.getenv("ENVIRONMENT", "").lower() == "test"
        or os.getenv("TEST_ENV", "").lower() == "true"
        or os.getenv("USE_PRODUCTION_DB_FOR_SDK_TESTS", "").lower() == "0"
    )


def get_test_database_config() -> dict:
    """
    Get test database configuration.

    Returns:
        Dictionary with database configuration
    """
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_TEST_PORT", "5434")),
        "user": os.getenv("POSTGRES_USER", "hub_test"),
        "password": os.getenv("POSTGRES_PASSWORD", "hub_test"),
        "database": os.getenv("POSTGRES_DB", "hub_test"),
    }


def get_test_redis_config() -> dict:
    """
    Get test Redis configuration.

    Returns:
        Dictionary with Redis configuration
    """
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_TEST_PORT", "6380")),
        "db": int(os.getenv("REDIS_DB", "0")),
    }


def get_test_minio_config() -> dict:
    """
    Get test MinIO/S3 configuration.

    Returns:
        Dictionary with MinIO configuration
    """
    return {
        "endpoint_url": os.getenv("AWS_S3_ENDPOINT_URL", "http://localhost:9010"),
        "access_key_id": os.getenv("MINIO_ROOT_USER", "minioadmin"),
        "secret_access_key": os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        "bucket_name": os.getenv("AWS_STORAGE_BUCKET_NAME", "hub-test"),
    }


def get_test_service_urls() -> dict:
    """
    Get test service URLs for all microservices.

    Returns:
        Dictionary mapping service names to URLs
    """
    return {
        "datacontract": os.getenv("DATACONTRACT_SERVICE_URL", "http://localhost:8093"),
        "dq": os.getenv("DQ_SERVICE_URL", "http://localhost:8084"),
        "compliance": os.getenv("COMPLIANCE_SERVICE_URL", "http://localhost:8085"),
        "semantic": os.getenv("SEMANTIC_SERVICE_URL", "http://localhost:8086"),
        "fuseki": os.getenv("FUSEKI_URL", "http://localhost:3031"),
    }
