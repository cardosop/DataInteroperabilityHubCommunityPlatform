"""
Unit tests for worker service health check endpoints (Phase 2.5).

Tests /healthz (liveness) and /ready (readiness) probes.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.db import connection
from django.core.cache import cache
from django.conf import settings

from services.worker.health import healthz, ready


pytestmark = pytest.mark.django_db(transaction=True)


class HealthzEndpointTest(TestCase):
    """Test /healthz endpoint (liveness probe) - Phase 2.5.1"""
    
    def test_healthz_returns_200_when_worker_running(self):
        """Test healthz returns 200 OK when worker process is running (2.5.1)"""
        status_code, content = healthz()
        
        self.assertEqual(status_code, 200)
        self.assertIn('status', content)
        self.assertEqual(content['status'], 'ok')
        self.assertIn('service', content)
        self.assertEqual(content['service'], 'worker-service')
        self.assertIn('timestamp', content)
    
    def test_healthz_returns_json_response(self):
        """Test healthz returns JSON response"""
        response = healthz(request=MagicMock())
        
        # Should return JsonResponse when request provided
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ok')
    
    def test_healthz_no_deep_checks(self):
        """Test healthz doesn't perform deep checks (just process running)"""
        # Healthz should return immediately without checking dependencies
        status_code, content = healthz()
        
        self.assertEqual(status_code, 200)
        # Should not have dependency checks
        self.assertNotIn('checks', content)
        self.assertNotIn('database', content)
        self.assertNotIn('redis', content)


class ReadyEndpointTest(TestCase):
    """Test /ready endpoint (readiness probe) - Phase 2.5.2"""
    
    def test_ready_returns_200_when_all_dependencies_ready(self):
        """Test ready returns 200 OK when all dependencies ready (2.5.2)"""
        status_code, content = ready()
        
        self.assertEqual(status_code, 200)
        self.assertIn('status', content)
        self.assertEqual(content['status'], 'ready')
        self.assertIn('checks', content)
        self.assertEqual(content['checks']['database'], 'ok')
        self.assertEqual(content['checks']['redis'], 'ok')
        self.assertEqual(content['checks']['cache'], 'ok')
    
    def test_ready_returns_503_when_database_unavailable(self):
        """Test ready returns 503 when database unavailable (2.5.2)"""
        with patch.object(connection, 'cursor') as mock_cursor:
            mock_cursor.side_effect = Exception("Database connection failed")
            
            status_code, content = ready()
            
            self.assertEqual(status_code, 503)
            self.assertEqual(content['status'], 'not_ready')
            self.assertIn('checks', content)
            self.assertIn('unhealthy', content['checks']['database'])
            self.assertIn('error', content)
    
    def test_ready_returns_503_when_redis_unavailable(self):
        """Test ready returns 503 when Redis unavailable (2.5.2)"""
        with patch('services.worker.health.redis') as mock_redis:
            mock_redis.from_url.side_effect = Exception("Redis connection failed")
            
            status_code, content = ready()
            
            self.assertEqual(status_code, 503)
            self.assertEqual(content['status'], 'not_ready')
            self.assertIn('checks', content)
            self.assertIn('unhealthy', content['checks']['redis'])
            self.assertIn('error', content)
    
    def test_ready_checks_database_connection(self):
        """Test ready checks database connection (2.5.2)"""
        with patch.object(connection, 'cursor') as mock_cursor:
            mock_cursor.return_value.__enter__.return_value.execute = MagicMock()
            
            status_code, content = ready()
            
            # Should have attempted database check
            mock_cursor.assert_called_once()
            self.assertIn('checks', content)
            self.assertIn('database', content['checks'])
    
    def test_ready_checks_redis_connection(self):
        """Test ready checks Redis connection (2.5.2)"""
        with patch('services.worker.health.redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_client
            
            status_code, content = ready()
            
            # Should have attempted Redis check
            mock_redis.from_url.assert_called_once()
            mock_client.ping.assert_called_once()
            self.assertIn('checks', content)
            self.assertIn('redis', content['checks'])
            self.assertEqual(content['checks']['redis'], 'ok')
    
    def test_ready_returns_json_response(self):
        """Test ready returns JSON response"""
        response = ready(request=MagicMock())
        
        # Should return JsonResponse when request provided
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ready')
        self.assertIn('checks', data)

