"""
Phase 260.4.D — schema-drift comparison helper for dataset refresh flow.

Wraps :class:`SchemaCompareService` so the
``POST /datasets/{id}/refresh-from-file/`` endpoint can produce a
stable drift dict against the active Contract linked to a dataset's
asset, without re-implementing the workflow's compare logic.

Two design choices worth noting:

1. **No contract → ``severity=NONE`` with explicit ``has_contract=False``**.
   The asset may legitimately have no contract attached — the
   refresh action is allowed to proceed in that case (the dataset
   evolves freely until a contract anchors a schema). Surfacing
   ``has_contract`` lets the FE banner say "no drift to evaluate"
   instead of silently masking the absence as "clean".

2. **Active contracts only**. The compare uses the first
   ``Contract`` linked to the asset with ``status=ACTIVE`` (preferring
   the highest version when multiple are active). DRAFT / RETIRED
   contracts are intentionally excluded — drift against a draft is
   an early-warning signal that doesn't belong in the audit log.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

from hub.apps.datasets.models import Dataset


def compute_dataset_contract_drift(dataset: Dataset) -> Dict[str, Any]:
    """Compute schema drift between *dataset* and its asset's active contract.

    Returns a JSON-serialisable drift dict with the following keys:

    * ``has_contract``: bool — True if an ACTIVE contract was found
      and the comparison ran; False otherwise.
    * ``contract_id``: str | None — the contract row used for the
      comparison (None when ``has_contract`` is False).
    * ``detected``: bool — True iff the schemas disagree on at least
      one field.
    * ``severity``: ``"NONE"`` / ``"WARN"`` / ``"FAIL"``.
    * ``missing_fields`` / ``extra_fields`` / ``type_mismatches`` /
      ``structural_incompatibility``: as documented on
      :class:`SchemaDriftResult`.

    The function is pure: no DB writes, no audit emission, no S3
    fetches. Composable by the action's audit + response layer.
    """
    from hub.apps.contracts.models import Contract, ContractStatus
    from hub.apps.contracts.services.schema_compare import SchemaCompareService

    if not dataset.asset_id:
        return _no_contract_drift(reason="dataset has no asset link")

    contract: Optional[Contract] = (
        Contract.objects.filter(
            tenant_id=dataset.tenant_id,
            asset_id=dataset.asset_id,
            status=ContractStatus.ACTIVE,
        )
        .order_by("-version", "-created_at")
        .first()
    )
    if contract is None:
        return _no_contract_drift(reason="no active contract for asset")

    result = SchemaCompareService.compare(
        contract_schema=contract.hub_contract_json or {},
        inferred_schema=dataset.schema_json or {},
    )
    drift = result.to_dict()
    return {
        "has_contract": True,
        "contract_id": str(contract.id),
        **drift,
    }


def _no_contract_drift(*, reason: str) -> Dict[str, Any]:
    return {
        "has_contract": False,
        "contract_id": None,
        "detected": False,
        "severity": "NONE",
        "missing_fields": [],
        "extra_fields": [],
        "type_mismatches": [],
        "structural_incompatibility": False,
        "skip_reason": reason,
    }
