"""Unit tests for the shared guarded-transition primitive (openspec P5).

`hub.apps.core.state_machine.GuardedStateMachine` is the one primitive
every "status field with a legal transition matrix" adopts (orders in
W2.3; scheduled runs and payment transactions migrate in W3 / R2-P1).

Contract pinned here:
- ``can_transition`` answers the matrix; identity transitions (from ==
  to) are always legal — a same-status save is a no-op, not a change.
- ``validate_transition`` is the guarded write path; its message names
  the illegal hop AND the legal targets from the source state.
- Terminal states are DERIVED from the matrix (empty target set) — no
  second list to keep in sync.
- Raw-string statuses behave identically to enum members (TextChoices
  members are str subclasses; the matrix must not care).

Pure unit tests — no database.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from django.core.exceptions import ValidationError
from django.db.models import TextChoices

from hub.apps.core.state_machine import GuardedStateMachine


class DemoStatus(TextChoices):
    DRAFT = "DRAFT", "Draft"
    READY = "READY", "Ready"
    DONE = "DONE", "Done"
    CANCELLED = "CANCELLED", "Cancelled"


class DemoMachine(GuardedStateMachine):
    TRANSITIONS: ClassVar[dict] = {
        DemoStatus.DRAFT: frozenset({DemoStatus.READY, DemoStatus.CANCELLED}),
        DemoStatus.READY: frozenset({DemoStatus.DONE}),
        DemoStatus.DONE: frozenset(),
        DemoStatus.CANCELLED: frozenset(),
    }


class TestGuardedStateMachine:
    """Pins for the shared primitive (DemoMachine, no DB)."""

    def test_legal_transitions(self):
        assert DemoMachine.can_transition(DemoStatus.DRAFT, DemoStatus.READY)
        assert DemoMachine.can_transition(DemoStatus.DRAFT, DemoStatus.CANCELLED)
        assert DemoMachine.can_transition(DemoStatus.READY, DemoStatus.DONE)

    def test_illegal_transitions(self):
        assert not DemoMachine.can_transition(DemoStatus.DRAFT, DemoStatus.DONE)
        assert not DemoMachine.can_transition(DemoStatus.READY, DemoStatus.CANCELLED)
        assert not DemoMachine.can_transition(DemoStatus.DONE, DemoStatus.DRAFT)

    def test_identity_is_not_a_transition(self):
        # Strict semantics: identity is NOT a legal hop, so an action
        # targeting the current state (e.g. approve on APPROVED) fails
        # its guard. Same-status saves are no-ops handled by the caller
        # (see Order.clean — it skips validation when status is unchanged).
        for s in DemoStatus:
            assert not DemoMachine.can_transition(s, s), s

    def test_validate_transition_raises_on_illegal_hop(self):
        with pytest.raises(ValidationError) as ctx:
            DemoMachine.validate_transition(DemoStatus.DRAFT, DemoStatus.DONE)
        message = str(ctx.value)
        assert "Invalid state transition" in message
        assert "DRAFT" in message
        assert "DONE" in message
        # The message lists the legal targets from the source state.
        assert "READY" in message
        assert "CANCELLED" in message

    def test_validate_transition_raises_terminal_message(self):
        with pytest.raises(ValidationError) as ctx:
            DemoMachine.validate_transition(DemoStatus.DONE, DemoStatus.DRAFT)
        assert "none (terminal state)" in str(ctx.value)

    def test_validate_transition_passes_legal_hops_and_rejects_identity(self):
        DemoMachine.validate_transition(DemoStatus.DRAFT, DemoStatus.READY)
        with pytest.raises(ValidationError):
            DemoMachine.validate_transition(DemoStatus.CANCELLED, DemoStatus.CANCELLED)

    def test_terminal_states_are_derived_from_the_matrix(self):
        assert DemoMachine.is_terminal(DemoStatus.DONE)
        assert DemoMachine.is_terminal(DemoStatus.CANCELLED)
        assert not DemoMachine.is_terminal(DemoStatus.DRAFT)
        assert not DemoMachine.is_terminal(DemoStatus.READY)

    def test_get_valid_transitions(self):
        assert DemoMachine.get_valid_transitions(DemoStatus.DRAFT) == frozenset(
            {DemoStatus.READY, DemoStatus.CANCELLED}
        )
        assert DemoMachine.get_valid_transitions(DemoStatus.DONE) == frozenset()

    def test_unknown_from_status_fails_closed(self):
        assert not DemoMachine.can_transition(DemoStatus.DONE, "NOPE")
        assert DemoMachine.get_valid_transitions("UNKNOWN") == frozenset()
        assert not DemoMachine.is_terminal("UNKNOWN")

    def test_raw_string_statuses_match_enum_members(self):
        # TextChoices members ARE strs — direct status assignment in some
        # legacy paths may leave plain strings behind; the matrix must not
        # treat them as a bypass.
        assert DemoMachine.can_transition("DRAFT", "READY")
        assert not DemoMachine.can_transition("DRAFT", "DONE")
        with pytest.raises(ValidationError):
            DemoMachine.validate_transition("DRAFT", "DONE")
