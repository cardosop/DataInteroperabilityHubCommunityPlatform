"""
Phase 260.6.B — ``SnapshotType`` enum tests.

Pre-260.6.B, ``DatasetSnapshot.snapshot_type`` was a free-form
``CharField`` accepting any string; the ``METADATA_ONLY`` code
path in ``TimeTravelQuery.create_snapshot`` had no test coverage,
and unknown values silently produced empty-payload snapshots.

260.6.B formalises the enum (``SnapshotType``) AND tightens the
helper's behaviour:

* Unknown ``snapshot_type`` → ``ValueError`` (was: silent empty
  snapshot).
* ``INCREMENTAL`` → ``NotImplementedError`` (was: silent empty
  snapshot — the placeholder branch never matched anything).
* ``METADATA_ONLY`` → produces the documented payload (now
  exercised end-to-end).

These tests pin the new contract layer-by-layer.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset, DatasetSnapshot, SnapshotType
from hub.apps.datasets.time_travel import TimeTravelQuery
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

User = get_user_model()


class _SnapshotTestBase(TestCase):
    """Shared tenant / asset / file / dataset fixture."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Snap {uid}",
            slug=f"snap-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"snap-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"snap-asset-{uid}",
            name="Snap Asset",
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
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={"fields": [{"name": "col1", "type": "string"}]},
            sample_data_json=[{"col1": "value1"}],
            row_count=100,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            version_tags=["production"],
            created_by=self.user,
        )
        VersionHistoryManager.create_version(self.dataset, is_current=True)


class SnapshotTypeEnumMembershipTest(TestCase):
    """Phase 260.6.B — pin the enum's membership set as a test
    invariant. The set is the contract surface SDK / FE consumers
    branch on; a silent rename / addition / removal would surface
    here as a build break rather than as a runtime mismatch."""

    @pytest.mark.integration
    def test_enum_members_match_spec(self):
        # Phase 260.6.B canonical set per
        # ``openspec/changes/fullcontract/specs/file-storage/spec.md``.
        members = {member.value for member in SnapshotType}
        self.assertEqual(
            members,
            {"FULL", "SCHEMA_ONLY", "METADATA_ONLY", "INCREMENTAL"},
            f"SnapshotType members must match spec; got {members!r}",
        )

    @pytest.mark.integration
    def test_enum_choices_used_by_field(self):
        # The ``DatasetSnapshot.snapshot_type`` field's choices
        # MUST match the enum — drift here means Forms / DRF
        # serializers reject values the model accepts (or vice
        # versa), an internally inconsistent contract.
        field = DatasetSnapshot._meta.get_field("snapshot_type")
        choice_values = {value for value, _label in field.choices or ()}
        enum_values = {member.value for member in SnapshotType}
        self.assertEqual(
            choice_values,
            enum_values,
            f"Field choices drifted from SnapshotType enum: "
            f"field={choice_values!r}, enum={enum_values!r}",
        )

    @pytest.mark.integration
    def test_default_is_full(self):
        # Pin the default so a future migration that flips the
        # default surfaces here. Existing deployment behaviour
        # depends on FULL being the default for callers that
        # don't pass ``snapshot_type`` explicitly.
        field = DatasetSnapshot._meta.get_field("snapshot_type")
        self.assertEqual(field.default, "FULL")


class SnapshotTypeMetadataOnlyTest(_SnapshotTestBase):
    """Phase 260.6.B — METADATA_ONLY snapshot was a code path
    introduced pre-260.6.B but never test-covered. This pins the
    expected payload shape so future refactors can't silently
    drop / rename the documented fields."""

    @pytest.mark.integration
    def test_metadata_only_snapshot_includes_documented_fields(self):
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset,
            snapshot_type=SnapshotType.METADATA_ONLY.value,
        )
        self.assertEqual(snapshot.snapshot_type, "METADATA_ONLY")
        # Documented fields per ``time_travel.create_snapshot``'s
        # METADATA_ONLY branch.
        for field in (
            "version",
            "semantic_version",
            "version_tags",
            "snapshot_metadata",
            "created_at",
        ):
            self.assertIn(
                field,
                snapshot.snapshot_data,
                f"METADATA_ONLY snapshot missing documented field "
                f"{field!r}; got {list(snapshot.snapshot_data.keys())}",
            )

    @pytest.mark.integration
    def test_metadata_only_snapshot_excludes_schema_and_sample(self):
        # The whole point of METADATA_ONLY is to produce a
        # lightweight payload WITHOUT schema / sample data.
        # Without this regression guard, a future refactor that
        # adds schema_json to the METADATA_ONLY branch would
        # bloat the column without any test failing.
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset,
            snapshot_type=SnapshotType.METADATA_ONLY.value,
        )
        self.assertNotIn("schema_json", snapshot.snapshot_data)
        self.assertNotIn("sample_data_json", snapshot.snapshot_data)
        self.assertNotIn("row_count", snapshot.snapshot_data)

    @pytest.mark.integration
    def test_metadata_only_accepts_enum_member_directly(self):
        # 260.6.B made the helper accept the enum member (not
        # just its string value). This test pins the ergonomic
        # contract — callers can write
        # ``create_snapshot(ds, SnapshotType.METADATA_ONLY)``
        # without remembering to call ``.value``.
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset,
            snapshot_type=SnapshotType.METADATA_ONLY,
        )
        self.assertEqual(snapshot.snapshot_type, "METADATA_ONLY")


