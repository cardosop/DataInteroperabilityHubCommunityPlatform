"""
Tests for the asset classification endpoints.

GET  /api/v1/assets/{id}/classification/  — list classifications
POST /api/v1/assets/{id}/classify/        — run the rule-based classifier

These endpoints back the SDK ``GovernanceAPI.get_classification`` /
``classify_asset`` contract (SDK batch 9-2-f).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.governance.models import DataClassification
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AssetClassificationEndpointsTest(TestCase):
    """API tests for classification + classify asset actions."""

    def setUp(self):
        self.client = APIClient()
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}", slug=f"test-tenant-{unique_id}"
        )
        self.user = User.objects.create_user(
            email=f"test-{unique_id}@example.com", password="testpass123", tenant=self.tenant
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_id}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        # W7.5 — enforced scope contract: classify gates on asset scopes.
        from hub.apps.users.models import Role

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        self.user.user_roles.create(role=provider_role)
        self.client.force_authenticate(user=self.user)

    def test_classification_list_empty(self):
        """GET classification returns an empty results dict for a fresh asset."""
        response = self.client.get(f"/api/v1/assets/{self.asset.id}/classification/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"results": [], "count": 0})

    def test_classify_creates_rows(self):
        """POST classify runs the classifier and persists a classification."""
        response = self.client.post(
            f"/api/v1/assets/{self.asset.id}/classify/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(response.data["count"], 1)
        row_id = response.data["results"][0]["id"]

        self.assertTrue(DataClassification.objects.filter(id=row_id).exists())
        classification = DataClassification.objects.get(id=row_id)
        self.assertEqual(classification.asset, self.asset)
        self.assertEqual(classification.tenant, self.tenant)

        # The classification is now visible through the list endpoint.
        list_response = self.client.get(f"/api/v1/assets/{self.asset.id}/classification/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], row_id)

    def test_classification_list_is_tenant_scoped(self):
        """A foreign asset's classifications must not leak."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug=f"other-tenant-{uuid.uuid4().hex[:8]}"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.DRAFT,
        )
        DataClassification.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            field_name="data",
            category="INTERNAL",
        )

        response = self.client.get(f"/api/v1/assets/{other_asset.id}/classification/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
