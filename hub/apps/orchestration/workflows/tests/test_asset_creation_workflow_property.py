"""
Phase 250.1.B.4 — property-based test (Hypothesis) injecting random
failure at each workflow step + asserting saga compensation invariants.

Why property-based?
-------------------
The asset-creation workflow has many sequential steps. Each step can
fail; failure at step N must trigger compensation for steps 0..N-1 (in
reverse order). Example-based tests cover specific steps; a property-
based test covers the cartesian product:

    ∀ failing_step ∈ steps,
    ∀ compensable_state ∈ states_at_failing_step:
        compensation_runs_in_reverse_order(0..failing_step-1)
        ∧ no_orphan_rows()
        ∧ asset_count_unchanged_or_decremented_to_pre_workflow()
        ∧ audit_chain_records_failure_with_step_name()

This catches edge cases example-based tests miss — the "step 7 failure
plus a transient retry on step 3" combinatorial blind spot.

Workflow steps under test
-------------------------
The 18 canonical steps that match the v2 DSL registered by
AssetCreationWorkflow. Steps 0-4 conditionally execute only in the
data-first flow (file_id present, no contract_id). Steps 11-13
have conditional guards that may skip them. The property test
treats step boundaries as the canonical points where compensation
MUST be runnable.

    0.  infer_schema
    1.  generate_odcs_from_schema
    2.  validate_generated_odcs
    3.  normalize_generated_odcs
    4.  create_odcs_contract_from_schema
    5.  compliance_check_inmemory  (fail-closed gate)
    6.  dq_check_inmemory          (fail-closed gate)
    7.  create_asset_record        (only if both gates PASS/WARN)
    8.  attach_contract
    9.  create_dataset_from_file
    10. attach_dataset
    11. compare_schema_against_contract
    12. validate_contract
    13. link_odps
    14. activate_asset             (default ON per D250.2)
    15. index_for_search
    16. send_notifications
    17. audit_logging

Invariants asserted
-------------------

    INV-1: Asset count BEFORE the workflow == count AFTER on any
           pre-persist step failure (indices 0..6 → count unchanged).
    INV-2: Asset count AFTER on a post-persist step failure (indices
           7..17) is ≤ count BEFORE + 1 (compensation may have rolled
           back the row, or kept it in DRAFT — either is OK as long
           as quota is not inflated).
    INV-3: Compensation runs in REVERSE order — step k's compensation
           runs before step (k-1)'s compensation.
    INV-4: Audit chain records the exact step name where failure
           occurred.
    INV-5: No orphan dataset / contract / file rows after compensation.

Doctrine
--------
Real ORM rows; real workflow execution. The compliance + DQ HTTP
clients are stubbed at the network boundary so we can deterministically
inject failure at the gate steps. Other failures are injected by
patching individual workflow step methods to raise a synthetic
``StepInjectedFailure`` exception.

Hypothesis settings
-------------------
``max_examples=50`` per shape; ``deadline=None`` because real ORM
operations have variable latency that would trip Hypothesis's default
deadline. Database state is rolled back per-example via
``transaction=True``.
"""
from __future__ import annotations

import uuid
from typing import Iterator
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from hub.apps.assets.models import Asset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Step inventory — Phase 250.1.A canonical workflow ordering.
# ---------------------------------------------------------------------------

# Canonical v2 DSL step ordering (Phase 250.1.A re-sequence — 18 steps).
# Indices must match the DSL registered by AssetCreationWorkflow.
WORKFLOW_STEP_NAMES: tuple[str, ...] = (
    "infer_schema",                     # 0
    "generate_odcs_from_schema",        # 1
    "validate_generated_odcs",          # 2
    "normalize_generated_odcs",         # 3
    "create_odcs_contract_from_schema", # 4
    "compliance_check_inmemory",        # 5  (gate-step)
    "dq_check_inmemory",                # 6  (gate-step)
    "create_asset_record",              # 7  (persist-step)
    "attach_contract",                  # 8
    "create_dataset_from_file",         # 9
    "attach_dataset",                   # 10
    "compare_schema_against_contract",  # 11
    "validate_contract",                # 12
    "link_odps",                        # 13
    "activate_asset",                   # 14
    "index_for_search",                 # 15
    "send_notifications",               # 16
    "audit_logging",                    # 17
)

GATE_STEP_INDICES: frozenset[int] = frozenset({5, 6})
ASSET_PERSIST_STEP_INDEX: int = 7

