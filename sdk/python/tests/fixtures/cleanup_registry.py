"""
Phase 216.X.3 layers 1+2 — per-test cleanup registry and per-session
provisioning teardown hook.

Three layers of cleanup are required by the spec:

1. **Per-test** ``cleanup_registry`` autouse fixture — every test that
   creates a backend resource registers it via
   ``cleanup_registry.add(callback)``; the registry runs each callback
   in LIFO order at function teardown, regardless of pass/fail status.
2. **Per-session** ``pytest_sessionfinish`` hook — invoked once when the
   test session ends; calls each registered persona-teardown callback so
   any provisioned personas are torn down even if a test crashed during
   their lifecycle.
3. **Per-deploy** ``manage.py purge_test_data --older-than=24h`` — Django
   management command run by a CI CronJob to sweep anything that
   escaped layers 1 and 2. Implemented separately at
   ``hub/apps/api/management/commands/purge_test_data.py``.

This module implements layers 1 and 2. Layer 3 lives in the hub app.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Tuple

import pytest

logger = logging.getLogger(__name__)


# Process-global list of persona teardown callbacks. The
# ``pytest_sessionfinish`` hook below drains it once per session.
_PERSONA_TEARDOWN_CALLBACKS: List[Tuple[str, Callable[[], None]]] = []


def register_persona_teardown(name: str, callback: Callable[[], None]) -> None:
    """Register a callback to be invoked at session teardown.

    Used by ``conftest.persona_provisioning_helper`` so personas
    provisioned during the session are guaranteed to be torn down even if
    every test that used them crashed mid-flight.
    """
    _PERSONA_TEARDOWN_CALLBACKS.append((name, callback))


def drain_persona_teardown_callbacks() -> List[Tuple[str, BaseException]]:
    """Run every registered persona teardown and return a list of failures.

    Failures are collected (not raised) so a single broken teardown does
    not prevent the rest from running. Pytest's ``sessionfinish`` hook
    logs them and exits non-zero if any failures occurred.
    """
    failures: List[Tuple[str, BaseException]] = []
    while _PERSONA_TEARDOWN_CALLBACKS:
        name, cb = _PERSONA_TEARDOWN_CALLBACKS.pop()
        try:
            cb()
        except BaseException as exc:  # noqa: BLE001 — collect everything
            failures.append((name, exc))
            logger.exception("persona teardown failed for %s", name)
    return failures


class CleanupRegistry:
    """Per-test cleanup registry. Callbacks run in LIFO order."""

    def __init__(self) -> None:
        self._callbacks: List[Tuple[str, Callable[[], None]]] = []

    def add(self, callback: Callable[[], None], *, label: str = "") -> None:
        """Register ``callback`` to run during teardown.

        Args:
            callback: Zero-arg callable to invoke.
            label: Optional human-readable label for diagnostics.
        """
        if not callable(callback):
            raise TypeError(f"cleanup callback must be callable, got {callback!r}")
        self._callbacks.append((label or repr(callback), callback))

    def __len__(self) -> int:
        return len(self._callbacks)

    def drain(self) -> List[Tuple[str, BaseException]]:
        """Run every callback in LIFO order; return collected failures.

        A failed callback does NOT abort the drain — every other
        callback still runs. This is critical: tests that create
        multiple resources MUST not leak the rest just because one
        cleanup failed.
        """
        failures: List[Tuple[str, BaseException]] = []
        while self._callbacks:
            label, cb = self._callbacks.pop()
            try:
                cb()
            except BaseException as exc:  # noqa: BLE001
                failures.append((label, exc))
                logger.exception("cleanup callback failed: %s", label)
        return failures


@pytest.fixture(autouse=True)
def cleanup_registry() -> "CleanupRegistry":
    """Yield a fresh ``CleanupRegistry`` for each test; drain on teardown."""
    registry = CleanupRegistry()
    yield registry
    failures = registry.drain()
    if failures:
        labels = ", ".join(label for label, _ in failures)
        raise RuntimeError(
            f"cleanup_registry teardown encountered {len(failures)} failures: {labels}"
        )
