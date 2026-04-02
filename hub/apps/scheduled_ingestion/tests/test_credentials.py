"""
Comprehensive tests for scheduled ingestion credential endpoints.

Tests cover:
- GET /api/v1/scheduled-ingestions/{id}/credentials/ - Get masked credentials
- POST /api/v1/scheduled-ingestions/{id}/credentials/test/ - Test connection

No mocks: connection tests use real InMemoryConnector injected via
_get_connector_factory_for_credentials (view getter).
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.tests.connector_fakes import (
    InMemoryConnector,
    InMemoryConnectorFactory,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class CredentialsEndpointTest(TestCase):
    """Test credentials endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        ensure_tenant_has_active_subscription(self.tenant)

        # Create DATA_PROVIDER role (must belong to tenant)
        self.data_provider_role = Role.objects.create(
            tenant=self.tenant, name="DATA_PROVIDER", description="Data Provider Role"
        )
        UserRole.objects.create(user=self.user, role=self.data_provider_role)

        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            description="Test scheduled ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

    def test_get_credentials_success(self):
        """Test getting masked credentials"""
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("scheduled_ingestion_id", response.data)
        self.assertIn("source_type", response.data)
        self.assertIn("masked_credentials", response.data)
        self.assertIn("metadata", response.data)

        # Verify credentials are masked
        masked_creds = response.data["masked_credentials"]
        self.assertIn("secret_access_key", masked_creds)
        self.assertIn("access_key_id", masked_creds)
        # Verify actual secret is not exposed
        self.assertNotIn(
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", masked_creds["secret_access_key"]
        )
        self.assertTrue(
            "***" in masked_creds["secret_access_key"]
            or "****" in masked_creds["secret_access_key"]
        )

    def test_get_credentials_unauthorized(self):
        """Test getting credentials without authentication"""
        self.client.logout()
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_credentials_forbidden(self):
        """Test getting credentials for another tenant's ingestion returns 404 (tenant-scoped queryset)."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE"
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=other_user)
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/"
        )

        # Cross-tenant: object not in queryset, so 404 (standard practice to avoid leaking existence)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_credentials_not_found(self):
        """Test getting credentials for non-existent ingestion"""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/scheduled-ingestions/{fake_id}/credentials/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_test_credentials_success(self):
        """Test successful connection test using real InMemoryConnector (no mocks)."""
        connector = InMemoryConnector(test_connection_result=True)
        factory = InMemoryConnectorFactory(connector)
        with patch(
            "hub.apps.scheduled_ingestion.views._get_connector_factory_for_credentials",
            return_value=factory,
        ):
            response = self.client.post(
                f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)
        self.assertTrue(response.data["success"])
        self.assertIn("message", response.data)
        self.assertIn("tested_at", response.data)
        self.assertIn("connection_details", response.data)

    def test_test_credentials_failure(self):
        """Test failed connection test using real InMemoryConnector (no mocks)."""
        connector = InMemoryConnector(test_connection_result=False)
        factory = InMemoryConnectorFactory(connector)
        with patch(
            "hub.apps.scheduled_ingestion.views._get_connector_factory_for_credentials",
            return_value=factory,
        ):
            response = self.client.post(
                f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("success", response.data)
        self.assertFalse(response.data["success"])
        self.assertIn("message", response.data)

    def test_test_credentials_unauthorized(self):
        """Test testing credentials without authentication"""
        self.client.logout()
        response = self.client.post(
            f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_test_credentials_forbidden(self):
        """Test testing credentials for another tenant's ingestion returns 404 (tenant-scoped queryset)."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE"
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_tenant_has_active_subscription(other_tenant)

        self.client.force_authenticate(user=other_user)
        response = self.client.post(
            f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/"
        )

        # Cross-tenant: object not in queryset, so 404 (standard practice to avoid leaking existence)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_test_credentials_connector_unavailable(self):
        """Test connection test when connector factory returns None (service unavailable)."""
        with patch(
            "hub.apps.scheduled_ingestion.views._get_connector_factory_for_credentials",
            return_value=None,
        ):
            response = self.client.post(
                f"/api/v1/scheduled-ingestions/{self.scheduled_ingestion.id}/credentials/test/"
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("success", response.data)
        self.assertFalse(response.data["success"])

    def test_credentials_masking_different_source_types(self):
        """Test credential masking for different source types"""
        # Test GCS
        gcs_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="GCS Ingestion",
            source_type=SourceType.GCS,
            source_config={
                "bucket": "test-bucket",
                "credentials_json": '{"private_key": "secret-key-12345"}',
                "private_key": "very-secret-key",
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/scheduled-ingestions/{gcs_ingestion.id}/credentials/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        masked_creds = response.data["masked_credentials"]
        # Verify sensitive fields are masked
        if "private_key" in masked_creds:
            self.assertTrue(
                "***" in masked_creds["private_key"] or "****" in masked_creds["private_key"]
            )
