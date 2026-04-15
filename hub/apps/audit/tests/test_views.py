"""
Unit tests for audit views (AuditEventViewSet).

Tests cover all viewset methods: list, retrieve, export with comprehensive
scenarios including success, failure, edge cases, and error handling.
"""
import uuid

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus


def grant_role(user, tenant, name):
    """Assign a tenant-scoped role to ``user`` idempotently.

    Phase 224.3.1 — raw audit list/retrieve/export now require
    TENANT_ADMIN or AUDITOR, so existing tests that exercise these
    endpoints must grant an appropriate role during setup.
    """
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name=name, defaults={"description": name}
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AuditEventViewSetTest(TestCase):
    """Test AuditEventViewSet operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenants
        self.tenant1 = Tenant.objects.create(
            name="View Test Tenant 1",
            slug="view-test-tenant-1",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.tenant2 = Tenant.objects.create(
            name="View Test Tenant 2",
            slug="view-test-tenant-2",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create users
        self.user1 = User.objects.create_user(
            email=f"viewuser1-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        self.user2 = User.objects.create_user(
            email=f"viewuser2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )

        # Create platform admin
        self.platform_admin = User.objects.create_user(
            email=f"viewadmin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )

        # Phase 224.3.1: raw audit endpoints require AUDITOR/TENANT_ADMIN.
        # user1 tests tenant-scoped read behavior, user2 lives on tenant2 and
        # only appears in negative/platform-admin assertions here, but grant
        # the role anyway so either may be used as an authenticated caller.
        grant_role(self.user1, self.tenant1, "AUDITOR")
        grant_role(self.user2, self.tenant2, "AUDITOR")

        # Create audit events
        self.event1 = create_audit_event(
            resource_type="ASSET",
            action="CREATED",
            actor_user=self.user1,
            tenant=self.tenant1,
            resource_id="123e4567-e89b-12d3-a456-426614174000",
            details={"name": "Asset 1"},
        )

        self.event2 = create_audit_event(
            resource_type="CONTRACT",
            action="CREATED",
            actor_user=self.user1,
            tenant=self.tenant1,
            resource_id="223e4567-e89b-12d3-a456-426614174000",
            details={"name": "Contract 1"},
        )

        self.event3 = create_audit_event(
            resource_type="ASSET",
            action="UPDATED",
            actor_user=self.user2,
            tenant=self.tenant2,
            resource_id="323e4567-e89b-12d3-a456-426614174000",
            details={"name": "Asset 2"},
        )

    # ========== LIST TESTS ==========

    def test_list_audit_events_returns_200(self):
        """Test listing audit events returns 200."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_audit_events_returns_results_key(self):
        """Test listing audit events returns results key."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/")

        self.assertIn("results", response.data)

    def test_list_audit_events_tenant_scoped_includes_event1(self):
        """Test that users can see their tenant's event1."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_tenant_scoped_includes_event2(self):
        """Test that users can see their tenant's event2."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event2.id), event_ids)

    def test_list_audit_events_tenant_scoped_excludes_other_tenant_events(self):
        """Test that users cannot see other tenant's events."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertNotIn(str(self.event3.id), event_ids)

    def test_list_audit_events_platform_admin_sees_event1(self):
        """Test that platform admins can see event1."""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_platform_admin_sees_event2(self):
        """Test that platform admins can see event2."""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event2.id), event_ids)

    def test_list_audit_events_platform_admin_sees_event3(self):
        """Test that platform admins can see event3."""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/audit/audit-events/")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event3.id), event_ids)

    def test_list_audit_events_filter_by_resource_type_includes_matching(self):
        """Test filtering audit events by resource_type includes matching events."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?resource_type=ASSET")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_filter_by_resource_type_excludes_non_matching(self):
        """Test filtering audit events by resource_type excludes non-matching events."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?resource_type=ASSET")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertNotIn(str(self.event2.id), event_ids)

    def test_list_audit_events_filter_by_action_includes_event1(self):
        """Test filtering audit events by action includes event1."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?action=CREATED")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_filter_by_action_includes_event2(self):
        """Test filtering audit events by action includes event2."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?action=CREATED")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event2.id), event_ids)

    def test_list_audit_events_filter_by_actor_user_id_includes_event1(self):
        """Test filtering audit events by actor_user_id includes event1."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/?actor_user_id={self.user1.id}")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_filter_by_actor_user_id_includes_event2(self):
        """Test filtering audit events by actor_user_id includes event2."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/?actor_user_id={self.user1.id}")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event2.id), event_ids)

    def test_list_audit_events_filter_by_start_date_includes_recent_events(self):
        """Test filtering audit events by start_date includes recent events."""
        self.client.force_authenticate(user=self.user1)

        # Create an old event
        old_timestamp = timezone.now() - timedelta(days=10)
        old_event = create_audit_event(
            resource_type="TEST",
            action="OLD_ACTION",
            actor_user=self.user1,
            tenant=self.tenant1,
        )
        AuditEvent.objects.filter(pk=old_event.pk).update(timestamp=old_timestamp)

        # Filter for recent events (last 7 days)
        start_date = (timezone.now() - timedelta(days=7)).isoformat()
        response = self.client.get(f"/api/v1/audit/audit-events/?start_date={start_date}")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertIn(str(self.event1.id), event_ids)

    def test_list_audit_events_filter_by_start_date_excludes_old_events(self):
        """Test filtering audit events by start_date excludes old events."""
        self.client.force_authenticate(user=self.user1)

        # Create an old event
        old_timestamp = timezone.now() - timedelta(days=10)
        old_event = create_audit_event(
            resource_type="TEST",
            action="OLD_ACTION",
            actor_user=self.user1,
            tenant=self.tenant1,
        )
        AuditEvent.objects.filter(pk=old_event.pk).update(timestamp=old_timestamp)

        # Filter for recent events (last 7 days)
        start_date = (timezone.now() - timedelta(days=7)).isoformat()
        response = self.client.get(f"/api/v1/audit/audit-events/?start_date={start_date}")
        event_ids = [event["id"] for event in response.data["results"]]

        self.assertNotIn(str(old_event.id), event_ids)

    def test_list_audit_events_filter_by_end_date(self):
        """Test filtering audit events by end_date."""
        self.client.force_authenticate(user=self.user1)

        end_date = (timezone.now() - timedelta(days=1)).isoformat()
        response = self.client.get(f"/api/v1/audit/audit-events/?end_date={end_date}")
        event_ids = [event["id"] for event in response.data["results"]]

        # Should not include recent events
        self.assertNotIn(str(self.event1.id), event_ids)

    def test_list_audit_events_unauthenticated_returns_401(self):
        """Test listing audit events without authentication returns 401."""
        response = self.client.get("/api/v1/audit/audit-events/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_audit_events_invalid_start_date_format_ignored(self):
        """Test that invalid start_date format is ignored."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?start_date=invalid-date")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_audit_events_invalid_end_date_format_ignored(self):
        """Test that invalid end_date format is ignored."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/?end_date=invalid-date")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_audit_events_ordered_by_timestamp_descending(self):
        """Test that audit events are ordered by timestamp descending."""
        self.client.force_authenticate(user=self.user1)

        # Create a newer event
        newer_event = create_audit_event(
            resource_type="TEST",
            action="NEWER_ACTION",
            actor_user=self.user1,
            tenant=self.tenant1,
        )

        response = self.client.get("/api/v1/audit/audit-events/")
        results = response.data["results"]

        # First event should be the newest
        self.assertEqual(results[0]["id"], str(newer_event.id))

    # ========== RETRIEVE TESTS ==========

    def test_retrieve_audit_event_returns_200(self):
        """Test retrieving audit event returns 200."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_audit_event_returns_correct_id(self):
        """Test retrieving audit event returns correct id."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.data["id"], str(self.event1.id))

    def test_retrieve_audit_event_returns_correct_resource_type(self):
        """Test retrieving audit event returns correct resource_type."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.data["resource_type"], "ASSET")

    def test_retrieve_audit_event_returns_correct_action(self):
        """Test retrieving audit event returns correct action."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.data["action"], "CREATED")

    def test_retrieve_audit_event_includes_tenant_name_field(self):
        """Test retrieving audit event includes tenant_name field."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertIn("tenant_name", response.data)

    def test_retrieve_audit_event_tenant_name_matches(self):
        """Test retrieving audit event tenant_name matches."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.data["tenant_name"], self.tenant1.name)

    def test_retrieve_audit_event_includes_actor_user_email_field(self):
        """Test retrieving audit event includes actor_user_email field."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertIn("actor_user_email", response.data)

    def test_retrieve_audit_event_actor_user_email_matches(self):
        """Test retrieving audit event actor_user_email matches."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.data["actor_user_email"], self.user1.email)

    def test_retrieve_audit_event_not_found_returns_404(self):
        """Test retrieving non-existent audit event returns 404."""
        self.client.force_authenticate(user=self.user1)

        import uuid

        non_existent_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/audit/audit-events/{non_existent_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_audit_event_different_tenant_returns_404(self):
        """Test retrieving audit event from different tenant returns 404."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event3.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_audit_event_platform_admin_can_access_any(self):
        """Test platform admin can retrieve audit event from any tenant."""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(f"/api/v1/audit/audit-events/{self.event3.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_audit_event_unauthenticated_returns_401(self):
        """Test retrieving audit event without authentication returns 401."""
        response = self.client.get(f"/api/v1/audit/audit-events/{self.event1.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== EXPORT TESTS ==========

    def test_export_audit_events_json_returns_200(self):
        """Test exporting audit events as JSON returns 200."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_export_audit_events_json_returns_list(self):
        """Test exporting audit events as JSON returns list."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")

        self.assertIsInstance(response.data, list)

    def test_export_audit_events_json_includes_events(self):
        """Test exporting audit events as JSON includes events."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")

        self.assertGreater(len(response.data), 0)

    def test_export_audit_events_json_respects_resource_type_filter(self):
        """Test exporting audit events as JSON respects resource_type filter."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(
            "/api/v1/audit/audit-events/export/?format=json&resource_type=ASSET"
        )

        # Verify all returned events match the filter
        if response.data:
            self.assertEqual(response.data[0]["resource_type"], "ASSET")

    def test_export_audit_events_csv_returns_200(self):
        """Test exporting audit events as CSV returns 200."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_export_audit_events_csv_has_csv_content_type(self):
        """Test exporting audit events as CSV has CSV content type."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")

        self.assertTrue(response["Content-Type"].startswith("text/csv"))

    def test_export_audit_events_csv_has_attachment_disposition(self):
        """Test exporting audit events as CSV has attachment disposition."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")

        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_audit_events_csv_has_id_header(self):
        """Test exporting audit events as CSV has ID header."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")
        content = response.content.decode("utf-8")
        lines = content.split("\n")

        self.assertIn("ID", lines[0])

    def test_export_audit_events_csv_has_timestamp_header(self):
        """Test exporting audit events as CSV has Timestamp header."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")
        content = response.content.decode("utf-8")
        lines = content.split("\n")

        self.assertIn("Timestamp", lines[0])

    def test_export_audit_events_csv_has_resource_type_header(self):
        """Test exporting audit events as CSV has Resource Type header."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=csv")
        content = response.content.decode("utf-8")
        lines = content.split("\n")

        self.assertIn("Resource Type", lines[0])

    def _create_bulk_audit_events(self, count):
        """Create *count* audit events via bulk_create (fast)."""
        from hub.apps.audit.models import AuditEvent

        events = [
            AuditEvent(
                resource_type="TEST",
                action=f"TEST_ACTION_{i}",
                actor_user=self.user1,
                tenant=self.tenant1,
                result="SUCCESS",
            )
            for i in range(count)
        ]
        AuditEvent.objects.bulk_create(events, batch_size=2000)

    def test_export_audit_events_size_limit_exceeded_returns_400(self):
        """Test exporting audit events exceeding size limit returns 400."""
        self.client.force_authenticate(user=self.user1)
        self._create_bulk_audit_events(10001)

        response = self.client.get(
            "/api/v1/audit/audit-events/export/?format=json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST,
        )

    def test_export_audit_events_size_limit_exceeded_has_error_key(self):
        """Test exporting audit events exceeding size limit has error key."""
        self.client.force_authenticate(user=self.user1)
        self._create_bulk_audit_events(10001)

        response = self.client.get(
            "/api/v1/audit/audit-events/export/?format=json",
        )
        self.assertIn("error", response.data)

    def test_export_audit_events_size_limit_error_message(self):
        """Test exporting audit events size limit error message."""
        self.client.force_authenticate(user=self.user1)
        self._create_bulk_audit_events(10001)

        response = self.client.get(
            "/api/v1/audit/audit-events/export/?format=json",
        )

        self.assertIn("maximum", response.data["error"].lower())

    def test_export_audit_events_unauthenticated_returns_401(self):
        """Test exporting audit events without authentication returns 401."""
        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_audit_events_tenant_scoped(self):
        """Test that export is tenant-scoped."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")
        event_ids = [event["id"] for event in response.data]

        self.assertIn(str(self.event1.id), event_ids)
        self.assertNotIn(str(self.event3.id), event_ids)

    def test_export_audit_events_platform_admin_sees_all(self):
        """Test that platform admin export includes all events."""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/audit/audit-events/export/?format=json")
        event_ids = [event["id"] for event in response.data]

        self.assertIn(str(self.event1.id), event_ids)
        self.assertIn(str(self.event3.id), event_ids)

    def test_export_audit_events_default_format_is_json(self):
        """Test that export default format is JSON."""
        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/audit/audit-events/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
