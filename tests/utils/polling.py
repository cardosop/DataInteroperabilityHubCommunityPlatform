"""
Polling utilities for integration tests.

Replaces fixed time.sleep with condition-based waiting to reduce flakiness.
No mocks; used for real async behavior (e.g. event persistence, flush).
"""

import time
from typing import Callable, Optional


def wait_until(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.2,
    message: str = "Condition not met within timeout",
) -> None:
    """
    Poll until condition() returns True or timeout is reached.

    Args:
        condition: Callable that returns True when the desired state is reached.
        timeout: Maximum time to wait in seconds.
        interval: Time between polls in seconds.
        message: Assertion message if timeout is reached.

    Raises:
        AssertionError: If condition is not met within timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError(message)
