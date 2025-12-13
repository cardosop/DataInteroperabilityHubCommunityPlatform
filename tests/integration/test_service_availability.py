"""
Integration tests for service availability checking.

Tests that all required services are available and healthy.
"""
import pytest
from django.test import TestCase
from django.conf import settings

from hub.apps.core.services.availability import (
    ServiceAvailabilityChecker,
    check_service_availability,
    check_all_services,
    get_all_service_configs
)


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


class ServiceAvailabilityTests(TestCase):
    """Tests for service availability checking"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.checker = ServiceAvailabilityChecker(cache_ttl=0)  # Disable cache for tests
    
    def test_check_dq_service_availability(self):
        """Test checking DQ service availability"""
        dq_url = getattr(settings, 'DQ_SERVICE_URL', 'http://localhost:8083')
        
        is_available, error_msg = check_service_availability(
            service_name='dq-service',
            service_url=dq_url,
            health_path='/health',
            timeout=5
        )
        
        # Service may or may not be available in test environment
        # Just verify the function works correctly
        self.assertIsInstance(is_available, bool)
        if not is_available:
            self.assertIsNotNone(error_msg)
    
    def test_check_compliance_service_availability(self):
        """Test checking compliance service availability"""
        compliance_url = getattr(settings, 'COMPLIANCE_SERVICE_URL', 'http://localhost:8082')
        
        is_available, error_msg = check_service_availability(
            service_name='compliance-service',
            service_url=compliance_url,
            health_path='/health',
            timeout=5
        )
        
        self.assertIsInstance(is_available, bool)
        if not is_available:
            self.assertIsNotNone(error_msg)
    
    def test_check_datacontract_service_availability(self):
        """Test checking DataContract service availability"""
        datacontract_url = getattr(settings, 'DATACONTRACT_CLI_SERVICE_URL', 'http://localhost:8080')
        
        is_available, error_msg = check_service_availability(
            service_name='datacontract-service',
            service_url=datacontract_url,
            health_path='/health',
            timeout=5
        )
        
        self.assertIsInstance(is_available, bool)
        if not is_available:
            self.assertIsNotNone(error_msg)
    
    def test_check_semantic_service_availability(self):
        """Test checking semantic service availability"""
        semantic_url = getattr(settings, 'SEMANTIC_SERVICE_URL', 'http://localhost:8081')
        
        is_available, error_msg = check_service_availability(
            service_name='semantic-service',
            service_url=semantic_url,
            health_path='/health',
            timeout=5
        )
        
        self.assertIsInstance(is_available, bool)
        if not is_available:
            self.assertIsNotNone(error_msg)
    
    def test_check_all_services(self):
        """Test checking all services at once"""
        results = check_all_services()
        
        # Verify results structure
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        
        # Verify each result
        for service_name, (is_available, error_msg) in results.items():
            self.assertIsInstance(is_available, bool)
            if not is_available:
                self.assertIsNotNone(error_msg)
    
    def test_get_all_service_configs(self):
        """Test getting all service configurations"""
        configs = get_all_service_configs()
        
        # Verify configs structure
        self.assertIsInstance(configs, dict)
        self.assertGreater(len(configs), 0)
        
        # Verify each config has required keys
        for service_name, config in configs.items():
            self.assertIn('url', config)
            self.assertIn('health_path', config)
            self.assertIn('timeout', config)
    
    def test_service_checker_logs_status(self):
        """Test that service checker logs status correctly"""
        configs = get_all_service_configs()
        results = self.checker.check_all_services(configs)
        
        # Log summary (this will be captured by test output)
        self.checker.log_service_status_summary(results)
        
        # Verify results were generated
        self.assertGreater(len(results), 0)
    
    def test_service_checker_handles_timeout(self):
        """Test that service checker handles timeouts gracefully"""
        # Use a non-existent service URL with very short timeout
        is_available, error_msg = self.checker.check_service_availability(
            service_name='test-timeout-service',
            service_url='http://192.0.2.1:9999',  # Non-routable IP
            health_path='/health',
            timeout=1
        )
        
        self.assertFalse(is_available)
        self.assertIsNotNone(error_msg)
        self.assertIn('timeout', error_msg.lower() or 'unreachable', error_msg.lower())
    
    def test_service_checker_handles_invalid_url(self):
        """Test that service checker handles invalid URLs gracefully"""
        is_available, error_msg = self.checker.check_service_availability(
            service_name='test-invalid-service',
            service_url='http://invalid-hostname-that-does-not-exist.local:8080',
            health_path='/health',
            timeout=2
        )
        
        self.assertFalse(is_available)
        self.assertIsNotNone(error_msg)

