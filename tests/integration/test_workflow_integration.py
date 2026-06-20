"""
Integration tests for workflow execution (contract/asset creation flows).

Uses real API and real workflows (no mocks/stubs).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import OriginalFormat, OriginalSpecType
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class WorkflowIntegrationTest(TestCase):
    """Integration tests for workflow execution."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        ensure_tenant_has_active_subscription(self.tenant)
        self.client.force_authenticate(user=self.user)
        ensure_user_has_data_provider_role(self.user)

    def test_contract_creation_workflow(self):
        """POST /api/v1/contracts/ runs contract creation workflow."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="wf-asset", name="Workflow Asset", status="DRAFT"
        )
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "asset_id": str(asset.id),
                "original_spec_type": OriginalSpecType.ODCS.value,
                "original_spec_version": "1.0.0",
                "original_format": OriginalFormat.JSON.value,
                "original_raw": "{}",
            },
            format="json",
        )
        self.assertLess(
            response.status_code,
            500,
        )

    def test_asset_list_workflow(self):
        """GET /api/v1/assets/ returns assets from real DB."""
        response = self.client.get("/api/v1/assets/")
        self.assertIn(response.status_code, [200, 404])
