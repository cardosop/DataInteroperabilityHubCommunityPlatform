"""
Regression tests for Billing API endpoints (subscription, invoices).

Per UPDATE_PLAN_MISSING_COVERAGE_5_6_1 §1.2 (P2) and REGRESSION_REVIEW_PHASE_5_1.
Uses real APIClient and real DB; no mocks/stubs. Skip or accept 404 when billing not configured.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class BillingRegressionTestBase(TestCase):
    """Base for Billing regression tests. Real DB and client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Billing Regression Tenant",
            slug="billing-regression",
        )
        self.user = User.objects.create_user(
            email="billing@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)


class SubscriptionRegressionTest(BillingRegressionTestBase):
    """Regression tests for /api/v1/billing/subscription/. Real client; no mocks."""

    def test_subscription_current_or_list(self):
        """GET /api/v1/billing/subscription/ or list returns 200, 403, or 404."""
        response = self.client.get("/api/v1/billing/subscription/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Subscription endpoint must respond",
        )


class InvoiceRegressionTest(BillingRegressionTestBase):
    """Regression tests for /api/v1/billing/invoices/. Real client; no mocks."""

    def test_invoices_list(self):
        """GET /api/v1/billing/invoices/ returns 200 and list or paginated, or 403/404."""
        response = self.client.get("/api/v1/billing/invoices/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Invoices list must respond",
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertTrue(
                isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                "Response must be list or paginated dict with 'results'",
            )
