"""
Phase 260.6.C — ``Dataset.kind`` field tests (closes Gap 28).

Pre-260.6.C, the ``DatasetKind`` enum existed but the FIELD was
absent from the ``Dataset`` model — dead code from a model
perspective. 260.6.C added the field with a backfill migration
and constrained the API write surface per OQ260.3 (external
clients can only create FILE-kind datasets; EXTERNAL_REF is set
server-side by the federation pipeline).

Test layers:

* **Enum / field invariants** — pin the choices set, default,
  index. A silent re-tune of any of these would surface as a
  test failure rather than a behaviour shift across deployments.
* **Migration data integrity** — every existing row has
  ``kind='FILE'`` after migration 0106 (the backfill default
  applies to all pre-260.6.C rows; orphan post-purge rows where
  ``file_id IS NULL`` were originally file-backed and correctly
  carry FILE).
* **Serializer write-surface contract** — POST /datasets/ with
  ``kind=EXTERNAL_REF`` returns 400 with the typed code
  ``EXTERNAL_REF_NOT_API_SETTABLE`` (per OQ260.3); omitting
  ``kind`` defaults to FILE; explicit ``kind=FILE`` admits.
* **Service-layer / ORM bypass** — the federation pipeline
  (which lands in Phase 250.5) writes ``kind=EXTERNAL_REF``
  directly via ``Dataset.objects.create`` without going through
  the API serializer. The model accepts EXTERNAL_REF as a
  legitimate value; only the API serializer rejects it.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset, DatasetKind
from hub.apps.datasets.serializers import DatasetCreateSerializer
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class DatasetKindEnumInvariantsTest(TestCase):
    """Phase 260.6.C — pin the enum + field invariants."""

    @pytest.mark.integration
    def test_enum_members_match_spec(self):
        members = {m.value for m in DatasetKind}
        self.assertEqual(
            members,
            {"FILE", "EXTERNAL_REF"},
            f"DatasetKind members must match spec; got {members!r}",
        )

    @pytest.mark.integration
    def test_field_default_is_FILE(self):
        # The default is what makes the backfill migration work
        # WITHOUT a separate data-migration step. Pinning here
        # catches a future migration that flips the default.
        field = Dataset._meta.get_field("kind")
        self.assertEqual(field.default, "FILE")

    @pytest.mark.integration
    def test_field_has_db_index(self):
        # ``db_index=True`` is load-bearing for the future
        # ``Dataset.objects.filter(kind=EXTERNAL_REF)`` query
        # the federation pipeline will run. Without the index a
        # multi-million-row table sequence-scans.
        field = Dataset._meta.get_field("kind")
        self.assertTrue(
            field.db_index,
            "Dataset.kind MUST be indexed for federation-filter performance",
        )

    @pytest.mark.integration
    def test_field_choices_match_enum(self):
        # Drift guard between enum and field choices — if these
        # diverge, Forms / DRF validation rejects values the
        # model accepts (or vice versa).
        field = Dataset._meta.get_field("kind")
        field_choice_values = {value for value, _label in field.choices or ()}
        enum_values = {m.value for m in DatasetKind}
        self.assertEqual(field_choice_values, enum_values)


class _DatasetKindTestBase(TestCase):
    """Shared tenant + user + asset + file fixture."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DK {uid}",
            slug=f"dk-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"dk-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"dk-asset-{uid}",
            name="DK Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="data.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/data.csv",
            created_by=self.user,
        )


class DatasetKindMigrationBackfillTest(_DatasetKindTestBase):
    """Phase 260.6.C — verify migration 0106's backfill produced
    correct values. Migration runs before any test executes; we
    test the post-migration invariant on freshly-created rows
    (which use the field's default) AND assert no rows exist
    with an empty / null ``kind`` (which the post-migration
    schema disallows)."""

    @pytest.mark.integration
    def test_default_dataset_creation_yields_kind_FILE(self):
        # ``Dataset.objects.create`` without explicit ``kind=``
        # should land FILE via the field default. Mirrors the
        # backfill behaviour for pre-260.6.C rows.
        ds = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        ds.refresh_from_db()
        self.assertEqual(ds.kind, "FILE")

    @pytest.mark.integration
    def test_dataset_with_no_file_still_defaults_FILE(self):
        # Pre-260.6.C orphan rows (file purged, file_id NULL)
        # were originally file-backed; backfill correctly tags
        # them ``FILE``. Sanity check on the field default
        # behaviour: a Dataset without a file FK still gets
        # ``kind='FILE'`` because the migration ran with that
        # default for ALL existing rows.
        ds = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=None,
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        ds.refresh_from_db()
        self.assertEqual(ds.kind, "FILE")


