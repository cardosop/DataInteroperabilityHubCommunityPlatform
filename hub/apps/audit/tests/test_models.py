"""
Unit tests for AuditEvent model.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.audit.models import AuditEvent


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuditEventModelTest(TestCase):
    """Test AuditEvent model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    def test_create_audit_event(self):
        """Test audit event creation"""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"}
        )
        
        self.assertEqual(event.tenant, self.tenant)
        self.assertEqual(event.actor_user, self.user)
        self.assertEqual(event.resource_type, "ASSET")
        self.assertEqual(event.action, "CREATED")
        self.assertEqual(event.result, "SUCCESS")

