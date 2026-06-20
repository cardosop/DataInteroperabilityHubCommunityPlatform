"""
Phase 250.2.B.6 — end-to-end TDD test for the schema-drift workflow step.

Pins the wire contract from D250.12:

* The workflow's ``compare_schema_against_contract`` step runs
  AFTER ``attach_dataset`` and BEFORE ``validate_contract``.
* When the contract's declared schema and the dataset's inferred
  schema disagree, the workflow:

  1. Persists ``schema_drift`` into ``WorkflowInstance.state_data``
     so the data-first endpoint can return it under
     ``result_summary.schema_drift``.
  2. Emits an ``ASSET_SCHEMA_DRIFT_DETECTED`` audit event with the
     severity + drift details (capped at 20 fields per category
     per Phase 240.5.F redaction policy).
  3. Lets the workflow continue (the gate is observability, NOT
     enforcement, per D250.12) so the asset still gets persisted.

* When the contract and dataset agree, NO audit event fires AND
  ``state_data["schema_drift"]`` carries ``detected=False``.

This test exercises the workflow step DIRECTLY (calling the bound
task function) so it runs deterministically without needing the
full data-first endpoint stack. The endpoint-level e2e is covered
by the existing ``test_data_first_*`` suites once they're augmented
with the new ``result_summary`` shape.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.orchestration.models import WorkflowInstance
from hub.apps.orchestration.workflows.asset_creation import (
    AssetCreationWorkflow,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    file_obj = File.objects.create(
        tenant=tenant,
        name="data.csv",
        content_type="text/csv",
        size=42,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{uuid.uuid4()}/data.csv",
        created_by=user,
    )
    return tenant, user, file_obj


def _seed_contract_with_schema(tenant, user, *, fields):
    """Seed a Contract row with the given schema fields under
    ``hub_contract_json``."""
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        status=ContractStatus.DRAFT,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.0.2",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_version="1.0.0",
        hub_contract_json={
            "info": {"name": "test contract", "version": "1.0.0"},
            "schema": {"fields": list(fields)},
        },
        normalization_status=NormalizationStatus.NORMALIZED_OK,
        created_by=user,
    )


def _seed_dataset_with_schema(tenant, user, file_obj, asset, *, fields):
    """Seed a Dataset row with the given inferred schema."""
    return Dataset.objects.create(
        tenant=tenant,
        asset=asset,
        file=file_obj,
        version=1,
        format="CSV",
        is_current=True,
        created_by=user,
        schema_json={"fields": list(fields)},
    )


def _seed_workflow_instance(tenant, user, asset, contract, dataset):
    """Build a minimal WorkflowInstance (no full engine bootstrapping
    needed — we call the task function directly)."""
    from hub.apps.orchestration.models import WorkflowDefinition, WorkflowStatus

    wf_def = WorkflowDefinition.objects.create(
        name="asset_creation_test",
        version="1.0.0",
        dsl_json={
            "version": "1.0.0",
            "steps": [
                {"name": "compare_schema_against_contract", "type": "task"},
            ],
        },
        is_active=True,
        created_by=user,
    )
    instance = WorkflowInstance.objects.create(
        workflow_definition=wf_def,
        workflow_name="asset_creation_test",
        workflow_version="1.0.0",
        tenant=tenant,
        status=WorkflowStatus.RUNNING,
        input_data={},
        state_data={
            "asset_id": str(asset.id),
            "contract_id": str(contract.id),
            "dataset_id": str(dataset.id),
        },
        created_by=user,
    )
    return instance


# ---------------------------------------------------------------------------
# 250.2.B.6 — wire contract: detected=True + audit emitted on mismatch
# ---------------------------------------------------------------------------


class SchemaDriftWorkflowMismatchTest(TestCase):
    """Mismatched schema → ``detected=True``, severity matches, audit
    event fires with the drift payload."""

    def test_structural_drift_emits_audit_with_fail_severity(self):
        tenant, user, file_obj = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        contract = _seed_contract_with_schema(
            tenant,
            user,
            fields=[
                {"name": "id", "type": "integer"},
                {"name": "email", "type": "string"},  # missing in dataset
            ],
        )
        dataset = _seed_dataset_with_schema(
            tenant,
            user,
            file_obj,
            asset,
            fields=[
                {"name": "id", "data_type": "string"},  # type mismatch (incompatible)
                # ``email`` missing → triggers structural FAIL
            ],
        )
        instance = _seed_workflow_instance(tenant, user, asset, contract, dataset)

        before_audit = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
            tenant=tenant,
        ).count()

        result = AssetCreationWorkflow._compare_schema_against_contract_task(
            input_data={},
            instance=instance,
            step=None,
        )

        # 1. Workflow output carries the drift envelope.
        assert "schema_drift" in result
        drift = result["schema_drift"]
        assert drift["detected"] is True
        assert drift["severity"] == "FAIL"
        assert drift["structural_incompatibility"] is True
        assert drift["missing_fields"] == ["email"]
        assert len(drift["type_mismatches"]) == 1
        assert drift["type_mismatches"][0]["field"] == "id"
        assert drift["type_mismatches"][0]["compatible"] is False

        # 2. Persisted to state_data so the API response can read it.
        instance.refresh_from_db()
        assert instance.state_data["schema_drift"] == drift

        # 3. Audit event emitted with severity + sanitised payload.
        after_audit = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
            tenant=tenant,
        ).order_by("-timestamp")
        assert after_audit.count() - before_audit == 1
        ev = after_audit.first()
        assert ev.details_json["severity"] == "FAIL"
        assert ev.details_json["asset_id"] == str(asset.id)
        assert ev.details_json["contract_id"] == str(contract.id)
        assert ev.details_json["dataset_id"] == str(dataset.id)
        assert ev.details_json["missing_fields"] == ["email"]
        assert ev.details_json["structural_incompatibility"] is True
        # Result code on the audit row distinguishes WARN from FAIL.
        assert ev.result == "FAILURE"

    def test_extra_only_drift_emits_audit_with_warn_severity(self):
        tenant, user, file_obj = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        contract = _seed_contract_with_schema(
            tenant,
            user,
            fields=[{"name": "id", "type": "integer"}],
        )
        dataset = _seed_dataset_with_schema(
            tenant,
            user,
            file_obj,
            asset,
            fields=[
                {"name": "id", "data_type": "integer"},
                {"name": "extra_audit_ts", "data_type": "timestamp"},
            ],
        )
        instance = _seed_workflow_instance(tenant, user, asset, contract, dataset)

        result = AssetCreationWorkflow._compare_schema_against_contract_task(
            input_data={},
            instance=instance,
            step=None,
        )

        drift = result["schema_drift"]
        assert drift["severity"] == "WARN"
        assert drift["extra_fields"] == ["extra_audit_ts"]
        assert drift["structural_incompatibility"] is False
        # Audit row uses WARNING result_code for WARN severity.
        ev = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
            tenant=tenant,
        ).first()
        assert ev is not None and ev.result == "WARNING"
        assert ev.details_json["severity"] == "WARN"


class SchemaDriftWorkflowAlignedTest(TestCase):
    """Aligned schema → no drift, no audit event."""

    def test_aligned_schemas_emit_no_audit(self):
        tenant, user, file_obj = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        contract = _seed_contract_with_schema(
            tenant,
            user,
            fields=[
                {"name": "id", "type": "integer"},
                {"name": "email", "type": "string"},
            ],
        )
        dataset = _seed_dataset_with_schema(
            tenant,
            user,
            file_obj,
            asset,
            fields=[
                {"name": "id", "data_type": "integer"},
                {"name": "email", "data_type": "string"},
            ],
        )
        instance = _seed_workflow_instance(tenant, user, asset, contract, dataset)
        before = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
            tenant=tenant,
        ).count()

        result = AssetCreationWorkflow._compare_schema_against_contract_task(
            input_data={},
            instance=instance,
            step=None,
        )

        drift = result["schema_drift"]
        assert drift["detected"] is False
        assert drift["severity"] == "NONE"
        # state_data MUST still carry the (clean) drift envelope so
        # the API response includes ``result_summary.schema_drift``
        # for client clarity.
        instance.refresh_from_db()
        assert instance.state_data["schema_drift"] == drift
        # No audit on a clean diff.
        after = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
            tenant=tenant,
        ).count()
        assert after == before


class SchemaDriftWorkflowMissingInputsTest(TestCase):
    """When dataset_id or contract_id is missing, the step skips
    cleanly (returns ``schema_drift.detected=False``, no audit)."""

    def test_missing_dataset_id_skips_cleanly(self):
        tenant, user, _file = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        contract = _seed_contract_with_schema(
            tenant,
            user,
            fields=[{"name": "id", "type": "integer"}],
        )
        # Build the instance state WITHOUT dataset_id
        from hub.apps.orchestration.models import WorkflowDefinition, WorkflowStatus

        wf_def = WorkflowDefinition.objects.create(
            name="asset_creation_test_skip",
            version="1.0.0",
            dsl_json={
                "version": "1.0.0",
                "steps": [{"name": "compare_schema_against_contract", "type": "task"}],
            },
            is_active=True,
            created_by=user,
        )
        instance = WorkflowInstance.objects.create(
            workflow_definition=wf_def,
            workflow_name="asset_creation_test_skip",
            workflow_version="1.0.0",
            tenant=tenant,
            status=WorkflowStatus.RUNNING,
            input_data={},
            state_data={
                "asset_id": str(asset.id),
                "contract_id": str(contract.id),
                # dataset_id intentionally missing
            },
            created_by=user,
        )

        result = AssetCreationWorkflow._compare_schema_against_contract_task(
            input_data={},
            instance=instance,
            step=None,
        )

        drift = result["schema_drift"]
        assert drift["detected"] is False
        assert drift["severity"] == "NONE"
        assert drift.get("skipped") is True
        # No audit event for the skipped path.
        assert (
            AuditEvent.objects.filter(
                action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
                tenant=tenant,
            ).count()
            == 0
        )


# ---------------------------------------------------------------------------
# 250.2.B audit-pass — best-effort audit emission must not break the workflow
# ---------------------------------------------------------------------------


class SchemaDriftWorkflowAuditFailureBestEffortTest(TestCase):
    """When ``create_audit_event`` raises (e.g. transient audit-DB
    outage), the workflow MUST still:

    1. Persist drift to ``state_data["schema_drift"]`` so the
       data-first endpoint can include it in ``result_summary``.
    2. Return the drift envelope from the task without re-raising
       (so the workflow continues to the next step).

    This pins the "drift detection is observability, not enforcement"
    contract from D250.12 even under audit-system failure modes.
    """

    def test_audit_emission_failure_preserves_drift_in_state_data(self):
        from unittest.mock import patch

        tenant, user, file_obj = _seed()
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        contract = _seed_contract_with_schema(
            tenant,
            user,
            fields=[
                {"name": "id", "type": "integer"},
                {"name": "email", "type": "string"},
            ],
        )
        dataset = _seed_dataset_with_schema(
            tenant,
            user,
            file_obj,
            asset,
            fields=[{"name": "id", "data_type": "string"}],  # FAIL drift
        )
        instance = _seed_workflow_instance(tenant, user, asset, contract, dataset)

        # Patch the audit-emission helper at the call-site import path
        # so the workflow's ``create_audit_event`` raises instead of
        # writing a row. The patch target is the task body's local
        # import (``from hub.apps.audit.utils import create_audit_event``)
        # — patching the source module guarantees the workflow sees
        # the failure.
        with patch(
            "hub.apps.audit.utils.create_audit_event",
            side_effect=RuntimeError("audit DB unreachable"),
        ):
            result = AssetCreationWorkflow._compare_schema_against_contract_task(
                input_data={},
                instance=instance,
                step=None,
            )

        # Workflow returned the drift envelope (no re-raise).
        drift = result["schema_drift"]
        assert drift["detected"] is True
        assert drift["severity"] == "FAIL"

        # state_data still carries the drift — the audit failure did
        # NOT roll back the persistence step.
        instance.refresh_from_db()
        assert instance.state_data["schema_drift"] == drift

        # No audit row was emitted (the patched helper raised).
        assert (
            AuditEvent.objects.filter(
                action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
                tenant=tenant,
            ).count()
            == 0
        )
