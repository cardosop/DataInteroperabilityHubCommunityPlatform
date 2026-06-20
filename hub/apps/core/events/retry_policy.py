"""
Event Retry Policy

Configurable retry policies for event processing failures.

Features:
- Configurable retry strategies (exponential, linear, fixed)
- Configurable max retries
- Configurable backoff multipliers
- Per-event-type retry policies
- Jitter support for retry delays
"""

import random
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class RetryPolicy:
    """
    Configurable retry policy for event processing.

    Attributes:
        max_retries: Maximum number of retry attempts
        strategy: Retry strategy (exponential, linear, fixed)
        base_delay: Base delay in seconds for first retry
        max_delay: Maximum delay in seconds
        multiplier: Multiplier for exponential/linear strategies
        jitter: Whether to add random jitter to delays
        jitter_range: Range for jitter (0.0 to 1.0)
    """

    def __init__(
        self,
        max_retries: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        max_delay: float = 300.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        jitter_range: float = 0.1,
    ):
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            strategy: Retry strategy
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Multiplier for exponential/linear strategies
            jitter: Whether to add random jitter
            jitter_range: Range for jitter (0.0 to 1.0)
        """
        self.max_retries = max_retries
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.jitter_range = jitter_range

    def calculate_delay(self, retry_count: int) -> float:
        """
        Calculate delay for retry attempt.

        Args:
            retry_count: Current retry count (0-indexed)

        Returns:
            Delay in seconds
        """
        if retry_count <= 0:
            return self.base_delay

        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.multiplier**retry_count)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (1 + retry_count * self.multiplier)
        else:  # FIXED
            delay = self.base_delay

        # Apply max delay cap
        delay = min(delay, self.max_delay)

        # Apply jitter if enabled
        if self.jitter:
            jitter_amount = delay * self.jitter_range * random.uniform(-1, 1)
            delay = max(0, delay + jitter_amount)

        return delay

    def should_retry(self, retry_count: int, error: Exception | None = None) -> bool:
        """
        Determine if retry should be attempted.

        Args:
            retry_count: Current retry count
            error: Exception that occurred (optional)

        Returns:
            True if should retry, False otherwise
        """
        if retry_count >= self.max_retries:
            return False

        # Check if error is retryable
        if error:
            # Don't retry on certain error types
            error_type = type(error).__name__
            non_retryable_errors = [
                "ValidationError",
                "PermissionDenied",
                "AuthenticationFailed",
                "NotFound",
            ]
            if any(non_retryable in error_type for non_retryable in non_retryable_errors):
                return False

        return True


# Default retry policy
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=getattr(settings, "EVENT_BUS_MAX_RETRIES", 3),
    strategy=RetryStrategy.EXPONENTIAL,
    base_delay=1.0,
    max_delay=300.0,
    multiplier=2.0,
    jitter=True,
    jitter_range=0.1,
)

# Per-event-type retry policies (can be configured in settings)
EVENT_TYPE_RETRY_POLICIES: dict[str, RetryPolicy] = {}


def get_retry_policy(event_type: str) -> RetryPolicy:
    """
    Get retry policy for event type.

    Args:
        event_type: Event type

    Returns:
        Retry policy instance
    """
    # Check for event-type-specific policy
    if event_type in EVENT_TYPE_RETRY_POLICIES:
        return EVENT_TYPE_RETRY_POLICIES[event_type]

    # Check for pattern-based policies
    for pattern, policy in EVENT_TYPE_RETRY_POLICIES.items():
        if "*" in pattern:
            # Simple wildcard matching
            prefix = pattern[:-1]
            if event_type.startswith(prefix):
                return policy

    # Return default policy
    return DEFAULT_RETRY_POLICY


def configure_event_type_policy(event_type: str, policy: RetryPolicy) -> None:
    """
    Configure retry policy for specific event type.

    Args:
        event_type: Event type or pattern (supports wildcards)
        policy: Retry policy instance
    """
    EVENT_TYPE_RETRY_POLICIES[event_type] = policy
    logger.info(
        "retry_policy_configured",
        event_type=event_type,
        max_retries=policy.max_retries,
        strategy=policy.strategy.value,
    )


def retry_with_policy(func: Callable, event_type: str, *args, **kwargs) -> Any:
    """
    Execute function with retry policy.

    Args:
        func: Function to execute
        event_type: Event type for policy selection
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        Exception: If all retries exhausted
    """
    policy = get_retry_policy(event_type)
    retry_count = 0

    while True:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            retry_count += 1

            if not policy.should_retry(retry_count, e):
                logger.error(
                    "retry_exhausted",
                    event_type=event_type,
                    retry_count=retry_count,
                    max_retries=policy.max_retries,
                    error=str(e),
                )
                raise

            delay = policy.calculate_delay(retry_count - 1)
            logger.warning(
                "retry_attempt",
                event_type=event_type,
                retry_count=retry_count,
                max_retries=policy.max_retries,
                delay=delay,
                error=str(e),
            )

            time.sleep(delay)
