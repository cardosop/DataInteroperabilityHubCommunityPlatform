"""
Security tests: IDOR for Contracts.

Per tasks 29.5.1. User from tenant A must not access tenant B's contract by ID.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import json

import pytest
from rest_framework import status

from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)

ODCS_MINIMAL = {
    "apiVersion": "odcs.io/v3.0.2",
    "kind": "DataContract",
    "id": "idor-test-contract",
    "name": "IDOR Test Contract",
    "schema": {"fields": [{"name": "id", "type": "string"}]},
}


class ContractIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's contract by ID."""

    def test_contract_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET contracts/{id}/ for other tenant's contract must return 403 or 404."""
        contract_b = Contract.objects.create(
            tenant=self.tenant_b,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(ODCS_MINIMAL),
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/contracts/{contract_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant contract access must be 403 or 404",
        )

    def test_contract_retrieve_succeeds_for_own_tenant(self):
        """GET contracts/{id}/ for own tenant's contract can return 200."""
        contract_a = Contract.objects.create(
            tenant=self.tenant_a,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(ODCS_MINIMAL),
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/contracts/{contract_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
