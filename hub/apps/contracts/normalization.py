"""
Contract Normalization

Normalizes contracts from ODCS and ODPS to HubContract format.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .context_fields import promote_context_fields
from .coverage import calculate_coverage
from .models import NormalizationStatus, OriginalSpecType
from .source_paths import SourcePathTracker, add_source_paths_to_extensions, track_field_mapping
from .spec_detection import detect_spec_type as detect_spec_type_new
from .spec_detection import store_original_spec_metadata
from .typed_models import validate_hub_contract_dict
from .validation import (
    validate_and_enrich_advanced_schema_attributes,
    validate_and_enrich_contacts,
    validate_and_enrich_lineage,
    validate_and_enrich_pricing,
    validate_and_enrich_roles,
    validate_and_enrich_servicelevels,
    validate_and_enrich_team,
)
from .versioning import ensure_version, get_default_version


@dataclass
class NormalizationResult:
    """Normalized HubContract output."""

    hub_contract: Optional[Dict[str, Any]]
    status: NormalizationStatus
    errors: List[str]
    warnings: List[str]
    spec_type: str
    spec_version: str
    coverage: Optional[Dict[str, Any]] = None


@runtime_checkable
class SpecNormalizer(Protocol):
    """Protocol for pluggable normalizers."""

    spec_type: str

    def supports(self, spec_type: str, spec_version: str, contract_data: Dict[str, Any]) -> bool:
        """Return True if this normalizer supports the given spec/version."""
        ...

    def normalize(
        self, contract_data: Dict[str, Any], spec_version: Optional[str] = None
    ) -> NormalizationResult:
        """Normalize raw contract data to HubContract."""
        ...


_NORMALIZER_REGISTRY: Dict[str, List[SpecNormalizer]] = {}


def register_normalizer(normalizer: SpecNormalizer) -> None:
    """Register a spec normalizer implementation."""
    _NORMALIZER_REGISTRY.setdefault(normalizer.spec_type, []).append(normalizer)


def get_normalizer(
    spec_type: str, spec_version: str, contract_data: Dict[str, Any]
) -> Optional[SpecNormalizer]:
    """
    Retrieve a normalizer that supports the given spec type/version.

    Prefers version-specific normalizers over default normalizers that support all versions.
    This ensures that version-specific implementations are used when available.

    Strategy: Check normalizers in reverse order (most recently registered first) since
    version-specific normalizers are registered after default normalizers.

    For ODCS, if no normalizer is found for the specified version, falls back to the
    latest version (3.0.2) to ensure backward compatibility and graceful handling of
    unknown or future versions.

    Args:
        spec_type: Specification type (e.g., "ODCS", "ODPS")
        spec_version: Specification version (e.g., "3.0.2", "3.0.1")
        contract_data: Contract data dictionary

    Returns:
        SpecNormalizer instance if found, None otherwise
    """
    normalizers = _NORMALIZER_REGISTRY.get(spec_type, [])
    if not normalizers:
        return None

    # Check in reverse order to prefer version-specific normalizers
    # (they are registered after default normalizers)
    # For ODCS, we need to skip the default wrapper (ODCSNormalizer) when looking
    # for version-specific normalizers
    from hub.apps.contracts.normalization.odcs_normalizer_default import ODCSNormalizerDefault

    version_specific_normalizer = None
    default_normalizer = None

    for normalizer in reversed(normalizers):
        if normalizer.supports(spec_type, spec_version, contract_data):
            # Check if this is the default wrapper or default implementation
            normalizer_class_name = normalizer.__class__.__name__
            if normalizer_class_name == "ODCSNormalizer" or isinstance(
                normalizer, ODCSNormalizerDefault
            ):
                # Store default normalizer but continue looking for version-specific
                if default_normalizer is None:
                    default_normalizer = normalizer
                continue
            # This is a version-specific normalizer - return it immediately
            return normalizer

    # If we found a version-specific normalizer above, it would have been returned
    # For ODCS with unknown versions, try fallback to 3.0.2 before using default
    # For other cases, use default normalizer if found
    if spec_type == OriginalSpecType.ODCS and spec_version != "3.0.2":
        # Don't use default normalizer yet - try fallback first (handled below)
        pass
    elif default_normalizer is not None:
        return default_normalizer

    # Fallback: For ODCS, if no normalizer found for the specified version,
    # try to find the latest version normalizer (3.0.2) to ensure backward
    # compatibility and graceful handling of unknown or future versions.
    # This allows the system to handle contracts with versions that don't
    # have a specific normalizer yet (e.g., future patch versions).
    if spec_type == OriginalSpecType.ODCS and spec_version != "3.0.2":
        # Try to find 3.0.2 normalizer (latest version)
        # Skip default normalizer wrapper - we want version-specific normalizers
        for normalizer in reversed(normalizers):
            # Skip default normalizer wrapper (ODCSNormalizer) and default implementation
            normalizer_class_name = normalizer.__class__.__name__
            if normalizer_class_name == "ODCSNormalizer" or isinstance(
                normalizer, ODCSNormalizerDefault
            ):
                continue
            # Check if this is a version-specific 3.0.2 normalizer
            if isinstance(normalizer, ODCSNormalizerV3_0_2):
                return normalizer
            # Also check via supports() and class name to ensure it's version-specific
            if normalizer.supports(spec_type, "3.0.2", contract_data):
                # Double-check it's not a default normalizer by checking class name
                if normalizer_class_name.startswith("ODCSNormalizerV"):
                    return normalizer

    return None


def _reset_normalizer_registry(registry: Optional[Dict[str, List[SpecNormalizer]]] = None) -> None:
    """
    Test helper: reset the normalizer registry to a provided snapshot.
    """
    _NORMALIZER_REGISTRY.clear()
    if registry:
        _NORMALIZER_REGISTRY.update(registry)


def _determine_normalization_status(
    hub_contract: Optional[Dict[str, Any]], errors: list, warnings: list
) -> NormalizationStatus:
    """
    Determine normalization status based on completeness and errors.

    Args:
        hub_contract: Normalized HubContract JSON (None if normalization failed)
        errors: List of errors encountered during normalization
        warnings: List of warnings encountered during normalization

    Returns:
        NormalizationStatus enum value
    """
    # If normalization failed (errors or no contract), return FAILED
    if errors or hub_contract is None:
        return NormalizationStatus.NORMALIZATION_FAILED

        # Check if critical sections are present
    info = hub_contract.get("info", {})
    # Empty string name should cause FAILED status (test expects this)
    if "info" not in hub_contract or "name" not in info or not info.get("name"):
        return NormalizationStatus.NORMALIZATION_FAILED

    schema = hub_contract.get("schema", {})
    if "schema" not in hub_contract or "fields" not in schema:
        return NormalizationStatus.NORMALIZATION_FAILED

    if not schema.get("fields"):
        return NormalizationStatus.NORMALIZATION_FAILED

    # If warnings present, status is WITH_WARNINGS
    # Extensions also indicate WITH_WARNINGS (they represent unmappable fields)
    if warnings or hub_contract.get("extensions"):
        return NormalizationStatus.NORMALIZED_WITH_WARNINGS

    # All critical sections present, no warnings
    return NormalizationStatus.NORMALIZED_OK


def _calculate_normalization_coverage(hub_contract: Dict[str, Any]) -> float:
    """
    Calculate normalization coverage as percentage of sections mapped.

    Args:
        hub_contract: Normalized HubContract JSON

    Returns:
        Coverage percentage (0.0 to 1.0)
    """
    coverage = calculate_coverage(hub_contract)
    return coverage.overall


def _map_quality_rules(quality_data: Dict[str, Any]) -> Optional[list]:
    """Map ODCS quality rules into canonical structure."""
    if not isinstance(quality_data, dict):
        return None

    rules = quality_data.get("rules") or []
    if not isinstance(rules, list):
        return None

    mapped_rules = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        mapped = {}
        field_map = {
            "id": ["id", "rule_id"],  # Map both id and rule_id to id
            "rule_id": ["rule_id"],  # Also preserve rule_id if present
            "name": ["name"],
            "dimension": ["dimension"],
            "type": ["type"],
            "rule": ["rule", "expression"],
            "unit": ["unit"],
            "operator": ["operator"],
            "threshold": ["threshold", "thresholdValue"],
            "valid_values": ["valid_values", "validValues"],
            "sql_query": ["sql_query", "sqlQuery"],
            "target": ["target"],
            "engine": ["engine"],
            "implementation": ["implementation"],
            "method": ["method"],
            "severity": ["severity"],
            "business_impact": ["business_impact", "businessImpact"],
            "scheduler": ["scheduler"],
            "schedule": ["schedule"],
            "tags": ["tags"],
        }
        for target, aliases in field_map.items():
            for alias in aliases:
                if alias in rule and rule.get(alias) is not None:
                    mapped[target] = rule[alias]
                    break
        if mapped:
            mapped_rules.append(mapped)
    return mapped_rules or None


def _map_quality_contract_level(quality_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract contract-level quality attributes (type/specification)."""
    if not isinstance(quality_data, dict):
        return {}
    mapped: Dict[str, Any] = {}
    if quality_data.get("type"):
        mapped["type"] = quality_data["type"]
    if quality_data.get("specification"):
        mapped["specification"] = quality_data["specification"]
    return mapped


