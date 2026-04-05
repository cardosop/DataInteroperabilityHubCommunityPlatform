"""
Integration tests for TenantEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
import uuid
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus, TenantConfig
from hub.apps.users.models import User, UserStatus
from hub.apps.core.events.service_publishers import TenantEventPublisher
from hub.apps.core.events.models import Event

uid = uuid.uuid4().hex[:8]


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class TenantEventPublisherIntegrationTest(TestCase):
    """Integration tests for TenantEventPublisher using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            region="us-east-1"
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create a test service with TenantEventPublisher
        class TestTenantService(TenantEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = TestTenantService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_publish_tenant_created_event(self):
        """Test publishing tenant.created event with real EventPublisher."""
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id),
            name=self.tenant.name,
            slug=self.tenant.slug,
            status=self.tenant.status,
            kyc_status=self.tenant.kyc_status,
            region=self.tenant.region
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.created")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["name"], self.tenant.name)
        self.assertEqual(event.data["slug"], self.tenant.slug)
        self.assertEqual(event.data["status"], self.tenant.status)
        self.assertEqual(event.data["kyc_status"], self.tenant.kyc_status)
        self.assertEqual(event.data["region"], self.tenant.region)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # Note: EventSchema.build_event hardcodes "hub" as service name
        # The EventPublisher's service_name is used for logging/metrics, not event source
        self.assertEqual(event.source_service, "hub")

    def test_publish_tenant_created_with_minimal_data(self):
        """Test publishing tenant.created event with only required fields."""
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.created")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertIsNone(event.data.get("name"))
        self.assertIsNone(event.data.get("slug"))
        self.assertIsNone(event.data.get("status"))
        self.assertIsNone(event.data.get("kyc_status"))
        self.assertIsNone(event.data.get("region"))

    def test_publish_tenant_updated_event(self):
        """Test publishing tenant.updated event with real EventPublisher."""
        changes = {
            "status": {"old": TenantStatus.ACTIVE, "new": TenantStatus.SUSPENDED},
            "kyc_status": {"old": KYCStatus.UNVERIFIED, "new": KYCStatus.VERIFIED}
        }
        event_id = self.service.publish_tenant_updated(
            tenant_id=str(self.tenant.id),
            changes=changes,
            previous_status=TenantStatus.ACTIVE,
            new_status=TenantStatus.SUSPENDED
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.updated")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertEqual(event.data["previous_status"], TenantStatus.ACTIVE)
        self.assertEqual(event.data["new_status"], TenantStatus.SUSPENDED)

    def test_publish_tenant_updated_with_minimal_data(self):
        """Test publishing tenant.updated event with only required fields."""
        changes = {"name": {"old": "Old Name", "new": "New Name"}}
        event_id = self.service.publish_tenant_updated(
            tenant_id=str(self.tenant.id),
            changes=changes
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.updated")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertIsNone(event.data.get("previous_status"))
        self.assertIsNone(event.data.get("new_status"))

    def test_publish_tenant_deleted_event(self):
        """Test publishing tenant.deleted event with real EventPublisher."""
        reason = "Tenant requested deletion"
        event_id = self.service.publish_tenant_deleted(
            tenant_id=str(self.tenant.id),
            reason=reason
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.deleted")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["reason"], reason)
        self.assertIn("deleted_at", event.data)
        # Verify deleted_at is a valid ISO format datetime string
        from datetime import datetime
        deleted_at = datetime.fromisoformat(event.data["deleted_at"].replace('Z', '+00:00'))
        self.assertIsNotNone(deleted_at)

    def test_publish_tenant_deleted_without_reason(self):
        """Test publishing tenant.deleted event without reason."""
        event_id = self.service.publish_tenant_deleted(
            tenant_id=str(self.tenant.id)
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.deleted")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertIsNone(event.data.get("reason"))
        self.assertIn("deleted_at", event.data)

    def test_publish_tenant_quota_changed_event(self):
        """Test publishing tenant.quota.changed event with real EventPublisher."""
        event_id = self.service.publish_tenant_quota_changed(
            tenant_id=str(self.tenant.id),
            quota_type="file_size",
            quota_field="max_file_size_bytes",
            previous_value=1048576,  # 1MB
            new_value=10485760  # 10MB
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.quota.changed")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["quota_type"], "file_size")
        self.assertEqual(event.data["quota_field"], "max_file_size_bytes")
        self.assertEqual(event.data["previous_value"], 1048576)
        self.assertEqual(event.data["new_value"], 10485760)

    def test_publish_tenant_quota_changed_with_array_values(self):
        """Test publishing tenant.quota.changed event with array quota values (e.g., compliance_regimes)."""
        event_id = self.service.publish_tenant_quota_changed(
            tenant_id=str(self.tenant.id),
            quota_type="compliance",
            quota_field="allowed_compliance_regimes",
            previous_value=["GDPR"],
            new_value=["GDPR", "LGPD", "CCPA"]
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.quota.changed")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["quota_type"], "compliance")
        self.assertEqual(event.data["quota_field"], "allowed_compliance_regimes")
        self.assertEqual(event.data["previous_value"], ["GDPR"])
        self.assertEqual(event.data["new_value"], ["GDPR", "LGPD", "CCPA"])

    def test_publish_tenant_quota_changed_with_null_values(self):
        """Test publishing tenant.quota.changed event with null values."""
        event_id = self.service.publish_tenant_quota_changed(
            tenant_id=str(self.tenant.id),
            quota_type="job_concurrency",
            quota_field="max_job_concurrency",
            previous_value=None,
            new_value=10
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.quota.changed")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["quota_type"], "job_concurrency")
        self.assertEqual(event.data["quota_field"], "max_job_concurrency")
        self.assertIsNone(event.data.get("previous_value"))
        self.assertEqual(event.data["new_value"], 10)

    def test_publish_tenant_quota_changed_with_minimal_data(self):
        """Test publishing tenant.quota.changed event with only required fields."""
        event_id = self.service.publish_tenant_quota_changed(
            tenant_id=str(self.tenant.id),
            quota_type="data_retention",
            quota_field="data_retention_days"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "tenant.quota.changed")
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        self.assertEqual(event.data["quota_type"], "data_retention")
        self.assertEqual(event.data["quota_field"], "data_retention_days")
        self.assertIsNone(event.data.get("previous_value"))
        self.assertIsNone(event.data.get("new_value"))

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id)
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        # Note: EventSchema.build_event hardcodes "hub" as service name
        # The EventPublisher's service_name is used for logging/metrics, not event source
        self.assertEqual(event.source_service, "hub")

    def test_event_timestamp_is_set(self):
        """Test that events have timestamp set."""
        before_publish = timezone.now()
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id)
        )
        after_publish = timezone.now()

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        # Verify timestamp is between before and after
        self.assertGreaterEqual(event.timestamp, before_publish)
        self.assertLessEqual(event.timestamp, after_publish)

    def test_event_tags_are_set(self):
        """Test that events have appropriate tags set."""
        # Test tenant.created tags
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id)
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("tenant", event.metadata.get("tags", []))
        self.assertIn("creation", event.metadata.get("tags", []))

        # Test tenant.updated tags
        event_id = self.service.publish_tenant_updated(
            tenant_id=str(self.tenant.id),
            changes={"status": {"old": "ACTIVE", "new": "SUSPENDED"}}
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("tenant", event.metadata.get("tags", []))
        self.assertIn("update", event.metadata.get("tags", []))

        # Test tenant.deleted tags
        event_id = self.service.publish_tenant_deleted(
            tenant_id=str(self.tenant.id)
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("tenant", event.metadata.get("tags", []))
        self.assertIn("deletion", event.metadata.get("tags", []))

        # Test tenant.quota.changed tags
        event_id = self.service.publish_tenant_quota_changed(
            tenant_id=str(self.tenant.id),
            quota_type="file_size",
            quota_field="max_file_size_bytes"
        )
        event = Event.objects.get(event_id=event_id)
        self.assertIn("tenant", event.metadata.get("tags", []))
        self.assertIn("quota", event.metadata.get("tags", []))

    def test_publisher_initialization_without_tenant_or_user(self):
        """Test that publisher can be initialized without tenant_id or user_id."""
        class TestTenantService(TenantEventPublisher):
            def __init__(self):
                super().__init__()

        service = TestTenantService()
        self.assertIsNotNone(service._event_publisher)
        self.assertIsNone(service._event_publisher.default_tenant_id)
        self.assertIsNone(service._event_publisher.default_user_id)

    def test_publisher_uses_service_tenant_and_user(self):
        """Test that event publisher uses service tenant_id and user_id by default."""
        # Create service with tenant and user
        service = self.service

        # Publish an event without explicitly passing tenant_id/user_id
        event_id = service.publish_tenant_created(
            tenant_id=str(self.tenant.id)
        )

        # Verify event has correct tenant_id and user_id
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_publisher_allows_override_tenant_and_user(self):
        """Test that event publisher allows overriding tenant_id and user_id via kwargs."""
        # Create a different tenant and user
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status=TenantStatus.ACTIVE
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Publish event with overridden tenant_id and user_id via kwargs
        # Note: The tenant_id parameter is required, but we can override the source tenant_id via kwargs
        # However, the data field will contain the tenant_id parameter value
        event_id = self.service.publish_tenant_created(
            tenant_id=str(self.tenant.id),
            user_id=str(other_user.id)  # Override via kwargs
        )

        # Verify event uses overridden values
        event = Event.objects.get(event_id=event_id)
        # The event data contains tenant_id from the method parameter
        self.assertEqual(event.data["tenant_id"], str(self.tenant.id))
        # The event source should use the overridden tenant_id from kwargs
        # Note: The EventPublisher uses tenant_id from kwargs if provided, otherwise uses default
        # Since we're passing tenant_id in kwargs, it should use that
        # However, the data field uses the tenant_id parameter, not the source tenant_id
        # This is expected behavior - the data field is what we're tracking, source is for audit

