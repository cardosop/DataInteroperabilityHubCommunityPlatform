"""Phase 111.8 — Unicode input handling for assets/contracts/datasets."""
import uuid
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UnicodeInputTest(TestCase):
    """Unicode characters persist and retrieve correctly."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE")

    def test_chinese_characters_in_asset_name(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"cn-{uuid.uuid4().hex[:6]}", name="数据资产", description="中文描述", status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertEqual(asset.name, "数据资产")
        self.assertEqual(asset.description, "中文描述")

    def test_arabic_characters_in_asset_name(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"ar-{uuid.uuid4().hex[:6]}", name="بيانات", description="وصف", status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertEqual(asset.name, "بيانات")

    def test_emoji_in_asset_name(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"em-{uuid.uuid4().hex[:6]}", name="🚀 Rocket Asset", description="Launch 🎉", status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertEqual(asset.name, "🚀 Rocket Asset")
        self.assertIn("🎉", asset.description)

    def test_special_chars_in_asset_name(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"sp-{uuid.uuid4().hex[:6]}", name="O'Brien & Co. (100%)", description='Quote "test"', status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertEqual(asset.name, "O'Brien & Co. (100%)")

    def test_accented_chars_in_asset_name(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"ac-{uuid.uuid4().hex[:6]}", name="café résumé naïve", description="Ñoño über", status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertEqual(asset.name, "café résumé naïve")

    def test_mixed_unicode_in_description(self):
        asset = Asset.objects.create(tenant=self.tenant, key=f"mx-{uuid.uuid4().hex[:6]}", name="Mixed", description="日本語 العربية 한국어 Ελληνικά", status=AssetStatus.DRAFT)
        asset.refresh_from_db()
        self.assertIn("日本語", asset.description)
        self.assertIn("العربية", asset.description)
        self.assertIn("한국어", asset.description)
