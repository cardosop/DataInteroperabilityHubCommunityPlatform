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

from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings

from hub.apps.contracts.structureless import is_payload_structureless
from hub.apps.core.services.base import ValidationError


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


def _count_models_with_fields(payload: Dict[str, Any]) -> int:
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


def _schema_fields_count(payload: Dict[str, Any]) -> int:
    """Count top-level ``schema.fields`` entries."""
    schema_block = payload.get("schema") or {}
    if not isinstance(schema_block, dict):
        return 0
    fields = schema_block.get("fields") or []
    if not isinstance(fields, list):
        return 0
    return len(fields)


def _normalisation_warnings_indicate_cycle(
    warnings: Optional[Iterable[str]],
) -> bool:
    """Detect Phase 227.L1.7 cyclic-ports warning in the warning list."""
    if not warnings:
        return False
    return any("STRUCTURELESS_CYCLIC_PORTS" in w for w in warnings if w)


def _classify(
    payload: Dict[str, Any],
    *,
    spec_type: Optional[str],
    warnings: Optional[Iterable[str]],
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
        "Contract has no resolvable structure. Add models or schema "
        "fields and retry."
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _resolve_remediation_url(contract_id: Optional[str]) -> str:
    """Return the Schema-editor deep link for the offending contract."""
    template = getattr(
        settings,
        "STRUCTURELESS_CONTRACT_SCHEMA_EDITOR_URL_TEMPLATE",
        DEFAULT_SCHEMA_EDITOR_URL_TEMPLATE,
    )
    cid = str(contract_id) if contract_id else PLACEHOLDER_CONTRACT_ID
    return template.replace("{contract_id}", cid)


def enforce_structural_floor(
    hub_contract: Optional[Dict[str, Any]],
    *,
    spec_type: Optional[str],
    spec_version: Optional[str],
    warnings: Optional[Iterable[str]] = None,
    contract_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    """Raise ``ValidationError(code="STRUCTURELESS_CONTRACT")`` if the
    payload violates the structural floor; otherwise return ``None``.

    Parameters
    ----------
    hub_contract
        The normalized HubContract dict (from the engine).
    spec_type
        Original ODCS/ODPS spec type for subcode classification.
    spec_version
        Original spec version, attached to the error payload.
    warnings
        Optional list of normalisation warnings; consulted to detect
        the cyclic-ports case (Phase 227 L1.7).
    contract_id
        Optional UUID for the offending contract — used to build the
        Schema-editor deep link. Omit on create where no UUID exists yet.
    tenant_id
        Optional tenant UUID. Forwarded to the audit-event helper
        (Phase 227 L7.3). Omit when no tenant context is available
        (e.g., management-command runs).
    source
        Optional label classifying WHERE the floor violation was
        observed: ``creation``, ``update``, ``migration``, etc.
        Forwarded to the ``contract_structureless_total`` metric
        (Phase 227 L7.1) and the audit-event details (Phase 227 L7.3).
        Defaults to ``unknown`` when omitted.

    Raises
    ------
    ValidationError
        With ``code="STRUCTURELESS_CONTRACT"``, ``http_status=400``,
        and ``details`` carrying ``subcode``, ``models_count``,
        ``schema_fields_count``, ``spec_type``, ``spec_version``,
        ``hint``, ``remediation_url``.

    Side effects (Phase 227 L7)
    ---------------------------
    On every raise, this function:

    * Increments ``contract_validation_failed_total{code, subcode,
      spec_type}`` and ``contract_structureless_total{spec_type,
      source}`` (L7.1).
    * Emits a structured WARN log via ``structlog`` carrying
      ``contract_id``, ``spec_type``, ``tenant_id``, ``subcode``
      (L7.4).
    * Emits a ``CONTRACT_STRUCTURELESS_REJECTED`` audit event via
      ``create_audit_event`` (L7.3). Failure to emit the audit event
      is logged but never blocks the raise — the raise is the
      load-bearing operation.
    """
    # ``is_payload_structureless`` handles None / non-dict / empty cases
    # uniformly; we treat all of those as floor violations.
    if not is_payload_structureless(hub_contract):
        return

    # Build details payload. For the None / non-dict case, counts are 0.
    payload = hub_contract if isinstance(hub_contract, dict) else {}
    models_count = _count_models_with_fields(payload)
    fields_count = _schema_fields_count(payload)

    subcode = _classify(payload, spec_type=spec_type, warnings=warnings)
    hint = _HINT_BY_SUBCODE.get(subcode, _HINT_BY_SUBCODE[SUBCODE_GENERIC])
    remediation_url = _resolve_remediation_url(contract_id)

    details: Dict[str, Any] = {
        "subcode": subcode,
        "models_count": models_count,
        "schema_fields_count": fields_count,
        "spec_type": spec_type,
        "spec_version": spec_version,
        "hint": hint,
        "remediation_url": remediation_url,
    }

    # ------------------------------------------------------------------
    # Phase 227 Wave 1 (227.L7.1, L7.3, L7.4) — observability emission.
    # All side-effects are wrapped in their own try/except so a metric
    # backend / audit DB outage CAN'T block the floor enforcement —
    # the raise is the load-bearing operation.
    # ------------------------------------------------------------------
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
    spec_type: Optional[str],
    spec_version: Optional[str],
    contract_id: Optional[str],
    tenant_id: Optional[str],
    source: str,
    details: Dict[str, Any],
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
            record_validation_failed,
            record_structureless,
        )
        record_validation_failed(
            code=code, subcode=subcode, spec_type=spec_type
        )
        record_structureless(spec_type=spec_type, source=source)
    except Exception:
        # Metrics outage MUST NOT block the raise.
        pass

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
    except Exception:
        # structlog import / emit failure MUST NOT block the raise.
        pass

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
            except Exception:
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
    except Exception:
        # Audit-event failure MUST NOT block the raise. The L7.4 log
        # already carries the same information for ops.
        pass


def collect_structural_floor_errors(
    hub_contract: Optional[Dict[str, Any]],
    *,
    spec_type: Optional[str],
    spec_version: Optional[str],
    warnings: Optional[Iterable[str]] = None,
    contract_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Non-raising sibling — returns a list of error-detail dicts.

    Used by call-sites that need to aggregate multiple validation
    failures (e.g., ``Asset.can_activate`` returning a list of blockers
    rather than raising). Returns an empty list when the payload
    satisfies the floor.
    """
    try:
        enforce_structural_floor(
            hub_contract,
            spec_type=spec_type,
            spec_version=spec_version,
            warnings=warnings,
            contract_id=contract_id,
        )
        return []
    except ValidationError as exc:
        return [
            {
                "code": exc.code,
                "message": exc.message,
                **(exc.details or {}),
            }
        ]
