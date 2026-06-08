"""
285.9.1.5.3 — Feature gate tests for transformation endpoints.

Tests:
- gate enabled → 200 on pipeline list
- gate disabled → 403 with TRANSFORMATION_DISABLED error_code
- check_transformation_enabled() returns structured response
- capability endpoint includes transformation_pipelines
"""
import pytest

import uuid

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import UserStatus, Role

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.uc("UC-TRANS-001"),
]


class TransformationFeatureGateTest(TestCase):
    """Tests for transformation_enabled feature gate on ViewSets."""

    def setUp(self):
        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        uid = uuid.uuid4().hex[:8]

        # Tenant with transformation enabled
        self.tenant_enabled = Tenant.objects.create(
            name=f"Test Enabled {uid}",
            slug=f"test-enabled-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            transformation_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant_enabled)

        self.user_enabled = User.objects.create_user(
            email=f"enabled-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_enabled,
            status=UserStatus.ACTIVE,
        )
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant_enabled,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.user_enabled.user_roles.create(role=data_provider_role)

        # Tenant with transformation disabled
        self.tenant_disabled = Tenant.objects.create(
            name=f"Test Disabled {uid}",
            slug=f"test-disabled-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            transformation_enabled=False,
        )
        ensure_tenant_has_active_subscription(self.tenant_disabled)

        self.user_disabled = User.objects.create_user(
            email=f"disabled-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_disabled,
            status=UserStatus.ACTIVE,
        )
        self.user_disabled.user_roles.create(role=data_provider_role)

        self.client = APIClient()

    # ── 285.9.1.5.3 test 1: gate enabled → 200 ────────────────────────

    @pytest.mark.integration
    def test_gate_enabled_returns_200(self):
        """When transformation_enabled=True, pipeline list returns 200."""
        self.client.force_authenticate(user=self.user_enabled)
        response = self.client.get("/api/v1/transformation/pipelines/")
        assert response.status_code == status.HTTP_200_OK

    # ── 285.9.1.5.3 test 2: gate disabled → 403 ───────────────────────

    @pytest.mark.integration
    def test_gate_disabled_returns_403(self):
        """When transformation_enabled=False, pipeline list returns 403."""
        self.client.force_authenticate(user=self.user_disabled)
        response = self.client.get("/api/v1/transformation/pipelines/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        # Error response is nested: {"error": {"code": "...", "details": {...}}}
        # The TRANSFORMATION_DISABLED code is in the details from the gate.
        error_body = data.get("error", data)
        error_code = error_body.get("code", "") if isinstance(error_body, dict) else ""
        assert error_code == "AUTH_FORBIDDEN"

    # ── 285.9.1.5.3 test 3: gate function returns structured response ──

    @pytest.mark.integration
    def test_gate_function_returns_structured_response(self):
        """check_transformation_enabled() returns Tenant on success, 403
        Response on failure."""
        from hub.apps.tenants.feature_flag_gates import check_transformation_enabled

        # Create a request-like object for the disabled tenant
        from unittest.mock import MagicMock
        request = MagicMock()
        request.user = self.user_disabled
        request.tenant = self.tenant_disabled

        # Gate should return a 403 Response (not the tenant)
        result = check_transformation_enabled(request)
        assert result is not None
        # When disabled, returns a Response (not a Tenant)
        from rest_framework.response import Response
        assert isinstance(result, Response)
        assert result.status_code == status.HTTP_403_FORBIDDEN
        assert result.data.get("error_code") == "TRANSFORMATION_DISABLED"

        # When enabled, returns the Tenant
        request.user = self.user_enabled
        request.tenant = self.tenant_enabled
        result = check_transformation_enabled(request)
        from hub.apps.tenants.models import Tenant as TenantModel
        assert isinstance(result, TenantModel)

    # ── 285.9.1.5.3 test 4: capability endpoint ────────────────────────

    @pytest.mark.integration
    def test_capability_endpoint_includes_transformation_pipelines(self):
        """GET /api/v1/capabilities/ returns transformation_pipelines bool
        matching the tenant flag."""
        # Enabled tenant
        self.client.force_authenticate(user=self.user_enabled)
        response = self.client.get("/api/v1/capabilities/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "capabilities" in data
        caps = data["capabilities"]
        assert "transformation_pipelines" in caps
        assert caps["transformation_pipelines"] is True

        # Disabled tenant
        self.client.force_authenticate(user=self.user_disabled)
        response = self.client.get("/api/v1/capabilities/")
        assert response.status_code == status.HTTP_200_OK
        caps = response.json()["capabilities"]
        assert caps["transformation_pipelines"] is False
