"""
Phase 260.1.B — orphan file soft-delete when eligible Dataset rows disappear.

Uses real ORM + ``captureOnCommitCallbacks(execute=True)`` (no mocked signals).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import transaction

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.files.models import FileStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


def _ds_kwargs(*, tenant, user, **extra):
    base = {
        "tenant": tenant,
        "format": "CSV",
        "row_count": 1,
        "schema_json": {"fields": [{"name": "id", "type": "string"}]},
        "created_by": user,
    }
    base.update(extra)
    return base


class DatasetOrphanFileCascadeTests(DatasetsTestBase):
    """260.1.B.4 / B.5 — retire + dataset removal + debounced orphan handling."""

    def setUp(self):
        super().setUp()
        ensure_tenant_has_active_subscription(self.tenant)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="Cascade asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_retired_asset_then_delete_last_dataset_soft_deletes_file(self):
        ds = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=self.asset,
                file=self.file,
            )
        )
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)

        with self.captureOnCommitCallbacks(execute=True):
            ds.delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.DELETED)
        self.assertIsNotNone(self.file.deleted_at)
        rows = AuditEvent.objects.filter(
            resource_type="FILE",
            action=audit_event_types.FILE_ORPHAN_DETECTED,
            resource_id=str(self.file.id),
        )
        self.assertEqual(rows.count(), 1)
        event = rows.get()
        codes = event.details_json.get("reason_codes", [])
        self.assertIn(
            "dataset_parent_asset_retired",
            codes,
        )

    @pytest.mark.integration
    def test_dataset_without_asset_deletes_file_when_last_ref_gone(self):
        ds = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=None,
                file=self.file,
            )
        )

        with self.captureOnCommitCallbacks(execute=True):
            ds.delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.DELETED)

    @pytest.mark.integration
    def test_active_parent_asset_blocks_orphan_soft_delete(self):
        self.assertNotEqual(self.asset.status, AssetStatus.RETIRED)

        ds = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=self.asset,
                file=self.file,
            )
        )

        with self.captureOnCommitCallbacks(execute=True):
            ds.delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.ACTIVE)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.FILE_ORPHAN_DETECTED,
                resource_id=str(self.file.id),
            ).exists(),
        )

    @pytest.mark.integration
    def test_bulk_dataset_delete_emits_single_orphan_audit(self):
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)

        # Each Dataset row needs a distinct ``version`` per
        # ``unique_dataset_version_per_asset`` (Phase 260.5.A
        # constraint on ``(tenant, asset, version)`` for
        # ``asset__isnull=False``). The orphan-debounce contract this
        # test exercises doesn't depend on the version values; just
        # space them out so all three rows can land.
        ds_ids = []
        for ver in (1, 2, 3):
            d = Dataset.objects.create(
                **_ds_kwargs(
                    tenant=self.tenant,
                    user=self.user,
                    asset=self.asset,
                    file=self.file,
                    version=ver,
                )
            )
            ds_ids.append(d.id)

        # Only count events for THIS file so pre-existing
        # FILE_ORPHAN_DETECTED rows from other tests don't
        # pollute the before/after delta.
        before = AuditEvent.objects.filter(
            action=audit_event_types.FILE_ORPHAN_DETECTED,
            resource_id=str(self.file.id),
        ).count()

        with self.captureOnCommitCallbacks(execute=True):
            Dataset.objects.filter(pk__in=ds_ids).delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.DELETED)
        after = AuditEvent.objects.filter(
            action=audit_event_types.FILE_ORPHAN_DETECTED,
            resource_id=str(self.file.id),
        ).count()
        self.assertEqual(after - before, 1)

    @pytest.mark.integration
    def test_full_transaction_rollback_then_eligible_delete_still_soft_deletes_file(self):
        """Rolled-back deletes must not strand votes or block a later real delete."""
        ds = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=self.asset,
                file=self.file,
            )
        )
        # ``Model.delete()`` clears ``instance.pk`` IN PLACE before
        # the SQL runs (so a subsequent ``.save()`` would re-INSERT).
        # The outer ``atomic()`` rollback restores the DB row but
        # NOT the in-memory ``ds.pk``. Capture the id up front so the
        # post-rollback existence check has a stable lookup key, then
        # re-load the instance for the second-attempt delete.
        ds_id = ds.pk
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)

        try:
            with transaction.atomic():
                ds.delete()
                raise RuntimeError("force outer rollback")
        except RuntimeError:
            pass

        self.assertTrue(Dataset.objects.filter(pk=ds_id).exists())
        ds = Dataset.objects.get(pk=ds_id)

        with self.captureOnCommitCallbacks(execute=True), transaction.atomic():
            ds.delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.DELETED)

    @pytest.mark.integration
    def test_inner_savepoint_rollback_drops_orphan_vote(self):
        """Votes from savepoint-rolled-back deletes must not merge with later work."""
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)
        ds = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=self.asset,
                file=self.file,
            )
        )
        # ``Model.delete()`` zeroes ``instance.pk`` even when the
        # surrounding savepoint rolls back; re-fetch by the captured
        # id so the second delete operates on a hydrated instance.
        ds_id = ds.pk

        with transaction.atomic():
            try:
                with transaction.atomic():
                    ds.delete()
                    raise ValueError("abort inner savepoint")
            except ValueError:
                pass
            self.assertTrue(Dataset.objects.filter(pk=ds_id).exists())

        ds = Dataset.objects.get(pk=ds_id)
        with self.captureOnCommitCallbacks(execute=True), transaction.atomic():
            ds.delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.DELETED)

    @pytest.mark.integration
    def test_mixed_eligibility_in_bulk_fails_closed(self):
        """One non-retired snapshot in the burst vetoes the aggregated vote."""
        Asset.objects.filter(pk=self.asset.pk).update(status=AssetStatus.RETIRED)
        other = Asset.objects.create(
            tenant=self.tenant,
            key=f"other-{uuid.uuid4().hex[:6]}",
            name="Other asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        ds_ret = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=self.asset,
                file=self.file,
            )
        )
        ds_live = Dataset.objects.create(
            **_ds_kwargs(
                tenant=self.tenant,
                user=self.user,
                asset=other,
                file=self.file,
            )
        )

        with self.captureOnCommitCallbacks(execute=True):
            Dataset.objects.filter(pk__in=[ds_ret.id, ds_live.id]).delete()

        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.ACTIVE)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.FILE_ORPHAN_DETECTED,
                resource_id=str(self.file.id),
            ).exists(),
        )