def _map_service_levels(contract_data: Dict[str, Any]) -> Optional[list]:
    """Map ODCS slaProperties into canonical servicelevels[] structure."""
    if not isinstance(contract_data, dict):
        return None

    sources = []
    lifecycle = contract_data.get("lifecycle")
    if lifecycle and isinstance(lifecycle, dict) and lifecycle.get("slaProperties"):
        sources.append(lifecycle.get("slaProperties"))
    if contract_data.get("slaProperties"):
        sources.append(contract_data.get("slaProperties"))

    servicelevels = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for entry in source:
            if not isinstance(entry, dict):
                continue
            mapped = {}
            field_map = {
                "id": ["id"],
                "name": ["name"],
                "description": ["description"],
                "property": ["property", "propertyName"],
                "metric": ["metric"],
                "objective": ["objective"],
                "target": ["target"],
                "unit": ["unit"],
                "operator": ["operator"],
                "threshold": ["threshold"],
                "window": ["window", "measurementWindow"],
                "schedule": ["schedule"],
                "tags": ["tags"],
                "priority": ["priority"],
                "element": ["element", "slaDefaultElement"],
                "applies_to": ["appliesTo", "applies_to"],
            }
            for target, aliases in field_map.items():
                for alias in aliases:
                    if alias in entry and entry.get(alias) is not None:
                        mapped[target] = entry[alias]
                        break
            extra = {k: v for k, v in entry.items() if k not in mapped}
            if extra:
                mapped["extensions"] = extra
            if mapped:
                servicelevels.append(mapped)
    return servicelevels or None


