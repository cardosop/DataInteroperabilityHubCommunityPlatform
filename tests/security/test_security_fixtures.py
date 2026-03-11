"""
Security test: Validates conftest fixtures (two_tenant_setup, authenticated_client_per_tenant).

Per tasks 29.1.5. Ensures fixtures work and cross-tenant isolation holds.
Real DB; no mocks.
"""

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus

pytestmark = pytest.mark.django_db(transaction=True)


def test_two_tenant_setup_cross_tenant_idor(authenticated_client_per_tenant, two_tenant_setup):
    """User from tenant A must not access tenant B's asset (validates fixtures)."""
    tenant_a, tenant_b, user_a, user_b = two_tenant_setup
    client_a, client_b = authenticated_client_per_tenant

    asset_b = Asset.objects.create(
        tenant=tenant_b,
        name="Asset in Tenant B",
        status=AssetStatus.ACTIVE,
    )
    response = client_a.get(f"/api/v1/assets/{asset_b.id}/")
    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ), "Cross-tenant asset access must be 403 or 404"
