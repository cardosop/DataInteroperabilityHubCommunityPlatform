"""
Asset Creation/Activation Workflow

Orchestrates the asset creation and activation process with proper error handling,
retry logic, and compensation. Supports both contract-first and data-first flows.

Phase 250.1.A — fail-closed-at-intake refactor
==============================================

For the **data-first flow** (``file_id`` provided), the workflow runs
the compliance and DQ gates BEFORE persisting the ``Asset`` row. A
FAIL on either gate (or an UNKNOWN result while the tenant has
``compliance_fail_closed_enabled=True``) refuses intake and emits
``ASSET_FAIL_CLOSED_REJECTED``; no asset / dataset rows are created.
Contract-first intake (``file_id is None``) is unchanged — there is
no payload to gate on.

Saga compensation map (250.1.A.4)
---------------------------------

If a step fails AFTER the ``Asset`` row was persisted, the engine
runs each completed step's compensation in reverse order. The
mapping below is the load-bearing contract — change it only with a
follow-up ADR + migration plan.

    forward step                  | compensation behaviour
    ------------------------------+-------------------------------------------
    create_asset_record           | delete the Asset row (cascades datasets,
                                  | contracts, runs that FK to it)
    attach_contract               | unset Contract.asset = None, restore
                                  | Contract.version, leave Contract row
                                  | (it pre-existed the workflow)
    create_dataset_from_file      | delete the Dataset row created here
    attach_dataset                | unset Dataset.asset, restore
                                  | Dataset.version
    validate_contract             | NO-OP (idempotent read; failure leaves
                                  | the Asset in DRAFT + WARN per D250.12)
    link_odps                     | rollback_odps_linking task (existing) —
                                  | unlinks ODPS↔ODCS, deletes the ODPS
                                  | Contract iff this workflow created it
    activate_asset                | revert Asset.status = DRAFT, decrement
                                  | version, re-apply prior compliance /
                                  | DQ statuses
    index_for_search              | best-effort delete from search index;
                                  | a stale entry is acceptable as the
                                  | next index pass corrects it
    send_notifications            | NO-OP (notifications are user-facing
                                  | side-effects; can't be unsent)

Per-step + workflow timeouts (250.1.A.5 / B-4)
----------------------------------------------

* :data:`DEFAULT_STEP_TIMEOUT_SECONDS` — soft cap per step (30 s).
  Enforced at the network layer by the configured ``httpx`` timeouts
  on the compliance / DQ / S3 clients; a step that exceeds the cap
  raises and the engine marks it FAILED → saga compensation runs.
* :data:`DEFAULT_WORKFLOW_TIMEOUT_SECONDS` — global cap (300 s = 5
  min). Persisted in ``state_data["__workflow_deadline_at__"]`` at
  ``execute()`` time; each step checks the deadline at entry and
  raises ``WorkflowDeadlineExceeded`` if breached.
"""
import functools
import json
import structlog
import time
from typing import Any, Callable, Dict, List, Optional
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.assets.business_rules import AssetsBusinessRules
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus
from hub.apps.search.indexing import SearchIndexer
from hub.apps.semantic.utils import map_asset_to_semantic
from hub.apps.audit.utils import create_audit_event, redact_fail_closed_audit_payload
from hub.apps.audit import event_types as audit_event_types
from hub.apps.notifications.tasks import send_email_async
from hub.apps.notifications.models import EmailType
from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)
UserModel = get_user_model()


# ---------------------------------------------------------------------------
# Phase 250.1.A.5 — per-step + workflow timeout constants (B-4 / 8.10.7)
# ---------------------------------------------------------------------------

#: Soft cap per workflow step in seconds. Enforced at the HTTP-client
#: layer (httpx timeouts on compliance / DQ / S3 clients) — a step
#: that exceeds the cap raises at the boundary and the engine marks
#: it FAILED → saga compensation runs.
DEFAULT_STEP_TIMEOUT_SECONDS: int = 30

#: Hard cap on the whole workflow execution. Persisted as a deadline
#: in ``state_data`` so each step can check it at entry without
#: needing a thread / signal handler.
DEFAULT_WORKFLOW_TIMEOUT_SECONDS: int = 300

#: Per-tenant statuses considered acceptable to PERSIST the Asset.
#: ``WARN`` is allowed because the asset still gets persisted; only
#: ``FAIL`` / ``UNKNOWN`` (or anything we can't classify) refuses
#: intake when tenant fail-closed is on.
_GATE_PASS_STATUSES = {"PASS", "WARN"}


class WorkflowDeadlineExceeded(Exception):
    """Raised when the workflow's wall-clock deadline is breached."""


class FailClosedRejection(Exception):
    """Raised when a pre-persistence gate FAILs and tenant fail-closed is on.

    Carries the gate name and reason so the workflow's audit emission
    can capture both the trigger and the original microservice
    response.

    **Important**: the engine catches every step exception, rolls
    back the step's savepoint, and writes ``str(e)`` into
    ``WorkflowInstance.error_message``. The compensation handler
    then prefixes that string when storing the workflow-level
    ``error_message``. To survive that round-trip — so the data-first
    view can resurface the typed exception with structured details
    — the ``__str__`` representation embeds a JSON-encoded payload
    flagged with :data:`SENTINEL`. :meth:`from_message` recognises
    the sentinel anywhere in the message and reconstructs the
    typed instance.

    The human-readable prefix is preserved for log readability;
    parsing happens by locating the JSON suffix.
    """

    SENTINEL: str = "FAIL_CLOSED_REJECTION_PAYLOAD"

    def __init__(
        self,
        gate: str,
        gate_status: str,
        reason: str,
        compliance_run_id: Optional[str] = None,
        dq_run_id: Optional[str] = None,
    ):
        self.gate = gate
        self.gate_status = gate_status
        self.reason = reason
        self.compliance_run_id = compliance_run_id
        self.dq_run_id = dq_run_id
        payload = json.dumps(
            {
                "_sentinel": self.SENTINEL,
                "gate": gate,
                "gate_status": gate_status,
                "reason": reason,
                "compliance_run_id": compliance_run_id,
                "dq_run_id": dq_run_id,
            },
            sort_keys=True,
        )
        super().__init__(
            f"asset intake refused (fail-closed): "
            f"{gate}={gate_status} ({reason}) "
            f"::FCR_BEGIN::{payload}::FCR_END::"
        )

    #: Start delimiter for the JSON-encoded payload in ``str(exc)``.
    _BEGIN: str = "::FCR_BEGIN::"
    #: End delimiter — chosen to be unique enough that a natural
    #: ``reason`` string won't contain it. JSON values are double-
    #: quoted, so the literal token ``::FCR_END::`` cannot appear
    #: inside a value without being explicitly written there.
    _END: str = "::FCR_END::"

    @classmethod
    def from_message(cls, message: Optional[str]) -> Optional["FailClosedRejection"]:
        """Reconstruct from a stored ``error_message`` if it embeds the sentinel.

        Returns ``None`` for any string that doesn't contain a valid
        FCR payload. Used by :meth:`AssetCreationWorkflow.execute`
        and the data-first view to recover the typed exception after
        the workflow engine has wrapped it in generic handling.

        The parser uses unique ``::FCR_BEGIN::`` / ``::FCR_END::``
        delimiters rather than re-using ``::`` so a ``reason`` text
        that contains colons cannot prematurely terminate the JSON
        window.
        """
        if not message:
            return None
        start = message.find(cls._BEGIN)
        if start == -1:
            return None
        end = message.find(cls._END, start + len(cls._BEGIN))
        if end == -1:
            return None
        raw = message[start + len(cls._BEGIN):end]
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("_sentinel") != cls.SENTINEL:
            return None
        return cls(
            gate=payload.get("gate", "unknown"),
            gate_status=payload.get("gate_status", "UNKNOWN"),
            reason=payload.get("reason", ""),
            compliance_run_id=payload.get("compliance_run_id"),
            dq_run_id=payload.get("dq_run_id"),
        )


