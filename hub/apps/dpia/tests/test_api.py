"""REST API for DPIA — real DB and middleware-style tenant resolution via user.tenant."""

from __future__ import annotations
import pytest

import pytest
import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dpia.models import Dpia, DpiaStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DpiaApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dpia-api-{uid}",
            slug=f"dpia-api-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        from django.contrib.auth import get_user_model as gum

        self.user = gum().objects.create_user(
            email=f"dpia-{uid}@example.com",
            password="test-pass-123!",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_create_list_and_asset_status(self):
        # ``wizard_payload`` is a JSON object — multipart form
        # encoding (DRF's default for ``client.post`` without
        # ``format="json"``) can't represent nested dicts and 500s.
        res = self.client.post(
            "/api/v1/dpia/records/",
            {"title": "Alpha", "regime": "GDPR", "wizard_payload": {"x": 1}},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        dpia_id = res.data["id"]

        lst = self.client.get("/api/v1/dpia/records/")
        self.assertEqual(lst.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in lst.data["results"]]
        self.assertIn(dpia_id, ids)

        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"k-{uuid.uuid4().hex[:6]}",
            name="Health analytics",
            status=AssetStatus.ACTIVE,
        )
        st = self.client.get("/api/v1/dpia/records/asset-status/", {"asset_id": str(asset.id)})
        self.assertEqual(st.status_code, status.HTTP_200_OK)
        self.assertTrue(st.data["compliance_dpia_enabled"])
        self.assertTrue(st.data["dpia_required"])

    @pytest.mark.integration
    def test_feature_disabled_blocks_create(self):
        self.tenant.compliance_dpia_enabled = False
        self.tenant.save(update_fields=["compliance_dpia_enabled"])
        res = self.client.post(
            "/api/v1/dpia/records/", {"title": "Blocked"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_create_rejects_asset_from_other_tenant(self):
        uid2 = uuid.uuid4().hex[:8]
        other = Tenant.objects.create(
            name=f"dpia-other-{uid2}",
            slug=f"dpia-other-{uid2}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=False,
        )
        foreign_asset = Asset.objects.create(
            tenant=other,
            key=f"fx-{uid2}",
            name="Foreign",
            status=AssetStatus.ACTIVE,
        )
        res = self.client.post(
            "/api/v1/dpia/records/",
            {"title": "Cross-tenant", "asset": str(foreign_asset.id)},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @pytest.mark.integration
    def test_derived_from_rejects_other_tenant_parent(self):
        uid2 = uuid.uuid4().hex[:8]
        other = Tenant.objects.create(
            name=f"dpia-parent-{uid2}",
            slug=f"dpia-parent-{uid2}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(other)
        parent = Dpia.objects.create(
            tenant=other,
            title="Platform template",
            regime="GDPR",
            status=DpiaStatus.DRAFT,
        )
        res = self.client.post(
            "/api/v1/dpia/records/",
            {"title": "Child", "regime": "GDPR", "derived_from": str(parent.id)},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class DpiaReviewApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dpia-rev-{uid}",
            slug=f"dpia-rev-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        from django.contrib.auth import get_user_model as gum

        self.dpo = gum().objects.create_user(
            email=f"dpo-{uid}@example.com",
            password="test-pass-123!",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role_dpo, _ = Role.objects.get_or_create(tenant=self.tenant, name="DPO")
        UserRole.objects.get_or_create(user=self.dpo, tenant=self.tenant, role=role_dpo)
        self.admin = gum().objects.create_user(
            email=f"adm-{uid}@example.com",
            password="test-pass-123!",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role_adm, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=self.admin, tenant=self.tenant, role=role_adm)

        self.dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Review me",
            created_by=self.admin,
            status=DpiaStatus.IN_REVIEW,
        )

    @pytest.mark.integration
    def test_dpo_review_approved(self):
        self.client.force_authenticate(user=self.dpo)
        res = self.client.post(
            f"/api/v1/dpia/records/{self.dpia.id}/review/",
            {
                "outcome": "APPROVED",
                "risk_residual": "LOW",
                "dpo_summary": "Looks fine",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], DpiaStatus.APPROVED)
