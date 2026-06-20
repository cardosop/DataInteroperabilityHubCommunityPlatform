"""
Phase 121G — Audit Event Payload Tests

Verifies audit events have correct structure and required fields.
"""

import uuid

from django.test import TestCase

from hub.apps.audit.utils import create_audit_event


class TestAuditEventPayloadStructure(TestCase):
    """Verify audit events have correct resource_type, action, and details."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        self.tenant = Tenant.objects.create(
            name=f"test-audit-{uuid.uuid4().hex[:8]}",
            slug=f"audit-{uuid.uuid4().hex[:8]}",
        )
        self.user = User.objects.create(
            email=f"audit-{uuid.uuid4().hex[:6]}@example.com",
            tenant=self.tenant,
        )

    def test_audit_event_has_resource_type(self):
        """Audit event stores resource_type."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
        )
        self.assertEqual(event.resource_type, "ASSET")

    def test_audit_event_has_action(self):
        """Audit event stores action."""
        event = create_audit_event(
            resource_type="CONTRACT",
            action="UPDATED",
            actor_user=self.user,
            tenant=self.tenant,
        )
        self.assertEqual(event.action, "UPDATED")

    def test_audit_event_has_actor_user_id(self):
        """Audit event stores actor_user_id."""
        event = create_audit_event(
            resource_type="DATASET",
            action="DELETED",
            actor_user=self.user,
            tenant=self.tenant,
        )
        self.assertEqual(str(event.actor_user_id), str(self.user.id))

    def test_audit_event_has_tenant_id(self):
        """Audit event stores tenant_id."""
        event = create_audit_event(
            resource_type="FILE",
            action="UPLOADED",
            actor_user=self.user,
            tenant=self.tenant,
        )
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))

    def test_audit_event_has_details_json(self):
        """Audit event stores details as JSON dict."""
        details = {"file_size": 1024, "content_type": "text/csv"}
        event = create_audit_event(
            resource_type="FILE",
            action="UPLOADED",
            actor_user=self.user,
            tenant=self.tenant,
            details=details,
        )
        self.assertIsInstance(event.details_json, dict)
        self.assertIn("file_size", event.details_json)

    def test_audit_event_has_timestamp(self):
        """Audit event has timestamp field."""
        event = create_audit_event(
            resource_type="ML_MODEL",
            action="MODEL_DEPLOYED",
            tenant=self.tenant,
        )
        self.assertIsNotNone(event.timestamp)

    def test_audit_event_result_defaults_to_success(self):
        """Audit event result defaults to SUCCESS."""
        event = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            tenant=self.tenant,
        )
        self.assertEqual(event.result, "SUCCESS")

    def test_audit_event_supports_failure_result(self):
        """Audit event can record FAILURE result."""
        event = create_audit_event(
            resource_type="COMPLIANCE",
            action="SCAN_FAILED",
            tenant=self.tenant,
            result="FAILURE",
            details={"error": "Timeout"},
        )
        self.assertEqual(event.result, "FAILURE")
