"""
Security tests for contract (datacontract) API.

Per tasks 29.6.5. Tests:
- 401 for unauthenticated access to contracts list, create, retrieve
- Tenant isolation (cross-tenant access returns 403 or 404)

No mocks - uses real implementations.
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
    "id": "datacontract-security-test",
    "name": "Datacontract Security Test",
    "schema": {"fields": [{"name": "id", "type": "string"}]},
}


class ContractSecurity401Test:
    """401: unauthenticated access to contract endpoints must be rejected."""

    def test_contracts_list_returns_401_when_unauthenticated(self):
        """GET contracts/ without auth must return 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.get("/api/v1/contracts/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_contracts_create_returns_401_when_unauthenticated(self):
        """POST contracts/ without auth must return 401."""
        from rest_framework.test import APIClient

        client = APIClient()
        response = client.post(
            "/api/v1/contracts/",
            {"original_raw": json.dumps(ODCS_MINIMAL), "original_format": "JSON"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_contracts_retrieve_returns_401_when_unauthenticated(self):
        """GET contracts/{id}/ without auth must return 401."""
        from rest_framework.test import APIClient

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import UserStatus

        from django.contrib.auth import get_user_model

        User = get_user_model()
        tenant = Tenant.objects.create(name="Temp Tenant", slug="temp-tenant-dc")
        user = User.objects.create_user(
            email="temp-dc@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        contract = Contract.objects.create(
            tenant=tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(ODCS_MINIMAL),
        )

        client = APIClient()
        response = client.get(f"/api/v1/contracts/{contract.id}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class ContractIDORSecurityTest(IDORTestBase):
    """Tenant isolation: user from tenant A must not access tenant B's contract."""

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
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ), "Cross-tenant contract access must be 403 or 404"

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
        assert response.status_code == status.HTTP_200_OK
