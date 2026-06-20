"""
HubContract Version Migration

Implements migration strategies for HubContract version upgrades.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Current HubContract version
CURRENT_HUBCONTRACT_VERSION = "1.0.0"


class MigrationStrategy:
    """Migration strategy enumeration"""

    ON_WRITE = "ON_WRITE"  # Migrate when contract is updated
    ON_READ = "ON_READ"  # Migrate when contract is accessed (lazy)
    BACKGROUND = "BACKGROUND"  # Queue background migration job


def migrate_hubcontract_v1_to_v2(
    hub_contract_v1: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    Migrate HubContract from v1 to v2 (GAP-10.2.1).

    Handles migration of:
    - Owners and tags from old format
    - Quality, compliance, lifecycle, marketplace sections
    - Field properties (semantic_type, format, pattern, etc.)
    - Generates warnings for missing sections

    Args:
        hub_contract_v1: HubContract v1.0.0 JSON

    Returns:
        Tuple of (hub_contract_v2, warnings)
    """
    warnings = []
    hub_contract_v2 = hub_contract_v1.copy()

    # Ensure hub_contract_version is set to 2
    hub_contract_v2["hub_contract_version"] = 2

    # Migrate info section: owners and tags (GAP-10.2.1)
    info = hub_contract_v2.get("info", {})
    if not info:
        info = {}
        hub_contract_v2["info"] = info
        warnings.append("Missing 'info' section - created empty section")

    # Migrate owners from old format (if exists in extensions or old location)
    if "owners" not in info:
        # Check extensions for old owner format
        extensions = hub_contract_v2.get("extensions", {})
        if extensions:
            # Check ODCS extensions
            odcs_ext = extensions.get("odcs", {})
            if odcs_ext and "owners" in odcs_ext:
                info["owners"] = odcs_ext["owners"]
                warnings.append("Migrated owners from extensions.odcs")

    # Migrate tags from old format
    if "tags" not in info:
        extensions = hub_contract_v2.get("extensions", {})
        if extensions:
            odcs_ext = extensions.get("odcs", {})
            if odcs_ext and "tags" in odcs_ext:
                info["tags"] = odcs_ext["tags"]
                warnings.append("Migrated tags from extensions.odcs")

    # Migrate quality section (GAP-10.2.1)
    if "quality" not in hub_contract_v2:
        quality = {}
        hub_contract_v2["quality"] = quality
        warnings.append("Missing 'quality' section - created empty section")
    else:
        quality = hub_contract_v2["quality"]
        # Ensure rules array exists
        if "rules" not in quality:
            quality["rules"] = []
        # Ensure default_profile_key exists if quality section is present
        if "default_profile_key" not in quality:
            quality["default_profile_key"] = None

    # Migrate privacy_compliance section (GAP-10.2.1)
    if "privacy_compliance" not in hub_contract_v2:
        # Check for old 'compliance' key
        if "compliance" in hub_contract_v2:
            hub_contract_v2["privacy_compliance"] = hub_contract_v2.pop("compliance")
            warnings.append("Migrated 'compliance' section to 'privacy_compliance'")
        else:
            privacy_compliance = {}
            hub_contract_v2["privacy_compliance"] = privacy_compliance
            warnings.append("Missing 'privacy_compliance' section - created empty section")
    else:
        privacy_compliance = hub_contract_v2["privacy_compliance"]
        # Ensure required fields exist
        if "contains_personal_data" not in privacy_compliance:
            privacy_compliance["contains_personal_data"] = False
        if "personal_data_categories" not in privacy_compliance:
            privacy_compliance["personal_data_categories"] = []
        if "jurisdictions" not in privacy_compliance:
            privacy_compliance["jurisdictions"] = []
        if "legal_bases" not in privacy_compliance:
            privacy_compliance["legal_bases"] = []

    # Migrate lifecycle section (GAP-10.2.1)
    if "lifecycle" not in hub_contract_v2:
        lifecycle = {}
        hub_contract_v2["lifecycle"] = lifecycle
        warnings.append("Missing 'lifecycle' section - created empty section")
    else:
        lifecycle = hub_contract_v2["lifecycle"]
        # Ensure required fields exist
        if "data_source" not in lifecycle:
            lifecycle["data_source"] = None
        if "refresh_cadence" not in lifecycle:
            lifecycle["refresh_cadence"] = None
        if "slas" not in lifecycle:
            lifecycle["slas"] = {}

    # Migrate marketplace section (GAP-10.2.1)
    if "marketplace" not in hub_contract_v2:
        marketplace = {}
        hub_contract_v2["marketplace"] = marketplace
        warnings.append("Missing 'marketplace' section - created empty section")
    else:
        marketplace = hub_contract_v2["marketplace"]
        # Ensure required fields exist
        if "license_summary" not in marketplace:
            marketplace["license_summary"] = None
        if "intended_use" not in marketplace:
            marketplace["intended_use"] = []
        if "restricted_use" not in marketplace:
            marketplace["restricted_use"] = []

    # Migrate schema.fields with enhanced properties (GAP-10.2.1)
    schema = hub_contract_v2.get("schema", {})
    if not schema:
        schema = {}
        hub_contract_v2["schema"] = schema
        warnings.append("Missing 'schema' section - created empty section")

    fields = schema.get("fields", [])
    if not fields:
        warnings.append("Missing 'schema.fields' - schema has no fields")
    else:
        # Migrate each field to include all properties (GAP-10.2.1)
        for field in fields:
            # Ensure basic properties exist
            if "name" not in field:
                warnings.append("Field missing 'name' property")
                continue

            # Migrate field properties from old format
            # Check if semantic_type, format, pattern, etc. are missing
            if "semantic_type" not in field:
                field["semantic_type"] = None
            if "format" not in field:
                field["format"] = None
            if "pattern" not in field:
                field["pattern"] = None
            if "enum" not in field:
                field["enum"] = None
            if "default" not in field:
                field["default"] = None
            if "min_length" not in field:
                field["min_length"] = None
            if "max_length" not in field:
                field["max_length"] = None
            if "minimum" not in field:
                field["minimum"] = None
            if "maximum" not in field:
                field["maximum"] = None
            if "metadata" not in field:
                field["metadata"] = {}

            # Migrate constraint flags
            if "is_primary_key" not in field:
                # Check if field is in primary_key array
                primary_key = schema.get("primary_key", [])
                field["is_primary_key"] = field.get("name") in primary_key
            if "is_unique" not in field:
                # Check if field is in unique_constraints
                unique_constraints = schema.get("unique_constraints", [])
                field["is_unique"] = any(
                    field.get("name")
                    in (constraint if isinstance(constraint, list) else [constraint])
                    for constraint in unique_constraints
                )
            if "is_indexed" not in field:
                # Check if field is in indexes
                indexes = schema.get("indexes", [])
                field["is_indexed"] = any(
                    field.get("name") in (index if isinstance(index, list) else [index])
                    for index in indexes
                )

    # Ensure schema has primary_key, unique_constraints, indexes arrays
    if "primary_key" not in schema:
        schema["primary_key"] = []
    if "unique_constraints" not in schema:
        schema["unique_constraints"] = []
    if "indexes" not in schema:
        schema["indexes"] = []

    return hub_contract_v2, warnings


