"""
Unit tests for audit event creation.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import (
    create_audit_event,
    log_auth_operation,
    log_tenant_operation,
    log_user_operation,
    redact_pii,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuditEventCreationTest(TestCase):
    """Test audit event creation"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_create_audit_event_has_id(self):
        """Test basic audit event creation has id."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertIsNotNone(event.id)

    def test_create_audit_event_sets_resource_type(self):
        """Test basic audit event creation sets resource_type."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.resource_type, "TEST")

    def test_create_audit_event_sets_action(self):
        """Test basic audit event creation sets action."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.action, "TEST_ACTION")

    def test_create_audit_event_sets_actor_user(self):
        """Test basic audit event creation sets actor_user."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.actor_user, self.user)

    def test_create_audit_event_sets_tenant(self):
        """Test basic audit event creation sets tenant."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.tenant, self.tenant)

    def test_create_audit_event_sets_result(self):
        """Test basic audit event creation sets result."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.result, "SUCCESS")

    def test_create_audit_event_sets_details(self):
        """Test basic audit event creation sets details."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={"test": "data"},
        )

        self.assertEqual(event.details_json["test"], "data")

    def test_audit_event_immutable(self):
        """Test that audit events cannot be updated or deleted"""
        event = create_audit_event(resource_type="TEST", action="TEST_ACTION", actor_user=self.user)
        original_action = event.action

        # Try to update
        with self.assertRaises((ValueError, Exception)):
            event.action = "UPDATED"
            event.save()

        # Verify DB state unchanged
        event.refresh_from_db()
        self.assertEqual(event.action, original_action)

        # Try to delete
        with self.assertRaises(ValueError):
            event.delete()

    def test_log_tenant_operation_sets_resource_type(self):
        """Test logging tenant operations sets resource_type."""
        event = log_tenant_operation(
            action="TENANT_CREATED",
            tenant=self.tenant,
            actor_user=self.user,
            details={"name": self.tenant.name},
        )

        self.assertEqual(event.resource_type, "TENANT")

    def test_log_tenant_operation_sets_action(self):
        """Test logging tenant operations sets action."""
        event = log_tenant_operation(
            action="TENANT_CREATED",
            tenant=self.tenant,
            actor_user=self.user,
            details={"name": self.tenant.name},
        )

        self.assertEqual(event.action, "TENANT_CREATED")

    def test_log_tenant_operation_sets_tenant(self):
        """Test logging tenant operations sets tenant."""
        event = log_tenant_operation(
            action="TENANT_CREATED",
            tenant=self.tenant,
            actor_user=self.user,
            details={"name": self.tenant.name},
        )

        self.assertEqual(event.tenant, self.tenant)

    def test_log_user_operation_sets_resource_type(self):
        """Test logging user operations sets resource_type."""
        event = log_user_operation(
            action="USER_CREATED",
            user=self.user,
            actor_user=self.user,
            details={"email": self.user.email},
        )

        self.assertEqual(event.resource_type, "USER")

    def test_log_user_operation_sets_action(self):
        """Test logging user operations sets action."""
        event = log_user_operation(
            action="USER_CREATED",
            user=self.user,
            actor_user=self.user,
            details={"email": self.user.email},
        )

        self.assertEqual(event.action, "USER_CREATED")

    def test_log_user_operation_sets_resource_id(self):
        """Test logging user operations sets resource_id."""
        event = log_user_operation(
            action="USER_CREATED",
            user=self.user,
            actor_user=self.user,
            details={"email": self.user.email},
        )

        self.assertEqual(event.resource_id, str(self.user.id))

    def test_log_auth_operation_sets_resource_type(self):
        """Test logging authentication operations sets resource_type."""
        event = log_auth_operation(action="LOGIN", user=self.user, details={"method": "password"})

        self.assertEqual(event.resource_type, "AUTH")

    def test_log_auth_operation_sets_action(self):
        """Test logging authentication operations sets action."""
        event = log_auth_operation(action="LOGIN", user=self.user, details={"method": "password"})

        self.assertEqual(event.action, "LOGIN")

    def test_log_auth_operation_sets_actor_user(self):
        """Test logging authentication operations sets actor_user."""
        event = log_auth_operation(action="LOGIN", user=self.user, details={"method": "password"})

        self.assertEqual(event.actor_user, self.user)

    def test_pii_redaction_email_redacts_email(self):
        """Test PII redaction for email addresses redacts email."""
        details = {"email": "user@example.com", "contact": "Contact: admin@example.com for help"}

        redacted = redact_pii(details)

        self.assertNotIn("user@", str(redacted["email"]))
        self.assertIn("@example.com", str(redacted["email"]))

    def test_pii_redaction_email_preserves_domain(self):
        """Test PII redaction for email addresses preserves domain."""
        details = {"email": "user@example.com", "contact": "Contact: admin@example.com for help"}

        redacted = redact_pii(details)

        self.assertIn("@", redacted["email"])

    def test_pii_redaction_email_redacts_contact(self):
        """Test PII redaction for email addresses redacts contact."""
        details = {"email": "user@example.com", "contact": "Contact: admin@example.com for help"}

        redacted = redact_pii(details)

        self.assertNotIn("admin@", str(redacted["contact"]))
        self.assertIn("@example.com", str(redacted["contact"]))

    def test_pii_redaction_phone_redacts_phone(self):
        """Test PII redaction for phone numbers redacts phone."""
        details = {"phone": "555-123-4567", "contact_info": "Call 555-123-4567 for support"}

        redacted = redact_pii(details)

        self.assertEqual(redacted["phone"], "[REDACTED_PHONE]")

    def test_pii_redaction_phone_redacts_contact_info(self):
        """Test PII redaction for phone numbers redacts contact_info."""
        details = {"phone": "555-123-4567", "contact_info": "Call 555-123-4567 for support"}

        redacted = redact_pii(details)

        self.assertNotIn("555-123-4567", str(redacted["contact_info"]))
        self.assertIn("[REDACTED_PHONE]", redacted["contact_info"])

    def test_pii_redaction_password_redacts_password(self):
        """Test PII redaction for password fields redacts password."""
        details = {
            "password": "secret123",
            "password_hash": "abc123",
            "api_key": "key123",
            "token": "token123",
        }

        redacted = redact_pii(details)

        self.assertEqual(redacted["password"], "[REDACTED]")
        self.assertNotIn("secret123", str(redacted["password"]))

    def test_pii_redaction_password_redacts_password_hash(self):
        """Test PII redaction for password fields redacts password_hash."""
        details = {
            "password": "secret123",
            "password_hash": "abc123",
            "api_key": "key123",
            "token": "token123",
        }

        redacted = redact_pii(details)

        self.assertEqual(redacted["password_hash"], "[REDACTED]")
        self.assertNotIn("abc123", str(redacted["password_hash"]))

    def test_pii_redaction_password_redacts_api_key(self):
        """Test PII redaction for password fields redacts api_key."""
        details = {
            "password": "secret123",
            "password_hash": "abc123",
            "api_key": "key123",
            "token": "token123",
        }

        redacted = redact_pii(details)

        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertNotIn("key123", str(redacted["api_key"]))

    def test_pii_redaction_password_redacts_token(self):
        """Test PII redaction for password fields redacts token."""
        details = {
            "password": "secret123",
            "password_hash": "abc123",
            "api_key": "key123",
            "token": "token123",
        }

        redacted = redact_pii(details)

        self.assertEqual(redacted["token"], "[REDACTED]")
        self.assertNotIn("token123", str(redacted["token"]))

    def test_pii_redaction_nested_redacts_email(self):
        """Test PII redaction in nested dictionaries redacts email."""
        details = {
            "user": {"email": "user@example.com", "phone": "555-123-4567"},
            "metadata": {"contact": "admin@example.com"},
        }

        redacted = redact_pii(details)

        self.assertNotIn("user@", str(redacted["user"]["email"]))
        self.assertIn("@example.com", str(redacted["user"]["email"]))

    def test_pii_redaction_nested_redacts_phone(self):
        """Test PII redaction in nested dictionaries redacts phone."""
        details = {
            "user": {"email": "user@example.com", "phone": "555-123-4567"},
            "metadata": {"contact": "admin@example.com"},
        }

        redacted = redact_pii(details)

        self.assertEqual(redacted["user"]["phone"], "[REDACTED_PHONE]")

    def test_pii_redaction_nested_redacts_contact(self):
        """Test PII redaction in nested dictionaries redacts contact."""
        details = {
            "user": {"email": "user@example.com", "phone": "555-123-4567"},
            "metadata": {"contact": "admin@example.com"},
        }

        redacted = redact_pii(details)

        self.assertNotIn("admin@", str(redacted["metadata"]["contact"]))
        self.assertIn("@example.com", str(redacted["metadata"]["contact"]))

    def test_audit_event_with_request_metadata(self):
        """Test audit event creation with request metadata"""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/test/")
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1", "HTTP_USER_AGENT": "Mozilla/5.0"}
        request.request_id = "test-request-id"

        event = create_audit_event(
            resource_type="TEST", action="TEST_ACTION", actor_user=self.user, request=request
        )

        # Request metadata should be included
        self.assertIn("ip_address", event.details_json)

    def test_audit_event_with_request_metadata_includes_user_agent(self):
        """Test audit event creation with request metadata includes user_agent."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/test/")
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1", "HTTP_USER_AGENT": "Mozilla/5.0"}
        request.request_id = "test-request-id"

        event = create_audit_event(
            resource_type="TEST", action="TEST_ACTION", actor_user=self.user, request=request
        )

        self.assertIn("user_agent", event.details_json)

    def test_audit_event_with_request_metadata_includes_request_id(self):
        """Test audit event creation with request metadata includes request_id."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/test/")
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1", "HTTP_USER_AGENT": "Mozilla/5.0"}
        request.request_id = "test-request-id"

        event = create_audit_event(
            resource_type="TEST", action="TEST_ACTION", actor_user=self.user, request=request
        )

        self.assertIn("request_id", event.details_json)

    def test_audit_event_with_request_metadata_sets_ip_address(self):
        """Test audit event creation with request metadata sets ip_address."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/test/")
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1", "HTTP_USER_AGENT": "Mozilla/5.0"}
        request.request_id = "test-request-id"

        event = create_audit_event(
            resource_type="TEST", action="TEST_ACTION", actor_user=self.user, request=request
        )

        self.assertEqual(event.details_json["ip_address"], "192.168.1.1")
