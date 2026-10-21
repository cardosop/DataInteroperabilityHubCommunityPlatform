import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.9 — Marketplace order lifecycle.

Validates the marketplace flow: a data_product_owner publishes a listing,
a data_consumer places an order on it (POST /marketplace/orders/), the
provider approves it, and the consumer can then access the underlying
asset.  The consumer-side endpoint was renamed from /subscriptions/ to
/orders/ (Phase 270.A.1) — the old path 404s.
"""

import requests
from tests._persona_provisioning import PersonaCredentials, provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import (
    api_base_url,
)
from tests.use_cases.conftest import register_asset_cleanup, register_contract_cleanup

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


def _create_asset(
    creds: PersonaCredentials, cleanup_registry=None, visibility: str = "PUBLIC"
) -> dict:
    """Create a test asset with a contract, activate it, and return it.

    Marketplace listings require ACTIVE assets. Activation requires an
    ACTIVE contract with valid normalization/validation statuses.

    Flow: create asset -> create ODCS contract for asset -> activate asset.

    ``visibility`` defaults to PUBLIC; the entitlement-access test passes
    INTERNAL so access is denied to other users until an order grants it.

    ``cleanup_registry`` (the autouse per-test fixture) registers API
    deletes for the asset and contract at teardown so the persistent
    full-mode backend doesn't accumulate them against the persona
    tenant's plan limits.  Cleanup snapshots *these* persona credentials
    (not the global CLI config, which other tests re-point).
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
            "visibility": visibility,
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert resp.status_code in (200, 201), (
        f"Asset creation failed: {resp.status_code}: {resp.text[:300]}"
    )
    asset = resp.json()
    asset_id = asset.get("id")

    if cleanup_registry is not None:
        register_asset_cleanup(cleanup_registry, asset_id, headers=headers, base_url=base)

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
            "asset_id": str(asset_id),  # noqa: PHASE216-STATIC-ID
        },
        timeout=120,  # workflow-backed endpoints can exceed 30s under load
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
    if cleanup_registry is not None:
        register_contract_cleanup(cleanup_registry, contract_id, headers=headers, base_url=base)
    if contract_id:
        # 3a: Trigger validation
        validate_resp = requests.post(
            f"{base}/contracts/{contract_id}/validate/",
            headers=headers,
            timeout=120,  # workflow-backed endpoints can exceed 30s under load
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
                timeout=60,  # workflow-backed calls can exceed 15s under load
            )
            if check.status_code == 200:
                cdata = check.json()
                vs = cdata.get("validation_status")
                ns = cdata.get("normalization_status")
                if vs in ("VALID", "WARNING_ONLY") and ns in (
                    "NORMALIZED_OK",
                    "NORMALIZED_WITH_WARNINGS",
                ):
                    # Update version for optimistic locking
                    contract_data = cdata
                    break
                if vs == "ERROR":
                    pytest.skip(
                        f"Contract validation returned ERROR: {cdata.get('validation_errors', [])}"
                    )
            _time.sleep(2)  # noqa: sleep-needed — retry loop  # INTENTIONAL: sleep-needed (auto-fixer marker completion)

        # 3b: Activate the contract (use latest version from poll)
        contract_version = contract_data.get("version", 1)
        activate_contract_resp = requests.patch(
            f"{base}/contracts/{contract_id}/",
            headers=headers,
            json={"status": "ACTIVE", "version": contract_version},
            timeout=60,  # workflow-backed calls can exceed 15s under load
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
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert get_resp.status_code == 200, f"Failed to fetch asset: {get_resp.status_code}"
    version = get_resp.json().get("version")

    activate_resp = requests.post(
        f"{base}/assets/{asset_id}/activate/",
        headers=headers,
        json={"version": version},
        timeout=60,  # workflow-backed calls can exceed 15s under load
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
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    if get_resp.status_code == 200:
        return get_resp.json()
    return asset


def _publish_listing(base: str, creds: PersonaCredentials, listing_id: str) -> None:
    """Publish a DRAFT listing via PATCH status=PUBLISHED.

    Listing creation produces a DRAFT; orders require a PUBLISHED listing.
    The publish transition runs the business-rule chain (KYB, compliance)
    inside ``MarketplaceService.update_listing``.
    """
    resp = requests.patch(
        f"{base}/marketplace/listings/{listing_id}/",
        headers=_auth_headers(creds.api_key),
        json={"status": "PUBLISHED"},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert resp.status_code == 200, (
        f"Listing publish returned {resp.status_code}: {resp.text[:400]}"
    )


# ===========================================================================
# Tests
# ===========================================================================


def test_publish_listing(cleanup_registry):
    """Provision a data_product_owner, create an asset, then publish it as
    a marketplace listing. Expect 201.
    """
    dpo = _dpo_creds()
    base = api_base_url()

    # Create an asset to list
    asset = _create_asset(dpo, cleanup_registry)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("listing")
    resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": "Automated test marketplace listing",
            "asset_id": asset_id,  # noqa: PHASE216-STATIC-ID
            "pricing_model": "FREE",
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    if resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert resp.status_code in (200, 201), (
        f"Listing creation returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    assert "id" in body or "listing_id" in body, f"Listing response missing id: {body}"


def test_listing_appears_in_catalog(cleanup_registry):
    """After publishing, the listing should be visible in the marketplace
    catalog (GET /marketplace/listings/).
    """
    dpo = _dpo_creds()
    base = api_base_url()

    asset = _create_asset(dpo, cleanup_registry)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("catalog-test")
    create_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": f"Test listing {listing_name}",
            "asset_id": asset_id,  # noqa: PHASE216-STATIC-ID
            "pricing_model": "FREE",
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    if create_resp.status_code == 404:
        pytest.skip("Marketplace listings endpoint not implemented (404)")

    assert create_resp.status_code in (200, 201)

    # List all marketplace listings
    list_resp = requests.get(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert list_resp.status_code == 200, f"Marketplace listing returned {list_resp.status_code}"

    list_body = list_resp.json()
    results = list_body if isinstance(list_body, list) else list_body.get("results", [])
    titles = [r.get("title") or r.get("name") for r in results]
    assert listing_name in titles, (
        f"Listing '{listing_name}' not found in catalog. Found: {titles[:10]}"
    )


def test_consumer_places_order(cleanup_registry):
    """A data_consumer places an order on a published listing. Expect 201.

    The dpo and dc personas live in different tenants, so this is the
    cross-tenant order flow: the API answers 201 with the order wrapped
    in ``{"order": {...}}`` and status REQUESTED (FREE listings require
    provider approval).  Approval and access follow in
    ``test_approved_order_grants_asset_access``.
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Publisher creates asset + listing, then publishes it.
    asset = _create_asset(dpo, cleanup_registry)
    asset_id = asset.get("id") or asset.get("key")

    listing_name = fresh_id("order-listing")
    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": listing_name,
            "short_description": f"Test listing {listing_name}",
            "asset_id": asset_id,  # noqa: PHASE216-STATIC-ID
            "pricing_model": "FREE",
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert listing_resp.status_code in (200, 201), (
        f"Listing creation returned {listing_resp.status_code}: {listing_resp.text[:500]}"
    )
    listing_body = listing_resp.json()
    listing_id = listing_body.get("id") or listing_body.get("listing_id")
    assert listing_id, f"Listing response missing id: {listing_body}"
    _publish_listing(base, dpo, listing_id)

    # Consumer places an order on the listing
    order_resp = requests.post(
        f"{base}/marketplace/orders/",
        headers=_auth_headers(dc.api_key),
        json={
            "listing_id": listing_id,
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert order_resp.status_code in (200, 201), (
        f"Order creation returned {order_resp.status_code}: {order_resp.text[:500]}"
    )
    order_body = order_resp.json()
    # Cross-tenant responses wrap the order; same-tenant responses are flat.
    order = order_body.get("order") or order_body
    assert order.get("id"), f"Order response missing id: {order_body}"
    # FREE listings require provider approval before fulfilment.
    assert order.get("status") == "REQUESTED", f"Expected REQUESTED order, got: {order_body}"


def test_approved_order_grants_asset_access(cleanup_registry):
    """Full order lifecycle across tenants: entitlement-gated access.

    dpo (tenant A) publishes an INTERNAL asset as a listing; dc (tenant
    B) has no access (POST /marketplace/entitlements/check-access/ →
    has_access false) until dc places an order and dpo approves it —
    approve grants an ACTIVE entitlement for tenant B and fulfils the
    order, after which check-access reports has_access true.

    (The plain ``GET /assets/{id}/`` route is tenant-scoped and never
    serves cross-tenant marketplace access; the entitlement check-access
    endpoint is the sanctioned access gate for consumers.)
    """
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    # Publisher: create an INTERNAL asset (most restrictive visibility)
    # + listing, then publish it.
    asset = _create_asset(dpo, cleanup_registry, visibility="INTERNAL")
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("access-listing"),
            "short_description": "Test access listing",
            "asset_id": asset_id,  # noqa: PHASE216-STATIC-ID
            "pricing_model": "FREE",
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert listing_resp.status_code in (200, 201), (
        f"Listing creation returned {listing_resp.status_code}: {listing_resp.text[:500]}"
    )
    listing_id = listing_resp.json().get("id") or listing_resp.json().get("listing_id")
    assert listing_id, f"Listing response missing id: {listing_resp.json()}"
    _publish_listing(base, dpo, listing_id)

    # Before any order: the consumer has no entitlement.
    pre_resp = requests.post(
        f"{base}/marketplace/entitlements/check-access/",
        headers=_auth_headers(dc.api_key),
        json={"asset_id": asset_id},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert pre_resp.status_code == 200, (
        f"check-access returned {pre_resp.status_code}: {pre_resp.text[:300]}"
    )
    assert pre_resp.json().get("has_access") is False, (
        f"Consumer had access before ordering: {pre_resp.json()}"
    )

    # Consumer places an order.
    order_resp = requests.post(
        f"{base}/marketplace/orders/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert order_resp.status_code in (200, 201), (
        f"Order creation returned {order_resp.status_code}: {order_resp.text[:300]}"
    )
    order_body = order_resp.json()
    order = order_body.get("order") or order_body
    order_id = order.get("id")
    assert order_id, f"Order response missing id: {order_body}"

    # Provider approves the order — approve grants the entitlement and
    # fulfils the order (POST /marketplace/orders/{id}/approve/).
    approve_resp = requests.post(
        f"{base}/marketplace/orders/{order_id}/approve/",
        headers=_auth_headers(dpo.api_key),
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert approve_resp.status_code in (200, 201), (
        f"Order approval returned {approve_resp.status_code}: {approve_resp.text[:300]}"
    )

    # After approval: check-access grants the consumer tenant.
    post_resp = requests.post(
        f"{base}/marketplace/entitlements/check-access/",
        headers=_auth_headers(dc.api_key),
        json={"asset_id": asset_id},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert post_resp.status_code == 200, (
        f"check-access returned {post_resp.status_code}: {post_resp.text[:300]}"
    )
    post_body = post_resp.json()
    assert post_body.get("has_access") is True, f"Consumer lacks access after approval: {post_body}"
    assert post_body.get("entitlement_id"), (
        f"check-access granted access without an entitlement id: {post_body}"
    )


def test_unsubscribed_user_cannot_access_private_asset(cleanup_registry):
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
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert asset_resp.status_code in (200, 201)
    asset_id = asset_resp.json().get("id") or asset_resp.json().get("key")
    register_asset_cleanup(
        cleanup_registry, asset_id, headers=_auth_headers(dpo.api_key), base_url=base
    )

    # Consumer tries to access WITHOUT subscribing
    get_resp = requests.get(
        f"{base}/assets/{asset_id}/",
        headers=_auth_headers(dc.api_key),
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert get_resp.status_code in (403, 404), (
        f"Unsubscribed consumer accessed private asset: "
        f"{get_resp.status_code}: {get_resp.text[:300]}"
    )


def test_duplicate_order_returns_conflict(cleanup_registry):
    """Placing a second order on the same listing should return 409."""
    dpo = _dpo_creds()
    dc = _dc_creds()
    base = api_base_url()

    asset = _create_asset(dpo, cleanup_registry)
    asset_id = asset.get("id") or asset.get("key")

    listing_resp = requests.post(
        f"{base}/marketplace/listings/",
        headers=_auth_headers(dpo.api_key),
        json={
            "title": fresh_id("dup-listing"),
            "short_description": "Test duplicate listing",
            "asset_id": asset_id,  # noqa: PHASE216-STATIC-ID
            "pricing_model": "FREE",
        },
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert listing_resp.status_code in (200, 201), (
        f"Listing creation returned {listing_resp.status_code}: {listing_resp.text[:500]}"
    )
    listing_id = listing_resp.json().get("id") or listing_resp.json().get("listing_id")
    assert listing_id, f"Listing response missing id: {listing_resp.json()}"
    _publish_listing(base, dpo, listing_id)

    # First order — succeeds.
    order1 = requests.post(
        f"{base}/marketplace/orders/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )
    assert order1.status_code in (200, 201), (
        f"First order returned {order1.status_code}: {order1.text[:300]}"
    )

    # Second order on the same listing — the API rejects duplicates with
    # 409 and echoes the existing order id.
    order2 = requests.post(
        f"{base}/marketplace/orders/",
        headers=_auth_headers(dc.api_key),
        json={"listing_id": listing_id},
        timeout=60,  # workflow-backed calls can exceed 15s under load
    )

    assert order2.status_code == 409, (
        f"Duplicate order returned {order2.status_code}, expected 409: {order2.text[:300]}"
    )
    body2 = order2.json()
    assert "already have an active order" in str(body2).lower(), (
        f"Duplicate order response lacks the expected message: {body2}"
    )
    assert body2.get("order_id"), f"Duplicate order response missing order_id: {body2}"
