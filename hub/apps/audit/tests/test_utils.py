"""
Unit tests for audit utilities.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.audit.utils import (
    redact_pii,
    redact_string,
    create_audit_event,
    log_tenant_operation,
    log_user_operation,
    log_auth_operation,
)

User = get_user_model()


class AuditUtilsTest(TestCase):
    """Test audit utilities"""
    
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
    
    def test_redact_pii_email(self):
        """Test PII redaction for email"""
        data = {
            "email": "test@example.com",
            "name": "Test User"
        }
        redacted = redact_pii(data)
        
        self.assertIn("email", redacted)
        # Email should be partially redacted
        self.assertNotEqual(redacted["email"], "test@example.com")
    
    def test_redact_pii_password(self):
        """Test PII redaction for password"""
        data = {
            "password": "secret123",
            "username": "testuser"
        }
        redacted = redact_pii(data)
        
        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertEqual(redacted["username"], "testuser")
    
    def test_redact_string(self):
        """Test string redaction"""
        text = "Contact test@example.com or call 555-123-4567"
        redacted = redact_string(text)
        
        # Email should be partially redacted (te***@example.com format)
        self.assertNotIn("test@example.com", redacted)
        # Should contain partial email (te***@example.com)
        self.assertIn("te***@example.com", redacted)
        # Phone number should be redacted (10-digit format)
        self.assertIn("[REDACTED_PHONE]", redacted)
    
    def test_create_audit_event(self):
        """Test create_audit_event"""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"}
        )
        
        self.assertEqual(event.resource_type, "ASSET")
        self.assertEqual(event.action, "CREATED")
        self.assertEqual(event.actor_user, self.user)
        self.assertEqual(event.tenant, self.tenant)
    
    def test_log_tenant_operation(self):
        """Test log_tenant_operation"""
        event = log_tenant_operation(
            action="UPDATED",
            tenant=self.tenant,
            actor_user=self.user,
            details={"field": "value"}
        )
        
        self.assertEqual(event.resource_type, "TENANT")
        self.assertEqual(event.action, "UPDATED")
    
    def test_log_user_operation(self):
        """Test log_user_operation"""
        event = log_user_operation(
            action="CREATED",
            user=self.user,
            actor_user=self.user,
            details={"field": "value"}
        )
        
        self.assertEqual(event.resource_type, "USER")
        self.assertEqual(event.action, "CREATED")
    
    def test_log_auth_operation(self):
        """Test log_auth_operation"""
        event = log_auth_operation(
            action="LOGIN",
            user=self.user,
            result="SUCCESS",
            details={"ip": "127.0.0.1"}
        )
        
        self.assertEqual(event.resource_type, "AUTH")
        self.assertEqual(event.action, "LOGIN")
        self.assertEqual(event.result, "SUCCESS")

