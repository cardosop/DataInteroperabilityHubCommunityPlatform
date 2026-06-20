"""Phase 111.9 — Unicode search returns correct results."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UnicodeSearchTest(TestCase):
    """Unicode search queries return correct results."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def test_search_chinese_asset_by_name(self):
        Asset.objects.create(
            tenant=self.tenant,
            key=f"cn-{uuid.uuid4().hex[:6]}",
            name="数据质量检查",
            status=AssetStatus.DRAFT,
        )
        results = Asset.objects.filter(name__icontains="数据")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().name, "数据质量检查")

    def test_search_emoji_asset(self):
        Asset.objects.create(
            tenant=self.tenant,
            key=f"em-{uuid.uuid4().hex[:6]}",
            name="🚀 Launch Data",
            status=AssetStatus.DRAFT,
        )
        results = Asset.objects.filter(name__icontains="🚀")
        self.assertEqual(results.count(), 1)

    def test_search_accented_asset(self):
        Asset.objects.create(
            tenant=self.tenant,
            key=f"ac-{uuid.uuid4().hex[:6]}",
            name="café data",
            status=AssetStatus.DRAFT,
        )
        results = Asset.objects.filter(name__icontains="café")
        self.assertEqual(results.count(), 1)

    def test_search_special_chars(self):
        Asset.objects.create(
            tenant=self.tenant,
            key=f"sp-{uuid.uuid4().hex[:6]}",
            name="O'Brien Dataset",
            status=AssetStatus.DRAFT,
        )
        results = Asset.objects.filter(name__icontains="O'Brien")
        self.assertEqual(results.count(), 1)
