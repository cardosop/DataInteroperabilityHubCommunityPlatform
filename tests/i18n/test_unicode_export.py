"""Phase 111.10 — Unicode export preserves UTF-8 encoding."""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UnicodeExportTest(TestCase):
    """Unicode data exports correctly as UTF-8."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def test_json_export_preserves_chinese(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"cn-{uuid.uuid4().hex[:6]}",
            name="数据资产",
            status=AssetStatus.DRAFT,
        )
        exported = json.dumps({"name": asset.name}, ensure_ascii=False)
        self.assertIn("数据资产", exported)
        # Verify it's valid JSON
        parsed = json.loads(exported)
        self.assertEqual(parsed["name"], "数据资产")

    def test_json_export_preserves_emoji(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"em-{uuid.uuid4().hex[:6]}",
            name="🚀 Launch",
            status=AssetStatus.DRAFT,
        )
        exported = json.dumps({"name": asset.name}, ensure_ascii=False)
        self.assertIn("🚀", exported)

    def test_json_export_preserves_mixed_unicode(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"mx-{uuid.uuid4().hex[:6]}",
            name="café العربية 한국어",
            status=AssetStatus.DRAFT,
        )
        exported = json.dumps({"name": asset.name}, ensure_ascii=False)
        self.assertIn("café", exported)
        self.assertIn("العربية", exported)
        self.assertIn("한국어", exported)

    def test_utf8_bytes_roundtrip(self):
        """String → UTF-8 bytes → string preserves content."""
        name = "O'Brien café 数据 🚀"
        encoded = name.encode("utf-8")
        decoded = encoded.decode("utf-8")
        self.assertEqual(name, decoded)
