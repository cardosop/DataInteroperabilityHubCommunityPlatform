"""
Circuit Breaker Implementation

Provides circuit breaker pattern for service resilience.
Prevents cascading failures by opening circuit after threshold failures.

Features:
- Three states: CLOSED, OPEN, HALF_OPEN
- Configurable failure threshold and timeout
- Redis-backed state storage for multi-instance deployments
- Thread-safe state management
- Decorator support for easy integration
- Fallback mechanism support
"""
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps

import structlog
import redis

logger = structlog.get_logger(__name__)

# Global registry for circuit breakers (for monitoring)
_circuit_breaker_registry: Dict[str, 'CircuitBreaker'] = {}
_registry_lock = threading.Lock()

# Import OpenTelemetry metrics
try:
    from hub.apps.observability.otel_metrics import get_meter
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    get_meter = None


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = 'CLOSED'      # Normal operation, allowing requests
    OPEN = 'OPEN'          # Circuit open, rejecting requests immediately
    HALF_OPEN = 'HALF_OPEN'  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get Redis client for circuit breaker state storage.

    Uses the shared cache connection pool to avoid per-call connection leaks.

    Returns:
        Redis client instance or None if unavailable
    """
    try:
        from hub.apps.core.redis_pools import get_redis_cache_client
        client = get_redis_cache_client()
        client.ping()
        return client
    except Exception as e:
        logger.warning(
            "circuit_breaker_redis_unavailable",
            error=str(e),
            message="Circuit breaker will use in-memory state only"
        )
        return None


class CircuitBreaker:
    """
    Circuit breaker implementation with Redis-backed state storage.

    Prevents cascading failures by opening circuit after threshold failures.
    Automatically transitions between CLOSED, OPEN, and HALF_OPEN states.

    Attributes:
        service_name: Name of the service being protected
        failure_threshold: Number of failures before opening circuit (default: 5)
        timeout_seconds: Seconds to wait before attempting HALF_OPEN (default: 60)
        success_threshold: Successes needed in HALF_OPEN to close circuit (default: 2)
        redis_client: Redis client for state storage (optional)
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            service_name: Name of the service being protected
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Seconds to wait before attempting HALF_OPEN
            success_threshold: Successes needed in HALF_OPEN to close circuit
            redis_client: Redis client for state storage (optional)
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold

        # Redis client for state storage
        self._redis_client = redis_client
        self._use_redis = redis_client is not None

        # In-memory state (fallback if Redis unavailable)
        self._local_state: Dict[str, Any] = {
            'state': CircuitBreakerState.CLOSED.value,
            'failure_count': 0,
            'success_count': 0,
            'opened_at': None,
        }
        self._local_lock = threading.RLock()

        # Redis key prefix
        self._redis_key_prefix = f"circuit_breaker:{service_name}"

        # Initialize OpenTelemetry metrics
        self._init_metrics()

        # Register circuit breaker for monitoring
        self._register()

    def _register(self) -> None:
        """Register circuit breaker in global registry for monitoring."""
        with _registry_lock:
            _circuit_breaker_registry[self.service_name] = self

    def _unregister(self) -> None:
        """Unregister circuit breaker from global registry."""
        with _registry_lock:
            _circuit_breaker_registry.pop(self.service_name, None)

    def _init_metrics(self) -> None:
        """Initialize OpenTelemetry metrics for circuit breaker."""
        if not OPENTELEMETRY_AVAILABLE:
            self._state_changes_counter = None
            self._failures_counter = None
            self._state_gauge = None
            return

        try:
            meter = get_meter()
            if meter is None:
                self._state_changes_counter = None
                self._failures_counter = None
                self._state_gauge = None
                return

            # Counter for state changes
            self._state_changes_counter = meter.create_counter(
                name='circuit_breaker_state_changes_total',
                description='Total number of circuit breaker state changes',
                unit='1'
            )

            # Counter for failures
            self._failures_counter = meter.create_counter(
                name='circuit_breaker_failures_total',
                description='Total number of circuit breaker failures',
                unit='1'
            )

            # Gauge for current state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
            self._state_gauge = meter.create_up_down_counter(
                name='circuit_breaker_state',
                description='Current circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)',
                unit='1'
            )
        except Exception as e:
            logger.warning(
                "circuit_breaker_metrics_init_error",
                error=str(e),
                service_name=self.service_name,
                message="Circuit breaker metrics not available"
            )
            self._state_changes_counter = None
            self._failures_counter = None
            self._state_gauge = None

    def _record_state_change(self, from_state: CircuitBreakerState, to_state: CircuitBreakerState) -> None:
        """Record circuit breaker state change metric."""
        if self._state_changes_counter is not None:
            try:
                self._state_changes_counter.add(
                    1,
                    attributes={
                        'service_name': self.service_name,
                        'from_state': from_state.value,
                        'to_state': to_state.value
                    }
                )
            except Exception as e:
                logger.warning(
                    "circuit_breaker_metrics_error",
                    error=str(e),
                    service_name=self.service_name,
                    metric="state_changes_total"
                )

    def _record_failure(self) -> None:
        """Record circuit breaker failure metric."""
        if self._failures_counter is not None:
            try:
                self._failures_counter.add(
                    1,
                    attributes={
                        'service_name': self.service_name,
                        'state': self._get_state().value
                    }
                )
            except Exception as e:
                logger.warning(
                    "circuit_breaker_metrics_error",
                    error=str(e),
                    service_name=self.service_name,
                    metric="failures_total"
                )

    def _update_state_gauge(self, state: CircuitBreakerState) -> None:
        """Update circuit breaker state gauge metric."""
        if self._state_gauge is not None:
            try:
                # Map state to numeric value: CLOSED=0, HALF_OPEN=1, OPEN=2
                state_value = {
                    CircuitBreakerState.CLOSED: 0,
                    CircuitBreakerState.HALF_OPEN: 1,
                    CircuitBreakerState.OPEN: 2
                }.get(state, 0)

                # Set gauge value (reset to 0 first, then set to new value)
                # For each service, we need to track previous value
                if not hasattr(self, '_previous_gauge_value'):
                    self._previous_gauge_value = 0

                # Reset previous value
                if self._previous_gauge_value != 0:
                    self._state_gauge.add(
                        -self._previous_gauge_value,
                        attributes={'service_name': self.service_name}
                    )

                # Set new value
                if state_value != 0:
                    self._state_gauge.add(
                        state_value,
                        attributes={'service_name': self.service_name}
                    )

                self._previous_gauge_value = state_value
            except Exception as e:
                logger.warning(
                    "circuit_breaker_metrics_error",
                    error=str(e),
                    service_name=self.service_name,
                    metric="state_gauge"
                )

    @property
    def redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with lazy initialization."""
        if self._redis_client is None:
            self._redis_client = get_redis_client()
            self._use_redis = self._redis_client is not None
        return self._redis_client

    def _get_state_key(self) -> str:
        """Get Redis key for state storage."""
        return f"{self._redis_key_prefix}:state"

    def _get_state(self) -> CircuitBreakerState:
        """
        Get current circuit breaker state.

        Returns:
            Current state (CLOSED, OPEN, or HALF_OPEN)
        """
        if self._use_redis and self.redis_client:
            try:
                state_data = self.redis_client.get(self._get_state_key())
                if state_data:
                    data = json.loads(state_data)
                    state = CircuitBreakerState(data.get('state', 'CLOSED'))
                    # Update local state cache
                    with self._local_lock:
                        self._local_state['state'] = state.value
                    return state
                else:
                    # Redis key doesn't exist - default to CLOSED and update local state
                    with self._local_lock:
                        self._local_state['state'] = CircuitBreakerState.CLOSED.value
                    return CircuitBreakerState.CLOSED
            except Exception as e:
                logger.warning(
                    "circuit_breaker_redis_read_error",
                    error=str(e),
                    service_name=self.service_name,
                    message="Falling back to local state"
                )
                self._use_redis = False

        # Fallback to local state
        with self._local_lock:
            return CircuitBreakerState(self._local_state['state'])

    def _set_state(self, state: CircuitBreakerState) -> None:
        """
        Set circuit breaker state.

        Args:
            state: New state to set
        """
        # Get current state for metrics
        current_state = self._get_state()
        state_changed = current_state != state

        if self._use_redis and self.redis_client:
            try:
                state_data = json.dumps({
                    'state': state.value,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
                self.redis_client.set(self._get_state_key(), state_data)
            except Exception as e:
                logger.warning(
                    "circuit_breaker_redis_write_error",
                    error=str(e),
                    service_name=self.service_name,
                    message="Falling back to local state"
                )
                self._use_redis = False

        # Update local state
        with self._local_lock:
            self._local_state['state'] = state.value
            # Also clear opened_at if state is CLOSED
            if state == CircuitBreakerState.CLOSED:
                self._local_state['opened_at'] = None

        # Record metrics and logging for state changes
        if state_changed:
            self._record_state_change(current_state, state)
            self._update_state_gauge(state)

            logger.info(
                "circuit_breaker_state_changed",
                service_name=self.service_name,
                from_state=current_state.value,
                to_state=state.value,
                failure_threshold=self.failure_threshold,
                timeout_seconds=self.timeout_seconds,
                success_threshold=self.success_threshold
            )

    def _get_failure_count(self) -> int:
        """Get current failure count."""
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:failure_count"
                count = self.redis_client.get(count_key)
                return int(count) if count else 0
            except Exception:
                pass

        with self._local_lock:
            return self._local_state.get('failure_count', 0)

    def _increment_failure_count(self) -> int:
        """
        Increment failure count atomically.

        Returns:
            New failure count
        """
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:failure_count"
                new_count = self.redis_client.incr(count_key)
                # Set expiration to prevent stale data
                self.redis_client.expire(count_key, self.timeout_seconds * 2)
                return new_count
            except Exception:
                pass

        with self._local_lock:
            self._local_state['failure_count'] = self._local_state.get('failure_count', 0) + 1
            return self._local_state['failure_count']

    def _reset_failure_count(self) -> None:
        """Reset failure count to zero."""
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:failure_count"
                self.redis_client.delete(count_key)
            except Exception:
                pass

        with self._local_lock:
            self._local_state['failure_count'] = 0

    def _get_success_count(self) -> int:
        """Get current success count (for HALF_OPEN state)."""
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:success_count"
                count = self.redis_client.get(count_key)
                return int(count) if count else 0
            except Exception:
                pass

        with self._local_lock:
            return self._local_state.get('success_count', 0)

    def _increment_success_count(self) -> int:
        """
        Increment success count atomically.

        Returns:
            New success count
        """
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:success_count"
                new_count = self.redis_client.incr(count_key)
                # Set expiration
                self.redis_client.expire(count_key, self.timeout_seconds * 2)
                return new_count
            except Exception:
                pass

        with self._local_lock:
            self._local_state['success_count'] = self._local_state.get('success_count', 0) + 1
            return self._local_state['success_count']

    def _reset_success_count(self) -> None:
        """Reset success count to zero."""
        if self._use_redis and self.redis_client:
            try:
                count_key = f"{self._redis_key_prefix}:success_count"
                self.redis_client.delete(count_key)
            except Exception:
                pass

        with self._local_lock:
            self._local_state['success_count'] = 0

    def _get_opened_at(self) -> Optional[datetime]:
        """Get timestamp when circuit was opened."""
        if self._use_redis and self.redis_client:
            try:
                timestamp_key = f"{self._redis_key_prefix}:opened_at"
                timestamp_str = self.redis_client.get(timestamp_key)
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str)
                    # Ensure timezone-aware datetime
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
            except Exception:
                pass

        with self._local_lock:
            opened_at_str = self._local_state.get('opened_at')
            if opened_at_str:
                dt = datetime.fromisoformat(opened_at_str)
                # Ensure timezone-aware datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            return None

    def _set_opened_at(self, timestamp: Optional[datetime] = None) -> None:
        """
        Set timestamp when circuit was opened.

        Args:
            timestamp: Timestamp to set (default: current time)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        else:
            # Ensure timezone-aware datetime
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

        timestamp_str = timestamp.isoformat()

        if self._use_redis and self.redis_client:
            try:
                timestamp_key = f"{self._redis_key_prefix}:opened_at"
                self.redis_client.set(timestamp_key, timestamp_str)
                self.redis_client.expire(timestamp_key, self.timeout_seconds * 2)
            except Exception:
                pass

        with self._local_lock:
            self._local_state['opened_at'] = timestamp_str

    def _clear_opened_at(self) -> None:
        """Clear opened_at timestamp."""
        if self._use_redis and self.redis_client:
            try:
                timestamp_key = f"{self._redis_key_prefix}:opened_at"
                self.redis_client.delete(timestamp_key)
            except Exception:
                pass

        with self._local_lock:
            self._local_state['opened_at'] = None

    def get_state(self) -> CircuitBreakerState:
        """
        Get current circuit breaker state.

        Returns:
            Current state
        """
        return self._get_state()

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive circuit breaker status for monitoring.

        Returns:
            Dictionary with circuit breaker status information
        """
        state = self._get_state()
        failure_count = self._get_failure_count()
        success_count = self._get_success_count()
        opened_at = self._get_opened_at()

        status = {
            'service_name': self.service_name,
            'state': state.value,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'timeout_seconds': self.timeout_seconds,
            'failure_count': failure_count,
            'success_count': success_count,
            'opened_at': opened_at.isoformat() if opened_at else None,
            'use_redis': self._use_redis,
        }

        # Add elapsed time if circuit is open
        if state == CircuitBreakerState.OPEN and opened_at:
            elapsed_seconds = (datetime.now(timezone.utc) - opened_at).total_seconds()
            remaining_seconds = max(0, self.timeout_seconds - elapsed_seconds)
            status['elapsed_seconds'] = elapsed_seconds
            status['remaining_seconds'] = remaining_seconds

        return status

    def _should_attempt_half_open(self) -> bool:
        """
        Check if circuit should transition from OPEN to HALF_OPEN.

        Returns:
            True if timeout has elapsed, False otherwise
        """
        opened_at = self._get_opened_at()
        if opened_at is None:
            return False

        elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds()
        return elapsed >= self.timeout_seconds

    def call(
        self,
        func: Callable,
        *args,
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            fallback: Optional fallback function if circuit is open or function fails
            **kwargs: Keyword arguments for function

        Returns:
            Result from function or fallback

        Raises:
            CircuitBreakerError: If circuit is open and no fallback provided
            Exception: If function raises exception and no fallback provided
        """
        # Phase 91.12: Acquire lock for the state-check + transition to
        # eliminate the TOCTOU race where two threads both read OPEN,
        # both decide to transition to HALF_OPEN, and both attempt the
        # probe request concurrently.
        with self._local_lock:
            current_state = self._get_state()

            # Handle OPEN state
            if current_state == CircuitBreakerState.OPEN:
                if self._should_attempt_half_open():
                    # Transition to HALF_OPEN
                    opened_at = self._get_opened_at()
                    elapsed_seconds = (datetime.now(timezone.utc) - opened_at).total_seconds() if opened_at else 0

                    logger.info(
                        "circuit_breaker_half_open_transition",
                        service_name=self.service_name,
                        timeout_seconds=self.timeout_seconds,
                        elapsed_seconds=elapsed_seconds,
                        message="Attempting HALF_OPEN after timeout"
                    )
                    self._set_state(CircuitBreakerState.HALF_OPEN)
                    self._reset_success_count()
                    current_state = CircuitBreakerState.HALF_OPEN
                else:
                    # Circuit still open - use fallback or raise error
                    opened_at = self._get_opened_at()
                    elapsed_seconds = (datetime.now(timezone.utc) - opened_at).total_seconds() if opened_at else 0
                    remaining_seconds = max(0, self.timeout_seconds - elapsed_seconds)

                    logger.debug(
                        "circuit_breaker_open_reject",
                        service_name=self.service_name,
                        elapsed_seconds=elapsed_seconds,
                        remaining_seconds=remaining_seconds,
                        timeout_seconds=self.timeout_seconds
                    )

                    if fallback:
                        logger.info(
                            "circuit_breaker_fallback",
                            service_name=self.service_name,
                            state="OPEN",
                            message="Using fallback function"
                        )
                        return fallback(*args, **kwargs)
                    else:
                        raise CircuitBreakerError(
                            f"Circuit breaker is OPEN for service '{self.service_name}'. "
                            f"Service unavailable. Retry after {remaining_seconds:.0f} seconds."
                        )
        # Lock released — execute the actual function outside the lock
        # to avoid holding it during potentially slow I/O.

        # Execute function
        try:
            result = func(*args, **kwargs)

            # Success - handle state transitions (under lock for atomicity)
            with self._local_lock:
                if current_state == CircuitBreakerState.HALF_OPEN:
                    success_count = self._increment_success_count()
                    logger.debug(
                        "circuit_breaker_half_open_success",
                        service_name=self.service_name,
                        success_count=success_count,
                        success_threshold=self.success_threshold
                    )

                    if success_count >= self.success_threshold:
                        logger.info(
                            "circuit_breaker_closed_transition",
                            service_name=self.service_name,
                            success_count=success_count,
                            success_threshold=self.success_threshold,
                            message="Circuit breaker CLOSED after success threshold"
                        )
                        self._set_state(CircuitBreakerState.CLOSED)
                        self._reset_failure_count()
                        self._reset_success_count()
                        self._clear_opened_at()
                elif current_state == CircuitBreakerState.CLOSED:
                    self._reset_failure_count()
                    logger.debug(
                        "circuit_breaker_success",
                        service_name=self.service_name,
                        state="CLOSED"
                    )

            return result

        except Exception as e:
            # Failure - handle state transitions (under lock)
            use_fallback = False
            raise_breaker_error = False

            with self._local_lock:
                failure_count = self._increment_failure_count()
                self._record_failure()

                logger.warning(
                    "circuit_breaker_failure",
                    service_name=self.service_name,
                    state=current_state.value,
                    failure_count=failure_count,
                    failure_threshold=self.failure_threshold,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if current_state == CircuitBreakerState.HALF_OPEN:
                    logger.warning(
                        "circuit_breaker_opened_from_half_open",
                        service_name=self.service_name,
                        error=str(e),
                        error_type=type(e).__name__,
                        timeout_seconds=self.timeout_seconds,
                        message="Circuit breaker OPENED from HALF_OPEN on failure"
                    )
                    self._set_state(CircuitBreakerState.OPEN)
                    self._set_opened_at()
                    self._reset_success_count()

                    if fallback:
                        use_fallback = True
                    else:
                        raise_breaker_error = True

                elif current_state == CircuitBreakerState.CLOSED:
                    if failure_count >= self.failure_threshold:
                        logger.warning(
                            "circuit_breaker_opened",
                            service_name=self.service_name,
                            failure_count=failure_count,
                            threshold=self.failure_threshold,
                            error=str(e),
                            error_type=type(e).__name__,
                            timeout_seconds=self.timeout_seconds,
                            message="Circuit breaker OPENED after failure threshold"
                        )
                        self._set_state(CircuitBreakerState.OPEN)
                        self._set_opened_at()

                        # Only use fallback when circuit just opened (threshold reached).
                        # Below-threshold failures should propagate the real error
                        # so callers can handle specific HTTP errors (e.g. 400 vs 503).
                        if fallback:
                            use_fallback = True

            # Act on decisions made under lock (outside the lock)
            if use_fallback:
                return fallback(*args, **kwargs)
            if raise_breaker_error:
                raise CircuitBreakerError(
                    f"Circuit breaker is OPEN for service '{self.service_name}'. "
                    f"Service unavailable. Retry after {self.timeout_seconds} seconds."
                )

            # Re-raise original exception
            raise

    def reset(self) -> None:
        """
        Reset circuit breaker to CLOSED state.

        Clears all state including failure counts and timestamps.
        """
        logger.info(
            "circuit_breaker_reset",
            service_name=self.service_name,
            message="Circuit breaker reset to CLOSED"
        )

        self._set_state(CircuitBreakerState.CLOSED)
        self._reset_failure_count()
        self._reset_success_count()
        self._clear_opened_at()

        # Clean up Redis keys
        if self._use_redis and self.redis_client:
            try:
                pattern = f"{self._redis_key_prefix}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass


def reset_circuit_breaker_by_name(service_name: str) -> None:
    """
    Reset circuit breaker state by service name.

    Clears Redis state and any in-memory state so the next client sees CLOSED.
    Intended for test isolation so one test's failures do not leave the circuit
    OPEN for subsequent tests (e.g. webhook-delivery).
    """
    from hub.apps.core.resilience.service_breakers import (
        get_shared_circuit_breaker,
        reset_shared_circuit_breakers_for_service,
    )

    reset_shared_circuit_breakers_for_service(service_name)
    get_shared_circuit_breaker(service_name).reset()


def get_all_circuit_breakers() -> Dict[str, 'CircuitBreaker']:
    """
    Get all registered circuit breakers for monitoring.

    Returns:
        Dictionary mapping service names to CircuitBreaker instances
    """
    with _registry_lock:
        return _circuit_breaker_registry.copy()


def get_circuit_breaker_status(service_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get circuit breaker status for monitoring.

    Args:
        service_name: Optional service name to get status for specific breaker.
                     If None, returns status for all breakers.

    Returns:
        Dictionary with circuit breaker status(es)
    """
    if service_name:
        with _registry_lock:
            breaker = _circuit_breaker_registry.get(service_name)
            if breaker:
                return breaker.get_status()
            return {'error': f'Circuit breaker not found for service: {service_name}'}
    else:
        # Return status for all circuit breakers
        with _registry_lock:
            return {
                service_name: breaker.get_status()
                for service_name, breaker in _circuit_breaker_registry.items()
            }


def circuit_breaker(
    service_name: str,
    failure_threshold: int = 5,
    timeout_seconds: int = 60,
    success_threshold: int = 2,
    redis_client: Optional[redis.Redis] = None,
    fallback: Optional[Callable] = None
):
    """
    Decorator for circuit breaker pattern.

    Usage:
        @circuit_breaker(service_name="my_service")
        def my_function():
            # function implementation
            pass

    Args:
        service_name: Name of the service being protected
        failure_threshold: Number of failures before opening circuit
        timeout_seconds: Seconds to wait before attempting HALF_OPEN
        success_threshold: Successes needed in HALF_OPEN to close circuit
        redis_client: Deprecated; shared breakers use the cache Redis pool.
        fallback: Optional fallback function

    Returns:
        Decorated function
    """
    _ = redis_client  # backward-compat signature; shared breaker uses cache Redis pool

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from hub.apps.core.resilience.service_breakers import (
                get_shared_circuit_breaker,
            )

            br = get_shared_circuit_breaker(
                service_name,
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds,
                success_threshold=success_threshold,
            )
            return br.call(func, *args, fallback=fallback, **kwargs)

        return wrapper

    return decorator

