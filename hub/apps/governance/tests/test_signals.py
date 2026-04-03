"""
Phase 80.3 — Governance signal tests.

Tests ABAC policy cache invalidation on AccessPolicy and FieldAccessPolicy
save/delete operations.
"""
import uuid
from unittest.mock import patch

import pytest
from django.db.models.signals import post_save, post_delete
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class GovernanceSignalTest(TestCase):
    """Tests for governance ABAC policy cache invalidation signals."""

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        tenant, _ = Tenant.objects.get_or_create(
            name="gov-sig-test", defaults={"slug": "gov-sig-test"},
        )
        return tenant

    def _create_asset(self, tenant):
        from hub.apps.assets.models import Asset
        return Asset.objects.create(
            tenant=tenant,
            name=f"gov-asset-{uuid.uuid4().hex[:6]}",
        )

    def _create_dataset(self, tenant):
        """Create a dataset via raw SQL to avoid model field mismatches."""
        from django.db import connection

        ds_id = uuid.uuid4()
        asset = self._create_asset(tenant)
        with connection.cursor() as c:
            c.execute(
                """INSERT INTO datasets
                   (id, tenant_id, asset_id, format, version,
                    is_current, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())""",
                [str(ds_id), str(tenant.id), str(asset.id),
                 "CSV", "1", True],
            )
        from hub.apps.datasets.models import Dataset
        return Dataset.objects.get(pk=ds_id)

    def test_signal_connected_to_post_save_and_post_delete(self):
        """All 3 signal handlers are connected."""
        from hub.apps.governance.signals import (
            invalidate_policy_cache_on_delete,
            invalidate_field_policy_cache,
            invalidate_policy_cache_on_save,
        )

        def _receiver_functions(signal):
            # Django 6+: each entry is
            # (lookup_key, receiver_ref, sender_ref, is_async); receiver at [1].
            out = set()
            for receiver_tuple in signal.receivers:
                if len(receiver_tuple) < 2:
                    continue
                ref = receiver_tuple[1]
                # weakref.ref or weakref.WeakMethod (not ReferenceType subclass)
                if hasattr(ref, "__call__"):
                    try:
                        obj = ref()
                    except TypeError:
                        obj = None
                    if obj is not None:
                        out.add(obj)
                elif callable(ref):
                    out.add(ref)
            return out

        save_receivers = _receiver_functions(post_save)
        delete_receivers = _receiver_functions(post_delete)
        assert invalidate_policy_cache_on_save in save_receivers
        assert invalidate_policy_cache_on_delete in delete_receivers
        assert invalidate_field_policy_cache in save_receivers
        assert invalidate_field_policy_cache in delete_receivers

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_policy_save_invalidates_tenant_cache(self, mock_inv):
        """Saving an AccessPolicy invalidates tenant cache."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        AccessPolicy.objects.create(
            tenant=tenant, name="test-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )
        mock_inv.assert_any_call(str(tenant.id))

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_policy_delete_invalidates_tenant_cache(self, mock_inv):
        """Deleting an AccessPolicy invalidates tenant cache."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="del-policy",
            conditions={"role": "admin"}, effect="DENY",
        )
        mock_inv.reset_mock()
        policy.delete()
        mock_inv.assert_any_call(str(tenant.id))

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_asset_scoped_policy_invalidates_scoped_cache(self, mock_inv):
        """AccessPolicy with asset invalidates asset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        asset = self._create_asset(tenant)
        AccessPolicy.objects.create(
            tenant=tenant, name="asset-policy",
            conditions={"role": "viewer"}, effect="ALLOW",
            asset=asset,
        )
        mock_inv.assert_any_call(
            str(tenant.id), "ASSET", str(asset.id),
        )

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_dataset_scoped_policy_invalidates_scoped_cache(self, mock_inv):
        """AccessPolicy with dataset invalidates dataset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        dataset = self._create_dataset(tenant)
        AccessPolicy.objects.create(
            tenant=tenant, name="ds-policy",
            conditions={"role": "analyst"}, effect="ALLOW",
            dataset=dataset,
        )
        mock_inv.assert_any_call(
            str(tenant.id), "DATASET", str(dataset.id),
        )

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_field_policy_save_invalidates_dataset_cache(self, mock_inv):
        """FieldAccessPolicy save invalidates dataset-scoped cache."""
        from hub.apps.governance.models import (
            AccessPolicy, FieldAccessPolicy,
        )
        tenant = self._create_tenant()
        dataset = self._create_dataset(tenant)
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="parent-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )
        mock_inv.reset_mock()
        FieldAccessPolicy.objects.create(
            tenant=tenant, access_policy=policy,
            dataset=dataset, field_name="ssn",
            access_type="DENY",
        )
        mock_inv.assert_any_call(
            str(tenant.id), "DATASET", str(dataset.id),
        )

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_field_policy_delete_invalidates_dataset_cache(self, mock_inv):
        """FieldAccessPolicy delete invalidates dataset-scoped cache."""
        from hub.apps.governance.models import (
            AccessPolicy, FieldAccessPolicy,
        )
        tenant = self._create_tenant()
        dataset = self._create_dataset(tenant)
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="parent-del",
            conditions={"role": "admin"}, effect="ALLOW",
        )
        fp = FieldAccessPolicy.objects.create(
            tenant=tenant, access_policy=policy,
            dataset=dataset, field_name="email",
            access_type="MASK",
        )
        mock_inv.reset_mock()
        fp.delete()
        mock_inv.assert_any_call(
            str(tenant.id), "DATASET", str(dataset.id),
        )

    @patch("hub.apps.governance.signals.ABACEngine.invalidate_policy_cache")
    def test_policy_update_invalidates_cache(self, mock_inv):
        """Updating an existing policy also triggers invalidation."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="upd-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )
        mock_inv.reset_mock()
        policy.effect = "DENY"
        policy.save(update_fields=["effect"])
        mock_inv.assert_any_call(str(tenant.id))
