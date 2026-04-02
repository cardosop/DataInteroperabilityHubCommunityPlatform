"""
Unit tests for API Analytics

Tests for usage tracking, endpoint popularity, and performance metrics.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.api.analytics.models import APIUsageMetric
from hub.apps.api.analytics.analytics import APIAnalyticsService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class APIAnalyticsServiceTest(TestCase):
    """Test APIAnalyticsService"""
    
    def setUp(self):
        """Set up test fixtures"""
        import uuid
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Analytics Test {uid}",
            slug=f"analytics-test-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"analytics-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_track_request(self):
        """Test request tracking"""
        APIAnalyticsService.track_request(
            tenant_id=str(self.tenant.id),
            endpoint_path="/api/v1/assets/",
            method="GET",
            status_code=200,
            latency_ms=50.0,
            user_id=str(self.user.id)
        )
        
        # Verify metric was created
        metric = APIUsageMetric.objects.filter(tenant=self.tenant).first()
        self.assertIsNotNone(metric)
        self.assertEqual(metric.endpoint_path, "/api/v1/assets/")
        self.assertEqual(metric.method, "GET")
        self.assertEqual(metric.status_code, 200)
        self.assertEqual(metric.latency_ms, 50.0)
    
    def test_get_endpoint_popularity(self):
        """Test endpoint popularity calculation"""
        # Create multiple requests
        for i in range(10):
            APIAnalyticsService.track_request(
                tenant_id=str(self.tenant.id),
                endpoint_path="/api/v1/assets/",
                method="GET",
                status_code=200,
                latency_ms=50.0
            )
        
        for i in range(5):
            APIAnalyticsService.track_request(
                tenant_id=str(self.tenant.id),
                endpoint_path="/api/v1/contracts/",
                method="GET",
                status_code=200,
                latency_ms=30.0
            )
        
        popularity = APIAnalyticsService.get_endpoint_popularity(
            tenant_id=str(self.tenant.id),
            limit=10
        )
        
        self.assertGreater(len(popularity), 0)
        # Assets endpoint should be most popular
        self.assertEqual(popularity[0]['endpoint'], "/api/v1/assets/")
        self.assertEqual(popularity[0]['request_count'], 10)
    
    def test_get_usage_trends(self):
        """Test usage trends calculation"""
        # Create requests over time
        now = timezone.now()
        for i in range(5):
            metric = APIUsageMetric.objects.create(
                tenant=self.tenant,
                endpoint_path="/api/v1/assets/",
                method="GET",
                status_code=200,
                created_at=now - timedelta(hours=i)
            )
        
        trends = APIAnalyticsService.get_usage_trends(
            tenant_id=str(self.tenant.id),
            granularity="hour"
        )
        
        self.assertGreater(len(trends), 0)
    
    def test_get_performance_metrics(self):
        """Test performance metrics calculation"""
        # Create requests with different latencies
        for latency in [10.0, 20.0, 30.0, 40.0, 50.0]:
            APIAnalyticsService.track_request(
                tenant_id=str(self.tenant.id),
                endpoint_path="/api/v1/assets/",
                method="GET",
                status_code=200,
                latency_ms=latency
            )
        
        metrics = APIAnalyticsService.get_performance_metrics(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("total_requests", metrics)
        self.assertIn("avg_latency_ms", metrics)
        self.assertIn("p95_latency_ms", metrics)
        self.assertEqual(metrics["total_requests"], 5)
    
    def test_get_analytics_dashboard(self):
        """Test complete analytics dashboard"""
        # Create some test data
        for i in range(5):
            APIAnalyticsService.track_request(
                tenant_id=str(self.tenant.id),
                endpoint_path=f"/api/v1/endpoint-{i}/",
                method="GET",
                status_code=200,
                latency_ms=50.0
            )
        
        dashboard = APIAnalyticsService.get_analytics_dashboard(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("popular_endpoints", dashboard)
        self.assertIn("usage_trends", dashboard)
        self.assertIn("performance_metrics", dashboard)

