"""
Phase 240.1.A.7 — canonical audit-event action constants.

Every audit row created from production code SHOULD reference one of
these constants instead of inlining a string literal — that way the
linter / type-checker catches a typo at the import site rather than
at audit-replay time when the row is already persisted.

Constants follow a "name == value" convention so that audit rows are
self-describing without an out-of-band lookup table:

    >>> from hub.apps.audit import event_types
    >>> event_types.DQ_ALERT_DELIVERED
    'DQ_ALERT_DELIVERED'

This module intentionally has zero runtime imports beyond ``__future__``
so it can be loaded in any context (signal handler, migration, RQ task)
without dragging in Django app-config side-effects.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Resource-type constants
# ---------------------------------------------------------------------------

#: ``resource_type`` value used on every DQ-alert audit row.
#: Pin once so audit-replay queries never need to UNION across drift.
DQ_ALERT_RESOURCE_TYPE: str = "DQ_ALERTING_RULE"


# ---------------------------------------------------------------------------
# DQ alerting pipeline (Phase 240.1.A)
# ---------------------------------------------------------------------------

#: Successful delivery to a configured channel.
#: ``details_json`` carries: channel, delivery_id, alert_id, rule_id, run_id.
DQ_ALERT_DELIVERED: str = "DQ_ALERT_DELIVERED"

#: Delivery attempt failed (will be retried unless retry budget exhausted).
#: ``details_json`` carries: channel, alert_id, rule_id, error, attempt_number.
DQ_ALERT_FAILED: str = "DQ_ALERT_FAILED"

#: Retry budget exhausted — alert moved to dead-letter queue.
#: ``details_json`` carries: channel, alert_id, rule_id, last_error,
#: total_attempts, dead_lettered_at.
#: This event also pages the ops PagerDuty (NOT the customer-facing one)
#: per D240.8.
DQ_ALERT_DEAD_LETTER: str = "DQ_ALERT_DEAD_LETTER"

#: Per-channel circuit breaker tripped to OPEN. Subsequent deliveries
#: short-circuit until the breaker recovers.
#: ``details_json`` carries: channel, tenant_id, failure_count,
#: timeout_seconds, circuit_breaker_name.
DQ_ALERT_CHANNEL_DEGRADED: str = "DQ_ALERT_CHANNEL_DEGRADED"


__all__ = [
    "DQ_ALERT_RESOURCE_TYPE",
    "DQ_ALERT_DELIVERED",
    "DQ_ALERT_FAILED",
    "DQ_ALERT_DEAD_LETTER",
    "DQ_ALERT_CHANNEL_DEGRADED",
]