def _map_contacts(contract_data: Dict[str, Any]) -> Optional[list]:
    """
    Map ODCS support[] channels into canonical contact list.

    Separates contact info (name, email) from support channels (tool, url, scope).
    Entries with name/email are treated as contacts, others as support channels.
    """
    support = contract_data.get("support")
    contacts = []
    if isinstance(support, list):
        for entry in support:
            if not isinstance(entry, dict):
                continue
            mapped = {}
            # Check if this is a contact (has name or email) or support channel
            has_contact_info = "name" in entry or "email" in entry or "address" in entry

            if has_contact_info:
                # Map as contact
                for target, aliases in {
                    "name": ["name"],
                    "email": ["email", "address"],
                    "url": ["url"],
                    "description": ["description"],
                    "tool": ["tool"],
                    "scope": ["scope"],
                }.items():
                    for alias in aliases:
                        if alias in entry and entry.get(alias) is not None:
                            mapped[target] = entry[alias]
                            break
                if mapped:
                    contacts.append(mapped)
                else:
                    # Preserve raw entry if nothing mapped
                    contacts.append({"extensions": entry})
            # If no contact info, it's a support channel (handled separately)
    return contacts or None


def _map_support_channels(contract_data: Dict[str, Any]) -> Optional[list]:
    """
    Map ODCS support[] channels into canonical support channel list.

    Preserves unmappable fields in extensions.

    Extracts support channels (tool, url, description, scope) separate from contacts.
    """
    support = contract_data.get("support")
    channels = []
    if isinstance(support, list):
        for entry in support:
            if not isinstance(entry, dict):
                continue
            # Only include if it's NOT a contact (no name/email)
            has_contact_info = "name" in entry or "email" in entry or "address" in entry
            if has_contact_info:
                continue  # Skip contacts, they're handled by _map_contacts

            mapped = {}
            for target, aliases in {
                "tool": ["tool"],
                "url": ["url"],
                "description": ["description"],
                "scope": ["scope"],
            }.items():
                for alias in aliases:
                    if alias in entry and entry.get(alias) is not None:
                        mapped[target] = entry[alias]
                        break

            # Preserve unmappable fields in extensions
            known_fields = {"tool", "url", "description", "scope", "name", "email", "address"}
            unmappable_fields = {}
            for key, value in entry.items():
                if key not in known_fields and not key.startswith("_"):
                    unmappable_fields[key] = value

            if unmappable_fields:
                mapped.setdefault("extensions", {})
                mapped["extensions"].update(unmappable_fields)

            if mapped:
                channels.append(mapped)
            else:
                # Preserve raw entry if nothing mapped
                channels.append({"extensions": entry})
    return channels or None


