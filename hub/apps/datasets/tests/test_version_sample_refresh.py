"""
Phase 260.5.I — Sample-data refresh on new dataset version
(closes pass-3 B3-10).

The pre-260.5.I bug: ``DatasetService.create_version_from_dataset``
and ``VersioningService.create_version`` both blindly copied
``parent.sample_data_json`` onto the new Dataset row. If the
parent's cached ``sample_data_json`` was stale or corrupt
(manual DB write, migration bug, partial restore), the corruption
propagated forward forever — every subsequent version inherited
the broken cache.

The fix: ``extract_sample_data_from_storage`` re-derives
``sample_data_json`` from the file's canonical bytes on every
version creation. The two version-creation paths share the
helper, so the cache-copy → fresh-extraction migration is
uniform across the codebase.

These tests use REAL MinIO + ``DatasetService.create_dataset``
to seed v1 with bytes-derived sample_data, then deliberately
CORRUPT v1's ``sample_data_json`` field (simulate stale cache /
manual DB mutation), then create v2 via
``create_version_from_dataset`` and assert v2's
``sample_data_json`` reflects the FILE's truth — NOT the
corrupted parent field. Skip when MinIO is unavailable.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.services import (
    DatasetService,
    extract_sample_data_from_storage,
)
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


_V1_CSV_BODY = b"id,name,age\n1,alice,30\n2,bob,25\n3,charlie,40\n"


class _VersionSampleRefreshTestMixin:
    """Real MinIO + tenant + asset setUp; mirrors the pattern from
    test_dataset_encoding_gate / test_multipart_complete_race.
    """

    def setUp(self):
        super().setUp()
        from hub.apps.files.storage import S3StorageClient

        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"VS {uid}",
            slug=f"vs-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"vs-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = DatasetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"vs-asset-{uid}",
            name="VS Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _seed_active_file(self, *, body: bytes = _V1_CSV_BODY) -> File:
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/data.csv"
        self.storage_client.upload_file(storage_path, body, "text/csv")
        return File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )

    def _create_v1_dataset(self) -> Dataset:
        f = self._seed_active_file()
        v1 = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
            asset_id=str(self.asset.id),
        )
        return v1


class VersionSampleRefreshHelperTest(
    _VersionSampleRefreshTestMixin, TransactionTestCase
):
    """The pure helper ``extract_sample_data_from_storage`` is the
    load-bearing primitive. Pin its contract on its own (no
    version-creation indirection)."""

    @pytest.mark.integration
    def test_helper_returns_bytes_derived_sample_data(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        f = self._seed_active_file()
        sample = extract_sample_data_from_storage(f, "CSV")
        # Derived from _V1_CSV_BODY: 3 rows, fields id/name/age.
        self.assertIsNotNone(sample)
        self.assertEqual(len(sample), 3)
        self.assertEqual(sample[0]["id"], "1")
        self.assertEqual(sample[0]["name"], "alice")

    @pytest.mark.integration
    def test_helper_returns_none_on_unreadable_file(self):
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        # Create a File row pointing at a storage_path that
        # doesn't exist — extraction should fail gracefully.
        file_id = uuid.uuid4()
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="missing.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/missing.csv",
            created_by=self.user,
        )
        # Best-effort: returns None on failure rather than raising
        # so version creation isn't blocked by sample-extraction
        # issues.
        result = extract_sample_data_from_storage(f, "CSV")
        self.assertIsNone(result)

    @pytest.mark.integration
    def test_helper_handles_none_inputs(self):
        # Defensive — these never happen in practice but the
        # helper must not crash on bad inputs (callers shouldn't
        # have to type-check before invoking).
        self.assertIsNone(extract_sample_data_from_storage(None, "CSV"))
        self.assertIsNone(extract_sample_data_from_storage(object(), ""))


class VersionSampleRefreshIntegrationTest(
    _VersionSampleRefreshTestMixin, TransactionTestCase
):
    """260.5.I.2 acceptance — create v1 + v2; assert v2's
    sample_data_json is derived from the file, NOT from a stale /
    corrupted parent cache.
    """

    @pytest.mark.integration
    def test_v2_sample_data_reflects_file_not_corrupted_parent_cache(self):
        # 1. Create v1 — sample_data populated by extract_sample_data
        #    inside create_dataset.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        v1 = self._create_v1_dataset()
        v1_original_sample = v1.sample_data_json or []
        self.assertGreater(
            len(v1_original_sample),
            0,
            "Sanity: v1 sample_data must be populated from create_dataset",
        )

        # 2. CORRUPT v1's sample_data_json directly (simulates a
        #    stale cache / migration bug / manual DB mutation).
        #    The file's bytes are unchanged — the corruption is
        #    in the denormalised cache only.
        v1.sample_data_json = [{"corrupted": True, "this_should_NOT_propagate": True}]
        v1.save(update_fields=["sample_data_json"])

        # 3. Create v2 from v1. Pre-260.5.I, this would have
        #    copied v1.sample_data_json (the corruption) onto v2.
        v2 = self.service.create_version_from_dataset(
            source_dataset_id=str(v1.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # 4. v2's sample_data_json MUST reflect fresh extraction
        #    from the file's canonical bytes — NOT the corrupted
        #    parent cache.
        self.assertIsNotNone(v2.sample_data_json)
        self.assertNotEqual(
            v2.sample_data_json,
            [{"corrupted": True, "this_should_NOT_propagate": True}],
            f"v2 inherited corrupted parent cache instead of fresh "
            f"file extraction; got v2.sample_data_json="
            f"{v2.sample_data_json!r}",
        )
        # Specifically: v2 should match what extract_sample_data
        # produces from the file's bytes.
        expected = extract_sample_data_from_storage(v1.file, v1.format)
        self.assertEqual(
            v2.sample_data_json,
            expected,
            f"v2.sample_data_json must equal fresh file extraction; "
            f"got v2={v2.sample_data_json!r}, expected={expected!r}",
        )
        # And the rows must match the original file content.
        self.assertEqual(len(v2.sample_data_json), 3)
        self.assertEqual(v2.sample_data_json[0]["name"], "alice")

    @pytest.mark.integration
    def test_v2_falls_back_to_parent_cache_when_file_is_unreadable(self):
        # Best-effort fallback: if the file is unreachable, v2
        # uses the parent's stored value rather than failing
        # version creation. The platform shouldn't refuse to
        # create a version because of a transient storage
        # outage — the dataset row is still meaningful, the
        # sample is just frozen at the last known value.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        v1 = self._create_v1_dataset()
        original_sample = list(v1.sample_data_json or [])

        # Break the file's storage path so re-extraction fails.
        v1.file.storage_path = f"{self.tenant.id}/missing/nope.csv"
        v1.file.save(update_fields=["storage_path"])

        v2 = self.service.create_version_from_dataset(
            source_dataset_id=str(v1.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Fallback to parent's cached value rather than empty /
        # crash. The parent's cache is the next-best answer when
        # the canonical truth (file bytes) is unreachable.
        self.assertEqual(
            v2.sample_data_json,
            original_sample,
            "Fallback path must use parent's sample_data_json when "
            "the file is unreachable",
        )

    @pytest.mark.integration
    def test_v2_sample_data_for_json_format_is_freshly_extracted(self):
        # Phase 260.5.I.R1 GAP-A — the helper is generic over
        # ``file_format``; this test pins JSON coverage so a
        # future regression in ``extract_sample_data``'s JSON
        # branch surfaces here. CSV-only coverage would have left
        # the JSON path silent.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        ndjson = (
            b'{"id": 1, "name": "alice"}\n'
            b'{"id": 2, "name": "bob"}\n'
            b'{"id": 3, "name": "charlie"}\n'
        )
        file_id = uuid.uuid4()
        storage_path = f"{self.tenant.id}/{file_id}/data.ndjson"
        self.storage_client.upload_file(storage_path, ndjson, "application/json")
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.ndjson",
            content_type="application/json",
            size=len(ndjson),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            created_by=self.user,
        )
        v1 = self.service.create_dataset(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            file_id=str(f.id),
            asset_id=str(self.asset.id),
        )
        self.assertEqual(
            v1.format,
            "JSON",
            f"Sanity: v1 format must be JSON; got {v1.format!r}",
        )

        # Corrupt v1's sample to detect leakage.
        v1.sample_data_json = [{"corrupted": True}]
        v1.save(update_fields=["sample_data_json"])

        v2 = self.service.create_version_from_dataset(
            source_dataset_id=str(v1.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # v2 must reflect fresh JSON extraction, NOT the
        # corrupted parent cache.
        self.assertNotEqual(v2.sample_data_json, [{"corrupted": True}])
        self.assertEqual(len(v2.sample_data_json), 3)
        self.assertEqual(v2.sample_data_json[0]["name"], "alice")

    @pytest.mark.integration
    def test_v2_with_schema_override_still_re_extracts_sample(self):
        # When the user provides a ``schema_json`` override, the
        # legacy bug surfaces sharply: schema reflects new
        # structure, sample reflects parent's old structure.
        # 260.5.I forces re-extraction so they stay coherent.
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")
        v1 = self._create_v1_dataset()
        # Corrupt v1's sample_data to detect leakage.
        v1.sample_data_json = [{"OLD_SCHEMA": True}]
        v1.save(update_fields=["sample_data_json"])

        # Schema override that adds an opinion (compatible — just
        # adds a note; doesn't actually drop / rename fields).
        new_schema = {
            "fields": [
                {"name": "id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": False},
                {"name": "age", "data_type": "integer", "nullable": True},
            ],
            "row_count_estimated": 3,
        }
        v2 = self.service.create_version_from_dataset(
            source_dataset_id=str(v1.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            schema_json=new_schema,
        )

        # Schema came from the override.
        self.assertEqual(v2.schema_json, new_schema)
        # Sample came from FRESH file extraction — NOT the
        # corrupted parent cache.
        self.assertNotEqual(
            v2.sample_data_json,
            [{"OLD_SCHEMA": True}],
            "Sample data must be fresh extraction even when schema "
            "is overridden",
        )
        self.assertEqual(len(v2.sample_data_json), 3)
        self.assertEqual(v2.sample_data_json[0]["name"], "alice")
