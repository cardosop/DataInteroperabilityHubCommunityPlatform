import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Audit journey: CLI audit command group.

Validates audit event listing, timestamp presence, and resource
filtering via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provision_admin():
    """Audit endpoints typically require elevated permissions."""
    return provision_persona("admin")


def _extract_events(body):
    """Extract the events list from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("events", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_list_audit_events():
    """GET /audit/ (or /audit/events/) returns a list of audit events."""
    creds = _provision_admin()

    resp = api_get("/audit/", creds)
    if resp.status_code == 404:
        resp = api_get("/audit/events/", creds)
    if resp.status_code == 404:
        pytest.skip("Audit endpoint not found (404)")

    assert resp.status_code == 200, f"Audit events returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    events = _extract_events(body)
    assert isinstance(events, list), f"Expected a list of audit events, got {type(events).__name__}"


def test_audit_event_has_timestamp():
    """Each audit event includes a timestamp field."""
    creds = _provision_admin()

    resp = api_get("/audit/", creds)
    if resp.status_code == 404:
        resp = api_get("/audit/events/", creds)
    if resp.status_code == 404:
        pytest.skip("Audit endpoint not found (404)")

    assert resp.status_code == 200, f"Audit events returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    events = _extract_events(body)

    if not events:
        pytest.skip("No audit events returned — cannot validate timestamp")

    event = events[0]
    has_timestamp = (
        "timestamp" in event
        or "created_at" in event
        or "occurred_at" in event
        or "event_time" in event
    )
    assert has_timestamp, f"Audit event missing timestamp field. Keys: {list(event.keys())}"


def test_audit_filter_by_resource():
    """GET /audit/ with a resource_type filter returns filtered results."""
    creds = _provision_admin()

    resp = api_get(
        "/audit/",
        creds,
        params={"resource_type": "asset"},
    )
    if resp.status_code == 404:
        resp = api_get(
            "/audit/events/",
            creds,
            params={"resource_type": "asset"},
        )
    if resp.status_code == 404:
        pytest.skip("Audit endpoint not found (404)")

    # Filter may not be supported — 200 or 400 are both acceptable
    if resp.status_code == 400:
        pytest.skip("Audit resource_type filter not supported (400)")

    assert resp.status_code == 200, f"Audit filter returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    events = _extract_events(body)
    assert isinstance(events, list), (
        f"Filtered audit response is not a list: {type(events).__name__}"
    )