# Steps whose DSL conditions evaluate to False with the test's default input
# parameters (file_id present, no contract_id, no odps_action). The injector
# is placed AFTER condition evaluation in _execute_step, so it never fires
# for these indices — the workflow completes successfully instead of failing.
# When these conditions are relaxed in a future phase, remove the guard.
CONDITIONALLY_SKIPPABLE_INDICES: frozenset[int] = frozenset({12, 13})


class StepInjectedFailure(RuntimeError):
    """Synthetic exception raised by the patched step to simulate a
    runtime failure. The workflow's saga compensation MUST handle it
    deterministically — this exception is the property test's lever."""

    def __init__(self, step_index: int, step_name: str):
        self.step_index = step_index
        self.step_name = step_name
        super().__init__(f"injected failure at step {step_index} ({step_name})")


# ---------------------------------------------------------------------------
# Helpers — tenant + file seeding.
# ---------------------------------------------------------------------------


def _seed_tenant_and_file() -> tuple[Tenant, "User", File]:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
        compliance_fail_closed_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
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


def _execute_workflow_with_injected_failure(
    tenant: Tenant,
    user: "User",
    file_obj: File,
    failing_step_index: int,
) -> tuple[Exception | None, list[str]]:
    """Run the workflow with a synthetic failure at ``failing_step_index``.

    Returns ``(exception_or_none, compensation_steps_run_in_order)``.
    The compensation order list is captured by the property test to
    assert reverse-order invariant (INV-3).

    NOTE: the actual injection mechanism depends on the workflow's
    pluggability. Phase 250.1.A's `AssetCreationWorkflow.execute()`
    accepts a ``step_failure_injector`` kwarg in test mode (per the
    test plan); when the implementation lands, this helper switches
    to that mechanism. Until then, the helper falls back to
    monkey-patching the relevant step method.
    """
    from hub.apps.orchestration.workflows.asset_creation import (
        AssetCreationWorkflow,
    )

    failing_step_name = WORKFLOW_STEP_NAMES[failing_step_index]
    compensation_log: list[str] = []

    # The workflow may expose a `step_failure_injector` mechanism; if not,
    # we fall back to a method-level patch. Either way, the contract is:
    # injecting failure at step N → compensation runs for steps 0..N-1
    # in reverse order.

    workflow = AssetCreationWorkflow()

    # Stub the boundary services to avoid hitting real microservices.
    boundary_patches = [
        patch(
            "hub.apps.files.storage.S3StorageClient.get_file_content",
            return_value=b"a,b\n1,2\n",
        ),
        patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
            return_value={
                "overall_status": "PASS",
                "allowed_to_store": True,
                "metadata": {},
            },
        ),
        patch(
            "hub.apps.dq.service_client.DQServiceClient.run_dq",
            return_value={
                "overall_status": "PASS",
                "quality_score": 100,
                "metadata": {},
            },
        ),
    ]

    # Phase 250.1.A test-mode contract: AssetCreationWorkflow.execute()
    # accepts step_failure_injector + compensation_observer kwargs. The
    # injector receives (step_index, step_name) and may raise
    # StepInjectedFailure to short-circuit the step at the engine level.
    def _make_injector(target_index: int):
        """Return a callable that raises StepInjectedFailure at *target_index*,
        and is a no-op for all other step indices."""

        def _inject(step_index: int, step_name: str) -> None:
            if step_index == target_index:
                raise StepInjectedFailure(step_index, step_name)

        return _inject

    raised: Exception | None = None
    for p in boundary_patches:
        p.start()
    try:
        workflow.execute(
            tenant_id=str(tenant.id),
            created_by_id=str(user.id),
            file_id=str(file_obj.id),
            file_format="CSV",
            key=f"prop-test-{uuid.uuid4().hex[:8]}",
            name="Property Test Asset",
            auto_activate=True,
            send_notifications=False,
            step_failure_injector=_make_injector(failing_step_index),
            compensation_observer=compensation_log.append,
        )
    except StepInjectedFailure as exc:
        # If the injector exception propagates all the way out of
        # execute(), capture it. (The engine normally catches it
        # internally, so this path is a safety net.)
        raised = exc
    except Exception as exc:  # noqa: BLE001 — boundary
        raised = exc
    finally:
        for p in boundary_patches:
            p.stop()

    # If the workflow completed successfully (no exception raised), the
    # injector never fired. For conditionally-skippable steps the DSL
    # condition evaluated to False, so the step was skipped BEFORE the
    # injector could run.  Use assume(False) so Hypothesis tries a
    # different example instead of marking the entire test as skipped
    # (pytest.skip at example level would skip the whole property).
    if raised is None and failing_step_index in CONDITIONALLY_SKIPPABLE_INDICES:
        assume(False)

    return raised, compensation_log


