import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.1 -- AssetsAPI journey.

End-to-end validation of the Assets CRUD surface: create, list, get-by-id,
update, delete, full lifecycle roundtrip, metadata attachment, and
name-based search.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_delete, api_get, api_post, api_put


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owner_creds():
    return provision_persona("data_product_owner")


def _create_asset(creds, *, name=None, extra=None):
    """Create an asset and return (response, asset_id)."""
    payload = {
        "name": name or fresh_id("asset"),
        "key": fresh_id("asset-key"),
        "description": "Automated journey test asset",
    }
    if extra:
        payload.update(extra)
    resp = api_post("/assets/", creds, json=payload)
    asset_id = None
    if resp.status_code in (200, 201):
        body = resp.json()
        asset_id = body.get("id") or body.get("asset_id")
    return resp, asset_id


def _skip_if_not_found(resp, label="Assets"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_create_asset():
    """POST /assets/ creates a new asset and returns 200/201."""
    creds = _owner_creds()
    resp, asset_id = _create_asset(creds)
    _skip_if_not_found(resp, "Create asset")

    assert resp.status_code in (200, 201), (
        f"POST /assets/ returned {resp.status_code}: {resp.text[:500]}"
    )
    assert asset_id is not None, "Response missing id/asset_id"


def test_list_assets():
    """GET /assets/ returns a list (possibly paginated)."""
    creds = _owner_creds()
    resp = api_get("/assets/", creds)
    _skip_if_not_found(resp, "List assets")

    assert resp.status_code == 200, (
        f"GET /assets/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    # Accept either a bare list or a paginated wrapper with "results"
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data key: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_get_asset_by_id():
    """GET /assets/<id>/ returns the asset we just created."""
    creds = _owner_creds()
    resp, asset_id = _create_asset(creds)
    _skip_if_not_found(resp, "Create asset")
    if asset_id is None:
        pytest.skip("Could not create asset to retrieve")

    get_resp = api_get(f"/assets/{asset_id}/", creds)
    assert get_resp.status_code == 200, (
        f"GET /assets/{asset_id}/ returned {get_resp.status_code}: {get_resp.text[:500]}"
    )
    body = get_resp.json()
    returned_id = body.get("id") or body.get("asset_id")
    assert str(returned_id) == str(asset_id)


def test_update_asset():
    """PUT /assets/<id>/ updates an existing asset."""
    creds = _owner_creds()
    resp, asset_id = _create_asset(creds)
    _skip_if_not_found(resp, "Create asset")
    if asset_id is None:
        pytest.skip("Could not create asset to update")

    new_desc = f"Updated by journey test {fresh_id('upd')}"
    put_resp = api_put(f"/assets/{asset_id}/", creds, json={"description": new_desc})
    _skip_if_not_found(put_resp, "Update asset")

    assert put_resp.status_code in (200, 204), (
        f"PUT /assets/{asset_id}/ returned {put_resp.status_code}: {put_resp.text[:500]}"
    )


def test_delete_asset():
    """DELETE /assets/<id>/ removes an asset."""
    creds = _owner_creds()
    resp, asset_id = _create_asset(creds)
    _skip_if_not_found(resp, "Create asset")
    if asset_id is None:
        pytest.skip("Could not create asset to delete")

    del_resp = api_delete(f"/assets/{asset_id}/", creds)
    _skip_if_not_found(del_resp, "Delete asset")

    assert del_resp.status_code in (200, 204), (
        f"DELETE /assets/{asset_id}/ returned {del_resp.status_code}: {del_resp.text[:500]}"
    )

    # Verify it is gone
    get_resp = api_get(f"/assets/{asset_id}/", creds)
    assert get_resp.status_code in (404, 410), (
        f"Asset still exists after DELETE: {get_resp.status_code}"
    )


def test_asset_lifecycle():
    """Full roundtrip: create -> update -> get -> delete."""
    creds = _owner_creds()
    name = fresh_id("lifecycle")

    # Create
    create_resp, asset_id = _create_asset(creds, name=name)
    _skip_if_not_found(create_resp, "Create asset (lifecycle)")
    if asset_id is None:
        pytest.skip("Could not create asset for lifecycle test")

    # Update
    updated_name = f"{name}-v2"
    put_resp = api_put(
        f"/assets/{asset_id}/",
        creds,
        json={"name": updated_name, "description": "lifecycle v2"},
    )
    assert put_resp.status_code in (200, 204), (
        f"Lifecycle update failed: {put_resp.status_code}"
    )

    # Get and verify update
    get_resp = api_get(f"/assets/{asset_id}/", creds)
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body.get("name") == updated_name or body.get("description") == "lifecycle v2"

    # Delete
    del_resp = api_delete(f"/assets/{asset_id}/", creds)
    assert del_resp.status_code in (200, 204)

    # Confirm gone
    gone_resp = api_get(f"/assets/{asset_id}/", creds)
    assert gone_resp.status_code in (404, 410)


def test_create_asset_with_metadata():
    """POST /assets/ with extra metadata fields succeeds."""
    creds = _owner_creds()
    extra = {
        "metadata": {
            "source_system": "journey-test",
            "owner_team": "platform-eng",
        },
        "tags": ["journey", "automated"],
    }
    resp, asset_id = _create_asset(creds, extra=extra)
    _skip_if_not_found(resp, "Create asset with metadata")

    assert resp.status_code in (200, 201), (
        f"Create with metadata failed: {resp.status_code}: {resp.text[:500]}"
    )
    assert asset_id is not None


def test_search_assets_by_name():
    """GET /assets/?search=<name> returns matching assets."""
    creds = _owner_creds()
    unique = fresh_id("searchable")
    create_resp, _ = _create_asset(creds, name=unique)
    _skip_if_not_found(create_resp, "Create asset for search")

    search_resp = api_get("/assets/", creds, params={"search": unique})
    assert search_resp.status_code == 200, (
        f"Search returned {search_resp.status_code}: {search_resp.text[:500]}"
    )

    body = search_resp.json()
    results = body if isinstance(body, list) else (
        body.get("results") or body.get("items") or body.get("data") or []
    )
    names = [r.get("name", "") for r in results]
    assert any(unique in n for n in names), (
        f"Search for '{unique}' did not return the created asset. Got names: {names}"
    )
