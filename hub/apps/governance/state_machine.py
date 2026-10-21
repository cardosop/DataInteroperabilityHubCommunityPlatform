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
# W11.7 — PENDING also admits the withdrawal/expiry hops the real
# surfaces perform: order-cancel revokes a still-pending request
# (marketplace/order_views.py) and the SLA sweep expires overdue
# pending requests (revoke_expired_access).  Without them the writers
# either diverged from the machine (the pre-fix state) or went silent.
ALLOWED_TRANSITIONS = {
    PENDING: {PENDING_NEXT_APPROVER, APPROVED, REJECTED, "REVOKED", "EXPIRED"},
    PENDING_NEXT_APPROVER: {PENDING_NEXT_APPROVER, APPROVED, REJECTED},
    APPROVED: {"REVOKED", "EXPIRED"},
    REJECTED: set(),
    "REVOKED": set(),
    "EXPIRED": set(),
}
