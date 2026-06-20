"""
Phase 250.2.A (closes Gap 2) — auto-activate default + tenant override
+ ASSET_AUTO_ACTIVATED audit emission.

Contract under test
-------------------

1. **Tenant-level default is True**:
   ``Tenant.asset_auto_activate_on_gate_pass`` defaults to True for
   newly-created tenant rows AND for existing rows after migration
   ``0035_tenant_auto_activate_flag`` runs (the AddField column-level
   default fills both).

2. **Resolved auto-activate = per-call AND tenant**: in
   ``AssetCreationWorkflow.execute()``, the effective decision is
   ``resolved = caller_auto_activate AND tenant.asset_auto_activate_on_gate_pass``.
   The resolved value is frozen into ``workflow_input["auto_activate"]``
   so a flag flip mid-execution does not affect an in-flight workflow
   (matches the ``compliance_fail_closed_enabled`` contract from Phase
   250.1.A.8).

3. **Activation outcome**:
   * caller=True, tenant=True  → resolved=True  → status=ACTIVE
   * caller=True, tenant=False → resolved=False → status=DRAFT
   * caller=False, tenant=True → resolved=False → status=DRAFT (caller
     wins for DRAFT-first review)
   * caller=False, tenant=False → resolved=False → status=DRAFT

4. **Audit emission**: ``ASSET_AUTO_ACTIVATED`` is emitted by
   ``_activate_asset_task`` ONLY when activation actually fires
   (resolved=True AND ``can_activate()`` returned True). The audit
   row carries ``caller_auto_activate``, ``tenant_auto_activate``,
   and ``resolved_auto_activate`` so an auditor can replay the
   decision without consulting tenant state at audit-replay time.

TDD doctrine
------------
* Real Django ORM rows: ``Tenant``, ``User``, ``Asset``, ``Contract``,
  real ``WorkflowInstance.objects.create()`` machinery.
* Real ``_activate_asset_task`` invocation — no mock of the activation
  logic, just direct call with synthetic ``input_data`` / ``instance``
  / ``step`` (matches the canonical pattern at
  ``test_asset_creation.py::test_activate_asset_task``).
* Real ``can_activate()`` evaluation — the asset has an ACTIVE
  contract with VALID validation_status + NORMALIZED_OK + a
  structural-floor-passing ``hub_contract_json`` payload so the
  gate genuinely passes.
* Real ``create_audit_event`` writes — assertions read the
  ``AuditEvent`` table directly. Audit emission is NOT mocked.
* The ``execute()`` resolver test directly exercises the
  caller-vs-tenant resolution by spying on the resolved
  ``workflow_input["auto_activate"]`` after the workflow input
  build phase, without running the full multi-step workflow
  (which depends on DQ / compliance / contract validation that
  this sub-phase doesn't gate).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.test import TestCase

from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    ComplianceStatus,
    DQStatus,
)
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.orchestration.models import StepStatus, WorkflowStep
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.asset_creation import (
    AssetCreationWorkflow,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


# A minimal hub_contract_json that satisfies the structural-floor at
# hub/apps/contracts/structureless.py:86 — at least one schema field
# carries the contract past ``is_payload_structureless``.
_VALID_HUB_CONTRACT_JSON: dict[str, Any] = {
    "schema": {
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "value", "type": "integer"},
        ]
    }
}


def _seed_tenant(*, auto_activate_flag: bool = True) -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"AutoActivateTest-{uid}",
        slug=f"auto-activate-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        asset_auto_activate_on_gate_pass=auto_activate_flag,
    )


def _seed_user(tenant: Tenant) -> User:
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
    )


def _seed_active_contract(tenant: Tenant, user: User) -> Contract:
    return Contract.objects.create(
        tenant=tenant,
        original_spec_type="OpenAPI",
        original_spec_version="3.0.0",
        hub_contract_json=_VALID_HUB_CONTRACT_JSON,
        status=ContractStatus.ACTIVE,
        validation_status="VALID",
        normalization_status="NORMALIZED_OK",
        created_by=user,
    )


def _seed_activatable_asset(
    *,
    tenant: Tenant,
    user: User,
    contract: Contract,
) -> Asset:
    """Seed an Asset that ``can_activate()`` returns True for: DRAFT
    status, gate fields PASS, with an ACTIVE structural-floor-passing
    contract attached so the gate genuinely passes."""
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:8]}",
        name="Activatable Asset",
        status=AssetStatus.DRAFT,
        dq_status=DQStatus.PASS,
        compliance_status=ComplianceStatus.PASS,
        created_by=user,
    )
    contract.asset = asset
    contract.save(update_fields=["asset"])
    return asset


def _build_workflow_instance(
    *,
    tenant: Tenant,
    user: User,
    asset: Asset,
    workflow_input: dict[str, Any],
):
    """Materialise a WorkflowInstance pointing at ``asset`` so
    ``_activate_asset_task`` can run end-to-end against real ORM."""
    engine = WorkflowEngine()
    registry = WorkflowRegistry()
    AssetCreationWorkflow.register_workflow(registry)
    AssetCreationWorkflow.register_tasks(engine)
    instance = engine.create_instance(
        workflow_name=AssetCreationWorkflow.WORKFLOW_NAME,
        input_data=workflow_input,
        tenant_id=str(tenant.id),
        created_by_id=str(user.id),
    )
    instance.state_data["asset_id"] = str(asset.id)
    instance.save()
    step = WorkflowStep(
        workflow_instance=instance,
        step_index=7,
        step_name="activate_asset",
        step_type="task",
        status=StepStatus.PENDING,
    )
    return instance, step


# ---------------------------------------------------------------------------
# 250.2.A.1 — tenant flag default
# ---------------------------------------------------------------------------


class TestTenantFlagDefault(TestCase):
    """The new ``asset_auto_activate_on_gate_pass`` field defaults to
    True on freshly-created tenants and is queryable via the regular
    ORM."""

    def test_new_tenant_has_flag_true_by_default(self):
        tenant = Tenant.objects.create(
            name=f"DefaultTenant-{uuid.uuid4().hex[:8]}",
            slug=f"default-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        # No override at create time → field default applies.
        assert tenant.asset_auto_activate_on_gate_pass is True

    def test_explicit_false_at_create_persists(self):
        tenant = Tenant.objects.create(
            name=f"OptOutTenant-{uuid.uuid4().hex[:8]}",
            slug=f"opt-out-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            asset_auto_activate_on_gate_pass=False,
        )
        tenant.refresh_from_db()
        assert tenant.asset_auto_activate_on_gate_pass is False


# ---------------------------------------------------------------------------
# 250.2.A.2 — execute() resolves caller AND tenant
# ---------------------------------------------------------------------------


class TestExecuteResolvesAutoActivate(TestCase):
    """``AssetCreationWorkflow.execute()`` reads
    ``Tenant.asset_auto_activate_on_gate_pass`` and ANDs it with the
    per-call ``auto_activate`` argument before stamping the resolved
    value into ``workflow_input``. Both the caller value and the
    tenant value are preserved in the input for audit traceability."""

    def _capture_workflow_input(
        self,
        *,
        tenant: Tenant,
        caller_auto_activate: bool,
    ) -> dict[str, Any]:
        """Drive ``AssetCreationWorkflow._resolve_auto_activate`` (the
        helper this phase introduces) directly — the helper is
        deliberately surfaced as a classmethod so the resolver
        contract is testable without standing up a full workflow
        run."""
        return AssetCreationWorkflow._resolve_auto_activate(
            tenant=tenant,
            caller_auto_activate=caller_auto_activate,
        )

    def test_caller_true_tenant_true_resolves_true(self):
        tenant = _seed_tenant(auto_activate_flag=True)
        resolved = self._capture_workflow_input(
            tenant=tenant,
            caller_auto_activate=True,
        )
        assert resolved["resolved_auto_activate"] is True
        assert resolved["caller_auto_activate"] is True
        assert resolved["tenant_auto_activate"] is True

    def test_caller_true_tenant_false_resolves_false(self):
        """Tenant override is the platform-policy backstop — caller
        cannot bypass the tenant-level kill switch by passing True."""
        tenant = _seed_tenant(auto_activate_flag=False)
        resolved = self._capture_workflow_input(
            tenant=tenant,
            caller_auto_activate=True,
        )
        assert resolved["resolved_auto_activate"] is False
        assert resolved["caller_auto_activate"] is True
        assert resolved["tenant_auto_activate"] is False

    def test_caller_false_tenant_true_resolves_false(self):
        """Caller-False is honoured even when tenant says auto-
        activate — DRAFT-first reviews are valid even on tenants
        that allow auto-activation."""
        tenant = _seed_tenant(auto_activate_flag=True)
        resolved = self._capture_workflow_input(
            tenant=tenant,
            caller_auto_activate=False,
        )
        assert resolved["resolved_auto_activate"] is False
        assert resolved["caller_auto_activate"] is False
        assert resolved["tenant_auto_activate"] is True

    def test_caller_false_tenant_false_resolves_false(self):
        tenant = _seed_tenant(auto_activate_flag=False)
        resolved = self._capture_workflow_input(
            tenant=tenant,
            caller_auto_activate=False,
        )
        assert resolved["resolved_auto_activate"] is False


# ---------------------------------------------------------------------------
# 250.2.A.4 — activation outcome (status=ACTIVE vs DRAFT)
# ---------------------------------------------------------------------------


class TestActivationOutcome(TestCase):
    """The ``_activate_asset_task`` does the actual DRAFT → ACTIVE
    flip only when ``input_data['auto_activate']`` is True. This
    sub-suite exercises the four corners of the truth table by
    invoking the task directly with synthetic input — the resolver
    suite above pins how that input is built."""

    def test_resolved_true_activates_to_ACTIVE(self):
        tenant = _seed_tenant(auto_activate_flag=True)
        user = _seed_user(tenant)
        contract = _seed_active_contract(tenant, user)
        asset = _seed_activatable_asset(
            tenant=tenant,
            user=user,
            contract=contract,
        )
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": True},
        )
        result = AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": True,
                "caller_auto_activate": True,
                "tenant_auto_activate": True,
            },
            instance,
            step,
        )
        assert result["activated"] is True
        asset.refresh_from_db()
        assert asset.status == AssetStatus.ACTIVE

    def test_resolved_false_via_tenant_keeps_DRAFT(self):
        tenant = _seed_tenant(auto_activate_flag=False)
        user = _seed_user(tenant)
        contract = _seed_active_contract(tenant, user)
        asset = _seed_activatable_asset(
            tenant=tenant,
            user=user,
            contract=contract,
        )
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": False},
        )
        result = AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": False,
                "caller_auto_activate": True,
                "tenant_auto_activate": False,
            },
            instance,
            step,
        )
        assert result["activated"] is False
        assert result.get("skipped") is True
        asset.refresh_from_db()
        assert asset.status == AssetStatus.DRAFT, (
            "Tenant flag=False MUST keep the asset in DRAFT even "
            "when the caller passed auto_activate=True."
        )

    def test_resolved_false_via_caller_keeps_DRAFT(self):
        tenant = _seed_tenant(auto_activate_flag=True)
        user = _seed_user(tenant)
        contract = _seed_active_contract(tenant, user)
        asset = _seed_activatable_asset(
            tenant=tenant,
            user=user,
            contract=contract,
        )
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": False},
        )
        result = AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": False,
                "caller_auto_activate": False,
                "tenant_auto_activate": True,
            },
            instance,
            step,
        )
        assert result["activated"] is False
        asset.refresh_from_db()
        assert asset.status == AssetStatus.DRAFT


# ---------------------------------------------------------------------------
# 250.2.A.3 — ASSET_AUTO_ACTIVATED audit event
# ---------------------------------------------------------------------------


class TestAutoActivatedAudit(TestCase):
    """``ASSET_AUTO_ACTIVATED`` MUST fire exactly when the activation
    actually succeeds via the auto-activate path. It MUST NOT fire on
    skip paths (caller-False / tenant-False / can_activate-blocked)."""

    def _seed(self, *, tenant_flag: bool):
        tenant = _seed_tenant(auto_activate_flag=tenant_flag)
        user = _seed_user(tenant)
        contract = _seed_active_contract(tenant, user)
        asset = _seed_activatable_asset(
            tenant=tenant,
            user=user,
            contract=contract,
        )
        return tenant, user, asset

    def _audit_rows_for_asset(self, asset: Asset):
        return list(
            AuditEvent.objects.filter(
                tenant=asset.tenant,
                action=audit_event_types.ASSET_AUTO_ACTIVATED,
                resource_id=asset.id,
            ).order_by("timestamp")
        )

    def test_audit_emitted_on_successful_auto_activation(self):
        tenant, user, asset = self._seed(tenant_flag=True)
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": True},
        )
        AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": True,
                "caller_auto_activate": True,
                "tenant_auto_activate": True,
            },
            instance,
            step,
        )
        rows = self._audit_rows_for_asset(asset)
        assert len(rows) == 1, (
            f"Exactly one ASSET_AUTO_ACTIVATED event MUST fire on "
            f"a successful auto-activation; got {len(rows)}."
        )
        details = rows[0].details_json or {}
        for required_key in (
            "tenant_id",
            "asset_id",
            "workflow_instance_id",
            "previous_status",
            "new_status",
            "dq_status",
            "compliance_status",
            "caller_auto_activate",
            "tenant_auto_activate",
            "resolved_auto_activate",
        ):
            assert required_key in details, (
                f"ASSET_AUTO_ACTIVATED details_json MUST include "
                f"{required_key!r}; got keys "
                f"{list(details.keys())}."
            )
        assert details["previous_status"] == AssetStatus.DRAFT
        assert details["new_status"] == AssetStatus.ACTIVE
        assert details["caller_auto_activate"] is True
        assert details["tenant_auto_activate"] is True
        assert details["resolved_auto_activate"] is True

    def test_audit_NOT_emitted_when_tenant_flag_false(self):
        tenant, user, asset = self._seed(tenant_flag=False)
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": False},
        )
        AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": False,
                "caller_auto_activate": True,
                "tenant_auto_activate": False,
            },
            instance,
            step,
        )
        rows = self._audit_rows_for_asset(asset)
        assert rows == [], (
            "ASSET_AUTO_ACTIVATED MUST NOT fire when the tenant flag "
            "was False — no actual activation happened."
        )

    def test_audit_NOT_emitted_when_caller_false(self):
        tenant, user, asset = self._seed(tenant_flag=True)
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": False},
        )
        AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": False,
                "caller_auto_activate": False,
                "tenant_auto_activate": True,
            },
            instance,
            step,
        )
        assert self._audit_rows_for_asset(asset) == []

    def test_audit_NOT_emitted_when_can_activate_blocked(self):
        """Even with resolved=True, if ``can_activate()`` returns
        False (no contract / contract not VALID / structural-floor
        breach), the activation never fires and ASSET_AUTO_ACTIVATED
        MUST NOT emit. This isolates the audit event from
        gate-blocked paths."""
        tenant = _seed_tenant(auto_activate_flag=True)
        user = _seed_user(tenant)
        # Asset with no contract attached → can_activate returns
        # (False, ["Asset must have an ACTIVE contract"]).
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"no-contract-{uuid.uuid4().hex[:8]}",
            name="No Contract",
            status=AssetStatus.DRAFT,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=user,
        )
        instance, step = _build_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            workflow_input={"auto_activate": True},
        )
        result = AssetCreationWorkflow._activate_asset_task(
            {
                "auto_activate": True,
                "caller_auto_activate": True,
                "tenant_auto_activate": True,
            },
            instance,
            step,
        )
        assert result["activated"] is False
        assert "blockers" in result
        assert self._audit_rows_for_asset(asset) == []
