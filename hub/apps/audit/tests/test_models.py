"""
Unit tests for AuditEvent model.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuditEventModelTest(TestCase):
    """Test AuditEvent model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_create_audit_event_sets_tenant(self):
        """Test audit event creation sets tenant."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"},
        )

        self.assertEqual(event.tenant, self.tenant)

    def test_create_audit_event_sets_actor_user(self):
        """Test audit event creation sets actor_user."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"},
        )

        self.assertEqual(event.actor_user, self.user)

    def test_create_audit_event_sets_resource_type(self):
        """Test audit event creation sets resource_type."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"},
        )

        self.assertEqual(event.resource_type, "ASSET")

    def test_create_audit_event_sets_action(self):
        """Test audit event creation sets action."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"},
        )

        self.assertEqual(event.action, "CREATED")

    def test_create_audit_event_sets_result(self):
        """Test audit event creation sets result."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            action="CREATED",
            result="SUCCESS",
            details_json={"key": "value"},
        )

        self.assertEqual(event.result, "SUCCESS")
