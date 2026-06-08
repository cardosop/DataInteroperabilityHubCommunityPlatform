"""
260.1.C — Backfill ACTIVE + NULL file_id → RETIRED (migration 0103 logic).

Uses bulk ORM update (no mocks): legacy inconsistency via ``.update()``,
which bypasses ``save()`` and File ``pre_delete``.
"""
from __future__ import annotations
import pytest


from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.retirement import backfill_orphan_active_datasets_qs
from hub.apps.datasets.tests.test_base import DatasetsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class OrphanDatasetBackfillTests(DatasetsTestBase):
    @pytest.mark.integration
    def test_backfill_retires_active_rows_with_null_file(self):
        ds = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={},
            sample_data_json=[],
            row_count=0,
            created_by=self.user,
        )
        Dataset.objects.filter(pk=ds.pk).update(file_id=None)
        ds.refresh_from_db()
        self.assertIsNone(ds.file)
        self.assertEqual(ds.status, DatasetStatus.ACTIVE)

        qs = Dataset.objects.filter(tenant=self.tenant)
        updated = backfill_orphan_active_datasets_qs(qs)
        self.assertEqual(updated, 1)
        ds.refresh_from_db()
        self.assertEqual(ds.status, DatasetStatus.RETIRED)
        self.assertIsNotNone(ds.retired_at)

    @pytest.mark.integration
    def test_backfill_leaves_active_rows_with_file_untouched(self):
        ds = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={},
            sample_data_json=[],
            row_count=0,
            created_by=self.user,
        )
        qs = Dataset.objects.filter(tenant=self.tenant)
        updated = backfill_orphan_active_datasets_qs(qs)
        self.assertEqual(updated, 0)
        ds.refresh_from_db()
        self.assertEqual(ds.status, DatasetStatus.ACTIVE)
        self.assertEqual(ds.file, self.file)
