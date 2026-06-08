"""
285.6.2 — Shared cost tracking for dlt pipeline runs.

Tracks bytes processed, rows loaded, and estimated cost per run.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PipelineRunCost:
    """Cost tracking for a single dlt pipeline run."""

    bytes_processed: int = 0
    rows_loaded: int = 0
    bytes_written: int = 0
    dlt_loads: int = 0
    estimated_cost_usd_cents: int = 0


@dataclass
class TenantCostTracker:
    """Per-tenant cost tracking across pipeline runs."""

    tenant_id: str
    runs: Dict[str, PipelineRunCost] = field(default_factory=dict)
    total_bytes_processed: int = 0
    total_cost_usd_cents: int = 0

    def record_run(self, run_id: str, cost: PipelineRunCost) -> None:
        self.runs[run_id] = cost
        self.total_bytes_processed += cost.bytes_processed
        self.total_cost_usd_cents += cost.estimated_cost_usd_cents

    def last_n_cost(self, n: int = 10) -> int:
        """Average cost of last N runs."""
        recent = list(self.runs.values())[-n:]
        if not recent:
            return 0
        return sum(r.estimated_cost_usd_cents for r in recent) // len(recent)


# In-memory tracker — replaced by DB model in Phase 4
_tracker: Dict[str, TenantCostTracker] = {}


def get_tenant_tracker(tenant_id: str) -> TenantCostTracker:
    if tenant_id not in _tracker:
        _tracker[tenant_id] = TenantCostTracker(tenant_id=tenant_id)
    return _tracker[tenant_id]
