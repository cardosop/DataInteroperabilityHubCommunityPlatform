"""
ODCS Contract Generator

Generates ODCS contracts from inferred schemas and HubContracts.
"""
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

logger = None
try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def generate_odcs_from_schema(
    inferred_schema: Dict[str, Any],
    contract_id: Optional[str] = None,
    contract_name: Optional[str] = None,
    contract_description: Optional[str] = None,
    contract_version: str = "1.0.0",
    odcs_version: str = "v3"
) -> Dict[str, Any]:
    """
    Generate ODCS contract from inferred schema.

    Maps inferred schema fields to ODCS contract format:
    - inferred_schema.fields → schema.fields
    - inferred_schema.primary_key_candidates → schema.primary_key
    - inferred_schema.unique_constraint_candidates → schema.unique_constraints
    - inferred_schema.index_recommendations → schema.indexes

    Args:
        inferred_schema: Inferred schema dictionary with fields, primary_key_candidates, etc.
        contract_id: Contract ID (default: auto-generated UUID)
        contract_name: Contract name (default: "Generated Contract")
        contract_description: Contract description (optional)
        contract_version: Contract version (default: "1.0.0")
        odcs_version: ODCS version (default: "v3")

    Returns:
        ODCS contract as dictionary

    Raises:
        ValueError: If inferred_schema is invalid or missing required fields
    """
    if not isinstance(inferred_schema, dict):
        raise ValueError("inferred_schema must be a dictionary")

    fields = inferred_schema.get("fields", [])
    if not fields or not isinstance(fields, list):
        raise ValueError("inferred_schema must have a 'fields' list with at least one field")

    # Generate contract ID if not provided
    if not contract_id:
        contract_id = f"generated-{uuid.uuid4().hex[:8]}"

    # Generate contract name if not provided
    if not contract_name:
        contract_name = "Generated Contract from Data"

    # Build ODCS contract
    odcs_contract = {
        "apiVersion": f"odcs/{odcs_version}",
        "kind": "DataContract",
        "id": contract_id,
        "name": contract_name,
        "version": contract_version
    }

    # Add description if provided
    if contract_description:
        odcs_contract["description"] = contract_description

    # Build schema section
    schema_fields = []
    primary_key = []
    unique_constraints = []
    indexes = []

    for field in fields:
        if not isinstance(field, dict):
            continue

        field_name = field.get("name")
        if not field_name:
            continue

        # Map inferred field to ODCS field format
        odcs_field = {
            "name": field_name,
            "type": field.get("data_type", "string")
        }

        # Add optional properties
        if "nullable" in field:
            odcs_field["nullable"] = field["nullable"]
        if "description" in field:
            odcs_field["description"] = field["description"]
        if "format" in field:
            odcs_field["format"] = field["format"]
        if "pattern" in field:
            odcs_field["pattern"] = field["pattern"]
        if "enum" in field:
            odcs_field["enum"] = field["enum"]
        if "default" in field:
            odcs_field["default"] = field["default"]
        if "min_length" in field:
            odcs_field["minLength"] = field["min_length"]
        if "max_length" in field:
            odcs_field["maxLength"] = field["max_length"]
        if "minimum" in field:
            odcs_field["minimum"] = field["minimum"]
        if "maximum" in field:
            odcs_field["maximum"] = field["maximum"]

        schema_fields.append(odcs_field)

        # Check for primary key flag
        if field.get("is_primary_key") or field_name in inferred_schema.get("primary_key_candidates", []):
            if field_name not in primary_key:
                primary_key.append(field_name)

        # Check for unique constraint flag
        if field.get("is_unique") or field_name in inferred_schema.get("unique_constraint_candidates", []):
            if field_name not in [uc[0] if isinstance(uc, list) and len(uc) > 0 else uc for uc in unique_constraints]:
                unique_constraints.append([field_name])

        # Check for index flag
        if field.get("is_indexed"):
            if field_name not in [idx[0] if isinstance(idx, list) and len(idx) > 0 else idx for idx in indexes]:
                indexes.append([field_name])

    # Add primary key from candidates if not already set
    primary_key_candidates = inferred_schema.get("primary_key_candidates", [])
    for pk_candidate in primary_key_candidates:
        if pk_candidate not in primary_key:
            primary_key.append(pk_candidate)

    # Add unique constraints from candidates if not already set
    unique_constraint_candidates = inferred_schema.get("unique_constraint_candidates", [])
    for uc_candidate in unique_constraint_candidates:
        if uc_candidate not in [uc[0] if isinstance(uc, list) and len(uc) > 0 else uc for uc in unique_constraints]:
            unique_constraints.append([uc_candidate])

    # Add indexes from recommendations if not already set
    index_recommendations = inferred_schema.get("index_recommendations", [])
    for idx_rec in index_recommendations:
        if isinstance(idx_rec, dict):
            field_name = idx_rec.get("field")
            if field_name and field_name not in [idx[0] if isinstance(idx, list) and len(idx) > 0 else idx for idx in indexes]:
                indexes.append([field_name])

    # Build schema object
    schema = {
        "fields": schema_fields
    }

    if primary_key:
        schema["primary_key"] = primary_key if len(primary_key) > 1 else primary_key[0]

    if unique_constraints:
        schema["unique_constraints"] = unique_constraints

    if indexes:
        schema["indexes"] = indexes

    odcs_contract["schema"] = schema

    # Add metadata
    odcs_contract["metadata"] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "generated_from": "inferred_schema",
        "row_count_estimated": inferred_schema.get("row_count_estimated")
    }

    if logger:
        try:
            logger.info(
                "ODCS contract generated from schema",
                contract_id=contract_id,
                fields_count=len(schema_fields),
                primary_key=str(primary_key),
                unique_constraints_count=len(unique_constraints),
                indexes_count=len(indexes)
            )
        except (TypeError, AttributeError):
            # Fallback for non-structlog loggers
            logger.info(
                f"ODCS contract generated from schema: contract_id={contract_id}, "
                f"fields_count={len(schema_fields)}, primary_key={primary_key}, "
                f"unique_constraints_count={len(unique_constraints)}, indexes_count={len(indexes)}"
            )

    return odcs_contract

