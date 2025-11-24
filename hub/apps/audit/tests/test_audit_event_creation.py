"""
Unit tests for audit event creation.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import (
    create_audit_event,
    log_tenant_operation,
    log_user_operation,
    log_auth_operation,
    redact_pii
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant

User = get_user_model()


class AuditEventCreationTest(TestCase):
    """Test audit event creation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_create_audit_event(self):
        """Test basic audit event creation"""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"}
        )
        
        self.assertIsNotNone(event.id)
        self.assertEqual(event.resource_type, "TEST")
        self.assertEqual(event.action, "TEST_ACTION")
        self.assertEqual(event.actor_user, self.user)
        self.assertEqual(event.tenant, self.tenant)
        self.assertEqual(event.result, "SUCCESS")
        self.assertEqual(event.details_json["test"], "data")
    
    def test_audit_event_immutable(self):
        """Test that audit events cannot be updated or deleted"""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user
        )
        
        # Try to update
        with self.assertRaises(ValueError):
            event.action = "UPDATED"
            event.save()
        
        # Try to delete
        with self.assertRaises(ValueError):
            event.delete()
    
    def test_log_tenant_operation(self):
        """Test logging tenant operations"""
        event = log_tenant_operation(
            action="TENANT_CREATED",
            tenant=self.tenant,
            actor_user=self.user,
            details={"name": self.tenant.name}
        )
        
        self.assertEqual(event.resource_type, "TENANT")
        self.assertEqual(event.action, "TENANT_CREATED")
        self.assertEqual(event.tenant, self.tenant)
    
    def test_log_user_operation(self):
        """Test logging user operations"""
        event = log_user_operation(
            action="USER_CREATED",
            user=self.user,
            actor_user=self.user,
            details={"email": self.user.email}
        )
        
        self.assertEqual(event.resource_type, "USER")
        self.assertEqual(event.action, "USER_CREATED")
        self.assertEqual(event.resource_id, str(self.user.id))
    
    def test_log_auth_operation(self):
        """Test logging authentication operations"""
        event = log_auth_operation(
            action="LOGIN",
            user=self.user,
            details={"method": "password"}
        )
        
        self.assertEqual(event.resource_type, "AUTH")
        self.assertEqual(event.action, "LOGIN")
        self.assertEqual(event.actor_user, self.user)
    
    def test_pii_redaction_email(self):
        """Test PII redaction for email addresses"""
        details = {
            "email": "user@example.com",
            "contact": "Contact: admin@example.com for help"
        }
        
        redacted = redact_pii(details)
        
        # Email should be partially redacted
        self.assertNotEqual(redacted["email"], "user@example.com")
        self.assertIn("@", redacted["email"])  # Domain should remain
        self.assertNotEqual(redacted["contact"], "Contact: admin@example.com for help")
    
    def test_pii_redaction_phone(self):
        """Test PII redaction for phone numbers"""
        details = {
            "phone": "555-123-4567",
            "contact_info": "Call 555-123-4567 for support"
        }
        
        redacted = redact_pii(details)
        
        # Phone should be redacted
        self.assertEqual(redacted["phone"], "[REDACTED_PHONE]")
        self.assertIn("[REDACTED_PHONE]", redacted["contact_info"])
    
    def test_pii_redaction_password(self):
        """Test PII redaction for password fields"""
        details = {
            "password": "secret123",
            "password_hash": "abc123",
            "api_key": "key123",
            "token": "token123"
        }
        
        redacted = redact_pii(details)
        
        # All sensitive fields should be redacted
        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertEqual(redacted["password_hash"], "[REDACTED]")
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["token"], "[REDACTED]")
    
    def test_pii_redaction_nested(self):
        """Test PII redaction in nested dictionaries"""
        details = {
            "user": {
                "email": "user@example.com",
                "phone": "555-123-4567"
            },
            "metadata": {
                "contact": "admin@example.com"
            }
        }
        
        redacted = redact_pii(details)
        
        # Nested PII should be redacted
        self.assertNotEqual(redacted["user"]["email"], "user@example.com")
        self.assertEqual(redacted["user"]["phone"], "[REDACTED_PHONE]")
        self.assertNotEqual(redacted["metadata"]["contact"], "admin@example.com")
    
    def test_audit_event_with_request_metadata(self):
        """Test audit event creation with request metadata"""
        from unittest.mock import Mock
        
        request = Mock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '192.168.1.1',
            'HTTP_USER_AGENT': 'Mozilla/5.0'
        }
        request.request_id = "test-request-id"
        
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            request=request
        )
        
        # Request metadata should be included
        self.assertIn("ip_address", event.details_json)
        self.assertIn("user_agent", event.details_json)
        self.assertIn("request_id", event.details_json)
        self.assertEqual(event.details_json["ip_address"], "192.168.1.1")