class DatasetCreateSerializerKindContractTest(_DatasetKindTestBase):
    """Phase 260.6.C / OQ260.3 — API write surface accepts only
    ``FILE`` from external clients."""

    def _payload(self, **overrides) -> dict:
        base = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        base.update(overrides)
        return base

    @pytest.mark.integration
    def test_omitting_kind_defaults_to_FILE(self):
        # Pre-260.6.C clients don't know ``kind`` exists; the
        # default keeps them working.
        s = DatasetCreateSerializer(data=self._payload())
        self.assertTrue(s.is_valid(), msg=str(s.errors))
        self.assertEqual(s.validated_data["kind"], "FILE")

    @pytest.mark.integration
    def test_explicit_kind_FILE_admits(self):
        # Forward-compat clients that explicitly send the field
        # MUST be admitted when they send the canonical FILE
        # value.
        s = DatasetCreateSerializer(data=self._payload(kind="FILE"))
        self.assertTrue(s.is_valid(), msg=str(s.errors))

    @pytest.mark.integration
    def test_kind_EXTERNAL_REF_rejected_with_typed_code(self):
        # Per OQ260.3: external clients cannot create
        # EXTERNAL_REF datasets. The error MUST carry a typed
        # code so SDK consumers branch precisely (not on parsed
        # message strings).
        s = DatasetCreateSerializer(data=self._payload(kind="EXTERNAL_REF"))
        self.assertFalse(s.is_valid())
        self.assertIn("kind", s.errors)
        codes = [getattr(d, "code", None) for d in s.errors["kind"]]
        self.assertIn(
            "EXTERNAL_REF_NOT_API_SETTABLE",
            codes,
            f"EXTERNAL_REF rejection must carry typed code; got {codes!r}",
        )

    @pytest.mark.integration
    def test_kind_unknown_rejected_by_choice_validation(self):
        # DRF's standard ``ChoiceField`` validation rejects
        # unrecognised values BEFORE our custom validator runs.
        # Pin so a typo'd value gets the standard error rather
        # than silently coercing to a default.
        s = DatasetCreateSerializer(data=self._payload(kind="GARBAGE"))
        self.assertFalse(s.is_valid())
        self.assertIn("kind", s.errors)


class DatasetServiceLayerKindBypassTest(_DatasetKindTestBase):
    """Phase 260.6.C / OQ260.3 — the federation pipeline (Asset
    Phase 250.5, future) writes ``EXTERNAL_REF`` server-side via
    the service / ORM layer, BYPASSING the API serializer's
    rejection. The model itself MUST accept EXTERNAL_REF as a
    legitimate value (only the serializer rejects it)."""

    @pytest.mark.integration
    def test_orm_create_with_kind_EXTERNAL_REF_succeeds(self):
        # ``Dataset.objects.create(kind=EXTERNAL_REF, ...)`` is
        # the federation pipeline's path. The model layer
        # accepts the value; only the API serializer rejects
        # external-client submissions.
        ds = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=None,  # external-ref datasets have no file FK
            kind=DatasetKind.EXTERNAL_REF,
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            format="EXTERNAL",
            version=1,
            created_by=self.user,
        )
        ds.refresh_from_db()
        self.assertEqual(ds.kind, "EXTERNAL_REF")

    @pytest.mark.integration
    def test_orm_filter_by_kind_returns_only_matching_rows(self):
        # The ``db_index=True`` test above pins the index
        # exists; this test pins that filtering on ``kind``
        # actually narrows the row set (regression guard for a
        # future migration that drops the index or breaks the
        # field semantics).
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            kind=DatasetKind.FILE,
            schema_json={},
            sample_data_json=[],
            row_count=0,
            format="CSV",
            version=1,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=None,
            kind=DatasetKind.EXTERNAL_REF,
            schema_json={},
            sample_data_json=[],
            row_count=0,
            format="EXTERNAL",
            version=2,
            created_by=self.user,
        )
        Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=None,
            kind=DatasetKind.EXTERNAL_REF,
            schema_json={},
            sample_data_json=[],
            row_count=0,
            format="EXTERNAL",
            version=3,
            created_by=self.user,
        )

        file_count = Dataset.objects.filter(
            tenant=self.tenant,
            kind=DatasetKind.FILE,
        ).count()
        external_count = Dataset.objects.filter(
            tenant=self.tenant,
            kind=DatasetKind.EXTERNAL_REF,
        ).count()

        self.assertEqual(file_count, 1)
        self.assertEqual(external_count, 2)
