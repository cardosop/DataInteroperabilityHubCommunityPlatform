"""Tests for DPIA high-risk trigger heuristics."""

from __future__ import annotations
import pytest

import pytest
import uuid

from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.consent.models import ConsentPurpose
from hub.apps.dpia.triggers import asset_requires_dpia
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class DpiaTriggerTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dpia-tr-{uid}",
            slug=f"dpia-tr-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    @pytest.mark.integration
    def test_subject_category_marker_in_name(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="Research with health outcomes",
            status=AssetStatus.ACTIVE,
        )
        self.assertTrue(asset_requires_dpia(asset))

    @pytest.mark.integration
    def test_processing_purpose_keyword(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"b-{uuid.uuid4().hex[:6]}",
            name="Basic asset",
            status=AssetStatus.ACTIVE,
        )
        p = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key="profiling_audience",
            name="Profiling for offer optimisation",
        )
        asset.processing_purposes.add(p)
        self.assertTrue(asset_requires_dpia(asset))

    @pytest.mark.integration
    def test_low_risk_asset_returns_false(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"c-{uuid.uuid4().hex[:6]}",
            name="Catalog metadata only",
            status=AssetStatus.ACTIVE,
        )
        self.assertFalse(asset_requires_dpia(asset))
