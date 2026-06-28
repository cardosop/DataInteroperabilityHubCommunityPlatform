"""
Phase TR.B — API integration test (relocated from E2E browser spec).

Tests the semantic service API connectivity.  The originally-planned
scheduled-semantic-webhooks endpoint was deferred per product decision
(D273.8); this test validates the semantic service health endpoint as a
service-reachability baseline until the webhooks feature is implemented.
"""

import os

import pytest
import requests

pytestmark = pytest.mark.django_db(transaction=True)


class TestApiLogic:
    """API logic formerly in E2E browser spec."""

    def test_semantic_service_health_responds(self):
        """Verify the semantic service health endpoint returns 200."""
        semantic_url = os.getenv(
            "SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081"
        )
        try:
            response = requests.get(
                f"{semantic_url.rstrip('/')}/health", timeout=10
            )
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Semantic service not reachable: {e}")

        assert response.status_code == 200, (
            f"Semantic service health should return 200 (got {response.status_code})"
        )