def _build_fail_closed_audit_payload(
    *,
    tenant_id: str,
    file_id: Optional[str],
    key: Optional[str],
    name: Optional[str],
    workflow_instance_id: str,
    rejection: FailClosedRejection,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build (redacted, full) payloads for fail-closed audit persistence."""
    full_details: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "file_id": str(file_id) if file_id else None,
        "key": key,
        "name": name,
        "gate": rejection.gate,
        "gate_status": rejection.gate_status,
        "reason": rejection.reason,
        "compliance_run_id": rejection.compliance_run_id,
        "dq_run_id": rejection.dq_run_id,
        "workflow_instance_id": str(workflow_instance_id),
    }
    if rejection.compliance_run_id:
        from hub.apps.compliance.models import ComplianceRun

        compliance_run = ComplianceRun.objects.filter(id=rejection.compliance_run_id).first()
        if compliance_run is not None:
            full_details["compliance"] = {
                "overall_status": compliance_run.overall_status,
                "allowed_to_store": compliance_run.allowed_to_store,
                "risk_level": compliance_run.risk_level,
                "detected_categories_json": compliance_run.detected_categories_json,
                "column_findings_json": compliance_run.column_findings_json,
                "regulation_mapping_json": compliance_run.regulation_mapping_json,
            }
    if rejection.dq_run_id:
        from hub.apps.dq.models import DQRun

        dq_run = DQRun.all_objects.filter(id=rejection.dq_run_id).first()
        if dq_run is not None:
            full_details["dq"] = {
                "overall_status": dq_run.overall_status,
                "quality_score": dq_run.quality_score,
                "checks_json": dq_run.checks_json,
                "details_json": dq_run.details_json,
            }
    return redact_fail_closed_audit_payload(full_details), full_details


def _check_workflow_deadline(instance: WorkflowInstance) -> None:
    """Raise :class:`WorkflowDeadlineExceeded` if the workflow's wall-clock budget is gone.

    Stored as a UNIX epoch (float) on ``state_data`` so it survives
    process boundaries and workflow re-resumption.
    """
    deadline = (instance.state_data or {}).get("__workflow_deadline_at__")
    if deadline is None:
        return
    if time.time() > float(deadline):
        raise WorkflowDeadlineExceeded(
            f"asset_creation workflow exceeded "
            f"{DEFAULT_WORKFLOW_TIMEOUT_SECONDS}s deadline"
        )


class AssetCreationWorkflow:
    """
    Asset creation/activation workflow orchestrator.

    Manages the complete asset creation and activation process. The
    Phase 250.1.A re-sequence runs the **compliance and DQ gates**
    BEFORE persisting the ``Asset`` row in the data-first flow:

    1. (data-first) infer schema → generate ODCS → validate ODCS →
       normalise ODCS → create contract row
    2. (data-first) compliance scan **in-memory** (no asset created)
    3. (data-first) DQ scan **in-memory** (no asset created)
    4. fail-closed gate — if EITHER gate FAILed (or returned
       UNKNOWN while ``tenant.compliance_fail_closed_enabled=True``),
       refuse to persist the Asset and emit
       ``ASSET_FAIL_CLOSED_REJECTED``
    5. create asset record (only on PASS/WARN)
    6. attach contract → create dataset → attach dataset
    7. validate contract → link ODPS
    8. activate asset (auto_activate defaults to True per D250.2)
    9. index for search → notifications → audit logging

    Contract-first intake skips steps 1–4; the gates have nothing to
    scan because there's no payload.
    """

    WORKFLOW_NAME = "asset_creation"
    WORKFLOW_VERSION = "2.0.0"  # Phase 250.1.A — gates moved pre-persistence

    #: Phase 250.1.C — legacy workflow version preserved during the
    #: 14-day soak window per D250.7 so in-flight runs created before
    #: the v2 deploy can complete on the v1 step sequence. Slated for
    #: removal in a follow-up PR after telemetry confirms zero v1
    #: in-flight runs (250.1.C.3).
    LEGACY_WORKFLOW_VERSION: str = "1.0.0"

    @classmethod
    def register_workflow(
        cls,
        registry: WorkflowRegistry,
        *,
        include_legacy_versions: bool = True,
    ) -> None:
        """Register every currently-supported version of the workflow.

        Phase 250.1.C — during the 14-day soak window per D250.7 the
        production deploy keeps **both** v1.0.0 and v2.0.0 registered.
        New instances default to v2 (the active version); in-flight
        v1 instances continue to dispatch against their pinned v1
        ``WorkflowDefinition`` row. After the soak completes and
        telemetry confirms zero v1 in-flight runs (250.1.C.3),
        ``include_legacy_versions=False`` (or deletion of
        :meth:`register_workflow_v1`) cleanly drops the v1 path.

        The v1 row is registered FIRST so the subsequent v2
        registration deactivates it (per
        :meth:`WorkflowVersionManager.create_version`'s
        deactivate-on-create-new behaviour); the net post-condition
        is "v2 active, v1 inactive but still in the table".

        Phase 250.1.A.3 — gates run BEFORE asset persistence in the
        data-first flow. The two new in-memory gate steps are
        ``compliance_check_inmemory`` and ``dq_check_inmemory``;
        ``create_asset_record`` reads the gate signals from
        ``state_data`` and refuses to persist when fail-closed.

        Args:
            registry: WorkflowRegistry instance
            include_legacy_versions: When True (default), register the
                v1 DSL alongside v2 so in-flight v1 runs can still
                resume. Set False post-soak (250.1.C.3).
        """
        if include_legacy_versions:
            cls.register_workflow_v1(registry)
        cls._register_workflow_v2(registry)

    @classmethod
    def _register_workflow_v2(cls, registry: WorkflowRegistry) -> None:
        """Register the v2.0.0 fail-closed-at-intake DSL."""
        workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                # ----- Data-first contract synthesis (unchanged) -----
                {
                    "name": "infer_schema",
                    "type": "task",
                    "task": "asset_creation.infer_schema",
                    "condition": {
                        "if": "{{ file_id != null && contract_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "generate_odcs_from_schema",
                    "type": "task",
                    "task": "asset_creation.generate_odcs_from_schema",
                    "condition": {
                        "if": "{{ schema_json != null && contract_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "validate_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.validate_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "normalize_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.normalize_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "create_odcs_contract_from_schema",
                    "type": "task",
                    "task": "asset_creation.create_odcs_contract_from_schema",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && hub_contract_json != null && contract_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                # ----- Phase 250.1.A.3 — pre-persistence gates -----
                {
                    "name": "compliance_check_inmemory",
                    "type": "task",
                    "task": "asset_creation.compliance_check_inmemory",
                    "condition": {
                        "if": "{{ file_id != null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "dq_check_inmemory",
                    "type": "task",
                    "task": "asset_creation.dq_check_inmemory",
                    "condition": {
                        "if": "{{ file_id != null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                # ----- Asset row + downstream -----
                {
                    "name": "create_asset_record",
                    "type": "task",
                    "task": "asset_creation.create_asset_record",
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "attach_contract",
                    "type": "task",
                    "task": "asset_creation.attach_contract",
                    # No condition - task will check internally if contract_id exists in state_data
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "create_dataset_from_file",
                    "type": "task",
                    "task": "asset_creation.create_dataset_from_file",
                    "condition": {
                        "if": "{{ file_id != null && dataset_id == null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "attach_dataset",
                    "type": "task",
                    "task": "asset_creation.attach_dataset",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                # ----- Phase 250.2.B.2 — schema-drift comparison -----
                # Runs AFTER attach_dataset (so the dataset's
                # ``schema_json`` is on the row) and BEFORE
                # validate_contract (so a structural-FAIL drift can
                # demote contract validation status before the gate
                # checks it). Conditional on BOTH dataset and
                # contract being present — neither alone is enough
                # to compare against.
                {
                    "name": "compare_schema_against_contract",
                    "type": "task",
                    "task": "asset_creation.compare_schema_against_contract",
                    "condition": {
                        "if": (
                            "{{ dataset_id != null && contract_id != null }}"
                        )
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "validate_contract",
                    "type": "task",
                    "task": "asset_creation.validate_contract",
                    "condition": {
                        "if": "{{ contract_id != null && contract_validation_status != 'VALID' }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "link_odps",
                    "type": "task",
                    "task": "asset_creation.link_odps",
                    "condition": {
                        "if": "{{ odps_action != null }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "activate_asset",
                    "type": "task",
                    "task": "asset_creation.activate_asset",
                    "condition": {
                        "if": "{{ auto_activate == true }}"
                    },
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "asset_creation.index_for_search",
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "asset_creation.send_notifications",
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "asset_creation.audit_logging",
                    "timeout_seconds": DEFAULT_STEP_TIMEOUT_SECONDS,
                },
            ],
            "compensation": {"enabled": True},
            "workflow_timeout_seconds": DEFAULT_WORKFLOW_TIMEOUT_SECONDS,
        }
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description=(
                "Phase 250.1.A — orchestrates asset creation with "
                "fail-closed-at-intake compliance + DQ gates that run "
                "BEFORE the Asset row is persisted (data-first flow)"
            ),
            version=cls.WORKFLOW_VERSION,
        )

    @classmethod
    def register_workflow_v1(cls, registry: WorkflowRegistry) -> None:
        """Register the **legacy v1.0.0** asset_creation DSL.

        Phase 250.1.C — preserved for the 14-day soak window per
        D250.7 so already-running v1 workflow instances can complete
        on the legacy step sequence (gates AFTER asset persistence).

        The v1 DSL deliberately reuses the existing legacy task
        registrations (``run_dq_checks``, ``run_compliance_checks``)
        which remain wired via :meth:`register_tasks`. The
        :meth:`_create_asset_record_task` skips its v2-only
        fail-closed gate when ``instance.workflow_version`` starts
        with ``"1."`` — see the version-aware guard at the top of
        that function.

        Slated for removal in a follow-up PR per 250.1.C.3 once
        telemetry confirms zero v1 in-flight runs (typically 14
        days after the v2 deploy).

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": cls.LEGACY_WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                # ----- Data-first contract synthesis (unchanged) -----
                {
                    "name": "infer_schema",
                    "type": "task",
                    "task": "asset_creation.infer_schema",
                    "condition": {
                        "if": "{{ file_id != null && contract_id == null }}"
                    },
                },
                {
                    "name": "generate_odcs_from_schema",
                    "type": "task",
                    "task": "asset_creation.generate_odcs_from_schema",
                    "condition": {
                        "if": "{{ schema_json != null && contract_id == null }}"
                    },
                },
                {
                    "name": "validate_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.validate_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    },
                },
                {
                    "name": "normalize_generated_odcs",
                    "type": "task",
                    "task": "asset_creation.normalize_generated_odcs",
                    "condition": {
                        "if": "{{ odcs_contract_json != null && contract_id == null }}"
                    },
                },
                {
                    "name": "create_odcs_contract_from_schema",
                    "type": "task",
                    "task": "asset_creation.create_odcs_contract_from_schema",
                    "condition": {
                        "if": (
                            "{{ odcs_contract_json != null && "
                            "hub_contract_json != null && "
                            "contract_id == null }}"
                        )
                    },
                },
                # ----- v1 ordering: asset persisted BEFORE gates -----
                {
                    "name": "create_asset_record",
                    "type": "task",
                    "task": "asset_creation.create_asset_record",
                },
                {
                    "name": "attach_contract",
                    "type": "task",
                    "task": "asset_creation.attach_contract",
                },
                {
                    "name": "create_dataset_from_file",
                    "type": "task",
                    "task": "asset_creation.create_dataset_from_file",
                    "condition": {
                        "if": "{{ file_id != null && dataset_id == null }}"
                    },
                },
                {
                    "name": "attach_dataset",
                    "type": "task",
                    "task": "asset_creation.attach_dataset",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    },
                },
                # ----- v1 post-asset gates (legacy) -----
                {
                    "name": "run_dq_checks",
                    "type": "task",
                    "task": "asset_creation.run_dq_checks",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    },
                },
                {
                    "name": "run_compliance_checks",
                    "type": "task",
                    "task": "asset_creation.run_compliance_checks",
                    "condition": {
                        "if": "{{ dataset_id != null }}"
                    },
                },
                # ----- Phase 250.2.B.2 — schema-drift comparison (v1) -----
                # Same task as v2; the v1 DSL just runs it after the
                # legacy post-asset gates instead of after the
                # in-memory pre-asset gates. The semantic is identical:
                # compare contract schema vs dataset schema, persist
                # severity to state_data, emit audit on detection.
                {
                    "name": "compare_schema_against_contract",
                    "type": "task",
                    "task": "asset_creation.compare_schema_against_contract",
                    "condition": {
                        "if": (
                            "{{ dataset_id != null && contract_id != null }}"
                        )
                    },
                },
                {
                    "name": "validate_contract",
                    "type": "task",
                    "task": "asset_creation.validate_contract",
                    "condition": {
                        "if": (
                            "{{ contract_id != null && "
                            "contract_validation_status != 'VALID' }}"
                        )
                    },
                },
                {
                    "name": "link_odps",
                    "type": "task",
                    "task": "asset_creation.link_odps",
                    "condition": {
                        "if": "{{ odps_action != null }}"
                    },
                },
                {
                    "name": "activate_asset",
                    "type": "task",
                    "task": "asset_creation.activate_asset",
                    "condition": {
                        "if": "{{ auto_activate == true }}"
                    },
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "asset_creation.index_for_search",
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "asset_creation.send_notifications",
                },
                {
                    "name": "audit_logging",
                    "type": "task",
                    "task": "asset_creation.audit_logging",
                },
            ],
            "compensation": {"enabled": True},
        }
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description=(
                "Phase 250.1.A pre-fix legacy DSL (v1.0.0). Preserved "
                "for the 14-day soak window per D250.7 so in-flight "
                "runs can complete on the original step sequence."
            ),
            version=cls.LEGACY_WORKFLOW_VERSION,
        )

    @staticmethod
    def _wrap_with_deadline_check(task_func: Callable) -> Callable:
        """Wrap a task so it raises ``WorkflowDeadlineExceeded`` at task entry.

        Phase 250.1.A.5 / B-4 — the global workflow wall-clock budget
        (5 min default) is checked at the START of every registered
        task, regardless of which step in the DSL it belongs to.
        Per-step soft caps are enforced separately at the HTTP-client
        layer (httpx timeouts on compliance / DQ / S3 clients).

        The wrapper is applied at registration time
        (:meth:`register_tasks`) so every step the engine dispatches
        to gets the check — not just the new gate steps. This closes
        the review-pass gap where the deadline was only enforced in
        4 of ~17 task functions.
        """

        @functools.wraps(task_func)
        def _deadline_checked(input_data, instance, step):
            _check_workflow_deadline(instance)
            return task_func(input_data, instance, step)

        return _deadline_checked

    @staticmethod
    def _append_result_summary_warnings(
        *,
        instance: WorkflowInstance,
        step_name: str,
        message: str,
        warnings_payload: list[Any],
    ) -> None:
        """Accumulate non-fatal workflow warnings in ``state_data``.

        Phase 250.7.E.1 — stores warnings under
        ``state_data.result_summary.warnings`` so the payload can be
        surfaced by API callers and mirrored to audit rows.
        """
        if not warnings_payload:
            return

        state_data: Dict[str, Any] = dict(instance.state_data or {})
        result_summary = state_data.get("result_summary")
        if not isinstance(result_summary, dict):
            result_summary = {}

        warnings_list_raw = result_summary.get("warnings")
        if not isinstance(warnings_list_raw, list):
            warnings_list_raw = []
        warnings_list: List[Dict[str, Any]] = list(warnings_list_raw)

        warnings_list.append(
            {
                "step": step_name,
                "message": message,
                "warnings": [str(w) for w in warnings_payload],
            }
        )
        result_summary["warnings"] = warnings_list
        state_data["result_summary"] = result_summary
        instance.state_data = state_data
        instance.save(update_fields=["state_data"])

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow tasks with the engine.

        Each task is wrapped via :meth:`_wrap_with_deadline_check` so
        the workflow-level wall-clock deadline (250.1.A.5) is
        enforced at the entry of every step, not just the new gate
        steps.

        Args:
            engine: WorkflowEngine instance
        """
        wrap = cls._wrap_with_deadline_check
        engine.register_task("asset_creation.infer_schema", wrap(cls._infer_schema_task))
        engine.register_task("asset_creation.generate_odcs_from_schema", wrap(cls._generate_odcs_from_schema_task))
        engine.register_task("asset_creation.validate_generated_odcs", wrap(cls._validate_generated_odcs_task))
        engine.register_task("asset_creation.normalize_generated_odcs", wrap(cls._normalize_generated_odcs_task))
        engine.register_task("asset_creation.create_odcs_contract_from_schema", wrap(cls._create_odcs_contract_from_schema_task))
        engine.register_task("asset_creation.create_asset_record", wrap(cls._create_asset_record_task))
        engine.register_task("asset_creation.create_dataset_from_file", wrap(cls._create_dataset_from_file_task))
        engine.register_task("asset_creation.attach_contract", wrap(cls._attach_contract_task))
        engine.register_task("asset_creation.attach_dataset", wrap(cls._attach_dataset_task))
        # Phase 250.2.B.2 — schema-drift comparison step.
        engine.register_task(
            "asset_creation.compare_schema_against_contract",
            wrap(cls._compare_schema_against_contract_task),
        )
        # Phase 250.1.A.3 — pre-persistence gate tasks (data-first flow)
        engine.register_task(
            "asset_creation.compliance_check_inmemory",
            wrap(cls._compliance_check_inmemory_task),
        )
        engine.register_task(
            "asset_creation.dq_check_inmemory",
            wrap(cls._dq_check_inmemory_task),
        )
        # Legacy post-asset gate tasks — kept registered so direct
        # unit tests + the v1 workflow handler (per 250.1.C) can
        # still call them. Removed from the v2 DSL above.
        engine.register_task("asset_creation.run_dq_checks", wrap(cls._run_dq_checks_task))
        engine.register_task("asset_creation.run_compliance_checks", wrap(cls._run_compliance_checks_task))
        engine.register_task("asset_creation.validate_contract", wrap(cls._validate_contract_task))
        engine.register_task("asset_creation.link_odps", wrap(cls._link_odps_task))
        # rollback_odps_linking runs as a compensation step — it MUST
        # NOT short-circuit on a deadline exceedance (compensation is
        # the last hope to undo state); intentionally NOT wrapped.
        engine.register_task("asset_creation.rollback_odps_linking", cls._rollback_odps_linking_task)
        engine.register_task("asset_creation.activate_asset", wrap(cls._activate_asset_task))
        engine.register_task("asset_creation.index_for_search", wrap(cls._index_for_search_task))
        engine.register_task("asset_creation.send_notifications", wrap(cls._send_notifications_task))
        engine.register_task("asset_creation.audit_logging", wrap(cls._audit_logging_task))

    @staticmethod
    def _infer_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Infer schema from data file (Data-First flow step 2).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with inferred schema
        """
        from hub.apps.files.models import File
        from hub.apps.datasets.schema_inference import (
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet
        )
        from hub.apps.files.storage import S3StorageClient

        file_id = input_data.get("file_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not file_id:
            raise ValueError("file_id is required for schema inference")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        file_obj = File.objects.get(id=file_id, tenant=tenant)

        # Get file format
        file_format = input_data.get("file_format") or file_obj.content_type
        if not file_format:
            # Try to infer from file extension
            if file_obj.name:
                ext = file_obj.name.split('.')[-1].upper()
                format_map = {
                    'CSV': 'CSV',
                    'JSON': 'JSON',
                    'PARQUET': 'PARQUET',
                    'XLSX': 'XLSX',
                    'XLS': 'XLS'
                }
                file_format = format_map.get(ext, 'CSV')
            else:
                file_format = 'CSV'

        # Download file from storage
        storage_client = S3StorageClient()
        try:
            file_content = storage_client.get_file_content(file_obj.storage_path)
        except Exception as e:
            logger.error(
                "Failed to download file for schema inference",
                workflow_instance_id=str(instance.id),
                file_id=str(file_id),
                error=str(e)
            )
            raise ValueError(f"Failed to download file: {str(e)}")

        # Infer schema based on format
        schema_json = {}
        try:
            if file_format.upper() == 'CSV':
                schema_json = infer_schema_from_csv(file_content)
            elif file_format.upper() == 'JSON':
                schema_json = infer_schema_from_json(file_content)
            elif file_format.upper() == 'PARQUET':
                schema_json = infer_schema_from_parquet(file_content)
            else:
                raise ValueError(f"Unsupported file format for schema inference: {file_format}")
        except Exception as e:
            logger.error(
                "Schema inference failed",
                workflow_instance_id=str(instance.id),
                file_id=str(file_id),
                file_format=file_format,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"Schema inference failed: {str(e)}")

        # Store schema in state_data
        instance.state_data["schema_json"] = schema_json
        instance.state_data["file_id"] = str(file_id)
        instance.state_data["file_format"] = file_format
        instance.save(update_fields=['state_data'])

        logger.info(
            "Schema inferred from data",
            workflow_instance_id=str(instance.id),
            file_id=str(file_id),
            file_format=file_format,
            fields_count=len(schema_json.get('fields', []))
        )

        return {
            "schema_json": schema_json,
            "file_id": str(file_id),
            "file_format": file_format
        }

    @staticmethod
    def _generate_odcs_from_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Generate ODCS contract from inferred schema (Data-First flow step 3).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with generated ODCS contract
        """
        from hub.apps.contracts.odcs_generator import generate_odcs_from_schema

        schema_json = instance.state_data.get("schema_json") or input_data.get("schema_json")
        if not schema_json:
            raise ValueError("schema_json is required (from previous step)")

        contract_id = input_data.get("contract_id")
        contract_name = input_data.get("contract_name") or input_data.get("name") or "Generated Contract from Data"
        contract_description = input_data.get("contract_description") or input_data.get("description")
        contract_version = input_data.get("contract_version", "1.0.0")
        odcs_version = input_data.get("odcs_version", "v3")

        # Generate ODCS contract
        odcs_contract = generate_odcs_from_schema(
            inferred_schema=schema_json,
            contract_id=contract_id,
            contract_name=contract_name,
            contract_description=contract_description,
            contract_version=contract_version,
            odcs_version=odcs_version
        )

        # Store ODCS contract in state_data
        instance.state_data["odcs_contract_json"] = odcs_contract
        instance.state_data["odcs_contract_id"] = odcs_contract.get("id")
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract generated from schema",
            workflow_instance_id=str(instance.id),
            contract_id=odcs_contract.get("id"),
            fields_count=len(odcs_contract.get("schema", {}).get("fields", []))
        )

        return {
            "odcs_contract_json": odcs_contract,
            "odcs_contract_id": odcs_contract.get("id")
        }

    @staticmethod
    def _validate_generated_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate generated ODCS contract (Data-First flow step 4).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation status
        """
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.models import OriginalFormat

        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")

        # Convert to JSON string for validation
        import json
        odcs_raw = json.dumps(odcs_contract_json)

        # Parse and validate ODCS contract
        try:
            parsed_contract = parse_contract(odcs_raw, OriginalFormat.JSON)
            # Basic validation - check required fields
            if not parsed_contract.get("id"):
                raise ValueError("ODCS contract missing required field: id")
            if not parsed_contract.get("name"):
                raise ValueError("ODCS contract missing required field: name")
            if not parsed_contract.get("schema"):
                raise ValueError("ODCS contract missing required field: schema")

            validation_status = "VALID"
            validation_errors = []
        except Exception as e:
            validation_status = "INVALID"
            validation_errors = [str(e)]
            logger.error(
                "ODCS contract validation failed",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODCS contract validation failed: {str(e)}")

        # Store validation status in state_data
        instance.state_data["odcs_validation_status"] = validation_status
        instance.state_data["odcs_validation_errors"] = validation_errors
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract validated",
            workflow_instance_id=str(instance.id),
            validation_status=validation_status
        )

        return {
            "validation_status": validation_status,
            "validation_errors": validation_errors
        }

    @staticmethod
    def _normalize_generated_odcs_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Normalize generated ODCS → HubContract (Data-First flow step 5).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with normalized HubContract
        """
        from hub.apps.contracts.normalization import normalize_contract
        from hub.apps.contracts.models import OriginalSpecType, OriginalFormat

        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")

        # Track ODCS ingestion (Task 6.2.2 - explicit backward compatibility)
        try:
            from hub.apps.observability.otel_metrics import odcs_ingestion_total
            tenant_id = getattr(instance, 'tenant_id', None) or 'unknown'
            odcs_ingestion_total.labels(source='technical', tenant_id=tenant_id).inc()
        except Exception:
            pass  # Metrics failure should not affect workflow

        # Convert to JSON string for normalization
        import json
        odcs_raw = json.dumps(odcs_contract_json)

        # Normalize ODCS → HubContract
        try:
            # normalize_contract returns: (hub_contract, spec_type, spec_version, status, errors, warnings)
            hub_contract, detected_spec_type, detected_spec_version, status, errors, warnings = normalize_contract(
                raw_contract=odcs_raw,
                format="JSON",
                spec_type=OriginalSpecType.ODCS.value
            )

            if status.value == "NORMALIZATION_FAILED":
                error_text = "; ".join(errors) if errors else "Unknown normalization error"
                raise ValueError(f"ODCS normalization failed: {error_text}")

            if not hub_contract:
                raise ValueError("Normalization succeeded but hub_contract is None")

        except Exception as e:
            logger.error(
                "ODCS normalization failed",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODCS normalization failed: {str(e)}")

        # Store HubContract in state_data
        instance.state_data["hub_contract_json"] = hub_contract
        instance.state_data["normalization_status"] = status.value
        instance.state_data["normalization_errors"] = errors
        instance.state_data["normalization_warnings"] = warnings
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract normalized to HubContract",
            workflow_instance_id=str(instance.id),
            normalization_status=status.value,
            errors_count=len(errors),
            warnings_count=len(warnings)
        )

        return {
            "hub_contract_json": hub_contract,
            "normalization_status": status.value,
            "normalization_errors": errors,
            "normalization_warnings": warnings
        }

    @staticmethod
    @transaction.atomic
    def _create_odcs_contract_from_schema_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create ODCS Contract record from generated contract (Data-First flow step 6).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with created contract ID
        """
        from hub.apps.contracts.models import (
            Contract,
            ContractStatus,
            OriginalSpecType,
            OriginalFormat,
            NormalizationStatus,
            ValidationStatus,
        )
        from django.contrib.auth import get_user_model
        import json

        User = get_user_model()

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        odcs_contract_json = instance.state_data.get("odcs_contract_json")
        hub_contract_json = instance.state_data.get("hub_contract_json")
        normalization_status = instance.state_data.get("normalization_status", "NORMALIZED_OK")

        # Phase 250.1.G.3 — propagate the validation result that
        # ``_validate_generated_odcs_task`` recorded in state_data.
        # Previously this was dropped on the floor, leaving the Contract
        # row with ``validation_status=NULL`` even though we'd just
        # validated the same payload one step earlier. That gap blocked
        # downstream activation: ``Asset.can_activate`` filters on
        # ``contracts(status=ACTIVE)`` and ``Contract.clean`` refuses
        # ACTIVE without a non-null VALID/WARNING_ONLY validation_status,
        # so the data-first flow could never auto-activate end-to-end.
        odcs_validation_status = instance.state_data.get("odcs_validation_status")
        odcs_validation_errors = instance.state_data.get("odcs_validation_errors", [])

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not odcs_contract_json:
            raise ValueError("odcs_contract_json is required (from previous step)")
        if not hub_contract_json:
            raise ValueError("hub_contract_json is required (from previous step)")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        user_id = instance.created_by_id or input_data.get("created_by_id")
        user = User.objects.get(id=user_id) if user_id else None

        # Convert ODCS contract to string for storage
        odcs_raw = json.dumps(odcs_contract_json, indent=2)

        # Determine ODCS version from contract
        odcs_version = odcs_contract_json.get("apiVersion", "odcs/v3").split("/")[-1] if odcs_contract_json.get("apiVersion") else "3.0.2"

        # Resolve validation_status into the model enum. ``None`` is kept
        # as ``None`` (column is nullable) so we don't fabricate a state
        # the validator never produced.
        contract_validation_status = (
            ValidationStatus(odcs_validation_status)
            if odcs_validation_status in {v.value for v in ValidationStatus}
            else None
        )

        # Create ODCS contract record (asset will be set later in attach_contract step)
        contract = Contract.objects.create(
            tenant=tenant,
            asset=None,  # Will be set when asset is created and attached
            version=1,  # Will be updated when attached to asset
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version=odcs_version,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_raw,
            hub_contract_version="1.0.0",
            hub_contract_json=hub_contract_json,
            normalization_status=NormalizationStatus(normalization_status) if normalization_status else NormalizationStatus.NORMALIZED_OK,
            normalization_errors=instance.state_data.get("normalization_errors", []),
            normalization_warnings=instance.state_data.get("normalization_warnings", []),
            validation_status=contract_validation_status,
            validation_errors=odcs_validation_errors,
            created_by=user
        )

        # Store contract_id in state_data
        instance.state_data["contract_id"] = str(contract.id)
        instance.save(update_fields=['state_data'])

        logger.info(
            "ODCS contract created from schema",
            workflow_instance_id=str(instance.id),
            contract_id=str(contract.id),
            odcs_version=odcs_version
        )

        return {
            "contract_id": str(contract.id),
            "contract_version": contract.version,
            "normalization_status": normalization_status
        }

    # ------------------------------------------------------------------
    # Phase 250.1.A.3 — pre-persistence in-memory gate tasks
    # ------------------------------------------------------------------

    @staticmethod
    def _compliance_check_inmemory_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step,
    ) -> Dict[str, Any]:
        """Run the compliance microservice scan against the file payload, NO Asset persisted.

        Phase 250.1.A.3 — invokes
        :meth:`hub.apps.compliance.services.ComplianceService.scan_inmemory`
        and writes its terminal status into ``state_data`` so the
        downstream ``create_asset_record`` step can fail-closed if
        the gate didn't return PASS / WARN.

        Phase 250.1.A.9 — if the compliance-service circuit breaker
        is OPEN at entry AND the tenant has NOT opted in via
        ``allow_intake_on_compliance_degraded``, the step fails
        immediately so the engine surfaces a workflow-level FAILED
        (the data-first endpoint maps that to 503 + Retry-After).
        """
        _check_workflow_deadline(instance)
        from hub.apps.compliance.services import ComplianceService
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerState
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        file_id = input_data.get("file_id") or instance.state_data.get("file_id")
        if not tenant_id:
            raise ValueError("tenant_id is required for compliance_check_inmemory")
        if not file_id:
            # No payload — only happens when the engine ignores the
            # condition guard. Skip rather than raise so the workflow
            # stays clean for contract-first callers.
            return {"skipped": True, "reason": "file_id not provided"}

        tenant = Tenant.objects.get(id=tenant_id)

        # Circuit breaker check (D250.9 / 250.1.A.9). When the
        # breaker is OPEN we either bypass-with-WARN (tenant
        # explicitly opted in) or hard-fail with a typed exception
        # the data-first endpoint translates to 503.
        breaker = get_shared_circuit_breaker("compliance-service")
        if breaker.get_state() == CircuitBreakerState.OPEN:
            allow_degraded = bool(getattr(
                tenant, "allow_intake_on_compliance_degraded", False
            ))
            if not allow_degraded:
                raise FailClosedRejection(
                    gate="compliance",
                    gate_status="DEGRADED",
                    reason=(
                        "compliance-service circuit OPEN; tenant has not "
                        "opted in to allow_intake_on_compliance_degraded"
                    ),
                )
            # Tenant opted in to degraded-mode intake — proceed but
            # mark the gate WARN. We DO NOT call scan_inmemory because
            # the breaker would short-circuit it to UNKNOWN anyway,
            # which the create_asset_record step would then read as
            # fail-closed.
            instance.state_data["compliance_inmemory_status"] = "WARN"
            instance.state_data["compliance_inmemory_run_id"] = None
            instance.state_data["compliance_inmemory_degraded"] = True
            instance.save(update_fields=["state_data"])
            return {
                "compliance_inmemory_status": "WARN",
                "compliance_inmemory_degraded": True,
                "skipped_scan": True,
            }

        run = ComplianceService.scan_inmemory(
            file_id=str(file_id),
            tenant=tenant,
            legal_basis=input_data.get("legal_basis"),
            applicable_regulations=input_data.get("applicable_regulations") or None,
            scan_mode=input_data.get("scan_mode", "internal"),
            destination_jurisdiction=input_data.get("destination_jurisdiction"),
            correlation_id=str(instance.id),
        )

        # Map the terminal run state into a single string the gate
        # step can compare against ``_GATE_PASS_STATUSES``. Anything
        # other than PASS / WARN is treated as a failure signal.
        if run.allowed_to_store and run.overall_status in _GATE_PASS_STATUSES:
            gate_status = run.overall_status
        elif run.allowed_to_store and run.overall_status is None:
            # Service returned a 200 with no overall_status field —
            # fail-closed (UNKNOWN signals indeterminate result).
            gate_status = "UNKNOWN"
        else:
            gate_status = run.overall_status or "UNKNOWN"

        instance.state_data["compliance_inmemory_status"] = gate_status
        instance.state_data["compliance_inmemory_run_id"] = str(run.id)
        instance.state_data["compliance_inmemory_allowed_to_store"] = bool(
            run.allowed_to_store
        )
        instance.save(update_fields=["state_data"])

        logger.info(
            "compliance_inmemory_scan_completed",
            workflow_instance_id=str(instance.id),
            file_id=str(file_id),
            run_id=str(run.id),
            gate_status=gate_status,
            allowed_to_store=bool(run.allowed_to_store),
        )
        return {
            "compliance_inmemory_status": gate_status,
            "compliance_inmemory_run_id": str(run.id),
            "compliance_inmemory_allowed_to_store": bool(run.allowed_to_store),
        }

    @staticmethod
    def _dq_check_inmemory_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step,
    ) -> Dict[str, Any]:
        """Run the dq-service scan against the file payload, NO Asset persisted.

        Companion to :meth:`_compliance_check_inmemory_task`.
        """
        _check_workflow_deadline(instance)
        from hub.apps.dq.services import DQService
        from hub.apps.tenants.models import Tenant

        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        file_id = input_data.get("file_id") or instance.state_data.get("file_id")
        if not tenant_id:
            raise ValueError("tenant_id is required for dq_check_inmemory")
        if not file_id:
            return {"skipped": True, "reason": "file_id not provided"}

        tenant = Tenant.objects.get(id=tenant_id)

        run = DQService.scan_inmemory(
            file_id=str(file_id),
            tenant=tenant,
            profile_key=input_data.get("profile_key", "intake_basic_gx"),
            correlation_id=str(instance.id),
        )

        gate_status = run.overall_status or "UNKNOWN"
        if gate_status not in _GATE_PASS_STATUSES and gate_status != "FAIL":
            # Anything we don't recognise (UNKNOWN, custom strings)
            # collapses to UNKNOWN so the gate has a single
            # fail-closed predicate.
            gate_status = "UNKNOWN"

        instance.state_data["dq_inmemory_status"] = gate_status
        instance.state_data["dq_inmemory_run_id"] = str(run.id)
        instance.state_data["dq_inmemory_quality_score"] = run.quality_score
        instance.save(update_fields=["state_data"])

        logger.info(
            "dq_inmemory_scan_completed",
            workflow_instance_id=str(instance.id),
            file_id=str(file_id),
            run_id=str(run.id),
            gate_status=gate_status,
            quality_score=run.quality_score,
        )
        return {
            "dq_inmemory_status": gate_status,
            "dq_inmemory_run_id": str(run.id),
            "dq_inmemory_quality_score": run.quality_score,
        }

    @staticmethod
    def _create_asset_record_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create asset record in DRAFT status.

        Phase 250.1.A.3 — checks the in-memory gate signals stored in
        ``state_data`` by the upstream ``compliance_check_inmemory``
        and ``dq_check_inmemory`` steps. If EITHER gate returned a
        non-PASS/WARN status AND the tenant has
        ``compliance_fail_closed_enabled=True``, the workflow refuses
        to persist the Asset row and emits the
        ``ASSET_FAIL_CLOSED_REJECTED`` audit event. The caller (the
        engine) maps the raised :class:`FailClosedRejection` into a
        workflow-level FAILED status; the data-first endpoint
        translates that into HTTP 4xx for the client.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with asset_id
        """
        _check_workflow_deadline(instance)
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        key = input_data.get("key")
        name = input_data.get("name")
        description = input_data.get("description")
        domain = input_data.get("domain")
        visibility = input_data.get("visibility", AssetVisibility.INTERNAL)
        created_by_id = input_data.get("created_by_id") or instance.created_by_id

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not key:
            raise ValueError("key is required")
        if not name:
            raise ValueError("name is required")

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None

        # ---- Phase 250.1.A.3 fail-closed-at-intake gate ----
        # The gate only kicks in for the data-first flow (file_id
        # set). Contract-first intake has nothing to scan and so
        # bypasses the gate entirely.
        #
        # Phase 250.1.C — the gate is a v2+ feature. v1 in-flight
        # runs predate the in-memory gates and have no
        # ``compliance_inmemory_status`` / ``dq_inmemory_status``
        # state; subjecting them to the gate would retroactively
        # reject runs whose tenant flipped fail-closed ON during
        # the soak window. We therefore guard the gate on the
        # workflow_version pinned at instance create-time.
        file_id_present = bool(
            input_data.get("file_id") or instance.state_data.get("file_id")
        )
        fail_closed_on = bool(getattr(
            tenant, "compliance_fail_closed_enabled", False
        ))
        instance_version = instance.workflow_version or "1.0.0"
        try:
            from hub.apps.orchestration.versioning import (
                WorkflowVersionManager,
            )
            gate_runs_on_this_version = (
                WorkflowVersionManager.compare_versions(
                    instance_version, "2.0.0"
                ) >= 0
            )
        except Exception:
            # Defensive fallback — non-semver versions count as v1.
            gate_runs_on_this_version = False

        if file_id_present and fail_closed_on and gate_runs_on_this_version:
            comp_status = (instance.state_data or {}).get(
                "compliance_inmemory_status"
            )
            dq_status = (instance.state_data or {}).get(
                "dq_inmemory_status"
            )
            comp_run_id = (instance.state_data or {}).get(
                "compliance_inmemory_run_id"
            )
            dq_run_id = (instance.state_data or {}).get("dq_inmemory_run_id")

            failing_gate: Optional[str] = None
            failing_status: Optional[str] = None
            if comp_status not in _GATE_PASS_STATUSES:
                failing_gate = "compliance"
                failing_status = comp_status or "UNKNOWN"
            elif dq_status not in _GATE_PASS_STATUSES:
                failing_gate = "dq"
                failing_status = dq_status or "UNKNOWN"

            if failing_gate is not None:
                # Audit emission is deferred to
                # :meth:`AssetCreationWorkflow.execute` (after the
                # engine atomic commits). Emitting here would write
                # the row inside the engine's per-step savepoint —
                # which is rolled back on exception, eating the
                # audit row. The typed exception below carries the
                # full rejection payload via JSON in str(); the
                # ``execute`` post-processor reconstructs it and
                # emits the audit event durably.
                raise FailClosedRejection(
                    gate=failing_gate,
                    gate_status=failing_status or "UNKNOWN",
                    reason=(
                        f"{failing_gate} gate returned "
                        f"{failing_status or 'UNKNOWN'} (tenant "
                        "fail-closed enabled)"
                    ),
                    compliance_run_id=str(comp_run_id) if comp_run_id else None,
                    dq_run_id=str(dq_run_id) if dq_run_id else None,
                )

        # Check if key already exists for tenant
        if Asset.objects.filter(tenant=tenant, key=key).exists():
            raise ValueError(f'Asset with key "{key}" already exists for this tenant')

        # Validate required fields before creation
        if not key or not name:
            raise ValueError("Asset key and name are required")

        # Carry the in-memory pre-persistence gate decisions through to
        # the persisted Asset row so the downstream ``activate_asset``
        # step's ``Asset.can_activate`` check (which requires
        # ``dq_status``/``compliance_status`` in {PASS, WARN} when a
        # dataset is present — assets/models.py:578-590) sees the same
        # signal that the pre-persistence gates already evaluated.
        #
        # Without this, ``compliance_check_inmemory`` and
        # ``dq_check_inmemory`` write only into ``state_data`` (a
        # workflow-local dict) and the Asset row inherits the model
        # defaults of UNKNOWN — which blocks activation even when both
        # gates returned PASS, leaving auto-activate workflows stuck in
        # DRAFT and the ``asset.activated`` webhook silent.
        comp_inmemory = (instance.state_data or {}).get("compliance_inmemory_status")
        dq_inmemory = (instance.state_data or {}).get("dq_inmemory_status")
        compliance_status_seed = (
            ComplianceStatus(comp_inmemory)
            if comp_inmemory in {v.value for v in ComplianceStatus}
            else ComplianceStatus.UNKNOWN
        )
        dq_status_seed = (
            DQStatus(dq_inmemory)
            if dq_inmemory in {v.value for v in DQStatus}
            else DQStatus.UNKNOWN
        )

        # Create asset
        with transaction.atomic():
            asset = Asset.objects.create(
                tenant=tenant,
                key=key,
                name=name,
                description=description,
                domain=domain,
                status=AssetStatus.DRAFT,
                visibility=visibility,
                created_by=created_by,
                dq_status=dq_status_seed,
                compliance_status=compliance_status_seed,
            )

        # Validate created asset using AssetsBusinessRules
        assets_rules = AssetsBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(created_by_id) if created_by_id else None
        )

        asset_validation_result = assets_rules.validate(
            asset=asset,
            tenant=tenant,
            user=created_by,
            validation_type="all"
        )

        if not asset_validation_result.is_valid:
            error_messages = asset_validation_result.errors
            # Log errors but don't fail - asset is already created
            logger.warning(
                "Asset validation warnings after creation",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=asset_validation_result.warnings,
                errors=error_messages,
            )
            AssetCreationWorkflow._append_result_summary_warnings(
                instance=instance,
                step_name="create_asset_record",
                message="Asset validation warnings after creation",
                warnings_payload=asset_validation_result.warnings,
            )
        elif asset_validation_result.warnings:
            logger.warning(
                "Asset validation warnings",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=asset_validation_result.warnings,
            )
            AssetCreationWorkflow._append_result_summary_warnings(
                instance=instance,
                step_name="create_asset_record",
                message="Asset validation warnings",
                warnings_payload=asset_validation_result.warnings,
            )

        # Store asset_id in state_data for subsequent steps
        instance.state_data["asset_id"] = str(asset.id)
        instance.save(update_fields=['state_data'])

        # Phase 250.1.G.3 — fire ``asset.created`` webhook event on
        # the FIRST commit that persists the Asset row. The publish
        # is deferred via ``transaction.on_commit`` so subscribers
        # only see assets that survive the workflow's outer atomic
        # (a fail-closed rejection or downstream rollback eats the
        # callback registration along with the asset row, so no
        # ghost events leak — see B2-6 contract).
        AssetCreationWorkflow._enqueue_asset_event(
            event="asset.created",
            asset=asset,
            tenant=tenant,
            user_id=created_by_id,
            data_extra={
                "name": asset.name,
                "domain": asset.domain or None,
                "status": asset.status,
                # ``contract_id`` is optionally attached by the
                # downstream attach_contract step; we read whatever
                # is in state_data at on_commit time so a v1 (post-
                # asset gates) instance still carries the contract
                # link if it was set.
                "contract_id": (instance.state_data or {}).get(
                    "contract_id"
                ),
            },
        )

        logger.info(
            "Asset record created",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            key=key,
            name=name
        )

        return {
            "asset_id": str(asset.id),
            "status": asset.status,
            "key": asset.key
        }

    @staticmethod
    def _enqueue_asset_event(
        *,
        event: str,
        asset: "Asset",
        tenant,
        user_id: Optional[str],
        data_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Schedule an ``asset.*`` event publish for the next commit.

        Phase 250.1.G — webhook event ordering contract. Events are
        deferred via ``transaction.on_commit`` so they fire in
        registration order AFTER the workflow's outer atomic
        commits — never on a row that was rolled back by the saga.

        ``event`` is one of the strings registered in
        :mod:`hub.apps.core.events.event_types` (``asset.created``,
        ``asset.updated``, ``asset.activated``, ``asset.published``,
        ``asset.retired``). ``asset`` MUST be a persisted model
        instance (the publish reads ``asset.id``); ``data_extra``
        carries the per-event-type payload fields beyond the common
        ``asset_id``.

        Failures of the publish are swallowed at the EventPublisher
        layer (logs `event_publish_failed`); we never want a
        webhook outage to fail the asset-creation workflow.
        """
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="asset_service",
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user_id) if user_id else None,
        )
        payload: Dict[str, Any] = {"asset_id": str(asset.id)}
        if data_extra:
            payload.update({k: v for k, v in data_extra.items() if v is not None})

        def _publish() -> None:
            try:
                publisher.publish(event_type=event, data=payload)
            except Exception as exc:  # noqa: BLE001 — webhook is best-effort
                logger.warning(
                    "asset_webhook_publish_failed",
                    event_type=event,
                    asset_id=str(asset.id),
                    error=str(exc),
                )

        transaction.on_commit(_publish)

    @staticmethod
    @transaction.atomic
    def _create_dataset_from_file_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create dataset from file and link to asset (Data-First flow step 9).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with dataset_id
        """
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.datasets.schema_inference import (
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet
        )
        from hub.apps.files.storage import S3StorageClient

        asset_id = instance.state_data.get("asset_id")
        file_id = instance.state_data.get("file_id") or input_data.get("file_id")
        file_format = instance.state_data.get("file_format") or input_data.get("file_format")
        schema_json = instance.state_data.get("schema_json")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not file_id:
            raise ValueError("file_id is required for dataset creation")

        asset = Asset.objects.get(id=asset_id)
        file_obj = File.objects.get(id=file_id, tenant=asset.tenant)

        # Determine file format if not provided
        if not file_format:
            format_map = {
                'text/csv': 'CSV',
                'application/csv': 'CSV',
                'application/json': 'JSON',
                'text/json': 'JSON',
                'application/parquet': 'PARQUET',
                'application/x-parquet': 'PARQUET',
            }
            file_format = format_map.get(file_obj.content_type, 'CSV')

            # Infer from filename if still not determined
            if file_format == 'CSV' and file_obj.name:
                filename_lower = file_obj.name.lower()
                if filename_lower.endswith('.json') or filename_lower.endswith('.ndjson'):
                    file_format = 'JSON'
                elif filename_lower.endswith('.parquet'):
                    file_format = 'PARQUET'

        # Infer schema if not already inferred
        if not schema_json:
            storage_client = S3StorageClient()
            try:
                file_content = storage_client.get_file_content(file_obj.storage_path)
            except Exception as e:
                logger.error(
                    "Failed to download file for schema inference",
                    workflow_instance_id=str(instance.id),
                    file_id=str(file_id),
                    error=str(e)
                )
                raise ValueError(f"Failed to download file: {str(e)}")

            # Infer schema based on format
            try:
                if file_format.upper() == 'CSV':
                    schema_json = infer_schema_from_csv(file_content)
                elif file_format.upper() == 'JSON':
                    schema_json = infer_schema_from_json(file_content)
                elif file_format.upper() == 'PARQUET':
                    schema_json = infer_schema_from_parquet(file_content)
                else:
                    schema_json = {"fields": []}
            except Exception as e:
                logger.warning(
                    "Schema inference failed, creating dataset without schema",
                    workflow_instance_id=str(instance.id),
                    file_id=str(file_id),
                    error=str(e)
                )
                schema_json = {"fields": []}

        # Get next version for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        next_version = latest_dataset.version + 1 if latest_dataset else 1

        # Create dataset
        user_id = instance.created_by_id or input_data.get("created_by_id")
        from hub.apps.users.models import User
        created_by = User.objects.get(id=user_id) if user_id else None

        dataset = Dataset.objects.create(
            tenant=asset.tenant,
            asset=asset,
            file=file_obj,
            version=next_version,
            format=file_format,
            is_current=True,
            created_by=created_by,
            schema_json=schema_json
        )

        # Store dataset_id in state_data
        instance.state_data["dataset_id"] = str(dataset.id)
        instance.save(update_fields=['state_data'])

        logger.info(
            "Dataset created from file",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            dataset_id=str(dataset.id),
            file_id=str(file_id),
            version=next_version
        )

        return {
            "dataset_id": str(dataset.id),
            "dataset_version": next_version,
            "file_id": str(file_id)
        }

    @staticmethod
    def _attach_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Attach contract to asset.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with contract_id
        """
        asset_id = instance.state_data.get("asset_id")
        # Get contract_id from state_data (for data-first flow) or input_data (for contract-first flow)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not contract_id:
            # Skip if contract_id not provided
            logger.info(
                "Skipping contract attachment: contract_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "contract_id not provided"}

        from hub.apps.contracts.models import Contract, ContractStatus

        asset = Asset.objects.get(id=asset_id)
        contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)

        # Attach contract to asset
        contract.asset = asset

        # Get next version for asset
        latest_contract = asset.contracts.order_by('-version').first()
        if latest_contract:
            contract.version = latest_contract.version + 1
        else:
            contract.version = 1

        # Promote DRAFT -> ACTIVE when both validation and normalization
        # already passed earlier in the workflow. Doing it HERE rather
        # than in ``_validate_contract_task`` is load-bearing: the
        # ``validate_contract`` DSL step's ``if`` predicate skips it
        # whenever ``contract_validation_status == 'VALID'``
        # (DSL: ``contract_id != null && contract_validation_status != 'VALID'``),
        # which is exactly the happy-path the data-first flow takes.
        # Without this promotion, the contract stays DRAFT forever and
        # ``Asset.can_activate`` blocks downstream activation with
        # "Asset must have an ACTIVE contract" — silently dropping the
        # ``asset.activated`` webhook for every successful intake.
        validation_ok = contract.validation_status in ("VALID", "WARNING_ONLY")
        normalization_ok = contract.normalization_status in (
            "NORMALIZED_OK",
            "NORMALIZED_WITH_WARNINGS",
        )
        update_fields = ['asset', 'version']
        if (
            validation_ok
            and normalization_ok
            and contract.status == ContractStatus.DRAFT
        ):
            contract.status = ContractStatus.ACTIVE
            update_fields.append('status')
            logger.info(
                "Contract promoted DRAFT -> ACTIVE on attach",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                contract_id=str(contract.id),
                validation_status=contract.validation_status,
                normalization_status=contract.normalization_status,
            )

        contract.save(update_fields=update_fields)

        # Store contract_id and validation status in state_data
        instance.state_data["contract_id"] = str(contract.id)
        instance.state_data["contract_validation_status"] = contract.validation_status
        instance.state_data["contract_normalization_status"] = contract.normalization_status
        instance.save(update_fields=['state_data'])

        logger.info(
            "Contract attached to asset",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            contract_id=str(contract.id),
            contract_version=contract.version
        )

        return {
            "contract_id": str(contract.id),
            "contract_version": contract.version,
            "validation_status": contract.validation_status,
            "normalization_status": contract.normalization_status,
            "status": contract.status,
        }

    @staticmethod
    def _attach_dataset_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Attach dataset to asset.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with dataset_id
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = input_data.get("dataset_id")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping dataset attachment: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}

        from hub.apps.datasets.models import Dataset

        asset = Asset.objects.get(id=asset_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=asset.tenant)

        # Attach dataset to asset
        dataset.asset = asset

        # Get next version for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        if latest_dataset:
            dataset.version = latest_dataset.version + 1
        else:
            dataset.version = 1

        dataset.save(update_fields=['asset', 'version'])

        # Store dataset_id in state_data
        instance.state_data["dataset_id"] = str(dataset.id)
        instance.save(update_fields=['state_data'])

        logger.info(
            "Dataset attached to asset",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            dataset_id=str(dataset.id),
            dataset_version=dataset.version
        )

        return {
            "dataset_id": str(dataset.id),
            "dataset_version": dataset.version
        }

    # ------------------------------------------------------------------
    # Phase 250.2.B — schema-drift comparison
    # ------------------------------------------------------------------

    #: Number of field names retained in the audit-event payload per
    #: drift category. Matches the Phase 240.5.F audit-payload size
    #: cap so a 1000-field contract drift doesn't blow past the
    #: ``details_json`` size budget.
    _SCHEMA_DRIFT_AUDIT_FIELD_CAP: int = 20

    @staticmethod
    def _compare_schema_against_contract_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step,
    ) -> Dict[str, Any]:
        """Diff the contract's schema vs the dataset's inferred schema.

        Phase 250.2.B.2 — runs between ``attach_dataset`` and
        ``validate_contract`` (in both v1 and v2 DSLs). Reads the
        contract's ``hub_contract_json["schema"]`` and the dataset's
        ``schema_json``, runs
        :meth:`SchemaCompareService.compare`, and persists the
        result to ``state_data["schema_drift"]`` for the workflow's
        result_summary + frontend banner.

        Severity contract per D250.12 / 250.2.B.3:

        * ``NONE`` — clean diff; step returns silently with
          ``schema_drift.detected=False``.
        * ``WARN`` — drift exists but it's all compatible
          (``extra_fields`` only OR compatible-widening
          mismatches). Asset is allowed to persist; banner shows
          a yellow notice.
        * ``FAIL`` — ``structural_incompatibility=True`` (missing
          fields OR incompatible type mismatches). Asset is STILL
          allowed to persist (the gate doesn't block here — the
          severity is observability, not enforcement, per D250.12).
          Banner shows a red error.

        On any non-NONE severity, the task ALSO emits
        ``ASSET_SCHEMA_DRIFT_DETECTED`` audit event so audit-replay
        queries can find drift incidents without scraping
        result-summary state.
        """
        from hub.apps.audit import event_types as audit_event_types
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.services.schema_compare import (
            SchemaCompareService,
        )
        from hub.apps.datasets.models import Dataset

        dataset_id = instance.state_data.get("dataset_id") or input_data.get("dataset_id")
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")

        # Skip cleanly when the workflow lacks either input. The
        # condition guard in the DSL also enforces this, but
        # double-check at the task body so a direct unit-test
        # caller doesn't crash on missing IDs.
        if not dataset_id or not contract_id:
            logger.info(
                "Skipping schema-drift comparison: dataset_id or contract_id missing",
                workflow_instance_id=str(instance.id),
                dataset_id=dataset_id,
                contract_id=contract_id,
            )
            return {
                "schema_drift": {
                    "detected": False,
                    "severity": "NONE",
                    "skipped": True,
                    "skip_reason": "dataset_id or contract_id missing",
                }
            }

        try:
            contract = Contract.objects.get(id=contract_id)
            dataset = Dataset.objects.get(id=dataset_id)
        except (Contract.DoesNotExist, Dataset.DoesNotExist) as exc:
            logger.warning(
                "Schema-drift skipped: contract or dataset row not found",
                workflow_instance_id=str(instance.id),
                error=str(exc),
            )
            return {
                "schema_drift": {
                    "detected": False,
                    "severity": "NONE",
                    "skipped": True,
                    "skip_reason": "contract or dataset row missing",
                }
            }

        result = SchemaCompareService.compare(
            contract_schema=contract.hub_contract_json or {},
            inferred_schema=dataset.schema_json or {},
        )
        drift = result.to_dict()

        # Persist drift to state_data so downstream steps + the
        # API result_summary can reference it.
        instance.state_data["schema_drift"] = drift
        instance.save(update_fields=["state_data"])

        # Emit audit event for any non-NONE severity. The cap on
        # field-name list length keeps details_json bounded even
        # for very wide contracts.
        cap = AssetCreationWorkflow._SCHEMA_DRIFT_AUDIT_FIELD_CAP
        if drift["detected"]:
            # Explicit severity → AuditEvent.result mapping. Pinning
            # the table here (instead of an inline ternary) means a
            # future severity rubric extension (e.g. ``CRITICAL``)
            # can't silently fall through to ``"FAILURE"`` — the
            # KeyError raised below is loud enough to fail the
            # workflow at audit-write time and surface the gap to ops.
            # The valid AuditEvent.result choices are pinned at
            # ``hub/apps/audit/models.py`` (``SUCCESS`` / ``FAILURE``
            # / ``WARNING``) so the mapping table here is the single
            # source of truth for severity → audit result.
            _SEVERITY_TO_AUDIT_RESULT = {"WARN": "WARNING", "FAIL": "FAILURE"}
            try:
                audit_result_code = _SEVERITY_TO_AUDIT_RESULT[drift["severity"]]
            except KeyError:
                # Defence in depth: ``drift["detected"]==True`` should
                # have already excluded ``NONE``; landing here means
                # SchemaDriftResult.severity returned an unknown tier.
                logger.error(
                    "schema_drift_unknown_severity",
                    workflow_instance_id=str(instance.id),
                    severity=drift["severity"],
                )
                # Skip the audit; drift is already durably in state_data.
                audit_result_code = None

            if audit_result_code is not None:
                try:
                    create_audit_event(
                        resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                        action=audit_event_types.ASSET_SCHEMA_DRIFT_DETECTED,
                        actor_user=getattr(instance, "created_by", None),
                        tenant=getattr(instance, "tenant", None),
                        resource_id=instance.state_data.get("asset_id"),
                        result=audit_result_code,
                        details={
                            # ``tenant_id`` is duplicated into details_json
                            # despite the ``tenant=`` kwarg already setting
                            # the audit row's tenant FK. The duplication is
                            # deliberate: audit-replay queries that scan
                            # ``details_json`` for cross-tenant aggregation
                            # (e.g. drift-rate dashboards in the analytics
                            # warehouse where the FK isn't joined back to
                            # ``tenants``) rely on the JSON copy. Removing
                            # the duplicate would silently break those
                            # downstream readers.
                            "tenant_id": (
                                str(instance.tenant_id) if instance.tenant_id else None
                            ),
                            "asset_id": instance.state_data.get("asset_id"),
                            "contract_id": str(contract.id),
                            "dataset_id": str(dataset.id),
                            "workflow_instance_id": str(instance.id),
                            "severity": drift["severity"],
                            "missing_fields": drift["missing_fields"][:cap],
                            "extra_fields": drift["extra_fields"][:cap],
                            "type_mismatches": drift["type_mismatches"][:cap],
                            "structural_incompatibility": drift[
                                "structural_incompatibility"
                            ],
                        },
                    )
                except Exception as audit_exc:  # noqa: BLE001
                    # Audit emission is best-effort — a failure here
                    # MUST NOT block the workflow because the drift is
                    # already in state_data + result_summary.
                    logger.warning(
                        "schema_drift_audit_emit_failed",
                        workflow_instance_id=str(instance.id),
                        error=str(audit_exc),
                    )

        logger.info(
            "Schema-drift comparison complete",
            workflow_instance_id=str(instance.id),
            severity=drift["severity"],
            missing_count=len(drift["missing_fields"]),
            extra_count=len(drift["extra_fields"]),
            mismatch_count=len(drift["type_mismatches"]),
        )

        return {"schema_drift": drift}

    @staticmethod
    def _run_dq_checks_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Run data quality checks on asset dataset.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with dq_status
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = instance.state_data.get("dataset_id") or input_data.get("dataset_id")
        profile_key = input_data.get("profile_key", "intake_basic_gx")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping DQ checks: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}

        from hub.apps.orchestration.workflows.data_quality import DataQualityCheckWorkflow

        asset = Asset.objects.get(id=asset_id)

        # Trigger DQ check workflow
        try:
            dq_result = DataQualityCheckWorkflow.execute(
                tenant_id=str(asset.tenant.id),
                asset_id=str(asset.id),
                dataset_id=dataset_id,
                profile_key=profile_key,
                triggered_by_id=str(instance.created_by_id)
            )

            # Get DQ run result from workflow state
            workflow_instance_id = dq_result.get("workflow_instance_id")
            if workflow_instance_id:
                from hub.apps.orchestration.models import WorkflowInstance as DQWorkflowInstance
                dq_workflow_instance = DQWorkflowInstance.objects.get(id=workflow_instance_id)
                dq_run_id = dq_workflow_instance.state_data.get("dq_run_id")

                if dq_run_id:
                    from hub.apps.dq.models import DQRun
                    dq_run = DQRun.objects.get(id=dq_run_id)

                    # Update asset DQ status
                    if dq_run.overall_status == "PASS":
                        asset.dq_status = DQStatus.PASS
                    elif dq_run.overall_status == "WARN":
                        asset.dq_status = DQStatus.WARN
                    elif dq_run.overall_status == "FAIL":
                        asset.dq_status = DQStatus.FAIL
                    else:
                        asset.dq_status = DQStatus.UNKNOWN

                    asset.save(update_fields=['dq_status'])

                    # Store DQ status in state_data
                    instance.state_data["dq_status"] = asset.dq_status
                    instance.state_data["dq_run_id"] = str(dq_run.id)
                    instance.state_data["quality_score"] = dq_run.quality_score
                    instance.save(update_fields=['state_data'])

                    logger.info(
                        "DQ checks completed",
                        workflow_instance_id=str(instance.id),
                        asset_id=str(asset.id),
                        dq_status=asset.dq_status,
                        quality_score=dq_run.quality_score
                    )

                    return {
                        "dq_status": asset.dq_status,
                        "quality_score": dq_run.quality_score,
                        "dq_run_id": str(dq_run.id)
                    }
        except Exception as e:
            error_str = str(e)
            # When DQ service is unavailable (e.g. in tests without dq-service-test),
            # skip DQ checks instead of failing the workflow (matches scheduled_ingestion behavior)
            if "DQ service is unavailable" in error_str or "Connection refused" in error_str:
                logger.warning(
                    "DQ service unavailable, skipping DQ checks",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    error=error_str
                )
                asset.dq_status = DQStatus.UNKNOWN
                asset.save(update_fields=['dq_status'])
                instance.state_data["dq_status"] = asset.dq_status
                instance.save(update_fields=['state_data'])
                return {"skipped": True, "reason": "DQ service unavailable", "dq_status": asset.dq_status}
            logger.error(
                "Failed to run DQ checks",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=error_str
            )
            # Set DQ status to UNKNOWN on failure
            asset.dq_status = DQStatus.UNKNOWN
            asset.save(update_fields=['dq_status'])
            raise

        return {
            "dq_status": DQStatus.UNKNOWN,
            "quality_score": None
        }

    @staticmethod
    def _run_compliance_checks_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Run compliance checks on asset dataset.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with compliance_status
        """
        asset_id = instance.state_data.get("asset_id")
        dataset_id = instance.state_data.get("dataset_id") or input_data.get("dataset_id")
        scan_mode = input_data.get("scan_mode", "internal")
        applicable_regulations = input_data.get("applicable_regulations", [])

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not dataset_id:
            # Skip if dataset_id not provided (contract-first flow)
            logger.info(
                "Skipping compliance checks: dataset_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "dataset_id not provided"}

        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.jobs.utils import create_job
        from hub.apps.jobs.models import JobType

        asset = Asset.objects.get(id=asset_id)
        dataset = Dataset.objects.get(id=dataset_id, tenant=asset.tenant)

        if not dataset.file:
            raise ValueError("Dataset must have a file for compliance checks")

        # Create compliance run
        triggered_by_id = instance.created_by_id
        from hub.apps.users.models import User
        triggered_by = User.objects.get(id=triggered_by_id) if triggered_by_id else None

        job = create_job(
            tenant=asset.tenant,
            user=triggered_by,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(asset.id),
            details_json={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations
            }
        )

        compliance_run = ComplianceRun.objects.create(
            tenant=asset.tenant,
            asset=asset,
            dataset=dataset,
            file=dataset.file,
            job=job,
            regulations=applicable_regulations if applicable_regulations else [],
            status=ComplianceRunStatus.PENDING
        )

        # Execute compliance check
        try:
            from hub.apps.compliance.views import execute_compliance_run
            execute_compliance_run(str(compliance_run.id))

            # Refresh compliance run
            compliance_run.refresh_from_db()

            # Update asset compliance status
            if compliance_run.overall_status == "PASS":
                asset.compliance_status = ComplianceStatus.PASS
            elif compliance_run.overall_status == "WARN":
                asset.compliance_status = ComplianceStatus.WARN
            elif compliance_run.overall_status == "FAIL":
                asset.compliance_status = ComplianceStatus.FAIL
            else:
                asset.compliance_status = ComplianceStatus.UNKNOWN

            asset.save(update_fields=['compliance_status'])

            # Store compliance status in state_data
            instance.state_data["compliance_status"] = asset.compliance_status
            instance.state_data["compliance_run_id"] = str(compliance_run.id)
            instance.save(update_fields=['state_data'])

            logger.info(
                "Compliance checks completed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                compliance_status=asset.compliance_status,
                risk_level=compliance_run.risk_level
            )

            return {
                "compliance_status": asset.compliance_status,
                "risk_level": compliance_run.risk_level,
                "compliance_run_id": str(compliance_run.id)
            }
        except Exception as e:
            logger.error(
                "Failed to run compliance checks",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Set compliance status to UNKNOWN on failure
            asset.compliance_status = ComplianceStatus.UNKNOWN
            asset.save(update_fields=['compliance_status'])
            raise

    @staticmethod
    def _validate_contract_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate contract if not already validated.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation_status
        """
        asset_id = instance.state_data.get("asset_id")
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        contract_validation_status = instance.state_data.get("contract_validation_status")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not contract_id:
            # Skip if contract_id not provided (data-first flow)
            logger.info(
                "Skipping contract validation: contract_id not provided",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {"skipped": True, "reason": "contract_id not provided"}

        from hub.apps.contracts.models import Contract, ContractStatus

        asset = Asset.objects.get(id=asset_id)
        contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)

        # Promotion gate (Phase 250.1.G.3): a DRAFT contract whose
        # validation + normalization both succeeded earlier in the
        # data-first flow should be promoted to ACTIVE here so the
        # downstream ``activate_asset`` step's ``can_activate`` check
        # (which filters ``contracts(status=ACTIVE)``) sees it. Without
        # this promotion the workflow would silently land in DRAFT and
        # the asset.activated webhook would never fire.
        already_validated = contract.validation_status in ("VALID", "WARNING_ONLY")
        normalization_ok = contract.normalization_status in (
            "NORMALIZED_OK",
            "NORMALIZED_WITH_WARNINGS",
        )
        if (
            already_validated
            and normalization_ok
            and contract.status == ContractStatus.DRAFT
        ):
            contract.status = ContractStatus.ACTIVE
            contract.save(update_fields=["status"])
            logger.info(
                "Contract promoted DRAFT -> ACTIVE",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                contract_id=str(contract.id),
                validation_status=contract.validation_status,
                normalization_status=contract.normalization_status,
            )

        # Idempotent short-circuit: already-validated contract
        if already_validated:
            instance.state_data["contract_validation_status"] = contract.validation_status
            instance.save(update_fields=["state_data"])
            logger.info(
                "Contract already validated",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                contract_id=str(contract.id),
                validation_status=contract.validation_status,
            )
            return {
                "validation_status": contract.validation_status,
                "already_validated": True,
            }

        # No prior validation result on the row — a future revision will
        # delegate to ContractCreationWorkflow.validate_contract here.
        # For now, surface what we know without falsifying state.
        instance.state_data["contract_validation_status"] = contract.validation_status
        instance.save(update_fields=['state_data'])

        logger.info(
            "Contract validation checked",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            contract_id=str(contract.id),
            validation_status=contract.validation_status
        )

        return {
            "validation_status": contract.validation_status,
            "already_validated": False
        }

    @staticmethod
    @transaction.atomic
    def _link_odps_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Link ODPS contract (optional step for marketplace).

        Supports three modes:
        1. upload: Parse and validate uploaded ODPS, create ODPS contract, link it
        2. generate: Generate ODPS from HubContract, create ODPS contract, link it
        3. link: Link to existing ODPS contract by ID

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ODPS contract ID and linking results
        """
        from hub.apps.contracts.odps_parser import ODPSParser
        from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
        from hub.apps.contracts.linking_validation import validate_linking
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
        from hub.apps.contracts.normalization import parse_contract
        from hub.apps.contracts.odps_version_detection import detect_odps_version
        from django.contrib.auth import get_user_model
        import json

        User = get_user_model()

        # Get asset_id from state_data
        asset_id = instance.state_data.get("asset_id")
        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")

        asset = Asset.objects.get(id=asset_id)
        tenant_id = str(asset.tenant_id)
        user_id = instance.created_by_id or input_data.get("created_by_id")
        user = User.objects.get(id=user_id) if user_id else None

        # Get ODPS action from input_data
        odps_action = input_data.get("odps_action")
        if not odps_action or odps_action not in ["upload", "generate", "link"]:
            # Skip if no ODPS action specified
            logger.info(
                "ODPS linking skipped (no action specified)",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "odps_linking_skipped": True,
                "reason": "No ODPS action specified"
            }

        # Get contract_id from state_data if available (for data-first flow)
        # Also check if contract is already attached to asset (for contract-first flow)
        contract_id = instance.state_data.get("contract_id") or input_data.get("contract_id")
        contract = None

        # First, try to get contract from contract_id
        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)
            except Contract.DoesNotExist:
                logger.warning(
                    "Contract not found for ODPS linking",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )

        # If no contract found by ID, try to get from asset's contracts
        if not contract:
            # Try to get ODCS contract from asset (for data-first flow where contract was just created)
            odcs_contract = asset.contracts.filter(
                original_spec_type=OriginalSpecType.ODCS
            ).order_by('-version').first()
            if odcs_contract:
                contract = odcs_contract
                contract_id = str(contract.id)
                logger.info(
                    "Using ODCS contract from asset for ODPS linking",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    contract_id=contract_id
                )

        odps_contract = None
        odps_contract_id = None

        try:
            if odps_action == "upload":
                # Parse and validate uploaded ODPS
                odps_raw = input_data.get("odps_raw")
                odps_format = input_data.get("odps_format", "JSON")

                if not odps_raw:
                    raise ValueError("odps_raw is required for ODPS upload")

                # Parse ODPS
                odps_doc = ODPSParser.parse(odps_raw, format=odps_format.lower())

                # Detect version
                odps_version = detect_odps_version(odps_doc) or "4.1"

                # Validate ODPS
                is_valid, validation_errors = ODPSParser.validate(odps_doc, version=odps_version)
                if not is_valid:
                    raise ValueError(f"ODPS validation failed: {validation_errors}")

                # Normalize ODPS to HubContract
                from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
                normalizer = ODPSNormalizer()
                normalize_result = normalizer.normalize(contract_data=odps_doc, spec_version=odps_version)
                hub_contract_from_odps = normalize_result.hub_contract

                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                next_version = latest_contract.version + 1 if latest_contract else 1

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=asset.tenant,
                    asset=asset,
                    version=next_version,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version=odps_version,
                    original_format=OriginalFormat.JSON if odps_format.upper() == "JSON" else OriginalFormat.YAML,
                    original_raw=odps_raw,
                    hub_contract_version="1.0.0",
                    hub_contract_json=hub_contract_from_odps,
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=[],
                    created_by=user
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract created from upload",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            elif odps_action == "generate":
                # Generate ODPS from HubContract
                if not contract:
                    raise ValueError("No contract available. Cannot generate ODPS from HubContract.")
                if not contract.hub_contract_json:
                    raise ValueError("Contract has no hub_contract_json. Cannot generate ODPS.")

                # Get original ODCS contract if available (for embedding in ODPS)
                original_odcs_contract = None
                if contract.original_raw and contract.original_spec_type == OriginalSpecType.ODCS:
                    try:
                        original_odcs_contract = parse_contract(
                            contract.original_raw, contract.original_format
                        )
                    except Exception:
                        # If parsing fails, continue without original ODCS
                        pass

                # Generate ODPS document
                odps_doc = generate_odps_from_hubcontract(
                    hub_contract=contract.hub_contract_json,
                    target_version="4.1",
                    original_odcs_contract=original_odcs_contract,
                    original_odcs_url=None,
                )

                # Format as JSON for storage
                odps_raw = json.dumps(odps_doc, indent=2)

                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                next_version = latest_contract.version + 1 if latest_contract else 1

                # Create ODPS contract record
                odps_contract = Contract.objects.create(
                    tenant=asset.tenant,
                    asset=asset,
                    version=next_version,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version="4.1",
                    original_format=OriginalFormat.JSON,
                    original_raw=odps_raw,
                    hub_contract_version="1.0.0",
                    hub_contract_json=contract.hub_contract_json,  # Use same HubContract
                    normalization_status=NormalizationStatus.NORMALIZED_OK,
                    normalization_errors=[],
                    normalization_warnings=[],
                    created_by=user
                )
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract generated from HubContract",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            elif odps_action == "link":
                # Link to existing ODPS contract
                existing_odps_contract_id = input_data.get("odps_contract_id")
                if not existing_odps_contract_id:
                    raise ValueError("odps_contract_id is required for ODPS linking")

                # Get existing ODPS contract
                try:
                    existing_odps_contract = Contract.objects.get(
                        id=existing_odps_contract_id,
                        tenant=asset.tenant,
                        original_spec_type=OriginalSpecType.ODPS
                    )
                except Contract.DoesNotExist:
                    raise ValueError(f"ODPS contract {existing_odps_contract_id} not found or not an ODPS contract")

                # If there's an ODCS contract, validate linking
                if contract:
                    validate_linking(
                        odps_contract_id=existing_odps_contract_id,
                        odcs_contract_id=str(contract.id),
                        tenant_id=tenant_id
                    )

                # Attach ODPS contract to asset
                existing_odps_contract.asset = asset
                # Get next version for asset
                latest_contract = asset.contracts.order_by('-version').first()
                if latest_contract:
                    existing_odps_contract.version = latest_contract.version + 1
                else:
                    existing_odps_contract.version = 1
                existing_odps_contract.save(update_fields=['asset', 'version'])

                odps_contract = existing_odps_contract
                odps_contract_id = str(odps_contract.id)

                logger.info(
                    "ODPS contract validated for linking",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    odps_contract_id=odps_contract_id
                )

            # Establish bidirectional link if both ODPS and ODCS contracts exist
            if odps_contract and contract:
                # ODPS → ODCS: Store in ODPS contract's hub_contract_json.extensions.x_odps.odcs_link
                if odps_contract.hub_contract_json:
                    if "extensions" not in odps_contract.hub_contract_json:
                        odps_contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in odps_contract.hub_contract_json["extensions"]:
                        odps_contract.hub_contract_json["extensions"]["x_odps"] = {}
                    odps_contract.hub_contract_json["extensions"]["x_odps"]["odcs_link"] = str(contract.id)
                    odps_contract.save(update_fields=["hub_contract_json"])

                # ODCS → ODPS: Store in ODCS contract's hub_contract_json.extensions.x_odps.odps_link
                if contract.hub_contract_json:
                    if "extensions" not in contract.hub_contract_json:
                        contract.hub_contract_json["extensions"] = {}
                    if "x_odps" not in contract.hub_contract_json["extensions"]:
                        contract.hub_contract_json["extensions"]["x_odps"] = {}
                    contract.hub_contract_json["extensions"]["x_odps"]["odps_link"] = odps_contract_id
                    contract.save(update_fields=["hub_contract_json"])

                logger.info(
                    "ODPS-ODCS contracts linked bidirectionally",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    contract_id=str(contract.id),
                    odps_contract_id=odps_contract_id,
                    action=odps_action
                )

            # Publish ODPS events
            from hub.apps.core.events.service_publishers import ODPSEventPublisher
            # Create ODPSEventPublisher instance with tenant_id and user_id
            # ODPSEventPublisher uses getattr to get tenant_id and user_id in __init__
            class TempODPSEventPublisher(ODPSEventPublisher):
                pass

            odps_event_publisher = TempODPSEventPublisher()
            odps_event_publisher.tenant_id = tenant_id
            odps_event_publisher.user_id = str(user_id) if user_id else None
            # Re-initialize _event_publisher with correct tenant/user
            from hub.apps.core.events.publisher import EventPublisher
            odps_event_publisher._event_publisher = EventPublisher(
                service_name="contract_service",
                tenant_id=tenant_id,
                user_id=str(user_id) if user_id else None,
            )

            # Publish ODPS created event (if this is a new contract from upload or generate)
            if odps_contract and odps_contract_id and odps_action in ["upload", "generate"]:
                # Get original_format as string
                original_format_str = None
                if odps_contract.original_format:
                    if hasattr(odps_contract.original_format, 'value'):
                        original_format_str = odps_contract.original_format.value
                    elif isinstance(odps_contract.original_format, str):
                        original_format_str = odps_contract.original_format
                    else:
                        original_format_str = str(odps_contract.original_format)

                odps_event_publisher.publish_odps_created(
                    contract_id=odps_contract_id,
                    asset_id=str(asset.id),
                    status=odps_contract.status,
                    odps_version=odps_contract.original_spec_version,
                    original_format=original_format_str
                )

            # Publish ODPS linked event (if both contracts exist)
            if odps_contract and odps_contract_id and contract:
                odps_event_publisher.publish_odps_linked(
                    odps_contract_id=odps_contract_id,
                    odcs_contract_id=str(contract.id),
                    link_type="bidirectional"
                )

            # Store ODPS contract ID and action in state_data for compensation
            instance.state_data["odps_contract_id"] = odps_contract_id
            instance.state_data["odps_action"] = odps_action
            if contract:
                instance.state_data["contract_id"] = str(contract.id)
            instance.save(update_fields=['state_data'])

            return {
                "odps_linked": True,
                "odps_contract_id": odps_contract_id,
                "action": odps_action,
                "state": {
                    "odps_contract_id": odps_contract_id
                }
            }

        except Exception as e:
            logger.error(
                "ODPS linking failed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                action=odps_action,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"ODPS linking failed: {str(e)}")

    @staticmethod
    @transaction.atomic
    def _rollback_odps_linking_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback ODPS linking (remove links and delete created ODPS contract if needed).

        This compensation task is called when a subsequent step fails and the workflow
        needs to rollback the ODPS linking operation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        from hub.apps.contracts.models import Contract

        # Get ODPS linking information from state_data
        contract_id = instance.state_data.get("contract_id")
        odps_contract_id = instance.state_data.get("odps_contract_id")
        odps_action = instance.state_data.get("odps_action")

        # Remove ODPS link from ODCS contract
        if contract_id:
            try:
                contract = Contract.objects.get(id=contract_id)
                # Remove ODPS link from contract
                if contract.hub_contract_json and "extensions" in contract.hub_contract_json:
                    x_odps = contract.hub_contract_json["extensions"].get("x_odps", {})
                    if "odps_link" in x_odps:
                        del x_odps["odps_link"]
                        contract.save(update_fields=["hub_contract_json"])
                        logger.info(
                            "ODPS link removed from ODCS contract during rollback",
                            workflow_instance_id=str(instance.id),
                            contract_id=contract_id
                        )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODCS contract not found during ODPS linking rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=contract_id
                )

        # Remove ODCS link from ODPS contract and delete if created during workflow
        if odps_contract_id:
            try:
                odps_contract = Contract.objects.get(id=odps_contract_id)
                # Remove ODCS link from ODPS contract
                if odps_contract.hub_contract_json and "extensions" in odps_contract.hub_contract_json:
                    x_odps = odps_contract.hub_contract_json["extensions"].get("x_odps", {})
                    if "odcs_link" in x_odps:
                        del x_odps["odcs_link"]
                        odps_contract.save(update_fields=["hub_contract_json"])

                # If ODPS contract was created during this workflow (upload or generate), delete it
                if odps_action in ["upload", "generate"]:
                    odps_contract.delete()
                    logger.info(
                        "ODPS contract rolled back (deleted)",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id
                    )
                else:
                    # For "link" action, just remove the link but keep the contract
                    logger.info(
                        "ODPS link removed from existing ODPS contract during rollback",
                        workflow_instance_id=str(instance.id),
                        odps_contract_id=odps_contract_id
                    )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODPS contract not found during rollback",
                    workflow_instance_id=str(instance.id),
                    odps_contract_id=odps_contract_id
                )

        logger.info(
            "ODPS linking rolled back",
            workflow_instance_id=str(instance.id),
            contract_id=contract_id,
            odps_contract_id=odps_contract_id,
            odps_action=odps_action
        )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _activate_asset_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Activate asset if all checks pass.

        Phase 250.1.A.6 / B2-2 — the activation lock takes
        ``SELECT FOR UPDATE`` on the Asset row inside an
        ``@transaction.atomic`` block so two concurrent activation
        requests serialise rather than racing on the version counter.
        We deliberately use SELECT FOR UPDATE rather than the heavier
        SERIALIZABLE isolation because:

        * The narrow critical section is a single row + version
          increment — row locking is sufficient.
        * SERIALIZABLE retries on the whole transaction; row locking
          blocks the loser until the winner commits, then re-reads
          fresh state. That maps cleanly onto the can_activate() +
          version-bump pattern below without a retry loop.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with activation status
        """
        _check_workflow_deadline(instance)
        asset_id = instance.state_data.get("asset_id")
        # Phase 250.1.A.3 / D250.2 — auto_activate now defaults TRUE
        # in :meth:`AssetCreationWorkflow.execute`. We still honour an
        # explicit ``False`` here for callers that want a DRAFT-first
        # workflow (legacy contract-first API users).
        auto_activate = input_data.get("auto_activate", True)

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")

        if not auto_activate:
            # Skip activation if auto_activate is False
            logger.info(
                "Auto-activation disabled, skipping activation",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "activated": False,
                "reason": "auto_activate is False",
                "skipped": True
            }

        # Phase 250.1.A.6 — take a row-level lock on the Asset for
        # the activation critical section. Two concurrent activation
        # requests for the same asset will serialise here; the loser
        # re-reads fresh state and either skips (already ACTIVE) or
        # proceeds with the latest version number.
        asset = Asset.objects.select_for_update().get(id=asset_id)

        # Check if asset can be activated
        can_activate, blockers = asset.can_activate()
        if not can_activate:
            logger.warning(
                "Cannot activate asset: requirements not met",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                blockers=blockers
            )
            return {
                "activated": False,
                "reason": "activation requirements not met",
                "blockers": blockers
            }

        # Validate asset lifecycle transition using AssetsBusinessRules
        tenant_id = str(asset.tenant_id) if asset.tenant_id else None
        user_id = str(instance.created_by_id) if instance.created_by_id else None

        assets_rules = AssetsBusinessRules(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Validate status transition
        old_status = asset.status
        new_status = AssetStatus.ACTIVE

        lifecycle_validation_result = assets_rules.validate(
            asset=asset,
            tenant=asset.tenant,
            user=instance.created_by,
            validation_type="lifecycle",
            old_status=old_status,
            new_status=new_status
        )

        if not lifecycle_validation_result.is_valid:
            error_messages = lifecycle_validation_result.errors
            raise ValueError(
                f"Asset activation validation failed: {'; '.join(error_messages)}"
            )

        # Log validation warnings if any
        if lifecycle_validation_result.warnings:
            logger.warning(
                "Asset activation validation warnings",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                warnings=lifecycle_validation_result.warnings,
            )
            AssetCreationWorkflow._append_result_summary_warnings(
                instance=instance,
                step_name="activate_asset",
                message="Asset activation validation warnings",
                warnings_payload=lifecycle_validation_result.warnings,
            )

        # Activate asset
        asset.status = AssetStatus.ACTIVE
        asset.increment_version()
        asset.save(update_fields=['status', 'version', 'updated_at'])

        # Phase 250.1.G.3 — fire ``asset.activated`` webhook event
        # on commit. The payload carries the dq + compliance status
        # snapshot taken AT activation time so subscribers don't
        # have to re-query — and so the webhook record matches the
        # exact gate signal that authorised the activation, even if
        # those statuses change later (e.g., a follow-up DQ run
        # demotes the asset).
        AssetCreationWorkflow._enqueue_asset_event(
            event="asset.activated",
            asset=asset,
            tenant=asset.tenant,
            user_id=instance.created_by_id,
            data_extra={
                "activation_reason": "auto_gate_pass",
                "dq_status": getattr(asset, "dq_status", None),
                "compliance_status": getattr(
                    asset, "compliance_status", None
                ),
            },
        )

        # Trigger semantic mapping.
        #
        # Phase 250.7.A.2 (closes Gap 15) — graceful degrade per
        # D250.6: failure here MUST NOT roll back the activation
        # (the asset is already ACTIVE in the DB at this point).
        # We mark ``semantic_status=FAIL`` and emit
        # ``ASSET_SEMANTIC_DEGRADED`` so the SPA can render the
        # inline degradation banner with a retry CTA.
        previous_semantic_status_for_map = asset.semantic_status
        try:
            map_asset_to_semantic(asset, tenant=asset.tenant)
        except Exception as e:
            logger.warning(
                "Semantic mapping failed for asset",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Don't fail activation if semantic mapping fails — this
            # is the load-bearing graceful-degrade contract.
            asset.semantic_status = "FAIL"
            asset.save(update_fields=["semantic_status", "updated_at"])
            try:
                create_audit_event(
                    resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                    action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
                    actor_user=getattr(instance, "created_by", None),
                    tenant=asset.tenant,
                    resource_id=str(asset.id),
                    result="WARNING",
                    details={
                        "tenant_id": (
                            str(instance.tenant_id) if instance.tenant_id else None
                        ),
                        "asset_id": str(asset.id),
                        "workflow_instance_id": str(instance.id),
                        "degraded_step": "activate_asset_semantic_map",
                        "error": str(e),
                        "previous_semantic_status": str(
                            previous_semantic_status_for_map
                        ),
                        "new_semantic_status": "FAIL",
                    },
                )
            except Exception as audit_exc:  # noqa: BLE001 — boundary
                logger.warning(
                    "asset_semantic_degraded_audit_emit_failed",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    error=str(audit_exc),
                )

        # Store activation status in state_data
        instance.state_data["asset_status"] = asset.status
        instance.state_data["activated"] = True
        instance.save(update_fields=['state_data'])

        logger.info(
            "Asset activated",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            old_status=old_status,
            new_status=asset.status
        )

        # Phase 250.2.A.3 (closes Gap 2) — emit ASSET_AUTO_ACTIVATED.
        # Fires only when the activation actually succeeded via the
        # auto-activate path (resolved=True AND can_activate=True).
        # The lifecycle-summary ASSET_ACTIVATED still fires later in
        # _audit_logging_task; this event specifically pins the
        # auto-activation decision so audit replay can answer
        # "why did this asset transition without a manual call?"
        # without re-reading tenant state.
        try:
            create_audit_event(
                resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                action=audit_event_types.ASSET_AUTO_ACTIVATED,
                actor_user=instance.created_by,
                tenant=asset.tenant,
                resource_id=str(asset.id),
                result="SUCCESS",
                details={
                    "tenant_id": str(asset.tenant_id),
                    "asset_id": str(asset.id),
                    "workflow_instance_id": str(instance.id),
                    "previous_status": str(old_status),
                    "new_status": str(asset.status),
                    "dq_status": str(getattr(asset, "dq_status", None)),
                    "compliance_status": str(
                        getattr(asset, "compliance_status", None)
                    ),
                    "caller_auto_activate": bool(
                        input_data.get("caller_auto_activate", auto_activate)
                    ),
                    "tenant_auto_activate": bool(
                        input_data.get("tenant_auto_activate", auto_activate)
                    ),
                    "resolved_auto_activate": True,
                },
            )
        except Exception as audit_exc:  # noqa: BLE001 — boundary
            # Audit emission is best-effort: a backend hiccup must
            # NOT roll back the activation. Mirrors the
            # ``cleanup_orphan_drafts`` and Phase 240 disciplines.
            logger.warning(
                "asset_auto_activated_audit_emit_failed",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(audit_exc),
            )

        return {
            "activated": True,
            "old_status": old_status,
            "new_status": asset.status
        }

    @staticmethod
    def _index_for_search_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """Index asset for search.

        Phase 250.7.A.2 (closes Gap 15) — graceful degrade contract
        per D250.6: when ``SearchIndexer.index_asset`` raises, the
        task does NOT propagate the exception (asset still
        activates). Instead it (a) flips ``Asset.semantic_status``
        to ``"FAIL"`` so the SPA can render the
        ``SemanticDegradedBanner`` inline, (b) emits the
        ``ASSET_SEMANTIC_DEGRADED`` audit row so audit-replay can
        find degradations without scanning workflow state, (c)
        returns ``{indexed: False, semantic_status: "FAIL"}`` so
        downstream steps can react.

        On success: flips ``semantic_status`` to ``"PASS"`` ONLY when
        the field is currently ``"UNKNOWN"``. The DSL runs the
        ``activate_asset`` step BEFORE ``index_for_search`` (see
        ``_DEFAULT_DSL`` ~line 447 / 640), and the activation's
        semantic-mapping wrapper sets ``"FAIL"`` if Fuseki is
        unreachable. An unconditional PASS write here would clobber
        that FAIL — masking a Fuseki outage on the SPA banner the
        moment OpenSearch is healthy. The FAIL ratchet is preserved:
        once any step downgrades semantic_status to FAIL, only an
        explicit retry (Phase 250.7.A.4 retry endpoint) may flip it
        back. Returns ``{indexed: True, semantic_status: <current>}``.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with ``search_index_id`` (on success),
            ``indexed`` bool, ``semantic_status`` ("PASS" / "FAIL").
        """
        asset_id = instance.state_data.get("asset_id")

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")

        asset = Asset.objects.get(id=asset_id)
        previous_semantic_status = asset.semantic_status

        try:
            search_index = SearchIndexer.index_asset(asset)

            logger.info(
                "Asset indexed for search",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                search_index_id=str(search_index.id)
            )

            # Mark PASS only if the field is still UNKNOWN. If a
            # prior step (activation's semantic-mapping wrapper)
            # already set FAIL because Fuseki was unreachable, leave
            # FAIL alone — overwriting it here would silently mask
            # the outage on the SPA banner. The two failure modes
            # (Fuseki / OpenSearch) are independent; FAIL is a
            # ratchet that only an explicit retry may release.
            if asset.semantic_status == "UNKNOWN":
                asset.semantic_status = "PASS"
                asset.save(update_fields=["semantic_status", "updated_at"])

            return {
                "search_index_id": str(search_index.id),
                "indexed": True,
                "semantic_status": asset.semantic_status,
            }
        except Exception as e:  # noqa: BLE001 — boundary
            logger.error(
                "Failed to index asset for search",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Phase 250.7.A.2 — degrade gracefully. Don't fail the
            # workflow; mark the asset's semantic_status FAIL and
            # emit the audit so downstream consumers can react.
            asset.semantic_status = "FAIL"
            asset.save(update_fields=["semantic_status", "updated_at"])

            try:
                create_audit_event(
                    resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                    action=audit_event_types.ASSET_SEMANTIC_DEGRADED,
                    actor_user=getattr(instance, "created_by", None),
                    tenant=getattr(instance, "tenant", None),
                    resource_id=str(asset.id),
                    result="WARNING",
                    details={
                        "tenant_id": (
                            str(instance.tenant_id) if instance.tenant_id else None
                        ),
                        "asset_id": str(asset.id),
                        "workflow_instance_id": str(instance.id),
                        "degraded_step": "index_for_search",
                        "error": str(e),
                        "previous_semantic_status": str(previous_semantic_status),
                        "new_semantic_status": "FAIL",
                    },
                )
            except Exception as audit_exc:  # noqa: BLE001 — boundary
                # Best-effort audit. The workflow already committed
                # the semantic_status flip; losing the audit row is
                # recoverable via DB diff (matches the
                # ``schema_drift_audit_emit_failed`` pattern from
                # Phase 250.2.B).
                logger.warning(
                    "asset_semantic_degraded_audit_emit_failed",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    error=str(audit_exc),
                )

            return {
                "indexed": False,
                "error": str(e),
                "semantic_status": "FAIL",
            }

    @staticmethod
    def _send_notifications_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Send notifications about asset creation/activation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with notification status
        """
        asset_id = instance.state_data.get("asset_id")
        send_notifications = input_data.get("send_notifications", True)

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")

        if not send_notifications:
            logger.info(
                "Notifications disabled, skipping",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset_id)
            )
            return {
                "notifications_sent": False,
                "reason": "send_notifications is False"
            }

        asset = Asset.objects.get(id=asset_id)
        activated = instance.state_data.get("activated", False)

        # Get creator email
        creator_email = None
        if asset.created_by and asset.created_by.email:
            creator_email = asset.created_by.email

        notifications_sent = []

        try:
            if creator_email:
                if activated:
                    subject = f"Asset '{asset.name}' Activated"
                    message = f"Your asset '{asset.name}' (key: {asset.key}) has been successfully activated."
                else:
                    subject = f"Asset '{asset.name}' Created"
                    message = f"Your asset '{asset.name}' (key: {asset.key}) has been created in DRAFT status."

                send_email_async(
                    email_type=EmailType.JOB_COMPLETION,
                    to_email=creator_email,
                    subject=subject,
                    template_name="job_completion",
                    context={"message": message, "asset_name": asset.name, "asset_key": asset.key},
                    tenant_id=str(asset.tenant.id)
                )
                notifications_sent.append(creator_email)

                logger.info(
                    "Notification sent to creator",
                    workflow_instance_id=str(instance.id),
                    asset_id=str(asset.id),
                    email=creator_email
                )
        except Exception as e:
            logger.error(
                "Failed to send notification",
                workflow_instance_id=str(instance.id),
                asset_id=str(asset.id),
                error=str(e)
            )
            # Don't fail workflow if notification fails

        return {
            "notifications_sent": len(notifications_sent) > 0,
            "recipients": notifications_sent
        }

    @staticmethod
    def _audit_logging_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Create audit log entry for asset creation/activation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit_event_id
        """
        asset_id = instance.state_data.get("asset_id")
        tenant_id = instance.tenant_id
        created_by_id = instance.created_by_id

        if not asset_id:
            raise ValueError("asset_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None
        asset = Asset.objects.get(id=asset_id)
        activated = instance.state_data.get("activated", False)

        action = "ASSET_ACTIVATED" if activated else "ASSET_CREATED"

        audit_event = create_audit_event(
            resource_type="ASSET",
            action=action,
            actor_user=created_by,
            tenant=tenant,
            resource_id=str(asset.id),
            details={
                "key": asset.key,
                "name": asset.name,
                "status": asset.status,
                "domain": asset.domain,
                "has_contract": asset.contracts.exists(),
                "has_dataset": asset.datasets.exists(),
                "dq_status": asset.dq_status,
                "compliance_status": asset.compliance_status,
                "workflow_instance_id": str(instance.id)
            }
        )

        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            asset_id=str(asset.id),
            audit_event_id=str(audit_event.id),
            action=action
        )

        result_summary = instance.state_data.get("result_summary") or {}
        summary_warnings = result_summary.get("warnings")
        if isinstance(summary_warnings, list) and summary_warnings:
            create_audit_event(
                resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                action=audit_event_types.ASSET_WORKFLOW_WARN_LOGGED,
                actor_user=created_by,
                tenant=tenant,
                resource_id=str(asset.id),
                result="WARNING",
                details={
                    "tenant_id": str(tenant.id),
                    "asset_id": str(asset.id),
                    "workflow_instance_id": str(instance.id),
                    "result_summary": {
                        "warnings": summary_warnings,
                    },
                },
            )

        return {
            "audit_event_id": str(audit_event.id),
            "action": action
        }

    # ------------------------------------------------------------------
    # Phase 250.2.A.2 (closes Gap 2) — auto-activate resolver
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_auto_activate(
        cls,
        *,
        tenant: "Tenant",  # type: ignore[name-defined]  # forward-reference to Tenant model; resolved at runtime
        caller_auto_activate: bool,
    ) -> Dict[str, Any]:
        """Resolve the effective ``auto_activate`` decision.

        The decision is ``caller_auto_activate AND tenant.
        asset_auto_activate_on_gate_pass``: a tenant that has
        flipped the platform-policy flag to False cannot have
        their assets auto-activated even if every API caller
        passes ``auto_activate=True``; conversely, a caller who
        explicitly passes False (DRAFT-first review) is honoured
        regardless of the tenant flag.

        Read at ``execute()`` time and frozen into
        ``workflow_input`` — same contract as
        ``compliance_fail_closed_enabled`` (Phase 250.1.A.8). A
        flag flip mid-execution does NOT affect an in-flight
        workflow.

        Returns a dict carrying:

        * ``resolved_auto_activate``: the AND of the two —
          consumed by ``_activate_asset_task`` to gate the save.
        * ``caller_auto_activate``: preserved for audit traceability.
        * ``tenant_auto_activate``: preserved for audit traceability
          AND so the in-flight workflow doesn't re-read the tenant
          row mid-execution.
        """
        # ``getattr`` with default True keeps the resolver
        # robust against legacy tenant rows persisted before
        # migration 0035 ran (defensive belt-and-suspenders;
        # the column-level default fills both new and existing
        # rows, but a partial deploy could see stale instances
        # in memory).
        tenant_flag = bool(
            getattr(tenant, "asset_auto_activate_on_gate_pass", True)
        )
        caller_flag = bool(caller_auto_activate)
        return {
            "resolved_auto_activate": caller_flag and tenant_flag,
            "caller_auto_activate": caller_flag,
            "tenant_auto_activate": tenant_flag,
        }

    @classmethod
    def execute(
        cls,
        tenant_id: str,
        key: str,
        name: str,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: str = AssetVisibility.INTERNAL,
        contract_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        profile_key: str = "intake_basic_gx",
        scan_mode: str = "internal",
        applicable_regulations: Optional[list] = None,
        # Phase 250.1.A.3 / D250.2 — auto_activate now defaults TRUE.
        # The workflow's gate steps already enforce fail-closed
        # semantics; once they pass, the asset SHOULD become ACTIVE
        # so the user doesn't have to chase a separate activation
        # call (the legacy default-False produced orphan DRAFTs).
        auto_activate: bool = True,
        send_notifications: bool = True,
        legal_basis: Optional[str] = None,
        destination_jurisdiction: Optional[str] = None,
        created_by_id: Optional[str] = None,
        file_id: Optional[str] = None,
        file_format: Optional[str] = None,
        odps_action: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: str = "JSON",
        odps_contract_id: Optional[str] = None,
        contract_name: Optional[str] = None,
        contract_description: Optional[str] = None,
        contract_version: str = "1.0.0",
        odcs_version: str = "v3",
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute asset creation workflow.

        Args:
            tenant_id: Tenant ID
            key: Asset key (unique per tenant)
            name: Asset name
            description: Asset description (optional)
            domain: Asset domain (optional)
            visibility: Asset visibility (default: INTERNAL)
            contract_id: Contract ID to attach (optional, for contract-first flow)
            dataset_id: Dataset ID to attach (optional, for data-first flow)
            profile_key: DQ profile key (default: intake_basic_gx)
            scan_mode: Compliance scan mode (default: internal)
            applicable_regulations: List of regulations to check (optional)
            auto_activate: Whether to auto-activate asset if checks pass (default: False)
            send_notifications: Whether to send notifications (default: True)
            created_by_id: User ID who created the asset
            file_id: File ID for data-first flow (optional, required for data-first flow)
            file_format: File format: "CSV", "JSON", "PARQUET" (optional, auto-detected if not provided)
            odps_action: ODPS action: "upload", "generate", or "link" (optional, for marketplace)
            odps_raw: ODPS document content (required if odps_action="upload")
            odps_format: ODPS format: "JSON" or "YAML" (default: "JSON", used if odps_action="upload")
            odps_contract_id: Existing ODPS contract ID (required if odps_action="link")
            contract_name: Contract name for generated ODCS (optional, used in data-first flow)
            contract_description: Contract description for generated ODCS (optional, used in data-first flow)
            contract_version: Contract version for generated ODCS (default: "1.0.0", used in data-first flow)
            odcs_version: ODCS version for generated contract (default: "v3", used in data-first flow)
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Validate tenant exists before creating workflow instance
        from hub.apps.tenants.models import Tenant
        try:
            tenant_obj = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant matching query does not exist: {tenant_id}")

        # Phase 250.2.A.2 (closes Gap 2) — resolve effective
        # auto-activate by ANDing the per-call value with the
        # tenant-level governance flag. Frozen into workflow_input
        # so a flag flip mid-execution does NOT affect an in-flight
        # workflow (matches Phase 250.1.A.8's
        # ``compliance_fail_closed_enabled`` contract).
        resolved_auto_activate_input = cls._resolve_auto_activate(
            tenant=tenant_obj,
            caller_auto_activate=auto_activate,
        )

        # Prepare workflow input
        # Only include non-None values to avoid condition evaluation issues
        workflow_input = {
            "tenant_id": tenant_id,
            "key": key,
            "name": name,
        }
        if description is not None:
            workflow_input["description"] = description
        if domain is not None:
            workflow_input["domain"] = domain
        if visibility is not None:
            workflow_input["visibility"] = visibility
        if contract_id is not None:
            workflow_input["contract_id"] = contract_id
        if dataset_id is not None:
            workflow_input["dataset_id"] = dataset_id
        if file_id is not None:
            workflow_input["file_id"] = file_id
        if file_format is not None:
            workflow_input["file_format"] = file_format
        if profile_key is not None:
            workflow_input["profile_key"] = profile_key
        if scan_mode is not None:
            workflow_input["scan_mode"] = scan_mode
        workflow_input["applicable_regulations"] = applicable_regulations or []
        # Phase 250.2.A.2 — ``auto_activate`` carries the resolved
        # decision; ``caller_auto_activate`` and ``tenant_auto_activate``
        # preserve the inputs for audit replay (read by
        # ``_activate_asset_task`` and stamped into
        # ``ASSET_AUTO_ACTIVATED.details_json``).
        workflow_input["auto_activate"] = (
            resolved_auto_activate_input["resolved_auto_activate"]
        )
        workflow_input["caller_auto_activate"] = (
            resolved_auto_activate_input["caller_auto_activate"]
        )
        workflow_input["tenant_auto_activate"] = (
            resolved_auto_activate_input["tenant_auto_activate"]
        )
        workflow_input["send_notifications"] = send_notifications
        if legal_basis is not None:
            workflow_input["legal_basis"] = legal_basis
        if destination_jurisdiction is not None:
            workflow_input["destination_jurisdiction"] = destination_jurisdiction
        if created_by_id is not None:
            workflow_input["created_by_id"] = created_by_id
        if odps_action is not None:
            workflow_input["odps_action"] = odps_action
        if odps_raw is not None:
            workflow_input["odps_raw"] = odps_raw
        if odps_format is not None:
            workflow_input["odps_format"] = odps_format
        if odps_contract_id is not None:
            workflow_input["odps_contract_id"] = odps_contract_id
        if contract_name is not None:
            workflow_input["contract_name"] = contract_name
        if contract_description is not None:
            workflow_input["contract_description"] = contract_description
        if contract_version is not None:
            workflow_input["contract_version"] = contract_version
        if odcs_version is not None:
            workflow_input["odcs_version"] = odcs_version

        # Create workflow instance
        try:
            workflow_instance = engine.create_instance(
                workflow_name=cls.WORKFLOW_NAME,
                input_data=workflow_input,
                tenant_id=tenant_id,
                created_by_id=created_by_id
            )
        except Exception as e:
            # Catch database integrity errors and convert to ValueError
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) or "foreign key constraint" in str(e).lower():
                raise ValueError(f"Invalid tenant_id: {tenant_id}") from e
            raise

        # Phase 250.1.A.5 — record the wall-clock deadline so per-step
        # ``_check_workflow_deadline`` calls can short-circuit if the
        # whole workflow has run past the global timeout.
        if workflow_instance.state_data is None:
            workflow_instance.state_data = {}
        workflow_instance.state_data["__workflow_deadline_at__"] = (
            time.time() + DEFAULT_WORKFLOW_TIMEOUT_SECONDS
        )
        workflow_instance.save(update_fields=["state_data"])

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Asset creation workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                asset_id=workflow_instance.state_data.get("asset_id")
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "output_data": workflow_instance.output_data
            }

        # Phase 250.1.A — workflow ran to a non-COMPLETED terminal
        # state. Two distinct sub-cases need typed handling so the
        # caller (data-first endpoint) can return the right HTTP
        # status + emit the right audit event:
        #
        # (a) Pre-persistence gate refused intake: error_message
        #     embeds a FailClosedRejection JSON payload. Re-raise the
        #     typed exception AFTER emitting ASSET_FAIL_CLOSED_REJECTED
        #     here — emission inside the engine's per-step savepoint
        #     gets rolled back, so this is the first stable place we
        #     can write the audit row.
        #
        # (b) Downstream step failed AFTER the asset was persisted:
        #     state_data carries the asset_id and the engine ran
        #     compensation (status=ROLLED_BACK). Emit
        #     ASSET_WORKFLOW_ROLLED_BACK so ops + dashboards see the
        #     rollback as a first-class event.
        error_message = workflow_instance.error_message or "Workflow execution failed"

        try:
            logger.error(
                "Asset creation workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                error=error_message
            )
        except TypeError:
            logger.error(
                f"Asset creation workflow failed: workflow_instance_id={workflow_instance.id}, "
                f"tenant_id={tenant_id}, error={error_message}"
            )

        # ---- (a) fail-closed-at-intake rejection ----
        fcr = FailClosedRejection.from_message(error_message)
        if fcr is not None:
            try:
                _tenant = Tenant.objects.filter(id=tenant_id).first()
                _user = (
                    UserModel.objects.filter(id=created_by_id).first()
                    if created_by_id
                    else None
                )
                redacted_details, full_details = _build_fail_closed_audit_payload(
                    tenant_id=str(tenant_id),
                    file_id=str(file_id) if file_id else None,
                    key=key,
                    name=name,
                    workflow_instance_id=str(workflow_instance.id),
                    rejection=fcr,
                )
                create_audit_event(
                    resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                    action=audit_event_types.ASSET_FAIL_CLOSED_REJECTED,
                    actor_user=_user,
                    tenant=_tenant,
                    resource_id=None,
                    result="FAILURE",
                    details=redacted_details,
                    full_details=full_details,
                )
            except Exception as audit_exc:
                logger.warning(
                    "fail_closed_audit_emit_failed",
                    workflow_instance_id=str(workflow_instance.id),
                    error=str(audit_exc),
                )
            raise fcr

        # ---- (b) downstream rollback after asset persistence ----
        rolled_back_asset_id = (
            workflow_instance.state_data.get("asset_id")
            if workflow_instance.state_data
            else None
        )
        if (
            workflow_instance.status == WorkflowStatus.ROLLED_BACK
            and rolled_back_asset_id
        ):
            try:
                _tenant = Tenant.objects.filter(id=tenant_id).first()
                _user = (
                    UserModel.objects.filter(id=created_by_id).first()
                    if created_by_id
                    else None
                )
                failed_step_name = (
                    (workflow_instance.error_details or {}).get(
                        "failed_step_name"
                    )
                    if workflow_instance.error_details
                    else None
                )
                create_audit_event(
                    resource_type=audit_event_types.ASSET_RESOURCE_TYPE,
                    action=audit_event_types.ASSET_WORKFLOW_ROLLED_BACK,
                    actor_user=_user,
                    tenant=_tenant,
                    resource_id=str(rolled_back_asset_id),
                    result="FAILURE",
                    details={
                        "tenant_id": str(tenant_id),
                        "asset_id": str(rolled_back_asset_id),
                        "workflow_instance_id": str(workflow_instance.id),
                        "failed_step": failed_step_name,
                        "error_message": error_message,
                    },
                )
            except Exception as audit_exc:
                logger.warning(
                    "rolled_back_audit_emit_failed",
                    workflow_instance_id=str(workflow_instance.id),
                    error=str(audit_exc),
                )

        raise ValueError(f"Asset creation workflow failed: {error_message}")

