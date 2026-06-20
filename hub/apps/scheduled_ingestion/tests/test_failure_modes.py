"""
Phase 260.7.F — scheduled-ingestion failure-mode audit-event tests
(closes pass-3 B3-9).

Three failure modes pinned, each emitting a typed audit event and an
appropriate run / dataset side-effect:

1. **Source unreachable** — emitted by the orchestration layer's
   ``_download_file_task`` when the connector cannot fetch a file
   (timeout, auth failure, 404, connector unregistered). The file is
   marked permanently failed; NO Dataset / File row is created.
   Audit: ``SCHEDULED_INGESTION_SOURCE_UNREACHABLE`` (FAILURE,
   audience=TENANT_ADMIN).

2. **Empty data** — emitted by the worker AFTER successful dataset
   creation when the inferred row count is 0 (e.g., a CSV with
   header only). The dataset version IS created (row_count=0,
   sample_data_json=[]) — empty snapshots are not a hard failure.
   Audit: ``SCHEDULED_INGESTION_EMPTY_DATA_WARN`` (WARNING,
   audience=TENANT_ADMIN).

3. **Schema-incompatible** — emitted by the worker BEFORE dataset
   creation when the new inferred schema removes fields the prior
   version had. The ingestion is rejected (no Dataset / File row).
   Audit: ``SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED``
   (FAILURE, audience=TENANT_ADMIN).

S3 stub policy: mirrors ``test_worker_services_validation_parity.py``
— ``S3StorageClient.save_file`` is the only patched boundary; every
other side-effect (DB writes, audit emission, business rules,
signals) runs against real machinery. This is the documented
boundary-mock pattern, not a business-logic mock.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.worker_services import process_file_for_run
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Fixture helpers — same shape as test_worker_services_validation_parity.py.
# ---------------------------------------------------------------------------


def _seed_tenant_user_si() -> tuple[Tenant, User, ScheduledIngestion]:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"FailMode-{uid}",
        slug=f"fail-mode-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    si = ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"FailMode SI {uid}",
        source_type=SourceType.S3,
        source_config={"bucket": "test-bucket", "prefix": "data/"},
        schedule_type=ScheduleType.DAILY,
        schedule_config={"time": "00:00"},
        file_pattern=r".*\.csv",
        auto_create_asset=True,
        created_by=user,
    )
    return tenant, user, si


def _seed_run(si: ScheduledIngestion) -> ScheduledIngestionRun:
    return ScheduledIngestionRun.objects.create(
        scheduled_ingestion=si,
        status=ScheduledIngestionRunStatus.RUNNING,
    )


def _stub_s3_save_file():
    """S3 boundary stub — same policy as parity tests."""
    return patch(
        "hub.apps.files.storage.S3StorageClient.save_file",
        return_value="test/storage/path",
    )


def _audit_count(*, tenant: Tenant, action: str) -> int:
    return AuditEvent.objects.filter(tenant=tenant, action=action).count()


def _last_audit_for_action(*, tenant: Tenant, action: str) -> AuditEvent:
    # ``AuditEvent`` exposes the canonical event time as ``timestamp``
    # (``auto_now_add=True``); there is no ``created_at`` column.
    # Pre-fix the ``-created_at`` order_by raised
    # ``FieldError: Cannot resolve keyword 'created_at'`` and masked
    # the failure-mode audit assertion below.
    return AuditEvent.objects.filter(tenant=tenant, action=action).order_by("-timestamp").first()


# ---------------------------------------------------------------------------
# 260.7.F — Empty-data warning. Fires AFTER dataset creation; the
# dataset version IS created with row_count=0; the run is NOT failed.
# ---------------------------------------------------------------------------


@override_settings(CLAMAV_ENABLED=False)
class EmptyDataWarnAuditTest(TestCase):
    """260.7.F — header-only CSV → dataset created with row_count=0 +
    SCHEDULED_INGESTION_EMPTY_DATA_WARN audit emitted.

    The task spec: "empty data → version with row_count=0 + WARN audit".
    The dataset is NOT blocked; the warning is informational so ops
    can spot empty-snapshot feeds without aborting the pipeline.
    """

    @pytest.mark.integration
    def test_header_only_csv_emits_empty_data_warn_and_creates_dataset(self):
        tenant, user, si = _seed_tenant_user_si()
        run = _seed_run(si)
        before_audit_count = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
        )

        # Header-only CSV: schema infers 2 columns, 0 data rows.
        header_only_csv = b"id,name\n"

        with _stub_s3_save_file():
            result = process_file_for_run(
                run_id=str(run.id),
                file_path="data/empty.csv",
                file_content=header_only_csv,
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                dq_options={"strict_mode": False},
            )

        # The dataset IS created (260.7.F contract: warning, not fail).
        self.assertIn("dataset_id", result)
        dataset = Dataset.objects.get(id=result["dataset_id"])
        self.assertEqual(
            dataset.row_count or 0,
            0,
            "260.7.F contract: empty-data dataset must have row_count=0",
        )
        # Asset auto-created (per scheduled_ingestion.auto_create_asset=True);
        # File row created (no rejection).
        self.assertIsNotNone(dataset.asset_id)
        self.assertIsNotNone(dataset.file_id)
        self.assertTrue(File.objects.filter(pk=dataset.file_id).exists())

        # Audit event emitted with WARNING severity + TENANT_ADMIN audience.
        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
            ),
            before_audit_count + 1,
            "260.7.F contract: empty-data must emit exactly one WARN audit",
        )
        audit = _last_audit_for_action(
            tenant=tenant,
            action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
        )
        self.assertEqual(audit.result, "WARNING")
        self.assertEqual(audit.details_json.get("audience"), "TENANT_ADMIN")
        self.assertEqual(
            audit.details_json.get("dataset_id"),
            str(dataset.id),
        )
        self.assertEqual(audit.details_json.get("row_count"), 0)

    @pytest.mark.integration
    def test_non_empty_csv_does_NOT_emit_empty_data_warn(self):
        """Regression guard: a CSV with actual data rows must NOT
        spuriously emit the empty-data warning.
        """
        tenant, user, si = _seed_tenant_user_si()
        run = _seed_run(si)
        before_audit_count = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
        )

        with _stub_s3_save_file():
            process_file_for_run(
                run_id=str(run.id),
                file_path="data/full.csv",
                file_content=b"id,name\n1,alpha\n2,beta\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
            ),
            before_audit_count,
            "non-empty CSV must NOT trigger empty-data warning",
        )


# ---------------------------------------------------------------------------
# 260.7.F — Schema-incompatible rejection. Fires BEFORE dataset
# creation when the new schema removes fields the prior version had.
# ---------------------------------------------------------------------------


@override_settings(CLAMAV_ENABLED=False)
class SchemaIncompatibleRejectionTest(TestCase):
    """260.7.F — new ingestion that removes fields → reject + audit +
    no Dataset / File row created. TENANT_ADMIN alerted via audit.

    Backward-compatible widenings (adding fields) are allowed —
    consumers that joined on the prior fields keep working.
    """

    @pytest.mark.integration
    def test_removing_field_rejects_with_audit(self):
        tenant, user, si = _seed_tenant_user_si()
        run_1 = _seed_run(si)

        # First run: 2-column CSV → asset + dataset v1 with fields {id, name}.
        with _stub_s3_save_file():
            r1 = process_file_for_run(
                run_id=str(run_1.id),
                file_path="data/v1.csv",
                file_content=b"id,name\n1,alpha\n2,beta\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )
        v1 = Dataset.objects.get(id=r1["dataset_id"])
        self.assertIn("id", {f["name"] for f in v1.schema_json["fields"]})
        self.assertIn("name", {f["name"] for f in v1.schema_json["fields"]})

        # Second run: same asset, but the source removed the ``name``
        # column. Should be REJECTED.
        run_2 = _seed_run(si)
        before_failure_audit = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        )
        before_dataset_count = Dataset.objects.filter(tenant=tenant).count()
        before_file_count = File.objects.filter(tenant=tenant).count()

        with _stub_s3_save_file(), self.assertRaises(ServiceValidationError) as cm:
            process_file_for_run(
                run_id=str(run_2.id),
                file_path="data/v2-broken.csv",
                # ``name`` removed from the new ingestion.
                file_content=b"id\n3\n4\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        # The exception carries the typed code + the missing-fields detail.
        self.assertEqual(cm.exception.code, "SCHEMA_INCOMPATIBLE")
        self.assertIn("name", cm.exception.details["missing_fields"])

        # NO new Dataset / File row was created. Pre-existing v1 row
        # is preserved; the count is unchanged.
        self.assertEqual(
            Dataset.objects.filter(tenant=tenant).count(),
            before_dataset_count,
            "rejection must NOT create a new dataset row",
        )
        self.assertEqual(
            File.objects.filter(tenant=tenant).count(),
            before_file_count,
            "rejection must NOT create a new file row",
        )

        # Audit event emitted with FAILURE severity + TENANT_ADMIN audience.
        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
            ),
            before_failure_audit + 1,
        )
        audit = _last_audit_for_action(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        )
        self.assertEqual(audit.result, "FAILURE")
        self.assertEqual(audit.details_json.get("audience"), "TENANT_ADMIN")
        self.assertIn("name", audit.details_json.get("missing_fields", []))
        self.assertEqual(
            audit.details_json.get("prior_dataset_id"),
            str(v1.id),
        )

    @pytest.mark.integration
    def test_adding_field_is_compatible_no_rejection(self):
        """Adding a new field is a backward-compatible widening — must
        NOT trigger schema-incompatible rejection. Pin the
        compatibility direction so a future regression that
        incorrectly rejects ADDED fields is caught."""
        tenant, user, si = _seed_tenant_user_si()
        run_1 = _seed_run(si)

        with _stub_s3_save_file():
            process_file_for_run(
                run_id=str(run_1.id),
                file_path="data/v1.csv",
                file_content=b"id\n1\n2\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        run_2 = _seed_run(si)
        before_failure_audit = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        )
        with _stub_s3_save_file():
            r2 = process_file_for_run(
                run_id=str(run_2.id),
                file_path="data/v2-widened.csv",
                # ``id`` retained, ``name`` added — superset of prior.
                file_content=b"id,name\n3,gamma\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        # The 2nd run succeeded: dataset version=2 created.
        self.assertIn("dataset_id", r2)
        v2 = Dataset.objects.get(id=r2["dataset_id"])
        self.assertEqual(v2.version, 2)

        # No schema-incompat audit fired.
        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
            ),
            before_failure_audit,
            "adding a field must NOT trigger SCHEMA_INCOMPATIBLE",
        )

    @pytest.mark.integration
    def test_first_run_no_prior_version_skips_compat_check(self):
        """The first run for an asset has no prior version to compare
        against. Schema-compat check is skipped (the new schema has
        no prior shape to be incompatible WITH). Pin so a future
        regression that incorrectly rejects first-version ingestions
        is caught.
        """
        tenant, user, si = _seed_tenant_user_si()
        run = _seed_run(si)
        before_failure_audit = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        )

        with _stub_s3_save_file():
            r = process_file_for_run(
                run_id=str(run.id),
                file_path="data/first.csv",
                file_content=b"id,name\n1,alpha\n",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        self.assertIn("dataset_id", r)
        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
            ),
            before_failure_audit,
            "first-version ingestion has no prior to compare against",
        )


# ---------------------------------------------------------------------------
# 260.7.F — Source-unreachable. Fires from the orchestration layer's
# _download_file_task when the connector cannot fetch a file.
# ---------------------------------------------------------------------------


@override_settings(CLAMAV_ENABLED=False)
class SourceUnreachableAuditTest(TestCase):
    """260.7.F — connector raises during ``_download_file_task`` →
    SCHEDULED_INGESTION_SOURCE_UNREACHABLE audit emitted (audience=
    TENANT_ADMIN), exception re-raised so the workflow loop's
    failure-recording path runs.
    """

    def _seed_workflow_instance(self, tenant: Tenant, user: User):
        """Build the minimal WorkflowDefinition + WorkflowInstance pair
        ``_download_file_task`` needs. The DSL must validate per
        ``WorkflowDefinition.clean`` (steps + version required)."""
        from hub.apps.orchestration.models import (
            WorkflowDefinition,
            WorkflowInstance,
        )

        uid = uuid.uuid4().hex[:8]
        wd = WorkflowDefinition.objects.create(
            name=f"si-test-{uid}",
            version="1.0.0",
            dsl_json={
                "steps": [{"name": "download", "task": "download_file"}],
                "version": "1.0.0",
            },
            created_by=user,
        )
        wi = WorkflowInstance.objects.create(
            workflow_definition=wd,
            workflow_name=wd.name,
            workflow_version=wd.version,
            tenant=tenant,
            input_data={},
            state_data={},
        )
        return wi

    @pytest.mark.integration
    def test_connector_raises_emits_source_unreachable_audit(self):
        from hub.apps.orchestration.workflows.scheduled_ingestion import (
            ScheduledIngestionWorkflow,
        )

        tenant, user, si = _seed_tenant_user_si()
        wi = self._seed_workflow_instance(tenant, user)

        before_audit = _audit_count(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
        )

        # Patch the connector factory to return a connector whose
        # download_file raises a transient-looking error (timeout /
        # auth fail / 404 / etc.). The audit emission path runs in
        # the except block; the exception is re-raised so the
        # workflow's failure-recording path runs.
        class _UnreachableConnector:
            def download_file(self, source_config, file_path, temp_path):
                raise Exception("Connection timed out")

        class _Factory:
            @staticmethod
            def get_connector(source_type):
                return _UnreachableConnector()

        with patch(
            "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory",
            return_value=_Factory,
        ):
            # ``_download_file_task`` reads ``file_path`` from
            # ``input_data["file_info"]["file_path"]`` (or
            # ``loop_item``), NOT from a top-level ``file_path`` key.
            # Provide it on the canonical path so the validator does
            # not short-circuit with "file_path is required" before
            # reaching the connector that should raise the
            # "Connection timed out" the audit row pins on.
            input_data = {
                "scheduled_ingestion_id": str(si.id),
                "source_type": str(si.source_type),
                "source_config": si.source_config,
                "file_info": {
                    "file_path": "data/unreachable.csv",
                    "size": 1024,
                },
            }
            with self.assertRaises(Exception) as cm:
                ScheduledIngestionWorkflow._download_file_task(
                    input_data=input_data,
                    instance=wi,
                    step={"name": "download_file"},
                )
            # The original connector exception propagates (the audit
            # emission is observability, not flow control).
            self.assertIn("Connection timed out", str(cm.exception))

        # Audit event emitted with FAILURE severity + TENANT_ADMIN audience.
        self.assertEqual(
            _audit_count(
                tenant=tenant,
                action="SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
            ),
            before_audit + 1,
            "260.7.F contract: source-unreachable must emit exactly one FAILURE audit",
        )
        audit = _last_audit_for_action(
            tenant=tenant,
            action="SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
        )
        self.assertEqual(audit.result, "FAILURE")
        self.assertEqual(audit.details_json.get("audience"), "TENANT_ADMIN")
        self.assertEqual(
            audit.details_json.get("file_path"),
            "data/unreachable.csv",
        )
        self.assertIn(
            "Connection timed out",
            audit.details_json.get("error_message", ""),
        )
        # The failed-files state was also recorded — audit emission is
        # ADDITIVE, not replacing the existing failure path.
        # NOTE: orchestration mutates ``instance.state_data`` IN MEMORY
        # without ``instance.save()`` (per the docstring at lines
        # 674-677 of scheduled_ingestion.py: "state_data is authoritative
        # and processed in update_ingestion_state"). DO NOT call
        # ``wi.refresh_from_db()`` here — that would replace the in-memory
        # mutation with the DB version (pre-mutation), masking the
        # in-memory recording the workflow relies on.
        failed = wi.state_data.get("failed_files_during_loop", [])
        self.assertTrue(
            any(f["file_path"] == "data/unreachable.csv" for f in failed),
            "260.7.F audit emission must NOT regress failed-files state recording",
        )


# ---------------------------------------------------------------------------
# 260.7.F — Audit-event constant invariants. Pin the constants exist
# in event_types.py exports so a future migration that drops one is
# caught at import time.
# ---------------------------------------------------------------------------


class FailureModeAuditEventConstantsTest(TestCase):
    """260.7.F.2 — pin the 3 audit-event constants exist + are
    exported. A future PR that renames or drops one would fail this
    test before any downstream code regression surfaces."""

    @pytest.mark.integration
    def test_three_constants_exist(self):
        from hub.apps.audit import event_types

        self.assertEqual(
            event_types.SCHEDULED_INGESTION_SOURCE_UNREACHABLE,
            "SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
        )
        self.assertEqual(
            event_types.SCHEDULED_INGESTION_EMPTY_DATA_WARN,
            "SCHEDULED_INGESTION_EMPTY_DATA_WARN",
        )
        self.assertEqual(
            event_types.SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED,
            "SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        )

    @pytest.mark.integration
    def test_three_constants_in_all(self):
        from hub.apps.audit import event_types

        for name in (
            "SCHEDULED_INGESTION_SOURCE_UNREACHABLE",
            "SCHEDULED_INGESTION_EMPTY_DATA_WARN",
            "SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
        ):
            self.assertIn(
                name,
                event_types.__all__,
                f"Phase 260.7.F constant {name!r} must be in event_types.__all__",
            )
