"""
ODPS Business Rules

Business rules for validating ODPS (Open Data Product Standard) contracts.
Provides comprehensive validation for ODPS structure, version, and linking rules.

This module implements business rules that enforce:
- ODPS document structure requirements
- ODPS version compatibility
- ODPS-ODCS linking rules

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hub.apps.contracts.linking_validation import (
    LinkingValidationError,
    validate_linking,
    validate_no_circular_reference,
)
from hub.apps.contracts.linking_validation import (
    validate_odps_to_odcs_link as _validate_odps_to_odcs_link,
)
from hub.apps.contracts.linking_validation import (
    validate_referential_integrity as _validate_referential_integrity,
)
from hub.apps.contracts.models import Contract, OriginalSpecType, ContractStatus, OriginalFormat, NormalizationStatus
from hub.apps.contracts.normalization import get_normalizer, parse_contract
from hub.apps.contracts.odps_version_detection import detect_odps_version
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import User

import structlog

logger = structlog.get_logger(__name__)

# Supported ODPS versions (from input validator and schema availability)
SUPPORTED_ODPS_VERSIONS = ["4.2", "4.1", "4.0", "3.x", "2.x", "1.x"]


@dataclass
class ODPSRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for ODPS business rules.

    Adds ODPS-specific context:
    - contract: The contract being validated
    - odps_doc: Optional ODPS document dictionary
    - odcs_contract: Optional linked ODCS contract
    """

    contract: Optional[Contract] = None
    odps_doc: Optional[Dict[str, Any]] = None
    odcs_contract: Optional[Contract] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update(
            {
                "contract_id": str(self.contract.id) if self.contract else None,
                "contract_type": self.contract.original_spec_type if self.contract else None,
                "odcs_contract_id": str(self.odcs_contract.id) if self.odcs_contract else None,
                "has_odps_doc": self.odps_doc is not None,
            }
        )
        return base_dict


