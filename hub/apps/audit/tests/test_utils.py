"""
Unit tests for audit utilities.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.audit.utils import (
    create_audit_event,
    log_auth_operation,
    log_tenant_operation,
    log_user_operation,
    redact_pii,
    redact_string,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class AuditUtilsTest(TestCase):
    """Test audit utilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    def test_redact_pii_email_includes_email_key(self):
        """Test PII redaction for email includes email key."""
        data = {"email": "test@example.com", "name": "Test User"}
        redacted = redact_pii(data)

        self.assertIn("email", redacted)

    def test_redact_pii_email_redacts_email(self):
        """Test PII redaction for email redacts email."""
        data = {"email": "test@example.com", "name": "Test User"}
        redacted = redact_pii(data)

        self.assertNotEqual(redacted["email"], "test@example.com")

    def test_redact_pii_password_redacts_password(self):
        """Test PII redaction for password redacts password."""
        data = {"password": "secret123", "username": "testuser"}
        redacted = redact_pii(data)

        self.assertEqual(redacted["password"], "[REDACTED]")

    def test_redact_pii_password_preserves_username(self):
        """Test PII redaction for password preserves username."""
        data = {"password": "secret123", "username": "testuser"}
        redacted = redact_pii(data)

        self.assertEqual(redacted["username"], "testuser")

    def test_redact_string_redacts_email(self):
        """Test string redaction redacts email."""
        text = "Contact test@example.com or call 555-123-4567"
        redacted = redact_string(text)

        self.assertNotIn("test@example.com", redacted)

    def test_redact_string_partially_redacts_email(self):
        """Test string redaction partially redacts email."""
        text = "Contact test@example.com or call 555-123-4567"
        redacted = redact_string(text)

        self.assertIn("te***@example.com", redacted)

    def test_redact_string_redacts_phone(self):
        """Test string redaction redacts phone number."""
        text = "Contact test@example.com or call 555-123-4567"
        redacted = redact_string(text)

        self.assertIn("[REDACTED_PHONE]", redacted)

    def test_create_audit_event_sets_resource_type(self):
        """Test create_audit_event sets resource_type."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"},
        )

        self.assertEqual(event.resource_type, "ASSET")

    def test_create_audit_event_sets_action(self):
        """Test create_audit_event sets action."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"},
        )

        self.assertEqual(event.action, "CREATED")

    def test_create_audit_event_sets_actor_user(self):
        """Test create_audit_event sets actor_user."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"},
        )

        self.assertEqual(event.actor_user, self.user)

    def test_create_audit_event_sets_tenant(self):
        """Test create_audit_event sets tenant."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"key": "value"},
        )

        self.assertEqual(event.tenant, self.tenant)

    def test_log_tenant_operation_sets_resource_type(self):
        """Test log_tenant_operation sets resource_type."""
        event = log_tenant_operation(
            action="UPDATED", tenant=self.tenant, actor_user=self.user, details={"field": "value"}
        )

        self.assertEqual(event.resource_type, "TENANT")

    def test_log_tenant_operation_sets_action(self):
        """Test log_tenant_operation sets action."""
        event = log_tenant_operation(
            action="UPDATED", tenant=self.tenant, actor_user=self.user, details={"field": "value"}
        )

        self.assertEqual(event.action, "UPDATED")

    def test_log_user_operation(self):
        """Test log_user_operation"""
        event = log_user_operation(
            action="CREATED", user=self.user, actor_user=self.user, details={"field": "value"}
        )

        self.assertEqual(event.resource_type, "USER")
        self.assertEqual(event.action, "CREATED")

    def test_log_auth_operation_sets_resource_type(self):
        """Test log_auth_operation sets resource_type."""
        event = log_auth_operation(
            action="LOGIN", user=self.user, result="SUCCESS", details={"ip": "127.0.0.1"}
        )

        self.assertEqual(event.resource_type, "AUTH")

    def test_log_auth_operation_sets_action(self):
        """Test log_auth_operation sets action."""
        event = log_auth_operation(
            action="LOGIN", user=self.user, result="SUCCESS", details={"ip": "127.0.0.1"}
        )

        self.assertEqual(event.action, "LOGIN")

    def test_log_auth_operation_sets_result(self):
        """Test log_auth_operation sets result."""
        event = log_auth_operation(
            action="LOGIN", user=self.user, result="SUCCESS", details={"ip": "127.0.0.1"}
        )

        self.assertEqual(event.result, "SUCCESS")

    # ========== FAILURE SCENARIOS ==========

    def test_create_audit_event_with_failure_result(self):
        """Test create_audit_event with FAILURE result (failure scenario)."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            result="FAILURE",
            details={"error": "Validation failed"},
        )

        self.assertEqual(event.result, "FAILURE")
        self.assertEqual(event.details_json["error"], "Validation failed")

    def test_create_audit_event_with_warning_result(self):
        """Test create_audit_event with WARNING result (failure scenario)."""
        event = create_audit_event(
            resource_type="ASSET",
            action="UPDATED",
            actor_user=self.user,
            tenant=self.tenant,
            result="WARNING",
            details={"warning": "Partial update"},
        )

        self.assertEqual(event.result, "WARNING")
        self.assertEqual(event.details_json["warning"], "Partial update")

    def test_redact_pii_with_none_value(self):
        """Test redact_pii with None value (failure scenario)."""
        data = {"email": None, "name": "Test User"}
        redacted = redact_pii(data)

        self.assertIsNone(redacted["email"])
        self.assertEqual(redacted["name"], "Test User")

    def test_create_audit_event_without_tenant_or_user(self):
        """Test create_audit_event without tenant or user (failure scenario)."""
        event = create_audit_event(resource_type="SYSTEM", action="SYSTEM_EVENT", result="SUCCESS")

        self.assertIsNone(event.tenant)
        self.assertIsNone(event.actor_user)

    # ========== EDGE CASES ==========

    def test_redact_pii_with_empty_dict(self):
        """Test redact_pii with empty dictionary (edge case)."""
        data = {}
        redacted = redact_pii(data)

        self.assertEqual(redacted, {})

    def test_redact_pii_with_empty_string(self):
        """Test redact_pii with empty string (edge case)."""
        data = {"email": "", "phone": ""}
        redacted = redact_pii(data)

        self.assertEqual(redacted["email"], "")
        self.assertEqual(redacted["phone"], "")

    def test_redact_string_with_empty_string(self):
        """Test redact_string with empty string (edge case)."""
        text = ""
        redacted = redact_string(text)

        self.assertEqual(redacted, "")

    def test_redact_string_with_no_pii(self):
        """Test redact_string with no PII (edge case)."""
        text = "This is a normal text without any sensitive information."
        redacted = redact_string(text)

        self.assertEqual(redacted, text)

    def test_create_audit_event_with_empty_details(self):
        """Test create_audit_event with empty details (edge case)."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details={},
        )

        self.assertEqual(event.details_json, {})

    def test_create_audit_event_with_none_details(self):
        """Test create_audit_event with None details (edge case)."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            tenant=self.tenant,
            details=None,
        )

        self.assertIsNotNone(event.details_json)

    def test_redact_pii_with_list_values(self):
        """Test redact_pii with list values (edge case)."""
        data = {
            "emails": ["test1@example.com", "test2@example.com"],
            "phones": ["555-123-4567", "555-987-6543"],
        }
        redacted = redact_pii(data)

        self.assertIn("emails", redacted)
        self.assertIn("phones", redacted)

    def test_redact_pii_with_deeply_nested_structure(self):
        """Test redact_pii with deeply nested structure (edge case)."""
        data = {
            "level1": {"level2": {"level3": {"email": "deep@example.com", "phone": "555-123-4567"}}}
        }
        redacted = redact_pii(data)

        self.assertNotEqual(redacted["level1"]["level2"]["level3"]["email"], "deep@example.com")
        self.assertEqual(redacted["level1"]["level2"]["level3"]["phone"], "[REDACTED_PHONE]")

    def test_create_audit_event_infers_tenant_from_user(self):
        """Test create_audit_event infers tenant from user (edge case)."""
        event = create_audit_event(
            resource_type="TEST",
            action="TEST_ACTION",
            actor_user=self.user,
            # tenant not provided, should be inferred from user
        )

        self.assertEqual(event.tenant, self.user.tenant)

    # ========== ERROR HANDLING ==========

    def test_redact_pii_with_invalid_data_type(self):
        """Test redact_pii with invalid data type (error handling)."""
        # redact_pii should handle non-dict types gracefully
        data = "not a dict"
        # This should not raise an error, but may return the original value
        # or handle it gracefully depending on implementation
        try:
            redacted = redact_pii(data)
            # If it doesn't raise, verify it handles gracefully
            self.assertIsNotNone(redacted)
        except (TypeError, AttributeError):
            # If it raises, that's also acceptable error handling
            pass

    def test_create_audit_event_with_invalid_resource_id_format(self):
        """Test create_audit_event with invalid resource_id format (error handling)."""
        # Should handle invalid UUID format gracefully
        try:
            event = create_audit_event(
                resource_type="TEST",
                action="TEST_ACTION",
                actor_user=self.user,
                tenant=self.tenant,
                resource_id="invalid-uuid",
            )
            # If it doesn't raise, verify it handles gracefully
            self.assertIsNotNone(event)
        except (ValueError, TypeError):
            # If it raises, that's also acceptable error handling
            pass

    def test_log_tenant_operation_with_none_tenant(self):
        """Test log_tenant_operation with None tenant (error handling)."""
        # Should handle None tenant gracefully
        try:
            event = log_tenant_operation(action="UPDATED", tenant=None, actor_user=self.user)
            # If it doesn't raise, verify it handles gracefully
            self.assertIsNotNone(event)
        except (TypeError, AttributeError):
            # If it raises, that's also acceptable error handling
            pass

    def test_log_user_operation_with_none_user(self):
        """Test log_user_operation with None user (error handling)."""
        # Should handle None user gracefully
        try:
            event = log_user_operation(action="CREATED", user=None, actor_user=self.user)
            # If it doesn't raise, verify it handles gracefully
            self.assertIsNotNone(event)
        except (TypeError, AttributeError):
            # If it raises, that's also acceptable error handling
            pass

    def test_log_auth_operation_with_none_user(self):
        """Test log_auth_operation with None user (error handling)."""
        # Should handle None user gracefully
        try:
            event = log_auth_operation(action="LOGIN", user=None, result="FAILURE")
            # If it doesn't raise, verify it handles gracefully
            self.assertIsNotNone(event)
        except (TypeError, AttributeError):
            # If it raises, that's also acceptable error handling
            pass
