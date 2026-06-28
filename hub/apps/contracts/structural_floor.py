"""
Phase 227 Wave 1 (227.L3) — structural-floor enforcer.

The "structural floor" is the invariant that every persisted contract MUST
carry resolvable structure: at least one ``models[*].fields[*]`` entry OR a
top-level ``schema.fields[*]`` entry. Wave 0 diagnosed contracts that
violated this floor (the "structureless" population); Wave 1 ENFORCES the
floor at the API edge, hard-failing creates and updates that would
otherwise silently persist a structureless row.

Per the 2026-04-30 ungate directive, this floor is **always enforced** —
no feature flag, no per-tenant override, no deprecation period. Customers
who upload structureless contracts must use the Schema editor to add
fields before retrying.

Public API
----------
* :func:`enforce_structural_floor` — accepts the normalized HubContract
  dict + spec metadata. Raises :class:`ValidationError` (the
  ``hub.apps.core.services.base`` flavour) when the floor is violated;
  returns ``None`` otherwise.

Design notes
------------
* The error carries ``code="STRUCTURELESS_CONTRACT"`` so API consumers
  can switch on it without parsing free-form messages.
* ``details.subcode`` distinguishes the cause (ODPS-no-ports vs
  ODCS-no-schema vs generic vs cyclic). This drives the
  remediation copy in the frontend toast / Schema editor deep link.
* ``models_count`` and ``schema_fields_count`` are reported so the
  frontend can render "you uploaded N models with 0 fields" specifics.
* ``remediation_url`` uses the same template pattern as the Wave 0
  notification helper — ops can override per-environment via
  ``STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE``.

Subcode taxonomy
----------------
* ``STRUCTURELESS_ODPS_NO_PORTS`` — ODPS contract whose normalisation
  yielded no models (ports either missing or unresolvable).
* ``STRUCTURELESS_ODCS_NO_SCHEMA`` — ODCS contract with no
  ``schema.fields`` and no ``models[*].fields``.
* ``STRUCTURELESS_CYCLIC_PORTS`` — ODPS contract whose port resolution
  short-circuited on a cycle (Phase 227.L1.7 visited-set hit).
* ``STRUCTURELESS_GENERIC`` — non-ODPS/ODCS spec_type or unrecognised
  shape; ops investigation needed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import logging

from django.conf import settings
from django.db import DatabaseError, InterfaceError, OperationalError

from hub.apps.core.services.base import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants — exported so tests + frontend can import them
# ---------------------------------------------------------------------------

ERROR_CODE = "STRUCTURELESS_CONTRACT"

SUBCODE_ODPS_NO_PORTS = "STRUCTURELESS_ODPS_NO_PORTS"
SUBCODE_ODCS_NO_SCHEMA = "STRUCTURELESS_ODCS_NO_SCHEMA"
SUBCODE_CYCLIC_PORTS = "STRUCTURELESS_CYCLIC_PORTS"
SUBCODE_GENERIC = "STRUCTURELESS_GENERIC"

DEFAULT_SCHEMA_EDITOR_URL_TEMPLATE = (
    "https://stagingmeshant-internal.example.com/contracts/{contract_id}/edit?tab=schema"
)

# When the contract has not yet been persisted (create path), no UUID is
# available; the frontend handles ``{contract_id}`` placeholder by
# routing the user to the editor's "new contract" entry point.
PLACEHOLDER_CONTRACT_ID = "{contract_id}"


# ---------------------------------------------------------------------------
# Subcode classification
# ---------------------------------------------------------------------------


def _count_models_with_fields(payload: dict[str, Any]) -> int:
    """Count models that have at least one field — i.e., contributing
    structure. ``models=[{"fields":[]}]`` counts as 0."""
    models = payload.get("models") or []
    if not isinstance(models, list):
        return 0
    return sum(
        1
        for m in models
        if isinstance(m, dict) and isinstance(m.get("fields"), list) and m["fields"]
    )


def _schema_fields_count(payload: dict[str, Any]) -> int:
    """Count top-level ``schema.fields`` entries."""
    schema_block = payload.get("schema") or {}
    if not isinstance(schema_block, dict):
        return 0
    fields = schema_block.get("fields") or []
    if not isinstance(fields, list):
        return 0
    return len(fields)


def _normalisation_warnings_indicate_cycle(
    warnings: Iterable[str] | None,
) -> bool:
    """Detect Phase 227.L1.7 cyclic-ports warning in the warning list."""
    if not warnings:
        return False
    return any("STRUCTURELESS_CYCLIC_PORTS" in w for w in warnings if w)


def _classify(
    payload: dict[str, Any],
    *,
    spec_type: str | None,
    warnings: Iterable[str] | None,
) -> str:
    """Pick the subcode that best explains why the payload is structureless."""
    spec = (spec_type or "").upper()

    # Cycle takes precedence over the generic ODPS-no-ports — a cycle is
    # actionable in a different way (audit / fix the FK chain) and we
    # want ops to see it surfaced specifically.
    if _normalisation_warnings_indicate_cycle(warnings):
        return SUBCODE_CYCLIC_PORTS

    if spec == "ODPS":
        return SUBCODE_ODPS_NO_PORTS
    if spec == "ODCS":
        return SUBCODE_ODCS_NO_SCHEMA
    return SUBCODE_GENERIC


# ---------------------------------------------------------------------------
# Hint copy
# ---------------------------------------------------------------------------

_HINT_BY_SUBCODE = {
    SUBCODE_ODPS_NO_PORTS: (
        "ODPS contract has no resolvable outputPort schemas. Add at "
        "least one outputPort with a `contract.spec.schema.fields[]`, "
        "`dataSchema.fields[]`, or a `contractId` referencing an "
        "existing ODCS contract."
    ),
    SUBCODE_ODCS_NO_SCHEMA: (
        "ODCS contract has no `schema.fields[]` and no "
        "`models[*].fields[]`. Open the Schema editor to add at least "
        "one model with one field."
    ),
    SUBCODE_CYCLIC_PORTS: (
        "ODPS port resolution detected a cycle (A → B → A). Fix the "
        "circular contractId reference, then retry."
    ),
    SUBCODE_GENERIC: (
        "Contract has no resolvable structure. Add models or schema fields and retry."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _resolve_remediation_url(contract_id: str | None) -> str:
    """Return the Schema-editor deep link for the offending contract."""
    template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        DEFAULT_SCHEMA_EDITOR_URL_TEMPLATE,
    )
    cid = str(contract_id) if contract_id else PLACEHOLDER_CONTRACT_ID
    return template.replace("{contract_id}", cid)


def enforce_structural_floor(
    hub_contract: dict[str, Any] | None,
    *,
    spec_type: str | None,
    spec_version: str | None,
    warnings: Iterable[str] | None = None,
    contract_id: str | None = None,
    tenant_id: str | None = None,
    source: str | None = None,
) -> None:
    """Raise ``ValidationError(code="STRUCTURELESS_CONTRACT")`` if the
    payload violates the structural floor; otherwise return ``None``.

    Phase 274.4 (PR-A): This is now a thin shim that delegates to
    ``StructuralFloorRule.validate_structural_floor()``. Call sites
    will be migrated to invoke the rule directly in PR-B.

    Observability side effects (metrics, audit, logging) remain in
    this shim for backward compatibility. PR-B moves them inside the
    rule's ``validate_structural_floor()`` per §13.1.
    """
    # Phase 274.4 — delegate validation to StructuralFloorRule.
    from hub.apps.contracts.business_rules import StructuralFloorRule

    result = StructuralFloorRule.validate_structural_floor(
        hub_contract or {},
        spec_type=spec_type or "",
        spec_version=spec_version or "",
        contract_id=contract_id or "",
        tenant_id=tenant_id or "",
        warnings=warnings,
    )

    if result.is_valid:
        return

    # Build details from the rule result.
    subcode = result.details.get("subcode", SUBCODE_GENERIC)
    hint = _HINT_BY_SUBCODE.get(subcode, _HINT_BY_SUBCODE[SUBCODE_GENERIC])
    remediation_url = _resolve_remediation_url(contract_id)

    payload = hub_contract if isinstance(hub_contract, dict) else {}
    details: dict[str, Any] = {
        "subcode": subcode,
        "models_count": _count_models_with_fields(payload),
        "schema_fields_count": _schema_fields_count(payload),
        "spec_type": spec_type,
        "spec_version": spec_version,
        "hint": hint,
        "remediation_url": remediation_url,
    }

    # Phase 227 Wave 1 observability emission.
    _emit_floor_violation_observability(
        code=ERROR_CODE,
        subcode=subcode,
        spec_type=spec_type,
        spec_version=spec_version,
        contract_id=contract_id,
        tenant_id=tenant_id,
        source=source or "unknown",
        details=details,
    )

    raise ValidationError(
        message=(
            "Contract failed the structural-floor invariant: it has no "
            "resolvable models or schema fields after normalisation. "
            f"({subcode})"
        ),
        code=ERROR_CODE,
        details=details,
        http_status=400,
    )


def _emit_floor_violation_observability(
    *,
    code: str,
    subcode: str,
    spec_type: str | None,
    spec_version: str | None,
    contract_id: str | None,
    tenant_id: str | None,
    source: str,
    details: dict[str, Any],
) -> None:
    """Phase 227 Wave 1 (227.L7.1, L7.3, L7.4) — emit metrics + log +
    audit event for a Layer-3 floor violation.

    Each side-effect is wrapped in its own try/except so a partial
    backend outage doesn't cascade. The caller raises the
    ``ValidationError`` after this function returns.
    """
    # L7.1 — metrics. Both counters are incremented so the dashboard
    # can correlate "Layer-3 failures" with "structureless source".
    try:
        from hub.apps.contracts.normalization_metrics import (
            record_structureless,
            record_validation_failed,
        )

        record_validation_failed(code=code, subcode=subcode, spec_type=spec_type)
        record_structureless(spec_type=spec_type, source=source)
    except ImportError:
        # Metrics module not installed — non-fatal.
        pass
    except Exception:
        logger.warning("structural_floor_metrics_failed", exc_info=True)

    # L7.4 — structured WARN log. Carries the four required fields:
    # contract_id, spec_type, tenant_id, subcode.
    try:
        import structlog

        log = structlog.get_logger(__name__)
        log.warning(
            "structural_floor_violation",
            contract_id=str(contract_id) if contract_id else None,
            spec_type=spec_type,
            spec_version=spec_version,
            tenant_id=str(tenant_id) if tenant_id else None,
            subcode=subcode,
            source=source,
            models_count=details.get("models_count"),
            schema_fields_count=details.get("schema_fields_count"),
        )
    except ImportError:
        # structlog not installed — non-fatal.
        pass
    except Exception:
        logger.warning("structural_floor_log_emit_failed", exc_info=True)

    # L7.3 — audit event. We use the unredacted details + label
    # values; ``create_audit_event`` runs ``redact_pii`` internally
    # so PII can't leak even if a future caller passes sensitive
    # context.
    try:
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        tenant_obj = None
        if tenant_id:
            try:
                tenant_obj = Tenant.objects.filter(id=tenant_id).first()
            except (InterfaceError, DatabaseError, OperationalError):
                tenant_obj = None

        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_STRUCTURELESS_REJECTED",
            actor_user=None,
            tenant=tenant_obj,
            resource_id=str(contract_id) if contract_id else None,
            result="FAILURE",
            details={
                "code": code,
                "subcode": subcode,
                "spec_type": spec_type,
                "spec_version": spec_version,
                "models_count": details.get("models_count"),
                "schema_fields_count": details.get("schema_fields_count"),
                "source": source,
            },
        )
    except ImportError:
        # Audit app not installed — non-fatal.
        pass
    except Exception:
        logger.warning("structural_floor_audit_failed", exc_info=True)


def collect_structural_floor_errors(
    hub_contract: dict[str, Any] | None,
    *,
    spec_type: str | None,
    spec_version: str | None,
    warnings: Iterable[str] | None = None,
    contract_id: str | None = None,
) -> list[dict[str, Any]]:
    """Non-raising sibling — returns a list of error-detail dicts.

    Phase 274.4: Delegates to StructuralFloorRule directly (avoids
    circularity through enforce_structural_floor → rule → this).
    """
    from hub.apps.contracts.business_rules import StructuralFloorRule

    result = StructuralFloorRule.validate_structural_floor(
        hub_contract or {},
        spec_type=spec_type or "",
        spec_version=spec_version or "",
        contract_id=contract_id or "",
        warnings=warnings,
    )

    if result.is_valid:
        return []

    subcode = result.details.get("subcode", SUBCODE_GENERIC)
    remediation_url = _resolve_remediation_url(contract_id or None)
    return [
        {
            "code": ERROR_CODE,
            "message": result.errors[0] if result.errors else "",
            "subcode": subcode,
            "remediation_url": remediation_url,
        }
    ]
