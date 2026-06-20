"""
Security tests for ML endpoints (Task 8.6.2).

- Authentication: unauthenticated requests to ML endpoints return 401.
- Tenant isolation: user from tenant B cannot retrieve or list ML models belonging to tenant A.

Uses real API client and backend; no mocks or stubs.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.security]


class MLSecurityTestBase(TestCase):
    """Base for ML security tests: two tenants, two users."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(
            name="ML Security Tenant A",
            slug=f"ml-security-tenant-a-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.tenant_b = Tenant.objects.create(
            name="ML Security Tenant B",
            slug=f"ml-security-tenant-b-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user_a = self._create_user("mlseca@example.com", self.tenant_a)
        self.user_b = self._create_user("mlsecb@example.com", self.tenant_b)

    def _create_user(self, email, tenant):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        return User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )


class MLAuthenticationSecurityTest(MLSecurityTestBase):
    """Authentication: ML endpoints require an authenticated user."""

    def test_ml_models_list_unauthenticated_returns_401(self):
        """GET /api/v1/ml/models/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/ml/models/")
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
            "ML models list must require authentication",
        )


class MLTenantIsolationSecurityTest(MLSecurityTestBase):
    """Tenant isolation: user cannot access another tenant's ML models."""

    def test_ml_model_retrieve_returns_404_for_other_tenant(self):
        """GET /api/v1/ml/models/{id}/ for another tenant's model returns 404."""
        from hub.apps.ml.models import MLModel, ModelStatus

        model_a = MLModel.objects.create(
            tenant=self.tenant_a,
            odh_model_id="sec-test-model",
            odh_model_name="Security Test Model",
            odh_model_version="1.0",
            model_type="CLASSIFICATION",
            status=ModelStatus.TRAINED,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get(f"/api/v1/ml/models/{model_a.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant ML model access must be 403 or 404",
        )

    def test_ml_models_list_returns_only_own_tenant_models(self):
        """GET /api/v1/ml/models/ as user B must not include tenant A's models."""
        from hub.apps.ml.models import MLModel, ModelStatus

        MLModel.objects.create(
            tenant=self.tenant_a,
            odh_model_id="sec-test-model-a",
            odh_model_name="Model A",
            odh_model_version="1.0",
            model_type="CLASSIFICATION",
            status=ModelStatus.TRAINED,
        )
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get("/api/v1/ml/models/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        results = (
            data.get("results")
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        ids = [str(r.get("id")) for r in results if isinstance(r, dict) and r.get("id")]
        model_a_ids = list(
            MLModel.objects.filter(tenant=self.tenant_a).values_list("id", flat=True)
        )
        for mid in model_a_ids:
            self.assertNotIn(
                str(mid),
                ids,
                "Tenant B must not see tenant A's ML models in list",
            )
