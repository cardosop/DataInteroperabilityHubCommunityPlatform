"""Phase 232.4 — RoPA generator walks real Asset / ConsentPurpose rows."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.consent.models import ConsentPurpose
from hub.apps.ropa.services.generator import build_ropa_payload

User = get_user_model()


class RopaGeneratorTests(TestCase):
    def setUp(self):
        cache.clear()
        from hub.apps.tenants.models import Tenant
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
        from hub.apps.users.models import Role, UserRole, UserStatus

        uid_fragment = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ropa-gen-{uid_fragment}",
            slug=f"ropa-gen-{uid_fragment}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_ropa_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"admin-{uid_fragment}@ropa.example.com",
            password="pwd123pwd",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)

    def tearDown(self):
        cache.clear()

    @pytest.mark.integration
    def test_payload_includes_asset_and_linked_purpose(self):
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="test.privacy",
            name="Test purpose",
        )
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="c1",
            name="catalog one",
            status=AssetStatus.ACTIVE,
            categories_of_subjects=["customers"],
            recipient_categories=["processors"],
        )
        asset.processing_purposes.add(purpose)

        payload = build_ropa_payload(tenant_id=str(self.tenant.id), regulation="GDPR")
        acts = payload.get("activities") or []
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["key"], "c1")
        self.assertEqual(len(acts[0]["processing_purposes"]), 1)

    @pytest.mark.integration
    def test_gap_when_purpose_missing(self):
        Asset.objects.create(
            tenant=self.tenant,
            key="c-bare",
            name="bare",
            status=AssetStatus.ACTIVE,
        )
        payload = build_ropa_payload(tenant_id=str(self.tenant.id), regulation="GDPR")
        gap_codes = [g["code"] for g in payload.get("gaps") or []]
        self.assertIn("MISSING_PROCESSING_PURPOSES", gap_codes)
        purpose_gap = next(g for g in payload["gaps"] if g["code"] == "MISSING_PROCESSING_PURPOSES")
        self.assertEqual(purpose_gap["fix_path"], "/governance/consent/purposes")