def migrate_hubcontract_v0_to_v1(hub_contract_v0):
    """
    Migrate HubContract from pre-v1 to v1.0.0 format.

    Handles migration of pre-v1 contracts to v1 format,
    adding required sections and normalizing the structure.

    Args:
        hub_contract_v0: HubContract pre-v1.0.0 JSON

    Returns:
        Tuple of (hub_contract_v1, warnings)
    """
    warnings = []
    hub_contract_v1 = hub_contract_v0.copy()

    # Set to v1
    hub_contract_v1["hub_contract_version"] = 1

    # Remove legacy 'version' field if present
    if "version" in hub_contract_v1:
        del hub_contract_v1["version"]

    # Ensure required v1 sections exist
    if "info" not in hub_contract_v1:
        hub_contract_v1["info"] = {}
        warnings.append("Missing 'info' section - created empty section")

    # Ensure schema section with required arrays
    if "schema" not in hub_contract_v1:
        hub_contract_v1["schema"] = {
            "fields": [],
            "primary_key": [],
            "unique_constraints": [],
            "indexes": [],
        }
        warnings.append("Missing 'schema' section - created empty section")
    else:
        schema = hub_contract_v1["schema"]
        if "primary_key" not in schema:
            schema["primary_key"] = []
        if "unique_constraints" not in schema:
            schema["unique_constraints"] = []
        if "indexes" not in schema:
            schema["indexes"] = []

    # Add other standard v1 sections
    for section in ["quality", "privacy_compliance", "lifecycle", "marketplace"]:
        if section not in hub_contract_v1:
            hub_contract_v1[section] = {}
            warnings.append(f"Missing '{section}' section - created empty section")

    return hub_contract_v1, warnings


