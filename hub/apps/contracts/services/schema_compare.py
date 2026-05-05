"""
Phase 250.2.B.1 — deterministic schema-diff service.

Compares a HubContract's declared schema (``hub_contract_json["schema"]``)
against an inferred-from-data schema (the shape produced by
:mod:`hub.apps.datasets.schema_inference`) and returns a structured
``SchemaDriftResult`` that the asset-creation workflow uses to set the
``schema_drift_status`` (``NONE`` / ``WARN`` / ``FAIL``) per D250.12.

Wire shapes accepted
---------------------

* HubContract format:
  ``{"schema": {"fields": [{"name": str, "type": str, ...}, ...]}}``
* Inferred (dataset) format:
  ``{"fields": [{"name": str, "data_type": str, "nullable": bool, ...}, ...]}``

The two paths use **different** type-key names (``"type"`` vs
``"data_type"``); the comparator normalises both to a canonical
internal representation before diffing so the algorithm is
shape-agnostic. New shapes can be added by extending
:meth:`SchemaCompareService._extract_fields`.

Severity rubric (D250.12)
-------------------------

* ``NONE`` — no drift detected; contract and dataset agree on every
  declared field's name and type.
* ``WARN`` — drift exists but it's all "compatible" (extra fields in
  the dataset that the contract didn't declare, or compatible type
  widenings like ``integer`` → ``long``). The asset can still be
  persisted; the workflow surfaces the drift on the API response so
  the user can decide whether to update the contract.
* ``FAIL`` — at least one ``missing_fields`` entry OR at least one
  incompatible ``type_mismatch``. The asset can still be persisted
  (per D250.12 "WARN-only blocks" rule), but
  ``structural_incompatibility=True`` is the signal that future
  ingestions of this dataset will not satisfy the contract's
  guarantees and ops should be alerted.

Determinism
-----------

The diff is **deterministic** — given the same contract + dataset
schema, the output is byte-identical across runs and across dict
insertion orderings. ``missing_fields`` and ``extra_fields`` are
sorted lexicographically; ``type_mismatches`` is sorted by field
name. This stability lets workflow ``state_data`` payloads be cached
by hash without false misses.

Performance
-----------

The algorithm is O(n) in the number of fields with two dict
lookups per field (one for the contract field, one for the dataset
field). 100-field diffs measure < 1 ms in practice, well under the
200 ms p95 budget from the spec.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Type-compatibility table (Phase 250.2.B.3)
# ---------------------------------------------------------------------------

#: Canonical aliases for ODCS / pandas-inferred type names. Two type
#: strings are considered EQUAL iff their canonical forms match.
#: This table intentionally folds ``str`` → ``string`` and ``int`` →
#: ``integer`` so the contract-side ODCS form and the dataset-side
#: pandas form interop without surfacing a false mismatch.
_TYPE_ALIASES: Dict[str, str] = {
    # Strings
    "string": "string",
    "str": "string",
    "varchar": "string",
    "text": "string",
    # Integers
    "integer": "integer",
    "int": "integer",
    "int32": "integer",
    "int64": "integer",  # canonical form is integer; widening handled below
    "long": "long",
    "bigint": "long",
    # Floats
    "float": "float",
    "float32": "float",
    "double": "double",
    "float64": "double",
    "decimal": "decimal",
    "numeric": "decimal",
    # Booleans
    "boolean": "boolean",
    "bool": "boolean",
    # Temporal
    "date": "date",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "time": "time",
    # Complex
    "object": "object",
    "struct": "object",
    "array": "array",
    "list": "array",
    "map": "map",
    "dict": "map",
    # Unknown / unsupported
    "unknown": "unknown",
    "null": "null",
}

#: Compatible widenings — ``contract_type`` → set of ``dataset_type`` values
#: that are SAFE supersets (the dataset can hold any value the contract
#: declares). The diff still REPORTS the mismatch, but flags it
#: ``compatible=True`` so the WARN-only severity rule doesn't escalate
#: it to a structural FAIL.
_COMPATIBLE_WIDENINGS: Dict[str, Set[str]] = {
    "integer": {"long"},          # int32 fits in int64
    "float": {"double", "decimal"},  # float32 fits in float64 / decimal
    "date": {"timestamp"},        # date fits in timestamp
}


def _canonicalise_type(raw: Optional[str]) -> str:
    """Normalise a type-name string for comparison.

    Returns ``""`` for ``None`` / non-string inputs so downstream
    equality checks treat them as "unknown but explicitly different".
    Whitespace + case are stripped to match across tool outputs.
    """
    if not isinstance(raw, str):
        return ""
    canonical = _TYPE_ALIASES.get(raw.strip().lower(), raw.strip().lower())
    return canonical


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaDriftResult:
    """Structured diff between a HubContract schema and an inferred dataset schema.

    Attributes:
        missing_fields: Field names declared by the contract that
            the dataset does NOT have. Sorted lexicographically.
        extra_fields: Field names present in the dataset that the
            contract does NOT declare. Sorted lexicographically.
        type_mismatches: Per-field type disagreements. Each entry is
            ``{"field": str, "contract_type": str, "dataset_type": str,
            "compatible": bool}`` where ``compatible=True`` means the
            mismatch is a safe widening. Sorted by field name.
        structural_incompatibility: True iff there's at least one
            missing field OR at least one ``type_mismatch`` with
            ``compatible=False``.
    """

    missing_fields: List[str] = field(default_factory=list)
    extra_fields: List[str] = field(default_factory=list)
    type_mismatches: List[Dict[str, Any]] = field(default_factory=list)
    structural_incompatibility: bool = False

    @property
    def detected(self) -> bool:
        """``True`` if any drift exists (any of the 3 categories non-empty)."""
        return bool(
            self.missing_fields or self.extra_fields or self.type_mismatches
        )

    @property
    def severity(self) -> str:
        """Severity tier per D250.12:

        * ``NONE`` — no drift detected.
        * ``FAIL`` — ``structural_incompatibility=True``.
        * ``WARN`` — drift exists but it's all compatible.
        """
        if not self.detected:
            return "NONE"
        if self.structural_incompatibility:
            return "FAIL"
        return "WARN"

    def to_dict(self) -> Dict[str, Any]:
        """Wire-friendly serialisation for ``state_data`` /
        API ``result_summary.schema_drift``.

        The output is JSON-stable: the same logical drift always
        produces a byte-identical dict so downstream cache keys +
        equality assertions don't false-miss on dict ordering.
        """
        return {
            "detected": self.detected,
            "severity": self.severity,
            "missing_fields": list(self.missing_fields),
            "extra_fields": list(self.extra_fields),
            "type_mismatches": [dict(m) for m in self.type_mismatches],
            "structural_incompatibility": self.structural_incompatibility,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SchemaCompareService:
    """Static comparator — no per-instance state, so a single call site
    can use the class methods directly without instantiating."""

    @staticmethod
    def _extract_fields(
        schema: Optional[Dict[str, Any]],
        *,
        type_key: str,
    ) -> Dict[str, str]:
        """Extract a ``{field_name: canonical_type}`` map from either
        wire shape.

        ``type_key`` is ``"type"`` for HubContract schemas and
        ``"data_type"`` for inferred-from-data schemas. The two
        callers within :meth:`compare` pass the appropriate key.

        Returns ``{}`` for ``None`` / malformed inputs (no ``fields``
        key, ``fields`` is not a list). Defensive design: a malformed
        contract on the workflow path should produce ``extra_fields``
        listing every dataset field rather than crashing the whole
        intake.
        """
        if not isinstance(schema, dict):
            return {}
        # HubContract puts fields under ``schema.fields``; inferred
        # puts them at the top under ``fields``. Try the nested path
        # first; fall back to the flat one.
        nested = schema.get("schema")
        if isinstance(nested, dict) and isinstance(nested.get("fields"), list):
            raw_fields = nested["fields"]
        elif isinstance(schema.get("fields"), list):
            raw_fields = schema["fields"]
        else:
            return {}

        result: Dict[str, str] = {}
        for entry in raw_fields:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            # The CONTRACT side uses ``type``; the INFERRED side uses
            # ``data_type``. We normalise both via _canonicalise_type
            # so the diff sees a single string per field.
            raw_type = entry.get(type_key) or entry.get("type") or entry.get("data_type")
            result[name] = _canonicalise_type(raw_type)
        return result

    @classmethod
    def compare(
        cls,
        *,
        contract_schema: Optional[Dict[str, Any]],
        inferred_schema: Optional[Dict[str, Any]],
    ) -> SchemaDriftResult:
        """Diff a HubContract schema against an inferred dataset schema.

        Args:
            contract_schema: The contract's ``hub_contract_json``
                (full dict — the comparator extracts the ``schema``
                key internally).
            inferred_schema: The dataset's inferred schema as
                produced by :mod:`hub.apps.datasets.schema_inference`.

        Returns:
            A :class:`SchemaDriftResult` with the three category
            lists populated (sorted) and ``structural_incompatibility``
            computed per D250.12.

        **Comparison scope (what counts as drift):**

        * Field NAME drift → ``missing_fields`` / ``extra_fields``.
        * Field TYPE drift (canonical type-name disagreement) →
          ``type_mismatches[]`` with ``compatible`` set per the
          widening table.

        **Comparison scope (what is INTENTIONALLY ignored):**

        * ``nullable`` differences are NOT compared. Both wire shapes
          may carry a ``"nullable": bool`` per field, but D250.12
          scopes this comparator to schema-shape drift (names + types).
          A contract that declares ``email`` as non-nullable against
          a dataset that has ``email`` nullable=True does NOT show up
          here — the appropriate gate is the constraint-validation
          step in the contract DQ pipeline (Phase 240.X), which
          checks NULL ratios against the contract's ``nullable``
          declaration with row-level evidence. Treating nullable
          divergence as "drift" here would conflate schema drift with
          data-quality drift, which the platform tracks on different
          surfaces (this banner vs DQ run dashboards).
        * Field-level ``description`` / ``constraints`` /
          ``examples`` / ``tags`` / ``rules`` differences are also
          ignored — those are contract-evolution metadata, not
          schema-shape drift.
        * Field ORDER is NOT compared; both schemas are diffed by
          set membership of field names.

        Output field-name uniqueness is guaranteed by
        :meth:`_extract_fields` returning a ``Dict[name, type]`` —
        the same name can't appear twice in the inputs we diff
        against, so ``missing_fields`` / ``extra_fields`` /
        ``type_mismatches[].field`` never carry duplicates. This
        unblocks the React banner using ``key={field}`` on its lists
        without a de-dupe pass.
        """
        contract_fields = cls._extract_fields(contract_schema, type_key="type")
        dataset_fields = cls._extract_fields(inferred_schema, type_key="data_type")

        contract_names = set(contract_fields.keys())
        dataset_names = set(dataset_fields.keys())

        # Missing: contract has it, dataset doesn't.
        missing = sorted(contract_names - dataset_names)
        # Extra: dataset has it, contract doesn't.
        extra = sorted(dataset_names - contract_names)

        # Type mismatches: same field name, different canonical types.
        # Iterate sorted intersection so the output ordering is stable.
        common = sorted(contract_names & dataset_names)
        type_mismatches: List[Dict[str, Any]] = []
        for name in common:
            ct = contract_fields[name]
            dt = dataset_fields[name]
            if ct == dt:
                continue
            compatible = dt in _COMPATIBLE_WIDENINGS.get(ct, set())
            type_mismatches.append(
                {
                    "field": name,
                    "contract_type": ct,
                    "dataset_type": dt,
                    "compatible": compatible,
                }
            )

        # Structural: any missing OR any incompatible type mismatch.
        structural = bool(missing) or any(
            not m["compatible"] for m in type_mismatches
        )

        return SchemaDriftResult(
            missing_fields=missing,
            extra_fields=extra,
            type_mismatches=type_mismatches,
            structural_incompatibility=structural,
        )
