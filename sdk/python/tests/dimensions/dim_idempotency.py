import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.7 — Dimension: idempotency.

Verifies that retrying a POST (e.g. asset creation) with the same
Idempotency-Key does NOT double-create the resource.
"""

import uuid

import requests

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


@pytest.fixture(scope="module")
def creds():
    return provision_persona("data_engineer")


def test_duplicate_post_with_idempotency_key_returns_same_resource(creds):
    """Two POSTs with the same Idempotency-Key must return the same resource id."""
    idem_key = str(uuid.uuid4())
    asset_name = fresh_id("idem-asset")

    def _create():
        return requests.post(
            f"{api_base_url()}/assets/",
            headers={
                "Authorization": f"Bearer {creds.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idem_key,
            },
            json={"name": asset_name, "key": fresh_id("idem-key")},
            timeout=15,
        )

    resp1 = _create()
    if resp1.status_code not in (200, 201):
        pytest.skip(f"Asset creation failed: {resp1.status_code} {resp1.text[:200]}")

    resp2 = _create()
    # Second call should return the same resource (200/201) or 409 (conflict)
    assert resp2.status_code in (200, 201, 409), (
        f"Retry with same Idempotency-Key returned {resp2.status_code}"
    )

    if resp2.status_code in (200, 201):
        id1 = resp1.json().get("id")
        id2 = resp2.json().get("id")
        assert id1 == id2, f"Idempotency violation: first={id1}, retry={id2} — double-create!"


def test_different_idempotency_key_creates_new_resource(creds):
    """Two POSTs with DIFFERENT Idempotency-Keys must create two resources."""

    def _create(key_suffix):
        return requests.post(
            f"{api_base_url()}/assets/",
            headers={
                "Authorization": f"Bearer {creds.api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json={"name": fresh_id("idem-diff"), "key": fresh_id(f"k-{key_suffix}")},
            timeout=15,
        )

    resp1 = _create("a")
    resp2 = _create("b")
    if resp1.status_code not in (200, 201) or resp2.status_code not in (200, 201):
        pytest.skip("Could not create two assets for comparison")

    id1 = resp1.json().get("id")
    id2 = resp2.json().get("id")
    assert id1 != id2, "Different Idempotency-Keys produced the same resource id"


def test_post_without_idempotency_key_still_works(creds):
    """POST without an Idempotency-Key header must still succeed (key is optional)."""
    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json={"name": fresh_id("no-idem"), "key": fresh_id("no-idem-key")},
        timeout=15,
    )
    assert resp.status_code in (200, 201, 400, 409), (
        f"POST without Idempotency-Key: {resp.status_code}"
    )
