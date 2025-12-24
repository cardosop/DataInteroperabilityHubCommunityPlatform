"""
ODPS Normalizer Base Class

Abstract base class for version-specific ODPS normalizers.
Provides common normalization logic and defines hooks for version-specific implementations.
"""
import structlog
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.odps_errors import ODPSNormalizationError
from hub.apps.contracts.odps_version_detection import detect_odps_version

# Import from normalization.py module (avoiding circular import with normalization package)
# The issue: 'hub.apps.contracts.normalization' resolves to the package, not the .py file
# Solution: Import the .py file directly using importlib and file path
import importlib.util
from pathlib import Path

# Get the path to normalization.py (parent directory)
_normalization_py_path = Path(__file__).parent.parent / 'normalization.py'

# Load the .py file as a separate module
_spec = importlib.util.spec_from_file_location('normalization_py_module', _normalization_py_path)
_normalization_py_module = importlib.util.module_from_spec(_spec)

# Set the module's __package__ to avoid relative import issues
_normalization_py_module.__package__ = 'hub.apps.contracts'

# Execute the module (this will run its imports)
_spec.loader.exec_module(_normalization_py_module)

# Extract the classes we need
NormalizationResult = _normalization_py_module.NormalizationResult
SpecNormalizer = _normalization_py_module.SpecNormalizer

logger = structlog.get_logger(__name__)


