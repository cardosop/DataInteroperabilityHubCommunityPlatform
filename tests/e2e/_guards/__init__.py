"""Dual-channel verification helpers for the Meshant E2E suite.

These are deliberately landed in PR 2 as *unused* — they exist so later PRs
(6a-6e and 7a-7d) can import them without introducing new infrastructure and
risk in the same diff. Each helper is designed to fail loud and clear:
silently dropping a verification is the exact anti-pattern this work exists
to kill, so every function raises `AssertionError` with a useful diagnostic
instead of returning a boolean.

Public API:
    assert_audit_event(tenant, action, resource_type, ...)
    assert_audit_event_eventually(tenant, action, resource_type, ..., timeout=10)
    two_tenants  (pytest fixture)

See /home/ph/.claude/plans/create-a-comprehensive-and-piped-fiddle.md
section "PR 2" for the architectural rationale.
"""

from ._assert_audit_event import (
    assert_audit_event,
    assert_audit_event_eventually,
)
from ._captured_server_errors import (
    captured_server_errors,
    detect_offending_records,
    format_diagnostic,
    is_strict_mode,
)
from ._skip_counter import (
    pytest_runtest_logreport,
    record_skip,
)
from ._two_tenants import two_tenants

__all__ = [
    "assert_audit_event",
    "assert_audit_event_eventually",
    "captured_server_errors",
    "detect_offending_records",
    "format_diagnostic",
    "is_strict_mode",
    "pytest_runtest_logreport",
    "record_skip",
    "two_tenants",
]
