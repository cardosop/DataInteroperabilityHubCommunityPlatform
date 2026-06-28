"""
Integration tests for security audit log API endpoint.

Tests the GET /api/v1/security/audit-logs/ endpoint with filtering, pagination, and authorization.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecurityLogger,
)
from tests.factories import TenantFactory, UserFactory

User = get_user_model()


class SecurityAuditLogAPIIntegrationTest(TestCase):
    """Integration tests for security audit log API."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.security_logger = SecurityLogger()

        # Create tenants and users
        self.tenant1 = TenantFactory()
        self.tenant2 = TenantFactory()
        self.admin_user = UserFactory(tenant=self.tenant1, is_platform_admin=True)
        self.regular_user = UserFactory(tenant=self.tenant1, is_platform_admin=False)

        # Create some test logs
        self.log1 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_type="external",
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
            user=self.regular_user,
            timestamp=timezone.now() - timedelta(hours=2),
        )
        self.log2 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_HIT.value,
            cache_operation="hit",
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
            user=self.regular_user,
            timestamp=timezone.now() - timedelta(hours=1),
        )
        self.log3 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            rate_limit_level="global",
            ref_path="https://example.com/schema3.json",
            tenant=self.tenant1,
            user=self.regular_user,
            timestamp=timezone.now(),
        )

    def test_list_security_audit_logs_requires_authentication(self):
        """Test that listing security audit logs requires authentication."""
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_security_audit_logs_requires_admin(self):
        """Test that listing security audit logs requires admin access."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_security_audit_logs_admin_access(self):
        """Test that admin users can list security audit logs."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 3)

    def test_filter_by_event_type(self):
        """Test filtering security audit logs by event_type."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/security/audit-logs/",
            {"event_type": SecurityEventType.EXTERNAL_REF_FETCH.value},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["event_type"], SecurityEventType.EXTERNAL_REF_FETCH.value
        )

    def test_filter_by_tenant_id(self):
        """Test filtering security audit logs by tenant_id."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/security/audit-logs/", {"tenant_id": str(self.tenant1.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        for result in response.data["results"]:
            self.assertEqual(result["tenant_id"], str(self.tenant1.id))

    def test_filter_by_user_id(self):
        """Test filtering security audit logs by user_id."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/security/audit-logs/", {"user_id": str(self.regular_user.id)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        for result in response.data["results"]:
            self.assertEqual(result["user_id"], str(self.regular_user.id))

    def test_filter_by_ref_type(self):
        """Test filtering security audit logs by ref_type."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/security/audit-logs/", {"ref_type": "external"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["ref_type"], "external")

    def test_filter_by_cache_operation(self):
        """Test filtering security audit logs by cache_operation."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/security/audit-logs/", {"cache_operation": "hit"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["cache_operation"], "hit")

    def test_filter_by_time_range(self):
        """Test filtering security audit logs by time range."""
        self.client.force_authenticate(user=self.admin_user)

        # Clear existing logs and create fresh ones with known timestamps
        SecurityAuditLog.objects.all().delete()
        now = timezone.now()

        # Note: timestamp has auto_now_add=True and save() prevents updates, so we use update() directly
        log1 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log1.id).update(timestamp=now - timedelta(hours=2))
        log1.refresh_from_db()

        log2 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_HIT.value,
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log2.id).update(timestamp=now - timedelta(hours=1))
        log2.refresh_from_db()

        log3 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            ref_path="https://example.com/schema3.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log3.id).update(timestamp=now)
        log3.refresh_from_db()

        # Filter by start_date
        start_date = (now - timedelta(hours=1.5)).isoformat()
        response = self.client.get("/api/v1/security/audit-logs/", {"start_date": start_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

        # Filter by end_date
        end_date = (now - timedelta(hours=1.5)).isoformat()
        response = self.client.get("/api/v1/security/audit-logs/", {"end_date": end_date})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_multiple_criteria(self):
        """Test filtering security audit logs by multiple criteria."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            "/api/v1/security/audit-logs/",
            {
                "tenant_id": str(self.tenant1.id),
                "event_type": SecurityEventType.CACHE_HIT.value,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["event_type"], SecurityEventType.CACHE_HIT.value
        )
        self.assertEqual(response.data["results"][0]["tenant_id"], str(self.tenant1.id))

    def test_ordering_by_timestamp(self):
        """Test ordering security audit logs by timestamp."""
        self.client.force_authenticate(user=self.admin_user)

        # Default ordering (newest first)
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["id"], str(self.log3.id))
        self.assertEqual(results[1]["id"], str(self.log2.id))
        self.assertEqual(results[2]["id"], str(self.log1.id))

        # Explicit ordering (oldest first)
        response = self.client.get("/api/v1/security/audit-logs/", {"ordering": "timestamp"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["id"], str(self.log1.id))
        self.assertEqual(results[2]["id"], str(self.log3.id))

    def test_retrieve_security_audit_log(self):
        """Test retrieving a single security audit log by ID."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"/api/v1/security/audit-logs/{self.log1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.log1.id))
        self.assertEqual(response.data["event_type"], SecurityEventType.EXTERNAL_REF_FETCH.value)
        self.assertEqual(response.data["ref_path"], "https://example.com/schema1.json")

    def test_retrieve_security_audit_log_requires_admin(self):
        """Test that retrieving a security audit log requires admin access."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f"/api/v1/security/audit-logs/{self.log1.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pagination(self):
        """Test that pagination works correctly."""
        # Create more logs to test pagination
        for i in range(10):
            SecurityAuditLog.objects.create(
                event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
                ref_path=f"https://example.com/schema{i}.json",
                tenant=self.tenant1,
            )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/security/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)
        self.assertGreater(response.data["count"], 10)

    def test_serializer_includes_all_fields(self):
        """Test that serializer includes all required fields."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(f"/api/v1/security/audit-logs/{self.log1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that all expected fields are present
        expected_fields = [
            "id",
            "event_type",
            "timestamp",
            "severity",
            "ref_type",
            "ref_path",
            "resolved_path",
            "rate_limit_level",
            "cache_operation",
            "cache_key",
            "eviction_reason",
            "violation_type",
            "attempted_path",
            "attempted_url",
            "description",
            "metadata_json",
            "request_id",
            "ip_address",
            "user_agent",
            "tenant_id",
            "tenant_name",
            "user_id",
            "user_email",
            "contract_id",
        ]
        for field in expected_fields:
            self.assertIn(field, response.data)
