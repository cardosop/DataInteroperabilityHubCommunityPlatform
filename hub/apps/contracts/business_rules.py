"""
ODPS Business Rules

Business rules for validating ODPS (Open Data Product Standard) contracts.
Provides comprehensive validation for ODPS structure, version, and linking rules.

This module implements business rules that enforce:
- ODPS document structure requirements
- ODPS version compatibility
- ODPS-ODCS linking rules
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.odps_version_detection import detect_odps_version
from hub.apps.contracts.linking_validation import (
    validate_linking,
    validate_odps_to_odcs_link as _validate_odps_to_odcs_link,
    validate_no_circular_reference,
    validate_referential_integrity as _validate_referential_integrity,
    LinkingValidationError
)
import logging

logger = logging.getLogger(__name__)

# Supported ODPS versions (from input validator and schema availability)
SUPPORTED_ODPS_VERSIONS = ["4.2", "4.1", "4.0", "3.x", "2.x", "1.x"]


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def __init__(self, is_valid: bool = True, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []


class ODPSBusinessRules:
    """
    Business rules for ODPS (Open Data Product Standard) validation.

    Provides methods for validating:
    - ODPS document structure
    - ODPS version compatibility
    - ODPS-ODCS linking rules
    """

    @staticmethod
    def validate_odps_structure(
        odps_doc: Dict[str, Any],
        strict: bool = False
    ) -> ValidationResult:
        """
        Validate ODPS document structure.

        Validates that the ODPS document has the required structure:
        - Top-level: schema (or version), product
        - Product: details (at least one language), dataSchema
        - Optional: product.contract, product.marketplace

        Args:
            odps_doc: ODPS document dictionary
            strict: If True, enforces stricter validation (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSBusinessRules()
            >>> result = rules.validate_odps_structure(odps_doc)
            >>> if not result.is_valid:
            ...     print(f"Validation failed: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(odps_doc, dict):
            errors.append("ODPS document must be a dictionary/object")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate top-level structure
        # Schema or version must be present
        has_schema = "schema" in odps_doc and odps_doc["schema"]
        has_version = "version" in odps_doc and odps_doc["version"]

        if not has_schema and not has_version:
            errors.append("ODPS document must have either 'schema' or 'version' field")

        # Validate schema URL format if present
        if has_schema:
            schema = odps_doc["schema"]
            if not isinstance(schema, str):
                errors.append("ODPS 'schema' field must be a string (URL)")
            elif not schema.startswith("http"):
                warnings.append(f"ODPS 'schema' field should be a valid URL, got: {schema}")

        # Product is required
        if "product" not in odps_doc:
            errors.append("ODPS document must have 'product' field")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        product = odps_doc["product"]
        if not isinstance(product, dict):
            errors.append("ODPS 'product' field must be an object")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate product.details (required, at least one language)
        if "details" not in product:
            errors.append("ODPS 'product.details' field is required")
        else:
            details = product["details"]
            if not isinstance(details, dict):
                errors.append("ODPS 'product.details' must be an object with language keys")
            elif len(details) == 0:
                errors.append("ODPS 'product.details' must have at least one language entry")
            else:
                # Validate each language entry
                for lang_code, lang_details in details.items():
                    if not isinstance(lang_details, dict):
                        errors.append(f"ODPS 'product.details.{lang_code}' must be an object")
                        continue

                    # Validate required fields in language details
                    if "productID" not in lang_details:
                        errors.append(f"ODPS 'product.details.{lang_code}.productID' is required")
                    if "name" not in lang_details:
                        errors.append(f"ODPS 'product.details.{lang_code}.name' is required")

        # Validate product.dataSchema (required)
        if "dataSchema" not in product:
            errors.append("ODPS 'product.dataSchema' field is required")
        else:
            data_schema = product["dataSchema"]
            if not isinstance(data_schema, dict):
                errors.append("ODPS 'product.dataSchema' must be an object")
            else:
                # Validate dataSchema.fields (required)
                if "fields" not in data_schema:
                    errors.append("ODPS 'product.dataSchema.fields' is required")
                else:
                    fields = data_schema["fields"]
                    if not isinstance(fields, list):
                        errors.append("ODPS 'product.dataSchema.fields' must be an array")
                    elif len(fields) == 0:
                        warnings.append("ODPS 'product.dataSchema.fields' is empty")
                    else:
                        # Validate each field
                        for i, field in enumerate(fields):
                            if not isinstance(field, dict):
                                errors.append(f"ODPS 'product.dataSchema.fields[{i}]' must be an object")
                                continue

                            if "name" not in field:
                                errors.append(f"ODPS 'product.dataSchema.fields[{i}].name' is required")
                            if "type" not in field:
                                errors.append(f"ODPS 'product.dataSchema.fields[{i}].type' is required")

        # Validate product.contract (optional, but if present must be valid)
        if "contract" in product:
            contract = product["contract"]
            if not isinstance(contract, dict):
                errors.append("ODPS 'product.contract' must be an object")
            else:
                # Contract should have spec, $ref, or contractURL
                has_spec = "spec" in contract
                has_ref = "$ref" in contract
                has_url = "contractURL" in contract

                if not (has_spec or has_ref or has_url):
                    errors.append("ODPS 'product.contract' must have 'spec', '$ref', or 'contractURL'")

        # Validate product.marketplace (optional, but if present must be valid)
        if "marketplace" in product:
            marketplace = product["marketplace"]
            if not isinstance(marketplace, dict):
                errors.append("ODPS 'product.marketplace' must be an object")
            else:
                # Validate marketplace structure if strict mode
                if strict:
                    # In strict mode, validate marketplace fields
                    if "pricingPlans" in marketplace:
                        pricing_plans = marketplace["pricingPlans"]
                        if not isinstance(pricing_plans, list):
                            errors.append("ODPS 'product.marketplace.pricingPlans' must be an array")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_odps_version(
        odps_doc: Dict[str, Any],
        required_version: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate ODPS version.

        Validates that:
        1. ODPS version can be detected from the document
        2. ODPS version is supported
        3. If required_version is provided, matches the detected version

        Args:
            odps_doc: ODPS document dictionary
            required_version: Optional required version (e.g., "4.1")

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSBusinessRules()
            >>> result = rules.validate_odps_version(odps_doc, required_version="4.1")
            >>> if not result.is_valid:
            ...     print(f"Version validation failed: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(odps_doc, dict):
            errors.append("ODPS document must be a dictionary/object")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Detect version
        try:
            detected_version = detect_odps_version(odps_doc)
        except Exception as e:
            errors.append(f"Failed to detect ODPS version: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        if detected_version == "unknown":
            errors.append("ODPS version could not be detected. Ensure 'schema' or 'version' field is present")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check if version is supported
        if detected_version not in SUPPORTED_ODPS_VERSIONS:
            # Check if it's a normalized version (e.g., "3.x" covers "3.9")
            major_version = detected_version.split(".")[0] if "." in detected_version else None
            is_supported = False

            if major_version:
                # Check if any supported version matches the major version
                for supported in SUPPORTED_ODPS_VERSIONS:
                    if supported.startswith(f"{major_version}.") or supported == f"{major_version}.x":
                        is_supported = True
                        break

                # Also check if detected version is a minor version of a supported major
                # (e.g., "3.9" should be supported if "3.x" is supported)
                if not is_supported and major_version.isdigit():
                    for supported in SUPPORTED_ODPS_VERSIONS:
                        if supported == f"{major_version}.x":
                            is_supported = True
                            break

            if not is_supported:
                errors.append(
                    f"Unsupported ODPS version '{detected_version}'. "
                    f"Supported versions: {', '.join(SUPPORTED_ODPS_VERSIONS)}"
                )
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check if required version matches
        if required_version:
            if detected_version != required_version:
                # Check if versions are compatible (e.g., "4.1" vs "4.0")
                # For now, require exact match
                errors.append(
                    f"ODPS version mismatch: detected '{detected_version}', required '{required_version}'"
                )
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check if version is deprecated
        if detected_version in ["1.x", "2.x", "3.x"]:
            warnings.append(
                f"ODPS version '{detected_version}' is deprecated. "
                "Consider upgrading to version 4.1 or 4.0"
            )

        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_odps_linking(
        odps_contract_id: str,
        odcs_contract_id: str,
        tenant_id: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate ODPS-ODCS linking rules.

        Validates that:
        1. Both contracts exist
        2. Contracts are of correct types (ODPS and ODCS)
        3. Contracts are compatible for linking
        4. No circular references would be created
        5. Contracts belong to the same tenant (if tenant_id provided)

        Args:
            odps_contract_id: ODPS contract UUID
            odcs_contract_id: ODCS contract UUID
            tenant_id: Optional tenant ID for ownership validation

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If validation fails (wrapped from LinkingValidationError)

        Example:
            >>> rules = ODPSBusinessRules()
            >>> result = rules.validate_odps_linking(
            ...     odps_contract_id="...",
            ...     odcs_contract_id="...",
            ...     tenant_id="..."
            ... )
            >>> if not result.is_valid:
            ...     print(f"Linking validation failed: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract IDs
        if not odps_contract_id:
            errors.append("ODPS contract ID is required")
        if not odcs_contract_id:
            errors.append("ODCS contract ID is required")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Use existing linking validation
        try:
            odps_contract, odcs_contract = validate_linking(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id,
                tenant_id=tenant_id
            )

            # Additional business rule validations
            # Check if contracts are already linked (idempotent)
            if odps_contract.hub_contract_json:
                extensions = odps_contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                existing_odcs_link = x_odps.get("odcs_link")

                if existing_odcs_link and str(existing_odcs_link) == str(odcs_contract_id):
                    warnings.append("Contracts are already linked (idempotent operation)")

            # Validate tenant ownership if tenant_id provided
            if tenant_id:
                if str(odps_contract.tenant_id) != str(tenant_id):
                    errors.append(
                        f"ODPS contract {odps_contract_id} does not belong to tenant {tenant_id}"
                    )
                if str(odcs_contract.tenant_id) != str(tenant_id):
                    errors.append(
                        f"ODCS contract {odcs_contract_id} does not belong to tenant {tenant_id}"
                    )

            if errors:
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings
            )

        except LinkingValidationError as e:
            # Convert LinkingValidationError to ValidationResult
            errors.append(e.message)
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error during ODPS linking validation: {e}",
                exc_info=True
            )
            errors.append(f"Unexpected error during linking validation: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

    @staticmethod
    def validate_odps_contract(
        contract: Contract,
        strict: bool = False
    ) -> ValidationResult:
        """
        Comprehensive validation of an ODPS contract.

        Validates:
        1. Contract is of type ODPS
        2. Contract has hub_contract_json
        3. ODPS structure is valid
        4. ODPS version is valid

        Args:
            contract: Contract instance
            strict: If True, enforces stricter validation (default: False)

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract type
        if contract.original_spec_type != OriginalSpecType.ODPS:
            errors.append(
                f"Contract {contract.id} is not an ODPS contract "
                f"(type: {contract.original_spec_type})"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate hub_contract_json exists
        if not contract.hub_contract_json:
            errors.append(f"ODPS contract {contract.id} has no hub_contract_json")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Reconstruct ODPS document from original_raw or hub_contract_json
        odps_doc = None

        # Try to get from original_raw first
        if contract.original_raw:
            try:
                import json
                odps_doc = json.loads(contract.original_raw)
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback to reconstructing from hub_contract_json
        if not odps_doc and contract.hub_contract_json:
            # For validation purposes, we can use a minimal ODPS structure
            # This is a simplified reconstruction for validation
            hub_contract = contract.hub_contract_json
            odps_doc = {
                "schema": f"https://opendataproducts.org/schema/v{contract.original_spec_version or '4.1'}",
                "version": contract.original_spec_version or "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": hub_contract.get("id", "unknown"),
                            "name": hub_contract.get("info", {}).get("name", "Unknown"),
                        }
                    },
                    "dataSchema": hub_contract.get("schema", {})
                }
            }

        if not odps_doc:
            errors.append(f"ODPS contract {contract.id} has no valid ODPS document data")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate structure
        structure_result = ODPSBusinessRules.validate_odps_structure(
            odps_doc=odps_doc,
            strict=strict
        )
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)

        # Validate version
        version_result = ODPSBusinessRules.validate_odps_version(
            odps_doc=odps_doc,
            required_version=contract.original_spec_version
        )
        errors.extend(version_result.errors)
        warnings.extend(version_result.warnings)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )



class ODPSLinkingRules:
    """
    Business rules for ODPS-ODCS linking validation.

    Provides methods for validating:
    - ODPS to ODCS link existence and validity
    - Circular reference detection
    - Referential integrity (bidirectional consistency)

    This class wraps the existing linking validation functions from
    `linking_validation.py` and provides a business rules interface
    that returns ValidationResult objects instead of raising exceptions.
    """

    @staticmethod
    def validate_odps_to_odcs_link(
        odps_contract: Contract
    ) -> ValidationResult:
        """
        Validate ODPS → ODCS link.

        Validates that if an ODPS contract has an odcs_link,
        the linked ODCS contract exists and is valid.

        Args:
            odps_contract: ODPS contract instance

        Returns:
            ValidationResult with validation status, errors, and warnings.
            If link exists and is valid, the linked ODCS contract is accessible
            through the validation context.

        Example:
            >>> rules = ODPSLinkingRules()
            >>> result = rules.validate_odps_to_odcs_link(odps_contract)
            >>> if result.is_valid:
            ...     print("ODPS → ODCS link is valid")
            >>> elif result.errors:
            ...     print(f"Link validation failed: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract type
        if odps_contract.original_spec_type != OriginalSpecType.ODPS:
            errors.append(
                f"Contract {odps_contract.id} is not an ODPS contract "
                f"(type: {odps_contract.original_spec_type})"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Use existing validation function
        try:
            linked_contract = _validate_odps_to_odcs_link(odps_contract)

            if linked_contract is None:
                # No link exists - this is valid (not an error)
                warnings.append("ODPS contract has no ODCS link")

            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings
            )

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context:
                # Add context details to errors for better debugging
                if "description" in e.context:
                    errors.append(e.context["description"])

            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        except Exception as e:
            logger.error(
                f"Unexpected error validating ODPS → ODCS link: {e}",
                exc_info=True
            )
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

    @staticmethod
    def validate_circular_references(
        odps_contract_id: str,
        odcs_contract_id: str
    ) -> ValidationResult:
        """
        Validate that linking would not create circular references.

        Uses depth-first search to detect if linking the contracts
        would create a circular reference chain.

        Args:
            odps_contract_id: ODPS contract UUID
            odcs_contract_id: ODCS contract UUID

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSLinkingRules()
            >>> result = rules.validate_circular_references(
            ...     odps_contract_id="...",
            ...     odcs_contract_id="..."
            ... )
            >>> if not result.is_valid:
            ...     print(f"Circular reference detected: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract IDs
        if not odps_contract_id:
            errors.append("ODPS contract ID is required")
        if not odcs_contract_id:
            errors.append("ODCS contract ID is required")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Use existing validation function
        try:
            validate_no_circular_reference(
                odps_contract_id=odps_contract_id,
                odcs_contract_id=odcs_contract_id
            )

            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings
            )

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context:
                # Add context details to errors for better debugging
                if "description" in e.context:
                    errors.append(e.context["description"])

            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        except Exception as e:
            logger.error(
                f"Unexpected error validating circular references: {e}",
                exc_info=True
            )
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

    @staticmethod
    def validate_referential_integrity(
        contract: Contract
    ) -> ValidationResult:
        """
        Validate referential integrity for contract links.

        Ensures that if contract A links to contract B,
        then contract B links back to contract A (bidirectional consistency).

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSLinkingRules()
            >>> result = rules.validate_referential_integrity(contract)
            >>> if not result.is_valid:
            ...     print(f"Referential integrity violation: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract has hub_contract_json
        if not contract.hub_contract_json:
            warnings.append(
                f"Contract {contract.id} has no hub_contract_json, "
                "skipping referential integrity check"
            )
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        # Use existing validation function
        try:
            _validate_referential_integrity(contract)

            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings
            )

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context and "errors" in e.context:
                # Add detailed errors from context
                errors.extend(e.context["errors"])

            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        except Exception as e:
            logger.error(
                f"Unexpected error validating referential integrity: {e}",
                exc_info=True
            )
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

    @staticmethod
    def validate_all_linking_rules(
        odps_contract: Contract,
        odcs_contract: Optional[Contract] = None
    ) -> ValidationResult:
        """
        Comprehensive validation of all linking rules for an ODPS contract.

        Validates:
        1. ODPS → ODCS link (if exists)
        2. Circular references (if ODCS contract provided)
        3. Referential integrity

        Args:
            odps_contract: ODPS contract instance
            odcs_contract: Optional ODCS contract instance (for circular reference check)

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSLinkingRules()
            >>> result = rules.validate_all_linking_rules(odps_contract, odcs_contract)
            >>> if not result.is_valid:
            ...     print(f"Linking validation failed: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate ODPS → ODCS link
        link_result = ODPSLinkingRules.validate_odps_to_odcs_link(odps_contract)
        errors.extend(link_result.errors)
        warnings.extend(link_result.warnings)

        # Validate circular references if ODCS contract provided
        if odcs_contract:
            circular_result = ODPSLinkingRules.validate_circular_references(
                odps_contract_id=str(odps_contract.id),
                odcs_contract_id=str(odcs_contract.id)
            )
            errors.extend(circular_result.errors)
            warnings.extend(circular_result.warnings)

        # Validate referential integrity
        integrity_result = ODPSLinkingRules.validate_referential_integrity(odps_contract)
        errors.extend(integrity_result.errors)
        warnings.extend(integrity_result.warnings)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )


class ODPSExportRules:
    """
    Business rules for ODPS export validation.

    Provides methods for validating:
    - Export format (JSON/YAML)
    - Data completeness (required fields present)
    - Fidelity (round-trip consistency, no data loss)

    This class ensures that ODPS contracts can be exported correctly
    and that exported data maintains fidelity with the original contract.
    """

    @staticmethod
    def validate_export_format(
        output_format: str
    ) -> ValidationResult:
        """
        Validate export format.

        Validates that the output format is supported (JSON or YAML).

        Args:
            output_format: Output format string ("json" or "yaml")

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSExportRules()
            >>> result = rules.validate_export_format("json")
            >>> if result.is_valid:
            ...     print("Format is valid")
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not output_format:
            errors.append("Output format is required")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        output_format_lower = output_format.lower()

        if output_format_lower not in ['json', 'yaml']:
            errors.append(
                f"Invalid output format: {output_format}. "
                "Must be 'json' or 'yaml'"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check YAML availability if YAML format requested
        if output_format_lower == 'yaml':
            try:
                import yaml
            except ImportError:
                errors.append(
                    "YAML format requested but PyYAML is not installed. "
                    "Install it with: pip install pyyaml"
                )
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_data_completeness(
        contract: Contract
    ) -> ValidationResult:
        """
        Validate data completeness for export.

        Ensures that the contract has all required data for ODPS export:
        - Contract has hub_contract_json
        - hub_contract_json has required sections (info)
        - Required fields are present and valid (info.name, id)

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSExportRules()
            >>> result = rules.validate_data_completeness(contract)
            >>> if not result.is_valid:
            ...     print(f"Data incomplete: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate contract has hub_contract_json
        if not contract.hub_contract_json:
            errors.append(
                f"Contract {contract.id} has no hub_contract_json. "
                "Cannot export as ODPS format."
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        hub_contract = contract.hub_contract_json

        # Validate hub_contract is a dictionary
        if not isinstance(hub_contract, dict):
            errors.append(
                f"Contract {contract.id} hub_contract_json must be a dictionary, "
                f"got {type(hub_contract).__name__}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate required 'info' section
        if "info" not in hub_contract:
            errors.append(
                f"Contract {contract.id} hub_contract_json missing required 'info' section"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        info = hub_contract.get("info")
        if not isinstance(info, dict):
            errors.append(
                f"Contract {contract.id} hub_contract_json 'info' must be a dictionary, "
                f"got {type(info).__name__}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate required 'info.name' field
        if "name" not in info:
            errors.append(
                f"Contract {contract.id} hub_contract_json 'info.name' is required"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        name = info.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(
                f"Contract {contract.id} hub_contract_json 'info.name' must be a "
                f"non-empty string, got {type(name).__name__ if name is not None else None}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate 'id' field (should be present, but warn if missing)
        contract_id = hub_contract.get("id")
        if not contract_id:
            warnings.append(
                f"Contract {contract.id} hub_contract_json missing 'id' field. "
                "Product ID will be empty in exported ODPS."
            )
        elif not isinstance(contract_id, str):
            warnings.append(
                f"Contract {contract.id} hub_contract_json 'id' should be a string, "
                f"got {type(contract_id).__name__}. May cause export issues."
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_fidelity(
        contract: Contract,
        exported_odps: Dict[str, Any],
        output_format: str = "json"
    ) -> ValidationResult:
        """
        Validate export fidelity (round-trip consistency).

        Ensures that exported ODPS maintains fidelity with the original contract:
        - Key fields are preserved (productID, name, etc.)
        - No critical data loss during export
        - Schema version is valid

        Args:
            contract: Original contract instance
            exported_odps: Exported ODPS document as dictionary
            output_format: Output format used ("json" or "yaml")

        Returns:
            ValidationResult with validation status, errors, and warnings

        Example:
            >>> rules = ODPSExportRules()
            >>> result = rules.validate_fidelity(contract, exported_odps)
            >>> if not result.is_valid:
            ...     print(f"Fidelity issues: {result.errors}")
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate exported_odps is a dictionary
        if not isinstance(exported_odps, dict):
            errors.append(
                f"Exported ODPS must be a dictionary, got {type(exported_odps).__name__}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate schema field exists
        if "schema" not in exported_odps:
            errors.append("Exported ODPS missing required 'schema' field")
        else:
            schema = exported_odps.get("schema")
            if not isinstance(schema, str) or not schema.strip():
                errors.append(
                    f"Exported ODPS 'schema' must be a non-empty string, "
                    f"got {type(schema).__name__ if schema is not None else None}"
                )

        # Validate product section exists
        if "product" not in exported_odps:
            errors.append("Exported ODPS missing required 'product' section")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        product = exported_odps.get("product")
        if not isinstance(product, dict):
            errors.append(
                f"Exported ODPS 'product' must be a dictionary, "
                f"got {type(product).__name__}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate product.details exists
        if "details" not in product:
            errors.append("Exported ODPS 'product.details' is required")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        details = product.get("details")
        if not isinstance(details, dict):
            errors.append(
                f"Exported ODPS 'product.details' must be a dictionary, "
                f"got {type(details).__name__}"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check if we have at least one language in details
        if not details:
            errors.append("Exported ODPS 'product.details' must contain at least one language")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate key fields are preserved from original contract
        hub_contract = contract.hub_contract_json
        if hub_contract:
            # Check productID preservation
            original_id = hub_contract.get("id", "")
            if original_id:
                # Find productID in exported ODPS (check first available language)
                first_lang = next(iter(details.keys()), None)
                if first_lang:
                    lang_details = details.get(first_lang, {})
                    exported_product_id = lang_details.get("productID", "")

                    if exported_product_id != original_id:
                        warnings.append(
                            f"Product ID mismatch: original '{original_id}' vs "
                            f"exported '{exported_product_id}'"
                        )

            # Check name preservation
            original_name = hub_contract.get("info", {}).get("name", "")
            if original_name:
                first_lang = next(iter(details.keys()), None)
                if first_lang:
                    lang_details = details.get(first_lang, {})
                    exported_name = lang_details.get("name", "")

                    if exported_name != original_name:
                        warnings.append(
                            f"Product name mismatch: original '{original_name}' vs "
                            f"exported '{exported_name}'"
                        )

        # Validate version field if present
        if "version" in exported_odps:
            version = exported_odps.get("version")
            if not isinstance(version, str) or not version.strip():
                warnings.append(
                    f"Exported ODPS 'version' should be a non-empty string, "
                    f"got {type(version).__name__ if version is not None else None}"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
