"""
Integration tests for monitoring infrastructure

Tests verify that monitoring services (Prometheus, Grafana, Jaeger)
are properly configured and accessible.
"""
import pytest
import requests
import os
from django.test import TestCase


class MonitoringInfrastructureTest(TestCase):
    """Test monitoring infrastructure setup"""
    
    def setUp(self):
        """Set up test configuration"""
        # These tests require services to be running
        # They will be skipped if services are not available
        self.prometheus_url = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
        self.grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')
        self.jaeger_url = os.getenv('JAEGER_URL', 'http://localhost:16686')
        self.timeout = 5  # seconds
    
    def _check_service_available(self, url):
        """Check if a service is available"""
        try:
            response = requests.get(url, timeout=self.timeout)
            return response.status_code in [200, 401, 403]  # 401/403 means service is up
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            return False
    
    def test_prometheus_available(self):
        """Test that Prometheus is available"""
        if not self._check_service_available(self.prometheus_url):
            pytest.skip("Prometheus not available")
        
        # Verify Prometheus is responding
        try:
            response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=self.timeout)
            self.assertEqual(response.status_code, 200)
        except requests.exceptions.RequestException:
            pytest.skip("Prometheus not accessible")
    
    def test_prometheus_configuration(self):
        """Test that Prometheus configuration is valid"""
        # Verify configuration file exists
        config_path = 'monitoring/prometheus/prometheus.yml'
        self.assertTrue(os.path.exists(config_path), "Prometheus config should exist")
        
        # Verify alerts file exists
        alerts_path = 'monitoring/prometheus/alerts.yml'
        self.assertTrue(os.path.exists(alerts_path), "Alerts config should exist")
    
    def test_grafana_available(self):
        """Test that Grafana is available"""
        if not self._check_service_available(self.grafana_url):
            pytest.skip("Grafana not available")
        
        # Verify Grafana is responding
        try:
            response = requests.get(f"{self.grafana_url}/api/health", timeout=self.timeout)
            self.assertIn(response.status_code, [200, 401, 403])
        except requests.exceptions.RequestException:
            pytest.skip("Grafana not accessible")
    
    def test_grafana_dashboards_exist(self):
        """Test that Grafana dashboards are created"""
        dashboard_dir = 'monitoring/grafana/dashboards'
        self.assertTrue(os.path.exists(dashboard_dir), "Dashboards directory should exist")
        
        # Verify required dashboards exist
        required_dashboards = [
            'system-health.json',
            'api-performance.json',
            'job-processing.json',
            'tenant-usage.json',
            'database-performance.json'
        ]
        
        for dashboard in required_dashboards:
            dashboard_path = os.path.join(dashboard_dir, dashboard)
            self.assertTrue(
                os.path.exists(dashboard_path),
                f"Dashboard {dashboard} should exist"
            )
    
    def test_grafana_datasource_configuration(self):
        """Test that Grafana datasource is configured"""
        datasource_path = 'monitoring/grafana/datasources/prometheus.yml'
        self.assertTrue(
            os.path.exists(datasource_path),
            "Grafana datasource config should exist"
        )
    
    def test_jaeger_available(self):
        """Test that Jaeger is available"""
        if not self._check_service_available(self.jaeger_url):
            pytest.skip("Jaeger not available")
        
        # Verify Jaeger UI is responding
        try:
            response = requests.get(self.jaeger_url, timeout=self.timeout)
            self.assertIn(response.status_code, [200, 401, 403])
        except requests.exceptions.RequestException:
            pytest.skip("Jaeger not accessible")
    
    def test_alertmanager_configuration(self):
        """Test that Alertmanager is configured"""
        # Verify configuration file exists
        config_path = 'monitoring/alertmanager/alertmanager.yml'
        self.assertTrue(
            os.path.exists(config_path),
            "Alertmanager config should exist"
        )
    
    def test_docker_compose_services(self):
        """Test that docker-compose includes monitoring services"""
        # Verify docker-compose.yml exists
        compose_path = 'docker-compose.yml'
        self.assertTrue(os.path.exists(compose_path), "docker-compose.yml should exist")
        
        # Read docker-compose.yml to verify services
        with open(compose_path, 'r') as f:
            content = f.read()
        
        # Verify monitoring services are defined
        self.assertIn('prometheus:', content, "Prometheus service should be defined")
        self.assertIn('grafana:', content, "Grafana service should be defined")
        self.assertIn('jaeger:', content, "Jaeger service should be defined")
        self.assertIn('alertmanager:', content, "Alertmanager service should be defined")
    
    def test_prometheus_scrape_configs(self):
        """Test that Prometheus scrape configs include all services"""
        config_path = 'monitoring/prometheus/prometheus.yml'
        if not os.path.exists(config_path):
            pytest.skip("Prometheus config not found")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Verify all services are configured
        required_services = [
            'api-service',
            'worker-service',
            'semantic-service',
            'dq-service',
            'compliance-service',
            'datacontract-service'
        ]
        
        for service in required_services:
            self.assertIn(
                service,
                content,
                f"Service {service} should be in Prometheus scrape configs"
            )

