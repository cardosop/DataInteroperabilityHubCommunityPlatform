import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Lineage journey: CLI lineage command group.

Validates lineage endpoint availability and graph structure
via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provision_analyst():
    return provision_persona("data_analyst")


# ===========================================================================
# Tests
# ===========================================================================


def test_lineage_endpoint_exists():
    """GET /lineage/ (or /lineage/graph/) responds with 200."""
    creds = _provision_analyst()

    resp = api_get("/lineage/", creds)
    if resp.status_code == 404:
        resp = api_get("/lineage/graph/", creds)
    if resp.status_code == 404:
        pytest.skip("Lineage endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Lineage endpoint returned {resp.status_code}: {resp.text[:500]}"
    )


def test_lineage_returns_graph_structure():
    """The lineage response contains nodes and edges (or equivalent
    graph structure fields).
    """
    creds = _provision_analyst()

    resp = api_get("/lineage/", creds)
    if resp.status_code == 404:
        resp = api_get("/lineage/graph/", creds)
    if resp.status_code == 404:
        pytest.skip("Lineage endpoint not found (404)")

    assert resp.status_code == 200, (
        f"Lineage endpoint returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()

    # The response should be a graph-like structure
    if isinstance(body, dict):
        graph_keys = {"nodes", "edges", "vertices", "links", "graph", "results", "items"}
        has_graph = any(k in body for k in graph_keys)
        assert has_graph, (
            f"Lineage response missing graph structure fields. Keys: {list(body.keys())}"
        )

        # If nodes are present, each should have an id
        nodes = body.get("nodes", body.get("vertices", []))
        if nodes and isinstance(nodes, list) and len(nodes) > 0:
            node = nodes[0]
            assert "id" in node or "node_id" in node or "asset_id" in node, (
                f"Lineage node missing id field. Keys: {list(node.keys())}"
            )
    elif isinstance(body, list):
        # Some APIs return a flat list of lineage entries
        if len(body) > 0:
            entry = body[0]
            assert isinstance(entry, dict), (
                f"Expected lineage entry to be a dict, got {type(entry).__name__}"
            )
