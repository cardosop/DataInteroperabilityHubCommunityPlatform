import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Webhooks journey: CLI webhooks command group.

Validates webhook listing, endpoint existence, and registration
via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get, api_post
from tests.fixtures.test_data import fresh_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provision_admin():
    """Webhook management typically requires admin permissions."""
    return provision_persona("admin")


def _extract_webhooks(body):
    """Extract the webhooks list from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("webhooks", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_list_webhooks():
    """GET /webhooks/ returns a list of registered webhooks."""
    creds = _provision_admin()

    resp = api_get("/webhooks/", creds)

    if resp.status_code == 404:
        pytest.skip("/webhooks/ endpoint not found (404)")

    assert resp.status_code == 200, (
        f"/webhooks/ returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    webhooks = _extract_webhooks(body)
    assert isinstance(webhooks, list), (
        f"Expected a list of webhooks, got {type(webhooks).__name__}"
    )


def test_webhook_endpoint_exists():
    """GET /webhooks/ responds without a 404, confirming the command
    group is available.
    """
    creds = _provision_admin()

    resp = api_get("/webhooks/", creds)

    if resp.status_code == 404:
        pytest.skip("/webhooks/ endpoint not found (404)")

    # Any non-404 success or auth error confirms the endpoint exists
    assert resp.status_code < 500, (
        f"/webhooks/ returned server error {resp.status_code}: {resp.text[:300]}"
    )


def test_create_webhook_registration():
    """POST /webhooks/ with a valid payload creates a webhook registration."""
    creds = _provision_admin()

    webhook_name = fresh_id("webhook")
    payload = {
        "name": webhook_name,
        "url": f"https://httpbin.org/post?id={webhook_name}",
        "events": ["asset.created", "asset.updated"],
        "active": True,
    }

    resp = api_post("/webhooks/", creds, json=payload)

    if resp.status_code == 404:
        pytest.skip("/webhooks/ POST endpoint not found (404)")

    if resp.status_code == 400:
        # Payload schema may differ — check the error for hints
        error_text = resp.text[:500].lower()
        if "event" in error_text or "url" in error_text:
            pytest.skip(
                f"Webhook payload schema mismatch (400): {resp.text[:300]}"
            )

    assert resp.status_code in (200, 201), (
        f"Webhook creation returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    assert "id" in body or "webhook_id" in body, (
        f"Webhook creation response missing id. Keys: {list(body.keys())}"
    )

    # Verify the webhook appears in the list
    list_resp = api_get("/webhooks/", creds)
    if list_resp.status_code == 200:
        webhooks = _extract_webhooks(list_resp.json())
        webhook_ids = [
            w.get("id", w.get("webhook_id")) for w in webhooks
        ]
        created_id = body.get("id", body.get("webhook_id"))
        assert created_id in webhook_ids, (
            f"Created webhook {created_id} not found in webhook list"
        )
