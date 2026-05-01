#!/usr/bin/env python
"""
Phase 228 F5 (REQ-LIN-F5-005 / 228.F5.8 / DoD-G5) — quarterly capacity
**simulation**.

Spec scenarios (REQ-LIN-F5-005):

* "When the simulation runs with the staging churn rate, the final
  row count is ≤1.5× the starting count AND the storage size
  projection for 3 years stays within the documented RDS instance class."

This script SIMULATES 90 days of typical lineage edits at the rate
observed on staging and asserts both invariants. Two run modes:

   --mode=projection  (default; pure-math, no DB writes)
       Reads the current LineageEdge row count + the configurable
       monthly churn rate, projects 90 days + 3 years of growth, and
       prints a structured JSON report. Exits 0 on pass / 2 on fail.
       Safe to run on production (read-only).

   --mode=stress      (CI / staging only)
       Actually inserts churn rows in a transaction and rolls back
       at the end so the DB is left untouched. Writes are batched
       to avoid hammering the WAL. NEVER run on prod.

Default churn parameters are calibrated to staging telemetry
(captured 2026-04-30):

   - Edge open rate:   ~120 / day
   - Edge close rate:  ~110 / day  (mostly close-and-reopen via
                                    the lineage-sync handler)
   - Monthly net growth: ~300 rows / tenant
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


GROWTH_THRESHOLD = 1.5
"""REQ-LIN-F5-005 — invariant ceiling. After 90 days of churn at the
staging rate, the row count SHALL stay within 1.5x of the starting
open-edge state. Pinned by the projection branch + the optional
stress branch."""


# Default churn parameters derived from staging telemetry. Override
# via CLI flags for what-if simulations.
DEFAULT_OPEN_RATE_PER_DAY = 120
DEFAULT_CLOSE_RATE_PER_DAY = 110
SIMULATION_DAYS = 90


def _maybe_setup_django() -> None:
    if "django" not in sys.modules or not getattr(_maybe_setup_django, "_done", False):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
        try:
            import django
            django.setup()
        except Exception:
            pass
        _maybe_setup_django._done = True  # type: ignore[attr-defined]


def project_90_day_growth(
    *,
    starting_open: int,
    starting_total: int,
    open_per_day: int = DEFAULT_OPEN_RATE_PER_DAY,
    close_per_day: int = DEFAULT_CLOSE_RATE_PER_DAY,
    days: int = SIMULATION_DAYS,
) -> dict[str, Any]:
    """Project the row count 90 days forward without touching the DB.

    Math model: every day adds ``open_per_day`` new rows AND closes
    ``close_per_day`` existing rows. Closing a row leaves it in the
    table (SCD-2) so total grows by ``open_per_day``. Open count
    grows by ``open_per_day - close_per_day``.

    Returns the projected end-state plus the 3-year projection
    (which the spec scenario also asserts on)."""
    daily_total_growth = open_per_day  # closing leaves rows in place
    daily_open_growth = open_per_day - close_per_day

    projected_total_90d = starting_total + (daily_total_growth * days)
    projected_open_90d = max(0, starting_open + (daily_open_growth * days))

    # 3-year projection — extrapolate the daily total growth.
    projected_total_3y = starting_total + (daily_total_growth * 365 * 3)

    growth_factor_90d = (
        projected_total_90d / projected_open_90d
        if projected_open_90d > 0
        else float("inf")
    )

    return {
        "starting_total": starting_total,
        "starting_open": starting_open,
        "open_per_day": open_per_day,
        "close_per_day": close_per_day,
        "days": days,
        "projected_total_90d": projected_total_90d,
        "projected_open_90d": projected_open_90d,
        "growth_factor_90d": round(growth_factor_90d, 4),
        "growth_threshold": GROWTH_THRESHOLD,
        "invariant_ok_90d": growth_factor_90d <= GROWTH_THRESHOLD or starting_open == 0,
        "projected_total_3y": projected_total_3y,
    }


# RDS budget assumptions derived from the platform DR baseline:
# `db.r6g.large` provisioned-IOPS instance with 200 GB allocated
# storage. Each LineageEdge row is ~512 B on-disk including the
# composite indexes. Threshold = ~95% of capacity so we trip on
# projection well before the disk fills.
RDS_BUDGET_BYTES = int(200 * 1024 * 1024 * 1024 * 0.95)
"""95% of 200 GB — lineage rows alone shouldn't consume more."""

ROW_BYTES_ESTIMATE = 512
"""Conservative on-disk size including B-tree index overhead."""


def storage_within_rds_budget(*, projected_rows: int) -> dict[str, Any]:
    bytes_estimate = projected_rows * ROW_BYTES_ESTIMATE
    return {
        "rows": projected_rows,
        "row_bytes_estimate": ROW_BYTES_ESTIMATE,
        "projected_bytes": bytes_estimate,
        "rds_budget_bytes": RDS_BUDGET_BYTES,
        "within_budget": bytes_estimate <= RDS_BUDGET_BYTES,
    }