def _map_servers(contract_data: Dict[str, Any]) -> Optional[list]:
    """Map ODCS servers[] into canonical structure."""
    servers = contract_data.get("servers")
    mapped_servers = []
    if isinstance(servers, list):
        for entry in servers:
            if not isinstance(entry, dict):
                continue
            mapped = {}
            server_type = (entry.get("type") or entry.get("serverType") or "custom").lower()
            mapped["type"] = server_type

            base_field_aliases = {
                "url": ["url", "endpoint", "endpointUrl"],
                "description": ["description"],
                "variables": ["variables"],
                "host": ["host"],
                "port": ["port"],
                "database": ["database", "db", "dbname"],
                "catalog": ["catalog"],
                "schema": ["schema"],
                "warehouse": ["warehouse"],
                "account": ["account"],
                "region": ["region"],
                "bucket": ["bucket"],
                "path": ["path"],
                "topic": ["topic"],
                "queue": ["queue"],
            }

            # Type-specific aliases
            type_specific = {
                "snowflake": {
                    "account": ["account", "snowflakeAccount"],
                    "warehouse": ["warehouse"],
                    "database": ["database"],
                    "schema": ["schema"],
                    "role": ["role"],
                    "region": ["region"],
                },
                "s3": {
                    "bucket": ["bucket"],
                    "path": ["path", "prefix"],
                    "region": ["region"],
                },
                "kafka": {
                    "topic": ["topic"],
                    "bootstrap_servers": ["bootstrapServers", "bootstrap"],
                    "security_protocol": ["securityProtocol"],
                },
                "postgresql": {
                    "host": ["host"],
                    "port": ["port"],
                    "database": ["database", "db", "dbname"],
                    "schema": ["schema"],
                    "user": ["user", "username"],
                },
            }

            alias_map = base_field_aliases.copy()
            if server_type in type_specific:
                alias_map.update(type_specific[server_type])

            for target, aliases in alias_map.items():
                for alias in aliases:
                    if alias in entry and entry.get(alias) is not None:
                        mapped[target] = entry[alias]
                        break

            # Preserve any extra properties
            extra = {k: v for k, v in entry.items() if k not in mapped}
            if extra:
                mapped.setdefault("extensions", extra)
            if mapped:
                mapped_servers.append(mapped)
    return mapped_servers or None


def _map_definitions(contract_data: Dict[str, Any]) -> Optional[list]:
    """
    Map ODCS authoritativeDefinitions into canonical definitions array.

    ODCS authoritativeDefinitions can be:
    - A dictionary mapping definition names to field definitions
    - A list of definition objects with 'name' property
    - Nested in description.authoritativeDefinitions

    Returns:
        List of definition entries, or None if no definitions found
    """
    definitions = []

    # Check top-level authoritativeDefinitions
    auth_defs = contract_data.get("authoritativeDefinitions")

    # Also check description.authoritativeDefinitions
    description = contract_data.get("description", {})
    if isinstance(description, dict):
        desc_auth_defs = description.get("authoritativeDefinitions")
        if desc_auth_defs:
            auth_defs = auth_defs or desc_auth_defs

    if not auth_defs:
        return None

    # Handle dictionary format: { "Address": { "type": "object", ... }, ... }
    if isinstance(auth_defs, dict):
        for def_name, def_data in auth_defs.items():
            if not isinstance(def_data, dict):
                continue

            definition = {
                "name": def_name,
            }

            # Map field definition properties
            field_property_map = {
                "type": "type",
                "description": "description",
                "nullable": "nullable",
                "format": "format",
                "pattern": "pattern",
                "enum": "enum",
                "default": "default",
                "minLength": "min_length",
                "maxLength": "max_length",
                "minimum": "minimum",
                "maximum": "maximum",
            }

            for odcs_key, hub_key in field_property_map.items():
                if odcs_key in def_data and def_data[odcs_key] is not None:
                    definition[hub_key] = def_data[odcs_key]

            # Handle nested properties (for object types)
            if "properties" in def_data:
                definition["properties"] = def_data["properties"]

            # Preserve any unmappable fields
            extra = {
                k: v
                for k, v in def_data.items()
                if k not in field_property_map and k != "properties"
            }
            if extra:
                definition.setdefault("extensions", extra)

            definitions.append(definition)

    # Handle list format: [ { "name": "Address", "type": "object", ... }, ... ]
    elif isinstance(auth_defs, list):
        for def_entry in auth_defs:
            if not isinstance(def_entry, dict):
                continue

            # Extract name (required)
            def_name = def_entry.get("name") or def_entry.get("$id", "").split("/")[-1]
            if not def_name:
                continue

            definition = {
                "name": def_name,
            }

            # Map field definition properties
            field_property_map = {
                "type": "type",
                "description": "description",
                "nullable": "nullable",
                "format": "format",
                "pattern": "pattern",
                "enum": "enum",
                "default": "default",
                "minLength": "min_length",
                "maxLength": "max_length",
                "minimum": "minimum",
                "maximum": "maximum",
            }

            for odcs_key, hub_key in field_property_map.items():
                if odcs_key in def_entry and def_entry[odcs_key] is not None:
                    definition[hub_key] = def_entry[odcs_key]

            # Handle nested properties
            if "properties" in def_entry:
                definition["properties"] = def_entry["properties"]

            # Preserve any unmappable fields
            extra = {
                k: v
                for k, v in def_entry.items()
                if k not in field_property_map and k != "properties" and k != "name" and k != "$id"
            }
            if extra:
                definition.setdefault("extensions", extra)

            definitions.append(definition)

    return definitions if definitions else None


