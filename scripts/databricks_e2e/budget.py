"""Phase 9 (task 9.2, design D1) — the hard-budget pre-flight.

Pure arithmetic, deliberately network-free: the projected run cost is the
sum of the requested legs' DBU estimates times a safety multiplier, and
``check_budget`` refuses anything above the ceiling BEFORE any create
call. The workflow invokes ``python -m scripts.databricks_e2e.budget`` as
its FIRST sandbox step — exit 1 (and the run dies) when the ceiling
refuses, so creating external infrastructure can never outrun the budget.

Fail-closed: a missing/unset ``DATABRICKS_E2E_BUDGET_DBUS`` ceiling
resolves to ZERO — every projected run is refused until the ceiling
secret exists.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

# Per-leg DBU estimates (planning-grade; the first instrumented runs
# refine them — design open question #1). The workflow's run covers all
# three legs.
LEG_DBUS: dict[str, int] = {
    "journey": 8,
    "contracts": 4,
    "overhead": 2,
}
ALL_LEGS = tuple(LEG_DBUS)
DEFAULT_MULTIPLIER = Decimal("1.25")


class BudgetExceeded(RuntimeError):
    """The projected run cost exceeds the hard ceiling."""


def projected_run_cost(
    legs,
    dbu_table: dict | None = None,
    multiplier=1.0,
) -> Decimal:
    """Sum ONLY the requested legs' estimates times the multiplier.

    An unknown leg name is refused (a typo'd leg must never make the
    projection cheaper than the real run).
    """
    table = LEG_DBUS if dbu_table is None else dbu_table
    for leg in legs:
        if leg not in table:
            raise ValueError(f"unknown budget leg {leg!r} (known: {sorted(table)})")
    total = sum(Decimal(table[leg]) for leg in legs)
    return total * Decimal(str(multiplier))


def check_budget(projected, ceiling) -> None:
    """Raise ``BudgetExceeded`` when the projection is above the ceiling;
    at-or-under passes."""
    if projected > ceiling:
        raise BudgetExceeded(f"projected {projected} DBU exceeds the hard ceiling of {ceiling} DBU")


def main() -> int:
    """The workflow's pre-flight CLI: project ALL legs with the env
    multiplier against the env ceiling; exit 1 when refused."""
    ceiling_raw = (os.environ.get("DATABRICKS_E2E_BUDGET_DBUS") or "0").strip()
    ceiling = Decimal(ceiling_raw or "0")
    multiplier_raw = os.environ.get("DATABRICKS_E2E_BUDGET_MULTIPLIER", str(DEFAULT_MULTIPLIER))
    projected = projected_run_cost(ALL_LEGS, multiplier=Decimal(multiplier_raw))
    try:
        check_budget(projected, ceiling)
    except BudgetExceeded as exc:
        print(f"BUDGET REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"BUDGET OK: projected {projected} DBU <= ceiling {ceiling} DBU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
