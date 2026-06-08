"""
Phase 274.5 — governance approval state machine constants.

Encodes the multi-step approval transition states so that all
consumers (DRF views, CLI, workers) reference the same named
constants rather than inline string literals.
"""

# AccessRequestStatus values used in multi-step approval.
PENDING_NEXT_APPROVER = "PENDING_NEXT_APPROVER"
PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"

# State → allowed transitions.
ALLOWED_TRANSITIONS = {
    PENDING: {PENDING_NEXT_APPROVER, APPROVED, REJECTED},
    PENDING_NEXT_APPROVER: {PENDING_NEXT_APPROVER, APPROVED, REJECTED},
    APPROVED: {"REVOKED", "EXPIRED"},
    REJECTED: set(),
    "REVOKED": set(),
    "EXPIRED": set(),
}
