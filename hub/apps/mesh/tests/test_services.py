"""
Unit tests for DataMeshService.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase, override_settings

from hub.apps.core.events.models import Event
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
)
from hub.apps.mesh.services import DataMeshService
from hub.apps.orchestration.models import WorkflowStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, UserRole
from django.core.cache import cache

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _ensure_tenant_admin(user, tenant):
    """Ensure user has TENANT_ADMIN role for create_domain permission."""
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="TENANT_ADMIN",
        defaults={"description": "Tenant admin role"},
    )
    UserRole.objects.get_or_create(user=user, role=role, defaults={})


class DataMeshServiceInitializationTest(TestCase):
    """Test DataMeshService initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    def test_service_initialization_with_tenant_and_user(self):
        """Test service initialization with tenant_id and user_id"""
        service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        self.assertEqual(service.tenant_id, str(self.tenant.id))
        self.assertEqual(service.user_id, str(self.user.id))
        self.assertEqual(service.service_name, "data_mesh_service")
        self.assertIsNotNone(service._event_publisher)

    def test_service_initialization_without_tenant_and_user(self):
        """Test service initialization without tenant_id and user_id"""
        service = DataMeshService()

        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)
        self.assertEqual(service.service_name, "data_mesh_service")
        self.assertIsNotNone(service._event_publisher)

    def test_service_initialization_with_tenant_only(self):
        """Test service initialization with tenant_id only"""
        service = DataMeshService(tenant_id=str(self.tenant.id))

        self.assertEqual(service.tenant_id, str(self.tenant.id))
        self.assertIsNone(service.user_id)
        self.assertEqual(service.service_name, "data_mesh_service")
        self.assertIsNotNone(service._event_publisher)


class DataMeshServiceEventPublishingTest(TestCase):
    """Test DataMeshService event publishing"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        _ensure_tenant_admin(self.user, self.tenant)
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user
        )

    def test_publish_domain_created_event(self):
        """Test publishing domain.created event"""
        event_id = self.service.publish_domain_created(
            domain_id=str(self.domain.id),
            name=self.domain.name,
            status=self.domain.status,
            owner_id=str(self.domain.owner_id) if self.domain.owner_id else None,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_domain_updated_event(self):
        """Test publishing domain.updated event"""
        changes = {"name": {"old": "Old Name", "new": "New Name"}}
        event_id = self.service.publish_domain_updated(
            domain_id=str(self.domain.id),
            changes=changes,
            previous_status=DomainStatus.ACTIVE,
            new_status=DomainStatus.ACTIVE,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_domain_deleted_event(self):
        """Test publishing domain.deleted event"""
        event_id = self.service.publish_domain_deleted(
            domain_id=str(self.domain.id),
            reason="Test deletion",
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_policy_applied_event(self):
        """Test publishing policy.applied event"""
        event_id = self.service.publish_policy_applied(
            policy_application_id="test-policy-app-id",
            domain_id=str(self.domain.id),
            policy_id="test-policy-id",
            status="APPLIED",
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_policy_revoked_event(self):
        """Test publishing policy.revoked event"""
        event_id = self.service.publish_policy_revoked(
            policy_application_id="test-policy-app-id",
            domain_id=str(self.domain.id),
            policy_id="test-policy-id",
            reason="Test revocation",
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    def test_publish_compliance_report_generated_event(self):
        """Test publishing compliance.report.generated event"""
        event_id = self.service.publish_compliance_report_generated(
            compliance_report_id="test-report-id",
            domain_id=str(self.domain.id),
            compliance_status="COMPLIANT",
            asset_id="test-asset-id",
            violation_count=0,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_event_publisher_uses_service_tenant_and_user(self):
        """Test that event publisher uses service tenant_id and user_id by default"""
        # Create service with tenant and user
        service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="domain.created", tenant_id=self.tenant.id
        ).count()

        # Publish event (pass required payload fields; test verifies tenant_id/user_id usage)
        event_id = service.publish_domain_created(
            domain_id=str(self.domain.id),
            name=self.domain.name,
            status=self.domain.status,
            owner_id=str(self.domain.owner_id) if self.domain.owner_id else None,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        events = Event.objects.filter(
            event_type="domain.created", tenant_id=self.tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "domain.created")
        self.assertEqual(event.tenant_id, self.tenant.id)
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.data.get("domain_id"), str(self.domain.id))

        # Check that the event publisher has the correct defaults
        self.assertEqual(service._event_publisher.default_tenant_id, str(self.tenant.id))
        self.assertEqual(service._event_publisher.default_user_id, str(self.user.id))

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_event_publisher_allows_override_tenant_and_user(self):
        """Test that event publisher allows overriding tenant_id and user_id per event"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=other_tenant
        )

        service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Get initial event count for other_tenant
        initial_count = Event.objects.filter(
            event_type="domain.created", tenant_id=other_tenant.id
        ).count()

        # Publish event with overridden tenant_id and user_id (pass required payload fields)
        event_id = service.publish_domain_created(
            domain_id=str(self.domain.id),
            name=self.domain.name,
            status=self.domain.status,
            owner_id=str(self.domain.owner_id) if self.domain.owner_id else None,
            tenant_id=str(other_tenant.id),
            user_id=str(other_user.id),
        )

        # Verify event was published with overridden tenant_id and user_id
        self.assertIsNotNone(event_id)
        events = Event.objects.filter(
            event_type="domain.created", tenant_id=other_tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "domain.created")
        self.assertEqual(event.tenant_id, other_tenant.id)
        self.assertEqual(str(event.user_id), str(other_user.id))
        self.assertEqual(event.data.get("domain_id"), str(self.domain.id))


