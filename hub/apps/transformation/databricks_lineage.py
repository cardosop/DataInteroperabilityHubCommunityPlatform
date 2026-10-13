"""Phase 11 (openspec add-databricks-control-plane task 11.4) — the dbt
run's lineage edge into the Hub lineage (design D5).

The run's source→result relationship records as a TRANSFORMATION
``LineageEdge`` through the SANCTIONED contract-lineage write path
(``contracts.lineage_edit_service.apply_lineage_patch`` — the
full-state patch; direct ``LineageEdge`` writes are forbidden outside
the sync handler, REQ-LIN-002). The edge's ``transformation_ref``
carries the pipeline id and ``job_ref`` the run id.

Target-agnostic: BOTH the local executors and the Databricks targets
record through this ONE function — the local path gains the lineage it
never wrote (the design's "same lineage records the local executors
write" was aspirational — reconciled in the 11.4 record). The edge
signature is deduplicated (a re-record is a no-op); a run whose result
asset carries no ACTIVE contract records nothing (never an invented
contract — the REQ-LIN-002 discipline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hub.apps.transformation.models import PipelineExecution

import structlog

logger = structlog.get_logger(__name__)


def _current_edges(contract) -> list[dict[str, Any]]:
    """The contract's open edge universe — the ``_edge_row_to_dict``
    convention of the lineage edit service (read-only; the patch owns
    the write)."""
    from django.db.models import Q

    from hub.apps.contracts.models import LineageEdge

    rows = LineageEdge.objects.filter(
        tenant_id=contract.tenant_id,
        valid_to__isnull=True,
    ).filter(Q(source_contract_id=contract.id) | Q(target_contract_id=contract.id))
    return [
        {
            "source_contract": (str(row.source_contract_id) if row.source_contract_id else None),
            "target_contract": (str(row.target_contract_id) if row.target_contract_id else None),
            "source_model": row.source_model or "",
            "source_field": row.source_field or "",
            "target_model": row.target_model or "",
            "target_field": row.target_field or "",
            "edge_type": row.edge_type,
            "transformation_ref": row.transformation_ref or "",
            "job_ref": row.job_ref or "",
        }
        for row in rows
    ]


def _signature(edge: dict[str, Any]) -> tuple:
    """The stable dedup signature (the service's ``_edge_signature``
    convention)."""
    return (
        edge.get("source_contract") or "",
        edge.get("source_model") or "",
        edge.get("source_field") or "",
        edge.get("target_contract") or "",
        edge.get("target_model") or "",
        edge.get("target_field") or "",
        edge.get("edge_type") or "reference",
    )


def record_transformation_lineage(run: PipelineExecution, *, user=None) -> dict[str, Any]:
    """Record the run's source→result TRANSFORMATION edge.

    The result asset's ACTIVE contract is the patch target; the source
    asset's ACTIVE contract anchors the source side (None when absent
    — the external-source convention). Existing edges survive (the
    full-state patch); a duplicate signature is a no-op.
    """
    from hub.apps.contracts.lineage_edit_service import apply_lineage_patch
    from hub.apps.contracts.models import Contract

    if run.result_asset_id is None:
        return {"recorded": False, "reason": "no_result_asset"}
    target = (
        Contract.objects.filter(asset_id=run.result_asset_id, status="ACTIVE")
        .order_by("-version")
        .first()
    )
    if target is None:
        logger.warning(
            "dbt_lineage_skipped_no_target_contract",
            extra={"run_id": str(run.id), "asset_id": str(run.result_asset_id)},
        )
        return {"recorded": False, "reason": "no_target_contract"}

    source = (
        Contract.objects.filter(asset_id=run.asset_id, status="ACTIVE").order_by("-version").first()
        if run.asset_id
        else None
    )

    edge = {
        "source_contract": str(source.id) if source is not None else None,
        "target_contract": str(target.id),
        "source_model": "",
        "source_field": "",
        "target_model": "",
        "target_field": "",
        "edge_type": "transformation",
        "transformation_ref": str(run.pipeline_id),
        "job_ref": str(run.id),
    }

    existing = _current_edges(target)
    if any(_signature(e) == _signature(edge) for e in existing):
        return {"recorded": False, "reason": "duplicate"}

    result = apply_lineage_patch(
        contract=target,
        desired_edges=[*existing, edge],
        user=user,
    )
    return {"recorded": True, "added": result.get("added")}
