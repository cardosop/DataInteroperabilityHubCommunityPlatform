"""
Phase 216.X.9 — unit tests for ``cli/tests/fixtures/wait_for.py``.

No mocks; uses real ``time.monotonic`` and a counter closure to drive
the predicate. Tests must remain deterministic so they use very small
intervals (1ms) and short timeouts.
"""

from __future__ import annotations

import time

import pytest
from tests.fixtures.wait_for import wait_for


def test_returns_immediately_when_predicate_is_already_true() -> None:
    start = time.monotonic()
    result = wait_for(lambda: "ready", timeout=5.0, interval=0.05)
    assert result == "ready"
    assert time.monotonic() - start < 0.5  # generous bound for slow CI


def test_eventually_returns_when_predicate_flips() -> None:
    counter = {"n": 0}

    def predicate() -> bool:
        counter["n"] += 1
        return counter["n"] >= 3

    result = wait_for(predicate, timeout=2.0, interval=0.01)
    assert result is True
    assert counter["n"] == 3


def test_raises_TimeoutError_when_predicate_never_succeeds() -> None:
    with pytest.raises(TimeoutError) as exc_info:
        wait_for(lambda: False, timeout=0.2, interval=0.05, description="never")
    assert "never" in str(exc_info.value)
    assert "iterations" in str(exc_info.value)


def test_propagates_exceptions_from_predicate_immediately() -> None:
    """Predicate exceptions are real bugs, not eventual-consistency signals."""

    class _Boom(RuntimeError):
        pass

    def predicate() -> bool:
        raise _Boom("explode")

    with pytest.raises(_Boom):
        wait_for(predicate, timeout=2.0, interval=0.01)


def test_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError):
        wait_for(lambda: True, timeout=0)
    with pytest.raises(ValueError):
        wait_for(lambda: True, timeout=-1)


def test_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError):
        wait_for(lambda: True, timeout=1.0, interval=0)


def test_returns_truthy_predicate_value_not_just_True() -> None:
    """If predicate returns a non-bool truthy value, that value is propagated."""
    result = wait_for(lambda: {"id": 42}, timeout=1.0, interval=0.01)
    assert result == {"id": 42}