def _map_terms(contract_data: Dict[str, Any]) -> Optional[dict]:
    """Map ODCS description usage/limitations into canonical terms."""
    description = contract_data.get("description")
    if not isinstance(description, dict):
        return None
    terms = {}
    for target, alias in {
        "usage": "usage",
        "limitations": "limitations",
        "billing": "billing",
        "support": "support",
        "sla": "sla",
    }.items():
        if alias in description and description.get(alias) is not None:
            terms[target] = description.get(alias)
    # Pricing can come from price object
    price = contract_data.get("price")
    if isinstance(price, dict):
        pricing = {}
        for target, alias in {
            "priceAmount": "priceAmount",
            "priceCurrency": "priceCurrency",
            "priceUnit": "priceUnit",
        }.items():
            if alias in price and price.get(alias) is not None:
                pricing[target] = price.get(alias)
        if pricing:
            terms["pricing"] = pricing
    return terms or None


def _map_fields(
    odcs_schema: Dict[str, Any],
    primary_key_fields: list,
    unique_constraint_fields: list,
    indexed_fields: list,
) -> list:
    """Map schema fields into canonical field definitions."""
    mapped_fields = []
    for field in odcs_schema.get("fields", []) or []:
        if not isinstance(field, dict):
            continue
        field_name = field.get("name", "")
        hub_field = {
            "name": field_name,
            "data_type": field.get("type", "string"),
            "nullable": field.get("nullable", True),
        }
        if "description" in field:
            hub_field["description"] = field["description"]
        if "semantic_type" in field:
            hub_field["semantic_type"] = field["semantic_type"]
        elif "semanticType" in field:
            hub_field["semantic_type"] = field["semanticType"]
        if "format" in field:
            hub_field["format"] = field["format"]
        if "pattern" in field:
            hub_field["pattern"] = field["pattern"]
        if "enum" in field:
            hub_field["enum"] = field["enum"]
        if "default" in field:
            hub_field["default"] = field["default"]
        if "min_length" in field or "minLength" in field:
            hub_field["min_length"] = field.get("min_length") or field.get("minLength")
        if "max_length" in field or "maxLength" in field:
            hub_field["max_length"] = field.get("max_length") or field.get("maxLength")
        if "minimum" in field:
            hub_field["minimum"] = field["minimum"]
            hub_field["min"] = field["minimum"]
        if "maximum" in field:
            hub_field["maximum"] = field["maximum"]
            hub_field["max"] = field["maximum"]
        if "min" in field and "minimum" not in field:
            hub_field["min"] = field["min"]
            hub_field["minimum"] = field["min"]
        if "max" in field and "maximum" not in field:
            hub_field["max"] = field["max"]
            hub_field["maximum"] = field["max"]
        if "metadata" in field:
            hub_field["metadata"] = field["metadata"]

        if field_name in primary_key_fields or field.get("is_primary_key"):
            hub_field["is_primary_key"] = True
        if field_name in unique_constraint_fields or field.get("is_unique"):
            hub_field["is_unique"] = True
        if field_name in indexed_fields or field.get("is_indexed"):
            hub_field["is_indexed"] = True

        # Extract field-level lineage
        from hub.apps.contracts.lineage import extract_field_level_lineage

        field_lineage = extract_field_level_lineage(field)
        if field_lineage:
            hub_field["lineage"] = field_lineage

        mapped_fields.append(hub_field)
    return mapped_fields


