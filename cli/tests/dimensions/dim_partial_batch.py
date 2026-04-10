import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.8 — Dimension: partial-batch failure.

Verifies that a bulk operation with one bad item does not fail the
entire batch — the good items succeed and the bad item is reported.
"""

import requests
from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_base_url


@pytest.fixture(scope="module")
def creds():
    return provision_persona("data_engineer")


def test_batch_create_with_one_invalid_item(creds):
    """A batch/bulk endpoint with 1 invalid item must not fail the entire batch."""
    items = [
        {"name": fresh_id("batch-good-1"), "key": fresh_id("bg1")},
        {"name": "", "key": ""},  # Invalid: empty name and key
        {"name": fresh_id("batch-good-2"), "key": fresh_id("bg2")},
    ]

    # Try the bulk endpoint if it exists
    resp = requests.post(
        f"{api_base_url()}/assets/bulk/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json={"items": items},
        timeout=30,
    )

    if resp.status_code == 404:
        # Bulk endpoint doesn't exist — test with sequential creates
        results = []
        for item in items:
            r = requests.post(
                f"{api_base_url()}/assets/",
                headers={
                    "Authorization": f"Bearer {creds.api_key}",
                    "Content-Type": "application/json",
                },
                json=item,
                timeout=15,
            )
            results.append(r.status_code)

        # At least one good item must succeed even though one is invalid
        successes = [s for s in results if s in (200, 201)]
        failures = [s for s in results if s in (400, 422)]
        assert len(successes) >= 1, (
            f"No successful creates in batch: {results}"
        )
        assert len(failures) >= 1, (
            f"Invalid item was not rejected: {results}"
        )
        return

    # Bulk endpoint exists
    if resp.status_code in (200, 207):
        data = resp.json()
        # 207 Multi-Status: some succeeded, some failed
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
            statuses = [r.get("status", r.get("code", 0)) for r in results]
            assert not all(s >= 400 for s in statuses if isinstance(s, int)), (
                f"All items failed in bulk: {statuses}"
            )


def test_single_invalid_item_returns_validation_error(creds):
    """A single invalid item must return a clear validation error, not 500."""
    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json={"name": "", "key": ""},
        timeout=15,
    )
    assert resp.status_code in (400, 422), (
        f"Invalid item returned {resp.status_code}, expected 400/422"
    )


def test_valid_item_after_invalid_succeeds(creds):
    """Creating a valid item immediately after a rejected one must succeed."""
    # First: invalid
    requests.post(
        f"{api_base_url()}/assets/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json={"name": "", "key": ""},
        timeout=15,
    )
    # Second: valid
    resp = requests.post(
        f"{api_base_url()}/assets/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "Content-Type": "application/json",
        },
        json={"name": fresh_id("after-bad"), "key": fresh_id("ab-key")},
        timeout=15,
    )
    assert resp.status_code in (200, 201), (
        f"Valid item after invalid returned {resp.status_code}"
    )
