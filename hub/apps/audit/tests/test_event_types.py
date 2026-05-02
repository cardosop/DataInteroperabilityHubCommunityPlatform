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