def _build_model_from_schema(
    schema_data: Dict[str, Any], fallback_name: str = "default"
) -> Dict[str, Any]:
    """Build canonical model entry from ODCS schema object."""
    if not isinstance(schema_data, dict):
        return {}

    primary_key_fields = []
    if "primary_key" in schema_data:
        primary_key_fields = (
            schema_data["primary_key"]
            if isinstance(schema_data["primary_key"], list)
            else [schema_data["primary_key"]]
        )

    unique_constraint_fields = []
    unique_constraints = None
    if "unique_constraints" in schema_data:
        unique_constraints = schema_data["unique_constraints"]
    elif "uniqueConstraints" in schema_data:
        unique_constraints = schema_data["uniqueConstraints"]

    if unique_constraints:
        for constraint in unique_constraints:
            if isinstance(constraint, dict) and "fields" in constraint:
                unique_constraint_fields.extend(
                    constraint["fields"]
                    if isinstance(constraint["fields"], list)
                    else [constraint["fields"]]
                )
            elif isinstance(constraint, list):
                unique_constraint_fields.extend(constraint)
            else:
                unique_constraint_fields.append(constraint)

    indexed_fields = []
    if "indexes" in schema_data:
        for index in schema_data["indexes"]:
            if isinstance(index, dict) and "fields" in index:
                indexed_fields.extend(
                    index["fields"] if isinstance(index["fields"], list) else [index["fields"]]
                )
            elif isinstance(index, list):
                indexed_fields.extend(index)
            elif isinstance(index, str):
                indexed_fields.append(index)

    # Field-level flags
    if "fields" in schema_data:
        for field in schema_data["fields"]:
            if not isinstance(field, dict):
                continue
            field_name = field.get("name", "")
            if field.get("primaryKey") or field.get("primary_key") or field.get("is_primary_key"):
                if field_name and field_name not in primary_key_fields:
                    primary_key_fields.append(field_name)
            if field.get("unique") or field.get("is_unique"):
                if field_name and field_name not in unique_constraint_fields:
                    unique_constraint_fields.append(field_name)
            if field.get("is_indexed"):
                if field_name and field_name not in indexed_fields:
                    indexed_fields.append(field_name)
        if unique_constraint_fields and not unique_constraints:
            unique_constraints = [[field] for field in unique_constraint_fields]

    fields = _map_fields(schema_data, primary_key_fields, unique_constraint_fields, indexed_fields)
    model_name = schema_data.get("name") or fallback_name
    model_entry: Dict[str, Any] = {"name": model_name, "fields": fields}
    if schema_data.get("description"):
        model_entry["description"] = schema_data.get("description")
    if primary_key_fields:
        model_entry["primary_key"] = primary_key_fields
    if unique_constraints:
        model_entry["unique_constraints"] = unique_constraints
    if indexed_fields:
        model_entry["indexes"] = indexed_fields
    if schema_data.get("logicalType"):
        model_entry["logical_type"] = schema_data.get("logicalType")
    if schema_data.get("physicalType"):
        model_entry["physical_type"] = schema_data.get("physicalType")
    if schema_data.get("physicalName"):
        model_entry["physical_name"] = schema_data.get("physicalName")
    if schema_data.get("dataGranularityDescription"):
        model_entry["data_granularity_description"] = schema_data.get("dataGranularityDescription")
    if schema_data.get("tags"):
        model_entry["tags"] = schema_data.get("tags")

    # Extract model-level lineage
    from hub.apps.contracts.lineage import extract_model_level_lineage

    model_lineage = extract_model_level_lineage(schema_data)
    if model_lineage:
        model_entry["lineage"] = model_lineage

    # Preserve unmappable fields in extensions
    known_fields = {
        "name",
        "description",
        "fields",
        "primary_key",
        "unique_constraints",
        "indexes",
        "logicalType",
        "physicalType",
        "physicalName",
        "dataGranularityDescription",
        "tags",
        "uniqueConstraints",
        "transformSourceObjects",
        "transformLogic",
        "transformDescription",
        "lineage",
        "schema",
        "model",
    }
    unmappable_fields = {}
    for key, value in schema_data.items():
        if key not in known_fields and not key.startswith("_"):
            unmappable_fields[key] = value
    if unmappable_fields:
        model_entry.setdefault("extensions", {})
        model_entry["extensions"].update(unmappable_fields)

    # Validate and enrich advanced schema attributes
    enriched_model, model_errors = validate_and_enrich_advanced_schema_attributes(model_entry)
    # Note: model_errors are warnings, not blocking errors
    if model_errors:
        # Store validation warnings in model extensions for traceability
        enriched_model.setdefault("extensions", {})
        enriched_model["extensions"]["_validation_warnings"] = model_errors

    return enriched_model


