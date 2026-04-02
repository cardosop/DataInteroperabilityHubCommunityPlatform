"""
Linked-asset warnings when a contract becomes INVALID (Phase 205).

Does not change asset lifecycle status; only merges
``metadata_json.contract_warnings``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from django.utils import timezone

from hub.apps.audit.utils import create_audit_event

if TYPE_CHECKING:
    from hub.apps.contracts.models import Contract


def maybe_apply_invalidation_after_validation(
    contract: "Contract",
    *,
    actor_user=None,
    request=None,
) -> None:
    """
    If *contract* is INVALID, apply linked-asset warnings + audit.

    Single entry point for service, REST validate, and post-job persistence.
    """
    from hub.apps.contracts.models import ValidationStatus

    vs = contract.validation_status
    if hasattr(vs, "value"):
        vs = vs.value
    if str(vs) != str(ValidationStatus.INVALID):
        return
    apply_linked_contract_invalidation_warnings(
        contract, actor_user=actor_user, request=request
    )


def persist_contract_validation_job_result(job_obj: Any, result: Dict[str, Any]) -> None:
    """
    After a successful CONTRACT_VALIDATION RQ job, copy CLI outcome onto Contract.

    Async validate previously left the contract row unchanged; without this,
    INVALID never reaches the DB and asset warnings never run for async flows.
    """
    from hub.apps.contracts.models import Contract

    if result.get("status") != "completed":
        return
    contract_id = result.get("contract_id")
    if not contract_id and getattr(job_obj, "resource_id", None) is not None:
        contract_id = str(job_obj.resource_id)
    if not contract_id:
        return
    try:
        contract = Contract.objects.get(id=contract_id)
    except (Contract.DoesNotExist, ValueError, TypeError):
        return

    vs = result.get("validation_status")
    if vs is None:
        return
    if hasattr(vs, "value"):
        vs = vs.value

    contract.validation_status = vs
    contract.validation_errors = result.get("errors") or []
    contract.validation_warnings = result.get("warnings") or []
    contract.last_validated_at = timezone.now()
    cli_v = result.get("cli_version")
    update_fields = [
        "validation_status",
        "validation_errors",
        "validation_warnings",
        "last_validated_at",
        "updated_at",
    ]
    if cli_v is not None:
        contract.cli_version = cli_v
        update_fields.insert(-1, "cli_version")
    contract.save(update_fields=update_fields)

    maybe_apply_invalidation_after_validation(
        contract, actor_user=getattr(job_obj, "created_by", None)
    )


def apply_linked_contract_invalidation_warnings(
    contract: "Contract",
    *,
    actor_user=None,
    request=None,
) -> List[str]:
    """
    For each asset linked to *contract*, append a warning entry and emit audit.

    Returns:
        Affected asset IDs (strings).
    """
    from hub.apps.assets.models import Asset

    now_iso = timezone.now().isoformat()
    warning_entry: Dict[str, Any] = {
        "contract_id": str(contract.id),
        "warning": "LINKED_CONTRACT_INVALID",
        "invalidated_at": now_iso,
    }

    qs = Asset.objects.filter(contracts__id=contract.id).distinct()
    affected: List[str] = []

    for asset in qs.iterator(chunk_size=50):
        affected.append(str(asset.id))
        raw_meta = asset.metadata_json
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        raw_cw = meta.get("contract_warnings") or []
        warnings = [w for w in raw_cw if isinstance(w, dict)]
        warnings = [
            w for w in warnings if w.get("contract_id") != str(contract.id)
        ]
        warnings.append(warning_entry)
        merged = {**meta, "contract_warnings": warnings}
        Asset.objects.filter(pk=asset.pk).update(metadata_json=merged)

    if affected:
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_INVALIDATED",
            actor_user=actor_user,
            tenant=getattr(contract, "tenant", None),
            resource_id=str(contract.id),
            result="WARNING",
            details={
                "contract_id": str(contract.id),
                "affected_asset_ids": affected,
            },
            request=request,
        )

    return affected