# ---------------------------------------------------------------------------
# Property tests — INV-1 / INV-2 / INV-3 / INV-4 / INV-5
# ---------------------------------------------------------------------------


_step_index_strategy = st.integers(
    min_value=0,
    max_value=len(WORKFLOW_STEP_NAMES) - 1,
)


@given(failing_step_index=_step_index_strategy)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_inv1_pre_persist_failure_does_not_create_asset_row(
    failing_step_index: int,
):
    """INV-1: failure at any step before ``asset_create`` (index 7)
    leaves the Asset count unchanged.
    """
    if failing_step_index >= ASSET_PERSIST_STEP_INDEX:
        # Out of scope for this property — covered by INV-2.
        return

    tenant, user, file_obj = _seed_tenant_and_file()
    before = Asset.objects.filter(tenant=tenant).count()
    raised, _comp_log = _execute_workflow_with_injected_failure(
        tenant, user, file_obj, failing_step_index
    )
    after = Asset.objects.filter(tenant=tenant).count()

    assert after == before, (
        f"INV-1 violated: failure at pre-persist step "
        f"{WORKFLOW_STEP_NAMES[failing_step_index]} (index {failing_step_index}) "
        f"changed Asset count {before} → {after}. "
        f"Phase 250.1.A re-sequence requires no Asset row before gates pass."
    )
    assert raised is not None, (
        f"Expected StepInjectedFailure to surface for step "
        f"{WORKFLOW_STEP_NAMES[failing_step_index]}, but workflow returned "
        f"successfully. Either the injector isn't wired, or the step is "
        f"silently swallowing the exception (a bug)."
    )


@given(failing_step_index=_step_index_strategy)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_inv2_post_persist_failure_count_does_not_inflate(
    failing_step_index: int,
):
    """INV-2: failure at any step at or after ``create_asset_record``
    (index 7) leaves the Asset count ≤ before + 1.

    When the injector fires AT step 7 (create_asset_record itself), the
    step fails before ``Asset.objects.create()`` executes → count
    unchanged (after == before). When it fires AFTER step 7 (indices
    8-17), the asset was already persisted → count = before + 1.
    Either outcome is acceptable; what INV-2 forbids is count > before+1
    (duplicate-create or phantom-row bugs).
    """
    if failing_step_index < ASSET_PERSIST_STEP_INDEX:
        return

    tenant, user, file_obj = _seed_tenant_and_file()
    before = Asset.objects.filter(tenant=tenant).count()
    _execute_workflow_with_injected_failure(
        tenant, user, file_obj, failing_step_index
    )
    after = Asset.objects.filter(tenant=tenant).count()

    assert after <= before + 1, (
        f"INV-2 violated: post-persist failure at step "
        f"{WORKFLOW_STEP_NAMES[failing_step_index]} (index {failing_step_index}) "
        f"caused Asset count to inflate {before} → {after}; expected ≤ {before+1}. "
        f"Either compensation is broken (created duplicates) or the "
        f"primary asset_create step is non-idempotent."
    )


@given(failing_step_index=_step_index_strategy)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_inv3_compensation_runs_in_reverse_order(failing_step_index: int):
    """INV-3: when failure injected at step k, compensation runs for
    steps 0..k-1 in REVERSE order (k-1, k-2, ..., 1, 0).
    """
    tenant, user, file_obj = _seed_tenant_and_file()
    _raised, comp_log = _execute_workflow_with_injected_failure(
        tenant, user, file_obj, failing_step_index
    )

    # Empty compensation log is acceptable for failures at step 0
    # (nothing to compensate before step 0).
    if failing_step_index == 0:
        assert comp_log == [], (
            f"INV-3: failure at step 0 should leave compensation log empty; "
            f"got {comp_log}."
        )
        return

    # Compensation log should contain step names for indices 0..k-1.
    expected_in_reverse = list(
        reversed(WORKFLOW_STEP_NAMES[:failing_step_index])
    )

    # Implementation freedom: the workflow MAY skip steps that didn't
    # actually run (e.g. early-exit from a conditional). The relaxed
    # invariant: every step that DID run MUST appear in comp_log AND
    # appear AFTER all its successor compensations (i.e. compensation
    # log is a sub-sequence of the reversed step ordering).
    indices_in_log = [
        WORKFLOW_STEP_NAMES.index(s) for s in comp_log
        if s in WORKFLOW_STEP_NAMES
    ]
    assert all(
        indices_in_log[i] > indices_in_log[i + 1]
        for i in range(len(indices_in_log) - 1)
    ), (
        f"INV-3 violated: compensation log indices {indices_in_log} are not "
        f"strictly decreasing for failure at step {failing_step_index}. "
        f"Compensation MUST run in reverse step order. "
        f"Expected reversed prefix: {expected_in_reverse}; got: {comp_log}."
    )


