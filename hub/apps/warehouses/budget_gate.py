"""P7 (openspec add-databricks-cost-guardrails task 7.4, design D3) +
W4.6 (openspec oss-release-remediation, G1) — the provider-agnostic
budget-enforcement seam at the warehouse dispatch surface.

The enforcement DECISION logic (budget rows, the rolling-hour window,
the ledger fallback) is provider estate code — it lives in
``hub.apps.databricks_admin.budget_enforce``, and the provider-boundary
contract (CLAUDE.md / ``warehouses/models.py``) forbids importing estate
code into this app. The dispatch view therefore rides the same registry
inversion as the 7.5 cost-recording seam: this module defines the
consumer side only (the ``BudgetDecision`` shape + the registry +
facade); ``databricks_admin`` registers the REAL enforcer at app-ready.
A future provider estate (Snowflake, ...) registers its own enforcer
the same way — the seam is homed here once, never duplicated per
provider (the Appendix B discipline).

Unregistered = NO gate (``None`` + a warning): budget enforcement is a
provider concept — a provider without one must not have its queries
refused. In the shipped full mode ``databricks_admin`` always registers
the enforcer, so the live-query path keeps its P7 behavior unchanged.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetDecision:
    """The enforcement outcome for one dispatch (the provider-agnostic
    shape — the estate enforcer conforms to it)."""

    mode: str  # "allow" | "block" | "alert"
    consumed: Decimal = Decimal("0")
    budget: Decimal | None = None
    code: str | None = None  # the classified code, when any
    reason: str = ""


#: The enforcer signature — ``(tenant_id, *, warehouse_id, redis_client)``.
BudgetEnforcer = Callable[..., BudgetDecision]

#: A one-slot registry: the most recent enforcer owns the decision
#: (list-held so the slot mutates without ``global``).
_registered_enforcer: list[BudgetEnforcer] = []
_registry_lock = threading.Lock()


def register_budget_enforcer(enforcer: BudgetEnforcer) -> None:
    """Register the provider's real enforcer. Idempotent — ``ready()``
    may run more than once per process (importlib reloads, test setups)."""
    with _registry_lock:
        _registered_enforcer[:] = [enforcer]


def enforce_budget(
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    redis_client: Any = None,
) -> BudgetDecision | None:
    """Decide BLOCK vs ALERT vs allow through the registered enforcer.

    ``None`` when no enforcer is registered — the provider-agnostic
    default (no budget concept → no gate). The warning is the SRE signal
    that a full-mode process lost its enforcer registration.
    """
    with _registry_lock:
        enforcer = _registered_enforcer[0] if _registered_enforcer else None
    if enforcer is None:
        logger.warning(
            "warehouse_budget_enforcer_unregistered: no provider registered "
            "a budget enforcer — dispatch proceeds without a budget gate "
            "(tenant=%s)",
            tenant_id,
        )
        return None
    return enforcer(tenant_id, warehouse_id=warehouse_id, redis_client=redis_client)
