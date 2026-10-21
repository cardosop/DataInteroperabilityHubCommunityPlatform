"""Phase 11 (openspec add-databricks-control-plane task 11.4) — the dbt
run's DBU estimate into the P7 ledger (design D5).

ONE ``dbt_run`` ledger row per transformation run through the
provider-agnostic cost-recording seam (the 7.5 inversion —
``warehouses.cost_recording.record_cost``) with the ADDITIVE source tag
(the P7 ledger's ``DatabricksCostLedgerSource.DBT_RUN`` choices value).
Stored, not billed — the billing sync appends the truth (the P7
contract).

The exactly-once discipline is the 10.6 terminal transition's: the
run row's ``databricks_dbu`` (an additive nullable column) is the
guard — re-checked inside ``select_for_update`` so two racing passes
still land exactly one ledger row; a second record is a no-op. The
estimate rides the 4.4 heuristic: wall-clock duration x (1 + 0.5 x
workers) x the settings-overridable DBH rate
(``DATABRICKS_DLT_UPDATE_COST_ESTIMATE_DBH_RATE`` shared with the 10.6
estimator — the one DBH-rate setting).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import transaction

if TYPE_CHECKING:
    from hub.apps.transformation.models import PipelineExecution

import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_DBH_RATE = 0.55


def estimate_dbt_run_cost(*, duration_seconds: float, workers: int, dbh_rate: float) -> dict:
    """The duration-x-size-x-rate ESTIMATE (design D5 — stored, not
    billed). The size factor is the 4.4 heuristic (1 + 0.5 x workers);
    workers clamp to zero (a malformed size never invents compute)."""
    try:
        workers = max(0, int(workers))
    except (TypeError, ValueError):
        workers = 0
    duration_seconds = max(0.0, float(duration_seconds))
    size_factor = 1.0 + 0.5 * workers
    rate = float(dbh_rate)
    cost = (duration_seconds / 3600.0) * rate * size_factor
    return {
        "duration_seconds": duration_seconds,
        "size_factor": size_factor,
        "dbh_rate": rate,
        "estimated_cost": round(cost, 6),
        "formula": "duration_hours x dbh_rate x (1 + 0.5 x workers)",
    }


def record_dbt_run_cost(
    run: PipelineExecution,
    *,
    workspace_id: str,
    workers: int,
    dbh_rate: float | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record ONE ledger row for the run — the exactly-once guard is
    ``databricks_dbu`` re-checked under ``select_for_update`` (the 10.6
    discipline). The run's wall-clock duration comes from its own
    started/completed stamps (a run without both is refused — the
    estimate needs a real duration). Best-effort: a ledger-write
    failure never blocks the run's terminal transition (the Phase 273
    discipline); the stored ``databricks_dbu`` is the truth regardless.
    """
    from hub.apps.transformation.models import PipelineExecution

    if run.started_at is None or run.completed_at is None:
        return {"recorded": False, "reason": "no_duration"}

    rate = float(
        dbh_rate
        if dbh_rate is not None
        else getattr(settings, "DATABRICKS_DLT_UPDATE_COST_ESTIMATE_DBH_RATE", _DEFAULT_DBH_RATE)
    )
    duration_seconds = max(0.0, (run.completed_at - run.started_at).total_seconds())
    metrics = estimate_dbt_run_cost(
        duration_seconds=duration_seconds, workers=workers, dbh_rate=rate
    )
    units = round(metrics["estimated_cost"], 6)

    with transaction.atomic():
        locked = PipelineExecution.objects.select_for_update().filter(pk=run.pk).first()
        if locked is None or locked.databricks_dbu is not None:
            return {"recorded": False, "reason": "already_recorded"}
        locked.databricks_dbu = Decimal(str(units))
        locked.save(update_fields=["databricks_dbu"])
        run.refresh_from_db()

    try:
        from hub.apps.warehouses.cost_recording import CostRecord, record_cost

        meta = {"run_id": str(run.id)}
        if extra_meta:
            meta.update(extra_meta)
        record_cost(
            CostRecord(
                tenant_id=str(run.pipeline.tenant_id),
                units=units,
                unit_label="USD_ESTIMATE",
                source="dbt_run",
                workspace_id=workspace_id,
                meta=meta,
            )
        )
    except Exception:
        logger.warning(
            "dbt_run_cost_record_failed",
            extra={"run_id": str(run.id)},
            exc_info=True,
        )

    return {"recorded": True, "units": units}
