"""Constraint-based asset creation tests (replaces threading-based concurrency)."""

import uuid

from django.db import IntegrityError, transaction
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant


class AssetCreationConstraintTest(TestCase):
    """DB unique constraint prevents duplicate asset keys per tenant."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T {uid}", slug=f"t-{uid}")
        self.tenant2 = Tenant.objects.create(name=f"T2 {uid}", slug=f"t2-{uid}")
        self.key = f"asset-key-{uid}"

    def test_duplicate_key_same_tenant_raises_integrity_error(self):
        Asset.objects.create(
            tenant=self.tenant, key=self.key, name="First", status=AssetStatus.DRAFT
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asset.objects.create(
                tenant=self.tenant, key=self.key, name="Dup", status=AssetStatus.DRAFT
            )

    def test_different_keys_same_tenant_both_succeed(self):
        Asset.objects.create(
            tenant=self.tenant, key=f"{self.key}-a", name="A", status=AssetStatus.DRAFT
        )
        Asset.objects.create(
            tenant=self.tenant, key=f"{self.key}-b", name="B", status=AssetStatus.DRAFT
        )
        self.assertEqual(
            Asset.objects.filter(tenant=self.tenant, key__startswith=self.key).count(), 2
        )

    def test_same_key_different_tenant_both_succeed(self):
        Asset.objects.create(tenant=self.tenant, key=self.key, name="T1", status=AssetStatus.DRAFT)
        Asset.objects.create(tenant=self.tenant2, key=self.key, name="T2", status=AssetStatus.DRAFT)
        self.assertEqual(Asset.objects.filter(key=self.key).count(), 2)
