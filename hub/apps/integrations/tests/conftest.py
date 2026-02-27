# -*- coding: utf-8 -*-
"""
Pytest conftest for integrations app tests.

Resets connector circuit breakers before each test so that expected failures
(invalid credentials, not found, retries exceeded, etc.) do not accumulate
and open the circuit for subsequent tests. Ensures test isolation without mocks.
"""

import pytest

from hub.apps.core.resilience.circuit_breaker import (
    reset_circuit_breaker_by_name,
)

AWS_DATA_EXCHANGE_CONNECTOR_SERVICE_NAME = "aws-data-exchange-connector"
GCP_MARKETPLACE_CONNECTOR_SERVICE_NAME = "gcp-marketplace-connector"


def _reset_connector_circuit_breakers():
    """Reset all connector circuit breakers used by integration tests."""
    reset_circuit_breaker_by_name(AWS_DATA_EXCHANGE_CONNECTOR_SERVICE_NAME)
    reset_circuit_breaker_by_name(GCP_MARKETPLACE_CONNECTOR_SERVICE_NAME)


@pytest.fixture(scope="function", autouse=True)
def reset_connector_circuit_breakers():
    """
    Reset connector circuit breakers before and after every test.

    Circuit breakers are shared (e.g. Redis-backed). Tests that expect
    connector failures would otherwise increment failure count; after the
    threshold the circuit opens and later tests get CircuitBreakerError.
    Resetting before each test prevents that for both AWS and GCP connectors.
    """
    _reset_connector_circuit_breakers()
    yield
    _reset_connector_circuit_breakers()
