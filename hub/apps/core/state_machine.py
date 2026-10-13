"""
Shared guarded-transition state machine (openspec oss-release-remediation P5).

One primitive for every status field that carries a legal transition
matrix. Adopted by orders (W2.3, R2-D4); scheduled runs and payment
transactions migrate onto it in W3 (R2-P1).

Contract:

- ``TRANSITIONS`` maps each status to the set of statuses it may move to.
- ``can_transition`` is STRICT: identity is not a transition (an action
  that targets the current state — e.g. approving an APPROVED order —
  must fail its guard). Same-status saves are no-ops and are the
  CALLER's decision: the save-path guard skips validation when the
  stored status is unchanged (see ``Order.clean``).
- Terminal states are DERIVED from the matrix (empty target set) — there
  is no second list to keep in sync.
- ``validate_transition`` is the guarded write path: anything that
  mutates a status field must ask the machine first (models via
  ``clean()``/``save()``, services before assignment). ``can_transition``
  is the boolean form, for friendly action-specific error messages.
- Statuses may be enum members (TextChoices) or raw strings — members
  ARE strings, and legacy direct-assignment paths can leave plain
  strings behind; the matrix must not treat that as a bypass.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.core.exceptions import ValidationError


def _label(status: Any) -> str:
    """Render a status for error messages (enum members or raw strings)."""
    return str(getattr(status, "value", status))


class GuardedStateMachine:
    """Base class for guarded status-transition matrices."""

    TRANSITIONS: ClassVar[dict[Any, frozenset[Any]]] = {}

    @classmethod
    def can_transition(cls, from_status: Any, to_status: Any) -> bool:
        """Return True when ``from → to`` is a legal hop (strict: not identity)."""
        return to_status in cls.TRANSITIONS.get(from_status, frozenset())

    @classmethod
    def validate_transition(cls, from_status: Any, to_status: Any) -> None:
        """Guard a status write; raises ValidationError on an illegal hop."""
        if cls.can_transition(from_status, to_status):
            return
        raise ValidationError(cls._transition_error(from_status, to_status))

    @classmethod
    def _transition_error(cls, from_status: Any, to_status: Any) -> str:
        valid = sorted(
            (getattr(s, "value", s) for s in cls.TRANSITIONS.get(from_status, ())),
            key=str,
        )
        suffix = ", ".join(str(s) for s in valid) or "none (terminal state)"
        return (
            f"Invalid state transition: {_label(from_status)} → {_label(to_status)}. "
            f"Valid transitions from {_label(from_status)}: {suffix}"
        )

    @classmethod
    def is_terminal(cls, status: Any) -> bool:
        """Return True when the status has no legal outgoing hop."""
        return status in cls.TRANSITIONS and not cls.TRANSITIONS[status]

    @classmethod
    def get_valid_transitions(cls, from_status: Any) -> frozenset[Any]:
        """Return the legal target set for a status (empty for terminal/unknown)."""
        return cls.TRANSITIONS.get(from_status, frozenset())
