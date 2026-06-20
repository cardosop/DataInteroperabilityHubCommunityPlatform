"""
ODPS Normalizer

Implements SpecNormalizer protocol for ODPS (Open Data Product Standard) documents.
Normalizes ODPS documents to HubContract format with comprehensive error handling
and graceful degradation for missing optional fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.odps_errors import ODPSNormalizationError
from hub.apps.contracts.odps_version_detection import detect_odps_version

if TYPE_CHECKING:
    from hub.apps.contracts.normalization_engine import NormalizationResult

logger = structlog.get_logger(__name__)


class ODPSNormalizer:
    """
    SpecNormalizer implementation for ODPS contracts.

    Provides normalization of ODPS documents to HubContract format with:
    - Comprehensive error handling with context
    - Graceful degradation for missing optional fields
    - Field-level error tracking
    - Type validation and conversion
    """

    spec_type: str = OriginalSpecType.ODPS

    def supports(self, spec_type: str, spec_version: str, contract_data: dict[str, Any]) -> bool:
        """
        Check if this normalizer supports the given spec type and version.

        Args:
            spec_type: Specification type (e.g., "ODPS")
            spec_version: Specification version (e.g., "4.1")
            contract_data: Contract data dictionary

        Returns:
            True if this normalizer supports the spec type, False otherwise
        """
        return spec_type == self.spec_type

    def normalize(
        self, contract_data: dict[str, Any], spec_version: str | None = None
    ) -> NormalizationResult:
        """
        Normalize ODPS contract data to HubContract format.

        This is the main entry point for ODPS normalization. It handles:
        - Error handling with context (field names, expected types)
        - Graceful degradation for missing optional fields
        - Type validation and conversion
        - Field mapping errors

        Args:
            contract_data: Raw ODPS contract data (dict)
            spec_version: Optional spec version (auto-detected if not provided)

        Returns:
            NormalizationResult with hub_contract, status, errors, warnings, etc.

        Raises:
            ODPSNormalizationError: For normalization errors with context
        """
        from hub.apps.contracts.normalization_engine import NormalizationResult  # noqa: F811

        errors: list[str] = []
        warnings: list[str] = []
        hub_contract: dict[str, Any] | None = None

        try:
            # Detect ODPS version if not provided
            if spec_version is None:
                try:
                    detected_version = detect_odps_version(contract_data)
                    spec_version = detected_version or "4.1"  # Default to 4.1
                except Exception as e:
                    error_msg = f"Failed to detect ODPS version: {e!s}"
                    logger.warning("odps_version_detection_failed", error=str(e), message=error_msg)
                    warnings.append(error_msg)
                    spec_version = "4.1"  # Default fallback

            # Validate contract_data is a dict
            if not isinstance(contract_data, dict):
                raise ODPSNormalizationError(
                    message=f"Contract data must be a dictionary, got {type(contract_data).__name__}",
                    error_code=ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED,
                    field_path="/",
                    context={
                        "expected": "dict",
                        "actual": type(contract_data).__name__,
                    },
                )

            # Initialize hub_contract structure
            hub_contract = self._initialize_hub_contract(contract_data, spec_version)

            # Normalize contract sections
            # ODPS → HubContract info mapping
            self._normalize_info(contract_data, hub_contract, warnings)
            # ODPS → HubContract quality mapping
            self._normalize_quality(contract_data, hub_contract, warnings)
            # ODPS → HubContract lifecycle mapping
            self._normalize_lifecycle(contract_data, hub_contract, warnings)
            # ODPS → HubContract marketplace mapping
            self._normalize_marketplace(contract_data, hub_contract, warnings)
            # Minimal schema normalization (populate from product.dataSchema if available)
            self._normalize_schema_minimal(contract_data, hub_contract, warnings)
            # ODPS contract extraction
            self._extract_contract(contract_data, hub_contract, warnings)
            # ODPS → HubContract product strategy mapping (ODPS 4.1+)
            self._normalize_product_strategy(contract_data, hub_contract, warnings, spec_version)

            # Determine normalization status
            status = self._determine_status(hub_contract, errors, warnings)

            # Track ODPS normalization metrics for observability
            try:
                from hub.apps.observability.otel_metrics import (
                    odps_normalization_total,
                    odps_version_distribution_total,
                )

                tenant_id = getattr(self, "tenant_id", None) or "unknown"
                status_str = status.value if hasattr(status, "value") else str(status)
                version_str = spec_version or "unknown"
                odps_normalization_total.labels(
                    status=status_str, version=version_str, tenant_id=tenant_id
                ).inc()
                odps_version_distribution_total.labels(
                    version=version_str, tenant_id=tenant_id
                ).inc()
            except Exception:
                pass  # Metrics failure should not affect normalization

            # Calculate coverage (placeholder for now)
            coverage = None
            if hub_contract:
                try:
                    from hub.apps.contracts.coverage import calculate_coverage

                    coverage_result = calculate_coverage(
                        hub_contract, spec_type=OriginalSpecType.ODPS
                    )
                    if coverage_result:
                        coverage = {
                            "overall": coverage_result.overall,
                            "sections": coverage_result.sections,
                        }
                except Exception as e:
                    logger.debug(
                        "odps_coverage_calculation_failed",
                        error=str(e),
                        message="Coverage calculation failed, continuing without coverage",
                    )

            return NormalizationResult(
                hub_contract=hub_contract,
                status=status,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version,
                coverage=coverage,
            )

        except ODPSNormalizationError as e:
            # Re-raise ODPSNormalizationError with full context
            errors.append(str(e))
            logger.warning(
                "odps_normalization_error",
                error_code=e.error_code,
                field_path=e.context.get("field_path"),
                message=str(e),
                context=e.context,
            )
            # Track ODPS normalization failure metrics
            try:
                from hub.apps.observability.otel_metrics import (
                    odps_normalization_total,
                    odps_version_distribution_total,
                )

                tenant_id = getattr(self, "tenant_id", None) or "unknown"
                version_str = spec_version or "unknown"
                odps_normalization_total.labels(
                    status="NORMALIZATION_FAILED", version=version_str, tenant_id=tenant_id
                ).inc()
                odps_version_distribution_total.labels(
                    version=version_str, tenant_id=tenant_id
                ).inc()
            except Exception:
                pass  # Metrics failure should not affect error handling
            return NormalizationResult(
                hub_contract=None,
                status=NormalizationStatus.NORMALIZATION_FAILED,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version or "4.1",
                coverage=None,
            )
        except Exception as e:
            # Catch any unexpected errors and wrap in ODPSNormalizationError
            error = ODPSNormalizationError(
                message=f"Unexpected error during ODPS normalization: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                cause=e,
            )
            errors.append(str(error))
            logger.error(
                "odps_normalization_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                message="Unexpected error during normalization",
            )
            return NormalizationResult(
                hub_contract=None,
                status=NormalizationStatus.NORMALIZATION_FAILED,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version or "4.1",
                coverage=None,
            )

    def _initialize_hub_contract(
        self, contract_data: dict[str, Any], spec_version: str
    ) -> dict[str, Any]:
        """
        Initialize HubContract structure with basic fields.

        Args:
            contract_data: Raw ODPS contract data
            spec_version: ODPS spec version

        Returns:
            Initialized HubContract dictionary

        Raises:
            ODPSNormalizationError: If initialization fails
        """
        try:
            hub_contract = {
                "info": {},
                "schema": {"fields": []},
                "extensions": {},
            }

            # Add normalization metadata
            hub_contract["normalization"] = {
                "original_spec_type": self.spec_type,
                "original_spec_version": spec_version,
                "normalized_at": None,  # Will be set by service layer
            }

            return hub_contract

        except Exception as e:
            raise ODPSNormalizationError(
                message=f"Failed to initialize HubContract structure: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/",
                cause=e,
            ) from e

    def _determine_status(
        self, hub_contract: dict[str, Any] | None, errors: list[str], warnings: list[str]
    ) -> NormalizationStatus:
        """
        Determine normalization status based on result.

        Args:
            hub_contract: Normalized HubContract (None if normalization failed)
            errors: List of errors
            warnings: List of warnings

        Returns:
            NormalizationStatus enum value
        """
        if errors or hub_contract is None:
            return NormalizationStatus.NORMALIZATION_FAILED

        # Check for critical sections
        info = hub_contract.get("info", {})
        if "info" not in hub_contract or "name" not in info or not info.get("name"):
            return NormalizationStatus.NORMALIZATION_FAILED

        # Initialize schema section if missing
        if "schema" not in hub_contract:
            hub_contract["schema"] = {}

        schema = hub_contract["schema"]
        # Initialize schema.fields as empty list if missing
        # For ODPS contracts, schema.fields may be empty if schema comes from ODCS contract
        if "fields" not in schema:
            schema["fields"] = []

        # For ODPS contracts, empty schema.fields is acceptable (schema comes from ODCS)
        # This is expected in Product-First flow where technical schema is in ODCS contract
        # Only require schema.fields to exist, not to be non-empty

        # If warnings present, status is WITH_WARNINGS
        if warnings or hub_contract.get("extensions"):
            return NormalizationStatus.NORMALIZED_WITH_WARNINGS

        # All critical sections present, no warnings
        return NormalizationStatus.NORMALIZED_OK

    def _normalize_field_with_error_context(
        self,
        field_name: str,
        field_path: str,
        value: Any,
        expected_type: type,
        default_value: Any = None,
        required: bool = False,
    ) -> Any:
        """
        Normalize a field with error context and graceful degradation.

        Args:
            field_name: Name of the field being normalized
            field_path: JSON Pointer path to the field
            value: Field value to normalize
            expected_type: Expected Python type
            default_value: Default value if field is missing (for optional fields)
            required: Whether the field is required

        Returns:
            Normalized field value

        Raises:
            ODPSNormalizationError: If normalization fails with context
        """
        # Handle missing field
        if value is None:
            if required:
                raise ODPSNormalizationError(
                    message=f"Required field '{field_name}' is missing at path '{field_path}'",
                    error_code=ODPSNormalizationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    field_path=field_path,
                    context={
                        "expected": expected_type.__name__,
                        "actual": None,
                    },
                )
            else:
                # Optional field missing - return default
                return default_value

        # Type validation
        if not isinstance(value, expected_type):
            raise ODPSNormalizationError(
                message=f"Field '{field_name}' at path '{field_path}' has invalid type: expected {expected_type.__name__}, got {type(value).__name__}",
                error_code=ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED,
                field_path=field_path,
                context={
                    "expected": expected_type.__name__,
                    "actual": type(value).__name__,
                },
            )

        return value

    def _normalize_optional_field(
        self,
        field_name: str,
        field_path: str,
        value: Any,
        expected_type: type,
        default_value: Any = None,
        warnings: list[str] | None = None,
    ) -> Any:
        """
        Normalize an optional field with graceful degradation.

        If the field is missing or invalid, logs a warning and returns default value.

        Args:
            field_name: Name of the field being normalized
            field_path: JSON Pointer path to the field
            value: Field value to normalize
            expected_type: Expected Python type
            default_value: Default value if field is missing or invalid
            warnings: Optional list to append warnings to

        Returns:
            Normalized field value or default_value
        """
        if value is None:
            if warnings is not None:
                warnings.append(
                    f"Optional field '{field_name}' at path '{field_path}' is missing, using default value"
                )
            logger.debug(
                "odps_optional_field_missing",
                field_name=field_name,
                field_path=field_path,
                message=f"Optional field '{field_name}' missing, using default",
            )
            return default_value

        if not isinstance(value, expected_type):
            if warnings is not None:
                warnings.append(
                    f"Optional field '{field_name}' at path '{field_path}' has invalid type "
                    f"(expected {expected_type.__name__}, got {type(value).__name__}), using default value"
                )
            logger.warning(
                "odps_optional_field_invalid_type",
                field_name=field_name,
                field_path=field_path,
                expected_type=expected_type.__name__,
                actual_type=type(value).__name__,
                message=f"Optional field '{field_name}' has invalid type, using default",
            )
            return default_value

        return value

    def _normalize_quality(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Normalize ODPS dataQuality section to HubContract quality format.

        Maps:
        - product.dataQuality.declarative.default → quality.default_profile_key
        - product.dataQuality.declarative dimensions → quality.rules[]
        - product.dataQuality.executable → quality.x_odps.executable[]

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to

        Raises:
            ODPSNormalizationError: If normalization fails with context
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            data_quality = product.get("dataQuality")
            if not isinstance(data_quality, dict):
                # No dataQuality section - this is optional, so just return
                return

            # Initialize quality section in hub_contract
            if "quality" not in hub_contract:
                hub_contract["quality"] = {}

            # Map declarative.default → default_profile_key
            declarative = data_quality.get("declarative")
            if isinstance(declarative, dict):
                default_profile = declarative.get("default")
                if default_profile is not None:
                    if isinstance(default_profile, str):
                        hub_contract["quality"]["default_profile_key"] = default_profile
                    else:
                        warnings.append(
                            f"product.dataQuality.declarative.default has invalid type "
                            f"(expected str, got {type(default_profile).__name__}), skipping"
                        )

                # Map each declarative dimension → quality.rules[]
                dimensions = declarative.get("dimensions")
                if isinstance(dimensions, dict):
                    rules = []
                    for dimension_name, dimension_data in dimensions.items():
                        if not isinstance(dimension_data, dict):
                            warnings.append(
                                f"product.dataQuality.declarative.dimensions.{dimension_name} "
                                f"has invalid type (expected dict, got {type(dimension_data).__name__}), skipping"
                            )
                            continue

                        # Generate rule from dimension
                        rule = self._generate_rule_from_dimension(
                            dimension_name, dimension_data, warnings
                        )
                        if rule:
                            rules.append(rule)

                    if rules:
                        if "rules" not in hub_contract["quality"]:
                            hub_contract["quality"]["rules"] = []
                        hub_contract["quality"]["rules"].extend(rules)

            # Store executable specs in quality.x_odps.executable[]
            executable = data_quality.get("executable")
            if executable is not None:
                # Initialize x_odps extension if not present
                if "x_odps" not in hub_contract["quality"]:
                    hub_contract["quality"]["x_odps"] = {}

                if isinstance(executable, list):
                    hub_contract["quality"]["x_odps"]["executable"] = executable
                elif isinstance(executable, dict):
                    # If executable is a single object, wrap it in a list
                    hub_contract["quality"]["x_odps"]["executable"] = [executable]
                else:
                    warnings.append(
                        f"product.dataQuality.executable has invalid type "
                        f"(expected list or dict, got {type(executable).__name__}), skipping"
                    )

        except Exception as e:
            # Wrap unexpected errors in ODPSNormalizationError
            raise ODPSNormalizationError(
                message=f"Failed to normalize quality section: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/dataQuality",
                cause=e,
            ) from e

    def _generate_rule_from_dimension(
        self, dimension_name: str, dimension_data: dict[str, Any], warnings: list[str]
    ) -> dict[str, Any] | None:
        """
        Generate a quality rule from an ODPS declarative dimension.

        Args:
            dimension_name: Name of the dimension (e.g., "completeness", "accuracy")
            dimension_data: Dimension data dictionary with objectives, units, etc.
            warnings: List to append warnings to

        Returns:
            Quality rule dictionary or None if generation fails
        """
        try:
            rule: dict[str, Any] = {
                "dimension": dimension_name,
            }

            # Extract rule ID/name
            rule_id = (
                dimension_data.get("ruleID") or dimension_data.get("rule_id") or dimension_name
            )
            rule["rule_id"] = str(rule_id)
            rule["name"] = dimension_data.get("name") or dimension_name

            # Extract objectives and generate expression
            objectives = dimension_data.get("objectives")
            if objectives is not None:
                expression = self._generate_expression_from_objectives(
                    objectives, dimension_data.get("unit"), warnings
                )
                if expression:
                    rule["expression"] = expression

            # Extract threshold
            threshold = dimension_data.get("threshold")
            if threshold is not None:
                rule["threshold"] = threshold

            # Extract unit
            unit = dimension_data.get("unit")
            if unit is not None:
                rule["unit"] = str(unit)

            # Extract severity
            severity = dimension_data.get("severity")
            if severity is not None:
                rule["severity"] = str(severity)
            else:
                # Default severity based on dimension type
                rule["severity"] = (
                    "ERROR" if dimension_name in ["completeness", "validity"] else "WARNING"
                )

            # Extract target (column, table, dataset)
            target = dimension_data.get("target")
            if target is not None:
                rule["target"] = str(target)

            # Extract description
            description = dimension_data.get("description")
            if description is not None:
                rule["description"] = str(description)

            # Extract any additional fields
            for key in [
                "operator",
                "valid_values",
                "sql_query",
                "engine",
                "implementation",
                "method",
            ]:
                if key in dimension_data:
                    rule[key] = dimension_data[key]

            return rule

        except Exception as e:
            warnings.append(f"Failed to generate rule from dimension '{dimension_name}': {e!s}")
            return None

    def _generate_expression_from_objectives(
        self, objectives: Any, unit: str | None, warnings: list[str]
    ) -> str | None:
        """
        Generate a rule expression from objectives and unit.

        Args:
            objectives: Objectives data (can be dict, list, or scalar)
            unit: Optional unit string
            warnings: List to append warnings to

        Returns:
            Expression string or None if generation fails
        """
        try:
            if isinstance(objectives, dict):
                # Objectives is a dictionary with keys like "min", "max", "target"
                parts = []
                if "min" in objectives:
                    parts.append(f">= {objectives['min']}")
                if "max" in objectives:
                    parts.append(f"<= {objectives['max']}")
                if "target" in objectives:
                    parts.append(f"== {objectives['target']}")
                if "range" in objectives:
                    range_val = objectives["range"]
                    if isinstance(range_val, (list, tuple)) and len(range_val) == 2:
                        parts.append(f"BETWEEN {range_val[0]} AND {range_val[1]}")

                expression = " AND ".join(parts) if parts else None
                if expression and unit:
                    expression = f"{expression} {unit}"
                return expression

            elif isinstance(objectives, (list, tuple)):
                # Objectives is a list of values
                if unit:
                    return f"IN {objectives} {unit}"
                return f"IN {objectives}"

            elif isinstance(objectives, (int, float)):
                # Objectives is a numeric value
                if unit:
                    return f"== {objectives} {unit}"
                return f"== {objectives}"

            elif isinstance(objectives, str):
                # Objectives is already an expression string
                if unit:
                    return f"{objectives} {unit}"
                return objectives

            else:
                warnings.append(
                    f"Unsupported objectives type: {type(objectives).__name__}, "
                    f"expected dict, list, scalar, or str"
                )
                return None

        except Exception as e:
            warnings.append(f"Failed to generate expression from objectives: {e!s}")
            return None

    def _normalize_lifecycle(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Normalize ODPS lifecycle section to HubContract lifecycle format.

        Maps:
        - product.details.<lang>.status → lifecycle.x_odps.status
        - product.details.<lang>.visibility → lifecycle.x_odps.visibility
        - product.SLA.declarative dimensions → lifecycle.slas and lifecycle.x_odps.sla_dimensions[]
        - product.SLA.executable → lifecycle.x_odps.executable_sla[]

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to

        Raises:
            ODPSNormalizationError: If normalization fails with context
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            # Initialize lifecycle section in hub_contract
            if "lifecycle" not in hub_contract:
                hub_contract["lifecycle"] = {}

            # Initialize x_odps extension if needed
            if "x_odps" not in hub_contract["lifecycle"]:
                hub_contract["lifecycle"]["x_odps"] = {}

            # Extract available languages and get preferred language
            available_languages = self._extract_available_languages(contract_data)
            if available_languages:
                preferred_lang = self._get_preferred_language(available_languages, preferred="en")
                if preferred_lang:
                    details = product.get("details", {})
                    lang_details = details.get(preferred_lang, {})
                    if isinstance(lang_details, dict):
                        # Map status → lifecycle.x_odps.status
                        status = lang_details.get("status")
                        if status is not None:
                            if isinstance(status, str):
                                hub_contract["lifecycle"]["x_odps"]["status"] = status
                            else:
                                warnings.append(
                                    f"product.details.{preferred_lang}.status has invalid type "
                                    f"(expected str, got {type(status).__name__}), skipping"
                                )

                        # Map visibility → lifecycle.x_odps.visibility
                        visibility = lang_details.get("visibility")
                        if visibility is not None:
                            if isinstance(visibility, str):
                                hub_contract["lifecycle"]["x_odps"]["visibility"] = visibility
                            else:
                                warnings.append(
                                    f"product.details.{preferred_lang}.visibility has invalid type "
                                    f"(expected str, got {type(visibility).__name__}), skipping"
                                )

            # Map SLA dimensions → lifecycle.slas and lifecycle.x_odps.sla_dimensions[]
            sla = product.get("SLA")
            if sla is not None:
                if not isinstance(sla, dict):
                    warnings.append(
                        f"product.SLA has invalid type (expected dict, got {type(sla).__name__}), skipping"
                    )
                else:
                    # Map declarative SLA dimensions
                    declarative = sla.get("declarative")
                    if isinstance(declarative, dict):
                        sla_dimensions = []
                        slas_dict = {}

                        dimensions = declarative.get("dimensions")
                        if isinstance(dimensions, dict):
                            for dimension_name, dimension_data in dimensions.items():
                                if not isinstance(dimension_data, dict):
                                    warnings.append(
                                        f"product.SLA.declarative.dimensions.{dimension_name} "
                                        f"has invalid type (expected dict, got {type(dimension_data).__name__}), skipping"
                                    )
                                    continue

                                # Extract dimension data
                                dimension_entry = {"name": dimension_name, "data": dimension_data}

                                # Map common SLA dimensions to lifecycle.slas
                                if dimension_name == "availability":
                                    target = dimension_data.get("target") or dimension_data.get(
                                        "threshold"
                                    )
                                    if target is not None:
                                        try:
                                            slas_dict["availability"] = float(target)
                                        except (ValueError, TypeError):
                                            warnings.append(
                                                f"product.SLA.declarative.dimensions.availability.target "
                                                f"has invalid type (expected number, got {type(target).__name__}), skipping"
                                            )

                                elif (
                                    dimension_name == "latency"
                                    or dimension_name == "latency_ms_p95"
                                ):
                                    target = dimension_data.get("target") or dimension_data.get(
                                        "threshold"
                                    )
                                    if target is not None:
                                        try:
                                            slas_dict["latency_ms_p95"] = float(target)
                                        except (ValueError, TypeError):
                                            warnings.append(
                                                f"product.SLA.declarative.dimensions.{dimension_name}.target "
                                                f"has invalid type (expected number, got {type(target).__name__}), skipping"
                                            )

                                elif dimension_name == "freshness":
                                    target = dimension_data.get("target") or dimension_data.get(
                                        "threshold"
                                    )
                                    if target is not None:
                                        # Freshness might be in seconds, convert if needed
                                        unit = dimension_data.get("unit", "seconds")
                                        try:
                                            target_value = float(target)
                                            if unit in ["hours", "hour", "h"]:
                                                target_value = target_value * 3600
                                            elif unit in ["days", "day", "d"]:
                                                target_value = target_value * 86400
                                            # Store in lifecycle.x_odps for freshness (not in standard slas)
                                            if (
                                                "freshness_sla_seconds"
                                                not in hub_contract["lifecycle"]["x_odps"]
                                            ):
                                                hub_contract["lifecycle"]["x_odps"][
                                                    "freshness_sla_seconds"
                                                ] = target_value
                                        except (ValueError, TypeError):
                                            warnings.append(
                                                f"product.SLA.declarative.dimensions.freshness.target "
                                                f"has invalid type (expected number, got {type(target).__name__}), skipping"
                                            )

                                # Add to sla_dimensions list
                                sla_dimensions.append(dimension_entry)

                        # Set lifecycle.slas if we have standard SLA dimensions
                        if slas_dict:
                            hub_contract["lifecycle"]["slas"] = slas_dict

                        # Store all SLA dimensions in lifecycle.x_odps.sla_dimensions[]
                        if sla_dimensions:
                            hub_contract["lifecycle"]["x_odps"]["sla_dimensions"] = sla_dimensions

                    # Store executable SLA specs
                    executable = sla.get("executable")
                    if executable is not None:
                        if isinstance(executable, list):
                            hub_contract["lifecycle"]["x_odps"]["executable_sla"] = executable
                        elif isinstance(executable, dict):
                            # If executable is a single object, wrap it in a list
                            hub_contract["lifecycle"]["x_odps"]["executable_sla"] = [executable]
                        else:
                            warnings.append(
                                f"product.SLA.executable has invalid type "
                                f"(expected list or dict, got {type(executable).__name__}), skipping"
                            )

        except Exception as e:
            # Wrap unexpected errors in ODPSNormalizationError
            raise ODPSNormalizationError(
                message=f"Failed to normalize lifecycle section: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product",
                cause=e,
            ) from e

    def _extract_contract(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Extract and normalize ODPS contract section.

        Handles three formats:
        - product.contract.$ref → resolve → ODCS → normalize
        - product.contract.spec → inline ODCS → normalize
        - product.contract.contractURL → store pointer

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to

        Raises:
            ODPSNormalizationError: If extraction fails with context
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            contract_section = product.get("contract")
            if not isinstance(contract_section, dict):
                # No contract section - this is optional, so just return
                return

            # Handle contractURL (just store as pointer)
            contract_url = contract_section.get("contractURL")
            if contract_url is not None:
                if isinstance(contract_url, str):
                    # Initialize extensions if needed
                    if "extensions" not in hub_contract:
                        hub_contract["extensions"] = {}
                    if "x_odps" not in hub_contract["extensions"]:
                        hub_contract["extensions"]["x_odps"] = {}
                    hub_contract["extensions"]["x_odps"]["contract_url"] = contract_url
                else:
                    warnings.append(
                        f"product.contract.contractURL has invalid type "
                        f"(expected str, got {type(contract_url).__name__}), skipping"
                    )

            # Handle $ref (resolve and normalize)
            contract_ref = contract_section.get("$ref")
            if contract_ref is not None:
                if not isinstance(contract_ref, str):
                    warnings.append(
                        f"product.contract.$ref has invalid type "
                        f"(expected str, got {type(contract_ref).__name__}), skipping"
                    )
                else:
                    try:
                        # Resolve the $ref
                        resolved_contract = self._resolve_contract_ref(
                            contract_ref, contract_data, warnings
                        )
                        if resolved_contract:
                            # Normalize the resolved ODCS contract
                            self._normalize_extracted_contract(
                                resolved_contract, hub_contract, warnings
                            )
                    except Exception as e:
                        warnings.append(f"Failed to resolve contract $ref '{contract_ref}': {e!s}")
                        logger.warning(
                            "odps_contract_ref_resolution_failed",
                            ref=contract_ref,
                            error=str(e),
                            message="Contract $ref resolution failed",
                        )

            # Handle inline spec
            contract_spec = contract_section.get("spec")
            if contract_spec is not None:
                if isinstance(contract_spec, dict):
                    # Inline ODCS contract
                    self._normalize_extracted_contract(contract_spec, hub_contract, warnings)
                else:
                    warnings.append(
                        f"product.contract.spec has invalid type "
                        f"(expected dict, got {type(contract_spec).__name__}), skipping"
                    )

        except Exception as e:
            # Wrap unexpected errors in ODPSNormalizationError
            raise ODPSNormalizationError(
                message=f"Failed to extract contract section: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/contract",
                cause=e,
            ) from e

    def _resolve_contract_ref(
        self, ref: str, contract_data: dict[str, Any], warnings: list[str]
    ) -> dict[str, Any] | None:
        """
        Resolve a contract $ref reference.

        Args:
            ref: $ref string (e.g., "#/definitions/contract", "./contract.json", "https://example.com/contract.json")
            contract_data: Full ODPS contract data (for internal refs)
            warnings: List to append warnings to

        Returns:
            Resolved contract data (ODCS format) or None if resolution fails
        """
        try:
            from hub.apps.contracts.ref_resolver import ExternalRefHandling, RefResolver
            from hub.apps.contracts.source_paths import resolve_json_pointer

            # Create a RefResolver instance
            # Note: tenant_id and user_id are optional for contract extraction
            resolver = RefResolver(
                tenant_id=None,
                user_id=None,
            )

            # Determine ref mode
            if ref.startswith("#/"):
                # Internal ref - extract value first, then resolve refs within it
                # Convert #/path to /path for JSON Pointer
                json_pointer = ref[1:] if ref.startswith("#") else ref
                extracted_value = resolve_json_pointer(contract_data, json_pointer)

                if extracted_value is None:
                    warnings.append(f"Contract $ref '{ref}' points to non-existent path, skipping")
                    return None

                if not isinstance(extracted_value, dict):
                    warnings.append(f"Contract $ref '{ref}' resolved to non-dict value, skipping")
                    return None

                # Resolve any refs within the extracted contract
                _, resolved = resolver.resolve_all_refs(
                    document=extracted_value, external_ref_handling=ExternalRefHandling.RESOLVE
                )

                if isinstance(resolved, dict):
                    return resolved
                else:
                    warnings.append(
                        f"Contract $ref '{ref}' resolved to non-dict value after ref resolution, skipping"
                    )
                    return None

            elif ref.startswith("./") or ref.startswith("../"):
                # Local ref - resolve using RefResolver
                # Get the base directory from contract_data if available
                base_path = getattr(contract_data, "_base_path", None)
                if base_path:
                    resolved_value = resolver.resolve_local(ref, base_path=base_path)
                else:
                    # Try to resolve without base path (may fail)
                    resolved_value = resolver.resolve_local(ref)

                if isinstance(resolved_value, dict):
                    return resolved_value
                else:
                    warnings.append(
                        f"Contract local $ref '{ref}' resolved to non-dict value, skipping"
                    )
                    return None

            else:
                # External ref - resolve using RefResolver
                resolved_value = resolver.resolve_external(ref)
                if isinstance(resolved_value, dict):
                    return resolved_value
                else:
                    warnings.append(
                        f"Contract external $ref '{ref}' resolved to non-dict value, skipping"
                    )
                    return None

        except Exception as e:
            warnings.append(f"Failed to resolve contract $ref '{ref}': {e!s}")
            logger.warning(
                "odps_contract_ref_resolution_error",
                ref=ref,
                error=str(e),
                message="Contract $ref resolution error",
            )
            return None

    def _normalize_extracted_contract(
        self, odcs_contract: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Normalize extracted ODCS contract using ODCSNormalizer.

        Args:
            odcs_contract: Extracted ODCS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
        """
        try:
            from hub.apps.contracts.normalization_engine import get_normalizer  # noqa: F811

            # Get ODCSNormalizer from registry
            odcs_normalizer = get_normalizer(
                OriginalSpecType.ODCS,
                "3.0.2",  # Default ODCS version
                odcs_contract,
            )

            if not odcs_normalizer:
                warnings.append(
                    "ODCSNormalizer not found in registry, cannot normalize extracted contract"
                )
                return

            # Normalize the ODCS contract
            result = odcs_normalizer.normalize(odcs_contract, spec_version="3.0.2")

            if result.hub_contract:
                # Store normalized contract in extensions.x_odps.contract
                if "extensions" not in hub_contract:
                    hub_contract["extensions"] = {}
                if "x_odps" not in hub_contract["extensions"]:
                    hub_contract["extensions"]["x_odps"] = {}
                hub_contract["extensions"]["x_odps"]["contract"] = result.hub_contract

                # Merge contract errors and warnings
                if result.errors:
                    warnings.extend([f"Contract normalization error: {e}" for e in result.errors])
                if result.warnings:
                    warnings.extend(
                        [f"Contract normalization warning: {w}" for w in result.warnings]
                    )

                logger.debug(
                    "odps_contract_extracted_and_normalized",
                    contract_status=result.status,
                    message="ODPS contract extracted and normalized successfully",
                )
            else:
                warnings.append(
                    f"Contract normalization failed: {', '.join(result.errors) if result.errors else 'Unknown error'}"
                )

        except Exception as e:
            warnings.append(f"Failed to normalize extracted contract: {e!s}")
            logger.warning(
                "odps_contract_normalization_error",
                error=str(e),
                message="Contract normalization error",
            )

    def _extract_available_languages(self, contract_data: dict[str, Any]) -> list[str]:
        """
        Extract available language codes from product.details.

        Args:
            contract_data: Raw ODPS contract data

        Returns:
            List of language codes (ISO 639-1 format, e.g., ["en", "fr", "de"])
        """
        product = contract_data.get("product", {})
        details = product.get("details", {})

        if not isinstance(details, dict):
            return []

        # Extract language codes (keys of details dict)
        languages = [lang for lang in details.keys() if isinstance(lang, str) and len(lang) == 2]
        return sorted(languages)  # Return sorted for consistency

    def _get_preferred_language(
        self, available_languages: list[str], preferred: str = "en"
    ) -> str | None:
        """
        Get preferred language from available languages.

        Args:
            available_languages: List of available language codes
            preferred: Preferred language code (default: "en")

        Returns:
            Preferred language code if available, otherwise first available language, or None
        """
        if not available_languages:
            return None

        # Prefer the specified language if available
        if preferred in available_languages:
            return preferred

        # Fallback to first available language
        return available_languages[0]

    def _normalize_info(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Normalize ODPS product details and dataHolder to HubContract info section.

        Maps:
        - product.details.<lang>.productID → HubContract.id
        - product.details.<lang>.name → HubContract.info.name
        - product.details.<lang>.description → HubContract.info.description
        - product.details.<lang>.productVersion → HubContract.info.version
        - dataHolder.<lang>.legalName → HubContract.info.owners[].name
        - dataHolder.<lang>.email → HubContract.info.owners[].email
        - product.details.<lang>.tags → HubContract.info.tags
        - product.details.<lang>.categories → HubContract.info.tags (merge)

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to populate
            warnings: List to append warnings to

        Raises:
            ODPSNormalizationError: If required fields are missing or invalid
        """
        try:
            # Ensure info section exists
            if "info" not in hub_contract:
                hub_contract["info"] = {}

            # Extract available languages
            available_languages = self._extract_available_languages(contract_data)

            if not available_languages:
                # No languages available - this is a critical error
                raise ODPSNormalizationError(
                    message="No language details found in product.details",
                    error_code=ODPSNormalizationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    field_path="/product/details",
                    context={
                        "expected": "dict with at least one language code",
                        "actual": "empty or missing",
                    },
                )

            # Get preferred language (default to "en", fallback to first available)
            preferred_lang = self._get_preferred_language(available_languages, preferred="en")

            if not preferred_lang:
                raise ODPSNormalizationError(
                    message="Could not determine preferred language",
                    error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                    field_path="/product/details",
                )

            # Get product details for preferred language
            product = contract_data.get("product", {})
            details = product.get("details", {})
            lang_details = details.get(preferred_lang, {})

            if not isinstance(lang_details, dict):
                raise ODPSNormalizationError(
                    message=f"Product details for language '{preferred_lang}' must be a dictionary",
                    error_code=ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED,
                    field_path=f"/product/details/{preferred_lang}",
                    context={
                        "expected": "dict",
                        "actual": type(lang_details).__name__,
                    },
                )

            # Map productID → HubContract.id (required)
            product_id = lang_details.get("productID")
            if product_id:
                if not isinstance(product_id, str):
                    raise ODPSNormalizationError(
                        message=f"productID must be a string, got {type(product_id).__name__}",
                        error_code=ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED,
                        field_path=f"/product/details/{preferred_lang}/productID",
                        context={
                            "expected": "str",
                            "actual": type(product_id).__name__,
                        },
                    )
                hub_contract["id"] = product_id
            else:
                # productID is required in ODPS, but we'll handle gracefully
                warnings.append(
                    f"productID missing in product.details.{preferred_lang}, using fallback"
                )

            # Map name → HubContract.info.name (required)
            name = lang_details.get("name")
            if name:
                if not isinstance(name, str):
                    raise ODPSNormalizationError(
                        message=f"name must be a string, got {type(name).__name__}",
                        error_code=ODPSNormalizationError.ERROR_CODE_TYPE_CONVERSION_FAILED,
                        field_path=f"/product/details/{preferred_lang}/name",
                        context={
                            "expected": "str",
                            "actual": type(name).__name__,
                        },
                    )
                hub_contract["info"]["name"] = name
            else:
                # Name is required - this will cause normalization to fail
                raise ODPSNormalizationError(
                    message=f"name is required in product.details.{preferred_lang}",
                    error_code=ODPSNormalizationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                    field_path=f"/product/details/{preferred_lang}/name",
                )

            # Map description → HubContract.info.description (optional)
            description = lang_details.get("description")
            if description:
                if not isinstance(description, str):
                    warnings.append(
                        f"description in product.details.{preferred_lang} has invalid type "
                        f"(expected str, got {type(description).__name__}), skipping"
                    )
                else:
                    hub_contract["info"]["description"] = description

            # Map productVersion → HubContract.info.version (optional)
            product_version = lang_details.get("productVersion")
            if product_version:
                if not isinstance(product_version, str):
                    warnings.append(
                        f"productVersion in product.details.{preferred_lang} has invalid type "
                        f"(expected str, got {type(product_version).__name__}), skipping"
                    )
                else:
                    hub_contract["info"]["version"] = product_version

            # Map tags → HubContract.info.tags (optional)
            tags = lang_details.get("tags")
            tag_list = []
            if tags:
                if isinstance(tags, list):
                    # Validate all tags are strings
                    valid_tags = []
                    for tag in tags:
                        if isinstance(tag, str):
                            valid_tags.append(tag)
                        else:
                            warnings.append(
                                f"Invalid tag type in product.details.{preferred_lang}.tags "
                                f"(expected str, got {type(tag).__name__}), skipping"
                            )
                    tag_list.extend(valid_tags)
                elif isinstance(tags, str):
                    # Single tag as string
                    tag_list.append(tags)
                else:
                    warnings.append(
                        f"tags in product.details.{preferred_lang} has invalid type "
                        f"(expected list or str, got {type(tags).__name__}), skipping"
                    )

            # Map categories → HubContract.info.tags (merge with tags)
            categories = lang_details.get("categories")
            if categories:
                if isinstance(categories, list):
                    # Validate all categories are strings
                    valid_categories = []
                    for category in categories:
                        if isinstance(category, str):
                            valid_categories.append(category)
                        else:
                            warnings.append(
                                f"Invalid category type in product.details.{preferred_lang}.categories "
                                f"(expected str, got {type(category).__name__}), skipping"
                            )
                    tag_list.extend(valid_categories)
                elif isinstance(categories, str):
                    # Single category as string
                    tag_list.append(categories)
                else:
                    warnings.append(
                        f"categories in product.details.{preferred_lang} has invalid type "
                        f"(expected list or str, got {type(categories).__name__}), skipping"
                    )

            # Set tags (merged from tags and categories)
            if tag_list:
                # Remove duplicates while preserving order
                seen = set()
                unique_tags = []
                for tag in tag_list:
                    if tag not in seen:
                        seen.add(tag)
                        unique_tags.append(tag)
                hub_contract["info"]["tags"] = unique_tags

            # Map dataHolder → HubContract.info.owners (optional)
            data_holder = contract_data.get("dataHolder")
            if data_holder:
                owners = []

                # dataHolder can be a dict keyed by language or a single object
                if isinstance(data_holder, dict):
                    # Check if it's keyed by language codes
                    is_language_keyed = all(
                        isinstance(k, str) and len(k) == 2 and k.islower()
                        for k in data_holder.keys()
                    )

                    if is_language_keyed:
                        # Multilingual dataHolder - use preferred language
                        holder_data = data_holder.get(preferred_lang, {})
                        if not holder_data and available_languages:
                            # Fallback to first available language
                            fallback_lang = available_languages[0]
                            holder_data = data_holder.get(fallback_lang, {})
                    else:
                        # Single dataHolder object (not keyed by language)
                        holder_data = data_holder
                else:
                    # Not a dict - skip
                    warnings.append(
                        f"dataHolder has invalid type (expected dict, got {type(data_holder).__name__}), skipping"
                    )
                    holder_data = None

                if holder_data and isinstance(holder_data, dict):
                    # Extract legalName and email
                    legal_name = holder_data.get("legalName")
                    email = holder_data.get("email")

                    # Create owner object if we have at least one field
                    if legal_name or email:
                        owner = {}
                        if legal_name:
                            if not isinstance(legal_name, str):
                                warnings.append(
                                    f"dataHolder.legalName has invalid type "
                                    f"(expected str, got {type(legal_name).__name__}), skipping"
                                )
                            else:
                                owner["name"] = legal_name

                        if email:
                            if not isinstance(email, str):
                                warnings.append(
                                    f"dataHolder.email has invalid type "
                                    f"(expected str, got {type(email).__name__}), skipping"
                                )
                            else:
                                owner["email"] = email

                        if owner:
                            owners.append(owner)

                if owners:
                    hub_contract["info"]["owners"] = owners

            # Store multilingual information in extensions for future use
            if len(available_languages) > 1:
                if "extensions" not in hub_contract:
                    hub_contract["extensions"] = {}
                if "x_odps" not in hub_contract["extensions"]:
                    hub_contract["extensions"]["x_odps"] = {}
                hub_contract["extensions"]["x_odps"]["available_languages"] = available_languages
                hub_contract["extensions"]["x_odps"]["preferred_language"] = preferred_lang
                # Store all language details for multilingual support
                hub_contract["extensions"]["x_odps"]["multilingual_details"] = {}
                for lang in available_languages:
                    if lang in details and isinstance(details[lang], dict):
                        hub_contract["extensions"]["x_odps"]["multilingual_details"][lang] = (
                            details[lang]
                        )

        except ODPSNormalizationError:
            # Re-raise ODPSNormalizationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSNormalizationError(
                message=f"Unexpected error during info normalization: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/details",
                cause=e,
            ) from e

    def _normalize_marketplace(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Normalize ODPS marketplace and license sections to HubContract marketplace format.

        Maps:
        - license.<lang>.definition → marketplace.license_summary
        - license.<lang>.restrictions → marketplace.restricted_use[]
        - license.<lang>.rights[] → marketplace.intended_use[]
        - product.marketplace.pricingPlans → marketplace.x_odps.pricing_plans[]
        - product.marketplace.accessMethods → marketplace.x_odps.access_methods{}
        - product.marketplace.paymentGateways → marketplace.x_odps.payment_gateways{}

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to

        Raises:
            ODPSNormalizationError: If normalization fails with context
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            # Initialize marketplace section in hub_contract
            if "marketplace" not in hub_contract:
                hub_contract["marketplace"] = {}

            # Initialize x_odps extension if needed
            if "x_odps" not in hub_contract["marketplace"]:
                hub_contract["marketplace"]["x_odps"] = {}

            # Extract available languages and get preferred language
            available_languages = self._extract_available_languages(contract_data)
            preferred_lang = (
                self._get_preferred_language(available_languages, preferred="en")
                if available_languages
                else None
            )

            # Map license section (multilingual, similar to product.details)
            license_data = contract_data.get("license")
            if license_data and isinstance(license_data, dict):
                # Check if license is keyed by language codes
                is_language_keyed = all(
                    isinstance(k, str) and len(k) == 2 and k.islower() for k in license_data.keys()
                )

                if is_language_keyed:
                    # Multilingual license - use preferred language
                    if preferred_lang:
                        lang_license = license_data.get(preferred_lang, {})
                        if not lang_license and available_languages:
                            # Fallback to first available language
                            fallback_lang = available_languages[0]
                            lang_license = license_data.get(fallback_lang, {})
                    # No preferred language, use first available
                    elif available_languages:
                        lang_license = license_data.get(available_languages[0], {})
                    else:
                        lang_license = {}
                else:
                    # Single license object (not keyed by language)
                    lang_license = license_data
            else:
                lang_license = {}

            if isinstance(lang_license, dict):
                # Map license.definition → marketplace.license_summary
                license_definition = lang_license.get("definition")
                if license_definition is not None:
                    if isinstance(license_definition, str):
                        hub_contract["marketplace"]["license_summary"] = license_definition
                    else:
                        warnings.append(
                            f"license.definition has invalid type "
                            f"(expected str, got {type(license_definition).__name__}), skipping"
                        )

                # Map license.restrictions → marketplace.restricted_use[]
                restrictions = lang_license.get("restrictions")
                if restrictions is not None:
                    restricted_use_list = []
                    if isinstance(restrictions, list):
                        # Validate all restrictions are strings
                        for restriction in restrictions:
                            if isinstance(restriction, str):
                                restricted_use_list.append(restriction)
                            else:
                                warnings.append(
                                    f"Invalid restriction type in license.restrictions "
                                    f"(expected str, got {type(restriction).__name__}), skipping"
                                )
                    elif isinstance(restrictions, str):
                        # Single restriction as string
                        restricted_use_list.append(restrictions)
                    else:
                        warnings.append(
                            f"license.restrictions has invalid type "
                            f"(expected list or str, got {type(restrictions).__name__}), skipping"
                        )

                    if restricted_use_list:
                        if "restricted_use" not in hub_contract["marketplace"]:
                            hub_contract["marketplace"]["restricted_use"] = []
                        hub_contract["marketplace"]["restricted_use"].extend(restricted_use_list)

                # Map license.rights[] → marketplace.intended_use[]
                rights = lang_license.get("rights")
                if rights is not None:
                    intended_use_list = []
                    if isinstance(rights, list):
                        # Validate all rights are strings
                        for right in rights:
                            if isinstance(right, str):
                                intended_use_list.append(right)
                            else:
                                warnings.append(
                                    f"Invalid right type in license.rights "
                                    f"(expected str, got {type(right).__name__}), skipping"
                                )
                    elif isinstance(rights, str):
                        # Single right as string
                        intended_use_list.append(rights)
                    else:
                        warnings.append(
                            f"license.rights has invalid type "
                            f"(expected list or str, got {type(rights).__name__}), skipping"
                        )

                    if intended_use_list:
                        if "intended_use" not in hub_contract["marketplace"]:
                            hub_contract["marketplace"]["intended_use"] = []
                        hub_contract["marketplace"]["intended_use"].extend(intended_use_list)

            # Map product.marketplace.pricingPlans → marketplace.x_odps.pricing_plans[]
            marketplace = product.get("marketplace")
            if isinstance(marketplace, dict):
                pricing_plans = marketplace.get("pricingPlans")
                if pricing_plans is not None:
                    if isinstance(pricing_plans, list):
                        # Validate all pricing plans are dicts
                        valid_plans = []
                        for plan in pricing_plans:
                            if isinstance(plan, dict):
                                valid_plans.append(plan)
                            else:
                                warnings.append(
                                    f"Invalid pricing plan type "
                                    f"(expected dict, got {type(plan).__name__}), skipping"
                                )
                        if valid_plans:
                            hub_contract["marketplace"]["x_odps"]["pricing_plans"] = valid_plans
                    elif isinstance(pricing_plans, dict):
                        # Single pricing plan as object, wrap in list
                        hub_contract["marketplace"]["x_odps"]["pricing_plans"] = [pricing_plans]
                    else:
                        warnings.append(
                            f"product.marketplace.pricingPlans has invalid type "
                            f"(expected list or dict, got {type(pricing_plans).__name__}), skipping"
                        )

                # Map product.marketplace.accessMethods → marketplace.x_odps.access_methods{}
                access_methods = marketplace.get("accessMethods")
                if access_methods is not None:
                    if isinstance(access_methods, dict):
                        hub_contract["marketplace"]["x_odps"]["access_methods"] = access_methods
                    else:
                        warnings.append(
                            f"product.marketplace.accessMethods has invalid type "
                            f"(expected dict, got {type(access_methods).__name__}), skipping"
                        )

                # Map product.marketplace.paymentGateways → marketplace.x_odps.payment_gateways{}
                payment_gateways = marketplace.get("paymentGateways")
                if payment_gateways is not None:
                    if isinstance(payment_gateways, dict):
                        hub_contract["marketplace"]["x_odps"]["payment_gateways"] = payment_gateways
                    else:
                        warnings.append(
                            f"product.marketplace.paymentGateways has invalid type "
                            f"(expected dict, got {type(payment_gateways).__name__}), skipping"
                        )

        except Exception as e:
            # Wrap unexpected errors in ODPSNormalizationError
            raise ODPSNormalizationError(
                message=f"Failed to normalize marketplace section: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/marketplace",
                cause=e,
            ) from e

    def _normalize_schema_minimal(
        self, contract_data: dict[str, Any], hub_contract: dict[str, Any], warnings: list[str]
    ) -> None:
        """
        Minimal schema normalization - populate schema fields from product.dataSchema or product.contract.spec.schema if available.

        This extracts schema fields from:
        1. product.dataSchema.fields (if present)
        2. product.contract.spec.schema.fields (if present, for ODCS contracts embedded in ODPS)

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            # Ensure schema section exists
            if "schema" not in hub_contract:
                hub_contract["schema"] = {}

            # Try product.dataSchema first
            data_schema = product.get("dataSchema")
            if isinstance(data_schema, dict):
                fields = data_schema.get("fields")
                if isinstance(fields, list) and fields:
                    # Copy fields to hub_contract schema
                    hub_contract["schema"]["fields"] = fields
                    return  # Found fields, done

            # Try product.contract.spec.schema (ODCS contract embedded in ODPS)
            contract_section = product.get("contract", {})
            if isinstance(contract_section, dict):
                contract_spec = contract_section.get("spec", {})
                if isinstance(contract_spec, dict):
                    contract_schema = contract_spec.get("schema", {})
                    if isinstance(contract_schema, dict):
                        fields = contract_schema.get("fields")
                        if isinstance(fields, list) and fields:
                            # Convert ODCS field format (type) to HubContract format (data_type)
                            # This is a minimal conversion - full normalization happens in _extract_contract
                            converted_fields = []
                            for field in fields:
                                if isinstance(field, dict):
                                    hub_field = {
                                        "name": field.get("name", ""),
                                        "data_type": field.get("type", "string"),
                                        "nullable": field.get("nullable", True),
                                    }
                                    # Copy other properties if present
                                    for prop in [
                                        "description",
                                        "format",
                                        "pattern",
                                        "enum",
                                        "default",
                                    ]:
                                        if prop in field:
                                            hub_field[prop] = field[prop]
                                    # Handle minLength/maxLength -> min_length/max_length
                                    if "minLength" in field:
                                        hub_field["min_length"] = field["minLength"]
                                    if "maxLength" in field:
                                        hub_field["max_length"] = field["maxLength"]
                                    converted_fields.append(hub_field)
                            if converted_fields:
                                hub_contract["schema"]["fields"] = converted_fields
                                return  # Found fields, done

        except Exception as e:
            # Don't fail normalization if schema extraction fails
            warnings.append(f"Failed to extract schema: {e!s}")

    def _normalize_product_strategy(
        self,
        contract_data: dict[str, Any],
        hub_contract: dict[str, Any],
        warnings: list[str],
        spec_version: str,
    ) -> None:
        """
        Normalize ODPS product strategy to HubContract info.x_odps.product_strategy.

        Maps (ODPS 4.1+ only):
        - productStrategy.objectives[] → info.x_odps.product_strategy.objectives[]
        - productStrategy.strategicAlignment[] → info.x_odps.product_strategy.strategicAlignment[]
        - productStrategy.productKPIs[] → info.x_odps.product_strategy.productKPIs[]

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to populate
            warnings: List to append warnings to
            spec_version: ODPS spec version (e.g., "4.1", "4.0")

        Raises:
            ODPSNormalizationError: If normalization fails with context
        """
        try:
            # Product strategy is only available in ODPS 4.1+
            # Check version: 4.1 or higher
            try:
                version_parts = spec_version.split(".")
                major_version = int(version_parts[0]) if version_parts else 0
                minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

                # Only process if version is 4.1 or higher
                if major_version < 4 or (major_version == 4 and minor_version < 1):
                    # Product strategy not supported in this version, skip silently
                    return
            except (ValueError, IndexError):
                # Version parsing failed, assume 4.1+ and continue
                logger.debug(
                    "odps_version_parse_failed",
                    spec_version=spec_version,
                    message="Failed to parse version, assuming 4.1+ for product strategy",
                )

            # Get productStrategy from contract_data
            # In ODPS, productStrategy is under product.productStrategy
            product = contract_data.get("product", {})
            if isinstance(product, dict):
                product_strategy = product.get("productStrategy")
            else:
                product_strategy = None

            if product_strategy is None:
                # Product strategy is optional, no warning needed
                return

            if not isinstance(product_strategy, dict):
                warnings.append(
                    f"productStrategy has invalid type "
                    f"(expected dict, got {type(product_strategy).__name__}), skipping"
                )
                return

            # Ensure info section exists
            if "info" not in hub_contract:
                hub_contract["info"] = {}

            # Ensure x_odps extension exists
            if "extensions" not in hub_contract:
                hub_contract["extensions"] = {}
            if "x_odps" not in hub_contract["extensions"]:
                hub_contract["extensions"]["x_odps"] = {}

            # Initialize product_strategy structure
            if "product_strategy" not in hub_contract["extensions"]["x_odps"]:
                hub_contract["extensions"]["x_odps"]["product_strategy"] = {}

            # Map objectives[]
            objectives = product_strategy.get("objectives")
            if objectives is not None:
                if isinstance(objectives, list):
                    # Validate all objectives are valid (strings or objects)
                    valid_objectives = []
                    for idx, objective in enumerate(objectives):
                        if isinstance(objective, (str, dict)):
                            valid_objectives.append(objective)
                        else:
                            warnings.append(
                                f"productStrategy.objectives[{idx}] has invalid type "
                                f"(expected str or dict, got {type(objective).__name__}), skipping"
                            )
                    if valid_objectives:
                        hub_contract["extensions"]["x_odps"]["product_strategy"]["objectives"] = (
                            valid_objectives
                        )
                elif isinstance(objectives, str):
                    # Single objective as string
                    hub_contract["extensions"]["x_odps"]["product_strategy"]["objectives"] = [
                        objectives
                    ]
                else:
                    warnings.append(
                        f"productStrategy.objectives has invalid type "
                        f"(expected list or str, got {type(objectives).__name__}), skipping"
                    )

            # Map strategicAlignment[]
            strategic_alignment = product_strategy.get("strategicAlignment")
            if strategic_alignment is not None:
                if isinstance(strategic_alignment, list):
                    # Validate all strategic alignment items are valid (strings or objects)
                    valid_alignment = []
                    for idx, alignment in enumerate(strategic_alignment):
                        if isinstance(alignment, (str, dict)):
                            valid_alignment.append(alignment)
                        else:
                            warnings.append(
                                f"productStrategy.strategicAlignment[{idx}] has invalid type "
                                f"(expected str or dict, got {type(alignment).__name__}), skipping"
                            )
                    if valid_alignment:
                        hub_contract["extensions"]["x_odps"]["product_strategy"][
                            "strategicAlignment"
                        ] = valid_alignment
                elif isinstance(strategic_alignment, str):
                    # Single strategic alignment as string
                    hub_contract["extensions"]["x_odps"]["product_strategy"][
                        "strategicAlignment"
                    ] = [strategic_alignment]
                else:
                    warnings.append(
                        f"productStrategy.strategicAlignment has invalid type "
                        f"(expected list or str, got {type(strategic_alignment).__name__}), skipping"
                    )

            # Map productKPIs[]
            product_kpis = product_strategy.get("productKPIs")
            if product_kpis is not None:
                if isinstance(product_kpis, list):
                    # Validate all KPIs are valid (strings or objects)
                    valid_kpis = []
                    for idx, kpi in enumerate(product_kpis):
                        if isinstance(kpi, (str, dict)):
                            valid_kpis.append(kpi)
                        else:
                            warnings.append(
                                f"productStrategy.productKPIs[{idx}] has invalid type "
                                f"(expected str or dict, got {type(kpi).__name__}), skipping"
                            )
                    if valid_kpis:
                        hub_contract["extensions"]["x_odps"]["product_strategy"]["productKPIs"] = (
                            valid_kpis
                        )
                elif isinstance(product_kpis, str):
                    # Single KPI as string
                    hub_contract["extensions"]["x_odps"]["product_strategy"]["productKPIs"] = [
                        product_kpis
                    ]
                else:
                    warnings.append(
                        f"productStrategy.productKPIs has invalid type "
                        f"(expected list or str, got {type(product_kpis).__name__}), skipping"
                    )

            # Only create product_strategy structure if at least one field was mapped
            if not hub_contract["extensions"]["x_odps"]["product_strategy"]:
                # No fields were mapped, remove empty structure
                del hub_contract["extensions"]["x_odps"]["product_strategy"]

        except ODPSNormalizationError:
            # Re-raise ODPSNormalizationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSNormalizationError(
                message=f"Unexpected error during product strategy normalization: {e!s}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/productStrategy",
                cause=e,
            ) from e
