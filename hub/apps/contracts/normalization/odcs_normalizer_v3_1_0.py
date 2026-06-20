"""
ODCS 3.1.0 Normalizer

Version-specific normalizer for ODCS (Open Data Contract Standard) version 3.1.0.
Implements ODCSNormalizerBase with 3.1.0-specific handling for breaking changes:

- team field restructured from array to object with members[] (aligned with ODPS v1.0.0)
- exclusiveMaximum/exclusiveMinimum changed from boolean (draft-07) to numeric (draft-2019)
- slaDefaultElement removed (deprecated since v3.0.2)
"""

import re
from typing import Any

import structlog

from hub.apps.contracts.normalization.odcs_normalizer_base import ODCSNormalizerBase

logger = structlog.get_logger(__name__)

# Semver pattern for 3.1.x matching — anchored to reject "3.1.0beta" etc.
_V3_1_PATTERN = re.compile(r"^3\.1\.\d+$")


class ODCSNormalizerV3_1_0(ODCSNormalizerBase):
    """
    ODCS 3.1.0-specific normalizer implementation.

    Handles breaking changes introduced in ODCS v3.1.0:

    1. **team restructure**: ``team`` changed from ``list[{name, email, role}]``
       to ``{members: [{name, email, role, id, description}]}``.
       Both shapes are detected and mapped to ``HubContract.info.owners``.

    2. **exclusiveMaximum / exclusiveMinimum type change**: in ``logicalTypeOptions``,
       these fields changed from ``bool`` (JSON Schema draft-07) to ``numeric``
       (JSON Schema draft-2019-09 — the actual exclusive bound value).

    3. **slaDefaultElement removed**: deprecated since v3.0.2; this normalizer
       emits a warning if present and does not map it.
    """

    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODCS version.

        Supports:
        - Exact version "3.1.0"
        - Any semver 3.1.x (e.g. "3.1.1", "3.1.2")
        """
        if spec_version is None:
            return False
        if spec_version == "3.1.0":
            return True
        if _V3_1_PATTERN.match(spec_version):
            return True
        return False

    # _parse_team_v31 is inherited from ODCSNormalizerBase — no override
    # needed.  The base class _normalize_roles_team_pricing already
    # detects both v3.0.x array and v3.1.0 object shapes, runs
    # validate_and_enrich_team, and populates info.owners.

    # ------------------------------------------------------------------
    # exclusiveMaximum / exclusiveMinimum handling
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_exclusive_bound(value: Any) -> Any:
        """
        Normalize an exclusiveMaximum or exclusiveMinimum value.

        - ``bool`` (v3.0.x / JSON Schema draft-07): kept as-is.
        - ``int`` or ``float`` (v3.1.0 / JSON Schema draft-2019-09): wrapped
          as ``{"value": v, "type": "numeric_bound"}``.
        - anything else: returned as-is (best-effort).
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return {"value": value, "type": "numeric_bound"}
        return value

    def _map_field_logical_type_options(
        self,
        logical_type_options: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Map ``logicalTypeOptions`` with v3.1.0 semantics:
        - exclusiveMaximum/exclusiveMinimum: bool → numeric
        - timezone / defaultTimezone: pass through for timestamp/time types
        """
        mapped = dict(logical_type_options)  # shallow copy
        for key in ("exclusiveMaximum", "exclusiveMinimum"):
            if key in mapped:
                mapped[key] = self._normalize_exclusive_bound(
                    mapped[key],
                )
        # timezone / defaultTimezone are already in `mapped`
        # via the shallow copy — no extra handling needed.
        return mapped

    # ------------------------------------------------------------------
    # Version-specific hook (called from base after common normalization)
    # ------------------------------------------------------------------

    def _map_version_specific_fields(
        self,
        odcs_contract: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Apply ODCS 3.1.0 breaking-change mappings *after* base
        normalization.

        **team**: NOT re-processed here.  The base class
        ``_normalize_roles_team_pricing`` already detects both v3.0.x
        array and v3.1.0 object shapes, parses them via
        ``_parse_team_v31``, runs ``validate_and_enrich_team``, and
        populates ``info.owners``.  Re-processing here would overwrite
        the validated data with raw unvalidated data.

        **logicalTypeOptions**: exclusive-bound values in source fields
        are normalised (bool kept as-is, numeric wrapped).

        **slaDefaultElement**: the base ``_map_service_levels`` already
        mapped ``slaDefaultElement`` → ``element``.  We undo that
        mapping for v3.1.0 and emit a deprecation warning.
        """
        # --- 1. exclusiveMaximum / exclusiveMinimum in logicalTypeOptions ---
        self._apply_exclusive_bounds_to_models(
            hub_contract,
            odcs_contract,
            warnings,
        )

        # --- 2. slaDefaultElement removal ---
        self._strip_sla_default_element(
            odcs_contract,
            hub_contract,
            warnings,
        )

        # --- 3. relationships (ODCS v3.1.0) ---
        self._map_relationships(odcs_contract, hub_contract, warnings)

        # --- 5. element_id (ODCS v3.1.0 id on objects/properties) ---
        self._map_element_ids(odcs_contract, hub_contract)

        # --- 6. quality.library built-in metric types ---
        self._map_quality_library(odcs_contract, hub_contract, warnings)

        # --- 7. logicalType: timestamp / time ---
        self._map_logical_types(hub_contract)

        logger.debug(
            "odcs_v3_1_0_version_specific_mapping_complete",
            spec_version=spec_version,
            message="ODCS 3.1.0 version-specific mapping complete",
        )

    # ------------------------------------------------------------------
    # Internal helpers called from _map_version_specific_fields
    # ------------------------------------------------------------------

    def _apply_exclusive_bounds_to_models(
        self,
        hub_contract: dict[str, Any],
        odcs_contract: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """
        Walk schema fields in the *original* ODCS contract and patch
        ``logicalTypeOptions`` in the already-mapped HubContract models/schema.
        """
        # Build a quick lookup: field_name → logicalTypeOptions from the source
        lto_by_field: dict[str, dict[str, Any]] = {}
        for schema_entry in self._iter_odcs_schema_entries(odcs_contract):
            for field in schema_entry.get("fields", []):
                if not isinstance(field, dict):
                    continue
                fname = field.get("name", "")
                lto = field.get("logicalTypeOptions") or field.get("logical_type_options")
                if isinstance(lto, dict) and fname:
                    lto_by_field[fname] = lto

        if not lto_by_field:
            return

        # Patch HubContract models[].fields[]
        for model in hub_contract.get("models", []):
            if not isinstance(model, dict):
                continue
            for hf in model.get("fields", []):
                if not isinstance(hf, dict):
                    continue
                fname = hf.get("name", "")
                if fname in lto_by_field:
                    hf["logicalTypeOptions"] = self._map_field_logical_type_options(
                        lto_by_field[fname]
                    )

        # Patch HubContract schema.fields[] (derived view)
        for hf in hub_contract.get("schema", {}).get("fields", []):
            if not isinstance(hf, dict):
                continue
            fname = hf.get("name", "")
            if fname in lto_by_field:
                hf["logicalTypeOptions"] = self._map_field_logical_type_options(lto_by_field[fname])

    @staticmethod
    def _iter_odcs_schema_entries(odcs_contract: dict[str, Any]):
        """Yield each schema dict from the ODCS contract (list or single)."""
        schema = odcs_contract.get("schema")
        if isinstance(schema, list):
            for entry in schema:
                if isinstance(entry, dict):
                    yield entry
        elif isinstance(schema, dict):
            yield schema

    def _strip_sla_default_element(
        self,
        odcs_contract: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """
        Undo the base normalizer's ``slaDefaultElement`` → ``element``
        mapping for v3.1.0 contracts.

        The base ``_map_service_levels`` maps both ``element`` and
        ``slaDefaultElement`` to the ``element`` target.  For v3.1.0
        ``slaDefaultElement`` is removed, so we must:

        1. Emit a deprecation warning if present in source.
        2. Remove ``element`` from each mapped service-level where the
           source only had ``slaDefaultElement`` (not a real
           ``element`` field).
        3. Clean ``slaDefaultElement`` from extensions if it leaked.
        """
        warned = False

        # Build lookup: SLA name → whether source also had real "element"
        sla_has_real_element: dict[str, bool] = {}
        for source_key in ("slaProperties", "lifecycle"):
            source = odcs_contract.get(source_key)
            if source_key == "lifecycle" and isinstance(source, dict):
                source = source.get("slaProperties")
            if not isinstance(source, list):
                continue
            for entry in source:
                if not isinstance(entry, dict):
                    continue
                if "slaDefaultElement" in entry:
                    if not warned:
                        warnings.append(
                            "Field 'slaDefaultElement' is removed in ODCS v3.1.0; ignored"
                        )
                        warned = True
                    sla_name = entry.get("name", "")
                    sla_has_real_element[sla_name] = "element" in entry

        if not warned:
            return

        # Walk mapped service levels and strip element where it came
        # solely from slaDefaultElement.
        for sl in hub_contract.get("servicelevels", []):
            if not isinstance(sl, dict):
                continue
            sl_name = sl.get("name", "")

            # If source had slaDefaultElement but NOT a real "element",
            # remove the element the base injected.
            if sl_name in sla_has_real_element and not sla_has_real_element[sl_name]:
                sl.pop("element", None)

            # Clean slaDefaultElement from extensions if it leaked
            ext = sl.get("extensions")
            if isinstance(ext, dict) and "slaDefaultElement" in ext:
                del ext["slaDefaultElement"]
                if not ext:
                    sl.pop("extensions", None)

    # ------------------------------------------------------------------
    # Phase 26.2 — v3.1.0 new field mappings
    # ------------------------------------------------------------------

    # v3.1.0 new server types (for documentation / validation)
    _V31_SERVER_TYPES = frozenset(
        {
            "HiveServer",
            "ImpalaServer",
            "ActianZenServer",
        }
    )

    # v3.1.0 built-in quality metric types
    _V31_QUALITY_METRIC_TYPES = frozenset(
        {
            "rowCount",
            "nullValues",
            "invalidValues",
            "duplicateValues",
            "missingValues",
        }
    )

    def _map_relationships(
        self,
        odcs: dict[str, Any],
        hub: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """Map ODCS v3.1.0 relationships[] on schema objects."""
        for schema_entry in self._iter_odcs_schema_entries(odcs):
            rels_raw = schema_entry.get("relationships")
            if not isinstance(rels_raw, list):
                continue
            name = schema_entry.get("name", "")
            mapped = []
            for r in rels_raw:
                if not isinstance(r, dict):
                    continue
                mapped.append(
                    {
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "type": r.get("type"),
                        "source": r.get("source", []),
                        "target_contract": r.get(
                            "targetContract",
                        ),
                        "target_model": r.get(
                            "targetModel",
                        ),
                        "target_properties": r.get(
                            "targetProperties",
                            [],
                        ),
                        "description": r.get("description"),
                        "custom_properties": r.get(
                            "customProperties",
                        ),
                    }
                )
            if not mapped:
                continue
            # Attach to matching hub model
            for model in hub.get("models", []):
                if not isinstance(model, dict):
                    continue
                if model.get("name") == name:
                    model["relationships"] = mapped
                    break
            # Also attach to schema level
            hub.setdefault("schema", {}).setdefault(
                "relationships",
                [],
            ).extend(mapped)

    def _map_element_ids(
        self,
        odcs: dict[str, Any],
        hub: dict[str, Any],
    ) -> None:
        """Map ODCS v3.1.0 ``id`` on objects/properties
        to ``element_id``."""
        for schema_entry in self._iter_odcs_schema_entries(odcs):
            obj_name = schema_entry.get("name", "")
            obj_id = schema_entry.get("id")
            # Build field-level id lookup
            field_ids: dict[str, str] = {}
            for f in schema_entry.get("fields", []):
                if isinstance(f, dict) and "id" in f:
                    fname = f.get("name", "")
                    if fname:
                        field_ids[fname] = f["id"]
            # Patch hub models[].fields[]
            for model in hub.get("models", []):
                if not isinstance(model, dict):
                    continue
                if model.get("name") == obj_name and obj_id:
                    model["element_id"] = obj_id
                for hf in model.get("fields", []):
                    if not isinstance(hf, dict):
                        continue
                    fname = hf.get("name", "")
                    if fname in field_ids:
                        hf["element_id"] = field_ids[fname]
            # Patch hub schema.fields[] (flat view)
            for hf in hub.get("schema", {}).get("fields", []):
                if not isinstance(hf, dict):
                    continue
                fname = hf.get("name", "")
                if fname in field_ids:
                    hf["element_id"] = field_ids[fname]

    def _map_quality_library(
        self,
        odcs: dict[str, Any],
        hub: dict[str, Any],
        warnings: list[str],
    ) -> None:
        """Map ODCS v3.1.0 quality.library metric entries."""
        quality = odcs.get("quality")
        if not isinstance(quality, dict):
            return
        library = quality.get("library")
        if not isinstance(library, list):
            return
        rules = hub.setdefault(
            "quality",
            {},
        ).setdefault("rules", [])
        for entry in library:
            if not isinstance(entry, dict):
                continue
            metric_type = entry.get("type", "")
            rule: dict[str, Any] = {
                "type": metric_type,
            }
            if "name" in entry:
                rule["name"] = entry["name"]
            if "dimension" in entry:
                rule["dimension"] = entry["dimension"]
            if "threshold" in entry:
                rule["threshold"] = entry["threshold"]
            if "description" in entry:
                rule["description"] = entry["description"]
            # Preserve extra fields
            for k, v in entry.items():
                if k not in rule:
                    rule[k] = v
            rules.append(rule)

    def _map_logical_types(
        self,
        hub: dict[str, Any],
    ) -> None:
        """Promote logicalType for timestamp/time fields
        in both models[].fields[] and schema.fields[]."""
        all_fields = []
        for model in hub.get("models", []):
            if isinstance(model, dict):
                all_fields.extend(model.get("fields", []))
        all_fields.extend(
            hub.get("schema", {}).get("fields", []),
        )
        for hf in all_fields:
            if not isinstance(hf, dict):
                continue
            lto = hf.get("logicalTypeOptions", {})
            if not isinstance(lto, dict):
                continue
            lt = lto.get("logicalType")
            if lt in ("timestamp", "time", "date"):
                hf.setdefault("logicalType", lt)
