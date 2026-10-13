"""Phase 6 (openspec wire-databricks-dlt-movement task 6.5) — pre-export
ODCS contract validation (design D4).

The export must never write data the source did not validate: BEFORE any
movement work (no credential resolution, no staging volume, no pipeline),
every contract-bearing source in the export's ``source_scope`` must carry
an ACTIVE ODCS contract whose CLI validation status is VALID or
WARNING_ONLY. All violations are aggregated into ONE classified error —
every offending source is reported, never fail-fast on the first.

The validation is PURE: reads only, zero side effects by construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hub.apps.contracts.models import Contract

if TYPE_CHECKING:
    from hub.apps.scheduled_export.models import ScheduledExport

# The validation statuses the pre-flight accepts (the same set the Asset
# lifecycle requires for an ACTIVE asset — an INVALID/ERROR/unvalidated
# contract is not a validated source).
_ACCEPTED_VALIDATION_STATUSES = {"VALID", "WARNING_ONLY"}


class ExportContractValidationError(Exception):
    """The source's ODCS contract(s) failed pre-export validation."""

    code = "EXPORT_CONTRACT_VALIDATION_FAILED"

    def __init__(self, violations: list[dict[str, Any]]):
        self.violations = violations
        super().__init__(
            "pre-export ODCS contract validation failed — "
            f"{len(violations)} violation(s): "
            + "; ".join(f"{v['source']} ({v['reason']})" for v in violations)
        )


def _validate_contract(
    contract: Contract | None, *, source: str, asset_id: str | None = None
) -> dict | None:
    """Return a violation dict for the contract, or None when it passes."""
    if contract is None:
        return {"source": source, "asset_id": asset_id, "reason": "no ACTIVE contract"}
    if contract.original_spec_type != "ODCS":
        return {
            "source": source,
            "asset_id": asset_id,
            "contract_id": str(contract.id),
            "reason": f"the ACTIVE contract is {contract.original_spec_type}, not ODCS",
        }
    if contract.validation_status not in _ACCEPTED_VALIDATION_STATUSES:
        return {
            "source": source,
            "asset_id": asset_id,
            "contract_id": str(contract.id),
            "reason": (
                f"validation_status={contract.validation_status or 'unvalidated'} "
                "— VALID or WARNING_ONLY required"
            ),
        }
    return None


def validate_export_contracts(export: ScheduledExport) -> list[Contract]:
    """Validate the ODCS contracts of every contract-bearing source in the
    export's scope. Returns the validated contracts, or raises
    ``ExportContractValidationError`` aggregating every violation.

    Zero side effects: reads only.
    """
    from hub.apps.assets.models import Asset
    from hub.apps.datasets.models import Dataset

    scope = export.source_scope or {}
    violations: list[dict[str, Any]] = []
    validated: list[Contract] = []

    asset_ids = scope.get("asset_ids", []) or []
    for asset_id in asset_ids:
        asset = Asset.objects.filter(id=asset_id, tenant=export.tenant).first()
        if asset is None:
            violations.append(
                {"source": f"asset:{asset_id}", "asset_id": asset_id, "reason": "asset not found"}
            )
            continue
        contract = asset.contracts.filter(status="ACTIVE").order_by("-version").first()
        violation = _validate_contract(contract, source=f"asset:{asset_id}", asset_id=asset_id)
        if violation:
            violations.append(violation)
        else:
            validated.append(contract)

    dataset_ids = scope.get("dataset_ids", []) or []
    for dataset_id in dataset_ids:
        dataset = Dataset.objects.filter(id=dataset_id, tenant=export.tenant).first()
        if dataset is None:
            violations.append({"source": f"dataset:{dataset_id}", "reason": "dataset not found"})
            continue
        contract = (
            dataset.asset.contracts.filter(status="ACTIVE").order_by("-version").first()
            if dataset.asset_id
            else None
        )
        violation = _validate_contract(
            contract,
            source=f"dataset:{dataset_id}",
            asset_id=str(dataset.asset_id) if dataset.asset_id else None,
        )
        if violation:
            violations.append(violation)
        else:
            validated.append(contract)

    contract_id = scope.get("contract_id")
    if contract_id:
        contract = Contract.objects.filter(id=contract_id, tenant=export.tenant).first()
        if contract is not None and contract.status != "ACTIVE":
            # The referenced contract must be the ACTIVE one — a DRAFT or
            # RETIRED reference is refused even when its validation bits pass.
            violations.append(
                {
                    "source": f"contract:{contract_id}",
                    "contract_id": str(contract.id),
                    "reason": f"the referenced contract is {contract.status}, not ACTIVE",
                }
            )
        else:
            violation = _validate_contract(contract, source=f"contract:{contract_id}")
            if violation:
                violations.append(violation)
            elif contract is not None:
                validated.append(contract)

    if violations:
        raise ExportContractValidationError(violations)
    return validated
