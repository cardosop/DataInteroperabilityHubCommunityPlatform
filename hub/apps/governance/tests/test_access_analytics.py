"""
Unit tests for Access Analytics

Tests for access logging, anomaly detection, and analytics.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.governance.access_analytics import AccessAnalyticsService, AccessLog
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AccessAnalyticsServiceTest(TestCase):
    """Test AccessAnalyticsService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_log_access(self):
        """Test access logging"""
        AccessAnalyticsService.log_access(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource_type="ASSET",
            resource_id="test-resource-id",
            action="READ",
            result="ALLOWED",
            ip_address="127.0.0.1"
        )
        
        # Verify log was created
        log = AccessLog.objects.filter(tenant=self.tenant).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.resource_type, "ASSET")
        self.assertEqual(log.action, "READ")
        self.assertEqual(log.result, "ALLOWED")
    
    def test_get_access_patterns(self):
        """Test access pattern analysis"""
        # Create multiple access logs
        for i in range(10):
            AccessAnalyticsService.log_access(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resource_type="ASSET",
                resource_id="asset-1",
                action="READ",
                result="ALLOWED"
            )
        
        patterns = AccessAnalyticsService.get_access_patterns(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertGreater(len(patterns), 0)
    
    def test_get_anomalies(self):
        """Test anomaly detection"""
        # Create access log outside business hours
        now = timezone.now().replace(hour=2, minute=0)  # 2 AM
        
        log = AccessLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            resource_type="ASSET",
            resource_id="test-id",
            action="READ",
            result="ALLOWED",
            created_at=now
        )
        
        # Check for anomalies
        AccessAnalyticsService._check_anomalies(log)
        
        # Refresh from DB
        log.refresh_from_db()
        
        # Should be flagged as anomaly (outside business hours)
        self.assertTrue(log.is_anomaly)
    
    def test_get_security_events(self):
        """Test security event tracking"""
        # Create denied access
        AccessAnalyticsService.log_access(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource_type="ASSET",
            resource_id="test-id",
            action="READ",
            result="DENIED"
        )
        
        events = AccessAnalyticsService.get_security_events(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]['result'], 'DENIED')
    
    def test_get_analytics_dashboard(self):
        """Test complete analytics dashboard"""
        # Create some test data
        for i in range(5):
            AccessAnalyticsService.log_access(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resource_type="ASSET",
                resource_id=f"asset-{i}",
                action="READ",
                result="ALLOWED"
            )
        
        dashboard = AccessAnalyticsService.get_analytics_dashboard(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("summary", dashboard)
        self.assertIn("top_users", dashboard)
        self.assertIn("top_resources", dashboard)
        self.assertIn("anomalies", dashboard)
        self.assertIn("security_events", dashboard)

