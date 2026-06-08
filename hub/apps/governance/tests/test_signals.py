"""
Phase 80.3 — Governance signal tests.

Tests ABAC policy cache invalidation on AccessPolicy and FieldAccessPolicy
save/delete operations. Uses real cache state verification (no mocks).
"""
import uuid

import pytest
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class GovernanceSignalTest(TestCase):
    """Tests for governance ABAC policy cache invalidation signals."""

    def setUp(self):
        """Clear cache before each test for clean state."""
        cache.clear()

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
        """Create a dataset via the ORM using the minimal required fields."""
        from hub.apps.datasets.models import Dataset

        asset = self._create_asset(tenant)
        return Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            format="CSV",
            version=1,
        )

    def _get_version_key(self, tenant_id):
        return f"abac_cache_version_{tenant_id}"

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

    def test_policy_save_invalidates_tenant_cache(self):
        """Saving an AccessPolicy invalidates tenant cache (real cache verification)."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()

        # Set baseline cache version
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 5)

        # Create policy → post_save signal → invalidate_policy_cache(tenant_id)
        # → increments version from 5 to 6
        AccessPolicy.objects.create(
            tenant=tenant, name="test-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )

        # Verify version was incremented
        new_version = cache.get(version_key)
        assert new_version == 6, (
            f"Expected cache version 6 after policy save, got {new_version}"
        )

    def test_policy_delete_invalidates_tenant_cache(self):
        """Deleting an AccessPolicy invalidates tenant cache (real cache verification)."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="del-policy",
            conditions={"role": "admin"}, effect="DENY",
        )

        # Set baseline cache version AFTER creation (which itself increments version)
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 10)

        # Delete policy → post_delete signal → invalidate_policy_cache(tenant_id)
        policy.delete()

        # Verify version was incremented
        new_version = cache.get(version_key)
        assert new_version == 11, (
            f"Expected cache version 11 after policy delete, got {new_version}"
        )

    def test_asset_scoped_policy_invalidates_scoped_cache(self):
        """AccessPolicy with asset invalidates asset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy
        from hub.apps.governance.abac import ABACEngine

        tenant = self._create_tenant()
        asset = self._create_asset(tenant)

        # Set baseline version
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 5)

        # Create asset-scoped policy → signal fires: version increment + scoped delete
        AccessPolicy.objects.create(
            tenant=tenant, name="asset-policy",
            conditions={"role": "viewer"}, effect="ALLOW",
            asset=asset,
        )

        # Version was incremented by invalidate_policy_cache(tenant_id)
        assert cache.get(version_key) == 6, (
            f"Version should increment to 6, got {cache.get(version_key)}"
        )

    def test_dataset_scoped_policy_invalidates_scoped_cache(self):
        """AccessPolicy with dataset invalidates dataset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy

        tenant = self._create_tenant()
        dataset = self._create_dataset(tenant)

        # Set baseline version
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 5)

        # Create dataset-scoped policy
        AccessPolicy.objects.create(
            tenant=tenant, name="ds-policy",
            conditions={"role": "analyst"}, effect="ALLOW",
            dataset=dataset,
        )

        # Version was incremented by invalidate_policy_cache(tenant_id)
        assert cache.get(version_key) == 6, (
            f"Version should increment to 6, got {cache.get(version_key)}"
        )

    def test_field_policy_save_invalidates_dataset_cache(self):
        """FieldAccessPolicy save invalidates dataset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
        from hub.apps.governance.abac import ABACEngine

        tenant = self._create_tenant()
        dataset = self._create_dataset(tenant)
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="parent-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )

        # Set a known version and populate the scoped cache key
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 10)
        scoped_key = ABACEngine._get_cache_key(
            str(tenant.id), "DATASET", str(dataset.id)
        )
        cache.set(scoped_key, ["cached-policy-id"])
        # Verify key was set
        assert cache.get(scoped_key) == ["cached-policy-id"], "Key should be populated before save"

        # Create field policy → signal fires:
        # invalidate_field_policy_cache calls invalidate_policy_cache(tenant_id, "DATASET", dataset_id)
        # which deletes the specific cache key
        FieldAccessPolicy.objects.create(
            tenant=tenant, access_policy=policy,
            dataset=dataset, field_name="ssn",
            access_type="DENY",
        )

        # The specific key should be deleted
        assert cache.get(scoped_key) is None, (
            f"Scoped cache key should be deleted after FieldAccessPolicy save, "
            f"but got: {cache.get(scoped_key)}"
        )

    def test_field_policy_delete_invalidates_dataset_cache(self):
        """FieldAccessPolicy delete invalidates dataset-scoped cache."""
        from hub.apps.governance.models import AccessPolicy, FieldAccessPolicy
        from hub.apps.governance.abac import ABACEngine

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

        # Set a known version and populate the scoped cache key
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 15)
        scoped_key = ABACEngine._get_cache_key(
            str(tenant.id), "DATASET", str(dataset.id)
        )
        cache.set(scoped_key, ["cached-id"])
        # Verify key was set
        assert cache.get(scoped_key) == ["cached-id"], "Key should be populated before delete"

        # Delete field policy → signal fires → specific key deleted
        fp.delete()

        # The specific key should be deleted
        assert cache.get(scoped_key) is None, (
            f"Scoped cache key should be deleted after FieldAccessPolicy delete, "
            f"but got: {cache.get(scoped_key)}"
        )

    def test_policy_update_invalidates_cache(self):
        """Updating an existing policy also triggers invalidation."""
        from hub.apps.governance.models import AccessPolicy
        tenant = self._create_tenant()
        policy = AccessPolicy.objects.create(
            tenant=tenant, name="upd-policy",
            conditions={"role": "admin"}, effect="ALLOW",
        )

        # Set baseline version AFTER creation
        version_key = self._get_version_key(tenant.id)
        cache.set(version_key, 20)

        # Update policy → post_save signal → invalidate_policy_cache
        policy.effect = "DENY"
        policy.save(update_fields=["effect"])

        # Version should be incremented
        new_version = cache.get(version_key)
        assert new_version == 21, (
            f"Expected cache version 21 after policy update, got {new_version}"
        )
