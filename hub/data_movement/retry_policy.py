"""W3.9 (oss-release-remediation F6) — the bounded retry policy for
the dlt movement path.

The dead ``dlt_retry`` module carried the repo's only failure
classifier but referenced the removed dlt 1.30 APIs (``LoadInfo.loads``
and the ``last_trace.last_trace`` chain) — its ``retry_failed``
AttributeError'd on every call and nothing imported it.  The
classification logic itself was sound; it is rebuilt here as the live
policy:

  * ``classify_failure`` — the error buckets (SCHEMA_MISMATCH /
    CONNECTION_ERROR / PERMISSION_DENIED / RESOURCE_EXHAUSTED /
    UNKNOWN).
  * ``is_retryable_error`` — ONLY the connection-class bucket
    (connection / timeout / refused / rate-limit) is retryable.
    Schema, permission, and resource-exhaustion failures are permanent
    — a retry cannot help them and wastes a run (fail-closed: the
    UNKNOWN bucket is permanent too).
  * ``call_with_bounded_retry`` — the canonical bounded loop
    (exponential backoff, capped; mirrors the repo's
    ``_stripe_call_with_retry`` shape): retryable exceptions are
    retried up to ``max_retries``; permanent exceptions re-raise
    immediately; the attempt count is returned so callers can record
    it.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when the retry bound is exhausted.

    Carries the attempt budget spent (``retry_count``) so callers can
    record it; ``str()`` delegates to the ORIGINAL error so the
    existing error-message contract is unchanged.
    """

    def __init__(self, retry_count: int, original: Exception):
        self.retry_count = retry_count
        self.original = original
        super().__init__(str(original))


SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
CONNECTION_ERROR = "CONNECTION_ERROR"
PERMISSION_DENIED = "PERMISSION_DENIED"
RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
UNKNOWN = "UNKNOWN"

# Only the connection-class bucket is retryable (F6): a transient
# transport failure can succeed on the next attempt; schema, permission,
# and resource failures cannot.
_RETRYABLE_CLASSES = frozenset({CONNECTION_ERROR})

MAX_RETRIES = 2  # three attempts total — the movement budget
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 8.0


def classify_failure(error: str) -> str:
    """Classify a failure message into one of the error buckets.

    Rebuilt from the dead ``dlt_retry.classify_failure`` (its logic was
    sound; its module was not — it referenced the removed dlt 1.30
    LoadInfo APIs).
    """
    error_lower = (error or "").lower()
    if "schema" in error_lower or "column" in error_lower or "type" in error_lower:
        return SCHEMA_MISMATCH
    if (
        "connection" in error_lower
        or "timeout" in error_lower
        or "refused" in error_lower
        or "timed out" in error_lower
        or "rate limit" in error_lower
        or "too many requests" in error_lower
    ):
        return CONNECTION_ERROR
    if (
        "permission" in error_lower
        or "access denied" in error_lower
        or "unauthorized" in error_lower
    ):
        return PERMISSION_DENIED
    if "memory" in error_lower or "oom" in error_lower or "killed" in error_lower:
        return RESOURCE_EXHAUSTED
    return UNKNOWN


def is_retryable_error(error: str) -> bool:
    """True when the failure class can succeed on a retry."""
    return classify_failure(error) in _RETRYABLE_CLASSES


def call_with_bounded_retry[T](
    func: Callable[[], T],
    *,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY_SECONDS,
    max_delay: float = MAX_DELAY_SECONDS,
    is_retryable: Callable[[Exception], bool] = lambda exc: is_retryable_error(str(exc)),
) -> tuple[T, int]:
    """Call ``func`` with BOUNDED retry on retryable exceptions.

    Returns ``(result, retry_count)``.  Retryable exceptions are retried
    up to ``max_retries`` times with capped exponential backoff;
    permanent exceptions re-raise immediately (zero retries).  The
    retry count lets callers record the actual attempt budget spent.
    """
    retry_count = 0
    for attempt in range(max_retries + 1):
        try:
            return func(), retry_count
        except Exception as exc:
            if attempt >= max_retries:
                raise RetryExhaustedError(retry_count, exc) from exc
            if not is_retryable(exc):
                raise
            retry_count += 1
            delay = min(base_delay * (2 ** (attempt)), max_delay)
            logger.warning(
                "dlt_retryable_failure_retrying: attempt=%d delay=%.1f error=%s",
                retry_count,
                delay,
                str(exc)[:300],
            )
            time.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover — loop always returns or raises
