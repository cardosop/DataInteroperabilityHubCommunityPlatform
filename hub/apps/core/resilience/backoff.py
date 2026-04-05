"""
Exponential Backoff with Jitter (Phase 91.11)

Non-blocking backoff delay calculator that replaces thread-blocking
``time.sleep(self.backoff_factor * (2 ** attempt))`` in service clients.

Uses "full jitter" strategy (AWS recommended) to decorrelate retries
across concurrent callers and avoid thundering-herd effects.

Reference: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
"""
import random
import time


def backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> float:
    """
    Calculate a jittered exponential backoff delay.

    Uses the "full jitter" formula::

        delay = random.uniform(0, min(max_delay, base_delay * 2^attempt))

    Args:
        attempt: Zero-indexed retry attempt number.
        base_delay: Base delay in seconds (multiplied by 2^attempt).
        max_delay: Upper cap on the computed delay.

    Returns:
        Jittered delay in seconds (always >= 0).
    """
    exp_delay = min(max_delay, base_delay * (2 ** attempt))
    return random.uniform(0, exp_delay)


def sleep_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> float:
    """
    Sleep for a jittered exponential backoff duration.

    Convenience wrapper around :func:`backoff_with_jitter` that calls
    ``time.sleep()`` with the computed delay.

    Args:
        attempt: Zero-indexed retry attempt number.
        base_delay: Base delay in seconds.
        max_delay: Upper cap on the computed delay.

    Returns:
        The actual delay slept (for logging).
    """
    delay = backoff_with_jitter(attempt, base_delay, max_delay)
    time.sleep(delay)
    return delay
