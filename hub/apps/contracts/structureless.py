"""
Phase 227 Wave 0 — canonical "structureless" predicate + triage classifier.

A normalized HubContract is structureless when it carries no structural
payload — i.e. both `models[*].fields[]` and `schema.fields[]` are empty
or absent. This module is the single source of truth so:

* `renormalize_contracts --filter=structureless` and
* the runbook triage logic and
* the customer T-14 notification body

all agree on which contracts are pending remediation.

Why "structureless" needs a canonical definition
------------------------------------------------
Phase 227 confirmed two normalizer bugs that produce empty `models[]`:

* **ODPS** — `outputPorts[]` are recorded only as metadata
  (`extensions.x_odps.output_ports`); the canonical normalization helper
  (Phase 227.L1, *_ports_helper.py*) is not yet shipped.
* **ODCS** — top-level contracts that omit the `schema:` block, or whose
  schema is empty, normalize to no models.

A privileged DB or a stale cache could surface variants where `models`
is present but every model has an empty `fields[]`, or where `schema`
exists but `fields` is null. The predicate here covers all of those.

Public API
----------
* :func:`is_structureless` — Python predicate operating on a `Contract`
  (or anything with `.hub_contract_json`).
* :func:`structureless_filter_q` — Django ``Q`` for coarse DB filtering.
  Iteration callers SHOULD also call :func:`is_structureless` per row to
  catch payload variants that the JSONField lookup cannot reach.
* :class:`StructurelessClassification` — string-valued enum used as the
  triage taxonomy in the dry-run report.
* :func:`classify_structureless_contract` — assigns a triage class to a
  structureless contract using its `original_spec_type` + `original_raw`.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Protocol

from django.db.models import Q


class _ContractLike(Protocol):
    """Minimal shape used by the predicate; matches `Contract` model.

    Attributes are typed as ``Any`` because the Django ORM exposes them
    as ``Field`` descriptors at the class level (e.g. ``CharField``,
    ``TextField``) which static checkers see as incompatible with plain
    ``str``. At instance access time the descriptors return strings.
    """

    hub_contract_json: Any
    original_spec_type: Any
    original_raw: Any


class StructurelessClassification(str, Enum):
    """Triage taxonomy for the Wave 0 dry-run report.

    Values are chosen for stable JSONL emission (lower-case, snake_case)
    and direct grep-ability in operator tooling.
    """

    PURE_ODPS_WITH_OUTPUTPORTS = "pure_odps_with_outputports"
    """ODPS contract whose `outputPorts[]` are present in `original_raw`
    but were dropped during normalization. Self-heals in Wave 3 once the
    Phase 227.L1 ports helper ships.
    """

    ODCS_NO_SCHEMA_BLOCK = "odcs_no_schema_block"
    """ODCS contract whose `original_raw` lacks a `schema:` block (or has
    one but no resolvable fields). Customer-action: open the Schema
    editor and add models/fields. Wave 4/5 deadline.
    """

    OTHER = "other"
    """Anything else — needs operator investigation. Logged for triage."""


def is_structureless(contract: _ContractLike) -> bool:
    """Return True iff the contract carries no structural payload.

    The predicate handles:

    * ``hub_contract_json`` is None (normalization never ran or was wiped).
    * ``hub_contract_json`` is a non-dict (malformed payload).
    * ``models`` missing OR empty list OR list-of-models-with-empty-fields.
    * ``schema.fields`` missing OR empty OR null.
    """
    payload = getattr(contract, "hub_contract_json", None)

    if payload is None:
        return True
    if not isinstance(payload, dict):
        # Defensive: any non-dict shape means no usable structure.
        return True

    # Models contribute structure only if at least one model has a
    # non-empty `fields[]`. A model with `fields=[]` carries no payload.
    models = payload.get("models") or []
    has_model_fields = any(
        isinstance(m, dict) and (m.get("fields") or [])
        for m in models
        if isinstance(m, dict)
    )

    schema_block = payload.get("schema") or {}
    if not isinstance(schema_block, dict):
        schema_block = {}
    schema_fields = schema_block.get("fields") or []

    has_schema_fields = bool(schema_fields)

    return not (has_model_fields or has_schema_fields)


def structureless_filter_q() -> Q:
    """Return a coarse Django ``Q`` for structureless contracts.

    Used as a pre-filter to bound the queryset; per-row precision is
    handled by :func:`is_structureless` during iteration. Coarse-only
    captures: ``hub_contract_json`` IS NULL, OR ``models = []``.

    A more precise ORM expression would require either Postgres-specific
    JSONField path comparisons that don't compose well across managers,
    or a generated column. Coarse + Python refinement is the right
    tradeoff for the Wave 0 dry-run scale (a few hundred contracts).
    """
    return Q(hub_contract_json__isnull=True) | Q(hub_contract_json__models=[])


# Pre-compiled patterns for the classifier. `re.IGNORECASE` so a customer's
# raw YAML/JSON input case doesn't trick the heuristic.
_OUTPUTPORTS_RE = re.compile(r"^\s*outputPorts\s*:", re.MULTILINE | re.IGNORECASE)
_SCHEMA_FIELDS_RE = re.compile(
    r"^\s*schema\s*:[\s\S]*?\bfields\s*:\s*\n\s*-",
    re.MULTILINE | re.IGNORECASE,
)


def classify_structureless_contract(
    contract: _ContractLike,
) -> StructurelessClassification:
    """Assign a triage class to a structureless contract.

    The classifier inspects the *original* contract bytes (``original_raw``)
    rather than the normalized payload, because the whole point of Wave 0
    is to find contracts whose normalized payload is empty *despite* the
    original carrying intent.

    Resolution rules (first match wins):

    1. ``ODPS`` whose original_raw contains a ``outputPorts:`` block →
       :attr:`StructurelessClassification.PURE_ODPS_WITH_OUTPUTPORTS`.
       Will self-heal in Wave 3 once the canonical ODPS-ports helper is
       shipped (Phase 227.L1).

    2. ``ODCS`` with no ``schema:`` block, or with a ``schema:`` block
       that has no ``fields:`` array → :attr:`ODCS_NO_SCHEMA_BLOCK`.
       Customer must add structure via the Schema editor.

    3. Everything else → :attr:`OTHER`. Operator investigation needed.
    """
    spec_type = (contract.original_spec_type or "").upper()
    raw = contract.original_raw or ""

    if spec_type == "ODPS":
        if _OUTPUTPORTS_RE.search(raw):
            return StructurelessClassification.PURE_ODPS_WITH_OUTPUTPORTS
        return StructurelessClassification.OTHER

    if spec_type == "ODCS":
        # Check for `schema:` block AND non-empty `fields:` under it.
        if _SCHEMA_FIELDS_RE.search(raw):
            # Schema block present *and* has fields — but the contract is
            # still structureless. The block itself is malformed (e.g.
            # nested objects the legacy normalizer dropped). Treat as
            # editor-actionable rather than "investigation needed".
            return StructurelessClassification.ODCS_NO_SCHEMA_BLOCK
        return StructurelessClassification.ODCS_NO_SCHEMA_BLOCK

    return StructurelessClassification.OTHER
