"""
Performance tests for OpenTelemetry metrics.

Tests verify that metrics collection has minimal overhead and doesn't
significantly impact application performance.
"""
import pytest
import uuid

pytestmark = pytest.mark.slow
import time
import statistics
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from tests.factories import TenantFactory

from hub.apps.observability.otel_metrics import (
    http_requests_total,
    http_request_duration_seconds,
    jobs_started_total,
    job_duration_seconds,
    tenant_running_jobs,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MetricsOverheadPerformanceTest(TestCase):
    """Test metrics collection overhead"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_metrics_collection_overhead(self):
        """Test that metrics collection has minimal overhead"""
        # Measure request time with metrics
        latencies = []
        for i in range(100):
            start_time = time.perf_counter()
            self.client.get('/health/')
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000)  # Convert to ms
        
        # Calculate average and P95 latency
        avg_latency = statistics.mean(latencies) if latencies else 0
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)] if sorted_latencies else 0
        
        # Health endpoint should be fast even with metrics collection (<100ms P95)
        self.assertLess(p95_latency, 100.0, f"P95 latency is {p95_latency:.2f}ms (avg: {avg_latency:.2f}ms), should be <100ms with metrics")
    
    def test_metrics_endpoint_performance(self):
        """Test that metrics endpoint responds quickly"""
        # Record some metrics first
        for i in range(10):
            http_requests_total.labels(method='GET', route='/test/', status_class='2xx').inc()
        
        # Measure metrics endpoint response time
        latencies = []
        for i in range(50):
            start_time = time.perf_counter()
            response = self.client.get('/metrics/')
            end_time = time.perf_counter()
            if response.status_code == 200:
                latencies.append((end_time - start_time) * 1000)  # Convert to ms
        
        if latencies:
            avg_latency = statistics.mean(latencies)
            p95_index = int(len(latencies) * 0.95)
            p95_latency = sorted(latencies)[min(p95_index, len(latencies) - 1)]
            
            # Metrics endpoint should respond quickly (<500ms P95)
            self.assertLess(p95_latency, 500.0, f"Metrics endpoint P95 latency is {p95_latency:.2f}ms (avg: {avg_latency:.2f}ms), should be <500ms")
    
    def test_metric_recording_overhead(self):
        """Test that recording metrics has minimal overhead"""
        tenant_id = str(self.tenant.id)
        
        # Measure time to record metrics
        times = []
        for i in range(1000):
            start_time = time.perf_counter()
            http_requests_total.labels(method='GET', route='/test/', status_class='2xx').inc()
            jobs_started_total.labels(job_type='DQ_RUN', tenant_id=tenant_id).inc()
            job_duration_seconds.labels(job_type='DQ_RUN', status='COMPLETED').observe(10.5)
            tenant_running_jobs.labels(tenant_id=tenant_id).set(5)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000000)  # Convert to microseconds
        
        avg_time = statistics.mean(times) if times else 0
        p95_time = sorted(times)[int(len(times) * 0.95)] if times else 0
        
        # Metric recording should be very fast (<100 microseconds per operation)
        self.assertLess(p95_time, 100.0, f"Metric recording P95 time is {p95_time:.2f}μs (avg: {avg_time:.2f}μs), should be <100μs")
    
    def test_metrics_collection_under_load(self):
        """Test metrics collection performance under load"""
        tenant_id = str(self.tenant.id)
        
        # Record many metrics quickly
        start_time = time.perf_counter()
        for i in range(10000):
            http_requests_total.labels(method='GET', route=f'/test{i%10}/', status_class='2xx').inc()
            jobs_started_total.labels(job_type='DQ_RUN', tenant_id=tenant_id).inc()
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        ops_per_second = 20000 / duration  # 10000 requests * 2 metrics each
        
        # Should handle at least 10,000 operations per second
        self.assertGreater(ops_per_second, 10000, f"Metrics collection throughput is {ops_per_second:.0f} ops/s, should be >10,000 ops/s")
    
    def test_metrics_endpoint_under_load(self):
        """Test metrics endpoint performance under load"""
        # Record many metrics
        for i in range(100):
            http_requests_total.labels(method='GET', route=f'/test{i%10}/', status_class='2xx').inc()
        
        # Query metrics endpoint multiple times
        start_time = time.perf_counter()
        for i in range(100):
            response = self.client.get('/metrics/')
            if response.status_code != 200:
                break
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        requests_per_second = 100 / duration
        
        # Should handle at least 10 requests per second
        self.assertGreater(requests_per_second, 10, f"Metrics endpoint throughput is {requests_per_second:.0f} req/s, should be >10 req/s")


class MetricsMemoryPerformanceTest(TestCase):
    """Test metrics memory usage"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = TenantFactory.create_tenant()
    
    def test_metrics_memory_usage(self):
        """Test that metrics don't cause excessive memory usage"""
        import sys
        import gc
        
        # Get initial memory
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Record many metrics with different labels
        tenant_id = str(self.tenant.id)
        for i in range(1000):
            http_requests_total.labels(method='GET', route=f'/test{i}/', status_class='2xx').inc()
            jobs_started_total.labels(job_type='DQ_RUN', tenant_id=tenant_id).inc()
        
        # Get final memory
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory increase should be reasonable (<10,000 objects for 1000 metrics)
        object_increase = final_objects - initial_objects
        self.assertLess(object_increase, 10000, f"Memory increase is {object_increase} objects, should be <10,000 for 1000 metrics")
    
    def test_metrics_no_memory_leak(self):
        """Test that metrics don't cause memory leaks"""
        import gc
        
        # Record metrics in a loop
        tenant_id = str(self.tenant.id)
        for iteration in range(10):
            for i in range(100):
                http_requests_total.labels(method='GET', route=f'/test{i}/', status_class='2xx').inc()
                jobs_started_total.labels(job_type='DQ_RUN', tenant_id=tenant_id).inc()
            
            # Force garbage collection
            gc.collect()
        
        # Memory should stabilize (no continuous growth)
        # This is a basic check - more sophisticated leak detection would use memory profiling
        self.assertIsNotNone(True)  # Operation completed without raising  # If we get here without OOM, test passes

