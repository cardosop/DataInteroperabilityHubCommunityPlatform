"""
Tests for Error Recovery Mechanisms
"""
import time
from unittest.mock import patch, MagicMock

from django.test import TestCase

from hub.apps.core.error_handling.error_recovery import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    ErrorRecovery,
    RetryStrategy,
    with_circuit_breaker,
    with_retry,
)


class ErrorRecoveryTest(TestCase):
    """Test ErrorRecovery utilities."""
    
    def test_should_retry_retryable_exception(self):
        """Test should_retry with retryable exception."""
        exc = ConnectionError("Connection failed")
        
        should_retry = ErrorRecovery.should_retry(exc)
        
        self.assertTrue(should_retry)
    
    def test_should_retry_non_retryable_exception(self):
        """Test should_retry with non-retryable exception."""
        exc = ValueError("Invalid value")
        
        should_retry = ErrorRecovery.should_retry(exc)
        
        self.assertFalse(should_retry)
    
    def test_should_retry_custom_retryable(self):
        """Test should_retry with custom retryable exceptions."""
        class CustomRetryableError(Exception):
            pass
        
        exc = CustomRetryableError("Custom error")
        
        should_retry = ErrorRecovery.should_retry(
            exc,
            retryable_exceptions=[CustomRetryableError],
        )
        
        self.assertTrue(should_retry)
    
    def test_should_retry_with_retryable_attribute(self):
        """Test should_retry with exception that has retryable attribute."""
        class RetryableException(Exception):
            retryable = True
        
        exc = RetryableException("Retryable error")
        
        should_retry = ErrorRecovery.should_retry(exc)
        
        self.assertTrue(should_retry)
    
    def test_should_retry_with_non_retryable_attribute(self):
        """Test should_retry with exception that has retryable=False attribute."""
        class NonRetryableException(Exception):
            retryable = False
        
        exc = NonRetryableException("Non-retryable error")
        
        should_retry = ErrorRecovery.should_retry(exc)
        
        self.assertFalse(should_retry)
    
    def test_calculate_backoff_exponential(self):
        """Test exponential backoff calculation."""
        delay1 = ErrorRecovery.calculate_backoff(0, RetryStrategy.EXPONENTIAL_BACKOFF, base_delay=1.0)
        delay2 = ErrorRecovery.calculate_backoff(1, RetryStrategy.EXPONENTIAL_BACKOFF, base_delay=1.0)
        delay3 = ErrorRecovery.calculate_backoff(2, RetryStrategy.EXPONENTIAL_BACKOFF, base_delay=1.0)
        
        self.assertEqual(delay1, 1.0)  # 2^0 = 1
        self.assertEqual(delay2, 2.0)  # 2^1 = 2
        self.assertEqual(delay3, 4.0)  # 2^2 = 4
    
    def test_calculate_backoff_linear(self):
        """Test linear backoff calculation."""
        delay1 = ErrorRecovery.calculate_backoff(0, RetryStrategy.LINEAR_BACKOFF, base_delay=1.0)
        delay2 = ErrorRecovery.calculate_backoff(1, RetryStrategy.LINEAR_BACKOFF, base_delay=1.0)
        delay3 = ErrorRecovery.calculate_backoff(2, RetryStrategy.LINEAR_BACKOFF, base_delay=1.0)
        
        self.assertEqual(delay1, 1.0)  # 1 * 1
        self.assertEqual(delay2, 2.0)  # 1 * 2
        self.assertEqual(delay3, 3.0)  # 1 * 3
    
    def test_calculate_backoff_fixed(self):
        """Test fixed delay calculation."""
        delay1 = ErrorRecovery.calculate_backoff(0, RetryStrategy.FIXED_DELAY, base_delay=2.0)
        delay2 = ErrorRecovery.calculate_backoff(1, RetryStrategy.FIXED_DELAY, base_delay=2.0)
        delay3 = ErrorRecovery.calculate_backoff(2, RetryStrategy.FIXED_DELAY, base_delay=2.0)
        
        self.assertEqual(delay1, 2.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 2.0)
    
    def test_calculate_backoff_max_delay(self):
        """Test backoff respects max delay."""
        delay = ErrorRecovery.calculate_backoff(
            10,  # Large attempt number
            RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=10.0,
        )
        
        self.assertLessEqual(delay, 10.0)