class ODPSNormalizerBase(ABC):
    """
    Abstract base class for version-specific ODPS normalizers.

    Provides common normalization logic and defines hooks for version-specific implementations.
    Subclasses must implement:
    - `_supports_version()`: Check if this normalizer supports a specific ODPS version
    - Optionally override `_map_version_specific_fields()` for version-specific mappings

    Common functionality provided:
    - Version detection and validation
    - Contract data validation
    - HubContract structure initialization
    - Common normalization methods (info, quality, lifecycle, marketplace, contract extraction)
    - Error handling and status determination
    - Helper methods for field normalization
    """

    spec_type: str = OriginalSpecType.ODPS

    @abstractmethod
    def _supports_version(self, spec_version: str) -> bool:
        """
        Check if this normalizer supports the given ODPS version.

        This is the primary hook for version-specific normalizers.
        Subclasses must implement this to indicate which versions they support.

        Args:
            spec_version: ODPS specification version (e.g., "4.1", "4.0", "3.x")

        Returns:
            True if this normalizer supports the version, False otherwise

        Examples:
            - ODPS 4.1 normalizer: return spec_version == "4.1"
            - ODPS 4.0 normalizer: return spec_version == "4.0"
            - ODPS 3.x normalizer: return spec_version.startswith("3.")
        """
        pass

    def supports(self, spec_type: str, spec_version: str, contract_data: Dict[str, Any]) -> bool:
        """
        Check if this normalizer supports the given spec type and version.

        This method implements the SpecNormalizer protocol. It checks:
        1. If the spec_type matches ODPS
        2. If this normalizer supports the specific version (via _supports_version hook)

        Args:
            spec_type: Specification type (e.g., "ODPS")
            spec_version: Specification version (e.g., "4.1")
            contract_data: Contract data dictionary (not used in base implementation)

        Returns:
            True if this normalizer supports the spec type and version, False otherwise
        """
        if spec_type != self.spec_type:
            return False

        return self._supports_version(spec_version)

    def normalize(
        self,
        contract_data: Dict[str, Any],
        spec_version: Optional[str] = None
    ) -> NormalizationResult:
        """
        Normalize ODPS contract data to HubContract format.

        This is the main entry point for ODPS normalization. It handles:
        - Version detection if not provided
        - Error handling with context (field names, expected types)
        - Graceful degradation for missing optional fields
        - Type validation and conversion
        - Field mapping errors
        - Version-specific field mappings (via hook)

        Args:
            contract_data: Raw ODPS contract data (dict)
            spec_version: Optional spec version (auto-detected if not provided)

        Returns:
            NormalizationResult with hub_contract, status, errors, warnings, etc.

        Raises:
            ODPSNormalizationError: For normalization errors with context
        """
        errors: List[str] = []
        warnings: List[str] = []
        hub_contract: Optional[Dict[str, Any]] = None

        try:
            # Detect ODPS version if not provided
            if spec_version is None:
                try:
                    detected_version = detect_odps_version(contract_data)
                    spec_version = detected_version or "4.1"  # Default to 4.1
                except Exception as e:
                    error_msg = f"Failed to detect ODPS version: {str(e)}"
                    logger.warning(
                        "odps_version_detection_failed",
                        error=str(e),
                        message=error_msg
                    )
                    warnings.append(error_msg)
                    spec_version = "4.1"  # Default fallback

            # Check if this normalizer supports the detected/provided version
            if not self._supports_version(spec_version):
                error_msg = (
                    f"This normalizer does not support ODPS version '{spec_version}'. "
                    f"Use a version-specific normalizer for this version."
                )
                errors.append(error_msg)
                logger.error(
                    "odps_version_not_supported",
                    spec_version=spec_version,
                    normalizer_class=self.__class__.__name__,
                    message=error_msg
                )
                return NormalizationResult(
                    hub_contract=None,
                    status=NormalizationStatus.NORMALIZATION_FAILED,
                    errors=errors,
                    warnings=warnings,
                    spec_type=self.spec_type,
                    spec_version=spec_version,
                    coverage=None
                )

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

            # Normalize contract sections (common across all versions)
            # Task 1.4.2: ODPS → HubContract info mapping
            self._normalize_info(contract_data, hub_contract, warnings)
            # Task 1.4.3: ODPS → HubContract quality mapping
            self._normalize_quality(contract_data, hub_contract, warnings)
            # Task 1.4.4: ODPS → HubContract lifecycle mapping
            self._normalize_lifecycle(contract_data, hub_contract, warnings)
            # Task 1.4.5: ODPS → HubContract marketplace mapping
            self._normalize_marketplace(contract_data, hub_contract, warnings)
            # Minimal schema normalization (populate from product.dataSchema if available)
            self._normalize_schema_minimal(contract_data, hub_contract, warnings)
            # Task 1.4.6: ODPS contract extraction
            self._extract_contract(contract_data, hub_contract, warnings)

            # Version-specific field mappings (hook for subclasses)
            self._map_version_specific_fields(contract_data, hub_contract, warnings, spec_version)

            # Determine normalization status
            status = self._determine_status(hub_contract, errors, warnings)

            # Calculate coverage (placeholder for now)
            coverage = None
            if hub_contract:
                try:
                    from hub.apps.contracts.coverage import calculate_coverage
                    coverage_result = calculate_coverage(hub_contract, spec_type=OriginalSpecType.ODPS)
                    if coverage_result:
                        coverage = {
                            "overall": coverage_result.overall,
                            "sections": coverage_result.sections,
                        }
                except Exception as e:
                    logger.debug(
                        "odps_coverage_calculation_failed",
                        error=str(e),
                        message="Coverage calculation failed, continuing without coverage"
                    )

            return NormalizationResult(
                hub_contract=hub_contract,
                status=status,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version,
                coverage=coverage
            )

        except ODPSNormalizationError as e:
            # Re-raise ODPSNormalizationError with full context
            errors.append(str(e))
            logger.error(
                "odps_normalization_error",
                error_code=e.error_code,
                field_path=e.context.get("field_path") if e.context else None,
                message=str(e),
                context=e.context
            )
            return NormalizationResult(
                hub_contract=None,
                status=NormalizationStatus.NORMALIZATION_FAILED,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version or "4.1",
                coverage=None
            )
        except Exception as e:
            # Catch any unexpected errors and wrap in ODPSNormalizationError
            error = ODPSNormalizationError(
                message=f"Unexpected error during ODPS normalization: {str(e)}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                cause=e,
            )
            errors.append(str(error))
            logger.error(
                "odps_normalization_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                message="Unexpected error during normalization"
            )
            return NormalizationResult(
                hub_contract=None,
                status=NormalizationStatus.NORMALIZATION_FAILED,
                errors=errors,
                warnings=warnings,
                spec_type=self.spec_type,
                spec_version=spec_version or "4.1",
                coverage=None
            )

    def _map_version_specific_fields(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
    ) -> None:
        """
        Hook for version-specific field mappings.

        Subclasses can override this method to implement version-specific mappings
        that are not common across all ODPS versions. This is called after all
        common normalization methods.

        Default implementation handles product strategy (ODPS 4.1+).
        Subclasses can override to add version-specific logic or to handle
        different versions of product strategy.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
            spec_version: ODPS spec version (e.g., "4.1", "4.0")
        """
        # Default implementation: handle product strategy for 4.1+
        self._normalize_product_strategy(contract_data, hub_contract, warnings, spec_version)

    def _initialize_hub_contract(
        self,
        contract_data: Dict[str, Any],
        spec_version: str
    ) -> Dict[str, Any]:
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
                "schema": {
                    "fields": []
                },
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
                message=f"Failed to initialize HubContract structure: {str(e)}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/",
                cause=e,
            ) from e

    def _determine_status(
        self,
        hub_contract: Optional[Dict[str, Any]],
        errors: List[str],
        warnings: List[str]
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
        required: bool = False
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
        warnings: Optional[List[str]] = None
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
                warnings.append(f"Optional field '{field_name}' at path '{field_path}' is missing, using default value")
            logger.debug(
                "odps_optional_field_missing",
                field_name=field_name,
                field_path=field_path,
                message=f"Optional field '{field_name}' missing, using default"
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
                message=f"Optional field '{field_name}' has invalid type, using default"
            )
            return default_value

        return value

    # Common normalization methods (shared across all versions)
    # These methods are implemented in the base class and can be overridden
    # by subclasses if version-specific behavior is needed.

    def _normalize_info(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
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
                warnings.append(f"productID missing in product.details.{preferred_lang}, using fallback")

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
                        hub_contract["extensions"]["x_odps"]["multilingual_details"][lang] = details[lang]

        except ODPSNormalizationError:
            # Re-raise ODPSNormalizationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ODPSNormalizationError(
                message=f"Unexpected error during info normalization: {str(e)}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/details",
                cause=e,
            ) from e

    def _normalize_quality(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
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
                message=f"Failed to normalize quality section: {str(e)}",
                error_code=ODPSNormalizationError.ERROR_CODE_NORMALIZATION_FAILED,
                field_path="/product/dataQuality",
                cause=e,
            ) from e

    def _generate_rule_from_dimension(
        self,
        dimension_name: str,
        dimension_data: Dict[str, Any],
        warnings: List[str]
    ) -> Optional[Dict[str, Any]]:
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
            rule: Dict[str, Any] = {
                "dimension": dimension_name,
            }

            # Extract rule ID/name
            rule_id = dimension_data.get("ruleID") or dimension_data.get("rule_id") or dimension_name
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
                rule["severity"] = "ERROR" if dimension_name in ["completeness", "validity"] else "WARNING"

            # Extract target (column, table, dataset)
            target = dimension_data.get("target")
            if target is not None:
                rule["target"] = str(target)

            # Extract description
            description = dimension_data.get("description")
            if description is not None:
                rule["description"] = str(description)

            # Extract any additional fields
            for key in ["operator", "valid_values", "sql_query", "engine", "implementation", "method"]:
                if key in dimension_data:
                    rule[key] = dimension_data[key]

            return rule

        except Exception as e:
            warnings.append(
                f"Failed to generate rule from dimension '{dimension_name}': {str(e)}"
            )
            return None

    def _generate_expression_from_objectives(
        self,
        objectives: Any,
        unit: Optional[str],
        warnings: List[str]
    ) -> Optional[str]:
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
            warnings.append(
                f"Failed to generate expression from objectives: {str(e)}"
            )
            return None

    def _normalize_lifecycle(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
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
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        temp_normalizer._normalize_lifecycle(contract_data, hub_contract, warnings)

    def _normalize_marketplace(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
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
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        temp_normalizer._normalize_marketplace(contract_data, hub_contract, warnings)

    def _extract_contract(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
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
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        temp_normalizer._extract_contract(contract_data, hub_contract, warnings)

    def _normalize_product_strategy(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str],
        spec_version: str
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
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        temp_normalizer._normalize_product_strategy(contract_data, hub_contract, warnings, spec_version)

    def _normalize_schema_minimal(
        self,
        contract_data: Dict[str, Any],
        hub_contract: Dict[str, Any],
        warnings: List[str]
    ) -> None:
        """
        Minimal schema normalization - populate schema fields from product.dataSchema if available.

        This is a minimal implementation to support tests. Full schema normalization
        will be implemented in a separate task.

        Args:
            contract_data: Raw ODPS contract data
            hub_contract: HubContract dictionary to update
            warnings: List to append warnings to
        """
        try:
            product = contract_data.get("product", {})
            if not isinstance(product, dict):
                return

            data_schema = product.get("dataSchema")
            if isinstance(data_schema, dict):
                fields = data_schema.get("fields")
                if isinstance(fields, list) and fields:
                    # Ensure schema section exists
                    if "schema" not in hub_contract:
                        hub_contract["schema"] = {}
                    # Copy fields to hub_contract schema
                    hub_contract["schema"]["fields"] = fields
        except Exception as e:
            # Don't fail normalization if schema extraction fails
            warnings.append(f"Failed to extract schema from product.dataSchema: {str(e)}")

    # Helper methods for language extraction (shared across all versions)

    def _extract_available_languages(self, contract_data: Dict[str, Any]) -> List[str]:
        """
        Extract available language codes from product.details.

        Args:
            contract_data: Raw ODPS contract data

        Returns:
            List of language codes (ISO 639-1 format, e.g., ["en", "fr", "de"])
        """
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        return temp_normalizer._extract_available_languages(contract_data)

    def _get_preferred_language(self, available_languages: List[str], preferred: str = "en") -> Optional[str]:
        """
        Get preferred language from available languages.

        Args:
            available_languages: List of available language codes
            preferred: Preferred language code (default: "en")

        Returns:
            Preferred language code if available, otherwise first available language, or None
        """
        from hub.apps.contracts.normalization.odps_normalizer import ODPSNormalizer
        temp_normalizer = ODPSNormalizer()
        return temp_normalizer._get_preferred_language(available_languages, preferred)

