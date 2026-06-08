"""
Phase 250.1.C.3 — tests for the v1 handler removal readiness command.

The command's contract:

1. Exit 0 (READY) when zero v1 in-flight runs AND soak elapsed.
2. Exit 1 (NOT READY) when any v1 in-flight run exists OR soak ongoing.
3. Exit 2 (DATA ERROR) on environment misconfiguration.
4. ``--json`` flag emits structured JSON consumable by Slack-digest /
   Prometheus-exporter pipelines.
5. ``--soak-days`` overrides the D250.7 default of 14 days.
6. Per-tenant breakdown + example instance ids surface for SRE triage.

Doctrine
--------
Real Django ORM rows. ``call_command(...)`` invokes the real management
command machinery so the test exercises ``add_arguments`` parsing and
``handle`` end-to-end. ``sys.exit`` raises ``SystemExit``; tests catch it
and assert on the exit code per the standard Django mgmt-cmd test pattern.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant() -> Tenant:
    """Create a real ``Tenant`` row so ``WorkflowInstance.tenant`` FK
    constraints (postgres-enforced) are satisfied. Synthetic UUIDs as
    raw values violate the FK contract per the audit-pass."""
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"ReadinessTest-{uid}",
        slug=f"readiness-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


# ---------------------------------------------------------------------------
# Fixture helpers — minimal seeding to drive the readiness check
# ---------------------------------------------------------------------------


def _seed_v1_definition_only() -> WorkflowDefinition:
    """v1 alone — no v2 yet — soak window NOT applicable (v1 still active)."""
    wf_def, _created = WorkflowDefinition.objects.get_or_create(
        name="asset_creation",
        version="1.0.0",
        defaults={
            "dsl_json": {"version": "1.0.0", "steps": [{"name": "test_step", "type": "task"}]},
            "is_active": True,
        },
    )
    return wf_def


def _seed_v1_v2_within_soak() -> tuple[WorkflowDefinition, WorkflowDefinition]:
    """Both versions present; v1 just deactivated → still in soak window."""
    v1, _created = WorkflowDefinition.objects.get_or_create(
        name="asset_creation",
        version="1.0.0",
        defaults={
            "dsl_json": {"version": "1.0.0", "steps": [{"name": "test_step", "type": "task"}]},
            "is_active": False,
        },
    )
    v2, _created = WorkflowDefinition.objects.get_or_create(
        name="asset_creation",
        version="2.0.0",
        defaults={
            "dsl_json": {"version": "1.0.0", "steps": [{"name": "test_step", "type": "task"}]},
            "is_active": True,
        },
    )
    return v1, v2


def _seed_v1_v2_post_soak(soak_days: int = 14) -> tuple[WorkflowDefinition, WorkflowDefinition]:
    """v1 + v2; v1 deactivated more than ``soak_days`` ago → soak elapsed."""
    v1, v2 = _seed_v1_v2_within_soak()
    # Move v1's updated_at backwards to simulate soak expiry.
    WorkflowDefinition.objects.filter(pk=v1.pk).update(
        updated_at=timezone.now() - timedelta(days=soak_days + 1),
    )
    v1.refresh_from_db()
    return v1, v2


def _seed_inflight_v1(*, count: int = 1) -> list[WorkflowInstance]:
    """Create ``count`` non-terminal v1 instances."""
    wf_def = _seed_v1_definition_only()
    instances: list[WorkflowInstance] = []
    for i in range(count):
        instances.append(WorkflowInstance.objects.create(
            workflow_definition=wf_def,
            workflow_name="asset_creation",
            workflow_version="1.0.0",
            status=WorkflowStatus.RUNNING,
            tenant_id=None,
            input_data={"key": f"inflight-{i}"},
        ))
    return instances


def _run_command(*args, expect_exit: int) -> str:
    """Invoke the command; assert SystemExit with the expected code; return stdout."""
    stdout = io.StringIO()
    with pytest.raises(SystemExit) as exc_info:
        call_command("check_workflow_v1_removal_readiness", *args, stdout=stdout)
    assert exc_info.value.code == expect_exit, (
        f"expected exit code {expect_exit}, got {exc_info.value.code}; "
        f"stdout was:\n{stdout.getvalue()}"
    )
    return stdout.getvalue()


# ---------------------------------------------------------------------------
# Exit-code contract — README-grade scenarios
# ---------------------------------------------------------------------------


class TestReadinessVerdict:
    """The command produces a 3-way verdict: READY (0) / NOT READY (1) / DATA ERROR (2)."""

    def test_ready_when_no_inflight_runs_and_soak_elapsed(self):
        _seed_v1_v2_post_soak()
        # No in-flight v1 instances seeded.
        out = _run_command(expect_exit=0)
        assert "READY" in out
        assert "blocked" not in out

    def test_not_ready_when_inflight_runs_exist(self):
        _seed_v1_v2_post_soak()
        _seed_inflight_v1(count=3)
        out = _run_command(expect_exit=1)
        assert "NOT READY" in out
        # Reason mentions in-flight count.
        assert "3_inflight_runs" in out

    def test_not_ready_when_soak_window_not_elapsed(self):
        _seed_v1_v2_within_soak()
        # No in-flight runs, but v1 still in soak.
        out = _run_command(expect_exit=1)
        assert "NOT READY" in out
        assert "soak_window_not_elapsed" in out

    def test_not_ready_when_both_blockers_present(self):
        _seed_v1_v2_within_soak()
        _seed_inflight_v1(count=2)
        out = _run_command(expect_exit=1)
        assert "NOT READY" in out
        assert "2_inflight_runs" in out
        assert "soak_window_not_elapsed" in out

    def test_only_non_terminal_statuses_count_as_inflight(self):
        """Terminal statuses (COMPLETED, FAILED, CANCELLED, ROLLED_BACK)
        are at-rest and SHOULD NOT block removal."""
        _seed_v1_v2_post_soak()
        # Seed terminal-state v1 instances — these are NOT blockers.
        for terminal_status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
            WorkflowStatus.ROLLED_BACK,
        ):
            WorkflowInstance.objects.create(
                workflow_definition=_seed_v1_definition_only(),
                workflow_name="asset_creation",
                workflow_version="1.0.0",
                status=terminal_status,
                input_data={"key": f"terminal-{terminal_status}"},
            )
        out = _run_command(expect_exit=0)
        assert "READY" in out

    def test_non_terminal_states_all_block(self):
        """Every status enum that is NOT terminal MUST count as in-flight."""
        _seed_v1_v2_post_soak()
        non_terminal = [
            WorkflowStatus.DRAFT,
            WorkflowStatus.RUNNING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.ROLLING_BACK,
            WorkflowStatus.COMPENSATION_INCOMPLETE,
        ]
        for s in non_terminal:
            WorkflowInstance.objects.create(
                workflow_definition=_seed_v1_definition_only(),
                workflow_name="asset_creation",
                workflow_version="1.0.0",
                status=s,
                input_data={"key": f"nt-{s}"},
            )
        out = _run_command(expect_exit=1)
        assert "NOT READY" in out
        # Five non-terminal instances should be blocking.
        assert "5_inflight_runs" in out


# ---------------------------------------------------------------------------
# JSON output — for CI / Slack-digest / Prometheus consumption
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """``--json`` emits a structured verdict consumable by automation."""

    def test_json_ready_verdict(self):
        _seed_v1_v2_post_soak()
        out = _run_command("--json", expect_exit=0)
        verdict = json.loads(out)
        assert verdict["ready"] is True
        assert verdict["exit_code"] == 0
        assert verdict["inflight_count"] == 0
        assert verdict["soak_elapsed"] is True
        assert verdict["workflow"] == "asset_creation"
        assert verdict["version"] == "1.0.0"
        assert verdict["soak_days"] == 14

    def test_json_not_ready_with_breakdown(self):
        _seed_v1_v2_post_soak()
        # Two REAL tenants with 2 + 1 inflight runs. Audit-pass fix:
        # synthetic UUIDs as `tenant_id` would violate the WorkflowInstance
        # → Tenant FK constraint at INSERT time on PostgreSQL.
        tenant_a = _seed_tenant()
        tenant_b = _seed_tenant()
        v1_def = _seed_v1_definition_only()
        for _ in range(2):
            WorkflowInstance.objects.create(
                workflow_definition=v1_def,
                workflow_name="asset_creation",
                workflow_version="1.0.0",
                status=WorkflowStatus.RUNNING,
                tenant=tenant_a,
                input_data={},
            )
        WorkflowInstance.objects.create(
            workflow_definition=v1_def,
            workflow_name="asset_creation",
            workflow_version="1.0.0",
            status=WorkflowStatus.RUNNING,
            tenant=tenant_b,
            input_data={},
        )
        out = _run_command("--json", expect_exit=1)
        verdict = json.loads(out)
        assert verdict["ready"] is False
        assert verdict["inflight_count"] == 3
        # Per-tenant breakdown distinguishes tenant_a (2 runs) from tenant_b (1 run).
        breakdown = verdict["per_tenant_breakdown"]
        assert breakdown[str(tenant_a.id)] == 2
        assert breakdown[str(tenant_b.id)] == 1
        # Examples list capped at 10 with full diagnostic shape.
        assert len(verdict["examples"]) == 3
        for ex in verdict["examples"]:
            assert {"instance_id", "tenant_id", "status", "started_at"}.issubset(ex.keys())


# ---------------------------------------------------------------------------
# Configurable knobs
# ---------------------------------------------------------------------------


class TestConfigurableKnobs:
    """The command accepts ``--workflow``, ``--workflow-version``, ``--soak-days``."""

    def test_custom_workflow_name(self):
        # Seed unrelated workflow; it should NOT count.
        WorkflowDefinition.objects.create(
            name="other_workflow",
            version="1.0.0",
            dsl_json={"version": "1.0.0", "steps": [{"name": "test_step", "type": "task"}]},
            is_active=True,
        )
        # Seed ``asset_creation`` v1 in soak (default behaviour: NOT READY).
        _seed_v1_v2_within_soak()
        # But check ``other_workflow`` instead — no v2 deployed there, so
        # is_version_eligible_for_inflight returns True (still active),
        # meaning soak NOT elapsed → NOT READY.
        out = _run_command(
            "--workflow=other_workflow",
            "--workflow-version=1.0.0",
            expect_exit=1,
        )
        assert "other_workflow" in out

    def test_custom_soak_days(self):
        """A version deactivated 7 days ago is OUTSIDE a 5-day soak but
        INSIDE a 14-day soak."""
        _seed_v1_v2_within_soak()
        # Move v1 7 days back.
        WorkflowDefinition.objects.filter(
            name="asset_creation", version="1.0.0"
        ).update(updated_at=timezone.now() - timedelta(days=7))
        # 5-day soak: v1 outside → READY (assuming no in-flight).
        out_short = _run_command("--soak-days=5", expect_exit=0)
        assert "READY" in out_short
        # 14-day soak (default): v1 inside → NOT READY.
        out_default = _run_command(expect_exit=1)
        assert "soak_window_not_elapsed" in out_default