class SnapshotTypeIncrementalNotImplementedTest(_SnapshotTestBase):
    """Phase 260.6.B — INCREMENTAL is a documented post-MVP
    placeholder. Calling create_snapshot with it MUST raise
    NotImplementedError so a future caller wiring INCREMENTAL
    into production gets a loud "not yet shipped" signal at
    runtime — NOT the silent empty-payload trap the pre-260.6.B
    code produced."""

    @pytest.mark.integration
    def test_incremental_snapshot_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            TimeTravelQuery.create_snapshot(
                self.dataset,
                snapshot_type=SnapshotType.INCREMENTAL.value,
            )
        # Error message names the spec so a new engineer hitting
        # this finds the design intent without grep'ing.
        message = str(ctx.exception)
        self.assertIn("INCREMENTAL", message)
        self.assertIn("post-MVP placeholder", message)
        self.assertIn("file-storage", message)

    @pytest.mark.integration
    def test_incremental_with_enum_member_also_raises(self):
        # Same as above but passing the bare enum member.
        with self.assertRaises(NotImplementedError):
            TimeTravelQuery.create_snapshot(
                self.dataset,
                snapshot_type=SnapshotType.INCREMENTAL,
            )

    @pytest.mark.integration
    def test_incremental_does_not_persist_a_row(self):
        # The raise MUST fire before any DB write — a
        # half-committed snapshot row would corrupt downstream
        # consumers that count snapshots per dataset.
        before = DatasetSnapshot.objects.filter(dataset=self.dataset).count()
        with self.assertRaises(NotImplementedError):
            TimeTravelQuery.create_snapshot(
                self.dataset,
                snapshot_type="INCREMENTAL",
            )
        after = DatasetSnapshot.objects.filter(dataset=self.dataset).count()
        self.assertEqual(
            after, before,
            "INCREMENTAL must NOT persist a snapshot row",
        )


class SnapshotTypeUnknownValueTest(_SnapshotTestBase):
    """Phase 260.6.B — unknown ``snapshot_type`` values used to
    silently produce empty-payload snapshots (pre-260.6.B's
    if/elif chain fell through with ``snapshot_data = {}``).
    260.6.B raises ``ValueError`` so typos are caught at the
    call site instead of silently corrupting downstream snapshot
    consumers."""

    @pytest.mark.integration
    def test_unknown_snapshot_type_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            TimeTravelQuery.create_snapshot(
                self.dataset,
                snapshot_type="RANDOM_TYPO",
            )
        # The error names the canonical valid set so a caller
        # that mis-typed has the corrected list right there.
        message = str(ctx.exception)
        self.assertIn("RANDOM_TYPO", message)
        for valid in ("FULL", "SCHEMA_ONLY", "METADATA_ONLY"):
            self.assertIn(valid, message)

    @pytest.mark.integration
    def test_unknown_does_not_persist_a_row(self):
        # Same regression-guard as INCREMENTAL — the raise must
        # fire before the DB write.
        before = DatasetSnapshot.objects.filter(dataset=self.dataset).count()
        with self.assertRaises(ValueError):
            TimeTravelQuery.create_snapshot(
                self.dataset,
                snapshot_type="GARBAGE",
            )
        after = DatasetSnapshot.objects.filter(dataset=self.dataset).count()
        self.assertEqual(after, before)


class RestoreFromSnapshotRequiresFullTest(_SnapshotTestBase):
    """Phase 260.6.B.R1 GAP-B — ``restore_from_snapshot`` MUST
    reject non-FULL snapshots. SCHEMA_ONLY and METADATA_ONLY
    intentionally omit load-bearing fields; restoring from them
    would produce a degraded Dataset row with ``None`` values
    where downstream consumers expect the parent's payload.
    """

    @pytest.mark.integration
    def test_restore_from_full_snapshot_succeeds(self):
        # Regression guard — the FULL path MUST continue to
        # work. The R1 check applies only to non-FULL types.
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset, snapshot_type=SnapshotType.FULL,
        )
        restored = TimeTravelQuery.restore_from_snapshot(snapshot)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.asset, self.asset)

    @pytest.mark.integration
    def test_restore_from_schema_only_raises_value_error(self):
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset, snapshot_type=SnapshotType.SCHEMA_ONLY,
        )
        with self.assertRaises(ValueError) as ctx:
            TimeTravelQuery.restore_from_snapshot(snapshot)
        message = str(ctx.exception)
        self.assertIn("FULL", message)
        self.assertIn("SCHEMA_ONLY", message)

    @pytest.mark.integration
    def test_restore_from_metadata_only_raises_value_error(self):
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset, snapshot_type=SnapshotType.METADATA_ONLY,
        )
        with self.assertRaises(ValueError) as ctx:
            TimeTravelQuery.restore_from_snapshot(snapshot)
        message = str(ctx.exception)
        self.assertIn("FULL", message)
        self.assertIn("METADATA_ONLY", message)

    @pytest.mark.integration
    def test_restore_rejection_does_not_create_dataset_row(self):
        # The raise MUST fire BEFORE any Dataset.objects.create
        # — a half-committed restore would corrupt the version
        # chain (rejected restore that nonetheless created a
        # version-incremented row).
        snapshot = TimeTravelQuery.create_snapshot(
            self.dataset, snapshot_type=SnapshotType.METADATA_ONLY,
        )
        before = Dataset.objects.filter(asset=self.asset).count()
        with self.assertRaises(ValueError):
            TimeTravelQuery.restore_from_snapshot(snapshot)
        after = Dataset.objects.filter(asset=self.asset).count()
        self.assertEqual(after, before)


