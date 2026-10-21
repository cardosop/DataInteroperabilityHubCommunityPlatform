"""
Security tests: IDOR for Governance access requests.

Per tasks 29.5.2. User from tenant A must not access tenant B's access request by ID.
Real APIClient; two tenants/users; assert 403 or 404 for cross-tenant GET.
"""

import uuid

import pytest
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.models import AccessRequest, AccessRequestStatus

from .base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class AccessRequestIDORTest(IDORTestBase):
    """IDOR: user from tenant A must not access tenant B's access request by ID."""

    def test_access_request_retrieve_returns_403_or_404_for_other_tenant(self):
        """GET governance/access-requests/{id}/ for other tenant's request must return 403 or 404."""
        asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            key=f"idor-ar-asset-b-{uuid.uuid4().hex[:8]}",
            name="IDOR Access Request Asset B",
            status=AssetStatus.DRAFT,
            created_by=self.user_b,
        )
        ar_b = AccessRequest.objects.create(
            tenant=self.tenant_b,
            requested_by=self.user_b,
            asset=asset_b,
            reason="Need access for analysis",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/governance/access-requests/{ar_b.id}/")
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant access request access must be 403 or 404",
        )

    def test_access_request_retrieve_succeeds_for_own_tenant(self):
        """GET governance/access-requests/{id}/ for own tenant's request can return 200."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"idor-ar-asset-a-{uuid.uuid4().hex[:8]}",
            name="IDOR Access Request Asset A",
            status=AssetStatus.DRAFT,
            created_by=self.user_a,
        )
        ar_a = AccessRequest.objects.create(
            tenant=self.tenant_a,
            requested_by=self.user_a,
            asset=asset_a,
            reason="Need access for analysis",
            requested_access_type="READ",
            status=AccessRequestStatus.PENDING,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/v1/governance/access-requests/{ar_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