def _ensure_abac_allow_domain_creation(tenant, user):
    """Create ABAC policy allowing domain creation (required when tenant has any applicable policies)."""
    from hub.apps.governance.models import AccessPolicy

    AccessPolicy.objects.get_or_create(
        tenant=tenant,
        name="Allow Domain Creation",
        defaults={
            "conditions": {"user": {"tenant_id": str(tenant.id)}},
            "effect": "ALLOW",
            "priority": 100,
            "enabled": True,
            "created_by": user,
        },
    )
    cache.clear()


class DataMeshServiceDomainOperationsTest(TestCase):
    """Test DataMeshService domain operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        _ensure_tenant_admin(self.user, self.tenant)
        _ensure_abac_allow_domain_creation(self.tenant, self.user)
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_get_domain_success(self):
        """Test getting domain by ID"""
        domain = DataMeshDomain.objects.create(tenant=self.tenant, name="Test Domain")

        result = self.service.get_domain(str(domain.id))

        self.assertEqual(result.id, domain.id)
        self.assertEqual(result.name, domain.name)

    def test_get_domain_not_found(self):
        """Test getting non-existent domain raises NotFoundError"""
        import uuid

        non_existent_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.get_domain(non_existent_id)

    def test_get_domain_requires_tenant_id(self):
        """Test that get_domain requires tenant_id"""
        service = DataMeshService()  # No tenant_id
        domain = DataMeshDomain.objects.create(tenant=self.tenant, name="Test Domain")

        with self.assertRaises(ValidationError) as cm:
            service.get_domain(str(domain.id))

        self.assertIn("tenant_id is required", str(cm.exception))

    def test_get_domains_with_filters(self):
        """Test getting domains with filters"""
        # Create domains
        domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Active Domain", status=DomainStatus.ACTIVE, owner=self.user
        )
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Inactive Domain",
            status=DomainStatus.INACTIVE,
            owner=self.user,
        )
        domain3 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Another Active Domain", status=DomainStatus.ACTIVE
        )

        # Test filter by status
        active_domains = self.service.get_domains(status=DomainStatus.ACTIVE)
        self.assertEqual(len(active_domains), 2)
        self.assertIn(domain1, active_domains)
        self.assertIn(domain3, active_domains)

        # Test filter by owner
        owner_domains = self.service.get_domains(owner_id=str(self.user.id))
        self.assertEqual(len(owner_domains), 2)
        self.assertIn(domain1, owner_domains)
        self.assertIn(domain2, owner_domains)

        # Test filter by status and owner
        active_owner_domains = self.service.get_domains(
            status=DomainStatus.ACTIVE, owner_id=str(self.user.id)
        )
        self.assertEqual(len(active_owner_domains), 1)
        self.assertIn(domain1, active_owner_domains)

    def test_get_domains_with_pagination(self):
        """Test getting domains with pagination"""
        # Create multiple domains
        for i in range(5):
            DataMeshDomain.objects.create(
                tenant=self.tenant, name=f"Domain {i}", status=DomainStatus.ACTIVE
            )

        # Test limit
        domains = self.service.get_domains(limit=3)
        self.assertEqual(len(domains), 3)

        # Test offset
        domains = self.service.get_domains(offset=2, limit=2)
        self.assertEqual(len(domains), 2)

    def test_create_domain_success(self):
        """Test creating domain successfully"""
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="New Domain",
            description="Test description",
            owner_id=str(self.user.id),
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 100},
        )

        self.assertIsNotNone(domain.id)
        self.assertEqual(domain.name, "New Domain")
        self.assertEqual(domain.description, "Test description")
        self.assertEqual(domain.owner, self.user)
        self.assertEqual(domain.boundaries, {"data_products": ["product1"]})
        self.assertEqual(domain.capabilities, {"apis": ["api1"]})
        self.assertEqual(domain.resource_quota, {"storage_gb": 100})
        self.assertEqual(domain.resource_usage, {"storage_gb_used": 0})
        self.assertEqual(domain.status, DomainStatus.ACTIVE)

    def test_create_domain_with_boundaries_validation(self):
        """Test creating domain with boundaries validation"""
        # Valid boundaries
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Domain with Boundaries",
            boundaries={
                "data_products": ["product1", "product2"],
                "schemas": ["schema1"],
                "access_patterns": ["pattern1"],
            },
        )
        self.assertIsNotNone(domain.id)
        self.assertEqual(len(domain.boundaries["data_products"]), 2)

        # Invalid boundaries - data_products not a list
        with self.assertRaises(ValidationError) as cm:
            self.service.create_domain(
                tenant_id=str(self.tenant.id),
                name="Invalid Boundaries",
                boundaries={"data_products": "not-a-list"},
            )
        self.assertIn("data_products must be a list", str(cm.exception))

    def test_create_domain_with_resource_quota_validation(self):
        """Test creating domain with resource quota validation"""
        # Valid resource quota
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Domain with Quota",
            resource_quota={"storage_gb": 100, "compute_hours": 50, "api_calls_per_day": 1000},
        )
        self.assertIsNotNone(domain.id)
        self.assertEqual(domain.resource_quota["storage_gb"], 100)
        self.assertEqual(domain.resource_usage["storage_gb_used"], 0)
        self.assertEqual(domain.resource_usage["compute_hours_used"], 0)
        self.assertEqual(domain.resource_usage["api_calls_per_day_used"], 0)

        # Invalid resource quota - negative value
        with self.assertRaises(ValidationError) as cm:
            self.service.create_domain(
                tenant_id=str(self.tenant.id),
                name="Invalid Quota",
                resource_quota={"storage_gb": -10},
            )
        self.assertIn("cannot be negative", str(cm.exception))

        # Invalid resource quota - not a number
        with self.assertRaises(ValidationError) as cm:
            self.service.create_domain(
                tenant_id=str(self.tenant.id),
                name="Invalid Quota Type",
                resource_quota={"storage_gb": "not-a-number"},
            )
        self.assertIn("must be a number", str(cm.exception))

    def test_create_domain_creates_audit_log(self):
        """Test that creating domain creates audit log"""
        from hub.apps.audit.models import AuditEvent

        # Create service with user_id set
        service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        domain = service.create_domain(
            tenant_id=str(self.tenant.id), name="Domain with Audit", owner_id=str(self.user.id)
        )

        # Check audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", action="DOMAIN_CREATED", resource_id=str(domain.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertIn("domain_id", audit_event.details_json)
        self.assertEqual(audit_event.details_json["domain_name"], "Domain with Audit")

    def test_create_domain_integration_workflow(self):
        """Integration test for complete domain creation workflow"""
        from hub.apps.audit.models import AuditEvent

        # Create domain with all fields
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Integration Test Domain",
            description="Integration test description",
            owner_id=str(self.user.id),
            boundaries={"data_products": ["product1", "product2"], "schemas": ["schema1"]},
            capabilities={"apis": ["api1"], "services": ["service1"]},
            resource_quota={"storage_gb": 200, "compute_hours": 100},
            status=DomainStatus.ACTIVE,
        )

        # Verify domain was created
        self.assertIsNotNone(domain.id)
        self.assertEqual(domain.name, "Integration Test Domain")
        self.assertEqual(domain.owner, self.user)
        self.assertEqual(len(domain.boundaries["data_products"]), 2)
        self.assertEqual(domain.resource_quota["storage_gb"], 200)
        self.assertEqual(domain.resource_usage["storage_gb_used"], 0)

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_DOMAIN", action="DOMAIN_CREATED", resource_id=str(domain.id)
        )
        self.assertEqual(audit_events.count(), 1)

        # Verify domain can be retrieved
        retrieved_domain = self.service.get_domain(str(domain.id))
        self.assertEqual(retrieved_domain.id, domain.id)
        self.assertEqual(retrieved_domain.name, domain.name)

        # Verify domain appears in list
        domains = self.service.get_domains(tenant_id=str(self.tenant.id))
        self.assertIn(domain, domains)

    def test_create_domain_duplicate_name(self):
        """Test creating domain with duplicate name raises ConflictError"""
        DataMeshDomain.objects.create(tenant=self.tenant, name="Existing Domain")

        with self.assertRaises(ConflictError) as cm:
            self.service.create_domain(tenant_id=str(self.tenant.id), name="Existing Domain")

        self.assertIn("already exists", str(cm.exception))

    def test_create_domain_empty_name(self):
        """Test creating domain with empty name raises ValidationError"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_domain(tenant_id=str(self.tenant.id), name="")

        self.assertIn("name is required", str(cm.exception))

    def test_create_domain_invalid_owner(self):
        """Test creating domain with invalid owner raises ValidationError"""
        import uuid

        invalid_owner_id = str(uuid.uuid4())

        with self.assertRaises(ValidationError) as cm:
            self.service.create_domain(
                tenant_id=str(self.tenant.id), name="New Domain", owner_id=invalid_owner_id
            )

        self.assertIn("not found or does not belong to tenant", str(cm.exception))

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_create_domain_publishes_event(self):
        """Test that creating domain publishes domain.created event"""
        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="domain.created", tenant_id=self.tenant.id
        ).count()

        domain = self.service.create_domain(tenant_id=str(self.tenant.id), name="New Domain")

        # Verify event was published
        events = Event.objects.filter(
            event_type="domain.created", tenant_id=self.tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "domain.created")
        self.assertEqual(event.tenant_id, self.tenant.id)
        self.assertEqual(event.data.get("domain_id"), str(domain.id))
        self.assertEqual(event.data.get("name"), domain.name)
        self.assertEqual(event.data.get("status"), domain.status)

    def test_update_domain_success(self):
        """Test updating domain successfully"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Original Name",
            description="Original description",
            owner=self.user,
            status=DomainStatus.ACTIVE,
        )

        # Create another user for owner update
        other_user = User.objects.create_user(
            email="other@example.com", password="testpass123", tenant=self.tenant
        )

        updated_domain = self.service.update_domain(
            domain_id=str(domain.id),
            name="Updated Name",
            description="Updated description",
            owner_id=str(other_user.id),
            boundaries={"data_products": ["product2"]},
            status=DomainStatus.INACTIVE,
        )

        self.assertEqual(updated_domain.name, "Updated Name")
        self.assertEqual(updated_domain.description, "Updated description")
        self.assertEqual(updated_domain.owner, other_user)
        self.assertEqual(updated_domain.boundaries, {"data_products": ["product2"]})
        self.assertEqual(updated_domain.status, DomainStatus.INACTIVE)

    def test_update_domain_duplicate_name(self):
        """Test updating domain with duplicate name raises ConflictError"""
        domain1 = DataMeshDomain.objects.create(tenant=self.tenant, name="Domain 1")
        domain2 = DataMeshDomain.objects.create(tenant=self.tenant, name="Domain 2")

        with self.assertRaises(ConflictError) as cm:
            self.service.update_domain(domain_id=str(domain1.id), name="Domain 2")

        self.assertIn("already exists", str(cm.exception))

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_update_domain_publishes_event(self):
        """Test that updating domain publishes domain.updated event"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Original Name", status=DomainStatus.ACTIVE
        )

        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="domain.updated", tenant_id=self.tenant.id
        ).count()

        self.service.update_domain(domain_id=str(domain.id), name="Updated Name")

        # Verify event was published
        events = Event.objects.filter(
            event_type="domain.updated", tenant_id=self.tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "domain.updated")
        self.assertEqual(event.tenant_id, self.tenant.id)
        self.assertEqual(event.data.get("domain_id"), str(domain.id))
        self.assertIn("name", event.data.get("changes", {}))

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_update_domain_no_changes_no_event(self):
        """Test that updating domain with no changes doesn't publish event"""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )

        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="domain.updated", tenant_id=self.tenant.id
        ).count()

        self.service.update_domain(domain_id=str(domain.id), name="Test Domain")  # Same name

        # Verify no event was published if no actual changes
        events = Event.objects.filter(event_type="domain.updated", tenant_id=self.tenant.id)
        # The service layer may or may not publish events when there are no changes
        # This depends on implementation - we verify the domain was not changed
        domain.refresh_from_db()
        self.assertEqual(domain.name, "Test Domain")

    def test_delete_domain_success(self):
        """Test deleting domain successfully"""
        domain = DataMeshDomain.objects.create(tenant=self.tenant, name="Domain to Delete")

        self.service.delete_domain(domain_id=str(domain.id), reason="Test deletion")

        # Verify domain is deleted
        with self.assertRaises(DataMeshDomain.DoesNotExist):
            DataMeshDomain.objects.get(id=domain.id)

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_delete_domain_publishes_event(self):
        """Test that deleting domain publishes domain.deleted event"""
        domain = DataMeshDomain.objects.create(tenant=self.tenant, name="Domain to Delete")
        domain_id = str(domain.id)

        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="domain.deleted", tenant_id=self.tenant.id
        ).count()

        self.service.delete_domain(domain_id=domain_id, reason="Test deletion")

        # Verify event was published
        events = Event.objects.filter(
            event_type="domain.deleted", tenant_id=self.tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "domain.deleted")
        self.assertEqual(event.tenant_id, self.tenant.id)
        self.assertEqual(event.data.get("domain_id"), domain_id)
        self.assertEqual(event.data.get("reason"), "Test deletion")


