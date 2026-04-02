"""
ODCS Generator

Generates ODCS (Open Data Contract Standard) documents from HubContract format.
Supports ODCS 3.0.2 generation with comprehensive error handling.

This module provides the reverse operation of ODCS normalization:
- HubContract → ODCS 3.0.2

Key Features:
- Comprehensive error handling with ODCSExportError and ODCSGenerationError
- Field-level error context (field name, expected type, actual type)
- Support for ODCS 3.0.2 (latest version)
- Graceful handling of missing optional fields
- YAML and JSON output formatting
"""
import structlog
import uuid
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from hub.apps.contracts.odcs_errors import ODCSExportError, ODCSGenerationError

logger = structlog.get_logger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None


class ODCSGeneratorBase(ABC):
    """
    Abstract base class for version-specific ODCS generators.

    Provides common generation logic and defines hooks for version-specific implementations.
    Subclasses must implement:
    - `generate_odcs_from_hubcontract()`: Generate ODCS document from HubContract

    Common functionality provided:
    - HubContract structure validation
    - Error handling with field-level context (field_path, expected, actual)
    - Structured logging with structlog
    - Common validation methods for required fields

    This refactors the existing `generate_odcs_from_hubcontract` function into a class-based
    approach to support version-specific generators while maintaining backward compatibility.
    """

    def __init__(self):
        """Initialize the ODCS generator base class."""
        self.logger = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS document from HubContract format.

        This is the primary method that subclasses must implement.
        It should handle version-specific ODCS generation logic.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (optional, may be determined by subclass)

        Returns:
            ODCS document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with context including:
                - field_path: Path to the field that caused the error
                - expected: Expected type or value
                - actual: Actual type or value that caused the error
        """
        pass

    def validate_hub_contract_structure(
        self,
        hub_contract: Dict[str, Any],
        field_path: str = "/"
    ) -> None:
        """
        Validate HubContract structure.

        Validates that the HubContract has the required structure:
        - Must be a dictionary
        - Must have 'info' section (dict)
        - Must have 'info.name' (non-empty string)
        - Must have 'id' (string)

        Args:
            hub_contract: HubContract dictionary to validate
            field_path: Current field path for error context (default: "/")

        Raises:
            ODCSGenerationError: If validation fails with field-level context
        """
        # Validate root is a dictionary
        if not isinstance(hub_contract, dict):
            raise ODCSGenerationError(
                message=f"HubContract must be a dictionary, got {type(hub_contract).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": field_path,
                    "expected": "dict",
                    "actual": type(hub_contract).__name__,
                },
            )

        # Validate required 'info' section
        if "info" not in hub_contract:
            raise ODCSGenerationError(
                message="HubContract missing required 'info' section",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": f"{field_path}info",
                    "expected": "dict",
                    "actual": None,
                },
            )

        info = hub_contract.get("info")
        if not isinstance(info, dict):
            raise ODCSGenerationError(
                message=f"HubContract 'info' must be a dictionary, got {type(info).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": f"{field_path}info",
                    "expected": "dict",
                    "actual": type(info).__name__,
                },
            )

        # Validate required 'info.name'
        if "name" not in info:
            raise ODCSGenerationError(
                message="HubContract 'info.name' is required",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": f"{field_path}info/name",
                    "expected": "str",
                    "actual": None,
                },
            )

        name = info.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ODCSGenerationError(
                message=f"HubContract 'info.name' must be a non-empty string, got {type(name).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": f"{field_path}info/name",
                    "expected": "str (non-empty)",
                    "actual": type(name).__name__ if name is not None else None,
                },
            )

        # Validate 'id' field (required)
        if "id" not in hub_contract:
            raise ODCSGenerationError(
                message="HubContract 'id' is required",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": f"{field_path}id",
                    "expected": "str",
                    "actual": None,
                },
            )

        contract_id = hub_contract.get("id")
        if not isinstance(contract_id, str):
            raise ODCSGenerationError(
                message=f"HubContract 'id' must be a string, got {type(contract_id).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": f"{field_path}id",
                    "expected": "str",
                    "actual": type(contract_id).__name__,
                },
            )

        # Log successful validation
        self.logger.debug(
            "hub_contract_structure_validated",
            contract_id=contract_id,
            name=name,
            field_path=field_path,
        )

    def validate_field_type(
        self,
        value: Any,
        expected_type: type,
        field_path: str,
        allow_none: bool = False
    ) -> None:
        """
        Validate field type with detailed error context.

        Args:
            value: Value to validate
            expected_type: Expected Python type (e.g., str, dict, list)
            field_path: JSON Pointer path to the field
            allow_none: If True, None values are allowed (default: False)

        Raises:
            ODCSGenerationError: If validation fails with field-level context
        """
        if value is None:
            if allow_none:
                return
            raise ODCSGenerationError(
                message=f"Field '{field_path}' must not be None",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": field_path,
                    "expected": expected_type.__name__,
                    "actual": None,
                },
            )

        if not isinstance(value, expected_type):
            raise ODCSGenerationError(
                message=f"Field '{field_path}' must be of type {expected_type.__name__}, got {type(value).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": field_path,
                    "expected": expected_type.__name__,
                    "actual": type(value).__name__,
                },
            )

    def log_generation_start(
        self,
        contract_id: str,
        name: str,
        target_version: Optional[str] = None
    ) -> None:
        """
        Log generation start with structured logging.

        Args:
            contract_id: Contract ID
            name: Contract name
            target_version: Target ODCS version (optional)
        """
        self.logger.info(
            "odcs_generation_started",
            contract_id=contract_id,
            name=name,
            target_version=target_version,
            generator_class=self.__class__.__name__,
        )

    def log_generation_complete(
        self,
        contract_id: str,
        name: str,
        target_version: Optional[str] = None
    ) -> None:
        """
        Log generation completion with structured logging.

        Args:
            contract_id: Contract ID
            name: Contract name
            target_version: Target ODCS version (optional)
        """
        self.logger.info(
            "odcs_generation_completed",
            contract_id=contract_id,
            name=name,
            target_version=target_version,
            generator_class=self.__class__.__name__,
        )

    def log_generation_error(
        self,
        error: Exception,
        contract_id: Optional[str] = None,
        field_path: Optional[str] = None
    ) -> None:
        """
        Log generation error with structured logging.

        Args:
            error: Exception that occurred
            contract_id: Contract ID (optional)
            field_path: Field path where error occurred (optional)
        """
        self.logger.error(
            "odcs_generation_error",
            error=str(error),
            error_type=type(error).__name__,
            contract_id=contract_id,
            field_path=field_path,
            generator_class=self.__class__.__name__,
            exc_info=True,
        )


class ODCSGeneratorV2_2_2(ODCSGeneratorBase):
    """
    ODCS 2.2.2 Generator implementation.

    Generates ODCS 2.2.2 documents from HubContract format.
    Handles major version differences from 3.x:
    - Gracefully degrades all 3.x-only features (warns and omits)
    - Supports all ODCS 2.2.2 features
    - Maps HubContract fields to ODCS 2.2.2 structure

    Key Mappings:
    - hub_contract.id → odcs.id
    - hub_contract.info.name → odcs.name
    - hub_contract.info.description → odcs.description
    - hub_contract.info.version → odcs.version
    - hub_contract.schema → odcs.schema
    - hub_contract.quality → odcs.quality (basic support)

    Key differences from 3.x:
    - Enhanced marketplace features (3.x+) are not supported
    - Enhanced lifecycle features (3.x+) are not supported
    - Privacy compliance features may have limited support
    - All 3.x-specific features are gracefully degraded
    """

    def __init__(self):
        """Initialize the ODCS 2.2.2 generator."""
        super().__init__()
        self.target_version = "2.2.2"

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS 2.2.2 document from HubContract format.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (ignored, always uses 2.2.2)

        Returns:
            ODCS 2.2.2 document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with field-level context
        """
        try:
            # Validate HubContract structure first
            self.validate_hub_contract_structure(hub_contract)

            contract_id = hub_contract["id"]
            info = hub_contract["info"]
            name = info["name"]

            self.log_generation_start(contract_id, name, self.target_version)

            # Initialize ODCS 2.2.2 document structure
            odcs_doc = {
                "apiVersion": f"odcs.io/v{self.target_version}",
                "kind": "DataContract",
                "id": contract_id,
                "name": name,
            }

            # Map basic info fields
            if "description" in info and info["description"]:
                self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
                odcs_doc["description"] = info["description"]

            if "version" in info and info["version"]:
                self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
                odcs_doc["version"] = info["version"]

            # Map info section (owners, tags, etc.)
            self._map_info_section(hub_contract, odcs_doc)

            # Map schema section (ODCS 2.2.2 format)
            self._map_schema_section_v2_2_2(hub_contract, odcs_doc)

            # Map quality section (basic support in 2.2.2)
            self._map_quality_section_v2_2_2(hub_contract, odcs_doc)

            # Map lifecycle section (with graceful degradation for 3.x features)
            self._map_lifecycle_section_v2_2_2(hub_contract, odcs_doc)

            # Map marketplace section (with graceful degradation for 3.x features)
            self._map_marketplace_section_v2_2_2(hub_contract, odcs_doc)

            # Map privacy_compliance section (limited support in 2.2.2)
            self._map_privacy_compliance_section_v2_2_2(hub_contract, odcs_doc)

            self.log_generation_complete(contract_id, name, self.target_version)
            return odcs_doc

        except ODCSGenerationError:
            # Re-raise ODCS errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.log_generation_error(e, hub_contract.get("id"))
            raise ODCSGenerationError(
                message=f"Unexpected error generating ODCS 2.2.2 document: {str(e)}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                cause=e,
            ) from e

    def _map_schema_section_v2_2_2(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract schema section to ODCS 2.2.2 format.

        ODCS 2.2.2 uses direct schema.fields[] array (similar to 3.0.1).

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        schema = hub_contract.get("schema")
        if not schema or not isinstance(schema, dict):
            return

        odcs_schema = {}

        # Map fields (ODCS 2.2.2 uses direct fields array)
        fields = schema.get("fields", [])
        if fields:
            odcs_fields = []
            for field in fields:
                if not isinstance(field, dict):
                    continue
                odcs_field = {
                    "name": field.get("name"),
                    "type": field.get("data_type") or field.get("type", "string"),
                }
                # Add optional field properties (basic support in 2.2.2)
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
                if "min_length" in field or "minLength" in field:
                    odcs_field["minLength"] = field.get("min_length") or field.get("minLength")
                if "max_length" in field or "maxLength" in field:
                    odcs_field["maxLength"] = field.get("max_length") or field.get("maxLength")
                if "minimum" in field:
                    odcs_field["minimum"] = field["minimum"]
                if "maximum" in field:
                    odcs_field["maximum"] = field["maximum"]
                odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        primary_key = schema.get("primary_key")
        if primary_key:
            if isinstance(primary_key, list):
                odcs_schema["primary_key"] = primary_key if len(primary_key) > 1 else primary_key[0] if primary_key else None
            elif isinstance(primary_key, str):
                odcs_schema["primary_key"] = primary_key

        # Map unique_constraints
        unique_constraints = schema.get("unique_constraints")
        if unique_constraints:
            odcs_schema["unique_constraints"] = unique_constraints

        # Map indexes
        indexes = schema.get("indexes")
        if indexes:
            odcs_schema["indexes"] = indexes

        if odcs_schema:
            odcs_doc["schema"] = odcs_schema

    def _map_quality_section_v2_2_2(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract quality section to ODCS 2.2.2 format.

        ODCS 2.2.2 has basic quality support.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        quality = hub_contract.get("quality")
        if not quality or not isinstance(quality, dict):
            return

        odcs_quality = {}

        # Map default_profile_key (if supported in 2.2.2)
        if "default_profile_key" in quality:
            odcs_quality["default_profile_key"] = quality["default_profile_key"]

        # Map rules (basic support in 2.2.2)
        rules = quality.get("rules", [])
        if rules:
            odcs_rules = []
            for rule in rules:
                if isinstance(rule, dict):
                    odcs_rule = {}
                    if "name" in rule:
                        odcs_rule["name"] = rule["name"]
                    if "type" in rule:
                        odcs_rule["type"] = rule["type"]
                    if "description" in rule:
                        odcs_rule["description"] = rule["description"]
                    if "expression" in rule:
                        odcs_rule["expression"] = rule["expression"]
                    if "severity" in rule:
                        odcs_rule["severity"] = rule["severity"]
                    if odcs_rule:
                        odcs_rules.append(odcs_rule)
            if odcs_rules:
                odcs_quality["rules"] = odcs_rules

        if odcs_quality:
            odcs_doc["quality"] = odcs_quality

    def _map_lifecycle_section_v2_2_2(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract lifecycle section to ODCS 2.2.2 format.

        ODCS 2.2.2 has limited lifecycle support. Gracefully degrades all 3.x features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        lifecycle = hub_contract.get("lifecycle")
        if not lifecycle or not isinstance(lifecycle, dict):
            return

        odcs_lifecycle = {}

        # ODCS 2.2.2 has very limited lifecycle support
        # Only map basic fields if they exist, but most lifecycle features are 3.x+
        if "data_source" in lifecycle:
            odcs_lifecycle["data_source"] = lifecycle["data_source"]

        # Check for 3.x lifecycle features and warn
        three_x_features = []
        if "refresh_cadence" in lifecycle:
            three_x_features.append("refresh_cadence")
        if "slas" in lifecycle:
            three_x_features.append("slas")
        if "enhanced_features" in lifecycle:
            three_x_features.append("enhanced_features")
        if "advanced_slas" in lifecycle:
            three_x_features.append("advanced_slas")

        if three_x_features:
            self.logger.warning(
                "odcs_v2_2_2_lifecycle_features_omitted",
                features=three_x_features,
                message=f"ODCS 3.x lifecycle features omitted in 2.2.2: {', '.join(three_x_features)}"
            )

        if odcs_lifecycle:
            odcs_doc["lifecycle"] = odcs_lifecycle

    def _map_marketplace_section_v2_2_2(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract marketplace section to ODCS 2.2.2 format.

        ODCS 2.2.2 has very limited marketplace support. Gracefully degrades all 3.x features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        marketplace = hub_contract.get("marketplace")
        if not marketplace or not isinstance(marketplace, dict):
            return

        odcs_marketplace = {}

        # ODCS 2.2.2 has very limited marketplace support
        # Most marketplace features are 3.x+

        # Check for 3.x marketplace features and warn
        three_x_features = []
        if "license_summary" in marketplace:
            three_x_features.append("license_summary")
        if "intended_use" in marketplace:
            three_x_features.append("intended_use")
        if "restricted_use" in marketplace:
            three_x_features.append("restricted_use")
        if "enhanced_features" in marketplace:
            three_x_features.append("enhanced_features")
        if "advanced_pricing" in marketplace:
            three_x_features.append("advanced_pricing")
        if "access_methods" in marketplace:
            three_x_features.append("access_methods")

        if three_x_features:
            self.logger.warning(
                "odcs_v2_2_2_marketplace_features_omitted",
                features=three_x_features,
                message=f"ODCS 3.x marketplace features omitted in 2.2.2: {', '.join(three_x_features)}"
            )

        # Only add marketplace section if it has content (unlikely for 2.2.2)
        if odcs_marketplace:
            odcs_doc["marketplace"] = odcs_marketplace

    def _map_privacy_compliance_section_v2_2_2(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract privacy_compliance section to ODCS 2.2.2 format.

        ODCS 2.2.2 has limited privacy compliance support.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        privacy_compliance = hub_contract.get("privacy_compliance")
        if not privacy_compliance or not isinstance(privacy_compliance, dict):
            return

        odcs_privacy = {}

        # ODCS 2.2.2 has basic privacy compliance support
        # Map basic fields that might be supported
        if "contains_personal_data" in privacy_compliance:
            odcs_privacy["contains_personal_data"] = privacy_compliance["contains_personal_data"]

        # Check for 3.x privacy features and warn
        three_x_features = []
        if "personal_data_categories" in privacy_compliance:
            three_x_features.append("personal_data_categories")
        if "jurisdictions" in privacy_compliance:
            three_x_features.append("jurisdictions")
        if "legal_bases" in privacy_compliance:
            three_x_features.append("legal_bases")
        if "retention_policy" in privacy_compliance:
            three_x_features.append("retention_policy")

        if three_x_features:
            self.logger.warning(
                "odcs_v2_2_2_privacy_features_omitted",
                features=three_x_features,
                message=f"ODCS 3.x privacy compliance features omitted in 2.2.2: {', '.join(three_x_features)}"
            )

        if odcs_privacy:
            odcs_doc["privacy_compliance"] = odcs_privacy

    def _map_info_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract info section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return

        # Map owners
        owners = info.get("owners", [])
        if owners:
            odcs_owners = []
            for owner in owners:
                if isinstance(owner, dict):
                    odcs_owner = {}
                    if "name" in owner:
                        odcs_owner["name"] = owner["name"]
                    if "email" in owner:
                        odcs_owner["email"] = owner["email"]
                    if odcs_owner:
                        odcs_owners.append(odcs_owner)
            if odcs_owners:
                if "info" not in odcs_doc:
                    odcs_doc["info"] = {}
                odcs_doc["info"]["owners"] = odcs_owners

        # Map tags
        tags = info.get("tags", [])
        if tags:
            if "info" not in odcs_doc:
                odcs_doc["info"] = {}
            odcs_doc["info"]["tags"] = tags


class ODCSGeneratorV3_0_1(ODCSGeneratorBase):
    """
    ODCS 3.0.1 Generator implementation.

    Generates ODCS 3.0.1 documents from HubContract format.
    Handles version-specific differences from 3.0.2:
    - Gracefully degrades 3.0.2-only features (warns and omits)
    - Supports all ODCS 3.0.1 features
    - Maps HubContract fields to ODCS 3.0.1 structure

    Key Mappings:
    - hub_contract.id → odcs.id
    - hub_contract.info.name → odcs.name
    - hub_contract.info.description → odcs.description
    - hub_contract.info.version → odcs.version
    - hub_contract.schema → odcs.schema
    - hub_contract.quality → odcs.quality
    - hub_contract.lifecycle → odcs.lifecycle (with graceful degradation for 3.0.2+ features)
    - hub_contract.marketplace → odcs.marketplace (with graceful degradation for 3.0.2+ features)
    - hub_contract.privacy_compliance → odcs.privacy_compliance

    Key differences from 3.0.2:
    - Enhanced marketplace features (3.0.2+) are not supported
    - Enhanced lifecycle features (3.0.2+) are not supported
    - Other 3.0.2-specific features are gracefully degraded
    """

    def __init__(self):
        """Initialize the ODCS 3.0.1 generator."""
        super().__init__()
        self.target_version = "3.0.1"

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS 3.0.1 document from HubContract format.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (ignored, always uses 3.0.1)

        Returns:
            ODCS 3.0.1 document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with field-level context
        """
        try:
            # Validate HubContract structure first
            self.validate_hub_contract_structure(hub_contract)

            contract_id = hub_contract["id"]
            info = hub_contract["info"]
            name = info["name"]

            self.log_generation_start(contract_id, name, self.target_version)

            # Initialize ODCS 3.0.1 document structure
            odcs_doc = {
                "apiVersion": f"odcs.io/v{self.target_version}",
                "kind": "DataContract",
                "id": contract_id,
                "name": name,
            }

            # Map basic info fields
            if "description" in info and info["description"]:
                self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
                odcs_doc["description"] = info["description"]

            if "version" in info and info["version"]:
                self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
                odcs_doc["version"] = info["version"]

            # Map info section (owners, tags, etc.)
            self._map_info_section(hub_contract, odcs_doc)

            # Map schema section (ODCS 3.0.1 format, no models[] support)
            self._map_schema_section_v3_0_1(hub_contract, odcs_doc)

            # Map quality section
            self._map_quality_section(hub_contract, odcs_doc)

            # Map lifecycle section (with graceful degradation for 3.0.2+ features)
            self._map_lifecycle_section_v3_0_1(hub_contract, odcs_doc)

            # Map marketplace section (with graceful degradation for 3.0.2+ features)
            self._map_marketplace_section_v3_0_1(hub_contract, odcs_doc)

            # Map privacy_compliance section
            self._map_privacy_compliance_section(hub_contract, odcs_doc)

            self.log_generation_complete(contract_id, name, self.target_version)
            return odcs_doc

        except ODCSGenerationError:
            # Re-raise ODCS errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.log_generation_error(e, hub_contract.get("id"))
            raise ODCSGenerationError(
                message=f"Unexpected error generating ODCS 3.0.1 document: {str(e)}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                cause=e,
            ) from e

    def _map_schema_section_v3_0_1(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract schema section to ODCS 3.0.1 format.

        ODCS 3.0.1 does not support models[] array, only direct schema.fields[].

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        schema = hub_contract.get("schema")
        if not schema or not isinstance(schema, dict):
            return

        odcs_schema = {}

        # Map fields (ODCS 3.0.1 uses direct fields array, not models[])
        fields = schema.get("fields", [])
        if fields:
            odcs_fields = []
            for field in fields:
                if not isinstance(field, dict):
                    continue
                odcs_field = {
                    "name": field.get("name"),
                    "type": field.get("data_type") or field.get("type", "string"),
                }
                # Add optional field properties
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
                if "min_length" in field or "minLength" in field:
                    odcs_field["minLength"] = field.get("min_length") or field.get("minLength")
                if "max_length" in field or "maxLength" in field:
                    odcs_field["maxLength"] = field.get("max_length") or field.get("maxLength")
                if "minimum" in field:
                    odcs_field["minimum"] = field["minimum"]
                if "maximum" in field:
                    odcs_field["maximum"] = field["maximum"]
                odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        primary_key = schema.get("primary_key")
        if primary_key:
            if isinstance(primary_key, list):
                odcs_schema["primary_key"] = primary_key if len(primary_key) > 1 else primary_key[0] if primary_key else None
            elif isinstance(primary_key, str):
                odcs_schema["primary_key"] = primary_key

        # Map unique_constraints
        unique_constraints = schema.get("unique_constraints")
        if unique_constraints:
            odcs_schema["unique_constraints"] = unique_constraints

        # Map indexes
        indexes = schema.get("indexes")
        if indexes:
            odcs_schema["indexes"] = indexes

        if odcs_schema:
            odcs_doc["schema"] = odcs_schema

    def _map_lifecycle_section_v3_0_1(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract lifecycle section to ODCS 3.0.1 format.

        Gracefully degrades 3.0.2+ enhanced lifecycle features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        lifecycle = hub_contract.get("lifecycle")
        if not lifecycle or not isinstance(lifecycle, dict):
            return

        odcs_lifecycle = {}

        # Map data_source (supported in 3.0.1)
        if "data_source" in lifecycle:
            odcs_lifecycle["data_source"] = lifecycle["data_source"]

        # Map refresh_cadence (supported in 3.0.1)
        if "refresh_cadence" in lifecycle:
            odcs_lifecycle["refresh_cadence"] = lifecycle["refresh_cadence"]

        # Map slas (supported in 3.0.1)
        slas = lifecycle.get("slas")
        if slas and isinstance(slas, dict):
            odcs_slas = {}
            if "availability" in slas:
                odcs_slas["availability"] = slas["availability"]
            if "latency_ms_p95" in slas:
                odcs_slas["latency_ms_p95"] = slas["latency_ms_p95"]
            if odcs_slas:
                odcs_lifecycle["slas"] = odcs_slas

        # Check for 3.0.2+ enhanced lifecycle features and warn
        enhanced_features = []
        if "enhanced_features" in lifecycle:
            enhanced_features.append("enhanced_features")
        if "advanced_slas" in lifecycle:
            enhanced_features.append("advanced_slas")

        if enhanced_features:
            self.logger.warning(
                "odcs_v3_0_1_enhanced_lifecycle_features_omitted",
                features=enhanced_features,
                message=f"ODCS 3.0.2+ enhanced lifecycle features omitted: {', '.join(enhanced_features)}"
            )

        if odcs_lifecycle:
            odcs_doc["lifecycle"] = odcs_lifecycle

    def _map_marketplace_section_v3_0_1(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract marketplace section to ODCS 3.0.1 format.

        Gracefully degrades 3.0.2+ enhanced marketplace features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        marketplace = hub_contract.get("marketplace")
        if not marketplace or not isinstance(marketplace, dict):
            return

        odcs_marketplace = {}

        # Map license_summary (supported in 3.0.1)
        if "license_summary" in marketplace:
            odcs_marketplace["license_summary"] = marketplace["license_summary"]

        # Map intended_use (supported in 3.0.1)
        if "intended_use" in marketplace:
            odcs_marketplace["intended_use"] = marketplace["intended_use"]

        # Map restricted_use (supported in 3.0.1)
        if "restricted_use" in marketplace:
            odcs_marketplace["restricted_use"] = marketplace["restricted_use"]

        # Check for 3.0.2+ enhanced marketplace features and warn
        enhanced_features = []
        if "enhanced_features" in marketplace:
            enhanced_features.append("enhanced_features")
        if "advanced_pricing" in marketplace:
            enhanced_features.append("advanced_pricing")
        if "access_methods" in marketplace:
            # Check if it's 3.0.2+ format
            access_methods = marketplace.get("access_methods")
            if isinstance(access_methods, list) and access_methods:
                first_method = access_methods[0] if access_methods else {}
                if isinstance(first_method, dict) and "enhanced" in first_method:
                    enhanced_features.append("access_methods (enhanced)")

        if enhanced_features:
            self.logger.warning(
                "odcs_v3_0_1_enhanced_marketplace_features_omitted",
                features=enhanced_features,
                message=f"ODCS 3.0.2+ enhanced marketplace features omitted: {', '.join(enhanced_features)}"
            )

        if odcs_marketplace:
            odcs_doc["marketplace"] = odcs_marketplace

    def _map_info_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract info section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return

        # Map owners
        owners = info.get("owners", [])
        if owners:
            odcs_owners = []
            for owner in owners:
                if isinstance(owner, dict):
                    odcs_owner = {}
                    if "name" in owner:
                        odcs_owner["name"] = owner["name"]
                    if "email" in owner:
                        odcs_owner["email"] = owner["email"]
                    if odcs_owner:
                        odcs_owners.append(odcs_owner)
            if odcs_owners:
                if "info" not in odcs_doc:
                    odcs_doc["info"] = {}
                odcs_doc["info"]["owners"] = odcs_owners

        # Map tags
        tags = info.get("tags", [])
        if tags:
            if "info" not in odcs_doc:
                odcs_doc["info"] = {}
            odcs_doc["info"]["tags"] = tags

    def _map_quality_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract quality section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        quality = hub_contract.get("quality")
        if not quality or not isinstance(quality, dict):
            return

        odcs_quality = {}

        # Map default_profile_key
        if "default_profile_key" in quality:
            odcs_quality["default_profile_key"] = quality["default_profile_key"]

        # Map rules
        rules = quality.get("rules", [])
        if rules:
            odcs_rules = []
            for rule in rules:
                if isinstance(rule, dict):
                    odcs_rule = {}
                    if "name" in rule:
                        odcs_rule["name"] = rule["name"]
                    if "type" in rule:
                        odcs_rule["type"] = rule["type"]
                    if "description" in rule:
                        odcs_rule["description"] = rule["description"]
                    if "expression" in rule:
                        odcs_rule["expression"] = rule["expression"]
                    if "severity" in rule:
                        odcs_rule["severity"] = rule["severity"]
                    if odcs_rule:
                        odcs_rules.append(odcs_rule)
            if odcs_rules:
                odcs_quality["rules"] = odcs_rules

        if odcs_quality:
            odcs_doc["quality"] = odcs_quality

    def _map_privacy_compliance_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract privacy_compliance section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        privacy_compliance = hub_contract.get("privacy_compliance")
        if not privacy_compliance or not isinstance(privacy_compliance, dict):
            return

        odcs_privacy = {}

        # Map contains_personal_data
        if "contains_personal_data" in privacy_compliance:
            odcs_privacy["contains_personal_data"] = privacy_compliance["contains_personal_data"]

        # Map personal_data_categories
        if "personal_data_categories" in privacy_compliance:
            odcs_privacy["personal_data_categories"] = privacy_compliance["personal_data_categories"]

        # Map jurisdictions
        if "jurisdictions" in privacy_compliance:
            odcs_privacy["jurisdictions"] = privacy_compliance["jurisdictions"]

        # Map legal_bases
        if "legal_bases" in privacy_compliance:
            odcs_privacy["legal_bases"] = privacy_compliance["legal_bases"]

        # Map retention_policy
        retention_policy = privacy_compliance.get("retention_policy")
        if retention_policy and isinstance(retention_policy, dict):
            odcs_retention = {}
            if "period" in retention_policy:
                odcs_retention["period"] = retention_policy["period"]
            if "notes" in retention_policy:
                odcs_retention["notes"] = retention_policy["notes"]
            if odcs_retention:
                odcs_privacy["retention_policy"] = odcs_retention

        if odcs_privacy:
            odcs_doc["privacy_compliance"] = odcs_privacy


class ODCSGeneratorV3_0_2(ODCSGeneratorBase):
    """
    ODCS 3.0.2 Generator implementation.

    Generates ODCS 3.0.2 documents from HubContract format.
    Implements comprehensive mapping of all HubContract sections to ODCS 3.0.2 structure.

    Key Mappings:
    - hub_contract.id → odcs.id
    - hub_contract.info.name → odcs.name
    - hub_contract.info.description → odcs.description
    - hub_contract.info.version → odcs.version
    - hub_contract.schema → odcs.schema (with models[] support)
    - hub_contract.quality → odcs.quality
    - hub_contract.lifecycle → odcs.lifecycle
    - hub_contract.servicelevels → odcs.slaProperties
    - hub_contract.lineage → odcs.transformSourceObjects, transformLogic
    - hub_contract.info.owners[] → odcs.info.owners[]
    - hub_contract.info.tags[] → odcs.info.tags[]
    """

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS 3.0.2 document from HubContract format.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (default: "3.0.2" for this generator)

        Returns:
            ODCS 3.0.2 document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with field-level context
        """
        # Use 3.0.2 as default version
        if target_version is None:
            target_version = "3.0.2"

        try:
            # Validate HubContract structure first
            self.validate_hub_contract_structure(hub_contract)

            contract_id = hub_contract["id"]
            info = hub_contract["info"]
            name = info["name"]

            self.log_generation_start(contract_id, name, target_version)

            # Initialize ODCS document structure
            odcs_doc = {
                "apiVersion": f"odcs.io/v{target_version}",
                "kind": "DataContract",
                "id": contract_id,
                "name": name,
            }

            # Map basic info fields
            if "description" in info and info["description"]:
                self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
                odcs_doc["description"] = info["description"]

            if "version" in info and info["version"]:
                self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
                odcs_doc["version"] = info["version"]

            # Map info section (owners, tags, etc.)
            self._map_info_section(hub_contract, odcs_doc)

            # Map schema section (including models[])
            self._map_schema_section(hub_contract, odcs_doc)

            # Map quality section
            self._map_quality_section(hub_contract, odcs_doc)

            # Map lifecycle section
            self._map_lifecycle_section(hub_contract, odcs_doc)

            # Map servicelevels section
            self._map_servicelevels_section(hub_contract, odcs_doc)

            # Map lineage section
            self._map_lineage_section(hub_contract, odcs_doc)

            # Map marketplace section (if present)
            self._map_marketplace_section(hub_contract, odcs_doc)

            # Map privacy_compliance section (if present)
            self._map_privacy_compliance_section(hub_contract, odcs_doc)

            self.log_generation_complete(contract_id, name, target_version)
            return odcs_doc

        except ODCSGenerationError:
            # Re-raise ODCS errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.log_generation_error(e, contract_id=hub_contract.get("id"))
            raise ODCSGenerationError(
                message=f"Unexpected error generating ODCS 3.0.2 document: {str(e)}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                cause=e,
            ) from e

    def _map_info_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract info section to ODCS info section."""
        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return

        # Initialize info section if not present
        if "info" not in odcs_doc:
            odcs_doc["info"] = {}

        # Map owners
        if "owners" in info and info["owners"]:
            owners = info["owners"]
            self.validate_field_type(owners, list, "/info/owners", allow_none=False)
            odcs_owners = []
            for i, owner in enumerate(owners):
                if isinstance(owner, dict):
                    odcs_owner = {}
                    if "name" in owner:
                        self.validate_field_type(owner["name"], str, f"/info/owners/{i}/name", allow_none=False)
                        odcs_owner["name"] = owner["name"]
                    if "email" in owner:
                        self.validate_field_type(owner["email"], str, f"/info/owners/{i}/email", allow_none=True)
                        odcs_owner["email"] = owner["email"]
                    if odcs_owner:  # Only add if has at least name or email
                        odcs_owners.append(odcs_owner)
                elif isinstance(owner, str):
                    # Convert string owner to dict format
                    odcs_owners.append({"name": owner})
            if odcs_owners:
                odcs_doc["info"]["owners"] = odcs_owners

        # Map tags
        if "tags" in info and info["tags"]:
            tags = info["tags"]
            self.validate_field_type(tags, list, "/info/tags", allow_none=False)
            # Validate all tags are strings
            odcs_tags = []
            for i, tag in enumerate(tags):
                self.validate_field_type(tag, str, f"/info/tags/{i}", allow_none=False)
                odcs_tags.append(tag)
            if odcs_tags:
                odcs_doc["info"]["tags"] = odcs_tags

        # Map other info fields (domain, tenant, dataProduct, etc.)
        for field in ["domain", "tenant", "dataProduct", "status"]:
            if field in info and info[field] is not None:
                self.validate_field_type(info[field], str, f"/info/{field}", allow_none=True)
                odcs_doc["info"][field] = info[field]

        # Only add info section if it has content
        if not odcs_doc["info"]:
            del odcs_doc["info"]

    def _map_schema_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract schema/models section to ODCS schema section."""
        # Check for models[] first (canonical structure)
        models = hub_contract.get("models")
        schema = hub_contract.get("schema", {})

        if models and isinstance(models, list) and len(models) > 0:
            # Multiple models - map to schema[] array
            odcs_schema = []
            for i, model in enumerate(models):
                if not isinstance(model, dict):
                    continue
                schema_entry = self._map_model_to_odcs_schema(model, f"/models/{i}")
                if schema_entry:
                    odcs_schema.append(schema_entry)
            if odcs_schema:
                odcs_doc["schema"] = odcs_schema if len(odcs_schema) > 1 else odcs_schema[0]
        elif schema and isinstance(schema, dict):
            # Single schema object - map to ODCS schema object
            odcs_schema = self._map_schema_to_odcs_schema(schema, "/schema")
            if odcs_schema:
                odcs_doc["schema"] = odcs_schema

    def _map_model_to_odcs_schema(
        self,
        model: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract model entry to ODCS schema entry."""
        if not isinstance(model, dict):
            return None

        odcs_schema = {}

        # Map name
        if "name" in model:
            self.validate_field_type(model["name"], str, f"{field_path}/name", allow_none=False)
            odcs_schema["name"] = model["name"]

        # Map description
        if "description" in model and model["description"]:
            self.validate_field_type(model["description"], str, f"{field_path}/description", allow_none=True)
            odcs_schema["description"] = model["description"]

        # Map logical_type and physical_type
        if "logical_type" in model:
            self.validate_field_type(model["logical_type"], str, f"{field_path}/logical_type", allow_none=True)
            odcs_schema["logicalType"] = model["logical_type"]
        if "physical_type" in model:
            self.validate_field_type(model["physical_type"], str, f"{field_path}/physical_type", allow_none=True)
            odcs_schema["physicalType"] = model["physical_type"]
        if "physical_name" in model:
            self.validate_field_type(model["physical_name"], str, f"{field_path}/physical_name", allow_none=True)
            odcs_schema["physicalName"] = model["physical_name"]

        # Map fields
        if "fields" in model and model["fields"]:
            fields = model["fields"]
            self.validate_field_type(fields, list, f"{field_path}/fields", allow_none=False)
            odcs_fields = []
            for i, field in enumerate(fields):
                if isinstance(field, dict):
                    odcs_field = self._map_field_to_odcs_field(field, f"{field_path}/fields/{i}")
                    if odcs_field:
                        odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        if "primary_key" in model and model["primary_key"]:
            primary_key = model["primary_key"]
            if isinstance(primary_key, list):
                odcs_schema["primaryKey"] = primary_key if len(primary_key) > 1 else primary_key[0]
            elif isinstance(primary_key, str):
                odcs_schema["primaryKey"] = primary_key

        # Map unique_constraints
        if "unique_constraints" in model and model["unique_constraints"]:
            unique_constraints = model["unique_constraints"]
            self.validate_field_type(unique_constraints, list, f"{field_path}/unique_constraints", allow_none=False)
            odcs_schema["uniqueConstraints"] = unique_constraints

        # Map indexes
        if "indexes" in model and model["indexes"]:
            indexes = model["indexes"]
            self.validate_field_type(indexes, list, f"{field_path}/indexes", allow_none=False)
            odcs_schema["indexes"] = indexes

        return odcs_schema if odcs_schema else None

    def _map_schema_to_odcs_schema(
        self,
        schema: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract schema object to ODCS schema object."""
        if not isinstance(schema, dict):
            return None

        odcs_schema = {}

        # Map fields
        if "fields" in schema and schema["fields"]:
            fields = schema["fields"]
            self.validate_field_type(fields, list, f"{field_path}/fields", allow_none=False)
            odcs_fields = []
            for i, field in enumerate(fields):
                if isinstance(field, dict):
                    odcs_field = self._map_field_to_odcs_field(field, f"{field_path}/fields/{i}")
                    if odcs_field:
                        odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        if "primary_key" in schema and schema["primary_key"]:
            primary_key = schema["primary_key"]
            if isinstance(primary_key, list):
                odcs_schema["primaryKey"] = primary_key if len(primary_key) > 1 else primary_key[0]
            elif isinstance(primary_key, str):
                odcs_schema["primaryKey"] = primary_key

        # Map unique_constraints
        if "unique_constraints" in schema and schema["unique_constraints"]:
            unique_constraints = schema["unique_constraints"]
            self.validate_field_type(unique_constraints, list, f"{field_path}/unique_constraints", allow_none=False)
            odcs_schema["uniqueConstraints"] = unique_constraints

        # Map indexes
        if "indexes" in schema and schema["indexes"]:
            indexes = schema["indexes"]
            self.validate_field_type(indexes, list, f"{field_path}/indexes", allow_none=False)
            odcs_schema["indexes"] = indexes

        return odcs_schema if odcs_schema else None

    def _map_field_to_odcs_field(
        self,
        field: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract field to ODCS field."""
        if not isinstance(field, dict):
            return None

        odcs_field = {}

        # Required: name
        if "name" not in field:
            raise ODCSGenerationError(
                message=f"Field missing required 'name' at {field_path}",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": f"{field_path}/name",
                    "expected": "str",
                    "actual": None,
                },
            )
        name = field["name"]
        self.validate_field_type(name, str, f"{field_path}/name", allow_none=False)
        odcs_field["name"] = name

        # Required: type (map data_type to type)
        field_type = field.get("data_type") or field.get("type", "string")
        self.validate_field_type(field_type, str, f"{field_path}/type", allow_none=False)
        odcs_field["type"] = field_type

        # Optional: nullable
        if "nullable" in field:
            self.validate_field_type(field["nullable"], bool, f"{field_path}/nullable", allow_none=True)
            odcs_field["nullable"] = field["nullable"]

        # Optional: description
        if "description" in field and field["description"]:
            self.validate_field_type(field["description"], str, f"{field_path}/description", allow_none=True)
            odcs_field["description"] = field["description"]

        # Optional: format, pattern, enum, default
        for prop in ["format", "pattern", "enum", "default"]:
            if prop in field and field[prop] is not None:
                odcs_field[prop] = field[prop]

        # Optional: minLength, maxLength (map from min_length, max_length)
        if "min_length" in field:
            odcs_field["minLength"] = field["min_length"]
        if "max_length" in field:
            odcs_field["maxLength"] = field["max_length"]

        # Optional: minimum, maximum
        for prop in ["minimum", "maximum"]:
            if prop in field and field[prop] is not None:
                odcs_field[prop] = field[prop]

        return odcs_field

    def _map_quality_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract quality section to ODCS quality section."""
        quality = hub_contract.get("quality")
        if not quality or not isinstance(quality, dict):
            return

        odcs_quality = {}

        # Map default_profile_key
        if "default_profile_key" in quality and quality["default_profile_key"]:
            self.validate_field_type(quality["default_profile_key"], str, "/quality/default_profile_key", allow_none=True)
            odcs_quality["default_profile_key"] = quality["default_profile_key"]

        # Map rules
        if "rules" in quality and quality["rules"]:
            rules = quality["rules"]
            self.validate_field_type(rules, list, "/quality/rules", allow_none=False)
            odcs_rules = []
            for i, rule in enumerate(rules):
                if isinstance(rule, dict):
                    odcs_rule = self._map_quality_rule_to_odcs(rule, f"/quality/rules/{i}")
                    if odcs_rule:
                        odcs_rules.append(odcs_rule)
            if odcs_rules:
                odcs_quality["rules"] = odcs_rules

        if odcs_quality:
            odcs_doc["quality"] = odcs_quality

    def _map_quality_rule_to_odcs(
        self,
        rule: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract quality rule to ODCS quality rule."""
        if not isinstance(rule, dict):
            return None

        odcs_rule = {}

        # Map common rule fields
        for field in ["id", "rule_id", "name", "dimension", "type", "rule", "expression", "severity", "threshold", "target", "unit", "description"]:
            if field in rule and rule[field] is not None:
                odcs_rule[field] = rule[field]

        return odcs_rule if odcs_rule else None

    def _map_lifecycle_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract lifecycle section to ODCS lifecycle section."""
        lifecycle = hub_contract.get("lifecycle")
        if not lifecycle or not isinstance(lifecycle, dict):
            return

        odcs_lifecycle = {}

        # Map data_source
        if "data_source" in lifecycle and lifecycle["data_source"]:
            if isinstance(lifecycle["data_source"], str):
                odcs_lifecycle["data_source"] = lifecycle["data_source"]
            elif isinstance(lifecycle["data_source"], dict):
                odcs_lifecycle["data_source"] = lifecycle["data_source"]

        # Map refresh_cadence
        if "refresh_cadence" in lifecycle and lifecycle["refresh_cadence"]:
            odcs_lifecycle["refresh_cadence"] = lifecycle["refresh_cadence"]

        # Map slas
        if "slas" in lifecycle and lifecycle["slas"]:
            slas = lifecycle["slas"]
            if isinstance(slas, dict):
                odcs_lifecycle["slas"] = slas

        if odcs_lifecycle:
            odcs_doc["lifecycle"] = odcs_lifecycle

    def _map_servicelevels_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract servicelevels section to ODCS slaProperties."""
        servicelevels = hub_contract.get("servicelevels")
        if not servicelevels or not isinstance(servicelevels, list):
            return

        odcs_sla_properties = []
        for i, servicelevel in enumerate(servicelevels):
            if not isinstance(servicelevel, dict):
                continue

            sla_property = {}

            # Map property name
            if "name" in servicelevel:
                self.validate_field_type(servicelevel["name"], str, f"/servicelevels/{i}/name", allow_none=False)
                sla_property["property"] = servicelevel["name"]
            elif "property" in servicelevel:
                self.validate_field_type(servicelevel["property"], str, f"/servicelevels/{i}/property", allow_none=False)
                sla_property["property"] = servicelevel["property"]

            # Map target
            if "target" in servicelevel:
                sla_property["target"] = servicelevel["target"]

            # Map unit
            if "unit" in servicelevel:
                self.validate_field_type(servicelevel["unit"], str, f"/servicelevels/{i}/unit", allow_none=True)
                sla_property["unit"] = servicelevel["unit"]

            # Map description
            if "description" in servicelevel:
                self.validate_field_type(servicelevel["description"], str, f"/servicelevels/{i}/description", allow_none=True)
                sla_property["description"] = servicelevel["description"]

            if sla_property:
                odcs_sla_properties.append(sla_property)

        if odcs_sla_properties:
            odcs_doc["slaProperties"] = odcs_sla_properties

    def _map_lineage_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract lineage section to ODCS transformSourceObjects and transformLogic."""
        lineage = hub_contract.get("lineage")
        if not lineage:
            return

        if isinstance(lineage, dict):
            # Map entries to transformSourceObjects
            entries = lineage.get("entries", [])
            if entries and isinstance(entries, list):
                transform_source_objects = []
                for i, entry in enumerate(entries):
                    if isinstance(entry, dict):
                        source_obj = {}
                        # Map contract reference
                        if "contract_id" in entry:
                            source_obj["name"] = entry["contract_id"]
                        if "contract_version" in entry:
                            source_obj["version"] = entry["contract_version"]
                        if "namespace" in entry:
                            source_obj["namespace"] = entry["namespace"]
                        if "model" in entry:
                            source_obj["model"] = entry["model"]
                        if "field" in entry:
                            source_obj["field"] = entry["field"]
                        if source_obj:
                            transform_source_objects.append(source_obj)
                if transform_source_objects:
                    odcs_doc["transformSourceObjects"] = transform_source_objects

            # Map transformLogic if present
            if "transform_logic" in lineage:
                odcs_doc["transformLogic"] = lineage["transform_logic"]
            elif "description" in lineage:
                odcs_doc["transformLogic"] = lineage["description"]

    def _map_marketplace_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract marketplace section to ODCS marketplace section."""
        marketplace = hub_contract.get("marketplace")
        if not marketplace or not isinstance(marketplace, dict):
            return

        odcs_marketplace = {}

        # Map license_summary
        if "license_summary" in marketplace and marketplace["license_summary"]:
            self.validate_field_type(marketplace["license_summary"], str, "/marketplace/license_summary", allow_none=True)
            odcs_marketplace["license_summary"] = marketplace["license_summary"]

        # Map intended_use
        if "intended_use" in marketplace and marketplace["intended_use"]:
            intended_use = marketplace["intended_use"]
            if isinstance(intended_use, list):
                odcs_marketplace["intended_use"] = intended_use
            elif isinstance(intended_use, str):
                odcs_marketplace["intended_use"] = [intended_use]

        # Map restricted_use
        if "restricted_use" in marketplace and marketplace["restricted_use"]:
            restricted_use = marketplace["restricted_use"]
            if isinstance(restricted_use, list):
                odcs_marketplace["restricted_use"] = restricted_use
            elif isinstance(restricted_use, str):
                odcs_marketplace["restricted_use"] = [restricted_use]

        if odcs_marketplace:
            odcs_doc["marketplace"] = odcs_marketplace

    def _map_privacy_compliance_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract privacy_compliance section to ODCS privacy_compliance section."""
        privacy_compliance = hub_contract.get("privacy_compliance")
        if not privacy_compliance or not isinstance(privacy_compliance, dict):
            return

        odcs_privacy_compliance = {}

        # Map all privacy_compliance fields
        for field in ["contains_personal_data", "personal_data_categories", "jurisdictions", "legal_bases", "retention_policy"]:
            if field in privacy_compliance and privacy_compliance[field] is not None:
                odcs_privacy_compliance[field] = privacy_compliance[field]

        if odcs_privacy_compliance:
            odcs_doc["privacy_compliance"] = odcs_privacy_compliance


class ODCSGeneratorV3_0_0(ODCSGeneratorBase):
    """
    ODCS 3.0.0 Generator implementation.

    Generates ODCS 3.0.0 documents from HubContract format.
    Implements comprehensive mapping of all HubContract sections to ODCS 3.0.0 structure.

    Key Mappings:
    - hub_contract.id → odcs.id
    - hub_contract.info.name → odcs.name
    - hub_contract.info.description → odcs.description
    - hub_contract.info.version → odcs.version
    - hub_contract.schema → odcs.schema (with models[] support)
    - hub_contract.quality → odcs.quality
    - hub_contract.lifecycle → odcs.lifecycle
    - hub_contract.servicelevels → odcs.slaProperties
    - hub_contract.lineage → odcs.transformSourceObjects, transformLogic
    - hub_contract.info.owners[] → odcs.info.owners[]
    - hub_contract.info.tags[] → odcs.info.tags[]

    Graceful Degradation:
    - Features introduced in ODCS 3.0.1+ and 3.0.2+ are omitted or logged as warnings
    - The generator focuses on core ODCS 3.0.0 features
    """

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS 3.0.0 document from HubContract format.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (default: "3.0.0" for this generator)

        Returns:
            ODCS 3.0.0 document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with field-level context
        """
        # Use 3.0.0 as default version
        if target_version is None:
            target_version = "3.0.0"

        try:
            # Validate HubContract structure first
            self.validate_hub_contract_structure(hub_contract)

            contract_id = hub_contract["id"]
            info = hub_contract["info"]
            name = info["name"]

            self.log_generation_start(contract_id, name, target_version)

            # Initialize ODCS document structure
            odcs_doc = {
                "apiVersion": f"odcs.io/v{target_version}",
                "kind": "DataContract",
                "id": contract_id,
                "name": name,
            }

            # Map basic info fields
            if "description" in info and info["description"]:
                self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
                odcs_doc["description"] = info["description"]

            if "version" in info and info["version"]:
                self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
                odcs_doc["version"] = info["version"]

            # Map info section (owners, tags, etc.)
            self._map_info_section(hub_contract, odcs_doc)

            # Map schema section (including models[])
            self._map_schema_section(hub_contract, odcs_doc)

            # Map quality section
            self._map_quality_section(hub_contract, odcs_doc)

            # Map lifecycle section
            self._map_lifecycle_section(hub_contract, odcs_doc)

            # Map servicelevels section
            self._map_servicelevels_section(hub_contract, odcs_doc)

            # Map lineage section
            self._map_lineage_section(hub_contract, odcs_doc)

            # Map marketplace section (if present)
            self._map_marketplace_section(hub_contract, odcs_doc)

            # Map privacy_compliance section (if present)
            self._map_privacy_compliance_section(hub_contract, odcs_doc)

            self.log_generation_complete(contract_id, name, target_version)
            return odcs_doc

        except ODCSGenerationError:
            # Re-raise ODCS errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.log_generation_error(e, contract_id=hub_contract.get("id"))
            raise ODCSGenerationError(
                message=f"Unexpected error generating ODCS 3.0.0 document: {str(e)}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                cause=e,
            ) from e

    def _map_info_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract info section to ODCS info section."""
        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return

        # Initialize info section if not present
        if "info" not in odcs_doc:
            odcs_doc["info"] = {}

        # Map owners
        if "owners" in info and info["owners"]:
            owners = info["owners"]
            self.validate_field_type(owners, list, "/info/owners", allow_none=False)
            odcs_owners = []
            for i, owner in enumerate(owners):
                if isinstance(owner, dict):
                    odcs_owner = {}
                    if "name" in owner:
                        self.validate_field_type(owner["name"], str, f"/info/owners/{i}/name", allow_none=False)
                        odcs_owner["name"] = owner["name"]
                    if "email" in owner:
                        self.validate_field_type(owner["email"], str, f"/info/owners/{i}/email", allow_none=True)
                        odcs_owner["email"] = owner["email"]
                    if odcs_owner:  # Only add if has at least name or email
                        odcs_owners.append(odcs_owner)
                elif isinstance(owner, str):
                    # Convert string owner to dict format
                    odcs_owners.append({"name": owner})
            if odcs_owners:
                odcs_doc["info"]["owners"] = odcs_owners

        # Map tags
        if "tags" in info and info["tags"]:
            tags = info["tags"]
            self.validate_field_type(tags, list, "/info/tags", allow_none=False)
            # Validate all tags are strings
            odcs_tags = []
            for i, tag in enumerate(tags):
                self.validate_field_type(tag, str, f"/info/tags/{i}", allow_none=False)
                odcs_tags.append(tag)
            if odcs_tags:
                odcs_doc["info"]["tags"] = odcs_tags

        # Map other info fields (domain, tenant, dataProduct, etc.)
        # Note: These may not be in ODCS 3.0.0 spec, but we include them for compatibility
        for field in ["domain", "tenant", "dataProduct", "status"]:
            if field in info and info[field] is not None:
                self.validate_field_type(info[field], str, f"/info/{field}", allow_none=True)
                odcs_doc["info"][field] = info[field]

        # Only add info section if it has content
        if not odcs_doc["info"]:
            del odcs_doc["info"]

    def _map_schema_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract schema/models section to ODCS schema section."""
        # Check for models[] first (canonical structure)
        models = hub_contract.get("models")
        schema = hub_contract.get("schema", {})

        if models and isinstance(models, list) and len(models) > 0:
            # Multiple models - map to schema[] array
            odcs_schema = []
            for i, model in enumerate(models):
                if not isinstance(model, dict):
                    continue
                schema_entry = self._map_model_to_odcs_schema(model, f"/models/{i}")
                if schema_entry:
                    odcs_schema.append(schema_entry)
            if odcs_schema:
                odcs_doc["schema"] = odcs_schema if len(odcs_schema) > 1 else odcs_schema[0]
        elif schema and isinstance(schema, dict):
            # Single schema object - map to ODCS schema object
            odcs_schema = self._map_schema_to_odcs_schema(schema, "/schema")
            if odcs_schema:
                odcs_doc["schema"] = odcs_schema

    def _map_model_to_odcs_schema(
        self,
        model: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract model entry to ODCS schema entry."""
        if not isinstance(model, dict):
            return None

        odcs_schema = {}

        # Map name
        if "name" in model:
            self.validate_field_type(model["name"], str, f"{field_path}/name", allow_none=False)
            odcs_schema["name"] = model["name"]

        # Map description
        if "description" in model and model["description"]:
            self.validate_field_type(model["description"], str, f"{field_path}/description", allow_none=True)
            odcs_schema["description"] = model["description"]

        # Map logical_type and physical_type (if supported in 3.0.0)
        if "logical_type" in model:
            self.validate_field_type(model["logical_type"], str, f"{field_path}/logical_type", allow_none=True)
            odcs_schema["logicalType"] = model["logical_type"]
        if "physical_type" in model:
            self.validate_field_type(model["physical_type"], str, f"{field_path}/physical_type", allow_none=True)
            odcs_schema["physicalType"] = model["physical_type"]
        if "physical_name" in model:
            self.validate_field_type(model["physical_name"], str, f"{field_path}/physical_name", allow_none=True)
            odcs_schema["physicalName"] = model["physical_name"]

        # Map fields
        if "fields" in model and model["fields"]:
            fields = model["fields"]
            self.validate_field_type(fields, list, f"{field_path}/fields", allow_none=False)
            odcs_fields = []
            for i, field in enumerate(fields):
                if isinstance(field, dict):
                    odcs_field = self._map_field_to_odcs_field(field, f"{field_path}/fields/{i}")
                    if odcs_field:
                        odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        if "primary_key" in model and model["primary_key"]:
            primary_key = model["primary_key"]
            if isinstance(primary_key, list):
                odcs_schema["primaryKey"] = primary_key if len(primary_key) > 1 else primary_key[0]
            elif isinstance(primary_key, str):
                odcs_schema["primaryKey"] = primary_key

        # Map unique_constraints
        if "unique_constraints" in model and model["unique_constraints"]:
            unique_constraints = model["unique_constraints"]
            self.validate_field_type(unique_constraints, list, f"{field_path}/unique_constraints", allow_none=False)
            odcs_schema["uniqueConstraints"] = unique_constraints

        # Map indexes
        if "indexes" in model and model["indexes"]:
            indexes = model["indexes"]
            self.validate_field_type(indexes, list, f"{field_path}/indexes", allow_none=False)
            odcs_schema["indexes"] = indexes

        return odcs_schema if odcs_schema else None

    def _map_schema_to_odcs_schema(
        self,
        schema: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract schema object to ODCS schema object."""
        if not isinstance(schema, dict):
            return None

        odcs_schema = {}

        # Map fields
        if "fields" in schema and schema["fields"]:
            fields = schema["fields"]
            self.validate_field_type(fields, list, f"{field_path}/fields", allow_none=False)
            odcs_fields = []
            for i, field in enumerate(fields):
                if isinstance(field, dict):
                    odcs_field = self._map_field_to_odcs_field(field, f"{field_path}/fields/{i}")
                    if odcs_field:
                        odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        if "primary_key" in schema and schema["primary_key"]:
            primary_key = schema["primary_key"]
            if isinstance(primary_key, list):
                odcs_schema["primaryKey"] = primary_key if len(primary_key) > 1 else primary_key[0]
            elif isinstance(primary_key, str):
                odcs_schema["primaryKey"] = primary_key

        # Map unique_constraints
        if "unique_constraints" in schema and schema["unique_constraints"]:
            unique_constraints = schema["unique_constraints"]
            self.validate_field_type(unique_constraints, list, f"{field_path}/unique_constraints", allow_none=False)
            odcs_schema["uniqueConstraints"] = unique_constraints

        # Map indexes
        if "indexes" in schema and schema["indexes"]:
            indexes = schema["indexes"]
            self.validate_field_type(indexes, list, f"{field_path}/indexes", allow_none=False)
            odcs_schema["indexes"] = indexes

        return odcs_schema if odcs_schema else None

    def _map_field_to_odcs_field(
        self,
        field: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract field to ODCS field."""
        if not isinstance(field, dict):
            return None

        odcs_field = {}

        # Required: name
        if "name" not in field:
            raise ODCSGenerationError(
                message=f"Field missing required 'name' at {field_path}",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": f"{field_path}/name",
                    "expected": "str",
                    "actual": None,
                },
            )
        name = field["name"]
        self.validate_field_type(name, str, f"{field_path}/name", allow_none=False)
        odcs_field["name"] = name

        # Required: type (map data_type to type)
        field_type = field.get("data_type") or field.get("type", "string")
        self.validate_field_type(field_type, str, f"{field_path}/type", allow_none=False)
        odcs_field["type"] = field_type

        # Optional: nullable
        if "nullable" in field:
            self.validate_field_type(field["nullable"], bool, f"{field_path}/nullable", allow_none=True)
            odcs_field["nullable"] = field["nullable"]

        # Optional: description
        if "description" in field and field["description"]:
            self.validate_field_type(field["description"], str, f"{field_path}/description", allow_none=True)
            odcs_field["description"] = field["description"]

        # Optional: format, pattern, enum, default
        for prop in ["format", "pattern", "enum", "default"]:
            if prop in field and field[prop] is not None:
                odcs_field[prop] = field[prop]

        # Optional: minLength, maxLength (map from min_length, max_length)
        if "min_length" in field:
            odcs_field["minLength"] = field["min_length"]
        if "max_length" in field:
            odcs_field["maxLength"] = field["max_length"]

        # Optional: minimum, maximum
        for prop in ["minimum", "maximum"]:
            if prop in field and field[prop] is not None:
                odcs_field[prop] = field[prop]

        return odcs_field

    def _map_quality_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract quality section to ODCS quality section."""
        quality = hub_contract.get("quality")
        if not quality or not isinstance(quality, dict):
            return

        odcs_quality = {}

        # Map default_profile_key
        if "default_profile_key" in quality and quality["default_profile_key"]:
            self.validate_field_type(quality["default_profile_key"], str, "/quality/default_profile_key", allow_none=True)
            odcs_quality["default_profile_key"] = quality["default_profile_key"]

        # Map rules
        if "rules" in quality and quality["rules"]:
            rules = quality["rules"]
            self.validate_field_type(rules, list, "/quality/rules", allow_none=False)
            odcs_rules = []
            for i, rule in enumerate(rules):
                if isinstance(rule, dict):
                    odcs_rule = self._map_quality_rule_to_odcs(rule, f"/quality/rules/{i}")
                    if odcs_rule:
                        odcs_rules.append(odcs_rule)
            if odcs_rules:
                odcs_quality["rules"] = odcs_rules

        if odcs_quality:
            odcs_doc["quality"] = odcs_quality

    def _map_quality_rule_to_odcs(
        self,
        rule: Dict[str, Any],
        field_path: str
    ) -> Optional[Dict[str, Any]]:
        """Map HubContract quality rule to ODCS quality rule."""
        if not isinstance(rule, dict):
            return None

        odcs_rule = {}

        # Map common rule fields
        for field in ["id", "rule_id", "name", "dimension", "type", "rule", "expression", "severity", "threshold", "target", "unit", "description"]:
            if field in rule and rule[field] is not None:
                odcs_rule[field] = rule[field]

        return odcs_rule if odcs_rule else None

    def _map_lifecycle_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract lifecycle section to ODCS lifecycle section."""
        lifecycle = hub_contract.get("lifecycle")
        if not lifecycle or not isinstance(lifecycle, dict):
            return

        odcs_lifecycle = {}

        # Map data_source
        if "data_source" in lifecycle and lifecycle["data_source"]:
            if isinstance(lifecycle["data_source"], str):
                odcs_lifecycle["data_source"] = lifecycle["data_source"]
            elif isinstance(lifecycle["data_source"], dict):
                odcs_lifecycle["data_source"] = lifecycle["data_source"]

        # Map refresh_cadence
        if "refresh_cadence" in lifecycle and lifecycle["refresh_cadence"]:
            odcs_lifecycle["refresh_cadence"] = lifecycle["refresh_cadence"]

        # Map slas
        if "slas" in lifecycle and lifecycle["slas"]:
            slas = lifecycle["slas"]
            if isinstance(slas, dict):
                odcs_lifecycle["slas"] = slas

        if odcs_lifecycle:
            odcs_doc["lifecycle"] = odcs_lifecycle

    def _map_servicelevels_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract servicelevels section to ODCS slaProperties."""
        servicelevels = hub_contract.get("servicelevels")
        if not servicelevels or not isinstance(servicelevels, list):
            return

        odcs_sla_properties = []
        for i, servicelevel in enumerate(servicelevels):
            if not isinstance(servicelevel, dict):
                continue

            sla_property = {}

            # Map property name
            if "name" in servicelevel:
                self.validate_field_type(servicelevel["name"], str, f"/servicelevels/{i}/name", allow_none=False)
                sla_property["property"] = servicelevel["name"]
            elif "property" in servicelevel:
                self.validate_field_type(servicelevel["property"], str, f"/servicelevels/{i}/property", allow_none=False)
                sla_property["property"] = servicelevel["property"]

            # Map target
            if "target" in servicelevel:
                sla_property["target"] = servicelevel["target"]

            # Map unit
            if "unit" in servicelevel:
                self.validate_field_type(servicelevel["unit"], str, f"/servicelevels/{i}/unit", allow_none=True)
                sla_property["unit"] = servicelevel["unit"]

            # Map description
            if "description" in servicelevel:
                self.validate_field_type(servicelevel["description"], str, f"/servicelevels/{i}/description", allow_none=True)
                sla_property["description"] = servicelevel["description"]

            if sla_property:
                odcs_sla_properties.append(sla_property)

        if odcs_sla_properties:
            odcs_doc["slaProperties"] = odcs_sla_properties

    def _map_lineage_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract lineage section to ODCS transformSourceObjects and transformLogic."""
        lineage = hub_contract.get("lineage")
        if not lineage:
            return

        if isinstance(lineage, dict):
            # Map entries to transformSourceObjects
            entries = lineage.get("entries", [])
            if entries and isinstance(entries, list):
                transform_source_objects = []
                for i, entry in enumerate(entries):
                    if isinstance(entry, dict):
                        source_obj = {}
                        # Map contract reference
                        if "contract_id" in entry:
                            source_obj["name"] = entry["contract_id"]
                        if "contract_version" in entry:
                            source_obj["version"] = entry["contract_version"]
                        if "namespace" in entry:
                            source_obj["namespace"] = entry["namespace"]
                        if "model" in entry:
                            source_obj["model"] = entry["model"]
                        if "field" in entry:
                            source_obj["field"] = entry["field"]
                        if source_obj:
                            transform_source_objects.append(source_obj)
                if transform_source_objects:
                    odcs_doc["transformSourceObjects"] = transform_source_objects

            # Map transformLogic if present
            if "transform_logic" in lineage:
                odcs_doc["transformLogic"] = lineage["transform_logic"]
            elif "description" in lineage:
                odcs_doc["transformLogic"] = lineage["description"]

    def _map_marketplace_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract marketplace section to ODCS marketplace section."""
        marketplace = hub_contract.get("marketplace")
        if not marketplace or not isinstance(marketplace, dict):
            return

        odcs_marketplace = {}

        # Map license_summary
        if "license_summary" in marketplace and marketplace["license_summary"]:
            self.validate_field_type(marketplace["license_summary"], str, "/marketplace/license_summary", allow_none=True)
            odcs_marketplace["license_summary"] = marketplace["license_summary"]

        # Map intended_use
        if "intended_use" in marketplace and marketplace["intended_use"]:
            intended_use = marketplace["intended_use"]
            if isinstance(intended_use, list):
                odcs_marketplace["intended_use"] = intended_use
            elif isinstance(intended_use, str):
                odcs_marketplace["intended_use"] = [intended_use]

        # Map restricted_use
        if "restricted_use" in marketplace and marketplace["restricted_use"]:
            restricted_use = marketplace["restricted_use"]
            if isinstance(restricted_use, list):
                odcs_marketplace["restricted_use"] = restricted_use
            elif isinstance(restricted_use, str):
                odcs_marketplace["restricted_use"] = [restricted_use]

        if odcs_marketplace:
            odcs_doc["marketplace"] = odcs_marketplace

    def _map_privacy_compliance_section(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any]
    ) -> None:
        """Map HubContract privacy_compliance section to ODCS privacy_compliance section."""
        privacy_compliance = hub_contract.get("privacy_compliance")
        if not privacy_compliance or not isinstance(privacy_compliance, dict):
            return

        odcs_privacy_compliance = {}

        # Map all privacy_compliance fields
        for field in ["contains_personal_data", "personal_data_categories", "jurisdictions", "legal_bases", "retention_policy"]:
            if field in privacy_compliance and privacy_compliance[field] is not None:
                odcs_privacy_compliance[field] = privacy_compliance[field]

        if odcs_privacy_compliance:
            odcs_doc["privacy_compliance"] = odcs_privacy_compliance


class ODCSGeneratorV3_0_0_Preview(ODCSGeneratorBase):
    """
    ODCS 3.0.0-Preview Generator implementation.

    Generates ODCS 3.0.0-preview documents from HubContract format.
    Handles preview version differences with graceful degradation:
    - Preview versions may have incomplete feature sets
    - Experimental features may be omitted
    - Supports core ODCS 3.0.0-preview features

    Key Mappings:
    - hub_contract.id → odcs.id
    - hub_contract.info.name → odcs.name
    - hub_contract.info.description → odcs.description
    - hub_contract.info.version → odcs.version
    - hub_contract.schema → odcs.schema (direct fields[], no models[] support)
    - hub_contract.quality → odcs.quality
    - hub_contract.lifecycle → odcs.lifecycle
    - hub_contract.info.owners[] → odcs.info.owners[]
    - hub_contract.info.tags[] → odcs.info.tags[]

    Graceful Degradation:
    - Features introduced in ODCS 3.0.1+ and 3.0.2+ are omitted or logged as warnings
    - Preview-specific experimental features are handled appropriately
    - Missing optional fields don't cause errors
    """

    def __init__(self):
        """Initialize the ODCS 3.0.0-preview generator."""
        super().__init__()
        self.target_version = "3.0.0-preview"

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ODCS 3.0.0-preview document from HubContract format.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (ignored, always uses 3.0.0-preview)

        Returns:
            ODCS 3.0.0-preview document as dictionary

        Raises:
            ODCSGenerationError: If generation fails with field-level context
        """
        try:
            # Validate HubContract structure first
            self.validate_hub_contract_structure(hub_contract)

            contract_id = hub_contract["id"]
            info = hub_contract["info"]
            name = info["name"]

            self.log_generation_start(contract_id, name, self.target_version)

            # Initialize ODCS 3.0.0-preview document structure
            odcs_doc = {
                "apiVersion": f"odcs.io/v{self.target_version}",
                "kind": "DataContract",
                "id": contract_id,
                "name": name,
            }

            # Map basic info fields
            if "description" in info and info["description"]:
                self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
                odcs_doc["description"] = info["description"]

            if "version" in info and info["version"]:
                self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
                odcs_doc["version"] = info["version"]

            # Map info section (owners, tags, etc.)
            self._map_info_section(hub_contract, odcs_doc)

            # Map schema section (ODCS 3.0.0-preview format, no models[] support)
            self._map_schema_section_v3_0_0_preview(hub_contract, odcs_doc)

            # Map quality section
            self._map_quality_section(hub_contract, odcs_doc)

            # Map lifecycle section (with graceful degradation for 3.0.1+ features)
            self._map_lifecycle_section_v3_0_0_preview(hub_contract, odcs_doc)

            # Map marketplace section (with graceful degradation for 3.0.1+ features)
            self._map_marketplace_section_v3_0_0_preview(hub_contract, odcs_doc)

            # Map privacy_compliance section (if supported in preview)
            self._map_privacy_compliance_section_v3_0_0_preview(hub_contract, odcs_doc)

            self.log_generation_complete(contract_id, name, self.target_version)
            return odcs_doc

        except ODCSGenerationError:
            # Re-raise ODCS errors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            self.log_generation_error(e, hub_contract.get("id"))
            raise ODCSGenerationError(
                message=f"Unexpected error generating ODCS 3.0.0-preview document: {str(e)}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                cause=e,
            ) from e

    def _map_info_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract info section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        info = hub_contract.get("info", {})
        if not isinstance(info, dict):
            return

        # Initialize info section if not present
        if "info" not in odcs_doc:
            odcs_doc["info"] = {}

        # Map owners
        owners = info.get("owners", [])
        if owners:
            odcs_owners = []
            for owner in owners:
                if isinstance(owner, dict):
                    odcs_owner = {}
                    if "name" in owner:
                        odcs_owner["name"] = owner["name"]
                    if "email" in owner:
                        odcs_owner["email"] = owner["email"]
                    if odcs_owner:
                        odcs_owners.append(odcs_owner)
                elif isinstance(owner, str):
                    # Convert string owner to dict format
                    odcs_owners.append({"name": owner})
            if odcs_owners:
                odcs_doc["info"]["owners"] = odcs_owners

        # Map tags
        tags = info.get("tags", [])
        if tags:
            odcs_doc["info"]["tags"] = tags

        # Only add info section if it has content
        if not odcs_doc["info"]:
            del odcs_doc["info"]

    def _map_schema_section_v3_0_0_preview(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract schema section to ODCS 3.0.0-preview format.

        ODCS 3.0.0-preview does not support models[] array, only direct schema.fields[].

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        schema = hub_contract.get("schema")
        if not schema or not isinstance(schema, dict):
            return

        odcs_schema = {}

        # Map fields (ODCS 3.0.0-preview uses direct fields array, not models[])
        fields = schema.get("fields", [])
        if fields:
            odcs_fields = []
            for field in fields:
                if not isinstance(field, dict):
                    continue
                odcs_field = {
                    "name": field.get("name"),
                    "type": field.get("data_type") or field.get("type", "string"),
                }
                # Add optional field properties
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
                if "min_length" in field or "minLength" in field:
                    odcs_field["minLength"] = field.get("min_length") or field.get("minLength")
                if "max_length" in field or "maxLength" in field:
                    odcs_field["maxLength"] = field.get("max_length") or field.get("maxLength")
                if "minimum" in field:
                    odcs_field["minimum"] = field["minimum"]
                if "maximum" in field:
                    odcs_field["maximum"] = field["maximum"]
                odcs_fields.append(odcs_field)
            if odcs_fields:
                odcs_schema["fields"] = odcs_fields

        # Map primary_key
        primary_key = schema.get("primary_key")
        if primary_key:
            if isinstance(primary_key, list):
                odcs_schema["primaryKey"] = primary_key if len(primary_key) > 1 else primary_key[0] if primary_key else None
            elif isinstance(primary_key, str):
                odcs_schema["primaryKey"] = primary_key

        # Map unique_constraints
        unique_constraints = schema.get("unique_constraints")
        if unique_constraints:
            odcs_schema["uniqueConstraints"] = unique_constraints

        # Map indexes
        indexes = schema.get("indexes")
        if indexes:
            odcs_schema["indexes"] = indexes

        if odcs_schema:
            odcs_doc["schema"] = odcs_schema

    def _map_quality_section(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract quality section to ODCS format.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        quality = hub_contract.get("quality")
        if not quality or not isinstance(quality, dict):
            return

        odcs_quality = {}

        # Map default_profile_key
        if "default_profile_key" in quality:
            odcs_quality["default_profile_key"] = quality["default_profile_key"]

        # Map rules
        rules = quality.get("rules", [])
        if rules:
            odcs_rules = []
            for rule in rules:
                if isinstance(rule, dict):
                    odcs_rule = {}
                    if "name" in rule:
                        odcs_rule["name"] = rule["name"]
                    if "type" in rule:
                        odcs_rule["type"] = rule["type"]
                    if "description" in rule:
                        odcs_rule["description"] = rule["description"]
                    if "expression" in rule:
                        odcs_rule["expression"] = rule["expression"]
                    if "severity" in rule:
                        odcs_rule["severity"] = rule["severity"]
                    if odcs_rule:
                        odcs_rules.append(odcs_rule)
            if odcs_rules:
                odcs_quality["rules"] = odcs_rules

        if odcs_quality:
            odcs_doc["quality"] = odcs_quality

    def _map_lifecycle_section_v3_0_0_preview(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract lifecycle section to ODCS 3.0.0-preview format.

        Gracefully degrades 3.0.1+ enhanced lifecycle features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        lifecycle = hub_contract.get("lifecycle")
        if not lifecycle or not isinstance(lifecycle, dict):
            return

        odcs_lifecycle = {}

        # Map data_source (supported in 3.0.0-preview)
        if "data_source" in lifecycle:
            odcs_lifecycle["data_source"] = lifecycle["data_source"]

        # Map refresh_cadence (supported in 3.0.0-preview)
        if "refresh_cadence" in lifecycle:
            odcs_lifecycle["refresh_cadence"] = lifecycle["refresh_cadence"]

        # Map slas (supported in 3.0.0-preview)
        slas = lifecycle.get("slas")
        if slas and isinstance(slas, dict):
            odcs_slas = {}
            if "availability" in slas:
                odcs_slas["availability"] = slas["availability"]
            if "latency_ms_p95" in slas:
                odcs_slas["latency_ms_p95"] = slas["latency_ms_p95"]
            if odcs_slas:
                odcs_lifecycle["slas"] = odcs_slas

        # Check for 3.0.1+ enhanced lifecycle features and warn
        enhanced_features = []
        if "enhanced_features" in lifecycle:
            enhanced_features.append("enhanced_features")
        if "advanced_slas" in lifecycle:
            enhanced_features.append("advanced_slas")

        if enhanced_features:
            self.logger.warning(
                "odcs_v3_0_0_preview_enhanced_lifecycle_features_omitted",
                features=enhanced_features,
                message=f"ODCS 3.0.1+ enhanced lifecycle features omitted: {', '.join(enhanced_features)}"
            )

        if odcs_lifecycle:
            odcs_doc["lifecycle"] = odcs_lifecycle

    def _map_marketplace_section_v3_0_0_preview(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract marketplace section to ODCS 3.0.0-preview format.

        Gracefully degrades 3.0.1+ enhanced marketplace features.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        marketplace = hub_contract.get("marketplace")
        if not marketplace or not isinstance(marketplace, dict):
            return

        odcs_marketplace = {}

        # Map license_summary (supported in 3.0.0-preview)
        if "license_summary" in marketplace:
            odcs_marketplace["license_summary"] = marketplace["license_summary"]

        # Map intended_use (supported in 3.0.0-preview)
        if "intended_use" in marketplace:
            odcs_marketplace["intended_use"] = marketplace["intended_use"]

        # Map restricted_use (supported in 3.0.0-preview)
        if "restricted_use" in marketplace:
            odcs_marketplace["restricted_use"] = marketplace["restricted_use"]

        # Check for 3.0.1+ enhanced marketplace features and warn
        enhanced_features = []
        if "enhanced_features" in marketplace:
            enhanced_features.append("enhanced_features")
        if "advanced_pricing" in marketplace:
            enhanced_features.append("advanced_pricing")
        if "access_methods" in marketplace:
            # Check if it's 3.0.1+ format
            access_methods = marketplace.get("access_methods")
            if isinstance(access_methods, list) and access_methods:
                first_method = access_methods[0] if access_methods else {}
                if isinstance(first_method, dict) and "enhanced" in first_method:
                    enhanced_features.append("access_methods (enhanced)")

        if enhanced_features:
            self.logger.warning(
                "odcs_v3_0_0_preview_enhanced_marketplace_features_omitted",
                features=enhanced_features,
                message=f"ODCS 3.0.1+ enhanced marketplace features omitted: {', '.join(enhanced_features)}"
            )

        if odcs_marketplace:
            odcs_doc["marketplace"] = odcs_marketplace

    def _map_privacy_compliance_section_v3_0_0_preview(self, hub_contract: Dict[str, Any], odcs_doc: Dict[str, Any]) -> None:
        """
        Map HubContract privacy_compliance section to ODCS 3.0.0-preview format.

        Preview version may have limited privacy compliance support.

        Args:
            hub_contract: HubContract dictionary
            odcs_doc: ODCS document dictionary to update
        """
        privacy_compliance = hub_contract.get("privacy_compliance")
        if not privacy_compliance or not isinstance(privacy_compliance, dict):
            return

        odcs_privacy = {}

        # Map basic privacy compliance fields (preview may support these)
        if "contains_personal_data" in privacy_compliance:
            odcs_privacy["contains_personal_data"] = privacy_compliance["contains_personal_data"]

        # Map personal_data_categories
        if "personal_data_categories" in privacy_compliance:
            odcs_privacy["personal_data_categories"] = privacy_compliance["personal_data_categories"]

        # Map jurisdictions
        if "jurisdictions" in privacy_compliance:
            odcs_privacy["jurisdictions"] = privacy_compliance["jurisdictions"]

        # Map legal_bases
        if "legal_bases" in privacy_compliance:
            odcs_privacy["legal_bases"] = privacy_compliance["legal_bases"]

        # Map retention_policy
        retention_policy = privacy_compliance.get("retention_policy")
        if retention_policy and isinstance(retention_policy, dict):
            odcs_retention = {}
            if "period" in retention_policy:
                odcs_retention["period"] = retention_policy["period"]
            if "notes" in retention_policy:
                odcs_retention["notes"] = retention_policy["notes"]
            if odcs_retention:
                odcs_privacy["retention_policy"] = odcs_retention

        if odcs_privacy:
            odcs_doc["privacy_compliance"] = odcs_privacy


# ============================================================================
# Generator Registry & Factory
# ============================================================================

# Registry for ODCS generators by version
_ODCS_GENERATOR_REGISTRY: Dict[str, ODCSGeneratorBase] = {}

# Latest ODCS version (used as fallback)
# Default export version — kept at 3.0.2 for backward compatibility.
# v3.1.0 is available via explicit version=3.1.0 query param.
_LATEST_ODCS_VERSION = "3.0.2"


def register_odcs_generator(version: str, generator: ODCSGeneratorBase) -> None:
    """
    Register an ODCS generator for a specific version.

    Args:
        version: ODCS version string (e.g., "3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2")
        generator: ODCSGeneratorBase instance
    """
    if not isinstance(generator, ODCSGeneratorBase):
        raise TypeError(
            f"Generator must be an instance of ODCSGeneratorBase, got {type(generator).__name__}"
        )
    _ODCS_GENERATOR_REGISTRY[version] = generator
    logger.debug(
        "odcs_generator_registered",
        version=version,
        generator_class=generator.__class__.__name__
    )


def get_odcs_generator(
    version: Optional[str] = None,
    hub_contract: Optional[Dict[str, Any]] = None
) -> ODCSGeneratorBase:
    """
    Get ODCS generator for the specified version.

    Version detection priority:
    1. Explicit version parameter (if provided)
    2. HubContract original_spec metadata (if original_spec_type is ODCS)
    3. Fallback to latest version (3.0.2) with warning

    Args:
        version: Target ODCS version (optional, will be detected if not provided)
        hub_contract: HubContract dictionary (optional, used for version detection)

    Returns:
        ODCSGeneratorBase instance for the requested version

    Raises:
        ODCSGenerationError: If no generator is found for the version and fallback fails
    """
    detected_version = version

    # If version not provided, try to detect from HubContract
    if detected_version is None and hub_contract is not None:
        detected_version = _detect_version_from_hubcontract(hub_contract)

    # If still no version, use latest as fallback
    if detected_version is None:
        detected_version = _LATEST_ODCS_VERSION
        logger.warning(
            "odcs_version_not_provided_using_fallback",
            fallback_version=detected_version,
            message="No ODCS version specified, using latest version as fallback"
        )

    # Normalize version string (handle variations like "3.0.0-preview")
    normalized_version = _normalize_version_string(detected_version)

    # Try to get generator for the requested version
    generator = _ODCS_GENERATOR_REGISTRY.get(normalized_version)

    if generator is not None:
        logger.debug(
            "odcs_generator_found",
            version=normalized_version,
            generator_class=generator.__class__.__name__
        )
        return generator

    # Fallback to latest version if requested version not found
    if normalized_version != _LATEST_ODCS_VERSION:
        logger.warning(
            "odcs_generator_not_found_using_fallback",
            requested_version=normalized_version,
            fallback_version=_LATEST_ODCS_VERSION,
            message=f"Generator for ODCS version '{normalized_version}' not found, using latest version '{_LATEST_ODCS_VERSION}' as fallback"
        )
        generator = _ODCS_GENERATOR_REGISTRY.get(_LATEST_ODCS_VERSION)

    if generator is None:
        raise ODCSGenerationError(
            message=f"No ODCS generator found for version '{normalized_version}' and fallback to '{_LATEST_ODCS_VERSION}' also failed. Available versions: {list(_ODCS_GENERATOR_REGISTRY.keys())}",
            error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
            context={
                "field_path": "/",
                "requested_version": normalized_version,
                "fallback_version": _LATEST_ODCS_VERSION,
                "available_versions": list(_ODCS_GENERATOR_REGISTRY.keys()),
            },
        )

    return generator


def _detect_version_from_hubcontract(hub_contract: Dict[str, Any]) -> Optional[str]:
    """
    Detect ODCS version from HubContract metadata.

    Checks:
    1. original_spec metadata (if original_spec_type is ODCS)
    2. normalization metadata (if original_spec_type is ODCS)

    Args:
        hub_contract: HubContract dictionary

    Returns:
        ODCS version string if detected, None otherwise
    """
    if not isinstance(hub_contract, dict):
        return None

    # Check original_spec metadata
    original_spec = hub_contract.get("original_spec")
    if isinstance(original_spec, dict):
        spec_type = original_spec.get("type")
        if spec_type == "ODCS":
            spec_version = original_spec.get("version")
            if spec_version:
                return spec_version

    # Check normalization metadata
    normalization = hub_contract.get("normalization")
    if isinstance(normalization, dict):
        spec_type = normalization.get("original_spec_type")
        if spec_type == "ODCS":
            spec_version = normalization.get("original_spec_version")
            if spec_version:
                return spec_version

    return None


def _normalize_version_string(version: str) -> str:
    """
    Normalize ODCS version string to registry key format.

    Handles variations like:
    - "3.0.0-preview" → "3.0.0-preview"
    - "3.0.0" → "3.0.0"
    - "v3.0.2" → "3.0.2"
    - "odcs.io/v3.0.2" → "3.0.2"

    Args:
        version: Version string to normalize

    Returns:
        Normalized version string
    """
    if not version:
        return _LATEST_ODCS_VERSION

    # Remove "v" prefix if present
    version = version.lstrip("vV")

    # Extract version from "odcs.io/v3.0.2" format
    if "/" in version:
        version = version.split("/")[-1]

    # Remove "v" prefix again (in case it was "odcs.io/v3.0.2")
    version = version.lstrip("vV")

    return version


def get_supported_odcs_versions() -> List[str]:
    """
    Get list of supported ODCS versions.

    Returns:
        List of supported ODCS version strings
    """
    return sorted(_ODCS_GENERATOR_REGISTRY.keys())


# =========================================================================
# Phase 26.4.1 — ODCS 3.1.0 Generator
# =========================================================================

class ODCSGeneratorV3_1_0(ODCSGeneratorV3_0_2):
    """
    ODCS 3.1.0 Generator — extends v3.0.2 with v3.1.0 fields.

    Additional mappings over v3.0.2:
    - relationships[] on schema objects and fields
    - element_id → id on schema objects and fields
    - info.owners → team.members (object, not array)
    - quality.library[] built-in metric types
    - Excludes deprecated slaDefaultElement
    - logicalType / logicalTypeOptions.timezone
    """

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: Dict[str, Any],
        target_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        if target_version is None:
            target_version = "3.1.0"

        # Generate base v3.0.2 document
        odcs_doc = super().generate_odcs_from_hubcontract(
            hub_contract, target_version=target_version,
        )

        # Ensure apiVersion uses consistent format
        odcs_doc["apiVersion"] = f"v{target_version}"
        odcs_doc["kind"] = "DataContract"

        # --- team: object with members[] ---
        self._map_team_v31(hub_contract, odcs_doc)

        # --- schema: relationships + element_id ---
        self._map_v31_schema_extensions(hub_contract, odcs_doc)

        # --- quality.library ---
        self._map_v31_quality_library(hub_contract, odcs_doc)

        # --- strip slaDefaultElement ---
        self._strip_sla_default_element(odcs_doc)

        return odcs_doc

    # -- v3.1.0-specific helpers --

    def _map_team_v31(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any],
    ) -> None:
        """Map info.owners → team.members (object structure)."""
        # Remove array-style team if base generator added it
        odcs_doc.pop("team", None)

        owners = hub_contract.get("info", {}).get("owners", [])
        team_list = hub_contract.get("team", [])
        members = []

        # Prefer team[] if available (richer data)
        if team_list and isinstance(team_list, list):
            for t in team_list:
                if not isinstance(t, dict):
                    continue
                member: Dict[str, Any] = {}
                if "member" in t or "name" in t:
                    member["name"] = t.get("name") or t.get("member")
                if "email" in t:
                    member["email"] = t["email"]
                if "role" in t:
                    member["role"] = t["role"]
                if "id" in t:
                    member["id"] = t["id"]
                if "description" in t:
                    member["description"] = t["description"]
                if member:
                    members.append(member)
        elif owners and isinstance(owners, list):
            for o in owners:
                if not isinstance(o, dict):
                    continue
                member = {}
                if "name" in o:
                    member["name"] = o["name"]
                if "email" in o:
                    member["email"] = o["email"]
                if member:
                    members.append(member)

        if members:
            odcs_doc["team"] = {"members": members}

    def _map_v31_schema_extensions(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any],
    ) -> None:
        """Add relationships[], element_id, logicalType to schema."""
        models = hub_contract.get("models", [])
        if not models or not isinstance(models, list):
            return

        # Get the already-generated schema entries
        odcs_schema = odcs_doc.get("schema")
        if odcs_schema is None:
            return

        # Normalize to list for iteration
        if isinstance(odcs_schema, dict):
            schema_list = [odcs_schema]
        elif isinstance(odcs_schema, list):
            schema_list = odcs_schema
        else:
            return

        for i, model in enumerate(models):
            if not isinstance(model, dict) or i >= len(schema_list):
                continue
            odcs_entry = schema_list[i]
            if not isinstance(odcs_entry, dict):
                continue

            # element_id → id
            eid = model.get("element_id")
            if eid:
                odcs_entry["id"] = eid

            # data_granularity_description
            dgd = model.get("data_granularity_description")
            if dgd:
                odcs_entry["dataGranularityDescription"] = dgd

            # relationships[]
            rels = model.get("relationships")
            if rels and isinstance(rels, list):
                odcs_rels = []
                for r in rels:
                    if not isinstance(r, dict):
                        continue
                    odcs_rel: Dict[str, Any] = {}
                    if r.get("id"):
                        odcs_rel["id"] = r["id"]
                    if r.get("name"):
                        odcs_rel["name"] = r["name"]
                    if r.get("type"):
                        odcs_rel["type"] = r["type"]
                    if r.get("source"):
                        odcs_rel["source"] = r["source"]
                    if r.get("target_contract"):
                        odcs_rel["targetContract"] = r["target_contract"]
                    if r.get("target_model"):
                        odcs_rel["targetModel"] = r["target_model"]
                    if r.get("target_properties"):
                        odcs_rel["targetProperties"] = r["target_properties"]
                    if r.get("description"):
                        odcs_rel["description"] = r["description"]
                    if r.get("custom_properties"):
                        odcs_rel["customProperties"] = r["custom_properties"]
                    if odcs_rel:
                        odcs_rels.append(odcs_rel)
                if odcs_rels:
                    odcs_entry["relationships"] = odcs_rels

            # field-level: element_id + logicalType
            model_fields = model.get("fields", [])
            odcs_fields = odcs_entry.get("fields", [])
            for j, mf in enumerate(model_fields):
                if not isinstance(mf, dict) or j >= len(odcs_fields):
                    continue
                of = odcs_fields[j]
                if not isinstance(of, dict):
                    continue
                feid = mf.get("element_id")
                if feid:
                    of["id"] = feid
                lt = mf.get("logicalType")
                if lt:
                    of["logicalType"] = lt
                lto = mf.get("logicalTypeOptions")
                if isinstance(lto, dict) and lto:
                    of["logicalTypeOptions"] = lto

    def _map_v31_quality_library(
        self,
        hub_contract: Dict[str, Any],
        odcs_doc: Dict[str, Any],
    ) -> None:
        """Map quality rules with v3.1.0 library types."""
        _LIB_TYPES = {
            "rowCount", "nullValues", "invalidValues",
            "duplicateValues", "missingValues",
        }
        quality = hub_contract.get("quality", {})
        if not isinstance(quality, dict):
            return
        rules = quality.get("rules", [])
        library_entries = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if rule.get("type") in _LIB_TYPES:
                library_entries.append(rule)

        if library_entries:
            odcs_quality = odcs_doc.setdefault("quality", {})
            odcs_quality["library"] = library_entries

    @staticmethod
    def _strip_sla_default_element(odcs_doc: Dict[str, Any]) -> None:
        """Remove deprecated slaDefaultElement from SLA entries."""
        for sl in odcs_doc.get("slaProperties", []):
            if isinstance(sl, dict):
                sl.pop("slaDefaultElement", None)


# Initialize registry with all available generators
def _initialize_generator_registry() -> None:
    """Initialize the generator registry with all available generators."""
    register_odcs_generator("3.1.0", ODCSGeneratorV3_1_0())
    register_odcs_generator("3.0.2", ODCSGeneratorV3_0_2())
    register_odcs_generator("3.0.1", ODCSGeneratorV3_0_1())
    register_odcs_generator("3.0.0", ODCSGeneratorV3_0_0())
    register_odcs_generator("3.0.0-preview", ODCSGeneratorV3_0_0_Preview())
    register_odcs_generator("2.2.2", ODCSGeneratorV2_2_2())
    logger.info(
        "odcs_generator_registry_initialized",
        versions=list(_ODCS_GENERATOR_REGISTRY.keys()),
        count=len(_ODCS_GENERATOR_REGISTRY)
    )


# Auto-initialize registry on module import
_initialize_generator_registry()


def generate_odcs_from_hubcontract(
    hub_contract: Dict[str, Any],
    target_version: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate ODCS document from HubContract format.

    Uses the generator registry to select the appropriate version-specific generator.
    Version detection priority:
    1. Explicit target_version parameter
    2. HubContract original_spec metadata (if original_spec_type is ODCS)
    3. Fallback to latest version (3.0.2) with warning

    Features:
    - Comprehensive error handling with context
    - Performance metrics (duration tracking)
    - Success/failure metrics
    - Structured logging

    Args:
        hub_contract: HubContract dictionary
        target_version: Target ODCS version (optional, will be auto-detected if not provided)
        tenant_id: Tenant ID for metrics (optional)

    Returns:
        ODCS document as dictionary

    Raises:
        ODCSGenerationError: If generation fails with context including:
            - field_path: Path to the field that caused the error
            - expected: Expected type or value
            - actual: Actual type or value that caused the error
    """
    start_time = time.time()
    effective_tenant_id = tenant_id or "unknown"
    detected_version = target_version
    final_version = None
    status = "success"

    # Validate input type first
    if not isinstance(hub_contract, dict):
        raise ODCSGenerationError(
            message=f"HubContract must be a dictionary, got {type(hub_contract).__name__}",
            error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
            context={
                "field_path": "/",
                "expected": "dict",
                "actual": type(hub_contract).__name__,
            },
        )

    try:
        # Get appropriate generator from registry
        generator = get_odcs_generator(version=target_version, hub_contract=hub_contract)

        # Detect final version that will be used
        if target_version:
            final_version = _normalize_version_string(target_version)
        else:
            detected = _detect_version_from_hubcontract(hub_contract)
            final_version = _normalize_version_string(detected) if detected else _LATEST_ODCS_VERSION

        # Log generation start
        logger.info(
            "odcs_generation_started",
            contract_id=hub_contract.get("id"),
            target_version=final_version,
            detected_version=detected_version,
            tenant_id=effective_tenant_id
        )

        # Use generator to create ODCS document
        odcs_doc = generator.generate_odcs_from_hubcontract(hub_contract, target_version=target_version)

        # Calculate duration
        duration = time.time() - start_time

        # Record success metrics
        try:
            from hub.apps.observability.otel_metrics import (
                odcs_generation_total,
                odcs_generation_duration_seconds,
                odcs_generation_success_rate,
            )
            odcs_generation_total.labels(
                status="success",
                version=final_version,
                tenant_id=effective_tenant_id
            ).inc()
            odcs_generation_duration_seconds.labels(
                status="success",
                version=final_version,
                tenant_id=effective_tenant_id
            ).observe(duration)
            odcs_generation_success_rate.labels(tenant_id=effective_tenant_id).set(1.0)
        except Exception as metrics_err:
            logger.debug(
                "odcs_generation_metrics_failed",
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )

        # Log successful completion
        logger.info(
            "odcs_generation_completed",
            contract_id=hub_contract.get("id"),
            version=final_version,
            duration_seconds=duration,
            tenant_id=effective_tenant_id
        )

        return odcs_doc

    except ODCSGenerationError as e:
        # Calculate duration for failed generation
        duration = time.time() - start_time
        status = "failure"

        # Record failure metrics
        try:
            from hub.apps.observability.otel_metrics import (
                odcs_generation_total,
                odcs_generation_duration_seconds,
                odcs_generation_success_rate,
            )
            odcs_generation_total.labels(
                status="failure",
                version=final_version or "unknown",
                tenant_id=effective_tenant_id
            ).inc()
            odcs_generation_duration_seconds.labels(
                status="failure",
                version=final_version or "unknown",
                tenant_id=effective_tenant_id
            ).observe(duration)
            odcs_generation_success_rate.labels(tenant_id=effective_tenant_id).set(0.0)
        except Exception as metrics_err:
            logger.debug(
                "odcs_generation_metrics_failed",
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )

        # Log failure
        logger.error(
            "odcs_generation_failed",
            contract_id=hub_contract.get("id"),
            version=final_version,
            duration_seconds=duration,
            error_code=getattr(e, 'error_code', 'UNKNOWN'),
            error_message=str(e),
            tenant_id=effective_tenant_id,
            exc_info=True
        )

        # Re-raise ODCS errors as-is
        raise

    except Exception as e:
        # Calculate duration for unexpected errors
        duration = time.time() - start_time
        status = "failure"

        # Record failure metrics
        try:
            from hub.apps.observability.otel_metrics import (
                odcs_generation_total,
                odcs_generation_duration_seconds,
                odcs_generation_success_rate,
            )
            odcs_generation_total.labels(
                status="failure",
                version=final_version or "unknown",
                tenant_id=effective_tenant_id
            ).inc()
            odcs_generation_duration_seconds.labels(
                status="failure",
                version=final_version or "unknown",
                tenant_id=effective_tenant_id
            ).observe(duration)
            odcs_generation_success_rate.labels(tenant_id=effective_tenant_id).set(0.0)
        except Exception as metrics_err:
            logger.debug(
                "odcs_generation_metrics_failed",
                extra={"error_type": type(metrics_err).__name__, "error": str(metrics_err)},
            )

        # Wrap unexpected errors
        logger.error(
            "odcs_generation_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            contract_id=hub_contract.get("id"),
            duration_seconds=duration,
            tenant_id=effective_tenant_id,
            exc_info=True,
        )
        raise ODCSGenerationError(
            message=f"Unexpected error generating ODCS document: {str(e)}",
            error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def _legacy_generate_odcs_from_hubcontract(
    hub_contract: Dict[str, Any],
    target_version: str = "3.0.2"
) -> Dict[str, Any]:
    """
    Legacy implementation (kept for reference, not used).

    This was the original implementation before the registry system.
    Now replaced by generate_odcs_from_hubcontract() which uses the registry.
    """
    try:
        # Validate input
        if not isinstance(hub_contract, dict):
            raise ODCSGenerationError(
                message=f"HubContract must be a dictionary, got {type(hub_contract).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "expected": "dict",
                    "actual": type(hub_contract).__name__,
                },
            )

        # Validate required sections
        if "info" not in hub_contract:
            raise ODCSGenerationError(
                message="HubContract missing required 'info' section",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": "/info",
                    "expected": "dict",
                    "actual": None,
                },
            )

        info = hub_contract.get("info")
        if not isinstance(info, dict):
            raise ODCSGenerationError(
                message=f"HubContract 'info' must be a dictionary, got {type(info).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/info",
                    "expected": "dict",
                    "actual": type(info).__name__,
                },
            )

        # Validate required info.name
        if "name" not in info:
            raise ODCSGenerationError(
                message="HubContract 'info.name' is required",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": "/info/name",
                    "expected": "str",
                    "actual": None,
                },
            )

        name = info.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ODCSGenerationError(
                message=f"HubContract 'info.name' must be a non-empty string, got {type(name).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/info/name",
                    "expected": "str (non-empty)",
                    "actual": type(name).__name__ if name is not None else None,
                },
            )

        # Get contract ID from hub_contract.id
        contract_id = hub_contract.get("id", "")
        if not isinstance(contract_id, str):
            raise ODCSGenerationError(
                message=f"HubContract 'id' must be a string, got {type(contract_id).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/id",
                    "expected": "str",
                    "actual": type(contract_id).__name__,
                },
            )

        # Initialize ODCS document structure
        odcs_doc = {
            "apiVersion": f"odcs.io/v{target_version}",
            "kind": "DataContract",
            "id": contract_id,
            "name": name,
        }

        # Add version if available
        version = info.get("version")
        if version is not None:
            if not isinstance(version, str):
                raise ODCSGenerationError(
                    message=f"HubContract 'info.version' must be a string, got {type(version).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": "/info/version",
                        "expected": "str",
                        "actual": type(version).__name__,
                    },
                )
            odcs_doc["version"] = version

        # Add description if available
        description = info.get("description")
        if description is not None:
            if not isinstance(description, str):
                raise ODCSGenerationError(
                    message=f"HubContract 'info.description' must be a string, got {type(description).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": "/info/description",
                        "expected": "str",
                        "actual": type(description).__name__,
                    },
                )
            odcs_doc["description"] = description

        # Map schema section if available
        schema = hub_contract.get("schema")
        if schema is not None:
            if not isinstance(schema, dict):
                raise ODCSGenerationError(
                    message=f"HubContract 'schema' must be a dictionary, got {type(schema).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": "/schema",
                        "expected": "dict",
                        "actual": type(schema).__name__,
                    },
                )
            odcs_doc["schema"] = schema

        logger.debug(
            "odcs_generated_from_hubcontract",
            contract_id=contract_id,
            name=name,
            target_version=target_version,
        )

        return odcs_doc

    except (ODCSGenerationError, ODCSExportError):
        # Re-raise ODCS errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "odcs_generation_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSGenerationError(
            message=f"Unexpected error generating ODCS document: {str(e)}",
            error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e


def generate_odcs_from_schema(
    inferred_schema: Dict[str, Any],
    contract_id: Optional[str] = None,
    contract_name: Optional[str] = None,
    contract_description: Optional[str] = None,
    contract_version: str = "1.0.0",
    odcs_version: str = "3.0.2"
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
        odcs_version: ODCS version (default: "3.0.2")

    Returns:
        ODCS contract as dictionary

    Raises:
        ODCSGenerationError: If inferred_schema is invalid or missing required fields
    """
    try:
        if not isinstance(inferred_schema, dict):
            raise ODCSGenerationError(
                message=f"inferred_schema must be a dictionary, got {type(inferred_schema).__name__}",
                error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                context={
                    "field_path": "/",
                    "expected": "dict",
                    "actual": type(inferred_schema).__name__,
                },
            )

        fields = inferred_schema.get("fields", [])
        if not fields or not isinstance(fields, list):
            raise ODCSGenerationError(
                message="inferred_schema must have a 'fields' list with at least one field",
                error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                context={
                    "field_path": "/fields",
                    "expected": "list (non-empty)",
                    "actual": type(fields).__name__ if fields is not None else None,
                },
            )

        # Generate contract ID if not provided
        if not contract_id:
            contract_id = f"generated-{uuid.uuid4().hex[:8]}"

        # Generate contract name if not provided
        if not contract_name:
            contract_name = "Generated Contract from Data"

        # Build ODCS contract
        # Normalize odcs_version format (remove 'v' prefix if present)
        normalized_odcs_version = odcs_version
        if normalized_odcs_version.startswith('v') or normalized_odcs_version.startswith('V'):
            normalized_odcs_version = normalized_odcs_version[1:]

        odcs_contract = {
            "apiVersion": f"odcs.io/v{normalized_odcs_version}",
            "kind": "DataContract",
            "id": contract_id,
            "name": contract_name,
            "version": contract_version
        }

        # Add description if provided
        if contract_description:
            if not isinstance(contract_description, str):
                raise ODCSGenerationError(
                    message=f"contract_description must be a string, got {type(contract_description).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": "/description",
                        "expected": "str",
                        "actual": type(contract_description).__name__,
                    },
                )
            odcs_contract["description"] = contract_description

        # Build schema section
        schema_fields = []
        primary_key = []
        unique_constraints = []
        indexes = []

        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                raise ODCSGenerationError(
                    message=f"inferred_schema.fields[{i}] must be a dictionary, got {type(field).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": f"/fields/{i}",
                        "expected": "dict",
                        "actual": type(field).__name__,
                    },
                )

            field_name = field.get("name")
            if not field_name:
                raise ODCSGenerationError(
                    message=f"inferred_schema.fields[{i}].name is required",
                    error_code=ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    context={
                        "field_path": f"/fields/{i}/name",
                        "expected": "str (non-empty)",
                        "actual": None,
                    },
                )

            if not isinstance(field_name, str):
                raise ODCSGenerationError(
                    message=f"inferred_schema.fields[{i}].name must be a string, got {type(field_name).__name__}",
                    error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
                    context={
                        "field_path": f"/fields/{i}/name",
                        "expected": "str",
                        "actual": type(field_name).__name__,
                    },
                )

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
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_from": "inferred_schema",
            "row_count_estimated": inferred_schema.get("row_count_estimated")
        }

        logger.info(
            "odcs_contract_generated_from_schema",
            contract_id=contract_id,
            fields_count=len(schema_fields),
            primary_key=str(primary_key),
            unique_constraints_count=len(unique_constraints),
            indexes_count=len(indexes)
        )

        return odcs_contract

    except (ODCSGenerationError, ODCSExportError):
        # Re-raise ODCS errors as-is
        raise
    except Exception as e:
        # Wrap unexpected errors
        logger.error(
            "odcs_generation_from_schema_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise ODCSGenerationError(
            message=f"Unexpected error generating ODCS from schema: {str(e)}",
            error_code=ODCSGenerationError.ERROR_CODE_GENERATION_FAILED,
            context={
                "field_path": "/",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            cause=e,
        ) from e

