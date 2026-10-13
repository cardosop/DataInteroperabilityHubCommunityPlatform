"""Phase 9 (openspec add-databricks-live-ci-sandbox task 9.3, design D2) —
the ordered journey plan: the leg registry, the sandbox discovery
selector, and the per-leg evidence/report schema.

Pure module — no Django, no network: the structure pins
(``test_structure.py``) assert these exact values, and the live legs
(``test_journey.py``) walk the registry in order. The leg order is
DEPENDENCY-DRIVEN: the warehouse-minimum leg precedes the SQL-driven
legs (schema/table creation and the billing-usage sync both need a
RUNNING warehouse), so it runs second — the title lists the surfaces,
the registry pins the execution order.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from hub.apps.databricks_admin.e2e_tooling.sandbox import SANDBOX_PREFIX

# ── The environment gate (the 9.4 conftest's shared contract) ─────────

E2E_GATE = "DATABRICKS_E2E"
WORKSPACE_HOST_ENV = "DATABRICKS_E2E_WORKSPACE_HOST"
WORKSPACE_TOKEN_ENV = "DATABRICKS_E2E_WORKSPACE_TOKEN"


def gate_reason() -> str | None:
    """Why the live journey cannot run — None when the environment is
    armed (the W16 policy governs absence: CI raises, local skips,
    never a silent pass)."""
    if os.environ.get(E2E_GATE, "").strip() != "1":
        return (
            f"{E2E_GATE}=1 is required "
            "(the nightly workflow arms it; the W16 policy governs absence)"
        )
    missing = [
        name
        for name in (WORKSPACE_HOST_ENV, WORKSPACE_TOKEN_ENV)
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        return f"missing sandbox credentials: {', '.join(missing)} (workflow environment secrets)"
    return None


# ── The ordered legs ──────────────────────────────────────────────────

JOURNEY_LEGS: tuple[str, ...] = (
    "workspace_register",  # discover the sandbox by convention name + client handshake
    "warehouse_minimum",  # the minimal serverless warehouse (prereq for the SQL legs)
    "uc_schema_table_grant",  # CREATE SCHEMA/TABLE via SQL + the grants REST leg
    "uc_verify",  # read-back over the same surfaces
    "uc_destroy",  # DROP TABLE/SCHEMA — the sandbox UC estate is gone
    "job_run_now",  # create → run-now → terminal
    "dlt_pipeline_lifecycle",  # create → start → stop
    "budget_sync",  # system.billing.usage delta via the statement API
    "delta_sharing_reference_client",  # the reference client vs the native share
)

# Every leg name must be a valid pytest-importable id AND a valid JSON key
# (the evidence schema below keys on it).
assert all(re.match(r"^[a-z][a-z0-9_]*$", leg) for leg in JOURNEY_LEGS)

# ── Sandbox discovery ─────────────────────────────────────────────────

#: The workspace-name pattern the run's sandbox carries. The suite
#: RE-DISCOVERS the sandbox by the convention (no handoff file — the
#: workflow's create step printed the envelope; the naming convention is
#: the single source of truth, hub/apps/databricks_admin/e2e_tooling/sandbox.py).
SANDBOX_PATTERN = re.compile(rf"^{re.escape(SANDBOX_PREFIX)}")


def owned_sandbox_rows(rows: list[dict]) -> list[dict]:
    """The discovery selector: every account workspace matching the
    convention prefix (and ONLY those — a real customer workspace is
    never selected)."""
    return [
        row for row in rows if SANDBOX_PATTERN.match(str(row.get("workspace_name", "")))
    ]


def resolve_sandbox(rows: list[dict], run_id: str) -> dict:
    """Resolve THE run's sandbox row: the convention match whose name
    carries this run's id (the workflow's GITHUB_RUN_ID). Raises
    ValueError when absent or ambiguous — the journey must fail, never
    guess."""
    matches = [
        row
        for row in owned_sandbox_rows(rows)
        if str(run_id) in str(row.get("workspace_name", ""))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one sandbox for run {run_id!r}, found {len(matches)}"
        )
    return matches[0]


# ── The evidence / report schema ──────────────────────────────────────

REPORT_VERSION = 1

EMPTY_REPORT: dict[str, Any] = {
    "schema_version": REPORT_VERSION,
    "run_id": None,
    "sandbox": None,  # {"workspace_name": ..., "workspace_id": ..., "workspace_url": ...}
    "legs": {
        leg: {"status": "pending", "requests": 0, "evidence": []}
        for leg in JOURNEY_LEGS
    },
    "outcome": None,  # "PASSED" | "FAILED" | "SKIPPED" — stamped at session end
}


def report_json(report: dict[str, Any]) -> str:
    """Serialize the report for the 9.6 artifact (deterministic keys)."""
    return json.dumps(report, sort_keys=True, indent=2, default=str)