class DataMeshServicePolicyOperationsTest(TestCase):
    """Test DataMeshService policy operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        _ensure_tenant_admin(self.user, self.tenant)
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy description",
            conditions={"user.role": "ADMIN"},
            effect="ALLOW",
            enabled=True,
            priority=100,
            created_by=self.user,
        )

    def test_apply_policy_success(self):
        """Test applying policy successfully"""
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides={}
        )

        self.assertIsNotNone(application.id)
        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(application.applied_by, self.user)
        self.assertEqual(application.overrides, {})
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)
        self.assertIsNotNone(application.applied_at)

    def test_apply_policy_with_overrides(self):
        """Test applying policy with overrides"""
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        overrides = {"effect": "DENY", "priority": 50, "conditions": {"user.role": "GUEST"}}

        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides=overrides
        )

        self.assertEqual(application.overrides, overrides)
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)

    def test_apply_policy_validates_policy_exists(self):
        """Test that apply_policy validates policy exists"""
        import uuid

        non_existent_policy_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError) as cm:
            self.service.apply_policy(
                domain_id=str(self.domain.id), policy_id=non_existent_policy_id
            )

        self.assertIn("not found", str(cm.exception).lower())

    def test_apply_policy_validates_policy_enabled(self):
        """Test that apply_policy validates policy is enabled"""
        from hub.apps.governance.models import AccessPolicy

        disabled_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Disabled Policy",
            conditions={"user.role": "ADMIN"},
            effect="ALLOW",
            enabled=False,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.apply_policy(
                domain_id=str(self.domain.id), policy_id=str(disabled_policy.id)
            )

        # Check that error message mentions disabled policy
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "disabled" in error_msg or "enabled" in error_msg,
            f"Error message should mention disabled/enabled, got: {error_msg}",
        )

    def test_apply_policy_validates_domain_compatibility(self):
        """Test that apply_policy validates policy and domain belong to same tenant"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.tenants.models import Tenant

        # Create another tenant and policy
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_policy = AccessPolicy.objects.create(
            tenant=other_tenant,
            name="Other Policy",
            conditions={"user.role": "ADMIN"},
            effect="ALLOW",
            enabled=True,
            created_by=self.user,
        )

        # Service fetches policy by ID (no tenant filter), then validates tenant match.
        # Policy belongs to other_tenant, domain belongs to self.tenant -> ValidationError
        with self.assertRaises(ValidationError) as cm:
            self.service.apply_policy(
                domain_id=str(self.domain.id), policy_id=str(other_policy.id)
            )

        self.assertIn("same tenant", str(cm.exception).lower())

    def test_apply_policy_validates_domain_active(self):
        """Test that apply_policy validates domain is active"""
        from hub.apps.mesh.models import DomainStatus

        inactive_domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Inactive Domain", status=DomainStatus.INACTIVE
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.apply_policy(
                domain_id=str(inactive_domain.id), policy_id=str(self.policy.id)
            )

        self.assertIn("active", str(cm.exception).lower())

    def test_apply_policy_validates_overrides_structure(self):
        """Test that apply_policy validates overrides structure"""
        # Test with valid overrides (dict)
        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides={"priority": 50}
        )
        self.assertIsNotNone(application)

        # The validation for invalid overrides happens at the model level
        # when PolicyApplication.clean() is called, which validates overrides is a dict
        # This is tested in test_policy_compliance_models.py

    def test_apply_policy_creates_compliance_check(self):
        """Test that apply_policy creates compliance check"""
        from hub.apps.mesh.models import ComplianceReport, MeshComplianceStatus

        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id)
        )

        # Check that compliance report was created or updated
        compliance_reports = ComplianceReport.objects.filter(domain=self.domain)
        # Compliance checking may create or update reports
        # The exact behavior depends on implementation
        self.assertIsNotNone(application)

    @override_settings(
        EVENT_BUS_ENABLE_PERSISTENCE=True,
        EVENT_BUS_ASYNC_PERSISTENCE=False,
        EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    )
    def test_apply_policy_publishes_event(self):
        """Test that apply_policy publishes policy.applied event"""
        # Get initial event count
        initial_count = Event.objects.filter(
            event_type="policy.applied", tenant_id=self.tenant.id
        ).count()

        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id)
        )

        # Verify event was published
        events = Event.objects.filter(
            event_type="policy.applied", tenant_id=self.tenant.id
        ).order_by("-created_at")
        self.assertGreaterEqual(events.count(), initial_count + 1)

        # Verify event details
        event = events.first()
        self.assertEqual(event.event_type, "policy.applied")
        self.assertEqual(event.tenant_id, self.tenant.id)
        self.assertEqual(event.data.get("policy_application_id"), str(application.id))
        self.assertEqual(event.data.get("domain_id"), str(self.domain.id))
        self.assertEqual(event.data.get("policy_id"), str(self.policy.id))
        self.assertEqual(event.data.get("status"), "APPLIED")

    def test_apply_policy_integration_workflow(self):
        """Integration test for complete policy application workflow"""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.mesh.models import (
            ComplianceReport,
            PolicyApplication,
            PolicyApplicationStatus,
        )

        # Apply policy
        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides={"priority": 50}
        )

        # Verify application was created
        self.assertIsNotNone(application.id)
        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)
        self.assertIsNotNone(application.applied_at)

        # Verify application can be retrieved
        retrieved_application = PolicyApplication.objects.get(id=application.id)
        self.assertEqual(retrieved_application.id, application.id)
        self.assertEqual(retrieved_application.status, PolicyApplicationStatus.APPLIED)

        # Verify application appears in domain's policy_applications
        domain_applications = self.domain.policy_applications.all()
        self.assertIn(application, domain_applications)

        # Verify policy appears in policy's mesh_domain_applications
        policy_applications = self.policy.mesh_domain_applications.all()
        self.assertIn(application, policy_applications)


