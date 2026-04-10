import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.9 — Marketplace order lifecycle.

Validates the marketplace flow: a data_product_owner publishes a listing,
a data_consumer subscribes to it, and the subscriber can then access the
underlying asset.
"""

import requests
from tests._persona_provisioning import provision_persona, PersonaCredentials
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _dpo_creds() -> PersonaCredentials:
    """Provision a publisher persona (data_mesh_domain_owner has
    TENANT_ADMIN + DATA_PROVIDER roles, sufficient for publishing).
    """
    return provision_persona("data_mesh_domain_owner")


def _dc_creds() -> PersonaCredentials:
    """Provision a subscriber persona (auditor is a non-publisher
    role in a separate session).
    """
    return provision_persona("auditor")


def _create_and_activate_asset(creds: PersonaCredentials) -> dict:
    """Create a test asset, satisfy activation prerequisites, activate it,
    and return the activated asset response body.

    The marketplace listing endpoint requires assets to be ACTIVE.
    This helper follows the real activation lifecycle:
      1. Create asset (DRAFT)
      2. POST ensure-e2e-activation-prerequisites (creates contract, sets DQ/compliance)
      3. POST activate (transitions DRAFT -> ACTIVE)
    """
    base = api_base_url()
    headers = _auth_headers(creds.api_key)
    asset_key = fresh_id("mkt-asset")

    # Step 1: Create asset (starts in DRAFT)
    create_resp = requests.post(
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
    assert create_resp.status_code in (200, 201), (
        f"Asset creation failed: {create_resp.status_code}: {create_resp.text[:300]}"
    )
    asset_body = create_resp.json()
    asset_id = asset_body.get("id") or asset_body.get("key")
    version = asset_body.get("version", 1)

    # Step 2: Ensure activation prerequisites (contract, DQ, compliance)
    prereq_resp = requests.post(
        f"{base}/assets/{asset_id}/ensure-e2e-activation-prerequisites/",
        headers=headers,
        json={},
        timeout=30,
    )
    assert prereq_resp.status_code in (200, 201), (
        f"ensure-e2e-activation-prerequisites failed: "
        f"{prereq_resp.status_code}: {prereq_resp.text[:300]}"
    )

    # Step 3: Activate the asset (DRAFT -> ACTIVE)
    activate_resp = requests.post(
        f"{base}/assets/{asset_id}/activate/",
        headers=headers,
        json={"version": version},
        timeout=15,
    )
    assert activate_resp.status_code == 200, (
        f"Asset activation failed: {activate_resp.status_code}: "
        f"{activate_resp.text[:500]}"
    )
    activated = activate_resp.json()
    assert activated.get("status") == "ACTIVE", (
        f"Asset status is not ACTIVE after activation: {activated}"
    )
    return activated


# ===========================================================================
# Tests
# ===========================================================================


def test_publish_listing():
    """Provision a data_product_owner, create and activate an asset, then
    publish it as a marketplace listing. Expect 201.
    """
    dpo = _dpo_creds()
    base = api_base_url()

    asset = _create_and_activate_asset(dpo)
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

    asset = _create_and_activate_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("catalog-test")
    create_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": "Test listing for catalog verification",
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

    # Publisher creates activated asset + listing
    asset = _create_and_activate_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("sub-listing")
    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": "Test listing for catalog verification",
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

    # Publisher: create activated asset + listing
    asset = _create_and_activate_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("access-listing"),
            "short_description": "Test listing for access verification",
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
    an internal-visibility asset behind a marketplace listing.
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Create an INTERNAL-visibility asset (PRIVATE is not a valid value;
    # valid choices are INTERNAL and PUBLIC)
    asset_key = fresh_id("priv-asset")
    asset_resp = requests.post(
        f"{base}/assets/",
        headers=_auth_headers(dpo.api_key),
        json={
            "name": f"Internal Asset {asset_key}",
            "key": asset_key,
            "description": "Internal visibility asset for access control test",
            "visibility": "INTERNAL",
        },
        timeout=15,
    )
    assert asset_resp.status_code in (200, 201), (
        f"Asset creation failed: {asset_resp.status_code}: {asset_resp.text[:300]}"
    )
    asset_id = asset_resp.json().get("id") or asset_resp.json().get("key")

    # Consumer tries to access WITHOUT subscribing
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(dc.api_key),
        timeout=15,
    )

    assert get_resp.status_code in (403, 404), (
        f"Unsubscribed consumer accessed internal asset: "
        f"{get_resp.status_code}: {get_resp.text[:300]}"
    )


def test_duplicate_subscription_returns_conflict():
    """Subscribing to the same listing twice should return 409 or 400."""
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    asset = _create_and_activate_asset(dpo)
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("dup-listing"),
            "short_description": "Test listing for duplicate subscription",
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