class WorkflowSnapshotCreationGoesThroughHelperTest(_SnapshotTestBase):
    """Phase 260.6.B.R1 GAP-A — the orchestration workflow path
    (``VersionCreationWorkflow._create_snapshot_task``) routes
    through ``TimeTravelQuery.create_snapshot`` so it inherits
    the same validation surface — unknown / INCREMENTAL types
    raise the same way they do at the helper.

    Pre-R1 the workflow used a free-form
    ``DatasetSnapshot.objects.create`` that accepted any
    ``snapshot_type`` string from ``input_data``; a workflow
    caller submitting ``"INCREMENTAL"`` or a typo would silently
    bypass the 260.6.B contract.
    """

    def _build_input(self, *, snapshot_type: str) -> dict:
        return {
            "dataset_id": str(self.dataset.id),
            "tenant_id": str(self.tenant.id),
            "store_snapshot": True,
            "snapshot_type": snapshot_type,
        }

    def _make_instance(self):
        # Lightweight workflow instance fixture — the task body
        # only reads ``tenant_id`` and ``id`` off the instance.
        # ``WorkflowDefinition`` is tenant-scopeless (the per-tenant
        # binding lives on ``WorkflowInstance.tenant``); its real
        # required fields are ``name`` (str), ``version`` (str), and
        # ``dsl_json`` (dict with at least one step) — see
        # ``hub.apps.orchestration.models.WorkflowDefinition.clean``.
        from hub.apps.orchestration.models import WorkflowInstance, WorkflowDefinition

        defn = WorkflowDefinition.objects.create(
            name=f"snap-test-{uuid.uuid4().hex[:8]}",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "noop", "type": "noop"}],
            },
            created_by=self.user,
        )
        return WorkflowInstance.objects.create(
            workflow_definition=defn, tenant=self.tenant,
            input_data={}, state_data={}, created_by=self.user,
        )

    @pytest.mark.integration
    def test_workflow_with_incremental_raises_not_implemented(self):
        from hub.apps.orchestration.workflows.version_creation import (
            VersionCreationWorkflow,
        )

        instance = self._make_instance()
        with self.assertRaises(NotImplementedError):
            VersionCreationWorkflow._store_version_snapshot_task(
                input_data=self._build_input(snapshot_type="INCREMENTAL"),
                instance=instance,
                step=None,
            )

    @pytest.mark.integration
    def test_workflow_with_unknown_type_raises_value_error(self):
        from hub.apps.orchestration.workflows.version_creation import (
            VersionCreationWorkflow,
        )

        instance = self._make_instance()
        with self.assertRaises(ValueError):
            VersionCreationWorkflow._store_version_snapshot_task(
                input_data=self._build_input(snapshot_type="GARBAGE"),
                instance=instance,
                step=None,
            )

    @pytest.mark.integration
    def test_workflow_with_metadata_only_routes_through_helper(self):
        # Sanity / regression — the workflow path must still
        # produce a snapshot for valid types. After R1 the
        # payload shape matches ``time_travel.create_snapshot``'s
        # METADATA_ONLY (no longer the workflow's pre-R1 extra
        # ``dataset_id`` / ``created_by_id`` denormalisations,
        # which were unused).
        from hub.apps.orchestration.workflows.version_creation import (
            VersionCreationWorkflow,
        )

        instance = self._make_instance()
        result = VersionCreationWorkflow._store_version_snapshot_task(
            input_data=self._build_input(snapshot_type="METADATA_ONLY"),
            instance=instance,
            step=None,
        )
        self.assertTrue(result["snapshot_stored"])
        snapshot = DatasetSnapshot.objects.get(id=result["snapshot_id"])
        self.assertEqual(snapshot.snapshot_type, "METADATA_ONLY")
        # Payload matches the helper's METADATA_ONLY shape (no
        # schema_json / sample_data_json).
        self.assertNotIn("schema_json", snapshot.snapshot_data)
        self.assertNotIn("sample_data_json", snapshot.snapshot_data)
