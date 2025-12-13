"""
Integration tests for Access Analytics

Tests for access logging integration with ABAC.
"""
import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.governance.access_analytics import AccessAnalyticsService
from hub.apps.governance.abac import ABACEngine
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AccessAnalyticsIntegrationTest(TestCase):
    """Integration tests for access analytics"""
    
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
    
    def test_abac_evaluation_with_logging(self):
        """Test ABAC evaluation with automatic logging"""
        # Evaluate access
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="ASSET",
            resource_id="test-id",
            access_type="READ"
        )
        
        # Log access
        AccessAnalyticsService.log_access(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource_type="ASSET",
            resource_id="test-id",
            action="READ",
            result="ALLOWED" if result.allowed else "DENIED",
            policy_evaluation={
                "policy_id": str(result.policy.id) if result.policy else None,
                "allowed": result.allowed
            }
        )
        
        # Verify log was created
        from hub.apps.governance.access_analytics import AccessLog
        log = AccessLog.objects.filter(tenant=self.tenant).first()
        self.assertIsNotNone(log)
        self.assertIsNotNone(log.policy_evaluation)

