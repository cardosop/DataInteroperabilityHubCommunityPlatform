"""
Phase TR.B — API integration test (relocated from E2E browser spec).

This test covers the API-level logic formerly tested in the
corresponding frontend/e2e/features/ spec. Browser interactions
are tested separately in the dual-verification replacement spec.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model

from hub.apps.contracts.models import Contract, NormalizationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestApiLogic:
    """API logic formerly in E2E browser spec."""

    def test_filter_structureless_returns_only_structureless_contracts(self):
        """GET /api/v1/contracts/?filter=structureless returns only structureless contracts.

        The frontend /admin/contract-health page calls this endpoint to list
        contracts that need schema attention.  A structureless contract is one
        whose hub_contract_json has no resolvable fields."""
        from rest_framework.test import APIClient

        # --- setup: tenant + TENANT_ADMIN user ---
        tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
            tenant=tenant,
        )
        ensure_user_has_tenant_admin_role(admin_user)

        # --- setup: one structureless contract, one normal ---
        structureless = Contract.objects.create(
            tenant=tenant,
            hub_contract_json={"models": [], "schema": {}},
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            created_by=admin_user,
        )
        normal = Contract.objects.create(
            tenant=tenant,
            hub_contract_json={
                "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}]
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=admin_user,
        )

        # --- call the endpoint ---
        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get("/api/v1/contracts/", {"filter": "structureless"})

        # --- assertions ---
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.content}"
        )
        results = response.data.get("results", response.data)
        returned_ids = {item["id"] for item in results}

        assert str(structureless.id) in returned_ids, (
            "Structureless contract should be returned by filter=structureless"
        )
        assert str(normal.id) not in returned_ids, (
            "Normal contract should NOT be returned by filter=structureless"
        )
