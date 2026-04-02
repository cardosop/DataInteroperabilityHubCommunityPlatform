"""
Integration tests for Observability Lineage API.

GET /api/v1/observability/lineage/

Tests use real DB and real contract lineage (LineageService); no mocks/stubs.
Covers: params, tenant isolation, response shape, auth, error handling.
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)


class ObservabilityLineageIntegrationTest(TestCase):
    """Integration tests for GET /api/v1/observability/lineage/ using real DB and contract lineage."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

        # Contract with lineage (real Contract; lineage from hub_contract_json)
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            hub_contract_json={
                "info": {"name": "test-contract"},
                "lineage": {
                    "contracts": [
                        {"namespace": "ns1", "name": "upstream-contract", "id": "up-1"},
                    ],
                    "entries": [
                        {"type": "derived", "source": "up-1", "target": "self"},
                    ],
                },
            },
        )

    def test_get_lineage_success_returns_200_and_shape(self):
        """GET observability/lineage/?contract_id=<id> returns 200 and contracts/entries."""
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": str(self.contract.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("contracts", response.data)
        self.assertIn("entries", response.data)
        self.assertIsInstance(response.data["contracts"], list)
        self.assertIsInstance(response.data["entries"], list)
        self.assertEqual(len(response.data["contracts"]), 1)
        self.assertEqual(len(response.data["entries"]), 1)

    def test_get_lineage_without_contract_id_returns_400(self):
        """GET /api/v1/observability/lineage/ without contract_id returns 400."""
        response = self.client.get("/api/v1/observability/lineage/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_lineage_malformed_contract_id_returns_400(self):
        """GET with malformed contract_id (not a valid UUID) returns 400."""
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": "not-a-uuid"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data.get("code"), "INVALID_UUID")

    def test_get_lineage_tenant_isolation_returns_404_for_other_tenant(self):
        """User from tenant A cannot get lineage for contract in tenant B."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            original_raw='{"info": {"name": "other"}}',
            original_format="JSON",
            hub_contract_json={"lineage": {"contracts": [], "entries": []}},
        )
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": str(other_contract.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_lineage_unauthenticated_returns_401(self):
        """GET /api/v1/observability/lineage/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": str(self.contract.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_lineage_invalid_contract_id_returns_404(self):
        """GET with non-existent contract_id returns 404."""
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_lineage_user_without_tenant_returns_400(self):
        """User without tenant gets 400 (same as other observability endpoints)."""
        user_no_tenant = User.objects.create_user(
            email=f"notenant-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": str(self.contract.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_get_lineage_empty_lineage_returns_200(self):
        """Contract with empty lineage returns 200 and empty lists."""
        empty_contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "empty"}}',
            original_format="JSON",
            hub_contract_json={"lineage": {"contracts": [], "entries": []}},
        )
        response = self.client.get(
            "/api/v1/observability/lineage/",
            {"contract_id": str(empty_contract.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contracts"], [])
        self.assertEqual(response.data["entries"], [])