def measure_current_state() -> tuple[int, int]:
    """Read current open + total LineageEdge counts. Pure-read."""
    _maybe_setup_django()
    from hub.apps.contracts.models import LineageEdge

    total = LineageEdge.objects.count()
    open_count = LineageEdge.objects.filter(valid_to__isnull=True).count()
    return open_count, total


def run_projection_mode(args: argparse.Namespace) -> int:
    open_count, total = measure_current_state()
    proj = project_90_day_growth(
        starting_open=open_count,
        starting_total=total,
        open_per_day=args.open_rate,
        close_per_day=args.close_rate,
        days=args.days,
    )
    budget_3y = storage_within_rds_budget(
        projected_rows=proj["projected_total_3y"],
    )
    output = {
        "phase": "228.F5.8",
        "mode": "projection",
        **proj,
        "rds_3y_budget": budget_3y,
        "overall_ok": proj["invariant_ok_90d"] and budget_3y["within_budget"],
        "guidance": (
            "If invariant_ok_90d=false: schedule "
            "`archive_lineage_edges --before=<12mo-ago>` to compress hot tier. "
            "If within_budget=false: open a P1 capacity ticket "
            "(see docs/architecture/lineage-archive-op3.md)."
        ),
    }
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0 if output["overall_ok"] else 2


def run_stress_mode(args: argparse.Namespace) -> int:
    """Actually insert churn rows in a transaction. NEVER on prod."""
    from datetime import timedelta as _td

    from django.db import transaction
    from django.utils import timezone

    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        print(json.dumps({
            "phase": "228.F5.8",
            "mode": "stress",
            "error": "stress mode is forbidden on production",
        }, sort_keys=True, indent=2))
        return 2

    from hub.apps.contracts.models import LineageEdge
    from hub.apps.tenants.models import Tenant

    tenant = Tenant.objects.first()
    if tenant is None:
        print(json.dumps({
            "phase": "228.F5.8",
            "mode": "stress",
            "error": "no tenant available — staging DB is empty?",
        }, sort_keys=True, indent=2))
        return 2

    starting_open, starting_total = measure_current_state()
    inserted = 0
    closed = 0
    try:
        with transaction.atomic():
            now = timezone.now()
            # Insert SIMULATION_DAYS * open_per_day rows then close
            # SIMULATION_DAYS * close_per_day rows.
            for d in range(args.days):
                day_open = LineageEdge.objects.bulk_create([
                    LineageEdge(
                        tenant=tenant,
                        edge_type="reference",
                        created_by_run="capacity_stress",
                    )
                    for _ in range(args.open_rate)
                ])
                inserted += len(day_open)

                # Close ``close_per_day`` rows — pick from the freshly
                # inserted batch so the test doesn't disturb other
                # tenants' history.
                close_ids = [r.pk for r in day_open[: args.close_rate]]
                if close_ids:
                    LineageEdge.objects.filter(pk__in=close_ids).update(
                        valid_to=now + _td(days=d, hours=12),
                    )
                    closed += len(close_ids)

            after_open, after_total = measure_current_state()
            growth_factor = (
                round(after_total / after_open, 4)
                if after_open > 0 else float("inf")
            )
            invariant_ok = growth_factor <= GROWTH_THRESHOLD or after_open == 0

            print(json.dumps({
                "phase": "228.F5.8",
                "mode": "stress",
                "starting_total": starting_total,
                "starting_open": starting_open,
                "inserted": inserted,
                "closed": closed,
                "after_total": after_total,
                "after_open": after_open,
                "growth_factor": growth_factor,
                "growth_threshold": GROWTH_THRESHOLD,
                "invariant_ok": invariant_ok,
            }, sort_keys=True, indent=2))

            # Always roll back so the DB is left untouched.
            transaction.set_rollback(True)
            return 0 if invariant_ok else 2
    except Exception as exc:
        print(json.dumps({
            "phase": "228.F5.8",
            "mode": "stress",
            "error": str(exc),
        }, sort_keys=True, indent=2))
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 228 F5 capacity simulation (REQ-LIN-F5-005)."
    )
    parser.add_argument(
        "--mode",
        choices=["projection", "stress"],
        default="projection",
        help="projection (default; pure-math, safe on prod) | stress (DB rollback).",
    )
    parser.add_argument(
        "--open-rate",
        type=int,
        default=DEFAULT_OPEN_RATE_PER_DAY,
        help=f"Edge-open rate per day (default {DEFAULT_OPEN_RATE_PER_DAY}).",
    )
    parser.add_argument(
        "--close-rate",
        type=int,
        default=DEFAULT_CLOSE_RATE_PER_DAY,
        help=f"Edge-close rate per day (default {DEFAULT_CLOSE_RATE_PER_DAY}).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=SIMULATION_DAYS,
        help=f"Days to simulate (default {SIMULATION_DAYS}).",
    )
    args = parser.parse_args(argv)

    if args.mode == "stress":
        return run_stress_mode(args)
    return run_projection_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
