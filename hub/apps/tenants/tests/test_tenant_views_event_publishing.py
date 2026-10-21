"""
E2E tests for Tenant views event publishing.

Tests event publishing through the full API request/response cycle.
All tests use real HTTP requests and verify events are published correctly.
"""

import uuid

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.core.events.models import Event
from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig, TenantPlan, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class TenantViewsEventPublishingE2ETest(TestCase):
    """E2E tests for tenant views event publishing using real HTTP requests."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create platform admin user for tenant operations
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,  # Platform admin has no tenant
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )

        # Authenticate as platform admin
        self.client.force_authenticate(user=self.platform_admin)

    def test_create_tenant_via_api_publishes_created_event(self):
        """Test that creating tenant via POST /api/v1/tenants/ publishes tenant.created event."""
        url = reverse("tenant-list")
        data = {"name": "New Tenant via API", "slug": "new-tenant-api", "region": "us-east-1"}

        response = self.client.post(url, data, format="json")

        # Verify tenant was created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tenant_id = response.data["id"]
        tenant = Tenant.objects.get(id=tenant_id)
        self.assertEqual(tenant.name, "New Tenant via API")
        self.assertEqual(tenant.slug, "new-tenant-api")

        # Verify event was published
        events = Event.objects.filter(event_type="tenant.created", data__tenant_id=tenant_id)
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.created")
        self.assertEqual(event.data["tenant_id"], tenant_id)
        self.assertEqual(event.data["name"], tenant.name)
        self.assertEqual(event.data["slug"], tenant.slug)
        self.assertEqual(event.data["status"], tenant.status)
        self.assertEqual(event.data["kyc_status"], tenant.kyc_status)
        self.assertEqual(event.data["region"], tenant.region)
        self.assertEqual(str(event.user_id), str(self.platform_admin.id))
        self.assertEqual(event.source_service, "hub")

    def test_update_tenant_via_api_publishes_updated_event(self):
        """Test that updating tenant via PUT /api/v1/tenants/{id}/ publishes tenant.updated event."""
        # Create tenant
        original_name = f"Test Tenant {uuid.uuid4().hex[:8]}"
        tenant = Tenant.objects.create(
            name=original_name,
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        url = reverse("tenant-detail", kwargs={"id": str(tenant.id)})
        data = {
            "name": "Updated Tenant via API",
            "slug": "updated-tenant-api",
            "kyc_status": KYCStatus.VERIFIED,
        }

        response = self.client.put(url, data, format="json")

        # Verify tenant was updated
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant.refresh_from_db()
        self.assertEqual(tenant.name, "Updated Tenant via API")
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)

        # Verify event was published
        events = Event.objects.filter(event_type="tenant.updated", data__tenant_id=str(tenant.id))
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.updated")
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertIn("name", event.data["changes"])
        self.assertIn("kyc_status", event.data["changes"])
        self.assertEqual(event.data["changes"]["name"]["old"], original_name)
        self.assertEqual(event.data["changes"]["name"]["new"], "Updated Tenant via API")

    def test_partial_update_tenant_via_api_publishes_updated_event(self):
        """Test that partial updating tenant via PATCH /api/v1/tenants/{id}/ publishes tenant.updated event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        url = reverse("tenant-detail", kwargs={"id": str(tenant.id)})
        data = {"kyc_status": KYCStatus.VERIFIED}

        response = self.client.patch(url, data, format="json")

        # Verify tenant was updated
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant.refresh_from_db()
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)

        # Verify event was published
        events = Event.objects.filter(event_type="tenant.updated", data__tenant_id=str(tenant.id))
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.updated")
        self.assertIn("kyc_status", event.data["changes"])

    def test_delete_tenant_via_api_publishes_deleted_event(self):
        """Test that deleting tenant via DELETE /api/v1/tenants/{id}/ publishes tenant.deleted event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        url = reverse("tenant-detail", kwargs={"id": str(tenant.id)})

        response = self.client.delete(url)

        # Verify tenant was deleted
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

        # Verify event was published
        events = Event.objects.filter(event_type="tenant.deleted", data__tenant_id=str(tenant.id))
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.event_type, "tenant.deleted")
        self.assertEqual(event.data["tenant_id"], str(tenant.id))
        self.assertIn("deleted_at", event.data)

    def test_update_tenant_config_via_api_publishes_quota_changed_events(self):
        """Test that updating tenant config via PATCH /api/v1/tenants/{tenant_id}/config/ publishes quota.changed events."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        # Create tenant admin user
        tenant_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@tenant.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        # Create and assign TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=tenant, name="TENANT_ADMIN", defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=tenant_admin, role=tenant_admin_role, tenant=tenant)

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                },
            )

        # Authenticate as tenant admin
        self.client.force_authenticate(user=tenant_admin)

        url = reverse("tenant-config-detail", kwargs={"tenant_id": str(tenant.id)})
        data = {
            "max_file_size_bytes": 10485760,  # 10MB
            "max_job_concurrency": 10,
        }

        response = self.client.patch(url, data, format="json")

        # Verify config was updated
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = TenantConfig.objects.get(tenant=tenant)
        self.assertEqual(config.max_file_size_bytes, 10485760)
        self.assertEqual(config.max_job_concurrency, 10)

        # Verify quota changed events were published
        events = Event.objects.filter(
            event_type="tenant.quota.changed", data__tenant_id=str(tenant.id)
        ).order_by("timestamp")

        self.assertEqual(events.count(), 2)

        # Check file size quota event
        file_size_event = events.filter(data__quota_field="max_file_size_bytes").first()
        self.assertIsNotNone(file_size_event)
        self.assertEqual(file_size_event.data["quota_type"], "file_size")
        self.assertEqual(file_size_event.data["new_value"], 10485760)

        # Check job concurrency quota event
        job_concurrency_event = events.filter(data__quota_field="max_job_concurrency").first()
        self.assertIsNotNone(job_concurrency_event)
        self.assertEqual(job_concurrency_event.data["quota_type"], "job_concurrency")
        self.assertEqual(job_concurrency_event.data["new_value"], 10)

    def test_update_tenant_config_with_compliance_regimes_publishes_event(self):
        """Test that updating tenant config with compliance regimes publishes quota.changed event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        # Create tenant config
        config = TenantConfig.objects.create(tenant=tenant, allowed_compliance_regimes=["GDPR"])

        # Create tenant admin user
        tenant_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@tenant.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        # Create and assign TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=tenant, name="TENANT_ADMIN", defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=tenant_admin, role=tenant_admin_role, tenant=tenant)

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                },
            )

        # Authenticate as tenant admin
        self.client.force_authenticate(user=tenant_admin)

        url = reverse("tenant-config-detail", kwargs={"tenant_id": str(tenant.id)})
        data = {"allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA"]}

        response = self.client.patch(url, data, format="json")

        # Verify config was updated
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.allowed_compliance_regimes, ["GDPR", "LGPD", "CCPA"])

        # Verify quota changed event was published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id),
            data__quota_field="allowed_compliance_regimes",
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["quota_type"], "compliance")
        self.assertEqual(event.data["previous_value"], ["GDPR"])
        self.assertEqual(event.data["new_value"], ["GDPR", "LGPD", "CCPA"])

    def test_update_tenant_config_with_rate_limits_publishes_event(self):
        """Test that updating tenant config with rate limits publishes quota.changed event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        # Create tenant config
        config = TenantConfig.objects.create(
            tenant=tenant, rate_limits={"file_uploads": {"burst_per_10s": 10}}
        )

        # Create tenant admin user
        tenant_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@tenant.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        # Create and assign TENANT_ADMIN role
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=tenant, name="TENANT_ADMIN", defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=tenant_admin, role=tenant_admin_role, tenant=tenant)

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                },
            )

        # Authenticate as tenant admin
        self.client.force_authenticate(user=tenant_admin)

        url = reverse("tenant-config-detail", kwargs={"tenant_id": str(tenant.id)})
        new_rate_limits = {
            "file_uploads": {"burst_per_10s": 20, "sustained_per_min": 100},
            "catalog_reads": {"burst_per_10s": 5},
        }
        data = {"rate_limits": new_rate_limits}

        response = self.client.patch(url, data, format="json")

        # Verify config was updated
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config.refresh_from_db()
        self.assertEqual(config.rate_limits, new_rate_limits)

        # Verify quota changed event was published
        events = Event.objects.filter(
            event_type="tenant.quota.changed",
            data__tenant_id=str(tenant.id),
            data__quota_field="rate_limits",
        )
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["quota_type"], "rate_limits")
        self.assertEqual(event.data["previous_value"], {"file_uploads": {"burst_per_10s": 10}})
        self.assertEqual(event.data["new_value"], new_rate_limits)

    def test_update_tenant_with_no_changes_does_not_publish_event(self):
        """Test that updating tenant with same values does not publish event."""
        # Create tenant
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
        )

        url = reverse("tenant-detail", kwargs={"id": str(tenant.id)})
        data = {
            "name": tenant.name,  # Same value
            "slug": tenant.slug,  # Same value
        }

        response = self.client.patch(url, data, format="json")

        # Verify tenant was not changed
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify no event was published
        events = Event.objects.filter(event_type="tenant.updated", data__tenant_id=str(tenant.id))
        self.assertEqual(events.count(), 0)

    def test_create_tenant_with_minimal_data_publishes_event(self):
        """Test that creating tenant with minimal data publishes event correctly."""
        url = reverse("tenant-list")
        data = {"name": "Minimal Tenant", "slug": "minimal-tenant"}

        response = self.client.post(url, data, format="json")

        # Verify tenant was created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tenant_id = response.data["id"]

        # Verify event was published
        events = Event.objects.filter(event_type="tenant.created", data__tenant_id=tenant_id)
        self.assertEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["name"], "Minimal Tenant")
        self.assertEqual(event.data["slug"], "minimal-tenant")
        self.assertIsNone(event.data.get("region"))
