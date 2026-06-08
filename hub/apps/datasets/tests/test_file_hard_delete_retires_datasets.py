"""
Phase 260.1.C — File hard-delete retires linked Dataset rows (pre_delete signal).

No mocks: real File.delete() under tenant RLS context.
"""
from __future__ import annotations
import pytest

from django.utils import timezone

from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.tenants.request_tenant import tenant_context

pytestmark = pytest.mark.django_db(transaction=True)


class FileHardDeleteRetiresDatasetsTests(DatasetsTestBase):
    """260.1.C.3 — pre_delete on File marks datasets RETIRED before SET_NULL."""

    @pytest.mark.integration
    def test_hard_delete_file_retires_active_datasets(self):
        ds = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={},
            sample_data_json=[{"a": 1}],
            row_count=1,
            created_by=self.user,
        )
        self.assertEqual(ds.status, DatasetStatus.ACTIVE)
        with tenant_context(str(self.tenant.id)):
            self.file.delete()
        ds.refresh_from_db()
        self.assertIsNone(ds.file)
        self.assertEqual(ds.status, DatasetStatus.RETIRED)
        self.assertIsNotNone(ds.retired_at)

    @pytest.mark.integration
    def test_hard_delete_file_skips_already_retired_datasets(self):
        ds = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            status=DatasetStatus.RETIRED,
            retired_at=timezone.now(),
            schema_json={},
            sample_data_json=[],
            row_count=0,
            created_by=self.user,
        )
        prior_retired = ds.retired_at
        with tenant_context(str(self.tenant.id)):
            self.file.delete()
        ds.refresh_from_db()
        self.assertIsNone(ds.file)
        self.assertEqual(ds.status, DatasetStatus.RETIRED)
        self.assertEqual(ds.retired_at, prior_retired)