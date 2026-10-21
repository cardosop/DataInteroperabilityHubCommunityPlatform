"""
Integration tests for API error handling.

Verifies 400, 401, 403, 404, and validation error responses with real client (no mocks/stubs).
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class APIErrorHandlingIntegrationTest(TestCase):
    """Integration tests for API error responses."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

    def test_404_for_nonexistent_resource(self):
        """GET nonexistent resource returns 404."""
        response = self.client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_401_without_auth(self):
        """Request without auth to protected endpoint returns 401 or 403."""
        client = APIClient()
        response = client.get("/api/v1/assets/")
        self.assertIn(
            response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_400_on_invalid_json_body(self):
        """POST with invalid JSON returns 400."""
        response = self.client.post(
            "/api/v1/contracts/",
            "not valid json",
            content_type="application/json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE],
        )

    def test_health_accepts_unauthenticated(self):
        """Health endpoint accepts unauthenticated requests."""
        unauthenticated_client = APIClient()
        response = unauthenticated_client.get("/health/")
        self.assertIn(response.status_code, [200, 503])
