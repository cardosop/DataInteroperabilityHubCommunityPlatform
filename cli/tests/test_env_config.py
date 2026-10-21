"""
Test Environment Configuration for CLI Tests

This module provides utilities for configuring the test environment
for CLI tests, including API URL detection and service health checks.
"""

import os
from typing import Any


def get_test_api_url() -> str:
    """
    Get the test API URL from environment variables or defaults.

    Priority:
    1. TEST_API_URL environment variable
    2. API_BASE_URL environment variable
    3. API_SERVICE_URL environment variable
    4. API_TEST_PORT environment variable (constructs URL)
    5. Default: http://localhost:8001 (test environment default)

    Returns:
        API base URL for testing
    """
    # Check explicit test API URL
    api_url = os.getenv("TEST_API_URL") or os.getenv("API_BASE_URL") or os.getenv("API_SERVICE_URL")
    if api_url:
        return api_url.rstrip("/")

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
        or os.getenv("CLI_TEST_ENV", "").lower() == "true"
    )


def get_test_config_path() -> str | None:
    """
    Get the path to the test configuration file.

    Returns:
        Path to test config file or None
    """
    return os.getenv("CLI_TEST_CONFIG_PATH") or os.path.join(
        os.path.dirname(__file__), "..", ".datahub_test_config.json"
    )


def get_test_credentials() -> dict[str, Any]:
    """
    Get test credentials for CLI authentication.

    Returns:
        Dictionary with test credentials
    """
    return {
        "email": os.getenv("TEST_USER_EMAIL", "test@example.com"),
        "password": os.getenv("TEST_USER_PASSWORD", "testpass123"),
        "api_key": os.getenv("TEST_API_KEY"),
        "api_token": os.getenv("TEST_API_TOKEN"),
    }


def get_test_service_urls() -> dict[str, str]:
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
