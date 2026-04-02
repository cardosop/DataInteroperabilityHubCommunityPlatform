"""
Integration tests for TenantService event publishing.

Tests event publishing using real TenantService and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus, TenantConfig
from hub.apps.users.models import User, UserStatus
from hub.apps.tenants.services import TenantService
from hub.apps.core.services.base import ValidationError
from hub.apps.core.events.models import Event
import uuid


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class TenantServiceEventPublishingTest(TestCase):
    """Integration tests for TenantService event publishing using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a platform admin user for tenant operations
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,  # Platform admin has no tenant
            status=UserStatus.ACTIVE,
            is_platform_admin=True
        )

        self.service = TenantService(
            tenant_id=None,  # Platform admin operations
            user_id=str(self.platform_admin.id)
        )

    def test_create_tenant_publishes_created_event(self):
        """Test that create_tenant() publishes tenant.created event."""
        tenant = self.service.create_tenant(
            name="New Tenant",
            slug="new-tenant",
            region="us-east-1"
        )

        # Verify tenant was created
        self.assertIsNotNone(tenant.id)
        self.assertEqual(tenant.name, "New Tenant")
        self.assertEqual(tenant.slug, "new-tenant")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)

        # Verify event was published
        events = Event.objects.filter(
            event_type="tenant.created",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.created")
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertEqual(event.data["name"], tenant.name)
        self.assertEqual(event.data["slug"], tenant.slug)
        self.assertEqual(event.data["status"], tenant.status)
        self.assertEqual(event.data["kyc_status"], tenant.kyc_status)
        self.assertEqual(event.data["region"], tenant.region)
        # Event source tenant_id is None for platform admin operations
        # Event data tenant_id is the created tenant's ID
        self.assertIsNone(event.tenant_id)  # Platform admin has no tenant
        self.assertEqual(str(event.user_id), str(self.platform_admin.id))
        self.assertEqual(event.source_service, "hub")

    def test_update_tenant_publishes_updated_event(self):
        """Test that update_tenant() publishes tenant.updated event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED
        )

        # Update tenant
        updated_tenant = self.service.update_tenant(
            tenant_id=str(tenant.id),
            name="Updated Tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Verify tenant was updated
        self.assertEqual(updated_tenant.name, "Updated Tenant")
        self.assertEqual(updated_tenant.kyc_status, KYCStatus.VERIFIED)

        # Verify event was published
        events = Event.objects.filter(
            event_type="tenant.updated",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.updated")
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertIn("name", event.data["changes"])
        self.assertIn("kyc_status", event.data["changes"])
        self.assertEqual(event.data["changes"]["name"]["old"], tenant.name)
        self.assertEqual(event.data["changes"]["name"]["new"], "Updated Tenant")
        self.assertEqual(event.data["changes"]["kyc_status"]["old"], KYCStatus.UNVERIFIED)
        self.assertEqual(event.data["changes"]["kyc_status"]["new"], KYCStatus.VERIFIED)
        self.assertEqual(event.data["previous_status"], TenantStatus.ACTIVE)
        self.assertEqual(event.data["new_status"], TenantStatus.ACTIVE)

    def test_update_tenant_with_no_changes_does_not_publish_event(self):
        """Test that update_tenant() with no changes does not publish event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Update tenant with same values
        updated_tenant = self.service.update_tenant(
            tenant_id=str(tenant.id),
            name=tenant.name  # Same value — no change expected
        )

        # Verify no event was published
        events = Event.objects.filter(
            event_type="tenant.updated",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 0)

    def test_delete_tenant_publishes_deleted_event(self):
        """Test that delete_tenant() publishes tenant.deleted event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Delete tenant
        deleted_tenant = self.service.delete_tenant(
            tenant_id=str(tenant.id),
            reason="Test deletion"
        )

        # Verify tenant was deleted
        self.assertEqual(deleted_tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(deleted_tenant.deleted_at)

        # Verify event was published
        events = Event.objects.filter(
            event_type="tenant.deleted",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.deleted")
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertEqual(event.data["reason"], "Test deletion")
        self.assertIn("deleted_at", event.data)

    def test_delete_tenant_without_reason_publishes_event(self):
        """Test that delete_tenant() without reason publishes tenant.deleted event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Delete tenant without reason
        deleted_tenant = self.service.delete_tenant(
            tenant_id=str(tenant.id)
        )

        # Verify tenant was deleted
        self.assertEqual(deleted_tenant.status, TenantStatus.DELETED)

        # Verify event was published
        events = Event.objects.filter(
            event_type="tenant.deleted",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.deleted")
        self.assertIsNone(event.data.get("reason"))
        self.assertIn("deleted_at", event.data)

    def test_update_tenant_config_publishes_quota_changed_events(self):
        """Test that update_tenant_config() publishes tenant.quota.changed events."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Create tenant config
        config = TenantConfig.objects.create(tenant=tenant)

        # Update config with quota changes
        updated_config = self.service.update_tenant_config(
            tenant_id=str(tenant.id),
            max_file_size_bytes=10485760,  # 10MB
            max_job_concurrency=10
        )

        # Verify config was updated
        self.assertEqual(updated_config.max_file_size_bytes, 10485760)
        self.assertEqual(updated_config.max_job_concurrency, 10)

        # Verify quota changed events were published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id)
        ).order_by("timestamp")

        self.assertEqual(events.count(), 2)

        # Check file size quota event
        file_size_event = events.filter(
            data__quota_field="max_file_size_bytes"
        ).first()
        self.assertIsNotNone(file_size_event)
        self.assertEqual(file_size_event.data["quota_type"], "file_size")
        self.assertEqual(file_size_event.data["quota_field"], "max_file_size_bytes")
        self.assertIsNone(file_size_event.data.get("previous_value"))
        self.assertEqual(file_size_event.data["new_value"], 10485760)

        # Check job concurrency quota event
        job_concurrency_event = events.filter(
            data__quota_field="max_job_concurrency"
        ).first()
        self.assertIsNotNone(job_concurrency_event)
        self.assertEqual(job_concurrency_event.data["quota_type"], "job_concurrency")
        self.assertEqual(job_concurrency_event.data["quota_field"], "max_job_concurrency")
        self.assertIsNone(job_concurrency_event.data.get("previous_value"))
        self.assertEqual(job_concurrency_event.data["new_value"], 10)

    def test_update_tenant_config_with_compliance_regimes_publishes_event(self):
        """Test that update_tenant_config() with compliance regimes publishes quota.changed event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Create tenant config
        config = TenantConfig.objects.create(
            tenant=tenant,
            allowed_compliance_regimes=["GDPR"]
        )

        # Update config with compliance regimes change
        updated_config = self.service.update_tenant_config(
            tenant_id=str(tenant.id),
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"]
        )

        # Verify config was updated
        self.assertEqual(updated_config.allowed_compliance_regimes, ["GDPR", "LGPD", "CCPA"])

        # Verify quota changed event was published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id),
            data__quota_field="allowed_compliance_regimes"
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["quota_type"], "compliance")
        self.assertEqual(event.data["quota_field"], "allowed_compliance_regimes")
        self.assertEqual(event.data["previous_value"], ["GDPR"])
        self.assertEqual(event.data["new_value"], ["GDPR", "LGPD", "CCPA"])

    def test_update_tenant_config_with_rate_limits_publishes_event(self):
        """Test that update_tenant_config() with rate limits publishes quota.changed event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Create tenant config
        config = TenantConfig.objects.create(
            tenant=tenant,
            rate_limits={"api": {"burst_per_10s": 10}}
        )

        # Update config with rate limits change
        new_rate_limits = {
            "api": {"burst_per_10s": 20, "sustained_per_min": 100},
            "upload": {"burst_per_10s": 5}
        }
        updated_config = self.service.update_tenant_config(
            tenant_id=str(tenant.id),
            rate_limits=new_rate_limits
        )

        # Verify config was updated
        self.assertEqual(updated_config.rate_limits, new_rate_limits)

        # Verify quota changed event was published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id),
            data__quota_field="rate_limits"
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["quota_type"], "rate_limits")
        self.assertEqual(event.data["quota_field"], "rate_limits")
        self.assertEqual(event.data["previous_value"], {"api": {"burst_per_10s": 10}})
        self.assertEqual(event.data["new_value"], new_rate_limits)

    def test_update_tenant_config_with_no_changes_does_not_publish_event(self):
        """Test that update_tenant_config() with no changes does not publish event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )

        # Create tenant config
        config = TenantConfig.objects.create(
            tenant=tenant,
            max_file_size_bytes=10485760
        )

        # Update config with same value
        updated_config = self.service.update_tenant_config(
            tenant_id=str(tenant.id),
            max_file_size_bytes=10485760  # Same value
        )

        # Verify no quota changed events were published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 0)

    def test_delete_already_deleted_tenant_raises_error(self):
        """Test that delete_tenant() on already deleted tenant raises ValidationError."""
        # Create and delete tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )
        self.service.delete_tenant(tenant_id=str(tenant.id))

        # Try to delete again
        with self.assertRaises(ValidationError):
            self.service.delete_tenant(tenant_id=str(tenant.id))

    def test_service_uses_tenant_and_user_from_initialization(self):
        """Test that service uses tenant_id and user_id from initialization for events."""
        # Create tenant and user
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE
        )
        user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE
        )

        # Create service with tenant and user
        service = TenantService(
            tenant_id=str(tenant.id),
            user_id=str(user.id)
        )

        # Create a new tenant (this will use service's tenant_id/user_id for event source)
        new_tenant = service.create_tenant(
            name="New Tenant",
            slug="new-tenant"
        )

        # Verify event has correct tenant_id and user_id
        events = Event.objects.filter(
            event_type="tenant.created",
            data__tenant_id=str(new_tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        # The event source tenant_id/user_id should be from the service initialization
        # (the tenant/user performing the operation)
        self.assertEqual(str(event.tenant_id), str(tenant.id))
        self.assertEqual(str(event.user_id), str(user.id))

    def test_create_tenant_with_minimal_data(self):
        """Test creating tenant with minimal required data."""
        tenant = self.service.create_tenant(
            name="Minimal Tenant",
            slug="minimal-tenant"
        )

        # Verify tenant was created
        self.assertIsNotNone(tenant.id)
        self.assertEqual(tenant.name, "Minimal Tenant")
        self.assertEqual(tenant.slug, "minimal-tenant")
        self.assertIsNone(tenant.region)

        # Verify event was published
        events = Event.objects.filter(
            event_type="tenant.created",
            data__tenant_id=str(tenant.id)
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["name"], tenant.name)
        self.assertEqual(event.data["slug"], tenant.slug)
        self.assertIsNone(event.data.get("region"))

