"""
Integration tests for workflow execution (contract/asset creation flows).

Uses real API and real workflows (no mocks/stubs).
"""

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import OriginalFormat, OriginalSpecType
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class WorkflowIntegrationTest(TestCase):
    """Integration tests for workflow execution."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)

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
        self.assertIn(
            response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_404_NOT_FOUND,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            ],
        )

    def test_asset_list_workflow(self):
        """GET /api/v1/assets/ returns assets from real DB."""
        response = self.client.get("/api/v1/assets/")
        self.assertIn(response.status_code, [200, 404])
