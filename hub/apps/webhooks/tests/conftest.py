# -*- coding: utf-8 -*-
"""
Pytest conftest for webhooks app tests.

Resets the webhook-delivery circuit breaker before each test so OPEN state from
earlier tests (or earlier failures in the same run) does not cause deliveries
to fail with "Circuit breaker is OPEN". Ensures test isolation without mocks.
"""

import pytest

from hub.apps.core.resilience.circuit_breaker import (
    reset_circuit_breaker_by_name,
)


WEBHOOK_DELIVERY_SERVICE_NAME = "webhook-delivery"


@pytest.fixture(autouse=True)
def reset_webhook_delivery_circuit_breaker():
    """Reset webhook-delivery circuit breaker before each test for isolation."""
    reset_circuit_breaker_by_name(WEBHOOK_DELIVERY_SERVICE_NAME)
    yield
    reset_circuit_breaker_by_name(WEBHOOK_DELIVERY_SERVICE_NAME)
