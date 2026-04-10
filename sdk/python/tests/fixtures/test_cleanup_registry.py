"""
Phase 216.X.9 — unit tests for ``cli/tests/fixtures/cleanup_registry.py``.

Verifies LIFO order, exception isolation, the autouse drain hook, and
the per-session persona teardown plumbing. No mocks.
"""
from __future__ import annotations

import pytest

from tests.fixtures.cleanup_registry import (
    CleanupRegistry,
    _PERSONA_TEARDOWN_CALLBACKS,
    drain_persona_teardown_callbacks,
    register_persona_teardown,
)


def test_callbacks_run_in_lifo_order() -> None:
    log: list[str] = []
    reg = CleanupRegistry()
    reg.add(lambda: log.append("first"))
    reg.add(lambda: log.append("second"))
    reg.add(lambda: log.append("third"))
    reg.drain()
    assert log == ["third", "second", "first"]


def test_drain_returns_no_failures_on_success() -> None:
    reg = CleanupRegistry()
    reg.add(lambda: None)
    reg.add(lambda: None)
    assert reg.drain() == []


def test_failed_callback_does_not_abort_remaining_callbacks() -> None:
    log: list[str] = []
    reg = CleanupRegistry()

    def boom() -> None:
        raise RuntimeError("nope")

    reg.add(lambda: log.append("a"))
    reg.add(boom, label="boom")
    reg.add(lambda: log.append("c"))
    failures = reg.drain()
    # All non-failing callbacks ran (LIFO: c, then boom, then a).
    assert log == ["c", "a"]
    assert len(failures) == 1
    assert failures[0][0] == "boom"
    assert isinstance(failures[0][1], RuntimeError)


def test_drain_empties_the_registry() -> None:
    reg = CleanupRegistry()
    reg.add(lambda: None)
    assert len(reg) == 1
    reg.drain()
    assert len(reg) == 0


def test_add_rejects_non_callable() -> None:
    reg = CleanupRegistry()
    with pytest.raises(TypeError):
        reg.add("not callable")  # type: ignore[arg-type]


def test_persona_teardown_is_drained_in_lifo() -> None:
    # Snapshot + restore so the global list is unaffected for other tests.
    snapshot = list(_PERSONA_TEARDOWN_CALLBACKS)
    _PERSONA_TEARDOWN_CALLBACKS.clear()
    log: list[str] = []
    register_persona_teardown("p1", lambda: log.append("p1"))
    register_persona_teardown("p2", lambda: log.append("p2"))
    register_persona_teardown("p3", lambda: log.append("p3"))
    failures = drain_persona_teardown_callbacks()
    assert log == ["p3", "p2", "p1"]
    assert failures == []
    # restore
    _PERSONA_TEARDOWN_CALLBACKS.extend(snapshot)


def test_persona_teardown_collects_failures() -> None:
    snapshot = list(_PERSONA_TEARDOWN_CALLBACKS)
    _PERSONA_TEARDOWN_CALLBACKS.clear()

    def boom() -> None:
        raise ValueError("kaboom")

    register_persona_teardown("good", lambda: None)
    register_persona_teardown("bad", boom)
    failures = drain_persona_teardown_callbacks()
    assert len(failures) == 1
    assert failures[0][0] == "bad"
    assert isinstance(failures[0][1], ValueError)
    _PERSONA_TEARDOWN_CALLBACKS.extend(snapshot)
