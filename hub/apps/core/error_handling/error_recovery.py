"""
Error Recovery Mechanisms

Provides retry logic, circuit breakers, and other error recovery patterns.
"""
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class ErrorRecovery:
    """Error recovery utilities."""
    
    @staticmethod
    def should_retry(
        exception: Exception,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        non_retryable_exceptions: Optional[List[Type[Exception]]] = None,
    ) -> bool:
        """
        Determine if an exception should be retried.
        
        Args:
            exception: Exception instance
            retryable_exceptions: List of retryable exception types
            non_retryable_exceptions: List of non-retryable exception types
            
        Returns:
            True if should retry, False otherwise
        """
        # Default retryable exceptions
        if retryable_exceptions is None:
            retryable_exceptions = [
                ConnectionError,
                TimeoutError,
                OSError,  # Network errors
            ]
        
        # Default non-retryable exceptions
        if non_retryable_exceptions is None:
            non_retryable_exceptions = [
                ValueError,
                TypeError,
                AttributeError,
            ]
        
        # Check non-retryable first
        for exc_type in non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False
        
        # Check retryable
        for exc_type in retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        # Check if exception has retryable attribute
        if hasattr(exception, "retryable"):
            return exception.retryable
        
        # Default: don't retry
        return False
    
    @staticmethod
    def calculate_backoff(
        attempt: int,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> float:
        """
        Calculate backoff delay for retry.
        
        Args:
            attempt: Attempt number (0-indexed)
            strategy: Retry strategy
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds
        """
        if strategy == RetryStrategy.NO_RETRY:
            return 0.0
        
        if strategy == RetryStrategy.FIXED_DELAY:
            delay = base_delay
        elif strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = base_delay * (attempt + 1)
        elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = base_delay * (2 ** attempt)
        else:
            delay = base_delay
        
        # Cap at max delay
        return min(delay, max_delay)


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping requests to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "circuit_breaker",
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes to close circuit
            timeout: Timeout in seconds before trying half-open
            name: Circuit breaker name
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change_time = time.time()
    
    def call(self, func: Callable[[], T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If function raises exception
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_state_change_time >= self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change_time = time.time()
                logger.info(
                    "circuit_breaker_half_open",
                    name=self.name,
                    timeout=self.timeout,
                )
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Wait {self.timeout - (time.time() - self.last_state_change_time):.1f}s"
                )
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            
            # Success
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.last_state_change_time = time.time()
                    logger.info(
                        "circuit_breaker_closed",
                        name=self.name,
                        success_count=self.success_count,
                    )
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
            
            return result
            
        except Exception as e:
            # Failure
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self.state = CircuitState.OPEN
                self.last_state_change_time = time.time()
                logger.warning(
                    "circuit_breaker_opened_from_half_open",
                    name=self.name,
                    error=str(e),
                )
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change_time = time.time()
                    logger.error(
                        "circuit_breaker_opened",
                        name=self.name,
                        failure_count=self.failure_count,
                        threshold=self.failure_threshold,
                    )
            
            raise


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


def with_retry(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Optional[List[Type[Exception]]] = None,
    non_retryable_exceptions: Optional[List[Type[Exception]]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator to retry function on failure.
    
    Args:
        max_attempts: Maximum number of attempts
        strategy: Retry strategy
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        retryable_exceptions: List of retryable exception types
        non_retryable_exceptions: List of non-retryable exception types
        on_retry: Callback called on each retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if should retry
                    if not ErrorRecovery.should_retry(
                        e,
                        retryable_exceptions,
                        non_retryable_exceptions,
                    ):
                        raise
                    
                    # Check if more attempts remaining
                    if attempt < max_attempts - 1:
                        # Calculate backoff
                        delay = ErrorRecovery.calculate_backoff(
                            attempt,
                            strategy,
                            base_delay,
                            max_delay,
                        )
                        
                        # Call retry callback
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                        
                        # Wait before retry
                        time.sleep(delay)
                    else:
                        # No more attempts
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")
        
        return wrapper
    return decorator


def with_circuit_breaker(
    circuit_breaker: Optional[CircuitBreaker] = None,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0,
    name: Optional[str] = None,
):
    """
    Decorator to protect function with circuit breaker.
    
    Args:
        circuit_breaker: Circuit breaker instance (creates new if not provided)
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes to close circuit
        timeout: Timeout in seconds before trying half-open
        name: Circuit breaker name
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Create circuit breaker if not provided
        cb = circuit_breaker or CircuitBreaker(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            name=name or func.__name__,
        )
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return cb.call(func, *args, **kwargs)
        
        return wrapper
    return decorator

