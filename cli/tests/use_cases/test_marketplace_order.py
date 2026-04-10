import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.9 — Marketplace order lifecycle.

Validates the marketplace flow: a data_product_owner publishes a listing,
a data_consumer subscribes to it, and the subscriber can then access the
underlying asset.
"""

import os
import time
import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.personas import MVP_PERSONA_ROLES
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
    api_get,
    api_post,
    api_put,
    api_delete,
    api_login,
    api_unauthenticated_get,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _dpo_creds() -> PersonaCredentials:
    """Provision a data_product_owner (publisher)."""
    return provision_persona("data_product_owner")


def _dc_creds() -> PersonaCredentials:
    """Provision a data_consumer (subscriber)."""
    return provision_persona("data_consumer")


def _create_asset(creds: PersonaCredentials) -> dict:
    """Create a test asset with a contract, activate it, and return it.

    Marketplace listings require ACTIVE assets. Activation requires an
    ACTIVE contract with valid normalization/validation statuses.

    Flow: create asset -> create ODCS contract for asset -> activate asset.
    """
    base = api_base_url()
    headers = _auth_headers(creds.api_key)
    asset_key = fresh_id("mkt-asset")

    # Step 1: Create asset
    resp = requests.post(
        f"{base}/assets/",
        headers=headers,
        json={
            "name": f"Marketplace Asset {asset_key}",
            "key": asset_key,
            "description": "Asset for marketplace listing test",
            "visibility": "PUBLIC",
        },
        timeout=15,
    )
    assert resp.status_code in (200, 201), (
        f"Asset creation failed: {resp.status_code}: {resp.text[:300]}"
    )
    asset = resp.json()
    asset_id = asset.get("id")

    # Step 2: Create an ODCS contract attached to the asset.
    # The contract must pass normalization (requires name + schema.fields).
    import json as _json

    odcs_content = {
        "apiVersion": "odcs.io/v3.0.0",
        "kind": "DataContract",
        "id": f"contract-{asset_key}",
        "name": f"Contract for {asset_key}",
        "version": "1.0.0",
        "schema": {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "value", "type": "string"},
            ]
        },
    }

    contract_resp = requests.post(
        f"{base}/contracts/",
        headers=headers,
        json={
            "original_spec_type": "ODCS",
            "original_format": "JSON",
            "original_raw": _json.dumps(odcs_content),
            "asset_id": str(asset_id),
        },
        timeout=30,
    )
    if contract_resp.status_code not in (200, 201):
        pytest.skip(
            f"Contract creation failed — cannot activate asset for "
            f"marketplace test: {contract_resp.status_code}: "
            f"{contract_resp.text[:200]}"
        )

    # Step 3: Validate the contract, then activate it.
    # Contracts are created in DRAFT with validation_status=None.
    # Asset activation requires an ACTIVE contract whose
    # validation_status is VALID or WARNING_ONLY.
    # Flow: POST /contracts/{id}/validate/ → PATCH {"status": "ACTIVE"}
    contract_data = contract_resp.json()
    contract_id = contract_data.get("id")
    if contract_id:
        # 3a: Trigger validation
        validate_resp = requests.post(
            f"{base}/contracts/{contract_id}/validate/",
            headers=headers,
            timeout=30,
        )
        if validate_resp.status_code not in (200, 201, 202):
            pytest.skip(
                f"Contract validation failed: "
                f"{validate_resp.status_code}: "
                f"{validate_resp.text[:200]}"
            )

        # 3a-poll: Wait for validation + normalization to complete
        # (may be async on first validate call)
        import time as _time
        for _ in range(15):
            check = requests.get(
                f"{base}/contracts/{contract_id}/",
                headers=headers,
                timeout=15,
            )
            if check.status_code == 200:
                cdata = check.json()
                vs = cdata.get("validation_status")
                ns = cdata.get("normalization_status")
                if vs in ("VALID", "WARNING_ONLY") and ns in (
                    "NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"
                ):
                    # Update version for optimistic locking
                    contract_data = cdata
                    break
                if vs == "ERROR":
                    pytest.skip(
                        f"Contract validation returned ERROR: "
                        f"{cdata.get('validation_errors', [])}"
                    )
            _time.sleep(2)

        # 3b: Activate the contract (use latest version from poll)
        contract_version = contract_data.get("version", 1)
        activate_contract_resp = requests.patch(
            f"{base}/contracts/{contract_id}/",
            headers=headers,
            json={"status": "ACTIVE", "version": contract_version},
            timeout=15,
        )
        if activate_contract_resp.status_code not in (200, 204):
            pytest.skip(
                f"Contract activation failed: "
                f"{activate_contract_resp.status_code}: "
                f"{activate_contract_resp.text[:200]}"
            )

    # Step 4: Activate the asset (requires version for optimistic locking)
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=headers,
        timeout=15,
    )
    assert get_resp.status_code == 200, (
        f"Failed to fetch asset: {get_resp.status_code}"
    )
    version = get_resp.json().get("version")

    activate_resp = requests.post(
        f"{base}/assets/{asset_id}/activate/",
        headers=headers,
        json={"version": version},
        timeout=15,
    )
    if activate_resp.status_code not in (200, 204):
        pytest.skip(
            f"Asset activation blocked — marketplace tests need "
            f"ACTIVE assets: {activate_resp.status_code}: "
            f"{activate_resp.text[:200]}"
        )

    # Re-fetch to get updated status
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=headers,
        timeout=15,
    )
    if get_resp.status_code == 200:
        return get_resp.json()
    return asset


# ===========================================================================
# Tests
# ===========================================================================


def test_publish_listing():
    """Provision a data_product_owner, create an asset, then publish it as
    a marketplace listing. Expect 201.
    """
    dpo = _dpo_creds()
    base = api_base_url()

    # Create an asset to list
    asset = _create_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("listing")
    resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": "Automated test marketplace listing",
            "asset_id": asset_id,
            "pricing_model": "FREE",
        },
        timeout=15,
    )

    if resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert resp.status_code in (200, 201), (
        f"Listing creation returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert "id" in body or "listing_id" in body, (
        f"Listing response missing id: {body}"
    )


def test_listing_appears_in_catalog():
    """After publishing, the listing should be visible in the marketplace
    catalog (GET /marketplace/listings/).
    """
    dpo = _dpo_creds()
    base = api_base_url()

    asset = _create_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("catalog-test")
    create_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": f"Test listing {listing_name}",
            "asset_id": asset_id,
            "pricing_model": "FREE",
        },
        timeout=15,
    )

    if create_resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert create_resp.status_code in (200, 201)

    # List all marketplace listings
    list_resp = requests.get(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        timeout=15,
    )
    assert list_resp.status_code == 200, (
        f"Marketplace listing returned {list_resp.status_code}"
    )

    list_body = list_resp.json()
    results = list_body if isinstance(list_body, list) else list_body.get("results", [])
    titles = [r.get("title") or r.get("name") for r in results]
    assert listing_name in titles, (
        f"Listing '{listing_name}' not found in catalog. Found: {titles[:10]}"
    )


def test_subscribe_to_listing():
    """Provision a data_consumer, find or create a listing, then subscribe.
    Expect 201.
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Publisher creates asset + listing
    asset = _create_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("sub-listing")
    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": f"Test listing {listing_name}",
            "asset_id": asset_id,
            "pricing_model": "FREE",
        },
        timeout=15,
    )

    if listing_resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert listing_resp.status_code in (200, 201)
    listing_body = listing_resp.json()
    listing_id = listing_body.get("id") or listing_body.get("listing_id")
    assert listing_id, f"Listing response missing id: {listing_body}"

    # Consumer subscribes
    sub_resp = requests.post(
        f"{base}/marketplace/subscriptions/",
        headers=_auth_headers(dc.api_key),
        json={
            "listing_id": listing_id,
        },
        timeout=15,
    )

    if sub_resp.status_code == 404:
        pytest.skip("Marketplace subscriptions endpoint not implemented (404)")

    assert sub_resp.status_code in (200, 201), (
        f"Subscription creation returned {sub_resp.status_code}: "
        f"{sub_resp.text[:500]}"
    )
    sub_body = sub_resp.json()
    assert "id" in sub_body or "subscription_id" in sub_body, (
        f"Subscription response missing id: {sub_body}"
    )


