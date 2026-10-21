"""
Integration tests for API info / OpenAPI schema endpoints.

Verifies the API root and OpenAPI schema endpoints are reachable
and return valid responses (no mocks/stubs).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class APIInfoEndpointsIntegrationTest(TestCase):
    """Integration tests for API info and OpenAPI schema endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)

    def test_openapi_schema_available(self):
        """OpenAPI schema endpoint responds (real schema)."""
        response = self.client.get("/api/v1/openapi.json")
        self.assertEqual(response.status_code, 200)

    def test_api_v1_info_available(self):
        """API info endpoint responds."""
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, 200)
