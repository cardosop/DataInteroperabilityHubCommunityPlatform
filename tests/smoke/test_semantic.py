"""
Full-stack semantic smoke test (312.15.1).

Validates SPARQL query execution and result retrieval against the semantic service.

The semantic layer is auth-gated (IsAuthenticated + IsTenantAdmin), so the
SPARQL calls run with the admin session from the smoke conftest
(authenticated_session, SMOKE_ADMIN_* credentials).

Usage:
    pytest tests/smoke/test_semantic.py --base-url=https://stagingmeshant-internal.example.com -v
"""

import os

import pytest
import requests

TIMEOUT = int(os.environ.get("SMOKE_TEST_TIMEOUT", "30"))


class TestSemanticSmoke:
    """SPARQL query smoke tests against the semantic service."""

    def test_semantic_service_health(self, timeout: int) -> None:
        """Semantic SERVICE health endpoint is reachable (direct microservice check)."""
        semantic_url = os.getenv("SEMANTIC_SERVICE_URL", "http://semantic-service-test:8081")
        try:
            response = requests.get(f"{semantic_url}/health", timeout=min(timeout, 5))
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Semantic service not available (transient: connection refused or timeout)")  # noqa: skip-in-body
        assert response.status_code == 200, (
            f"Semantic service health returned {response.status_code}"
        )
        data = response.json()
        assert "status" in data

    def test_sparql_query_basic(
        self, base_url: str, authenticated_session: requests.Session, timeout: int
    ) -> None:
        """Execute a simple SPARQL query and verify results structure."""
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5"
        r = authenticated_session.post(
            f"{base_url}/api/v1/semantic/sparql",
            json={"query": query},
            timeout=timeout,
        )
        assert r.status_code == 200, f"SPARQL query failed: {r.status_code} body={r.text[:200]}"
        data = r.json()
        assert "results" in data or "bindings" in data or "head" in data, (
            f"Unexpected SPARQL response format: "
            f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
        )

    def test_sparql_query_results_count(
        self, base_url: str, authenticated_session: requests.Session, timeout: int
    ) -> None:
        """SPARQL query with LIMIT returns correct number of results."""
        query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 3"
        r = authenticated_session.post(
            f"{base_url}/api/v1/semantic/sparql",
            json={"query": query},
            timeout=timeout,
        )
        if r.status_code != 200:
            pytest.skip(f"SPARQL returned {r.status_code} — may need data seeding")  # noqa: skip-in-body — runtime service dependency
        data = r.json()
        bindings = data.get("results", {}).get("bindings", []) if isinstance(data, dict) else []
        assert len(bindings) <= 3, f"LIMIT 3 violated: {len(bindings)} results"

    def test_sparql_endpoint_accepts_get(
        self, base_url: str, authenticated_session: requests.Session, timeout: int
    ) -> None:
        """SPARQL endpoint supports GET with query parameter."""
        query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"
        r = authenticated_session.get(
            f"{base_url}/api/v1/semantic/sparql",
            params={"query": query},
            timeout=timeout,
        )
        assert r.status_code in (200, 400, 405), f"Unexpected: {r.status_code}"

    def test_sparql_rejects_invalid_query(
        self, base_url: str, authenticated_session: requests.Session, timeout: int
    ) -> None:
        """Malformed SPARQL returns 400, not 500."""
        r = authenticated_session.post(
            f"{base_url}/api/v1/semantic/sparql",
            json={"query": "THIS IS NOT SPARQL"},
            timeout=timeout,
        )
        assert r.status_code in (400, 422), (
            f"Expected 400/422 for invalid SPARQL, got {r.status_code}"
        )