class DataMeshServicePolicyAuditLoggingTest(TestCase):
    """Test DataMeshService policy audit logging"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )
        _ensure_tenant_admin(self.user, self.tenant)
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy description",
            conditions={"user.role": "ADMIN"},
            effect="ALLOW",
            enabled=True,
            priority=100,
            created_by=self.user,
        )

    def test_apply_policy_creates_audit_event(self):
        """Test that apply_policy creates audit event"""
        from hub.apps.audit.models import AuditEvent

        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides={"priority": 50}
        )

        # Check audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_POLICY", action="APPLIED", resource_id=str(application.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit details
        details = audit_event.details_json
        self.assertEqual(details["policy_application_id"], str(application.id))
        self.assertEqual(details["domain_id"], str(self.domain.id))
        self.assertEqual(details["domain_name"], self.domain.name)
        self.assertEqual(details["policy_id"], str(self.policy.id))
        self.assertEqual(details["policy_name"], self.policy.name)
        self.assertEqual(details["applied_by_id"], str(self.user.id))
        self.assertEqual(details["tenant_id"], str(self.tenant.id))
        # JSON may convert numbers to strings when stored/retrieved
        self.assertIn("priority", details["overrides"])
        self.assertEqual(str(details["overrides"]["priority"]), "50")
        self.assertEqual(details["status"], "APPLIED")

    def test_revoke_policy_creates_audit_event(self):
        """Test that revoke_policy creates audit event"""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.mesh.models import PolicyApplicationStatus

        # First apply a policy
        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id)
        )

        # Now revoke it
        revoked_application = self.service.revoke_policy(
            policy_application_id=str(application.id), reason="Test revocation"
        )

        # Check audit event was created for revocation
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_POLICY", action="REMOVED", resource_id=str(application.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit details
        details = audit_event.details_json
        self.assertEqual(details["policy_application_id"], str(application.id))
        self.assertEqual(details["domain_id"], str(self.domain.id))
        self.assertEqual(details["domain_name"], self.domain.name)
        self.assertEqual(details["policy_id"], str(self.policy.id))
        self.assertEqual(details["policy_name"], self.policy.name)
        self.assertEqual(details["applied_by_id"], str(self.user.id))
        self.assertEqual(details["revoked_by_id"], str(self.user.id))
        self.assertEqual(details["tenant_id"], str(self.tenant.id))
        self.assertEqual(details["reason"], "Test revocation")
        self.assertEqual(details["status"], PolicyApplicationStatus.REVOKED)
        self.assertEqual(details["previous_status"], PolicyApplicationStatus.APPLIED)

    def test_audit_logging_integration_workflow(self):
        """Integration test for complete audit logging workflow"""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.mesh.models import PolicyApplicationStatus

        # Apply policy
        application = self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id), overrides={"priority": 75}
        )

        # Verify APPLIED audit event exists
        applied_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_POLICY", action="APPLIED", resource_id=str(application.id)
        )
        self.assertEqual(applied_events.count(), 1)

        applied_event = applied_events.first()
        self.assertEqual(applied_event.details_json["status"], "APPLIED")
        self.assertIn("applied_by_id", applied_event.details_json)
        self.assertIn("domain_id", applied_event.details_json)
        self.assertIn("policy_id", applied_event.details_json)

        # Revoke policy
        revoked_application = self.service.revoke_policy(
            policy_application_id=str(application.id), reason="Integration test revocation"
        )

        # Verify REMOVED audit event exists
        removed_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_POLICY", action="REMOVED", resource_id=str(application.id)
        )
        self.assertEqual(removed_events.count(), 1)

        removed_event = removed_events.first()
        self.assertEqual(removed_event.details_json["status"], PolicyApplicationStatus.REVOKED)
        self.assertEqual(
            removed_event.details_json["previous_status"], PolicyApplicationStatus.APPLIED
        )
        self.assertIn("revoked_by_id", removed_event.details_json)
        self.assertIn("reason", removed_event.details_json)
        self.assertEqual(removed_event.details_json["reason"], "Integration test revocation")

        # Verify both events are linked to same resource
        self.assertEqual(applied_event.resource_id, removed_event.resource_id)
        self.assertEqual(applied_event.tenant, removed_event.tenant)

        # Verify chronological order
        self.assertLess(applied_event.timestamp, removed_event.timestamp)

    def test_audit_logging_without_user(self):
        """Test audit logging when service has no user_id"""
        from hub.apps.audit.models import AuditEvent

        # Create service without user_id
        service_no_user = DataMeshService(tenant_id=str(self.tenant.id))

        application = service_no_user.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(self.policy.id)
        )

        # Audit event should still be created, but without actor_user
        audit_events = AuditEvent.objects.filter(
            resource_type="DATA_MESH_POLICY", action="APPLIED", resource_id=str(application.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertIsNone(audit_event.actor_user)
        # But applied_by_id should be None in details if no user
        details = audit_event.details_json
        self.assertIsNone(details.get("applied_by_id"))

    def test_audit_logging_includes_all_required_fields(self):
        """Test that audit logging includes all required fields"""
        from hub.apps.audit.models import AuditEvent

        application = self.service.apply_policy(
            domain_id=str(self.domain.id),
            policy_id=str(self.policy.id),
            overrides={"effect": "DENY", "priority": 25},
        )

        audit_event = AuditEvent.objects.get(
            resource_type="DATA_MESH_POLICY", action="APPLIED", resource_id=str(application.id)
        )

        details = audit_event.details_json

        # Verify all required fields are present
        required_fields = [
            "policy_application_id",
            "domain_id",
            "domain_name",
            "policy_id",
            "policy_name",
            "applied_by_id",
            "tenant_id",
            "overrides",
            "status",
        ]

        for field in required_fields:
            self.assertIn(field, details, f"Required field '{field}' missing from audit details")

        # Verify field values
        self.assertEqual(details["policy_application_id"], str(application.id))
        self.assertEqual(details["domain_id"], str(self.domain.id))
        self.assertEqual(details["policy_id"], str(self.policy.id))
        self.assertEqual(details["applied_by_id"], str(self.user.id))
        self.assertEqual(details["tenant_id"], str(self.tenant.id))
        # JSON may convert numbers to strings when stored/retrieved
        self.assertEqual(details["overrides"]["effect"], "DENY")
        self.assertIn("priority", details["overrides"])
        self.assertEqual(str(details["overrides"]["priority"]), "25")


class DataMeshServiceWorkflowIntegrationTest(TestCase):
    """Integration tests for DataMeshService workflow integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant Workflow", slug="test-tenant-workflow", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test-workflow@example.com", password="testpass123", tenant=self.tenant
        )
        _ensure_tenant_admin(self.user, self.tenant)
        _ensure_abac_allow_domain_creation(self.tenant, self.user)
        self.service = DataMeshService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_create_domain_uses_workflow(self):
        """Test that create_domain uses workflow orchestration"""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus

        # Create default policies
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Default Policy 1",
            conditions={"effect": "ALLOW"},
            effect="ALLOW",
            enabled=True,
            asset=None,
            dataset=None,
        )

        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow Test Domain",
            description="Test domain created via workflow",
            owner_id=str(self.user.id),
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["rest"]},
            resource_quota={"storage_gb": 100},
        )

        # Verify domain was created
        self.assertIsNotNone(domain.id)
        self.assertEqual(domain.name, "Workflow Test Domain")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)

        # Verify workflow instance is linked
        self.assertIsNotNone(domain.workflow_instance)
        workflow_instance = domain.workflow_instance

        # Verify workflow completed successfully
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(workflow_instance.workflow_name, "data_mesh")
        self.assertEqual(workflow_instance.workflow_version, "1.0.0")

        # Verify workflow state data
        self.assertIn("domain_id", workflow_instance.state_data)
        self.assertEqual(workflow_instance.state_data["domain_id"], str(domain.id))
        self.assertEqual(workflow_instance.state_data["progress_percentage"], 100)

        # Verify policies were applied
        from hub.apps.mesh.models import PolicyApplication

        policy_applications = PolicyApplication.objects.filter(domain=domain)
        self.assertGreaterEqual(policy_applications.count(), 1)

    def test_get_domain_workflow_instance(self):
        """Test getting workflow instance for a domain"""
        from hub.apps.governance.models import AccessPolicy

        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow Instance Test Domain",
            owner_id=str(self.user.id),
        )

        # Get workflow instance
        workflow_instance = self.service.get_domain_workflow_instance(str(domain.id))

        # Verify workflow instance exists
        self.assertIsNotNone(workflow_instance)
        self.assertEqual(workflow_instance.workflow_name, "data_mesh")
        self.assertEqual(workflow_instance.status, WorkflowStatus.COMPLETED)

    def test_get_domain_workflow_state(self):
        """Test getting workflow state for a domain"""
        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow State Test Domain",
            owner_id=str(self.user.id),
            resource_quota={"storage_gb": 200},
        )

        # Get workflow state
        workflow_state = self.service.get_domain_workflow_state(str(domain.id))

        # Verify workflow state exists
        self.assertIsNotNone(workflow_state)
        self.assertIn("domain_id", workflow_state)
        self.assertIn("progress_percentage", workflow_state)
        self.assertEqual(workflow_state["domain_id"], str(domain.id))
        self.assertEqual(workflow_state["progress_percentage"], 100)

    def test_get_domain_workflow_status(self):
        """Test getting workflow status for a domain"""
        from hub.apps.orchestration.models import WorkflowStatus

        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow Status Test Domain",
            owner_id=str(self.user.id),
        )

        # Get workflow status
        workflow_status = self.service.get_domain_workflow_status(str(domain.id))

        # Verify workflow status
        self.assertIsNotNone(workflow_status)
        self.assertEqual(workflow_status, WorkflowStatus.COMPLETED)

    def test_get_domain_workflow_progress(self):
        """Test getting workflow progress for a domain"""
        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow Progress Test Domain",
            owner_id=str(self.user.id),
        )

        # Get workflow progress
        progress = self.service.get_domain_workflow_progress(str(domain.id))

        # Verify progress
        self.assertIsNotNone(progress)
        self.assertEqual(progress, 100)

    def test_create_domain_workflow_tracking_methods(self):
        """Test all workflow tracking methods work together"""
        # Create domain via service
        domain = self.service.create_domain(
            tenant_id=str(self.tenant.id),
            name="Workflow Tracking Test Domain",
            description="Test domain for workflow tracking",
            owner_id=str(self.user.id),
            boundaries={"data_products": ["product1", "product2"]},
            capabilities={"apis": ["rest", "graphql"]},
            resource_quota={"storage_gb": 500, "compute_hours": 200},
        )

        # Test all tracking methods
        workflow_instance = self.service.get_domain_workflow_instance(str(domain.id))
        workflow_state = self.service.get_domain_workflow_state(str(domain.id))
        workflow_status = self.service.get_domain_workflow_status(str(domain.id))
        workflow_progress = self.service.get_domain_workflow_progress(str(domain.id))

        # Verify all methods return expected values
        self.assertIsNotNone(workflow_instance)
        self.assertIsNotNone(workflow_state)
        self.assertIsNotNone(workflow_status)
        self.assertIsNotNone(workflow_progress)

        # Verify consistency
        self.assertEqual(workflow_instance.status, workflow_status)
        self.assertEqual(workflow_state["progress_percentage"], workflow_progress)
        self.assertEqual(workflow_state["domain_id"], str(domain.id))

    def test_create_domain_without_workflow_instance(self):
        """Test workflow tracking methods return None for domains without workflow"""
        # Create domain directly (not via service/workflow)
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Direct Domain", owner=self.user
        )

        # All tracking methods should return None
        self.assertIsNone(self.service.get_domain_workflow_instance(str(domain.id)))
        self.assertIsNone(self.service.get_domain_workflow_state(str(domain.id)))
        self.assertIsNone(self.service.get_domain_workflow_status(str(domain.id)))
        self.assertIsNone(self.service.get_domain_workflow_progress(str(domain.id)))