@register_rule(
    rule_name="odps_validation",
    description="Validates ODPS document structure, version compatibility, and ODPS-ODCS linking rules",
    tags=["odps", "contracts", "validation"],
    priority=10,
)
class ODPSBusinessRules(BusinessRules):
    """
    Business rules for ODPS (Open Data Product Standard) validation.

    Extends BusinessRules base class with ODPS-specific validation:
    - ODPS document structure validation
    - ODPS version compatibility validation
    - ODPS-ODCS linking rules validation
    - Comprehensive ODPS contract validation

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ODPSBusinessRules"

    def validate(
        self, context: Optional[RuleExecutionContext] = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all ODPS validation checks.
        It can be called with an ODPSRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        contract and odps_doc from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - contract: Contract instance (optional)
                - odps_doc: ODPS document dictionary (optional)
                - validation_type: Optional validation type filter
                    ('structure', 'version', 'linking', 'contract', 'all')
                - strict: If True, enforces stricter validation (default: False)
                - required_version: Optional required version for version validation

        Returns:
            ValidationResult with validation status and details
        """
        # Extract contract and odps_doc from context or kwargs
        if isinstance(context, ODPSRuleExecutionContext):
            contract = context.contract
            odps_doc = context.odps_doc
        else:
            # Try to get from kwargs first
            contract = kwargs.get("contract")
            odps_doc = kwargs.get("odps_doc")

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, "metadata") and isinstance(context.metadata, dict):
                contract = contract or context.metadata.get("contract")
                odps_doc = odps_doc or context.metadata.get("odps_doc")

            # Also check context.resource
            if not contract and context and hasattr(context, "resource"):
                if isinstance(context.resource, Contract):
                    contract = context.resource

        # Determine what to validate
        validation_type = kwargs.get("validation_type", "all")
        strict = kwargs.get("strict", False)
        required_version = kwargs.get("required_version")

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate structure if odps_doc provided
        if odps_doc and validation_type in ("structure", "all"):
            structure_result = self.validate_odps_structure(odps_doc, strict=strict)
            result = result.combine(structure_result)
            validated_items.append("structure")

        # Validate version if odps_doc provided
        if odps_doc and validation_type in ("version", "all"):
            version_result = self.validate_odps_version(odps_doc, required_version=required_version)
            result = result.combine(version_result)
            validated_items.append("version")

        # Validate linking if contract provided
        if contract and validation_type in ("linking", "all"):
            linking_result = self._validate_odps_linking_from_contract(contract)
            result = result.combine(linking_result)
            validated_items.append("linking")

        # Validate contract comprehensively if contract provided
        if contract and validation_type in ("contract", "all"):
            contract_result = self.validate_odps_contract(contract, strict=strict)
            result = result.combine(contract_result)
            validated_items.append("contract")

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=["At least one of contract or odps_doc must be provided"],
                details={"validation_type": validation_type},
            )

        # Add validation summary to details
        result.details["validated_items"] = validated_items
        result.details["validation_type"] = validation_type

        return result

    def _validate_odps_linking_from_contract(self, contract: Contract) -> ValidationResult:
        """
        Validate ODPS linking from a contract instance.

        This is a helper method that extracts linking information from a contract
        and calls the main linking validation method.

        Args:
            contract: Contract instance

        Returns:
            ValidationResult with validation status
        """
        if contract.original_spec_type != OriginalSpecType.ODPS:
            return ValidationResult(
                is_valid=True,
                warnings=[
                    f"Contract {contract.id} is not an ODPS contract, skipping linking validation"
                ],
            )

        # Extract odcs_link from contract if present
        if not contract.hub_contract_json:
            return ValidationResult(
                is_valid=True,
                warnings=[
                    f"Contract {contract.id} has no hub_contract_json, skipping linking validation"
                ],
            )

        extensions = contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        odcs_link = x_odps.get("odcs_link")

        if not odcs_link:
            return ValidationResult(is_valid=True, warnings=["ODPS contract has no ODCS link"])

        # Use the linking validation method
        return self.validate_odps_linking(
            odps_contract_id=str(contract.id),
            odcs_contract_id=str(odcs_link),
            tenant_id=str(contract.tenant_id) if contract.tenant_id else None,
        )

    def validate_odps_structure(
        self, odps_doc: Dict[str, Any], strict: bool = False
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
                                errors.append(
                                    f"ODPS 'product.dataSchema.fields[{i}]' must be an object"
                                )
                                continue

                            if "name" not in field:
                                errors.append(
                                    f"ODPS 'product.dataSchema.fields[{i}].name' is required"
                                )
                            if "type" not in field:
                                errors.append(
                                    f"ODPS 'product.dataSchema.fields[{i}].type' is required"
                                )

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
                    errors.append(
                        "ODPS 'product.contract' must have 'spec', '$ref', or 'contractURL'"
                    )

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
                            errors.append(
                                "ODPS 'product.marketplace.pricingPlans' must be an array"
                            )

        is_valid = len(errors) == 0

        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    def validate_odps_version(
        self, odps_doc: Dict[str, Any], required_version: Optional[str] = None
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
            errors.append(
                "ODPS version could not be detected. Ensure 'schema' or 'version' field is present"
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check if version is supported
        if detected_version not in SUPPORTED_ODPS_VERSIONS:
            # Check if it's a normalized version (e.g., "3.x" covers "3.9")
            major_version = detected_version.split(".")[0] if "." in detected_version else None
            is_supported = False

            if major_version:
                # Check if any supported version matches the major version
                for supported in SUPPORTED_ODPS_VERSIONS:
                    if (
                        supported.startswith(f"{major_version}.")
                        or supported == f"{major_version}.x"
                    ):
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

        return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

    def validate_odps_linking(
        self, odps_contract_id: str, odcs_contract_id: str, tenant_id: Optional[str] = None
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
                tenant_id=tenant_id,
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

            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        except LinkingValidationError as e:
            # Convert LinkingValidationError to ValidationResult
            errors.append(e.message)
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error during ODPS linking validation: {e}", exc_info=True)
            errors.append(f"Unexpected error during linking validation: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    def validate_odps_contract(self, contract: Contract, strict: bool = False) -> ValidationResult:
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
                    "dataSchema": hub_contract.get("schema", {}),
                },
            }

        if not odps_doc:
            errors.append(f"ODPS contract {contract.id} has no valid ODPS document data")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate structure
        structure_result = self.validate_odps_structure(odps_doc=odps_doc, strict=strict)
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)

        # Validate version
        version_result = self.validate_odps_version(
            odps_doc=odps_doc, required_version=contract.original_spec_version
        )
        errors.extend(version_result.errors)
        warnings.extend(version_result.warnings)

        is_valid = len(errors) == 0

        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


@register_rule(
    rule_name="odps_linking_validation",
    description="Validates ODPS-ODCS linking rules including link existence, circular references, and referential integrity",
    tags=["odps", "linking", "validation"],
    priority=10,
)
class ODPSLinkingRules(BusinessRules):
    """
    Business rules for ODPS-ODCS linking validation.

    Extends BusinessRules base class with ODPS-ODCS linking validation:
    - ODPS to ODCS link existence and validity
    - Circular reference detection
    - Referential integrity (bidirectional consistency)

    This class wraps the existing linking validation functions from
    `linking_validation.py` and provides a business rules interface
    that returns ValidationResult objects instead of raising exceptions.

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ODPSLinkingRules"

    def validate(
        self, context: Optional[RuleExecutionContext] = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all ODPS linking validation checks.
        It can be called with an ODPSRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        contract and odcs_contract from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - odps_contract: ODPS contract instance (required)
                - odcs_contract: Optional ODCS contract instance
                - validation_type: Optional validation type filter
                    ('link', 'circular', 'integrity', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract contracts from context or kwargs
        if isinstance(context, ODPSRuleExecutionContext):
            odps_contract = context.contract
            odcs_contract = context.odcs_contract
        else:
            # Try to get from kwargs first
            odps_contract = kwargs.get("odps_contract")
            odcs_contract = kwargs.get("odcs_contract")

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, "metadata") and isinstance(context.metadata, dict):
                odps_contract = odps_contract or context.metadata.get("odps_contract")
                odcs_contract = odcs_contract or context.metadata.get("odcs_contract")

            # Also check context.resource
            if not odps_contract and context and hasattr(context, "resource"):
                if isinstance(context.resource, Contract):
                    odps_contract = context.resource

        # Determine what to validate
        validation_type = kwargs.get("validation_type", "all")

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate ODPS contract is provided
        if not odps_contract:
            return ValidationResult(
                is_valid=False,
                errors=["odps_contract is required for linking validation"],
                details={"validation_type": validation_type},
            )

        # Validate ODPS → ODCS link
        if validation_type in ("link", "all"):
            link_result = self.validate_odps_to_odcs_link(odps_contract)
            result = result.combine(link_result)
            validated_items.append("link")

        # Validate circular references if ODCS contract provided
        if odcs_contract and validation_type in ("circular", "all"):
            circular_result = self.validate_circular_references(
                odps_contract_id=str(odps_contract.id), odcs_contract_id=str(odcs_contract.id)
            )
            result = result.combine(circular_result)
            validated_items.append("circular")

        # Validate referential integrity
        if validation_type in ("integrity", "all"):
            integrity_result = self.validate_referential_integrity(odps_contract)
            result = result.combine(integrity_result)
            validated_items.append("integrity")

        # Add validation summary to details
        result.details["validated_items"] = validated_items
        result.details["validation_type"] = validation_type

        return result

    def validate_odps_to_odcs_link(self, odps_contract: Contract) -> ValidationResult:
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

            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context:
                # Add context details to errors for better debugging
                if "description" in e.context:
                    errors.append(e.context["description"])

            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            logger.error(f"Unexpected error validating ODPS → ODCS link: {e}", exc_info=True)
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    def validate_circular_references(
        self, odps_contract_id: str, odcs_contract_id: str
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
                odps_contract_id=odps_contract_id, odcs_contract_id=odcs_contract_id
            )

            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context:
                # Add context details to errors for better debugging
                if "description" in e.context:
                    errors.append(e.context["description"])

            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            logger.error(f"Unexpected error validating circular references: {e}", exc_info=True)
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    def validate_referential_integrity(self, contract: Contract) -> ValidationResult:
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

            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        except LinkingValidationError as e:
            errors.append(e.message)
            if e.context and "errors" in e.context:
                # Add detailed errors from context
                errors.extend(e.context["errors"])

            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            logger.error(f"Unexpected error validating referential integrity: {e}", exc_info=True)
            errors.append(f"Unexpected error during validation: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    def validate_all_linking_rules(
        self, odps_contract: Contract, odcs_contract: Optional[Contract] = None
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
            >>> rules = ODPSLinkingRules(tenant_id="...", user_id="...")
            >>> result = rules.validate_all_linking_rules(odps_contract, odcs_contract)
            >>> if not result.is_valid:
            ...     print(f"Linking validation failed: {result.errors}")
        """
        # Use the main validate method with all validation types
        context = ODPSRuleExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            contract=odps_contract,
            odcs_contract=odcs_contract,
        )
        return self.validate(context, validation_type="all")


@register_rule(
    rule_name="odps_export_validation",
    description="Validates ODPS export format, data completeness, and fidelity (round-trip consistency)",
    tags=["odps", "export", "validation"],
    priority=10,
)
class ODPSExportRules(BusinessRules):
    """
    Business rules for ODPS export validation.

    Extends BusinessRules base class with ODPS export validation:
    - Export format (JSON/YAML) validation
    - Data completeness (required fields present) validation
    - Fidelity (round-trip consistency, no data loss) validation

    This class ensures that ODPS contracts can be exported correctly
    and that exported data maintains fidelity with the original contract.

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ODPSExportRules"

    def validate(
        self, context: Optional[RuleExecutionContext] = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all ODPS export validation checks.
        It can be called with an ODPSRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        contract, exported_odps, and output_format from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - contract: Contract instance (optional, for completeness/fidelity)
                - exported_odps: Exported ODPS document dictionary (optional, for fidelity)
                - output_format: Output format string ("json" or "yaml") (optional, for format)
                - validation_type: Optional validation type filter
                    ('format', 'completeness', 'fidelity', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract contract, exported_odps, and output_format from context or kwargs
        if isinstance(context, ODPSRuleExecutionContext):
            contract = context.contract
            odps_doc = context.odps_doc  # This could be exported_odps
        else:
            # Try to get from kwargs first
            contract = kwargs.get("contract")
            odps_doc = kwargs.get("exported_odps") or kwargs.get("odps_doc")
            output_format = kwargs.get("output_format")

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, "metadata") and isinstance(context.metadata, dict):
                contract = contract or context.metadata.get("contract")
                odps_doc = (
                    odps_doc
                    or context.metadata.get("exported_odps")
                    or context.metadata.get("odps_doc")
                )
                output_format = output_format or context.metadata.get("output_format")

            # Also check context.resource
            if not contract and context and hasattr(context, "resource"):
                if isinstance(context.resource, Contract):
                    contract = context.resource

        # Determine what to validate
        validation_type = kwargs.get("validation_type", "all")

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate export format if output_format provided
        if "output_format" in kwargs or (
            context and hasattr(context, "metadata") and context.metadata.get("output_format")
        ):
            output_format = kwargs.get("output_format") or (
                context.metadata.get("output_format")
                if context and hasattr(context, "metadata")
                else None
            )
            if output_format and validation_type in ("format", "all"):
                format_result = self.validate_export_format(output_format)
                result = result.combine(format_result)
                validated_items.append("format")

        # Validate data completeness if contract provided
        if contract and validation_type in ("completeness", "all"):
            completeness_result = self.validate_data_completeness(contract)
            result = result.combine(completeness_result)
            validated_items.append("completeness")

        # Validate fidelity if contract and exported_odps provided
        if contract and odps_doc and validation_type in ("fidelity", "all"):
            output_format = kwargs.get("output_format", "json")
            fidelity_result = self.validate_fidelity(
                contract, odps_doc, output_format=output_format
            )
            result = result.combine(fidelity_result)
            validated_items.append("fidelity")

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=[
                    "At least one of contract, exported_odps, or output_format must be provided"
                ],
                details={"validation_type": validation_type},
            )

        # Add validation summary to details
        result.details["validated_items"] = validated_items
        result.details["validation_type"] = validation_type

        return result

    def validate_export_format(self, output_format: str) -> ValidationResult:
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

        if output_format_lower not in ["json", "yaml"]:
            errors.append(f"Invalid output format: {output_format}. " "Must be 'json' or 'yaml'")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check YAML availability if YAML format requested
        if output_format_lower == "yaml":
            try:
                import yaml
            except ImportError:
                errors.append(
                    "YAML format requested but PyYAML is not installed. "
                    "Install it with: pip install pyyaml"
                )
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

    def validate_data_completeness(self, contract: Contract) -> ValidationResult:
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
                f"Contract {contract.id} has no hub_contract_json. " "Cannot export as ODPS format."
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
            errors.append(f"Contract {contract.id} hub_contract_json 'info.name' is required")
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

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_fidelity(
        self, contract: Contract, exported_odps: Dict[str, Any], output_format: str = "json"
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
            errors.append(f"Exported ODPS must be a dictionary, got {type(exported_odps).__name__}")
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
                f"Exported ODPS 'product' must be a dictionary, " f"got {type(product).__name__}"
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

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


@register_rule(
    rule_name="contracts_lifecycle_validation",
    description="Validates contract lifecycle operations: creation, update, deletion, and version compatibility validation",
    tags=["contracts", "lifecycle", "validation"],
    priority=10,
)
class ContractsBusinessRules(BusinessRules):
    """
    Business rules for contract lifecycle validation.

    Extends BusinessRules base class with contract lifecycle validation:
    - Contract creation validation (valid contract structure)
    - Contract update validation (can update contract)
    - Contract deletion validation (cannot delete if referenced)
    - Contract version validation (version compatibility)

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ContractsBusinessRules"

    def validate(
        self, context: Optional[RuleExecutionContext] = None, *args, **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates contract lifecycle validation checks.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - contract: Contract instance (optional)
                - operation: Operation type ('create', 'update', 'delete', 'version', 'all')
                - contract_data: Dictionary with contract data for creation/update (optional)

        Returns:
            ValidationResult with validation status and details
        """
        # Extract contract from context or kwargs
        contract = kwargs.get("contract")
        operation = kwargs.get("operation", "all")
        contract_data = kwargs.get("contract_data")

        if context and hasattr(context, "resource"):
            if isinstance(context.resource, Contract):
                contract = contract or context.resource

        # Initialize result
        result = ValidationResult(is_valid=True)
        validated_items = []

        # Validate creation if contract_data provided
        if contract_data and operation in ("create", "all"):
            creation_result = self.validate_contract_creation(contract_data)
            result = result.combine(creation_result)
            validated_items.append("creation")

        # Validate update if contract provided
        if contract and operation in ("update", "all"):
            update_result = self.validate_contract_update(contract, contract_data=contract_data)
            result = result.combine(update_result)
            validated_items.append("update")

        # Validate deletion if contract provided
        if contract and operation in ("delete", "all"):
            deletion_result = self.validate_contract_deletion(contract)
            result = result.combine(deletion_result)
            validated_items.append("deletion")

        # Validate version if contract provided
        if contract and operation in ("version", "all"):
            version_result = self.validate_contract_version(contract)
            result = result.combine(version_result)
            validated_items.append("version")

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=["At least one of contract or contract_data must be provided"],
                details={"operation": operation},
            )

        result.details["validated_items"] = validated_items
        result.details["operation"] = operation

        return result

    def validate_contract_creation(
        self, contract_data: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate contract creation (valid contract structure).

        Validates:
        - Required fields are present (tenant_id, original_raw, original_format, original_spec_type)
        - Contract structure is valid
        - Tenant exists
        - Asset exists (if provided)
        - Version compatibility

        Args:
            contract_data: Dictionary containing contract data for creation

        Returns:
            ValidationResult with validation status and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": "contract_creation",
            "contract_data_provided": contract_data is not None,
        }

        if not contract_data:
            errors.append("Contract data must be provided")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings, details=details)

        if not isinstance(contract_data, dict):
            errors.append(f"Contract data must be a dictionary, got {type(contract_data).__name__}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings, details=details)

        # Validate required fields
        required_fields = ["tenant_id", "original_raw", "original_format", "original_spec_type"]
        missing_fields = []
        for field in required_fields:
            if field not in contract_data:
                missing_fields.append(field)
            elif field == "original_raw" and isinstance(contract_data[field], str) and not contract_data[field].strip():
                # Empty string is treated as missing
                missing_fields.append(field)
            elif not contract_data[field]:
                missing_fields.append(field)

        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            details["missing_fields"] = missing_fields
        else:
            details["has_required_fields"] = True

        # Validate tenant_id exists
        tenant_id = contract_data.get("tenant_id")
        if tenant_id:
            try:
                from hub.apps.tenants.models import Tenant
                tenant = Tenant.objects.get(id=tenant_id)
                details["tenant_exists"] = True
                details["tenant_id"] = str(tenant.id)
            except Tenant.DoesNotExist:
                errors.append(f"Tenant with ID '{tenant_id}' does not exist")
                details["tenant_exists"] = False
            except Exception as e:
                errors.append(f"Error validating tenant: {str(e)}")
                details["tenant_exists"] = False

        # Validate asset_id exists (if provided)
        asset_id = contract_data.get("asset_id")
        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
                details["asset_exists"] = True
                details["asset_id"] = str(asset.id)
            except Asset.DoesNotExist:
                errors.append(f"Asset with ID '{asset_id}' does not exist for tenant '{tenant_id}'")
                details["asset_exists"] = False
            except Exception as e:
                errors.append(f"Error validating asset: {str(e)}")
                details["asset_exists"] = False
        else:
            details["asset_exists"] = None  # Not provided

        # Validate original_format
        original_format = contract_data.get("original_format")
        if original_format:
            valid_formats = [choice[0] for choice in OriginalFormat.choices]
            if original_format not in valid_formats:
                errors.append(
                    f"Invalid original_format '{original_format}'. "
                    f"Valid formats are: {', '.join(valid_formats)}"
                )
                details["original_format_valid"] = False
            else:
                details["original_format_valid"] = True

        # Validate original_spec_type
        original_spec_type = contract_data.get("original_spec_type")
        if original_spec_type:
            valid_spec_types = [choice[0] for choice in OriginalSpecType.choices]
            if original_spec_type not in valid_spec_types:
                errors.append(
                    f"Invalid original_spec_type '{original_spec_type}'. "
                    f"Valid spec types are: {', '.join(valid_spec_types)}"
                )
                details["original_spec_type_valid"] = False
            else:
                details["original_spec_type_valid"] = True

        # Validate original_raw is not empty
        original_raw = contract_data.get("original_raw")
        if original_raw:
            if not isinstance(original_raw, str):
                errors.append(f"original_raw must be a string, got {type(original_raw).__name__}")
            elif not original_raw.strip():
                errors.append("original_raw cannot be empty")
            else:
                details["original_raw_valid"] = True
                # Try to parse JSON/YAML to validate structure
                try:
                    if original_format == "JSON":
                        import json
                        json.loads(original_raw)
                        details["original_raw_parseable"] = True
                    elif original_format == "YAML":
                        import yaml
                        yaml.safe_load(original_raw)
                        details["original_raw_parseable"] = True
                except Exception as e:
                    warnings.append(f"Could not parse original_raw: {str(e)}")
                    details["original_raw_parseable"] = False
        else:
            details["original_raw_valid"] = False

        # Validate version (if provided)
        version = contract_data.get("version")
        if version is not None:
            if not isinstance(version, int) or version < 1:
                errors.append(f"version must be a positive integer, got {version}")
                details["version_valid"] = False
            else:
                details["version_valid"] = True
                details["version"] = version

        # Validate status (if provided)
        status = contract_data.get("status")
        if status:
            valid_statuses = [choice[0] for choice in ContractStatus.choices]
            if status not in valid_statuses:
                errors.append(
                    f"Invalid status '{status}'. "
                    f"Valid statuses are: {', '.join(valid_statuses)}"
                )
                details["status_valid"] = False
            else:
                details["status_valid"] = True

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details)

    def validate_contract_update(
        self, contract: Contract, contract_data: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate contract update (can update contract).

        Validates:
        - Contract exists and is accessible
        - User has permission to update
        - Update does not violate constraints
        - Status transitions are valid
        - Version changes are valid

        Args:
            contract: Contract instance to update
            contract_data: Optional dictionary with update data

        Returns:
            ValidationResult with validation status and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": "contract_update",
            "contract_id": str(contract.id) if contract else None,
        }

        if not contract:
            errors.append("Contract must be provided")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings, details=details)

        details["contract_exists"] = True
        details["current_status"] = contract.status
        details["current_version"] = contract.version

        # Validate tenant context
        if self.tenant_id:
            if str(contract.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Contract {contract.id} does not belong to tenant {self.tenant_id}. "
                    f"Contract belongs to tenant {contract.tenant_id}"
                )
                details["tenant_match"] = False
            else:
                details["tenant_match"] = True
        else:
            warnings.append("No tenant context provided. Tenant validation skipped.")
            details["tenant_match"] = None

        # Validate contract is not RETIRED (can't update retired contracts)
        if contract.status == ContractStatus.RETIRED:
            errors.append(
                f"Cannot update contract {contract.id} with status RETIRED. "
                "Retired contracts are immutable."
            )
            details["can_update"] = False
            details["update_blocked_reason"] = "contract_retired"
        else:
            details["can_update"] = True

        # Validate status transition if status is being updated
        if contract_data and "status" in contract_data:
            new_status = contract_data["status"]
            current_status = contract.status

            valid_statuses = [choice[0] for choice in ContractStatus.choices]
            if new_status not in valid_statuses:
                errors.append(
                    f"Invalid status '{new_status}'. "
                    f"Valid statuses are: {', '.join(valid_statuses)}"
                )
                details["status_transition_valid"] = False
            else:
                # Validate status transition
                valid_transitions = {
                    ContractStatus.DRAFT: [ContractStatus.ACTIVE, ContractStatus.RETIRED],
                    ContractStatus.ACTIVE: [ContractStatus.RETIRED],
                    ContractStatus.RETIRED: [],  # Cannot transition from RETIRED
                }

                if new_status == current_status:
                    details["status_transition_valid"] = True
                    details["status_transition_type"] = "no_change"
                elif new_status in valid_transitions.get(current_status, []):
                    details["status_transition_valid"] = True
                    details["status_transition_type"] = "valid"
                else:
                    errors.append(
                        f"Invalid status transition from '{current_status}' to '{new_status}'. "
                        f"Valid transitions from '{current_status}' are: "
                        f"{', '.join(valid_transitions.get(current_status, []))}"
                    )
                    details["status_transition_valid"] = False
                    details["status_transition_type"] = "invalid"

        # Validate version change if version is being updated
        if contract_data and "version" in contract_data:
            new_version = contract_data["version"]
            current_version = contract.version

            if not isinstance(new_version, int):
                errors.append(f"version must be an integer, got {type(new_version).__name__}")
                details["version_change_valid"] = False
            elif new_version < 1:
                errors.append(f"version must be a positive integer, got {new_version}")
                details["version_change_valid"] = False
            elif new_version < current_version:
                errors.append(
                    f"Cannot decrease contract version from {current_version} to {new_version}. "
                    "Versions can only be incremented."
                )
                details["version_change_valid"] = False
            elif new_version == current_version:
                warnings.append(f"Version unchanged ({current_version})")
                details["version_change_valid"] = True
            else:
                # Check if version already exists for this asset
                if contract.asset_id:
                    existing_contract = Contract.objects.filter(
                        tenant_id=contract.tenant_id,
                        asset_id=contract.asset_id,
                        version=new_version
                    ).exclude(id=contract.id).first()

                    if existing_contract:
                        errors.append(
                            f"Version {new_version} already exists for asset {contract.asset_id}. "
                            f"Existing contract: {existing_contract.id}"
                        )
                        details["version_change_valid"] = False
                    else:
                        details["version_change_valid"] = True
                else:
                    details["version_change_valid"] = True

        # Validate original_raw update (if provided)
        if contract_data and "original_raw" in contract_data:
            original_raw = contract_data["original_raw"]
            original_format = contract_data.get("original_format", contract.original_format)

            if original_raw:
                if not isinstance(original_raw, str) or not original_raw.strip():
                    errors.append("original_raw cannot be empty")
                else:
                    # Try to parse JSON/YAML
                    try:
                        if original_format == "JSON":
                            import json
                            json.loads(original_raw)
                        elif original_format == "YAML":
                            import yaml
                            yaml.safe_load(original_raw)
                    except Exception as e:
                        warnings.append(f"Could not parse original_raw: {str(e)}")

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details)

    def validate_contract_deletion(self, contract: Contract) -> ValidationResult:
        """
        Validate contract deletion (cannot delete if referenced).

        Validates:
        - Contract exists
        - Contract is not referenced by other contracts (ODPS-ODCS links)
        - Contract is not referenced by scheduled ingestions
        - Contract can be safely deleted

        Args:
            contract: Contract instance to delete

        Returns:
            ValidationResult with validation status and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": "contract_deletion",
            "contract_id": str(contract.id) if contract else None,
        }

        if not contract:
            errors.append("Contract must be provided")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings, details=details)

        details["contract_exists"] = True
        details["contract_status"] = contract.status

        # Validate tenant context
        if self.tenant_id:
            if str(contract.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Contract {contract.id} does not belong to tenant {self.tenant_id}. "
                    f"Contract belongs to tenant {contract.tenant_id}"
                )
                details["tenant_match"] = False
            else:
                details["tenant_match"] = True
        else:
            warnings.append("No tenant context provided. Tenant validation skipped.")
            details["tenant_match"] = None

        # Check if contract is referenced by scheduled ingestions
        try:
            from hub.apps.scheduled_ingestion.models import ScheduledIngestion
            scheduled_ingestions = ScheduledIngestion.objects.filter(contract_id=contract.id)
            ingestion_count = scheduled_ingestions.count()

            if ingestion_count > 0:
                errors.append(
                    f"Cannot delete contract {contract.id}. "
                    f"It is referenced by {ingestion_count} scheduled ingestion(s). "
                    f"Remove references before deleting."
                )
                details["referenced_by_scheduled_ingestions"] = True
                details["scheduled_ingestion_count"] = ingestion_count
            else:
                details["referenced_by_scheduled_ingestions"] = False
                details["scheduled_ingestion_count"] = 0
        except Exception as e:
            warnings.append(f"Could not check scheduled ingestion references: {str(e)}")
            details["referenced_by_scheduled_ingestions"] = None

        # Check if contract is referenced by other contracts (ODPS-ODCS links)
        try:
            # Check if this contract is linked from ODPS contracts
            odps_contracts_linking = Contract.objects.filter(
                original_spec_type=OriginalSpecType.ODPS,
                hub_contract_json__extensions__x_odps__odcs_link=str(contract.id)
            ).exclude(id=contract.id)

            odps_link_count = odps_contracts_linking.count()
            if odps_link_count > 0:
                errors.append(
                    f"Cannot delete contract {contract.id}. "
                    f"It is linked from {odps_link_count} ODPS contract(s). "
                    f"Remove links before deleting."
                )
                details["referenced_by_odps_contracts"] = True
                details["odps_link_count"] = odps_link_count
            else:
                details["referenced_by_odps_contracts"] = False
                details["odps_link_count"] = 0

            # Check if this contract links to other contracts (if it's an ODPS contract)
            if contract.original_spec_type == OriginalSpecType.ODPS and contract.hub_contract_json:
                extensions = contract.hub_contract_json.get("extensions", {})
                x_odps = extensions.get("x_odps", {})
                odcs_link = x_odps.get("odcs_link")

                if odcs_link:
                    try:
                        linked_contract = Contract.objects.get(id=odcs_link)
                        warnings.append(
                            f"Contract {contract.id} links to contract {odcs_link}. "
                            "Deleting this contract will break the link."
                        )
                        details["links_to_contract"] = str(odcs_link)
                    except Contract.DoesNotExist:
                        warnings.append(
                            f"Contract {contract.id} links to non-existent contract {odcs_link}. "
                            "Link will be removed on deletion."
                        )
                        details["links_to_contract"] = str(odcs_link)
                        details["linked_contract_exists"] = False
        except Exception as e:
            warnings.append(f"Could not check contract references: {str(e)}")
            details["referenced_by_odps_contracts"] = None

        # Warn if contract is ACTIVE
        if contract.status == ContractStatus.ACTIVE:
            warnings.append(
                f"Contract {contract.id} is ACTIVE. "
                "Consider retiring it before deletion."
            )
            details["is_active"] = True
        else:
            details["is_active"] = False

        details["can_delete"] = len(errors) == 0
        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details)

    def validate_contract_version(self, contract: Contract) -> ValidationResult:
        """
        Validate contract version (version compatibility).

        Validates:
        - Version is valid (positive integer)
        - Version is compatible with asset (if asset has other contracts)
        - Version follows semantic versioning (if applicable)
        - Version conflicts don't exist

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": "contract_version",
            "contract_id": str(contract.id) if contract else None,
        }

        if not contract:
            errors.append("Contract must be provided")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings, details=details)

        details["contract_exists"] = True
        details["contract_version"] = contract.version
        details["contract_status"] = contract.status

        # Validate version is positive integer
        if not isinstance(contract.version, int) or contract.version < 1:
            errors.append(
                f"Contract version must be a positive integer, got {contract.version}"
            )
            details["version_format_valid"] = False
        else:
            details["version_format_valid"] = True

        # Check for version conflicts with other contracts for the same asset
        if contract.asset_id:
            try:
                conflicting_contracts = Contract.objects.filter(
                    tenant_id=contract.tenant_id,
                    asset_id=contract.asset_id,
                    version=contract.version
                ).exclude(id=contract.id)

                conflict_count = conflicting_contracts.count()
                if conflict_count > 0:
                    errors.append(
                        f"Version conflict: Contract {contract.id} has version {contract.version} "
                        f"which conflicts with {conflict_count} other contract(s) for asset {contract.asset_id}. "
                        f"Conflicting contract IDs: {', '.join(str(c.id) for c in conflicting_contracts[:5])}"
                    )
                    details["version_conflict"] = True
                    details["conflict_count"] = conflict_count
                else:
                    details["version_conflict"] = False
                    details["conflict_count"] = 0

                # Check version sequence (warn if gaps exist)
                other_contracts = Contract.objects.filter(
                    tenant_id=contract.tenant_id,
                    asset_id=contract.asset_id
                ).exclude(id=contract.id).order_by("version")

                if other_contracts.exists():
                    versions = [c.version for c in other_contracts]
                    max_version = max(versions) if versions else 0

                    if contract.version > max_version + 1:
                        warnings.append(
                            f"Version {contract.version} is significantly higher than the maximum "
                            f"existing version ({max_version}). Consider using version {max_version + 1}."
                        )
                        details["version_gap_detected"] = True
                    else:
                        details["version_gap_detected"] = False
            except Exception as e:
                warnings.append(f"Could not check version conflicts: {str(e)}")
                details["version_conflict"] = None
        else:
            details["version_conflict"] = None
            details["version_gap_detected"] = None

        # Validate original_spec_version format (if applicable)
        if contract.original_spec_version:
            # Basic validation: should be a version string (e.g., "3.0.2", "4.1")
            spec_version = contract.original_spec_version
            if not isinstance(spec_version, str) or not spec_version.strip():
                errors.append(
                    f"original_spec_version must be a non-empty string, got {spec_version}"
                )
                details["spec_version_valid"] = False
            else:
                details["spec_version_valid"] = True
                details["original_spec_version"] = spec_version

        details["is_valid"] = len(errors) == 0
        details["has_warnings"] = len(warnings) > 0

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings, details=details)


@register_rule(
    rule_name="odps_normalization_validation",
    description="Validates contract normalization eligibility, status, and fidelity (data loss prevention)",
    tags=["odps", "normalization", "validation"],
    priority=10,
)
class ODPSNormalizationRules(BusinessRules):
    """
    Business rules for contract normalization validation.

    Extends BusinessRules base class with normalization-specific validation:
    - Normalization eligibility validation (contract can be normalized)
    - Normalization status validation (NORMALIZED_OK, NORMALIZED_WITH_WARNINGS, NORMALIZATION_FAILED)
    - Normalization fidelity validation (no data loss during normalization)

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    def validate(
        self,
        context: ODPSRuleExecutionContext,
        validation_type: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate contract normalization based on validation_type.

        Args:
            context: ODPSRuleExecutionContext with contract and optional ODPS document
            validation_type: Type of validation to perform:
                - "eligibility": Check if contract can be normalized
                - "status": Validate normalization status
                - "fidelity": Check for data loss during normalization
                - None or "all": Perform all validations

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        if not context.contract:
            return ValidationResult(
                is_valid=False,
                errors=["Contract is required for normalization validation"],
                warnings=[],
            )

        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Determine which validations to perform
        if validation_type is None or validation_type == "all":
            validation_types = ["eligibility", "status", "fidelity"]
        else:
            validation_types = [validation_type]

        # Perform requested validations
        if "eligibility" in validation_types:
            eligibility_result = self.validate_normalization_eligibility(context.contract)
            errors.extend(eligibility_result.errors)
            warnings.extend(eligibility_result.warnings)
            details["eligibility"] = eligibility_result.details or {}

        if "status" in validation_types:
            status_result = self.validate_normalization_status(context.contract)
            errors.extend(status_result.errors)
            warnings.extend(status_result.warnings)
            details["status"] = status_result.details or {}

        if "fidelity" in validation_types:
            fidelity_result = self.validate_normalization_fidelity(context.contract)
            errors.extend(fidelity_result.errors)
            warnings.extend(fidelity_result.warnings)
            details["fidelity"] = fidelity_result.details or {}

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    def validate_normalization_eligibility(self, contract: Contract) -> ValidationResult:
        """
        Validate that a contract is eligible for normalization.

        A contract is eligible for normalization if:
        - It has original_raw content
        - It has a valid original_format (JSON or YAML)
        - It has a valid original_spec_type (ODCS or ODPS)
        - A normalizer exists for the spec type/version

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with eligibility check results
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "contract_id": str(contract.id),
            "is_eligible": False,
        }

        # Check original_raw exists
        if not contract.original_raw:
            errors.append("Contract must have original_raw content to be eligible for normalization")
            details["has_original_raw"] = False
        else:
            details["has_original_raw"] = True
            details["original_raw_length"] = len(contract.original_raw)

        # Check original_format is valid
        if not contract.original_format:
            errors.append("Contract must have original_format (JSON or YAML) to be eligible for normalization")
            details["has_original_format"] = False
        elif contract.original_format not in [OriginalFormat.JSON, OriginalFormat.YAML]:
            errors.append(
                f"Contract original_format must be JSON or YAML, got {contract.original_format}"
            )
            details["has_original_format"] = False
            details["original_format"] = contract.original_format
        else:
            details["has_original_format"] = True
            details["original_format"] = contract.original_format

        # Check original_spec_type is valid
        if not contract.original_spec_type:
            errors.append("Contract must have original_spec_type (ODCS or ODPS) to be eligible for normalization")
            details["has_original_spec_type"] = False
        elif contract.original_spec_type not in [OriginalSpecType.ODCS, OriginalSpecType.ODPS]:
            errors.append(
                f"Contract original_spec_type must be ODCS or ODPS, got {contract.original_spec_type}"
            )
            details["has_original_spec_type"] = False
            details["original_spec_type"] = contract.original_spec_type
        else:
            details["has_original_spec_type"] = True
            details["original_spec_type"] = contract.original_spec_type

        # Check if normalizer exists for this spec type/version
        if contract.original_raw and contract.original_format and contract.original_spec_type:
            try:
                # Parse contract to get contract_data
                contract_data = parse_contract(contract.original_raw, contract.original_format)

                # Detect spec version if not set
                spec_version = contract.original_spec_version or contract_data.get("version", "1.0")
                if isinstance(spec_version, tuple):
                    spec_version = spec_version[0] if spec_version else "1.0"

                # Check if normalizer exists
                normalizer = get_normalizer(
                    contract.original_spec_type,
                    str(spec_version),
                    contract_data,
                )
                if not normalizer:
                    errors.append(
                        f"No normalizer found for spec_type={contract.original_spec_type}, "
                        f"spec_version={spec_version}. Contract cannot be normalized."
                    )
                    details["normalizer_exists"] = False
                    details["spec_version"] = spec_version
                else:
                    details["normalizer_exists"] = True
                    details["spec_version"] = spec_version
                    details["normalizer_type"] = type(normalizer).__name__
            except Exception as e:
                errors.append(
                    f"Error checking normalizer availability: {str(e)}. "
                    "Contract eligibility cannot be determined."
                )
                details["normalizer_check_error"] = str(e)
                details["normalizer_exists"] = None

        # Determine overall eligibility
        details["is_eligible"] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    def validate_normalization_status(self, contract: Contract) -> ValidationResult:
        """
        Validate contract normalization status.

        Validates that normalization_status is one of:
        - NORMALIZED_OK: Normalization succeeded with no warnings
        - NORMALIZED_WITH_WARNINGS: Normalization succeeded but with warnings
        - NORMALIZATION_FAILED: Normalization failed
        - NOT_NORMALIZED: Contract has not been normalized yet

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with normalization status validation results
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "contract_id": str(contract.id),
            "normalization_status": contract.normalization_status,
        }

        # Check normalization_status is set
        if not contract.normalization_status:
            errors.append("Contract normalization_status is not set")
            details["status_valid"] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        # Validate normalization_status is a valid enum value
        valid_statuses = [
            NormalizationStatus.NOT_NORMALIZED,
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
            NormalizationStatus.NORMALIZATION_FAILED,
        ]

        if contract.normalization_status not in valid_statuses:
            errors.append(
                f"Contract normalization_status must be one of {valid_statuses}, "
                f"got {contract.normalization_status}"
            )
            details["status_valid"] = False
        else:
            details["status_valid"] = True

        # Check consistency between status and hub_contract_json
        if contract.normalization_status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS,
        ]:
            if not contract.hub_contract_json:
                errors.append(
                    f"Contract has normalization_status={contract.normalization_status} "
                    "but hub_contract_json is missing. Status and data are inconsistent."
                )
                details["status_data_consistent"] = False
            else:
                details["status_data_consistent"] = True
                # Validate hub_contract_json structure
                if not isinstance(contract.hub_contract_json, dict):
                    errors.append(
                        f"Contract hub_contract_json must be a dictionary, "
                        f"got {type(contract.hub_contract_json).__name__}"
                    )
                    details["hub_contract_valid"] = False
                else:
                    # Check critical sections exist
                    info = contract.hub_contract_json.get("info")
                    schema = contract.hub_contract_json.get("schema")
                    if not info:
                        warnings.append("Contract hub_contract_json missing 'info' section")
                        details["has_info"] = False
                    else:
                        details["has_info"] = True
                    if not schema:
                        warnings.append("Contract hub_contract_json missing 'schema' section")
                        details["has_schema"] = False
                    else:
                        details["has_schema"] = True
                    details["hub_contract_valid"] = True

            # Check for warning details if status is NORMALIZED_WITH_WARNINGS
            if contract.normalization_status == NormalizationStatus.NORMALIZED_WITH_WARNINGS:
                if contract.normalization_warnings and len(contract.normalization_warnings) > 0:
                    details["has_warnings"] = True
                    details["warning_count"] = len(contract.normalization_warnings)
                    if isinstance(contract.normalization_warnings, list):
                        details["warnings"] = contract.normalization_warnings[:5]  # First 5 warnings
                else:
                    warnings.append(
                        "Contract has normalization_status=NORMALIZED_WITH_WARNINGS "
                        "but normalization_warnings is empty or missing. Warning details are missing."
                    )
                    details["has_warnings"] = False

        elif contract.normalization_status == NormalizationStatus.NORMALIZATION_FAILED:
            # If normalization failed, check for error details
            if contract.normalization_errors and len(contract.normalization_errors) > 0:
                details["has_errors"] = True
                details["error_count"] = len(contract.normalization_errors)
                if isinstance(contract.normalization_errors, list):
                    details["errors"] = contract.normalization_errors[:5]  # First 5 errors
            else:
                warnings.append(
                    "Contract has normalization_status=NORMALIZATION_FAILED "
                    "but normalization_errors is empty or missing. Error details are missing."
                )
                details["has_errors"] = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details,
        )

    def validate_normalization_fidelity(self, contract: Contract) -> ValidationResult:
        """
        Validate normalization fidelity (no data loss during normalization).

        Ensures that critical fields from the original contract are preserved
        in the normalized hub_contract_json:
        - Contract name/ID is preserved
        - Schema fields are preserved
        - Critical metadata is preserved
        - Coverage metrics indicate completeness

        Args:
            contract: Contract instance to validate

        Returns:
            ValidationResult with fidelity validation results
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "contract_id": str(contract.id),
            "fidelity_check": "not_performed",
        }

        # Check prerequisites
        if not contract.original_raw or not contract.original_raw.strip():
            errors.append("Contract must have original_raw to validate normalization fidelity")
            details["fidelity_check"] = "skipped_missing_original"
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        if not contract.hub_contract_json:
            errors.append("Contract must have hub_contract_json to validate normalization fidelity")
            details["fidelity_check"] = "skipped_missing_hub_contract"
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        if contract.normalization_status == NormalizationStatus.NORMALIZATION_FAILED:
            errors.append(
                "Cannot validate fidelity for contract with normalization_status=NORMALIZATION_FAILED"
            )
            details["fidelity_check"] = "skipped_failed_normalization"
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        # Parse original contract
        try:
            original_data = parse_contract(contract.original_raw, contract.original_format)
        except Exception as e:
            errors.append(f"Failed to parse original contract: {str(e)}")
            details["fidelity_check"] = "failed_parse_original"
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details,
            )

        hub_contract = contract.hub_contract_json
        details["fidelity_check"] = "performed"

        # Check critical fields are preserved
        # 1. Name/ID preservation
        original_name = None
        if contract.original_spec_type == OriginalSpecType.ODPS:
            product = original_data.get("product", {})
            original_name = product.get("name") or product.get("productID")
        elif contract.original_spec_type == OriginalSpecType.ODCS:
            info = original_data.get("info", {})
            original_name = info.get("name") or info.get("title")

        hub_name = hub_contract.get("info", {}).get("name")
        if original_name and not hub_name:
            errors.append(
                f"Original contract name '{original_name}' was lost during normalization. "
                "Fidelity check failed."
            )
            details["name_preserved"] = False
        elif original_name and hub_name:
            details["name_preserved"] = True
            details["original_name"] = original_name
            details["hub_name"] = hub_name
            if original_name != hub_name:
                warnings.append(
                    f"Original contract name '{original_name}' differs from "
                    f"normalized name '{hub_name}'. This may indicate data transformation."
                )
        else:
            warnings.append("Could not determine original contract name for fidelity check")
            details["name_preserved"] = None

        # 2. Schema fields preservation
        original_fields_count = 0
        hub_fields_count = 0

        if contract.original_spec_type == OriginalSpecType.ODPS:
            product = original_data.get("product", {})
            data_schema = product.get("dataSchema", {})
            if isinstance(data_schema, dict):
                fields = data_schema.get("fields", [])
                if isinstance(fields, list):
                    original_fields_count = len(fields)
        elif contract.original_spec_type == OriginalSpecType.ODCS:
            schema = original_data.get("schema", {})
            fields = schema.get("fields", [])
            if isinstance(fields, list):
                original_fields_count = len(fields)

        schema = hub_contract.get("schema", {})
        fields = schema.get("fields", [])
        if isinstance(fields, list):
            hub_fields_count = len(fields)

        details["original_fields_count"] = original_fields_count
        details["hub_fields_count"] = hub_fields_count

        if original_fields_count > 0:
            if hub_fields_count == 0:
                errors.append(
                    f"Original contract had {original_fields_count} schema fields, "
                    "but normalized contract has 0 fields. Data loss detected."
                )
                details["fields_preserved"] = False
            elif hub_fields_count < original_fields_count:
                warnings.append(
                    f"Original contract had {original_fields_count} schema fields, "
                    f"but normalized contract has {hub_fields_count} fields. "
                    f"Possible data loss ({original_fields_count - hub_fields_count} fields missing)."
                )
                details["fields_preserved"] = "partial"
            else:
                details["fields_preserved"] = True

        # 3. Check normalization coverage if available
        normalization_metadata = hub_contract.get("normalization", {})
        coverage = normalization_metadata.get("coverage")
        if coverage:
            overall_coverage = coverage.get("overall", 0.0)
            details["coverage"] = overall_coverage
            if overall_coverage < 0.7:
                warnings.append(
                    f"Normalization coverage is {overall_coverage:.2%}, which is below 70%. "
                    "This may indicate incomplete normalization or data loss."
                )
            elif overall_coverage >= 0.9:
                details["coverage_adequate"] = True
            else:
                details["coverage_adequate"] = "marginal"
        else:
            warnings.append("Normalization coverage metrics not available for fidelity check")
            details["coverage"] = None

        # 4. Check for extensions (unmappable fields)
        extensions = hub_contract.get("extensions", {})
        if extensions:
            extension_keys = list(extensions.keys())
            details["has_extensions"] = True
            details["extension_count"] = len(extension_keys)
            warnings.append(
                f"Normalized contract has {len(extension_keys)} extension(s), "
                "indicating some fields could not be mapped to HubContract format. "
                "This may indicate partial data loss or transformation."
            )
        else:
            details["has_extensions"] = False

        # Summary
        details["fidelity_score"] = "high" if len(errors) == 0 and len(warnings) == 0 else "medium" if len(errors) == 0 else "low"

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details,
        )
