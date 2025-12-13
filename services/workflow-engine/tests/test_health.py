"""
Integration tests for workflow engine service health checks.
"""
import pytest
from django.test import TestCase
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis

# Import health check functions (use importlib to handle hyphen in module name)
import importlib.util
import os

health_module_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    'health.py'
)
spec = importlib.util.spec_from_file_location("health", health_module_path)
health_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_module)
healthz = health_module.healthz
ready = health_module.ready


class HealthCheckTest(TestCase):
    """Test health check endpoints."""
    
    def test_healthz_returns_ok(self):
        """Test that /healthz returns 200 OK."""
        status_code, response_data = healthz()
        
        assert status_code == 200
        assert response_data['status'] == 'ok'
        assert response_data['service'] == 'workflow-engine-service'
        assert 'timestamp' in response_data
    
    def test_ready_returns_ok_when_dependencies_available(self):
        """Test that /ready returns 200 OK when all dependencies are available."""
        status_code, response_data = ready()
        
        assert status_code == 200
        assert response_data['status'] == 'ready'
        assert response_data['service'] == 'workflow-engine-service'
        assert 'checks' in response_data
        assert response_data['checks']['database'] == 'ok'
        assert response_data['checks']['redis'] == 'ok'
        assert response_data['checks']['cache'] == 'ok'
        assert 'timestamp' in response_data
    
    def test_ready_handles_database_error(self):
        """Test that /ready handles database connection errors gracefully."""
        # Temporarily break database connection
        original_close = connection.close
        
        def broken_close():
            raise Exception("Database connection failed")
        
        connection.close = broken_close
        
        try:
            status_code, response_data = ready()
            
            # Should return 503 if database check fails
            assert status_code == 503
            assert response_data['status'] == 'not_ready'
            assert 'database' in response_data['checks']
            assert 'unhealthy' in response_data['checks']['database']
        finally:
            connection.close = original_close
    
    def test_ready_handles_redis_error(self):
        """Test that /ready handles Redis connection errors gracefully."""
        # Mock Redis connection failure
        original_from_url = redis.from_url
        
        def broken_from_url(url):
            raise redis.ConnectionError("Redis connection failed")
        
        redis.from_url = broken_from_url
        
        try:
            status_code, response_data = ready()
            
            # Should return 503 if Redis check fails
            assert status_code == 503
            assert response_data['status'] == 'not_ready'
            assert 'redis' in response_data['checks']
            assert 'unhealthy' in response_data['checks']['redis']
        finally:
            redis.from_url = original_from_url

