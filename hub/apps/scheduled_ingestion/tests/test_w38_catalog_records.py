"""W3.8 (oss-release-remediation R2-P7/D6) — the shared catalog-record
creation core.

ONE implementation of the File+Dataset creation used by BOTH the legacy
per-file worker path (``worker_services.process_file_for_run``) and the
dlt spine (``hub.data_movement.ingestion_execution``) — the D6
parity-first fix.  The worker's creation block (File + hub-storage
upload + ClamAV gate + asset resolution + Dataset + version history +
schema-compat check + search index) is extracted verbatim into
``hub/apps/scheduled_ingestion/catalog_records.py`` so the two
entrypoints can never diverge again (the sibling-copy failure class).

Pins (real DB + real schema inference + the sanctioned S3 storage
boundary stand-in + ClamAV disabled — the worker-parity suite's
conventions):

* the core creates File (ACTIVE, sha256, storage_path, provenance
  markers) + Dataset (format, version, linkage) + version history;
* re-delivery is IDEMPOTENT by source key (the crash-window contract
  the dlt spine relies on);
* the guard matrix: empty content, unsupported extension, schema
  incompatibility, and active-name collision are classified loudly;
* per-asset versioning increments with parent linkage.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)

_STORAGE_SAVE = "hub.apps.files.storage.S3StorageClient.save_file"

_CSV_ROWS = b"id,name\n1,alpha\n2,beta\n"
_CSV_ROWS_NARROW = b"id\n1\n2\n"


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"w38core-{uid}",
        slug=f"w38core-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_ingestion(tenant, *, auto_create_asset=False, auto_activate=False, asset=None):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"w38core-ing-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
        schedule_type="DAILY",
        schedule_config={"time": "02:00"},
        file_pattern=".*",
        auto_create_asset=auto_create_asset,
        auto_activate=auto_activate,
        asset=asset,
        created_by=None,
    )


def _create(scheduled_ingestion, file_path, file_content, **kwargs):
    from hub.apps.scheduled_ingestion.catalog_records import (
        create_file_and_dataset_records,
    )

    return create_file_and_dataset_records(scheduled_ingestion, file_path, file_content, **kwargs)


class TestCreateFileAndDatasetRecords:
    """The extracted core creates the full catalog record set."""

    @pytest.fixture(autouse=True)
    def _clamav_disabled(self, settings):
        settings.CLAMAV_ENABLED = False

    @pytest.fixture(autouse=True)
    def storage_stand_in(self):
        # Keyword-tolerant: the core calls save_file(tenant_id=...,
        # file_id=..., file_content=...) — all keyword arguments.
        with patch(_STORAGE_SAVE) as save:
            save.side_effect = (
                lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: (
                    f"{tenant_id}/{file_id}/content"
                )
            )
            yield save

    def test_creates_file_dataset_and_version_history(self):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, auto_create_asset=True)

        result = _create(ingestion, "staging/a.csv", _CSV_ROWS)

        assert result.created is True
        assert result.file.status == FileStatus.ACTIVE
        assert result.file.storage_path
        assert result.file.content_sha256
        assert result.file.size == len(_CSV_ROWS)
        assert result.file.metadata_json == {
            "scheduled_ingestion_id": str(ingestion.id),
            "source_key": "staging/a.csv",
        }
        assert result.dataset.format == "CSV"
        assert result.dataset.file_id == result.file.id
        assert result.dataset.asset_id == result.asset.id
        assert result.dataset.version == 1
        assert result.asset is not None
        assert Dataset.objects.filter(tenant=tenant).count() == 1
        assert File.objects.filter(tenant=tenant).count() == 1

    def test_pe_disguised_as_csv_is_rejected_by_the_magic_gate(self):
        """W10.3 (round-3 re-audit): the worker/dlt catalog path runs
        the SAME magic-byte gate as the browser upload path — a PE
        payload named .csv must be classified FILE_FORMAT_MISMATCH and
        never create a File row (the pre-fix path catalogued it ACTIVE)."""
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, auto_create_asset=True)
        pe_payload = b"MZ\x90\x00" + b"\x00" * 64

        with pytest.raises(ServiceValidationError) as ei:
            _create(ingestion, "staging/evil.csv", pe_payload)
        assert ei.value.code == "FILE_FORMAT_MISMATCH"
        assert not File.objects.filter(tenant=tenant).exists()

    def test_repeat_delivery_is_idempotent_by_source_key(self):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)

        first = _create(ingestion, "staging/a.csv", _CSV_ROWS)
        second = _create(ingestion, "staging/a.csv", _CSV_ROWS)

        assert second.created is False, "the re-delivery found the existing rows"
        assert second.file.id == first.file.id
        assert second.dataset.id == first.dataset.id
        assert File.objects.filter(tenant=tenant).count() == 1
        assert Dataset.objects.filter(tenant=tenant).count() == 1

    def test_empty_content_is_rejected(self):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)

        with pytest.raises(ServiceValidationError) as excinfo:
            _create(ingestion, "staging/a.csv", b"")

        assert excinfo.value.code == "EMPTY_FILE"

    def test_unsupported_extension_is_rejected(self):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)

        with pytest.raises(ServiceValidationError) as excinfo:
            _create(ingestion, "staging/b.exe", b"content")

        assert excinfo.value.code == "UNSUPPORTED_FORMAT"

    def test_same_asset_increments_version_with_parent_linkage(self):
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset

        tenant = _mk_tenant()
        asset = Asset.objects.create(tenant=tenant, name="w38core-asset", key="w38core-asset")
        ingestion = _mk_ingestion(tenant, asset=asset)

        first = _create(ingestion, "staging/a.csv", _CSV_ROWS)
        second = _create(ingestion, "staging/b.csv", _CSV_ROWS)

        assert first.dataset.version == 1
        assert second.dataset.version == 2, "the second file on the asset is version 2"
        assert second.dataset.parent_version_id == first.dataset.id
        assert list(
            Dataset.objects.filter(tenant=tenant)
            .order_by("version")
            .values_list("version", flat=True)
        ) == [1, 2]

    def test_schema_incompatible_new_version_is_rejected(self):
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset

        tenant = _mk_tenant()
        asset = Asset.objects.create(tenant=tenant, name="w38core-asset2", key="w38core-asset2")
        ingestion = _mk_ingestion(tenant, asset=asset)

        _create(ingestion, "staging/a.csv", _CSV_ROWS)  # fields: id, name

        with pytest.raises(ServiceValidationError) as excinfo:
            _create(ingestion, "staging/b.csv", _CSV_ROWS_NARROW)  # drops "name"

        assert excinfo.value.code == "SCHEMA_INCOMPATIBLE"
        assert Dataset.objects.filter(tenant=tenant).count() == 1, (
            "the incompatible version was rejected — no new row"
        )

    def test_active_name_collision_is_classified(self):
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)

        _create(ingestion, "staging/a.csv", _CSV_ROWS)
        # A DIFFERENT source key with the same basename collides on the
        # (tenant, name) unique-when-ACTIVE constraint — the core must
        # classify it instead of leaking an IntegrityError.
        with pytest.raises(ServiceValidationError) as excinfo:
            _create(ingestion, "prod/a.csv", _CSV_ROWS)

        assert excinfo.value.code == "CATALOG_FILE_NAME_COLLISION"
        assert File.objects.filter(tenant=tenant).count() == 1

    def test_auto_create_asset_and_auto_activate(self):
        from hub.apps.assets.models import Asset, AssetStatus

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, auto_create_asset=True, auto_activate=True)

        result = _create(ingestion, "staging/a.csv", _CSV_ROWS)

        assert result.asset is not None
        ingestion.refresh_from_db()
        assert ingestion.asset_id == result.asset.id
        result.asset.refresh_from_db()
        assert result.asset.status == AssetStatus.ACTIVE
        assert Asset.objects.filter(tenant=tenant).count() == 1
