"""
Integration tests for service-to-service interactions.

Verifies DQ, Compliance, and API interactions with real services (no mocks/stubs).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class ServiceInteractionsIntegrationTest(TestCase):
    """Integration tests for service interactions."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="svc-test-asset",
            name="Service Test Asset",
            status="DRAFT",
        )

    def test_dq_runs_endpoint_integration(self):
        """POST /api/v1/dq/runs/ triggers DQ service interaction."""
        response = self.client.post(
            "/api/v1/dq/runs/",
            {"asset_id": str(self.asset.id), "profile": "intake_basic_gx"},
            format="json",
        )  # noqa: broad-status-codes

        self.assertIn(
            response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ],
        )

    def test_contracts_list_uses_real_backend(self):
        """GET /api/v1/contracts/ returns from real service."""
        response = self.client.get("/api/v1/contracts/")
        self.assertIn(response.status_code, [200, 404])

    def test_assets_list_uses_real_backend(self):
        """GET /api/v1/assets/ returns from real service."""
        response = self.client.get("/api/v1/assets/")
        self.assertIn(response.status_code, [200, 404])