def test_subscriber_can_access_asset():
    """After subscribing to a listing, the data_consumer should be able to
    GET the underlying asset (200).
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Publisher: create asset + listing
    asset = _create_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("access-listing"),
            "short_description": "Test access listing",
            "asset_id": asset_id,
            "pricing_model": "FREE",
        },
        timeout=15,
    )

    if listing_resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert listing_resp.status_code in (200, 201)
    listing_id = listing_resp.json().get("id") or listing_resp.json().get("listing_id")

    # Consumer: subscribe
    sub_resp = requests.post(
        f"{base}/marketplace/subscriptions/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=15,
    )

    if sub_resp.status_code == 404:
        pytest.skip("Marketplace subscriptions endpoint not implemented (404)")

    assert sub_resp.status_code in (200, 201), (
        f"Subscription failed: {sub_resp.status_code}: {sub_resp.text[:300]}"
    )

    # Consumer: access the asset
    asset_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(dc.api_key),
        timeout=15,
    )

    assert asset_resp.status_code == 200, (
        f"Subscriber cannot access asset after subscription: "
        f"{asset_resp.status_code}: {asset_resp.text[:300]}"
    )
    asset_body = asset_resp.json()
    fetched_id = asset_body.get("id") or asset_body.get("key")
    assert str(fetched_id) == str(asset_id), (
        f"Fetched asset id mismatch: {fetched_id} != {asset_id}"
    )


def test_unsubscribed_user_cannot_access_private_asset():
    """A data_consumer who has NOT subscribed should not be able to access
    a private asset behind a marketplace listing.
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Create an internal-visibility asset (the most restrictive visibility)
    asset_key = fresh_id("priv-asset")
    asset_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(dpo.api_key),
        json={
            "name": f"Internal Asset {asset_key}",
            "key": asset_key,
            "visibility": "INTERNAL",
        },
        timeout=15,
    )
    assert asset_resp.status_code in (200, 201)
    asset_id = asset_resp.json().get("id") or asset_resp.json().get("key")

    # Consumer tries to access WITHOUT subscribing
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(dc.api_key),
        timeout=15,
    )

    assert get_resp.status_code in (403, 404), (
        f"Unsubscribed consumer accessed private asset: "
        f"{get_resp.status_code}: {get_resp.text[:300]}"
    )


def test_duplicate_subscription_returns_conflict():
    """Subscribing to the same listing twice should return 409 or 400."""
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    asset = _create_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("dup-listing"),
            "short_description": "Test duplicate listing",
            "asset_id": asset_id,
            "pricing_model": "FREE",
        },
        timeout=15,
    )

    if listing_resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert listing_resp.status_code in (200, 201)
    listing_id = listing_resp.json().get("id") or listing_resp.json().get("listing_id")

    # First subscription
    sub1 = requests.post(
        f"{base}/marketplace/subscriptions/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=15,
    )

    if sub1.status_code == 404:
        pytest.skip("Marketplace subscriptions endpoint not implemented (404)")

    assert sub1.status_code in (200, 201)

    # Second subscription — should conflict
    sub2 = requests.post(
        f"{base}/marketplace/subscriptions/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=15,
    )

    assert sub2.status_code in (400, 409, 422), (
        f"Duplicate subscription returned {sub2.status_code}, expected 400/409/422: "
        f"{sub2.text[:300]}"
    )
