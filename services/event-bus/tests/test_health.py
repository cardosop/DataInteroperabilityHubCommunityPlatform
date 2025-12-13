"""
Integration tests for event bus health service.
"""
import pytest
import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from fastapi.testclient import TestClient
from django.test import TestCase
from unittest.mock import Mock, patch

# Import health app using importlib
import importlib.util
health_module_path = Path(__file__).parent.parent / "health.py"
spec = importlib.util.spec_from_file_location("event_bus_health", str(health_module_path))
health_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_module)
app = health_module.app


class EventBusHealthServiceTest(TestCase):
    """Test event bus health service endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_healthz_endpoint(self):
        """Test liveness probe endpoint."""
        response = self.client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "event-bus-service"
    
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_health_endpoint_healthy(self, mock_health_check):
        """Test health endpoint when healthy."""
        mock_health_check.return_value = {
            "status": "healthy",
            "checks": {
                "redis": {"status": "ok", "latency_ms": 1.5},
                "database": {"status": "ok"}
            }
        }
        
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_health_endpoint_unhealthy(self, mock_health_check):
        """Test health endpoint when unhealthy."""
        mock_health_check.return_value = {
            "status": "unhealthy",
            "checks": {
                "redis": {"status": "error", "error": "Connection failed"}
            }
        }
        
        response = self.client.get("/health")
        assert response.status_code == 503
    
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_ready_endpoint_ready(self, mock_health_check):
        """Test readiness probe when ready."""
        mock_health_check.return_value = {
            "status": "healthy",
            "checks": {
                "redis": {"status": "ok"},
                "database": {"status": "ok"}
            }
        }
        
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_ready_endpoint_not_ready(self, mock_health_check):
        """Test readiness probe when not ready."""
        mock_health_check.return_value = {
            "status": "unhealthy",
            "checks": {
                "redis": {"status": "error", "error": "Connection failed"}
            }
        }
        
        response = self.client.get("/ready")
        assert response.status_code == 503
    
    @patch.object(health_module.event_bus_client, 'get_connection_pool_stats')
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_metrics_endpoint(self, mock_health_check, mock_pool_stats):
        """Test Prometheus metrics endpoint."""
        mock_health_check.return_value = {
            "status": "healthy",
            "checks": {
                "redis": {"status": "ok", "latency_ms": 1.5}
            }
        }
        mock_pool_stats.return_value = {
            "created_connections": 5,
            "available_connections": 3,
            "in_use_connections": 2,
            "max_connections": 100,
            "connection_utilization": 5.0
        }
        
        response = self.client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        content = response.text
        assert "event_bus_redis_pool_created_connections" in content
        assert "event_bus_redis_pool_utilization_percent" in content
    
    @patch.object(health_module.event_bus_client, 'get_connection_pool_stats')
    @patch.object(health_module.event_bus_client, 'health_check')
    def test_stats_endpoint(self, mock_health_check, mock_pool_stats):
        """Test stats endpoint."""
        mock_health_check.return_value = {
            "status": "healthy",
            "checks": {"redis": {"status": "ok"}}
        }
        mock_pool_stats.return_value = {
            "created_connections": 5,
            "max_connections": 100
        }
        
        response = self.client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert "connection_pool" in data
        assert "health" in data
        assert "timestamp" in data

