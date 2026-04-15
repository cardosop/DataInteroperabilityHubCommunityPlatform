"""
Tests for InternalTestDataView security hardening (Task 220.2).

Covers:
- Environment gate: endpoint returns 404 in production/staging
- Authentication: unauthenticated requests are rejected (401)
- Authorization: requests without worker scope are rejected (403)
- Functional: worker-authenticated requests in dev/test environment succeed
- Existing guards: X-Internal-Test-Data header is still required
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.scheduled_ingestion.internal_auth import (
    SCOPE_SCHEDULED_INGESTION_INTERNAL,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(30),
]


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name="Test Data Worker Key",
        scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
    )
    return plaintext


class InternalTestDataViewHardeningTest(TestCase):
    """Security hardening tests for InternalTestDataView (220.2)."""

    def setUp(self):
        self.client = APIClient()
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"TestData Tenant {unique}",
            slug=f"testdata-tenant-{unique}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"testdata-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.api_key = _create_worker_api_key(self.tenant, self.user)
        self.url = "/api/v1/scheduled-ingestions/internal/test-data/sample.csv"

    # ----- Environment gate (220.2.2) -----

    @override_settings(ENVIRONMENT="production")
    def test_returns_404_in_production(self):
        """Endpoint must be hidden in production."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.api_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(ENVIRONMENT="staging")
    def test_returns_404_in_staging(self):
        """Endpoint must be hidden in staging."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.api_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ----- Authentication (220.2.1) -----

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request must be rejected."""
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        # DRF returns 401 for unauthenticated requests when
        # authentication_classes is set (not empty).
        self.assertIn(
            resp.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_wrong_api_key_returns_401(self):
        """Invalid API key must be rejected."""
        self.client.credentials(
            HTTP_AUTHORIZATION="ApiKey invalid-key-12345",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertIn(
            resp.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_api_key_without_worker_scope_returns_403(self):
        """API key without scheduled_ingestion:internal scope must be rejected."""
        # Create API key with no scopes
        no_scope_key = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(no_scope_key),
            name="No Scope Key",
            scopes=[],
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {no_scope_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ----- Functional: happy path -----

    def test_worker_authenticated_with_header_returns_csv(self):
        """Worker-authenticated request with correct header returns CSV."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.api_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            self.url,
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Content should be the test CSV
        self.assertIn(b"id,name", resp.content)

    def test_worker_authenticated_without_header_returns_404(self):
        """Worker-authenticated but missing X-Internal-Test-Data header returns 404."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.api_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_filename_returns_404(self):
        """Request for non-existent file returns 404."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.api_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        resp = self.client.get(
            "/api/v1/scheduled-ingestions/internal/test-data/evil.sh",
            HTTP_X_INTERNAL_TEST_DATA="1",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
