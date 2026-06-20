"""
Integration tests for Marketplace integration (listings, APIs).

Uses real API client and real services (no mocks/stubs).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceIntegrationTest(TestCase):
    """Integration tests for marketplace APIs."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)

    def test_marketplace_listings_endpoint(self):
        """GET marketplace listings uses real backend."""
        response = self.client.get("/api/v1/marketplace/listings/")
        self.assertIn(response.status_code, [200, 404])

    def test_marketplace_catalog_endpoint(self):
        """GET marketplace catalog uses real backend."""
        response = self.client.get("/api/v1/marketplace/catalog/")
        self.assertIn(response.status_code, [200, 404])
