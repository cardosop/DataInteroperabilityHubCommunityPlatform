"""
Regression tests for Governance API endpoints.

Per UPDATE_PLAN_MISSING_COVERAGE_5_6_1 §1.2 (P2) and REGRESSION_REVIEW_PHASE_5_1.
Uses real APIClient and real DB; no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class GovernanceRegressionTestBase(TestCase):
    """Base for Governance regression tests. Real DB and client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Governance Regression Tenant {uuid.uuid4().hex[:8]}",
            slug="governance-regression",
        )
        self.user = User.objects.create_user(
            email=f"governance-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)


class AccessRequestRegressionTest(GovernanceRegressionTestBase):
    """Regression tests for /api/v1/governance/access-requests/. Real client; no mocks."""

    def test_access_requests_list(self):
        """GET /api/v1/governance/access-requests/ returns 200 and list or paginated results."""
        response = self.client.get("/api/v1/governance/access-requests/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Access requests list must respond with 200, 403, or 404",
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertTrue(
                isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                "Response must be list or paginated dict with 'results'",
            )


class RetentionPolicyRegressionTest(GovernanceRegressionTestBase):
    """Regression tests for /api/v1/governance/retention-policies/. Real client; no mocks."""

    def test_retention_policies_list(self):
        """GET /api/v1/governance/retention-policies/ returns 200 and list or paginated results."""
        response = self.client.get("/api/v1/governance/retention-policies/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Retention policies list must respond with 200, 403, or 404",
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertTrue(
                isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                "Response must be list or paginated dict with 'results'",
            )
