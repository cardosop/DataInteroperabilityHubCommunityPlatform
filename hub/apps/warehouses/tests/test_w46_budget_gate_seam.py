"""W4.6 (openspec oss-release-remediation, G1) — TDD pins for the
provider-agnostic budget-gate seam.

No mocks: the REAL registry + facade. The ready()-wiring pin proves the
inversion end-to-end — after Django app population the estate's REAL
``budget_enforce.enforce_budget`` IS registered, and a tenant with NO
budget row resolves ``BudgetDecision(mode="allow")`` through the real
DB path. The stand-in pin registers a REAL enforcer implementation (a
pure function over the BudgetDecision shape — the execution_targets
"consumer-side stand-in" convention) and restores the estate enforcer
in ``finally`` (module-global registries persist across a batch). The
unregistered default (None) is pinned in
``scripts/tests/test_w46_provider_seams_standalone.py`` — under Django
the estate always registers at app-ready.
"""

from __future__ import annotations

import uuid

import pytest

from hub.apps.tenants.models import Tenant
from hub.apps.warehouses.budget_gate import (
    BudgetDecision,
    enforce_budget,
    register_budget_enforcer,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _restore_estate_enforcer():
    from hub.apps.databricks_admin.budget_enforce import enforce_budget as real_enforcer

    register_budget_enforcer(real_enforcer)


class TestBudgetGateSeam:
    def test_ready_wiring_registers_the_estate_enforcer(self):
        """The inversion end-to-end: the REAL enforcer answers through the
        seam (a tenant with no budget row → allow, ZERO network calls)."""
        tenant = Tenant.objects.create(
            name=f"budget-seam-{uuid.uuid4().hex[:8]}",
            slug=f"budget-seam-{uuid.uuid4().hex[:8]}",
        )
        decision = enforce_budget(str(tenant.id))
        assert decision is not None
        assert isinstance(decision, BudgetDecision)
        assert decision.mode == "allow"  # no budget row → the estate's allow path

    def test_registered_enforcer_receives_the_kwargs(self):
        """A provider's own enforcer owns the decision (the future-provider
        contract) — restored to the estate afterward."""
        seen = {}

        def stand_in(tenant_id, *, warehouse_id=None, redis_client=None):
            seen.update(tenant_id=tenant_id, warehouse_id=warehouse_id)
            return BudgetDecision(mode="block", code="STAND_IN_BLOCKED")

        try:
            register_budget_enforcer(stand_in)
            decision = enforce_budget("t-1", warehouse_id="w-9")
            assert decision.mode == "block"
            assert decision.code == "STAND_IN_BLOCKED"
            assert seen == {"tenant_id": "t-1", "warehouse_id": "w-9"}
        finally:
            _restore_estate_enforcer()
