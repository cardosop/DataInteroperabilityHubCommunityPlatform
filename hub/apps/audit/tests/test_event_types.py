"""
Phase 240.1.A.7 — audit-event constants for the DQ alerting pipeline.

These constants are the load-bearing names used by the alerting clients,
the RQ retry task, and the circuit breaker — they MUST exist as module
attributes (not just string literals scattered through the codebase) so
that callers can import them and the linter/type-checker can flag a
typo at the import site instead of at audit-replay time.
"""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.unit]


def test_module_imports():
    from hub.apps.audit import event_types  # noqa: F401


def test_dq_alert_constants_exist_and_are_strings():
    from hub.apps.audit import event_types

    expected = {
        "DQ_ALERT_DELIVERED",
        "DQ_ALERT_FAILED",
        "DQ_ALERT_DEAD_LETTER",
        "DQ_ALERT_CHANNEL_DEGRADED",
    }
    for name in expected:
        assert hasattr(event_types, name), f"event_types.{name} missing"
        value = getattr(event_types, name)
        assert isinstance(value, str), f"{name} must be str, got {type(value)}"
        assert value == name, (
            f"convention: constant value matches the constant name "
            f"so audit rows are self-describing ({name} != {value})"
        )


def test_constants_are_unique():
    from hub.apps.audit import event_types

    names = [
        event_types.DQ_ALERT_DELIVERED,
        event_types.DQ_ALERT_FAILED,
        event_types.DQ_ALERT_DEAD_LETTER,
        event_types.DQ_ALERT_CHANNEL_DEGRADED,
    ]
    assert len(set(names)) == len(names), "duplicate audit constants"


def test_resource_type_constant_exists():
    """The resource_type used on every DQ-alert audit row.

    Pinning this prevents the alerting code from drifting to
    ``"DQAlertingRule"`` vs ``"DQ_ALERTING_RULE"`` over time —
    a divergence that would silently fragment audit-replay queries.
    """
    from hub.apps.audit import event_types

    assert event_types.DQ_ALERT_RESOURCE_TYPE == "DQ_ALERTING_RULE"


# ---------------------------------------------------------------------------
# Phase 250.1.A.7 — fail-closed asset-creation audit events
# ---------------------------------------------------------------------------


def test_asset_fail_closed_constants_exist_and_are_strings():
    """Phase 250.1.A.7 — pin the two fail-closed-at-intake action names.

    These names are emitted by the asset-creation workflow when (a) a
    pre-persistence gate (compliance/DQ) returns FAIL and the workflow
    refuses to persist an asset row, or (b) a downstream step fails
    after the asset row was persisted and the saga compensates the
    full chain. Pinning the literal here prevents drift between the
    workflow emit-site and any future audit-replay queries.
    """
    from hub.apps.audit import event_types

    expected = {
        "ASSET_FAIL_CLOSED_REJECTED",
        "ASSET_WORKFLOW_ROLLED_BACK",
    }
    for name in expected:
        assert hasattr(event_types, name), f"event_types.{name} missing"
        value = getattr(event_types, name)
        assert isinstance(value, str), f"{name} must be str, got {type(value)}"
        assert value == name, (
            f"convention: constant value matches the constant name "
            f"so audit rows are self-describing ({name} != {value})"
        )


def test_asset_resource_type_constant_exists():
    """The ``resource_type`` value used on every asset-related audit row.

    Existing call-sites in :mod:`hub.apps.assets.views` and the
    asset-creation workflow already use the literal ``"ASSET"``;
    pinning the constant here keeps fail-closed events consistent
    with the rest of the asset audit surface.
    """
    from hub.apps.audit import event_types

    assert event_types.ASSET_RESOURCE_TYPE == "ASSET"


def test_asset_fail_closed_constants_are_unique_against_existing():
    """No new constant collides with the DQ alerting names."""
    from hub.apps.audit import event_types

    all_names = [
        event_types.DQ_ALERT_DELIVERED,
        event_types.DQ_ALERT_FAILED,
        event_types.DQ_ALERT_DEAD_LETTER,
        event_types.DQ_ALERT_CHANNEL_DEGRADED,
        event_types.ASSET_FAIL_CLOSED_REJECTED,
        event_types.ASSET_WORKFLOW_ROLLED_BACK,
    ]
    assert len(set(all_names)) == len(all_names), "duplicate audit constants"


# ---------------------------------------------------------------------------
# Phase 250.6.D.1 — onboarding-completion audit event
# ---------------------------------------------------------------------------


def test_onboarding_completed_constant_exists_and_is_self_describing():
    """``ONBOARDING_COMPLETED`` is pinned so signal-handler emit sites
    can import it instead of repeating the literal — drift between
    ``"ONBOARDING_COMPLETED"`` and a typo'd ``"ONBOARDING_DONE"``
    silently fragments audit-replay queries.
    """
    from hub.apps.audit import event_types

    assert hasattr(event_types, "ONBOARDING_COMPLETED")
    value = event_types.ONBOARDING_COMPLETED
    assert isinstance(value, str)
    assert value == "ONBOARDING_COMPLETED", (
        "convention: constant value matches the constant name so "
        "audit rows are self-describing"
    )


def test_onboarding_completed_does_not_collide_with_existing_constants():
    """The new code is unique against every other event_types constant."""
    from hub.apps.audit import event_types

    all_names = [
        event_types.DQ_ALERT_DELIVERED,
        event_types.DQ_ALERT_FAILED,
        event_types.DQ_ALERT_DEAD_LETTER,
        event_types.DQ_ALERT_CHANNEL_DEGRADED,
        event_types.ASSET_FAIL_CLOSED_REJECTED,
        event_types.ASSET_WORKFLOW_ROLLED_BACK,
        event_types.ASSET_ORPHAN_DRAFT_PURGED,
        event_types.ASSET_AUTO_ACTIVATED,
        event_types.ASSET_SCHEMA_DRIFT_DETECTED,
        event_types.ASSET_VISIBILITY_WRITE_DEPRECATED,
        event_types.ASSET_SEMANTIC_DEGRADED,
        event_types.ASSET_WORKFLOW_WARN_LOGGED,
        event_types.FEDERATED_IMPORT_REJECTED,
        event_types.FEDERATED_IMPORT_CROSS_REGION_BLOCKED,
        event_types.FEDERATED_SOURCE_TENANT_DELETED,
        event_types.ONBOARDING_COMPLETED,
    ]
    assert len(set(all_names)) == len(all_names), "duplicate audit constants"


def test_asset_semantic_degraded_constant_is_self_describing():
    """Phase 250.7.A — convention: constant value matches the
    constant name so audit rows are self-describing."""
    from hub.apps.audit import event_types

    assert event_types.ASSET_SEMANTIC_DEGRADED == "ASSET_SEMANTIC_DEGRADED"


def test_asset_workflow_warn_logged_constant_is_self_describing():
    """Phase 250.7.E — workflow WARN summary audit action constant."""
    from hub.apps.audit import event_types

    assert event_types.ASSET_WORKFLOW_WARN_LOGGED == "ASSET_WORKFLOW_WARN_LOGGED"


def test_cross_tenant_denied_constant_is_self_describing():
    """Phase 260.A.5 — cross-tenant denial audit action constant."""
    from hub.apps.audit import event_types

    assert event_types.CROSS_TENANT_DENIED == "CROSS_TENANT_DENIED"
