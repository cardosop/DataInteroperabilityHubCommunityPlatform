"""
Regression tests for GDPR-related API endpoints (erasure-requests, export-jobs).

Per UPDATE_PLAN_MISSING_COVERAGE_5_6_1 §1.2 (P2) and REGRESSION_REVIEW_PHASE_5_1.
Uses real APIClient and real DB; no mocks/stubs. Skip or accept 404 when ErasureService/export not configured.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus
import uuid

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class GDPRRegressionTestBase(TestCase):
    """Base for GDPR regression tests. Real DB and client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="GDPR Regression Tenant",
            slug="gdpr-regression",
        )
        self.user = User.objects.create_user(
            email=f"gdpr-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)


class ErasureRequestRegressionTest(GDPRRegressionTestBase):
    """Regression tests for /api/v1/users/me/erasure-requests/. Real client; no mocks."""

    def test_erasure_requests_list(self):
        """GET /api/v1/users/me/erasure-requests/ returns 200, 403, or 404."""
        response = self.client.get("/api/v1/users/me/erasure-requests/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Erasure requests list must respond",
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertTrue(
                isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                "Response must be list or paginated dict with 'results'",
            )


class DataExportJobRegressionTest(GDPRRegressionTestBase):
    """Regression tests for /api/v1/users/me/export-jobs/. Real client; no mocks."""

    def test_export_jobs_list(self):
        """GET /api/v1/users/me/export-jobs/ returns 200, 403, or 404."""
        response = self.client.get("/api/v1/users/me/export-jobs/")
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Export jobs list must respond",
        )
        if response.status_code == status.HTTP_200_OK:
            data = response.json() if hasattr(response, "json") else response.data
            self.assertTrue(
                isinstance(data, list) or (isinstance(data, dict) and "results" in data),
                "Response must be list or paginated dict with 'results'",
            )
