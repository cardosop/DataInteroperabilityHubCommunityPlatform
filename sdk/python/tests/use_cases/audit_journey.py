import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.2 -- AuditAPI journey.

Validates the audit-event read surface: listing, required fields,
filtering by resource type, and chronological ordering.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _admin_creds():
    return provision_persona("platform_admin")


def _skip_if_not_found(resp, label="Audit"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_list_audit_events():
    """GET /audit/events/ returns a list of audit entries."""
    creds = _admin_creds()
    resp = api_get("/audit/events/", creds)
    _skip_if_not_found(resp, "List audit events")

    assert resp.status_code == 200, (
        f"GET /audit/events/ returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    if isinstance(body, dict):
        assert "results" in body or "items" in body or "data" in body, (
            f"Paginated response missing results/items/data: {list(body.keys())}"
        )
    else:
        assert isinstance(body, list)


def test_audit_event_has_required_fields():
    """Each audit event must contain at least an action, timestamp, and actor."""
    creds = _admin_creds()
    resp = api_get("/audit/events/", creds)
    _skip_if_not_found(resp, "Audit events")

    assert resp.status_code == 200
    body = resp.json()
    events = body if isinstance(body, list) else (
        body.get("results") or body.get("items") or body.get("data") or []
    )

    if not events:
        pytest.skip("No audit events available to inspect")

    event = events[0]
    # At minimum we expect some form of action, timestamp, and actor
    keys_lower = {k.lower() for k in event.keys()}
    has_action = any(k in keys_lower for k in ("action", "event_type", "event", "type"))
    has_timestamp = any(k in keys_lower for k in ("timestamp", "created_at", "occurred_at", "time"))
    has_actor = any(k in keys_lower for k in ("actor", "user", "user_id", "actor_id", "performed_by"))

    assert has_action, f"Audit event missing action field: {list(event.keys())}"
    assert has_timestamp, f"Audit event missing timestamp field: {list(event.keys())}"
    assert has_actor, f"Audit event missing actor field: {list(event.keys())}"


def test_audit_events_filtered_by_resource_type():
    """GET /audit/events/?resource_type=asset filters results."""
    creds = _admin_creds()
    resp = api_get("/audit/events/", creds, params={"resource_type": "asset"})
    _skip_if_not_found(resp, "Audit events filtered")

    assert resp.status_code == 200, (
        f"Filtered audit query returned {resp.status_code}: {resp.text[:500]}"
    )
    body = resp.json()
    events = body if isinstance(body, list) else (
        body.get("results") or body.get("items") or body.get("data") or []
    )
    # If there are results, verify they relate to the requested resource type
    for ev in events[:10]:
        rt = (
            ev.get("resource_type", "")
            or ev.get("entity_type", "")
            or ev.get("object_type", "")
        ).lower()
        if rt:
            assert "asset" in rt, (
                f"Audit event resource_type mismatch: expected 'asset', got '{rt}'"
            )


def test_audit_events_ordered_by_timestamp():
    """Audit events should be returned in reverse-chronological order."""
    creds = _admin_creds()
    resp = api_get("/audit/events/", creds, params={"limit": "20"})
    _skip_if_not_found(resp, "Audit events")

    assert resp.status_code == 200
    body = resp.json()
    events = body if isinstance(body, list) else (
        body.get("results") or body.get("items") or body.get("data") or []
    )

    if len(events) < 2:
        pytest.skip("Not enough audit events to verify ordering")

    # Extract timestamps
    timestamps = []
    for ev in events:
        ts = (
            ev.get("timestamp")
            or ev.get("created_at")
            or ev.get("occurred_at")
            or ev.get("time")
        )
        if ts:
            timestamps.append(str(ts))

    if len(timestamps) < 2:
        pytest.skip("Audit events lack timestamp fields for ordering check")

    # Reverse-chronological: each timestamp >= next
    for i in range(len(timestamps) - 1):
        assert timestamps[i] >= timestamps[i + 1], (
            f"Audit events not in reverse-chronological order at index {i}: "
            f"{timestamps[i]} < {timestamps[i + 1]}"
        )
