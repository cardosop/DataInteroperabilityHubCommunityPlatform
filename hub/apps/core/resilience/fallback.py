"""
Fallback Mechanism Utilities

Provides fallback strategies for service resilience.
"""

from collections.abc import Callable
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class FallbackStrategy(Enum):
    """Fallback strategies."""

    RETURN_NONE = "RETURN_NONE"  # Return None on failure
    RETURN_DEFAULT = "RETURN_DEFAULT"  # Return default value
    RAISE_EXCEPTION = "RAISE_EXCEPTION"  # Raise exception (no fallback)
    CUSTOM_FUNCTION = "CUSTOM_FUNCTION"  # Use custom fallback function


class FallbackError(Exception):
    """Exception raised when fallback mechanism fails."""


def fallback(
    strategy: FallbackStrategy = FallbackStrategy.RETURN_NONE,
    default_value: Any = None,
    fallback_func: Callable | None = None,
) -> Callable:
    """
    Create fallback function based on strategy.

    Args:
        strategy: Fallback strategy to use
        default_value: Default value for RETURN_DEFAULT strategy
        fallback_func: Custom fallback function for CUSTOM_FUNCTION strategy

    Returns:
        Fallback function

    Raises:
        ValueError: If strategy requires function/value but none provided
    """
    if strategy == FallbackStrategy.RETURN_NONE:

        def fallback_none(*args, **kwargs):
            logger.warning("fallback_return_none", message="Fallback returning None")

        return fallback_none

    elif strategy == FallbackStrategy.RETURN_DEFAULT:

        def fallback_default(*args, **kwargs):
            logger.warning(
                "fallback_return_default",
                default_value=default_value,
                message="Fallback returning default value",
            )
            return default_value

        return fallback_default

    elif strategy == FallbackStrategy.RAISE_EXCEPTION:

        def fallback_raise(*args, **kwargs):
            logger.error("fallback_raise_exception", message="Fallback raising exception")
            raise FallbackError("Fallback strategy is RAISE_EXCEPTION")

        return fallback_raise

    elif strategy == FallbackStrategy.CUSTOM_FUNCTION:
        if fallback_func is None:
            raise ValueError("fallback_func required for CUSTOM_FUNCTION strategy")

        def fallback_custom(*args, **kwargs):
            logger.info("fallback_custom_function", message="Using custom fallback function")
            return fallback_func(*args, **kwargs)

        return fallback_custom

    else:
        raise ValueError(f"Unknown fallback strategy: {strategy}")
