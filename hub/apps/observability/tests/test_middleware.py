"""
Unit tests for metrics middleware.
"""
import pytest
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from unittest.mock import Mock, patch
import time

from hub.apps.observability.middleware import MetricsMiddleware
from hub.apps.observability.otel_metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_errors_total,
)


pytestmark = pytest.mark.django_db(transaction=True)


class MetricsMiddlewareTest(TestCase):
    """Test MetricsMiddleware"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = MetricsMiddleware(self.get_response)
    
    def test_middleware_is_callable(self):
        """Test that middleware is callable (Django 6 pattern)"""
        request = self.factory.get("/api/v1/assets/")
        response = self.middleware(request)
        
        self.assertIsNotNone(response)
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()
    
    def test_records_request_start_time(self):
        """Test that middleware records request start time"""
        request = self.factory.get("/api/v1/assets/")
        
        self.middleware.process_request(request)
        
        self.assertTrue(hasattr(request, '_metrics_start_time'))
        self.assertIsInstance(request._metrics_start_time, float)
    
    def test_records_http_metrics(self):
        """Test that middleware records HTTP request metrics"""
        request = self.factory.get("/api/v1/assets/")
        response = HttpResponse()
        response.status_code = 200
        
        # Mock the metrics objects
        mock_counter = Mock()
        mock_histogram = Mock()
        
        with patch('hub.apps.observability.middleware.http_requests_total') as mock_http_total:
            with patch('hub.apps.observability.middleware.http_request_duration_seconds') as mock_duration:
                mock_http_total.labels.return_value = mock_counter
                mock_duration.labels.return_value = mock_histogram
                
                self.middleware.process_request(request)
                self.middleware.process_response(request, response)
                
                # Should record metrics
                mock_counter.inc.assert_called_once()
                mock_histogram.observe.assert_called_once()
    
    def test_records_error_metrics(self):
        """Test that middleware records error metrics for 4xx/5xx responses"""
        request = self.factory.get("/api/v1/assets/")
        response = HttpResponse()
        response.status_code = 404
        
        # Mock the metrics objects
        mock_error_counter = Mock()
        
        with patch('hub.apps.observability.middleware.http_errors_total') as mock_http_errors:
            mock_http_errors.labels.return_value = mock_error_counter
            
            self.middleware.process_request(request)
            self.middleware.process_response(request, response)
            
            # Should record error metric
            mock_error_counter.inc.assert_called_once()
    
    def test_normalizes_route(self):
        """Test that middleware normalizes routes (replaces UUIDs with {id})"""
        request = self.factory.get("/api/v1/contracts/123e4567-e89b-12d3-a456-426614174000/")
        
        normalized = self.middleware._normalize_route(request.path)
        
        self.assertEqual(normalized, "/api/v1/contracts/{id}/")
    
    def test_normalizes_numeric_ids(self):
        """Test that middleware normalizes numeric IDs"""
        request = self.factory.get("/api/v1/assets/123/")
        
        normalized = self.middleware._normalize_route(request.path)
        
        self.assertEqual(normalized, "/api/v1/assets/{id}/")
    
    def test_handles_missing_start_time(self):
        """Test that middleware handles missing start time gracefully"""
        request = self.factory.get("/api/v1/assets/")
        # Don't call process_request, so _metrics_start_time is not set
        response = HttpResponse()
        response.status_code = 200
        
        # Should not raise exception
        result = self.middleware.process_response(request, response)
        
        self.assertIsNotNone(result)
    
    def test_calculates_duration(self):
        """Test that middleware calculates request duration"""
        request = self.factory.get("/api/v1/assets/")
        response = HttpResponse()
        response.status_code = 200
        
        # Set start time
        request._metrics_start_time = time.time() - 0.1  # 100ms ago
        
        # Mock the metrics objects
        mock_histogram = Mock()
        
        with patch('hub.apps.observability.middleware.http_request_duration_seconds') as mock_duration:
            mock_duration.labels.return_value = mock_histogram
            
            self.middleware.process_response(request, response)
            
            # Should observe duration
            mock_histogram.observe.assert_called_once()
            observed_duration = mock_histogram.observe.call_args[0][0]
            self.assertGreaterEqual(observed_duration, 0.1)
            self.assertLess(observed_duration, 0.2)  # Should be close to 0.1
    
    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        request = self.factory.get("/api/v1/assets/")
        response = HttpResponse()
        response.status_code = 200
        
        start = time.time()
        for _ in range(100):
            self.middleware.process_request(request)
            self.middleware.process_response(request, response)
        elapsed = time.time() - start
        
        # Should process 100 requests in less than 0.5 seconds
        self.assertLess(elapsed, 0.5, f"Middleware too slow: {elapsed:.3f}s for 100 requests")

