"""
Phase 228 (REQ-LIN-006, 228.0.18) — capability flag tests.

Pins the five lineage flags + the GET /api/v1/capabilities/ endpoint
+ the test-mode / production default policy + per-flag override.
"""
from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient


def test_five_lineage_flags_are_registered():
    """REQ-LIN-006 — exactly the five named flags."""
    from hub.apps.api.capabilities import LINEAGE_CAPABILITY_FLAGS

    assert set(LINEAGE_CAPABILITY_FLAGS) == {
        "lineage.cross_tenant_marketplace",
        "lineage.field_level_mapping",
        "lineage.change_notifications",
        "lineage.openlineage_export",
        "lineage.snapshots",
    }


def test_test_environment_auto_enables_all_flags():
    """REQ-LIN-006 scenario: test env returns all flags True."""
    from hub.apps.api.capabilities import get_capabilities, LINEAGE_CAPABILITY_FLAGS

    # Pytest sets PYTEST_CURRENT_TEST so _is_test_environment() returns True.
    caps = get_capabilities()
    for flag in LINEAGE_CAPABILITY_FLAGS:
        assert caps[flag] is True, (
            f"flag {flag!r} should be True in test env; got {caps[flag]!r}"
        )


def test_settings_override_wins_over_default(monkeypatch):
    """Per-flag setting override beats env default."""
    with override_settings(
        CAPABILITY_FLAGS={
            "lineage.field_level_mapping": False,
            "lineage.snapshots": False,
        },
    ):
        from hub.apps.api.capabilities import get_capabilities
        caps = get_capabilities()
        assert caps["lineage.field_level_mapping"] is False
        assert caps["lineage.snapshots"] is False
        # Other flags stay test-default (True under pytest).
        assert caps["lineage.cross_tenant_marketplace"] is True


def test_capabilities_endpoint_returns_flag_map(db):
    """REQ-LIN-006 scenario: ``GET /api/v1/capabilities/`` returns the
    flat capability map. AllowAny so the frontend can call pre-auth."""
    client = APIClient()
    resp = client.get("/api/v1/capabilities/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert "capabilities" in data
    caps = data["capabilities"]
    expected = {
        "lineage.cross_tenant_marketplace",
        "lineage.field_level_mapping",
        "lineage.change_notifications",
        "lineage.openlineage_export",
        "lineage.snapshots",
    }
    assert expected.issubset(caps.keys()), (
        f"endpoint must return all five lineage flags; got {sorted(caps)}"
    )
    # Every value is a bool.
    for k, v in caps.items():
        assert isinstance(v, bool), f"flag {k!r} non-bool: {v!r}"


def test_is_capability_enabled_unknown_flag_returns_false():
    from hub.apps.api.capabilities import is_capability_enabled
    assert is_capability_enabled("lineage.does_not_exist") is False