def _derive_schema_from_model(model_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Create schema derived view from a canonical model."""
    schema = {"fields": model_entry.get("fields", [])}
    if model_entry.get("primary_key"):
        schema["primary_key"] = model_entry.get("primary_key")
    if model_entry.get("unique_constraints"):
        schema["unique_constraints"] = model_entry.get("unique_constraints")
    if model_entry.get("indexes"):
        schema["indexes"] = model_entry.get("indexes")
    if model_entry.get("tags"):
        schema["tags"] = model_entry.get("tags")
    return schema


def detect_spec_type(contract_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Detect contract specification type and version from contract data.

    Uses enhanced detection logic from spec_detection module.

    Args:
        contract_data: Parsed contract data (dict)

    Returns:
        Tuple of (spec_type, spec_version)
    """
    return detect_spec_type_new(contract_data)


def parse_contract(raw_contract: str, format: str) -> Dict[str, Any]:
    """
    Parse contract from raw string.

    Args:
        raw_contract: Raw contract content
        format: Format (JSON or YAML)

    Returns:
        Parsed contract as dictionary
    """
    if format.upper() == "JSON":
        return json.loads(raw_contract)
    elif format.upper() == "YAML":
        if not YAML_AVAILABLE:
            raise ValueError(
                "PyYAML is required for YAML parsing. Install with: pip install pyyaml"
            )
        # Strip leading/trailing whitespace
        cleaned_contract = raw_contract.strip()

        # Handle YAML strings with leading indentation from multi-line strings
        # Find the minimum indentation across all non-empty lines
        lines = cleaned_contract.split("\n")
        if lines:
            # Calculate indentation for each non-empty line
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                indent_lengths = [len(line) - len(line.lstrip()) for line in non_empty_lines]
                min_indent = min(indent_lengths) if indent_lengths else 0

                # Special case: if first line has no indentation (min_indent = 0) but other lines do,
                # find the minimum indentation of the other lines and remove that
                if min_indent == 0 and len(non_empty_lines) > 1:
                    # Check if any line (other than first) has indentation
                    other_lines = non_empty_lines[1:]
                    other_indent_lengths = [len(line) - len(line.lstrip()) for line in other_lines]
                    if other_indent_lengths and min(other_indent_lengths) > 0:
                        # Use the minimum indent from other lines
                        min_indent = min(other_indent_lengths)

                # If there's common indentation, remove it while preserving relative indentation
                if min_indent > 0:
                    dedented_lines = []
                    for line in lines:
                        if line.strip():  # Non-empty line
                            # Only remove min_indent if the line actually has that much indentation
                            line_indent = len(line) - len(line.lstrip())
                            if line_indent >= min_indent:
                                # Remove min_indent spaces, preserving relative indentation
                                dedented_lines.append(line[min_indent:])
                            else:
                                # Line has less indentation than min_indent, keep it as-is (or strip if needed)
                                # This handles cases where first line has no indentation
                                dedented_lines.append(line.lstrip() if line_indent == 0 else line)
                        else:  # Empty line
                            dedented_lines.append("")
                    cleaned_contract = "\n".join(dedented_lines)

        return yaml.safe_load(cleaned_contract)
    else:
        raise ValueError(f"Unsupported format: {format}")


class ODCSNormalizer:
    """
    SpecNormalizer implementation for ODCS contracts.

    This class now uses ODCSNormalizerBase internally for backward compatibility.
    The normalization logic has been refactored into ODCSNormalizerBase to support
    version-specific normalizers while maintaining the existing API.
    """

    spec_type = OriginalSpecType.ODCS

    def __init__(self):
        """Initialize ODCSNormalizer with default implementation."""
        # Lazy import to avoid circular import
        self._normalizer = None

    def _get_normalizer(self):
        """Get the default normalizer, initializing it if necessary."""
        if self._normalizer is None:
            # Use the default normalizer that supports all versions for backward compatibility
            from hub.apps.contracts.normalization.odcs_normalizer_default import (
                ODCSNormalizerDefault,
            )

            self._normalizer = ODCSNormalizerDefault()
        return self._normalizer

    def supports(self, spec_type: str, spec_version: str, contract_data: Dict[str, Any]) -> bool:
        """Check if this normalizer supports the given spec type and version."""
        return self._get_normalizer().supports(spec_type, spec_version, contract_data)

    def normalize(
        self, contract_data: Dict[str, Any], spec_version: Optional[str] = None
    ) -> NormalizationResult:
        """Normalize ODCS contract data to HubContract format."""
        return self._get_normalizer().normalize(contract_data, spec_version)


# Register default normalizers
register_normalizer(ODCSNormalizer())

# Register ODCS version-specific normalizers
try:
    from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2

    register_normalizer(ODCSNormalizerV3_0_2())
except ImportError:
    # ODCS 3.0.2 normalizer not available (should not happen in production)
    pass

try:
    from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import (
        ODCSNormalizerV3_0_0_Preview,
    )

    register_normalizer(ODCSNormalizerV3_0_0_Preview())
except ImportError:
    # ODCS 3.0.0-preview normalizer not available (should not happen in production)
    pass

# Register ODPS normalizers
try:
    from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer

    register_normalizer(ODPSNormalizer())
except ImportError:
    # ODPS normalizer not available (should not happen in production)
    pass

# Register ODPS version-specific normalizers (backward compatibility)
try:
    from hub.apps.contracts.normalization.odps_normalizer_v4_1 import ODPSNormalizerV4_1

    register_normalizer(ODPSNormalizerV4_1())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odps_normalizer_v4_0 import ODPSNormalizerV4_0

    register_normalizer(ODPSNormalizerV4_0())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odps_normalizer_v3_x import ODPSNormalizerV3_X

    register_normalizer(ODPSNormalizerV3_X())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odps_normalizer_v2_x import ODPSNormalizerV2_X

    register_normalizer(ODPSNormalizerV2_X())
except ImportError:
    pass

# Register ODCS version-specific normalizers
try:
    from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1

    register_normalizer(ODCSNormalizerV3_0_1())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0

    register_normalizer(ODCSNormalizerV3_0_0())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2

    register_normalizer(ODCSNormalizerV2_2_2())
except ImportError:
    pass

try:
    from hub.apps.contracts.normalization.odps_normalizer_v1_x import ODPSNormalizerV1_X

    register_normalizer(ODPSNormalizerV1_X())
except ImportError:
    pass


def normalize_contract(
    raw_contract: str, format: str, spec_type: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], str, str, NormalizationStatus, list, list]:
    """
    Normalize contract to HubContract format.

    Supports:
    - Open Data Contract Standard (ODCS) v2.2.2, v3.0.0, v3.0.0-preview, v3.0.1, v3.0.2+
    - Open Data Product Standard (ODPS) v1.x, v2.x, v3.x, v4.0, v4.1+

    Args:
        raw_contract: Raw contract content
        format: Format (JSON or YAML)
        spec_type: Optional spec type (ODCS or ODPS). If None, will be detected.

    Returns:
        Tuple of (hub_contract_json, detected_spec_type, detected_spec_version, normalization_status, errors, warnings)
    """
    try:
        # Parse contract
        contract_data = parse_contract(raw_contract, format)

        # Detect spec type if not provided
        if not spec_type:
            spec_type, spec_version = detect_spec_type(contract_data)
        else:
            spec_version = contract_data.get("version", "1.0")

        normalizer = get_normalizer(spec_type, spec_version, contract_data)
        if not normalizer:
            errors = [
                f"No normalizer registered for spec type {spec_type} (version {spec_version}). "
                "Ensure a SpecNormalizer is registered for this spec type."
            ]
            return (
                None,
                spec_type,
                spec_version,
                NormalizationStatus.NORMALIZATION_FAILED,
                errors,
                [],
            )

        # For ODCS fallback: if we got a 3.0.2 normalizer for an unknown version,
        # use "3.0.2" as the spec_version for normalization
        from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2

        if (
            spec_type == OriginalSpecType.ODCS
            and spec_version != "3.0.2"
            and isinstance(normalizer, ODCSNormalizerV3_0_2)
        ):
            # Use 3.0.2 as the version for normalization when using fallback
            normalization_version = "3.0.2"
        else:
            normalization_version = spec_version

        result = normalizer.normalize(contract_data, spec_version=normalization_version)
        hub_contract, status, errors, warnings = (
            result.hub_contract,
            result.status,
            result.errors,
            result.warnings,
        )
        spec_version = result.spec_version or spec_version

        # Store original spec metadata in HubContract
        if hub_contract:
            hub_contract = store_original_spec_metadata(hub_contract, contract_data)

        # Ensure all contracts have version "1.0.0" during development
        if hub_contract:
            hub_contract = ensure_version(hub_contract)
            if not hub_contract.get("hub_contract_version"):
                hub_contract["hub_contract_version"] = get_default_version()

        return hub_contract, spec_type, spec_version, status, errors, warnings

    except Exception as e:
        errors = [f"Failed to normalize contract: {str(e)}"]
        # Return ODCS as default spec type
        return (
            None,
            OriginalSpecType.ODCS,
            "3.0.2",
            NormalizationStatus.NORMALIZATION_FAILED,
            errors,
            [],
        )


def validate_hubcontract_schema(hub_contract: Dict[str, Any]) -> Tuple[bool, list]:
    """
    Validate HubContract JSON against schema.

    Args:
        hub_contract: HubContract JSON

    Returns:
        Tuple of (is_valid: bool, errors: list)
    """
    validated_contract, validation_errors = validate_hub_contract_dict(hub_contract)
    if validation_errors:
        return False, validation_errors

    errors = []
    expected_version = get_default_version()
    if validated_contract and validated_contract.hub_contract_version != expected_version:
        errors.append(
            f'Invalid hub_contract_version: {validated_contract.hub_contract_version} (expected: "{expected_version}")'
        )

    return len(errors) == 0, errors
