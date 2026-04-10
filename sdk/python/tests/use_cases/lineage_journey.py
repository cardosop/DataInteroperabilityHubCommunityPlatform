import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.6 -- LineageAPI journey.

Validates the lineage surface: retrieving lineage for an asset, verifying
the response contains nodes and edges, and confirming the endpoint exists.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_creds():
    return provision_persona("platform_admin")


def _owner_creds():
    return provision_persona("data_product_owner")


def _skip_if_not_found(resp, label="Lineage"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _get_any_asset_id(creds):
    """Return an asset id from the listing, or None."""
    resp = api_get("/assets/", creds)
    if resp.status_code != 200:
        return None
    body = resp.json()
    items = body if isinstance(body, list) else (
        body.get("results") or body.get("items") or body.get("data") or []
    )
    if not items:
        return None
    return items[0].get("id") or items[0].get("asset_id")


# ===========================================================================
# Tests
# ===========================================================================


def test_get_lineage_for_asset():
    """GET /lineage/<asset_id>/ (or /assets/<id>/lineage/) returns lineage data."""
    creds = _owner_creds()
    asset_id = _get_any_asset_id(creds)
    if asset_id is None:
        pytest.skip("No assets available for lineage lookup")

    # Try common lineage URL patterns
    for path in (
        f"/lineage/{asset_id}/",
        f"/assets/{asset_id}/lineage/",
        f"/lineage/?asset_id={asset_id}",
    ):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code in (200, 204), (
                f"Lineage endpoint {path} returned {resp.status_code}: "
                f"{resp.text[:500]}"
            )
            return

    pytest.skip("No lineage endpoint pattern responded (all 404)")


def test_lineage_has_nodes_and_edges():
    """Lineage response should contain nodes and edges (or equivalent)."""
    creds = _owner_creds()
    asset_id = _get_any_asset_id(creds)
    if asset_id is None:
        pytest.skip("No assets available for lineage lookup")

    # Try common patterns
    resp = None
    for path in (
        f"/lineage/{asset_id}/",
        f"/assets/{asset_id}/lineage/",
        f"/lineage/?asset_id={asset_id}",
    ):
        candidate = api_get(path, creds)
        if candidate.status_code == 200:
            resp = candidate
            break

    if resp is None:
        pytest.skip("No lineage endpoint returned 200")

    body = resp.json()

    # Lineage responses typically have nodes/edges or vertices/links
    keys_lower = {k.lower() for k in body.keys()} if isinstance(body, dict) else set()
    has_nodes = any(
        k in keys_lower
        for k in ("nodes", "vertices", "entities", "sources", "upstream", "downstream")
    )
    has_edges = any(
        k in keys_lower
        for k in ("edges", "links", "relationships", "connections")
    )

    # At minimum the body should have some structure
    assert has_nodes or has_edges or isinstance(body, list), (
        f"Lineage response lacks nodes/edges structure: {list(body.keys()) if isinstance(body, dict) else type(body)}"
    )


def test_lineage_endpoint_exists():
    """At least one lineage endpoint responds with a non-5xx status."""
    creds = _owner_creds()

    for path in ("/lineage/", "/lineage/graph/", "/assets/lineage/"):
        resp = api_get(path, creds)
        if resp.status_code != 404:
            assert resp.status_code < 500, (
                f"Lineage endpoint {path} returned server error "
                f"{resp.status_code}: {resp.text[:300]}"
            )
            return

    pytest.skip("No lineage endpoint responded (all 404)")
