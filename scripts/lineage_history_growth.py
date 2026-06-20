#!/usr/bin/env python
"""
Phase 228 F5 (228.F5.8) — wrapper around the canonical capacity
simulation at :mod:`tests.load.lineage_history_growth` (spec
REQ-LIN-F5-005 names that path).

This wrapper exists so quarterly cron jobs scheduled against
``scripts/`` (the legacy canonical location) keep working without
config drift; the actual logic — including the 90-day churn
simulation + 3-year RDS budget projection — lives in the spec-named
module under ``tests/load/``.
"""

from __future__ import annotations

import sys

# Re-export the canonical entry-points so anyone importing
# ``scripts.lineage_history_growth.measure`` keeps working.
sys.path.insert(0, __file__.replace("scripts/lineage_history_growth.py", ""))
from tests.load.lineage_history_growth import (
    GROWTH_THRESHOLD,
    main,
    measure_current_state,
    project_90_day_growth,
    storage_within_rds_budget,
)


# Backward-compat shim: the original ``measure()`` returned a dict
# with a different field name. Keep the function around so any
# pre-existing operator / dashboard glue that imported it doesn't
# break, but delegate the actual computation to the canonical
# module.
def measure() -> dict:
    open_count, total = measure_current_state()
    proj = project_90_day_growth(
        starting_open=open_count,
        starting_total=total,
    )
    budget_3y = storage_within_rds_budget(
        projected_rows=proj["projected_total_3y"],
    )
    growth_factor = (
        round(total / open_count, 4) if open_count > 0 else (1.0 if total == 0 else float("inf"))
    )
    return {
        "phase": "228.F5.8",
        "total_rows": total,
        "open_rows": open_count,
        "closed_rows": total - open_count,
        "growth_factor": growth_factor,
        "growth_threshold": GROWTH_THRESHOLD,
        "invariant_ok": growth_factor <= GROWTH_THRESHOLD or open_count == 0,
        "projection_90d": proj,
        "rds_3y_budget": budget_3y,
        "guidance": (
            "Canonical script lives at tests/load/lineage_history_growth.py "
            "per spec REQ-LIN-F5-005. This wrapper preserves the "
            "scripts/ entry-point for legacy cron jobs."
        ),
    }


__all__ = [
    "GROWTH_THRESHOLD",
    "main",
    "measure",
    "measure_current_state",
    "project_90_day_growth",
    "storage_within_rds_budget",
]


if __name__ == "__main__":
    raise SystemExit(main())