class CircuitBreakerTest(TestCase):
    """Test CircuitBreaker class."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker()
        
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.success_count, 0)
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        self.assertEqual(result, "success")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)
    
    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # First 2 failures should not open circuit
        for _ in range(2):
            with self.assertRaises(ConnectionError):
                cb.call(failing_func)
        
        self.assertEqual(cb.state, CircuitState.CLOSED)
        
        # 3rd failure should open circuit
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertEqual(cb.failure_count, 3)
    
    def test_circuit_breaker_open_rejects_calls(self):
        """Test circuit breaker rejects calls when open."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # Open circuit
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        # Should reject calls
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call(failing_func)
    
    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker transitions to half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # Open circuit
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        self.assertEqual(cb.state, CircuitState.OPEN)
        
        # Wait for timeout
        time.sleep(0.2)  # INTENTIONAL: wait for circuit breaker timeout to expire
        
        # Should transition to half-open
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        self.assertEqual(result, "success")
    
    def test_circuit_breaker_closes_after_success_threshold(self):
        """Test circuit breaker closes after success threshold."""
        cb = CircuitBreaker(
            failure_threshold=1,
            success_threshold=2,
            timeout=0.1,
        )
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        def success_func():
            return "success"
        
        # Open circuit
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        # Wait for timeout
        time.sleep(0.2)  # INTENTIONAL: wait for circuit breaker timeout to expire
        
        # Success calls in half-open
        cb.call(success_func)
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        
        cb.call(success_func)
        self.assertEqual(cb.state, CircuitState.CLOSED)
    
    def test_circuit_breaker_failure_in_half_open(self):
        """Test circuit breaker opens again on failure in half-open."""
        cb = CircuitBreaker(failure_threshold=1, timeout=0.1)
        
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # Open circuit
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        # Wait for timeout
        time.sleep(0.2)  # INTENTIONAL: wait for circuit breaker timeout to expire
        
        # Failure in half-open should open again
        with self.assertRaises(ConnectionError):
            cb.call(failing_func)
        
        self.assertEqual(cb.state, CircuitState.OPEN)


class WithRetryDecoratorTest(TestCase):
    """Test with_retry decorator."""
    
    def test_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt."""
        @with_retry(max_attempts=3)
        def success_func():
            return "success"
        
        result = success_func()
        
        self.assertEqual(result, "success")
    
    def test_retry_succeeds_after_failures(self):
        """Test retry succeeds after initial failures."""
        attempt_count = [0]
        
        @with_retry(max_attempts=3, base_delay=0.01)
        def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = flaky_func()
        
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count[0], 2)
    
    def test_retry_exhausted(self):
        """Test retry exhausts all attempts."""
        attempt_count = [0]
        
        @with_retry(max_attempts=3, base_delay=0.01)
        def always_failing_func():
            attempt_count[0] += 1
            raise ConnectionError("Connection failed")
        
        with self.assertRaises(ConnectionError):
            always_failing_func()
        
        self.assertEqual(attempt_count[0], 3)
    
    def test_retry_non_retryable_exception(self):
        """Test retry doesn't retry non-retryable exceptions."""
        attempt_count = [0]
        
        @with_retry(max_attempts=3, base_delay=0.01)
        def non_retryable_func():
            attempt_count[0] += 1
            raise ValueError("Invalid value")
        
        with self.assertRaises(ValueError):
            non_retryable_func()
        
        # Should only attempt once
        self.assertEqual(attempt_count[0], 1)
    
    def test_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []
        
        def on_retry(exc, attempt):
            callback_calls.append((exc, attempt))
        
        attempt_count = [0]
        
        @with_retry(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = flaky_func()
        
        self.assertEqual(result, "success")
        self.assertEqual(len(callback_calls), 1)
        self.assertIsInstance(callback_calls[0][0], ConnectionError)
        self.assertEqual(callback_calls[0][1], 1)


class WithCircuitBreakerDecoratorTest(TestCase):
    """Test with_circuit_breaker decorator."""
    
    def test_circuit_breaker_decorator_success(self):
        """Test circuit breaker decorator with success."""
        @with_circuit_breaker(failure_threshold=3)
        def success_func():
            return "success"
        
        result = success_func()
        
        self.assertEqual(result, "success")
    
    def test_circuit_breaker_decorator_failure(self):
        """Test circuit breaker decorator with failure."""
        @with_circuit_breaker(failure_threshold=1)
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # First failure should raise exception
        with self.assertRaises(ConnectionError):
            failing_func()
        
        # Second call should raise CircuitBreakerOpenError
        with self.assertRaises(CircuitBreakerOpenError):
            failing_func()
    
    def test_circuit_breaker_decorator_custom_breaker(self):
        """Test circuit breaker decorator with custom breaker."""
        cb = CircuitBreaker(failure_threshold=1)
        
        @with_circuit_breaker(circuit_breaker=cb)
        def failing_func():
            raise ConnectionError("Connection failed")
        
        # Open circuit
        with self.assertRaises(ConnectionError):
            failing_func()
        
        # Should reject
        with self.assertRaises(CircuitBreakerOpenError):
            failing_func()