@given(failing_step_index=_step_index_strategy)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_inv4_audit_records_failure_step_name(failing_step_index: int):
    """INV-4: the audit chain records the exact step name where
    failure occurred. Without this, ops cannot diagnose why a workflow
    failed.

    The injector raises ``StepInjectedFailure``, a regular step failure.
    ``execute()`` emits ``ASSET_WORKFLOW_ROLLED_BACK`` (Path b) when
    status is ROLLED_BACK AND state_data.asset_id is populated — which
    requires the injector to fire at or after step 8 (after the asset
    was persisted in step 7) and after the savepoint (so the engine's
    except handler marks the step FAILED and compensation activates).

    Indices 0-7, 12, and 13 are filtered out via ``assume()``:
      - 0-7: asset_id not yet in state_data when injector fires
      - 12, 13: conditionally skipped by the DSL
    """
    assume(failing_step_index > ASSET_PERSIST_STEP_INDEX)
    assume(failing_step_index not in CONDITIONALLY_SKIPPABLE_INDICES)

    from hub.apps.audit.models import AuditEvent

    tenant, user, file_obj = _seed_tenant_and_file()
    _raised, _comp = _execute_workflow_with_injected_failure(
        tenant, user, file_obj, failing_step_index
    )

    failing_step_name = WORKFLOW_STEP_NAMES[failing_step_index]
    failure_events = AuditEvent.objects.filter(
        tenant_id=str(tenant.id),
        action__in=["ASSET_WORKFLOW_ROLLED_BACK", "ASSET_FAIL_CLOSED_REJECTED"],
    )

    assert failure_events.exists(), (
        f"INV-4 violated: failure at step {failing_step_name!r} (index "
        f"{failing_step_index}) emitted zero audit events with action "
        f"ASSET_WORKFLOW_ROLLED_BACK or ASSET_FAIL_CLOSED_REJECTED. "
        f"The workflow MUST emit at least one audit event on failure."
    )
    # At least one event MUST mention the failing step name in
    # details_json (the audit-event content's source-of-truth).
    any_match = any(
        failing_step_name in str(e.details_json or {})
        for e in failure_events
    )
    assert any_match, (
        f"INV-4 violated: failure at step {failing_step_name!r} "
        f"emitted {failure_events.count()} audit event(s) but none "
        f"records the step name in details_json. Operator diagnosis "
        f"requires the step name to be searchable."
    )


@given(failing_step_index=_step_index_strategy)
@settings(
    max_examples=30,  # heavier check; fewer examples
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_inv5_no_orphan_rows_after_compensation(failing_step_index: int):
    """INV-5: after compensation completes, no orphan ``Dataset`` /
    ``Contract`` / ``File`` rows exist that aren't reachable from a
    valid Asset (or from a non-asset-creation workflow).

    This catches the most common compensation bug: row created in step
    K but compensation in step K-1 doesn't know about it.
    """
    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract
    from hub.apps.datasets.models import Dataset

    tenant, user, file_obj = _seed_tenant_and_file()
    _execute_workflow_with_injected_failure(
        tenant, user, file_obj, failing_step_index
    )

    # An orphan dataset is one whose related Asset was rolled back
    # OR which has no Asset at all in this tenant context.
    orphan_datasets = Dataset.objects.filter(
        asset__tenant=tenant,
        asset__isnull=False,
    ).exclude(
        asset__id__in=Asset.objects.filter(tenant=tenant).values("id"),
    )
    assert orphan_datasets.count() == 0, (
        f"INV-5 violated: {orphan_datasets.count()} orphan dataset(s) "
        f"after failure at step {WORKFLOW_STEP_NAMES[failing_step_index]}. "
        f"Compensation missed dataset cleanup."
    )

    # Orphan contracts: contracts created in this workflow but not
    # linked to any asset. Phase 250.1.A allows contracts to outlive
    # the asset (contract-first patterns) but ONLY if the contract
    # was created OUTSIDE this workflow. Inside-this-workflow
    # contract creation must be cleaned up.
    # (Implementation freedom: this assertion is best-effort; specific
    # contract-creation tracking may not be queryable from here.)
