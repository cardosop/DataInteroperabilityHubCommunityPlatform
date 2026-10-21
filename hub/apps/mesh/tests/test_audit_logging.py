"""
Unit tests for DataMeshService audit logging.

Tests verify comprehensive audit logging for domain operations:
- Domain creation (DOMAIN_CREATED)
- Domain update (UPDATED) with change tracking
- Domain deletion (DELETED)
- Ownership transfer (OWNERSHIP_TRANSFERRED)

All tests use real audit event creation (no mocks) to ensure integration.
"""

import uuid

from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.mesh.services import DataMeshService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus


class DataMeshAuditLoggingTest(TestCase):
    """Test comprehensive audit logging for data mesh domains"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        # Create another user for ownership transfer test
        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service
        self.service = DataMeshService(
            tenant_id=self.tenant_id, user_id=str(self.tenant_admin_user.id)
        )

    def test_create_domain_creates_audit_event(self):
        """Test that creating a domain creates an audit event with DOMAIN_CREATED action"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Test Domain",
            description="Test domain description",
            owner_id=str(self.tenant_admin_user.id),
            resource_quota={"storage_gb": 100},
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        )

        self.assertEqual(
            audit_events.count(), 1, "Should have exactly one DOMAIN_CREATED audit event"
        )

        audit_event = audit_events.first()
        self.assertEqual(audit_event.resource_type, "DATA_MESH_DOMAIN")
        self.assertEqual(audit_event.action, "DOMAIN_CREATED")
        self.assertEqual(audit_event.resource_id, domain.id)
        self.assertEqual(audit_event.actor_user, self.tenant_admin_user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify details_json contains required fields
        details = audit_event.details_json
        self.assertEqual(details["domain_id"], str(domain.id))
        self.assertEqual(details["domain_name"], "Test Domain")
        self.assertEqual(details["status"], domain.status)
        self.assertEqual(details["owner_id"], str(self.tenant_admin_user.id))
        self.assertEqual(details["tenant_id"], self.tenant_id)
        self.assertTrue(details["has_resource_quota"])

    def test_update_domain_creates_audit_event(self):
        """Test that updating a domain creates an audit event with UPDATED action"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Test Domain", description="Original description"
        )

        # Update domain
        self.service.update_domain(
            domain_id=str(domain.id),
            tenant_id=self.tenant_id,
            name="Updated Domain",
            description="Updated description",
            status="INACTIVE",
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="UPDATED"
        )

        self.assertEqual(audit_events.count(), 1, "Should have exactly one UPDATED audit event")

        audit_event = audit_events.first()
        self.assertEqual(audit_event.resource_type, "DATA_MESH_DOMAIN")
        self.assertEqual(audit_event.action, "UPDATED")
        self.assertEqual(audit_event.resource_id, domain.id)
        self.assertEqual(audit_event.actor_user, self.tenant_admin_user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify details_json contains required fields
        details = audit_event.details_json
        self.assertEqual(details["domain_id"], str(domain.id))
        self.assertEqual(details["domain_name"], "Updated Domain")
        self.assertEqual(details["status"], "INACTIVE")
        self.assertEqual(details["tenant_id"], self.tenant_id)
        self.assertIn("changes", details)
        self.assertIn("name", details["changes"])
        self.assertIn("description", details["changes"])
        self.assertIn("status", details["changes"])

    def test_update_domain_ownership_creates_ownership_transfer_audit_event(self):
        """Test that transferring ownership creates OWNERSHIP_TRANSFERRED audit event"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Test Domain", owner_id=str(self.tenant_admin_user.id)
        )

        # Transfer ownership
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, owner_id=str(self.other_user.id)
        )

        # Verify OWNERSHIP_TRANSFERRED audit event was created
        ownership_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN",
            resource_id=str(domain.id),
            action="OWNERSHIP_TRANSFERRED",
        )

        self.assertEqual(
            ownership_events.count(), 1, "Should have exactly one OWNERSHIP_TRANSFERRED audit event"
        )

        ownership_event = ownership_events.first()
        self.assertEqual(ownership_event.resource_type, "DATA_MESH_DOMAIN")
        self.assertEqual(ownership_event.action, "OWNERSHIP_TRANSFERRED")
        self.assertEqual(ownership_event.resource_id, domain.id)
        self.assertEqual(ownership_event.actor_user, self.tenant_admin_user)
        self.assertEqual(ownership_event.tenant, self.tenant)
        self.assertEqual(ownership_event.result, "SUCCESS")

        # Verify details_json contains ownership transfer information
        details = ownership_event.details_json
        self.assertEqual(details["domain_id"], str(domain.id))
        self.assertEqual(details["domain_name"], domain.name)
        self.assertEqual(details["owner_id"], str(self.other_user.id))
        self.assertEqual(details["tenant_id"], self.tenant_id)
        self.assertEqual(details["previous_owner_id"], str(self.tenant_admin_user.id))
        self.assertEqual(details["new_owner_id"], str(self.other_user.id))

        # Verify UPDATED audit event was also created
        updated_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="UPDATED"
        )
        self.assertEqual(updated_events.count(), 1, "Should also have UPDATED audit event")

    def test_delete_domain_creates_audit_event(self):
        """Test that deleting a domain creates an audit event with DELETED action"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Test Domain", owner_id=str(self.tenant_admin_user.id)
        )

        domain_id_str = str(domain.id)

        # Delete domain
        self.service.delete_domain(
            domain_id=domain_id_str, tenant_id=self.tenant_id, reason="Test deletion"
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=domain_id_str, action="DELETED"
        )

        self.assertEqual(audit_events.count(), 1, "Should have exactly one DELETED audit event")

        audit_event = audit_events.first()
        self.assertEqual(audit_event.resource_type, "DATA_MESH_DOMAIN")
        self.assertEqual(audit_event.action, "DELETED")
        self.assertEqual(str(audit_event.resource_id), domain_id_str)
        self.assertEqual(audit_event.actor_user, self.tenant_admin_user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify details_json contains required fields
        details = audit_event.details_json
        self.assertEqual(details["domain_id"], domain_id_str)
        self.assertEqual(details["domain_name"], "Test Domain")
        self.assertEqual(details["owner_id"], str(self.tenant_admin_user.id))
        self.assertEqual(details["tenant_id"], self.tenant_id)
        self.assertEqual(details["reason"], "Test deletion")

    def test_audit_event_details_include_all_required_fields(self):
        """Test that audit events include domain_id, owner_id, and tenant_id in details_json"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Test Domain", owner_id=str(self.tenant_admin_user.id)
        )

        # Check DOMAIN_CREATED event
        created_event = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        ).first()

        self.assertIsNotNone(created_event)
        details = created_event.details_json
        self.assertIn("domain_id", details)
        self.assertIn("owner_id", details)
        self.assertIn("tenant_id", details)
        self.assertEqual(details["domain_id"], str(domain.id))
        self.assertEqual(details["owner_id"], str(self.tenant_admin_user.id))
        self.assertEqual(details["tenant_id"], self.tenant_id)

    def test_audit_event_created_without_owner(self):
        """Test that audit events are created correctly when domain has no owner"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Test Domain", owner_id=None
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        )

        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        details = audit_event.details_json
        self.assertIsNone(details["owner_id"])

    def test_multiple_updates_create_multiple_audit_events(self):
        """Test that multiple updates create multiple UPDATED audit events"""
        domain = self.service.create_domain(tenant_id=self.tenant_id, name="Test Domain")

        # First update
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, name="Updated Name 1"
        )

        # Second update
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, description="Updated Description"
        )

        # Verify multiple audit events were created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="UPDATED"
        ).order_by("timestamp")

        self.assertEqual(audit_events.count(), 2, "Should have two UPDATED audit events")

    def test_complete_domain_lifecycle_creates_complete_audit_trail(self):
        """Test that a complete domain lifecycle creates a complete audit trail"""
        # Create domain
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Lifecycle Domain",
            owner_id=str(self.tenant_admin_user.id),
        )

        # Update domain
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, name="Updated Lifecycle Domain"
        )

        # Transfer ownership
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, owner_id=str(self.other_user.id)
        )

        # Delete domain
        self.service.delete_domain(domain_id=str(domain.id), tenant_id=self.tenant_id)

        # Verify complete audit trail
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id)
        ).order_by("timestamp")

        # Should have DOMAIN_CREATED, UPDATED (x2), OWNERSHIP_TRANSFERRED, DELETED
        self.assertEqual(audit_events.count(), 5, "Should have exactly 5 audit events")

        actions = [event.action for event in audit_events]
        self.assertIn("DOMAIN_CREATED", actions)
        self.assertIn("UPDATED", actions)
        self.assertIn("OWNERSHIP_TRANSFERRED", actions)
        self.assertIn("DELETED", actions)

    def test_audit_event_actor_user_is_correct(self):
        """Test that audit events correctly record the actor user"""
        domain = self.service.create_domain(tenant_id=self.tenant_id, name="Test Domain")

        # Verify actor_user is set correctly
        audit_event = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        ).first()

        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.tenant_admin_user)

    def test_audit_event_tenant_is_correct(self):
        """Test that audit events correctly record the tenant"""
        domain = self.service.create_domain(tenant_id=self.tenant_id, name="Test Domain")

        # Verify tenant is set correctly
        audit_event = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        ).first()

        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.tenant, self.tenant)


class DataMeshAuditLoggingIntegrationTest(TestCase):
    """Integration tests for audit logging with real services"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        # Create service
        self.service = DataMeshService(
            tenant_id=self.tenant_id, user_id=str(self.tenant_admin_user.id)
        )

    def test_audit_logging_integration_with_real_audit_service(self):
        """Test that audit logging integrates correctly with real audit service"""
        # Create domain
        domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Integration Test Domain",
            owner_id=str(self.tenant_admin_user.id),
            resource_quota={"storage_gb": 200, "compute_hours": 50},
        )

        # Verify audit event exists in database
        audit_event = AuditEvent.objects.get(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        )

        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.resource_type, "DATA_MESH_DOMAIN")
        self.assertEqual(audit_event.action, "DOMAIN_CREATED")
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify details are properly stored
        details = audit_event.details_json
        self.assertIsInstance(details, dict)
        self.assertIn("domain_id", details)
        self.assertIn("owner_id", details)
        self.assertIn("tenant_id", details)

        # Verify audit event is queryable
        queried_events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DATA_MESH_DOMAIN", action="DOMAIN_CREATED"
        )
        self.assertEqual(queried_events.count(), 1)

    def test_audit_event_immutability(self):
        """Test that audit events are immutable (cannot be updated or deleted)"""
        domain = self.service.create_domain(
            tenant_id=self.tenant_id, name="Immutability Test Domain"
        )

        audit_event = AuditEvent.objects.get(
            resource_type="DATA_MESH_DOMAIN", resource_id=str(domain.id), action="DOMAIN_CREATED"
        )

        # Try to update (should fail)
        with self.assertRaises(ValueError) as cm:
            audit_event.result = "FAILURE"
            audit_event.save()
        self.assertIn("immutable", str(cm.exception).lower())

        # Try to delete (should fail)
        with self.assertRaises(ValueError) as cm:
            audit_event.delete()
        self.assertIn("immutable", str(cm.exception).lower())
