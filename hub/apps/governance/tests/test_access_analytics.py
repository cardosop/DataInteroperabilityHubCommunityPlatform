"""
Unit tests for Access Analytics

Tests for access logging, anomaly detection, and analytics.
"""
import uuid

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
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_log_access(self):
        """Test access logging"""
        resource_uuid = str(uuid.uuid4())
        AccessAnalyticsService.log_access(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource_type="ASSET",
            resource_id=resource_uuid,
            action="READ",
            result="ALLOWED",
            ip_address="127.0.0.1",
        )

        # Verify log was created
        log = AccessLog.objects.filter(tenant=self.tenant).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.resource_type, "ASSET")
        self.assertEqual(str(log.resource_id), resource_uuid)
        self.assertEqual(log.action, "READ")
        self.assertEqual(log.result, "ALLOWED")
    
    def test_get_access_patterns(self):
        """Test access pattern analysis"""
        resource_uuid = str(uuid.uuid4())
        for _ in range(10):
            AccessAnalyticsService.log_access(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resource_type="ASSET",
                resource_id=resource_uuid,
                action="READ",
                result="ALLOWED",
            )

        patterns = AccessAnalyticsService.get_access_patterns(
            tenant_id=str(self.tenant.id)
        )

        self.assertGreaterEqual(len(patterns), 1)
        # Verify our created resource appears in patterns
        resource_ids = [p.get("resource_id") for p in patterns]
        self.assertIn(resource_uuid, resource_ids)
        # Verify pattern structure contains expected fields
        pattern = [p for p in patterns if p.get("resource_id") == resource_uuid][0]
        self.assertEqual(pattern["resource_type"], "ASSET")
        self.assertEqual(pattern["action"], "READ")
        self.assertGreaterEqual(pattern["access_count"], 10)
    
    def test_get_anomalies(self):
        """Test anomaly detection"""
        # Create access log outside business hours (2 AM)
        now = timezone.now().replace(hour=2, minute=0, second=0, microsecond=0)
        resource_uuid = uuid.uuid4()

        log = AccessLog.objects.create(
            tenant=self.tenant,
            user=self.user,
            resource_type="ASSET",
            resource_id=resource_uuid,
            action="READ",
            result="ALLOWED",
        )
        # Force created_at so auto_now_add does not override (persist 2 AM for anomaly check)
        log.created_at = now
        log.save(update_fields=["created_at"])

        AccessAnalyticsService._check_anomalies(log)
        log.refresh_from_db()
        self.assertTrue(log.is_anomaly, msg=f"Expected is_anomaly=True (created_at={log.created_at})")
    
    def test_get_security_events(self):
        """Test security event tracking"""
        resource_uuid = str(uuid.uuid4())
        AccessAnalyticsService.log_access(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource_type="ASSET",
            resource_id=resource_uuid,
            action="READ",
            result="DENIED",
        )

        events = AccessAnalyticsService.get_security_events(
            tenant_id=str(self.tenant.id)
        )

        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["result"], "DENIED")
    
    def test_get_analytics_dashboard(self):
        """Test complete analytics dashboard"""
        for i in range(5):
            AccessAnalyticsService.log_access(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resource_type="ASSET",
                resource_id=str(uuid.uuid4()),
                action="READ",
                result="ALLOWED",
            )

        dashboard = AccessAnalyticsService.get_analytics_dashboard(
            tenant_id=str(self.tenant.id)
        )

        self.assertIn("summary", dashboard)
        self.assertIsInstance(dashboard["summary"], dict)
        self.assertIn("total_accesses", dashboard["summary"])
        self.assertIsInstance(dashboard["summary"]["total_accesses"], int)
        self.assertGreaterEqual(dashboard["summary"]["total_accesses"], 5)
        self.assertIn("allowed_accesses", dashboard["summary"])
        self.assertIsInstance(dashboard["summary"]["allowed_accesses"], int)
        self.assertIn("top_users", dashboard)
        self.assertIsInstance(dashboard["top_users"], list)
        self.assertIn("top_resources", dashboard)
        self.assertIsInstance(dashboard["top_resources"], list)
        self.assertIn("anomalies", dashboard)
        self.assertIn("security_events", dashboard)

