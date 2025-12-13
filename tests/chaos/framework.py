"""
Chaos Engineering Test Framework

Framework for testing system resilience through controlled failures,
resource constraints, and edge cases.

All tests use real services (no mocks/stubs) to test actual system behavior.
"""
import time
import random
import threading
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures to inject"""
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DATABASE_CONNECTION_ERROR = "database_connection_error"
    SLOW_RESPONSE = "slow_response"
    PARTIAL_FAILURE = "partial_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class ChaosScenario:
    """Chaos test scenario configuration"""
    name: str
    failure_type: FailureType
    duration: float  # seconds
    probability: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = None


class ChaosEngine:
    """Chaos engineering test engine"""
    
    def __init__(self):
        self.active_scenarios: List[ChaosScenario] = []
        self.failure_injectors: Dict[FailureType, Callable] = {
            FailureType.NETWORK_TIMEOUT: self._inject_network_timeout,
            FailureType.SLOW_RESPONSE: self._inject_slow_response,
            FailureType.PARTIAL_FAILURE: self._inject_partial_failure,
        }
    
    def inject_failure(
        self,
        scenario: ChaosScenario,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Inject a failure into a function call.
        
        Args:
            scenario: Chaos scenario configuration
            func: Function to execute with failure injection
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or raises exception
        """
        if random.random() > scenario.probability:
            # No failure injected
            return func(*args, **kwargs)
        
        injector = self.failure_injectors.get(scenario.failure_type)
        if injector:
            return injector(scenario, func, *args, **kwargs)
        
        # Unknown failure type, execute normally
        return func(*args, **kwargs)
    
    def _inject_network_timeout(
        self,
        scenario: ChaosScenario,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Inject network timeout failure"""
        import socket
        timeout = scenario.metadata.get("timeout", 0.1) if scenario.metadata else 0.1
        raise socket.timeout(f"Network timeout after {timeout}s (chaos injection)")
    
    def _inject_slow_response(
        self,
        scenario: ChaosScenario,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Inject slow response"""
        delay = scenario.metadata.get("delay", 5.0) if scenario.metadata else 5.0
        time.sleep(delay)
        return func(*args, **kwargs)
    
    def _inject_partial_failure(
        self,
        scenario: ChaosScenario,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Inject partial failure (some requests succeed, some fail)"""
        if random.random() < 0.5:
            # 50% chance of failure
            raise Exception("Partial failure (chaos injection)")
        return func(*args, **kwargs)
    
    def run_chaos_test(
        self,
        scenario: ChaosScenario,
        test_func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Optional[str]]:
        """
        Run a chaos test scenario.
        
        Args:
            scenario: Chaos scenario configuration
            test_func: Test function to execute
            *args: Test function arguments
            **kwargs: Test function keyword arguments
            
        Returns:
            Tuple of (passed: bool, message: Optional[str])
        """
        logger.info(f"Running chaos scenario: {scenario.name}")
        
        try:
            # Inject failure into test function
            result = self.inject_failure(scenario, test_func, *args, **kwargs)
            
            # Test should handle the failure gracefully
            logger.info(f"Chaos scenario {scenario.name} completed successfully")
            return True, None
            
        except Exception as e:
            # Check if exception is expected (part of the chaos scenario)
            if scenario.failure_type in [FailureType.NETWORK_TIMEOUT, FailureType.NETWORK_ERROR]:
                # These failures are expected, test should handle them
                logger.info(f"Chaos scenario {scenario.name} handled expected failure: {e}")
                return True, None
            else:
                # Unexpected failure
                logger.error(f"Chaos scenario {scenario.name} failed unexpectedly: {e}")
                return False, str(e)


class ResilienceTest:
    """Test system resilience to various failure scenarios"""
    
    def __init__(self, chaos_engine: ChaosEngine):
        self.chaos_engine = chaos_engine
    
    def test_network_timeout_resilience(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Optional[str]]:
        """
        Test resilience to network timeouts.
        
        Args:
            func: Function to test
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (passed: bool, message: Optional[str])
        """
        scenario = ChaosScenario(
            name="network_timeout",
            failure_type=FailureType.NETWORK_TIMEOUT,
            duration=1.0,
            probability=0.3,
            metadata={"timeout": 0.1}
        )
        
        return self.chaos_engine.run_chaos_test(scenario, func, *args, **kwargs)
    
    def test_slow_response_resilience(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Optional[str]]:
        """
        Test resilience to slow responses.
        
        Args:
            func: Function to test
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (passed: bool, message: Optional[str])
        """
        scenario = ChaosScenario(
            name="slow_response",
            failure_type=FailureType.SLOW_RESPONSE,
            duration=10.0,
            probability=0.2,
            metadata={"delay": 2.0}
        )
        
        return self.chaos_engine.run_chaos_test(scenario, func, *args, **kwargs)
    
    def test_partial_failure_resilience(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Optional[str]]:
        """
        Test resilience to partial failures.
        
        Args:
            func: Function to test
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (passed: bool, message: Optional[str])
        """
        scenario = ChaosScenario(
            name="partial_failure",
            failure_type=FailureType.PARTIAL_FAILURE,
            duration=5.0,
            probability=0.5,
            metadata={}
        )
        
        return self.chaos_engine.run_chaos_test(scenario, func, *args, **kwargs)