def migrate_hubcontract(
    hub_contract: dict[str, Any], source_version: str, target_version: str
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """
    Migrate HubContract between versions.

    Args:
        hub_contract: HubContract JSON
        source_version: Source HubContract version (e.g., "1.0.0")
        target_version: Target HubContract version (e.g., "2.0.0")

    Returns:
        Tuple of (migrated_hub_contract, warnings, errors)
    """
    errors = []
    warnings = []

    if source_version == target_version:
        # No migration needed
        return hub_contract, warnings, errors

    # Parse version numbers
    try:
        source_major = int(source_version.split(".")[0])
        target_major = int(target_version.split(".")[0])
    except (ValueError, IndexError):
        errors.append(f"Invalid version format: {source_version} or {target_version}")
        return None, warnings, errors

    # Only support forward migration (upgrade)
    if source_major > target_major:
        errors.append(f"Cannot downgrade from {source_version} to {target_version}")
        return None, warnings, errors

    # Migration path: v1 -> v2
    if source_major == 1 and target_major == 2:
        try:
            migrated, migration_warnings = migrate_hubcontract_v1_to_v2(hub_contract)
            warnings.extend(migration_warnings)
            return migrated, warnings, errors
        except Exception as e:
            errors.append(f"Migration failed: {e!s}")
            logger.exception("HubContract migration failed")
            return None, warnings, errors

    # Migration path: pre-v1 (0.x) -> v1 (1.x)
    if source_major == 0 and target_major == 1:
        try:
            migrated, migration_warnings = migrate_hubcontract_v0_to_v1(hub_contract)
            warnings.extend(migration_warnings)
            return migrated, warnings, errors
        except Exception as e:
            errors.append(f"Migration failed: {e!s}")
            logger.exception("HubContract v0->v1 migration failed")
            return None, warnings, errors

    # Future migration paths can be added here
    # e.g., v2 -> v3, v1 -> v3 (via v2)

    errors.append(f"Migration from {source_version} to {target_version} not supported")
    return None, warnings, errors


def get_current_hubcontract_version() -> str:
    """
    Get current HubContract version.

    Returns:
        Current HubContract version string
    """
    return CURRENT_HUBCONTRACT_VERSION


def needs_migration(hub_contract_version: str | None) -> bool:
    """
    Check if contract needs migration.

    Args:
        hub_contract_version: Current HubContract version

    Returns:
        True if migration is needed
    """
    if not hub_contract_version:
        return False  # Not normalized yet

    current_version = get_current_hubcontract_version()
    return hub_contract_version != current_version


def can_migrate(source_version: str, target_version: str) -> bool:
    """
    Check if migration is supported.

    Args:
        source_version: Source version
        target_version: Target version

    Returns:
        True if migration is supported
    """
    try:
        source_major = int(source_version.split(".")[0])
        target_major = int(target_version.split(".")[0])

        # Only support forward migration
        if source_major > target_major:
            return False

        # Support v1 -> v2
        if source_major == 1 and target_major == 2:
            return True

        # Support pre-v1 (0.x) -> v1 (1.x)
        if source_major == 0 and target_major == 1:
            return True

        # Add more migration paths as needed

        return False
    except (ValueError, IndexError):
        return False
