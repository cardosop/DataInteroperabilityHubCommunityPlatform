"""
Phase 274.5.4 — approval state machine tests (8 cases).

Covers PENDING_NEXT_APPROVER transitions from the state_machine module.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.governance.state_machine import (
    ALLOWED_TRANSITIONS,
    APPROVED,
    PENDING,
    PENDING_NEXT_APPROVER,
    REJECTED,
)

pytestmark = pytest.mark.django_db(transaction=True)


class TestApprovalStateMachine(TestCase):
    """Phase 274.5 — state machine constants and transitions."""

    def test_pending_allows_next_approver(self):
        assert PENDING_NEXT_APPROVER in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_allows_approved(self):
        assert APPROVED in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_allows_rejected(self):
        assert REJECTED in ALLOWED_TRANSITIONS[PENDING]

    def test_pending_next_allows_approved(self):
        assert APPROVED in ALLOWED_TRANSITIONS[PENDING_NEXT_APPROVER]

    def test_pending_next_allows_rejected(self):
        assert REJECTED in ALLOWED_TRANSITIONS[PENDING_NEXT_APPROVER]

    def test_approved_allows_revoked(self):
        assert "REVOKED" in ALLOWED_TRANSITIONS[APPROVED]

    def test_rejected_is_terminal(self):
        assert ALLOWED_TRANSITIONS[REJECTED] == set()

    def test_constants_are_strings(self):
        assert isinstance(PENDING, str)
        assert isinstance(PENDING_NEXT_APPROVER, str)
        assert isinstance(APPROVED, str)
        assert isinstance(REJECTED, str)
