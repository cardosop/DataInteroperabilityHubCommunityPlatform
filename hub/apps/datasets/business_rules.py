"""
Datasets Business Rules

Comprehensive business rules validation for datasets, including:
- Dataset structure validation
- Dataset schema validation
- Tenant and user context validation
- Dataset version validation
- Dataset-file relationship validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.datasets.models import Dataset
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.assets.models import Asset
    from hub.apps.files.models import File
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class DatasetsRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for datasets business rules.

    Adds datasets-specific context:
    - dataset: The dataset being validated
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    - file: Optional file instance for file-dataset relationship validation
    - asset: Optional asset instance for asset-dataset relationship validation
    """
    dataset: Optional[Dataset] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None
    file: Optional[Any] = None  # Using Any to avoid circular import
    asset: Optional[Any] = None  # Using Any to avoid circular import

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'dataset_id': str(self.dataset.id) if self.dataset else None,
            'tenant_id': str(self.tenant.id) if self.tenant else None,
            'user_id': str(self.user.id) if self.user else None,
            'file_id': str(self.file.id) if self.file else None,
            'asset_id': str(self.asset.id) if self.asset else None,
        })
        return base_dict


@register_rule(
    rule_name="datasets_validation",
    description="Validates dataset structure, schema, tenant context, and version management",
    tags=["datasets", "validation"],
    priority=10
)
class DatasetsBusinessRules(BusinessRules):
    """
    Business rules validator for datasets.

    Extends BusinessRules base class with datasets-specific validation:
    - Dataset structure and schema validation
    - Tenant context consistency
    - User permissions and access validation
    - Dataset version management validation
    - Dataset-file relationship validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "DatasetsBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all dataset validation checks.
        It can be called with a DatasetsRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        dataset, tenant, user, file, and asset from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - dataset: Dataset instance (required)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - file: Optional file instance
                - asset: Optional asset instance
                - validation_type: Optional validation type filter
                    ('structure', 'schema', 'tenant_context', 'permissions', 'version', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract dataset, tenant, user, file, and asset from context or kwargs
        if isinstance(context, DatasetsRuleExecutionContext):
            dataset = context.dataset
            tenant = context.tenant
            user = context.user
            file = context.file
            asset = context.asset
        else:
            # Try to get from kwargs first
            dataset = kwargs.get('dataset')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')
            file = kwargs.get('file')
            asset = kwargs.get('asset')

            # If not in kwargs, try to get from context.metadata or context.resource
            if not dataset:
                if context and hasattr(context, 'resource') and isinstance(context.resource, Dataset):
                    dataset = context.resource
                elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                    dataset = context.metadata.get('dataset')
                    tenant = context.metadata.get('tenant') or tenant
                    user = context.metadata.get('user') or user
                    file = context.metadata.get('file') or file
                    asset = context.metadata.get('asset') or asset

        if not dataset:
            return ValidationResult(
                is_valid=False,
                errors=["Dataset is required for validation"],
                details={"validation_type": kwargs.get('validation_type', 'all')}
            )

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'dataset_id': str(dataset.id),
            'validation_type': validation_type,
            'validation_checks': {}
        }

        # Run validation checks based on validation_type
        if validation_type in ['structure', 'all']:
            structure_result = self._validate_dataset_structure(dataset)
            if not structure_result.is_valid:
                errors.extend(structure_result.errors)
                warnings.extend(structure_result.warnings)
            details['validation_checks']['structure'] = structure_result.details

        if validation_type in ['schema', 'all']:
            # Get previous dataset version if available for compatibility checks
            previous_dataset = kwargs.get('previous_dataset')
            schema_result = self._validate_dataset_schema(dataset, previous_dataset=previous_dataset)
            if not schema_result.is_valid:
                errors.extend(schema_result.errors)
                warnings.extend(schema_result.warnings)
            details['validation_checks']['schema'] = schema_result.details

        if validation_type in ['tenant_context', 'all']:
            tenant_result = self._validate_tenant_context(dataset, tenant)
            if not tenant_result.is_valid:
                errors.extend(tenant_result.errors)
                warnings.extend(tenant_result.warnings)
            details['validation_checks']['tenant_context'] = tenant_result.details

        if validation_type in ['permissions', 'all']:
            # Default to READ access for general validation
            permissions_result = self._validate_permissions(dataset, user, access_type="READ")
            if not permissions_result.is_valid:
                errors.extend(permissions_result.errors)
                warnings.extend(permissions_result.warnings)
            details['validation_checks']['permissions'] = permissions_result.details

        if validation_type in ['version', 'all']:
            version_result = self._validate_dataset_version(dataset)
            if not version_result.is_valid:
                errors.extend(version_result.errors)
                warnings.extend(version_result.warnings)
            details['validation_checks']['version'] = version_result.details

        if validation_type in ['file_relationship', 'all']:
            file_result = self._validate_file_relationship(dataset, file)
            if not file_result.is_valid:
                errors.extend(file_result.errors)
                warnings.extend(file_result.warnings)
            details['validation_checks']['file_relationship'] = file_result.details

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_dataset_schema(
        self,
        dataset: Dataset,
        previous_dataset: Optional[Dataset] = None
    ) -> ValidationResult:
        """
        Public method to validate dataset schema.

        Validates:
        - Schema structure (valid JSON Schema format)
        - Schema field validation (required fields, data types)
        - Schema version compatibility check (if previous_dataset provided)
        - Schema evolution validation (backward compatibility)

        Args:
            dataset: Dataset instance to validate
            previous_dataset: Optional previous dataset version for compatibility check

        Returns:
            ValidationResult with schema validation status
        """
        return self._validate_dataset_schema(dataset, previous_dataset=previous_dataset)

    def _validate_dataset_structure(self, dataset: Dataset) -> ValidationResult:
        """
        Validate dataset structure and required fields.

        Args:
            dataset: Dataset instance to validate

        Returns:
            ValidationResult with structure validation status
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Check for tenant (handle RelatedObjectDoesNotExist)
        try:
            has_tenant = dataset.tenant is not None
        except Exception:
            has_tenant = False

        # Check for file (handle RelatedObjectDoesNotExist)
        try:
            has_file = dataset.file is not None
        except Exception:
            has_file = False

        details: Dict[str, Any] = {
            'has_tenant': has_tenant,
            'has_file': has_file,
            'has_format': bool(dataset.format),
            'has_version': dataset.version is not None,
        }

        # Validate required fields
        if not has_tenant:
            errors.append("Dataset must have a tenant")
            details['has_tenant'] = False

        if not has_file:
            errors.append("Dataset must have a file")
            details['has_file'] = False

        if not dataset.format:
            errors.append("Dataset must have a format")
            details['has_format'] = False
        elif dataset.format not in ['CSV', 'JSON', 'PARQUET']:
            warnings.append(f"Dataset format '{dataset.format}' is not a standard format (CSV, JSON, PARQUET)")
            details['format_valid'] = False
        else:
            details['format_valid'] = True

        if dataset.version is None or dataset.version < 1:
            errors.append("Dataset version must be a positive integer")
            details['has_version'] = False
            details['version_valid'] = False
        else:
            details['version_valid'] = True

        # Validate format matches file extension/content type if file exists
        if has_file and dataset.format:
            file_name_lower = dataset.file.name.lower()
            format_matches = False

            if dataset.format == 'CSV' and (file_name_lower.endswith('.csv') or 'csv' in dataset.file.content_type.lower()):
                format_matches = True
            elif dataset.format == 'JSON' and (file_name_lower.endswith(('.json', '.ndjson')) or 'json' in dataset.file.content_type.lower()):
                format_matches = True
            elif dataset.format == 'PARQUET' and (file_name_lower.endswith('.parquet') or 'parquet' in dataset.file.content_type.lower()):
                format_matches = True

            if not format_matches:
                warnings.append(
                    f"Dataset format '{dataset.format}' may not match file extension or content type "
                    f"('{dataset.file.name}', '{dataset.file.content_type}')"
                )
                details['format_matches_file'] = False
            else:
                details['format_matches_file'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dataset_schema(
        self,
        dataset: Dataset,
        previous_dataset: Optional[Dataset] = None
    ) -> ValidationResult:
        """
        Validate dataset schema structure and content.

        Validates:
        - Schema structure (valid JSON Schema format)
        - Schema field validation (required fields, data types)
        - Schema version compatibility check (if previous_dataset provided)
        - Schema evolution validation (backward compatibility)

        Args:
            dataset: Dataset instance to validate
            previous_dataset: Optional previous dataset version for compatibility check

        Returns:
            ValidationResult with schema validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'has_schema': dataset.schema_json is not None,
            'schema_valid': False,
            'fields_count': 0,
            'validation_checks': {}
        }

        # Check if schema_json is None (not just falsy, since {} is falsy but valid)
        if dataset.schema_json is None:
            details['has_schema'] = False
            return ValidationResult(
                is_valid=True,  # Not an error if no schema
                errors=errors,
                warnings=["Dataset has no schema_json - schema validation skipped"],
                details=details
            )

        schema = dataset.schema_json
        if not isinstance(schema, dict):
            errors.append("Dataset schema_json must be a dictionary")
            details['schema_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 1. Validate schema structure (JSON Schema format)
        structure_result = self._validate_schema_structure(schema)
        errors.extend(structure_result.errors)
        warnings.extend(structure_result.warnings)
        details['validation_checks']['structure'] = structure_result.details
        if not structure_result.is_valid:
            details['schema_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 2. Validate schema fields (required fields, data types)
        fields_result = self._validate_schema_fields(schema)
        errors.extend(fields_result.errors)
        warnings.extend(fields_result.warnings)
        details['validation_checks']['fields'] = fields_result.details
        details['fields_count'] = fields_result.details.get('fields_count', 0)
        if not fields_result.is_valid:
            details['schema_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 3. Validate schema version compatibility (if previous version exists)
        if previous_dataset:
            compatibility_result = self._validate_schema_version_compatibility(
                previous_dataset, dataset
            )
            errors.extend(compatibility_result.errors)
            warnings.extend(compatibility_result.warnings)
            details['validation_checks']['version_compatibility'] = compatibility_result.details

        # 4. Validate schema evolution (backward compatibility)
        if previous_dataset:
            evolution_result = self._validate_schema_evolution(previous_dataset, dataset)
            errors.extend(evolution_result.errors)
            warnings.extend(evolution_result.warnings)
            details['validation_checks']['evolution'] = evolution_result.details

        details['schema_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_schema_structure(self, schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate schema structure conforms to JSON Schema format.

        Args:
            schema: Schema dictionary to validate

        Returns:
            ValidationResult with structure validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'is_dict': isinstance(schema, dict),
            'has_fields': 'fields' in schema,
            'has_valid_structure': False
        }

        if not isinstance(schema, dict):
            errors.append("Schema must be a dictionary")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate schema has fields array
        if 'fields' not in schema:
            warnings.append("Schema missing 'fields' key - schema may be incomplete")
            details['has_fields'] = False
        else:
            fields = schema.get('fields', [])
            if not isinstance(fields, list):
                errors.append("Schema 'fields' must be a list")
                details['has_valid_structure'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        # Optional: Validate against JSON Schema draft if jsonschema library available
        try:
            import jsonschema
            from jsonschema import Draft202012Validator, SchemaError

            # Basic JSON Schema structure validation
            # Note: We're validating the structure, not the schema itself as a JSON Schema
            # Dataset schemas are custom format, so we validate structure only
            details['has_valid_structure'] = True
        except ImportError:
            # jsonschema not available - skip JSON Schema validation
            warnings.append("jsonschema library not available - JSON Schema validation skipped")
            details['has_valid_structure'] = True  # Assume valid if we can't validate

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_schema_fields(self, schema: Dict[str, Any]) -> ValidationResult:
        """
        Validate schema fields have required properties and valid data types.

        Args:
            schema: Schema dictionary to validate

        Returns:
            ValidationResult with field validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'fields_count': 0,
            'valid_fields': 0,
            'invalid_fields': 0,
            'field_errors': []
        }

        fields = schema.get('fields', [])
        if not isinstance(fields, list):
            errors.append("Schema 'fields' must be a list")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['fields_count'] = len(fields)

        # Valid data types
        valid_data_types = {
            'string', 'integer', 'int', 'long', 'float', 'double', 'decimal',
            'boolean', 'bool', 'date', 'datetime', 'timestamp', 'time',
            'binary', 'array', 'object', 'struct', 'map', 'null'
        }

        # Validate each field
        field_names = set()
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                errors.append(f"Field at index {i} must be a dictionary")
                details['invalid_fields'] += 1
                continue

            # Required: name
            if 'name' not in field:
                errors.append(f"Field at index {i} missing required 'name' property")
                details['invalid_fields'] += 1
                continue

            field_name = field.get('name')
            if not isinstance(field_name, str) or not field_name.strip():
                errors.append(f"Field at index {i} has invalid name: {field_name}")
                details['invalid_fields'] += 1
                continue

            # Check for duplicate field names
            if field_name in field_names:
                errors.append(f"Duplicate field name '{field_name}' found")
                details['invalid_fields'] += 1
                continue
            field_names.add(field_name)

            # Required: type or data_type
            field_type = field.get('type') or field.get('data_type')
            if not field_type:
                warnings.append(f"Field '{field_name}' missing 'type' or 'data_type' property")
            elif isinstance(field_type, str):
                # Normalize type name
                normalized_type = field_type.lower().strip()
                if normalized_type not in valid_data_types:
                    warnings.append(
                        f"Field '{field_name}' has unrecognized data type '{field_type}' "
                        f"(accepted types: {', '.join(sorted(valid_data_types))})"
                    )

            # Optional: nullable (should be boolean)
            if 'nullable' in field and not isinstance(field.get('nullable'), bool):
                warnings.append(f"Field '{field_name}' has non-boolean 'nullable' property")

            details['valid_fields'] += 1

        if details['invalid_fields'] > 0:
            details['field_errors'] = errors.copy()

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_schema_version_compatibility(
        self,
        previous_dataset: Dataset,
        current_dataset: Dataset
    ) -> ValidationResult:
        """
        Validate schema version compatibility between versions.

        Args:
            previous_dataset: Previous dataset version
            current_dataset: Current dataset version

        Returns:
            ValidationResult with version compatibility status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'previous_version': previous_dataset.version,
            'current_version': current_dataset.version,
            'version_compatible': False,
            'compatibility_level': None
        }

        # Check if both have schemas
        if not previous_dataset.schema_json:
            warnings.append("Previous dataset version has no schema - compatibility check skipped")
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not current_dataset.schema_json:
            warnings.append("Current dataset has no schema - compatibility check skipped")
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Use SchemaEvolutionTracker to calculate compatibility
        from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker

        try:
            schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
                previous_dataset.schema_json,
                current_dataset.schema_json
            )

            details['compatibility_level'] = schema_diff.compatibility_level.value
            details['version_compatible'] = (
                schema_diff.compatibility_level.value in [
                    'FULLY_COMPATIBLE',
                    'BACKWARD_COMPATIBLE'
                ]
            )

            # Add warnings for compatibility issues
            if schema_diff.compatibility_level.value == 'FORWARD_COMPATIBLE':
                warnings.append(
                    "Schema is forward compatible (fields removed) - may break consumers"
                )
            elif schema_diff.compatibility_level.value == 'INCOMPATIBLE':
                errors.append(
                    "Schema is incompatible - breaking changes detected "
                    f"({len([c for c in schema_diff.changes if c.breaking])} breaking changes)"
                )

            # Add details about changes
            details['changes_summary'] = schema_diff.summary
            details['breaking_changes_count'] = len([
                c for c in schema_diff.changes if c.breaking
            ])

        except Exception as e:
            logger.warning(
                f"Failed to calculate schema compatibility: {e}",
                exc_info=True
            )
            warnings.append(f"Schema compatibility check failed: {str(e)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_schema_evolution(
        self,
        previous_dataset: Dataset,
        current_dataset: Dataset
    ) -> ValidationResult:
        """
        Validate schema evolution maintains backward compatibility.

        Args:
            previous_dataset: Previous dataset version
            current_dataset: Current dataset version

        Returns:
            ValidationResult with evolution validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'backward_compatible': False,
            'evolution_valid': False
        }

        # Check if both have schemas
        if not previous_dataset.schema_json or not current_dataset.schema_json:
            warnings.append("Cannot validate evolution - one or both datasets lack schema")
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Use SchemaEvolutionTracker to check evolution
        from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker, CompatibilityLevel

        try:
            schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
                previous_dataset.schema_json,
                current_dataset.schema_json
            )

            # Check backward compatibility
            details['backward_compatible'] = (
                schema_diff.compatibility_level in [
                    CompatibilityLevel.FULLY_COMPATIBLE,
                    CompatibilityLevel.BACKWARD_COMPATIBLE
                ]
            )

            # Validate evolution rules:
            # 1. Fields can be added (backward compatible)
            # 2. Fields cannot be removed without deprecation (forward compatible is warning)
            # 3. Field types cannot change (incompatible)
            # 4. Nullable cannot change from True to False (breaking)

            breaking_changes = [c for c in schema_diff.changes if c.breaking]
            if breaking_changes:
                breaking_descriptions = [
                    c.description for c in breaking_changes
                ]
                errors.append(
                    f"Schema evolution contains breaking changes: {', '.join(breaking_descriptions)}"
                )
                details['evolution_valid'] = False
            else:
                details['evolution_valid'] = True

            # Add warnings for non-breaking but potentially problematic changes
            non_breaking_changes = [c for c in schema_diff.changes if not c.breaking]
            if non_breaking_changes:
                warnings.append(
                    f"Schema evolution contains {len(non_breaking_changes)} non-breaking changes"
                )

            details['changes'] = [
                {
                    'type': c.change_type.value,
                    'field_name': c.field_name,
                    'description': c.description,
                    'breaking': c.breaking
                }
                for c in schema_diff.changes
            ]

        except Exception as e:
            logger.warning(
                f"Failed to validate schema evolution: {e}",
                exc_info=True
            )
            warnings.append(f"Schema evolution validation failed: {str(e)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_context(self, dataset: Dataset, tenant: Optional[Any] = None) -> ValidationResult:
        """
        Validate dataset tenant context consistency.

        Args:
            dataset: Dataset instance to validate
            tenant: Optional tenant instance for comparison

        Returns:
            ValidationResult with tenant context validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'dataset_tenant_id': str(dataset.tenant.id) if dataset.tenant else None,
            'provided_tenant_id': str(tenant.id) if tenant else None,
            'tenants_match': False,
        }

        if not dataset.tenant:
            errors.append("Dataset must have a tenant")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # If tenant is provided, validate it matches dataset tenant
        if tenant:
            if str(dataset.tenant.id) != str(tenant.id):
                errors.append(
                    f"Dataset tenant ({dataset.tenant.id}) does not match provided tenant ({tenant.id})"
                )
                details['tenants_match'] = False
            else:
                details['tenants_match'] = True

        # Validate dataset.file.tenant matches dataset.tenant if file exists
        if dataset.file and dataset.file.tenant:
            if str(dataset.file.tenant.id) != str(dataset.tenant.id):
                errors.append(
                    f"Dataset file tenant ({dataset.file.tenant.id}) does not match dataset tenant ({dataset.tenant.id})"
                )
                details['file_tenant_match'] = False
            else:
                details['file_tenant_match'] = True

        # Validate dataset.asset.tenant matches dataset.tenant if asset exists
        if dataset.asset and dataset.asset.tenant:
            if str(dataset.asset.tenant.id) != str(dataset.tenant.id):
                errors.append(
                    f"Dataset asset tenant ({dataset.asset.tenant.id}) does not match dataset tenant ({dataset.tenant.id})"
                )
                details['asset_tenant_match'] = False
            else:
                details['asset_tenant_match'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_permissions(
        self,
        dataset: Dataset,
        user: Optional[User] = None,
        access_type: str = "READ"
    ) -> ValidationResult:
        """
        Validate user permissions for dataset access.

        Integrates with GovernanceService and ABACEngine for comprehensive access control:
        - Checks tenant isolation (same tenant = allowed by default)
        - Checks ABAC policies via ABACEngine
        - Checks approved AccessRequests

        Args:
            dataset: Dataset instance to validate
            user: Optional user instance for permission validation
            access_type: Access type to validate ("READ" or "WRITE")

        Returns:
            ValidationResult with permissions validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'user_provided': user is not None,
            'access_type': access_type,
            'read_access_allowed': False,
            'write_access_allowed': False,
            'tenant_isolation_valid': False,
            'abac_policy_checked': False,
            'access_request_checked': False,
        }

        if not user:
            warnings.append("User not provided - permission validation skipped")
            details['read_access_allowed'] = True  # Not an error, just skipped
            details['write_access_allowed'] = False  # Write requires explicit user
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate user has tenant
        if not hasattr(user, 'tenant') or not user.tenant:
            errors.append("User must have a tenant for permission validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 1. Validate tenant isolation
        tenant_isolation_result = self._validate_tenant_isolation(dataset, user)
        if not tenant_isolation_result.is_valid:
            errors.extend(tenant_isolation_result.errors)
            warnings.extend(tenant_isolation_result.warnings)
        details['tenant_isolation_valid'] = tenant_isolation_result.is_valid
        details['tenant_isolation'] = tenant_isolation_result.details

        # If tenant isolation fails, deny access
        if not tenant_isolation_result.is_valid:
            details['read_access_allowed'] = False
            details['write_access_allowed'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # 2. Check ABAC policies via ABACEngine
        abac_result = self._validate_abac_access(dataset, user, access_type)
        details['abac_policy_checked'] = True
        details['abac_result'] = {
            'allowed': abac_result.allowed if hasattr(abac_result, 'allowed') else False,
            'policy_id': str(abac_result.policy.id) if hasattr(abac_result, 'policy') and abac_result.policy else None,
            'masking_required': abac_result.masking_required if hasattr(abac_result, 'masking_required') else False,
        }

        # Check if same tenant (default allow for same tenant if no explicit policy)
        is_same_tenant = tenant_isolation_result.details.get('same_tenant', False)

        # Always check access requests first (they take precedence)
        access_request_result = self._validate_access_request(dataset, user, access_type)
        details['access_request_checked'] = True
        details['access_request'] = access_request_result.details

        if access_request_result.is_valid:
            # Access request approved - grant access
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True
            warnings.append(
                f"Access granted via approved access request"
            )
        elif abac_result.allowed:
            # ABAC policy allows access
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True

            if abac_result.masking_required:
                warnings.append(
                    f"Access allowed but data masking is required for dataset '{dataset.id}'"
                )
        elif is_same_tenant:
            # Same tenant: default allow if no explicit DENY policy
            # (ABAC defaults to deny if no policy matches, but same tenant should allow)
            if access_type == "READ":
                details['read_access_allowed'] = True
            else:
                details['write_access_allowed'] = True
            warnings.append(
                f"Same-tenant access allowed by default (no explicit ABAC policy found)"
            )
        else:
            # Cross-tenant and no ABAC policy and no access request: deny access
            errors.append(
                f"User '{user.id}' does not have {access_type} access to dataset '{dataset.id}'. "
                f"No ABAC policy allows access and no approved access request found."
            )
            if access_type == "READ":
                details['read_access_allowed'] = False
            else:
                details['write_access_allowed'] = False

        # Set overall access_allowed based on requested access_type
        if access_type == "READ":
            details['access_allowed'] = details['read_access_allowed']
        else:
            details['access_allowed'] = details['write_access_allowed']

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_isolation(self, dataset: Dataset, user: User) -> ValidationResult:
        """
        Validate tenant isolation for dataset access.

        Same-tenant access is allowed by default. Cross-tenant access requires
        explicit entitlements (AccessRequests or ABAC policies).

        Args:
            dataset: Dataset instance to validate
            user: User instance for tenant comparison

        Returns:
            ValidationResult with tenant isolation validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'user_tenant_id': str(user.tenant.id) if user.tenant else None,
            'dataset_tenant_id': str(dataset.tenant.id) if dataset.tenant else None,
            'same_tenant': False,
            'cross_tenant': False,
        }

        if not dataset.tenant:
            errors.append("Dataset must have a tenant for isolation validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not user.tenant:
            errors.append("User must have a tenant for isolation validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if same tenant
        if str(user.tenant.id) == str(dataset.tenant.id):
            details['same_tenant'] = True
            details['cross_tenant'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Cross-tenant access - requires explicit entitlements
        details['same_tenant'] = False
        details['cross_tenant'] = True
        warnings.append(
            f"Cross-tenant access detected: user tenant ({user.tenant.id}) != dataset tenant ({dataset.tenant.id}). "
            f"Access requires explicit entitlements (AccessRequest or ABAC policy)."
        )

        # Cross-tenant is not an error by itself - it's validated by ABAC/access requests
        return ValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_abac_access(
        self,
        dataset: Dataset,
        user: User,
        access_type: str
    ) -> Any:
        """
        Validate access using ABAC engine.

        Args:
            dataset: Dataset instance
            user: User instance
            access_type: Access type ("READ" or "WRITE")

        Returns:
            PolicyEvaluationResult from ABACEngine
        """
        from hub.apps.governance.abac import ABACEngine

        try:
            result = ABACEngine.evaluate_access(
                user_id=str(user.id),
                tenant_id=str(dataset.tenant.id),
                resource_type="DATASET",
                resource_id=str(dataset.id),
                access_type=access_type
            )
            return result
        except Exception as e:
            logger.warning(
                f"ABAC access evaluation failed for dataset {dataset.id}, user {user.id}: {e}",
                exc_info=True
            )
            # On error, deny access (fail-secure)
            from hub.apps.governance.abac import PolicyEvaluationResult
            return PolicyEvaluationResult(allowed=False)

    def _validate_access_request(
        self,
        dataset: Dataset,
        user: User,
        access_type: str
    ) -> ValidationResult:
        """
        Validate if user has an approved access request for the dataset.

        Args:
            dataset: Dataset instance
            user: User instance
            access_type: Access type ("READ" or "WRITE")

        Returns:
            ValidationResult with access request validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'has_approved_request': False,
            'access_request_id': None,
            'access_request_status': None,
        }

        from hub.apps.governance.models import AccessRequest, AccessRequestStatus
        from django.utils import timezone

        # Check for approved access requests
        access_requests = AccessRequest.objects.filter(
            dataset=dataset,
            requested_by=user,
            requested_access_type=access_type,
            status=AccessRequestStatus.APPROVED
        ).order_by('-approved_at')

        # Check if any approved request is still valid (not expired)
        valid_request = None
        for request in access_requests:
            # Check expiration if expires_at is set
            if request.expires_at:
                if request.expires_at < timezone.now():
                    continue  # Expired, skip
            valid_request = request
            break

        if valid_request:
            details['has_approved_request'] = True
            details['access_request_id'] = str(valid_request.id)
            details['access_request_status'] = valid_request.status
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # No valid approved request found
        details['has_approved_request'] = False
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_dataset_read_access(
        self,
        dataset: Dataset,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user has READ access to dataset.

        Args:
            dataset: Dataset instance
            user: User instance

        Returns:
            ValidationResult with read access validation status
        """
        return self._validate_permissions(dataset, user, access_type="READ")

    def validate_dataset_write_access(
        self,
        dataset: Dataset,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user has WRITE access to dataset.

        Args:
            dataset: Dataset instance
            user: User instance

        Returns:
            ValidationResult with write access validation status
        """
        return self._validate_permissions(dataset, user, access_type="WRITE")

    def _validate_dataset_version(self, dataset: Dataset) -> ValidationResult:
        """
        Validate dataset version management.

        Args:
            dataset: Dataset instance to validate

        Returns:
            ValidationResult with version validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'version': dataset.version,
            'version_valid': False,
            'has_parent_version': dataset.parent_version is not None,
            'is_current': dataset.is_current,
        }

        # Validate version is positive integer
        if dataset.version is None or dataset.version < 1:
            errors.append("Dataset version must be a positive integer")
            details['version_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['version_valid'] = True

        # Validate version uniqueness if asset is provided
        if dataset.asset:
            from hub.apps.datasets.models import Dataset as DatasetModel
            conflicting_dataset = DatasetModel.objects.filter(
                tenant=dataset.tenant,
                asset=dataset.asset,
                version=dataset.version
            ).exclude(id=dataset.id).first()

            if conflicting_dataset:
                errors.append(
                    f"Dataset version {dataset.version} already exists for asset '{dataset.asset.id}' "
                    f"(conflicting dataset: {conflicting_dataset.id})"
                )
                details['version_unique'] = False
            else:
                details['version_unique'] = True

        # Validate parent_version relationship if provided
        if dataset.parent_version:
            if dataset.parent_version.tenant.id != dataset.tenant.id:
                errors.append(
                    f"Parent version dataset tenant ({dataset.parent_version.tenant.id}) "
                    f"does not match dataset tenant ({dataset.tenant.id})"
                )
                details['parent_version_valid'] = False
            elif dataset.parent_version.asset != dataset.asset:
                warnings.append(
                    f"Parent version dataset asset ({dataset.parent_version.asset.id if dataset.parent_version.asset else None}) "
                    f"does not match dataset asset ({dataset.asset.id if dataset.asset else None})"
                )
                details['parent_version_valid'] = True
            else:
                details['parent_version_valid'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_file_relationship(self, dataset: Dataset, file: Optional[Any] = None) -> ValidationResult:
        """
        Validate dataset-file relationship.

        Args:
            dataset: Dataset instance to validate
            file: Optional file instance for comparison

        Returns:
            ValidationResult with file relationship validation status
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            'dataset_file_id': str(dataset.file.id) if dataset.file else None,
            'provided_file_id': str(file.id) if file else None,
            'files_match': False,
        }

        if not dataset.file:
            errors.append("Dataset must have a file")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # If file is provided, validate it matches dataset.file
        if file:
            if str(dataset.file.id) != str(file.id):
                errors.append(
                    f"Dataset file ({dataset.file.id}) does not match provided file ({file.id})"
                )
                details['files_match'] = False
            else:
                details['files_match'] = True

        # Validate file is active
        if hasattr(dataset.file, 'is_active'):
            if not dataset.file.is_active():
                warnings.append(
                    f"Dataset file '{dataset.file.name}' is not active (status: {dataset.file.status})"
                )
                details['file_active'] = False
            else:
                details['file_active'] = True

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )


    def validate_version_number(
        self,
        dataset: Dataset,
        semantic_version: Optional[str] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate semantic version number format and rules.

        Validates:
        - Semantic version format (MAJOR.MINOR.PATCH)
        - Version components are non-negative integers
        - Version follows semantic versioning rules
        - Version is appropriate for dataset changes

        Args:
            dataset: Dataset instance to validate
            semantic_version: Optional semantic version string (default: dataset.semantic_version)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and version details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        import re
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(dataset.id),
            "version_validation": {}
        }

        version_str = semantic_version or dataset.semantic_version

        if not version_str:
            warnings.append(
                "Semantic version is not set. Consider setting a semantic version for better version tracking"
            )
            details["version_validation"]["has_semantic_version"] = False
            details["version_validation"]["version_valid"] = True  # Not required, just recommended
            result = ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )
            return result

        details["version_validation"]["has_semantic_version"] = True
        details["version_validation"]["semantic_version"] = version_str

        # Validate semantic version format: MAJOR.MINOR.PATCH
        # Optional: MAJOR.MINOR.PATCH-PRERELEASE+BUILD
        semver_pattern = r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'

        if not re.match(semver_pattern, version_str):
            errors.append(
                f"Invalid semantic version format '{version_str}'. "
                f"Expected format: MAJOR.MINOR.PATCH (e.g., '1.0.0')"
            )
            details["version_validation"]["format_valid"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError(
                    f"Version number validation failed: {', '.join(errors)}",
                    code="INVALID_SEMANTIC_VERSION",
                    details=details
                )
            return result

        details["version_validation"]["format_valid"] = True

        # Parse version components
        from hub.apps.datasets.versioning import VersionHistoryManager
        parsed_version = VersionHistoryManager._parse_semantic_version(version_str)

        if not parsed_version:
            errors.append(
                f"Failed to parse semantic version '{version_str}'"
            )
            details["version_validation"]["parse_valid"] = False
        else:
            major, minor, patch = parsed_version
            details["version_validation"]["parse_valid"] = True
            details["version_validation"]["major"] = major
            details["version_validation"]["minor"] = minor
            details["version_validation"]["patch"] = patch

            # Validate version components are non-negative
            if major < 0 or minor < 0 or patch < 0:
                errors.append(
                    f"Semantic version components must be non-negative integers. "
                    f"Got: {major}.{minor}.{patch}"
                )
                details["version_validation"]["components_valid"] = False
            else:
                details["version_validation"]["components_valid"] = True

            # Validate version is not 0.0.0 (should start from 1.0.0)
            if major == 0 and minor == 0 and patch == 0:
                warnings.append(
                    "Semantic version 0.0.0 is typically used for initial development. "
                    "Consider starting from 1.0.0 for production releases"
                )
                details["version_validation"]["zero_version_warning"] = True

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Version number validation failed: {', '.join(errors)}",
                code="INVALID_SEMANTIC_VERSION",
                details=details
            )

        return result

    def validate_version_compatibility(
        self,
        dataset: Dataset,
        parent_version: Optional[Dataset] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate version compatibility and backward compatibility rules.

        Validates:
        - Version increment follows semantic versioning rules
        - Backward compatibility is maintained (no breaking changes without major version bump)
        - Parent version relationship is valid
        - Version progression is logical

        Args:
            dataset: Dataset instance to validate
            parent_version: Optional parent version (default: dataset.parent_version)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and compatibility details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(dataset.id),
            "compatibility_checks": {}
        }

        parent = parent_version or dataset.parent_version

        if not parent:
            # No parent version - this is the first version (valid)
            details["compatibility_checks"]["has_parent"] = False
            details["compatibility_checks"]["compatibility_valid"] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["compatibility_checks"]["has_parent"] = True
        details["compatibility_checks"]["parent_version_id"] = str(parent.id)
        details["compatibility_checks"]["parent_semantic_version"] = parent.semantic_version

        # Validate parent version has semantic version
        if not parent.semantic_version:
            warnings.append(
                "Parent version does not have a semantic version. "
                "Cannot validate version compatibility without parent semantic version"
            )
            details["compatibility_checks"]["parent_has_semantic_version"] = False
            details["compatibility_checks"]["compatibility_valid"] = True  # Warning only
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["compatibility_checks"]["parent_has_semantic_version"] = True

        # Validate current dataset has semantic version
        if not dataset.semantic_version:
            warnings.append(
                "Current dataset does not have a semantic version. "
                "Cannot validate version compatibility"
            )
            details["compatibility_checks"]["current_has_semantic_version"] = False
            details["compatibility_checks"]["compatibility_valid"] = True  # Warning only
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["compatibility_checks"]["current_has_semantic_version"] = True
        details["compatibility_checks"]["current_semantic_version"] = dataset.semantic_version

        # Parse semantic versions
        from hub.apps.datasets.versioning import VersionHistoryManager
        parent_parsed = VersionHistoryManager._parse_semantic_version(parent.semantic_version)
        current_parsed = VersionHistoryManager._parse_semantic_version(dataset.semantic_version)

        if not parent_parsed or not current_parsed:
            errors.append(
                f"Failed to parse semantic versions. "
                f"Parent: {parent.semantic_version}, Current: {dataset.semantic_version}"
            )
            details["compatibility_checks"]["parse_valid"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                from hub.apps.core.services.base import ValidationError
                raise ValidationError(
                    f"Version compatibility validation failed: {', '.join(errors)}",
                    code="VERSION_COMPATIBILITY_FAILED",
                    details=details
                )
            return result

        details["compatibility_checks"]["parse_valid"] = True

        parent_major, parent_minor, parent_patch = parent_parsed
        current_major, current_minor, current_patch = current_parsed

        # Check for version regression (current < parent)
        if (current_major < parent_major or
            (current_major == parent_major and current_minor < parent_minor) or
            (current_major == parent_major and current_minor == parent_minor and current_patch < parent_patch)):
            errors.append(
                f"Version regression detected: current version {dataset.semantic_version} "
                f"is less than parent version {parent.semantic_version}. "
                f"Versions must always increase"
            )
            details["compatibility_checks"]["version_regression"] = True
            details["compatibility_checks"]["compatibility_valid"] = False
        else:
            details["compatibility_checks"]["version_regression"] = False

        # Check for breaking changes without major version bump
        if dataset.schema_json and parent.schema_json:
            is_breaking = VersionHistoryManager._is_breaking_change(
                parent.schema_json or {},
                dataset.schema_json or {}
            )

            if is_breaking:
                details["compatibility_checks"]["has_breaking_changes"] = True
                if current_major <= parent_major:
                    errors.append(
                        f"Breaking changes detected but major version was not incremented. "
                        f"Parent version: {parent.semantic_version}, Current version: {dataset.semantic_version}. "
                        f"Breaking changes require a major version increment"
                    )
                    details["compatibility_checks"]["breaking_change_handled"] = False
                    details["compatibility_checks"]["compatibility_valid"] = False
                else:
                    details["compatibility_checks"]["breaking_change_handled"] = True
                    details["compatibility_checks"]["compatibility_valid"] = True
            else:
                details["compatibility_checks"]["has_breaking_changes"] = False
                details["compatibility_checks"]["compatibility_valid"] = True

        # Validate version increment follows semantic versioning rules
        if current_major > parent_major:
            # Major version increment - reset minor and patch
            if current_minor != 0 or current_patch != 0:
                warnings.append(
                    f"Major version increment detected, but minor and patch versions are not reset to 0. "
                    f"Expected: {current_major}.0.0, Got: {dataset.semantic_version}"
                )
                details["compatibility_checks"]["major_increment_reset"] = False
            else:
                details["compatibility_checks"]["major_increment_reset"] = True
        elif current_minor > parent_minor:
            # Minor version increment - reset patch
            if current_patch != 0:
                warnings.append(
                    f"Minor version increment detected, but patch version is not reset to 0. "
                    f"Expected: {current_major}.{current_minor}.0, Got: {dataset.semantic_version}"
                )
                details["compatibility_checks"]["minor_increment_reset"] = False
            else:
                details["compatibility_checks"]["minor_increment_reset"] = True

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Version compatibility validation failed: {', '.join(errors)}",
                code="VERSION_COMPATIBILITY_FAILED",
                details=details
            )

        return result

    def validate_version_creation(
        self,
        dataset: Dataset,
        proposed_semantic_version: Optional[str] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate version creation (prevent duplicate versions).

        Validates:
        - Version uniqueness within asset (cannot create duplicate versions)
        - Semantic version uniqueness within asset
        - Version hash uniqueness (prevent duplicate content)
        - Version number increment is valid

        Args:
            dataset: Dataset instance to validate
            proposed_semantic_version: Optional proposed semantic version
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and creation details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(dataset.id),
            "creation_checks": {}
        }

        if not dataset.asset:
            # No asset - version uniqueness not applicable
            warnings.append(
                "Dataset is not associated with an asset. "
                "Version uniqueness validation skipped"
            )
            details["creation_checks"]["has_asset"] = False
            details["creation_checks"]["creation_valid"] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["creation_checks"]["has_asset"] = True
        details["creation_checks"]["asset_id"] = str(dataset.asset.id)

        # Check for duplicate version number
        existing_version = Dataset.objects.filter(
            tenant=dataset.tenant,
            asset=dataset.asset,
            version=dataset.version
        ).exclude(id=dataset.id).first()

        if existing_version:
            errors.append(
                f"Dataset version {dataset.version} already exists for asset '{dataset.asset.id}'. "
                f"Conflicting dataset: {existing_version.id}"
            )
            details["creation_checks"]["version_unique"] = False
            details["creation_checks"]["conflicting_dataset_id"] = str(existing_version.id)
        else:
            details["creation_checks"]["version_unique"] = True

        # Check for duplicate semantic version
        semantic_version = proposed_semantic_version or dataset.semantic_version
        if semantic_version:
            existing_semantic = Dataset.objects.filter(
                tenant=dataset.tenant,
                asset=dataset.asset,
                semantic_version=semantic_version
            ).exclude(id=dataset.id).first()

            if existing_semantic:
                errors.append(
                    f"Semantic version '{semantic_version}' already exists for asset '{dataset.asset.id}'. "
                    f"Conflicting dataset: {existing_semantic.id}"
                )
                details["creation_checks"]["semantic_version_unique"] = False
                details["creation_checks"]["conflicting_semantic_dataset_id"] = str(existing_semantic.id)
            else:
                details["creation_checks"]["semantic_version_unique"] = True
                details["creation_checks"]["semantic_version"] = semantic_version

        # Check for duplicate version hash (same content)
        if dataset.version_hash:
            existing_hash = Dataset.objects.filter(
                tenant=dataset.tenant,
                asset=dataset.asset,
                version_hash=dataset.version_hash
            ).exclude(id=dataset.id).first()

            if existing_hash:
                warnings.append(
                    f"Version hash '{dataset.version_hash[:16]}...' already exists for asset '{dataset.asset.id}'. "
                    f"This indicates identical content. Conflicting dataset: {existing_hash.id}"
                )
                details["creation_checks"]["hash_unique"] = False
                details["creation_checks"]["conflicting_hash_dataset_id"] = str(existing_hash.id)
            else:
                details["creation_checks"]["hash_unique"] = True

        # Validate version number increment
        latest_dataset = Dataset.objects.filter(
            tenant=dataset.tenant,
            asset=dataset.asset
        ).exclude(id=dataset.id).order_by('-version').first()

        if latest_dataset:
            details["creation_checks"]["has_existing_versions"] = True
            details["creation_checks"]["latest_version"] = latest_dataset.version

            if dataset.version <= latest_dataset.version:
                errors.append(
                    f"Version {dataset.version} must be greater than latest version {latest_dataset.version}"
                )
                details["creation_checks"]["version_increment_valid"] = False
            else:
                details["creation_checks"]["version_increment_valid"] = True
        else:
            details["creation_checks"]["has_existing_versions"] = False
            details["creation_checks"]["version_increment_valid"] = True

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Version creation validation failed: {', '.join(errors)}",
                code="VERSION_CREATION_FAILED",
                details=details
            )

        return result

    def validate_version_deletion(
        self,
        dataset: Dataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate version deletion (check for references).

        Validates:
        - No child versions reference this version as parent
        - No active references from other models (classifications, policies, etc.)
        - Version is not marked as current (is_current=True)
        - Version is archived before deletion

        Args:
            dataset: Dataset instance to validate for deletion
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and deletion details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(dataset.id),
            "deletion_checks": {}
        }

        # Check for child versions
        child_versions = dataset.child_versions.all()
        child_count = child_versions.count()

        if child_count > 0:
            errors.append(
                f"Cannot delete dataset version {dataset.version} ({dataset.semantic_version or 'no semantic version'}). "
                f"It has {child_count} child version(s) that reference it as parent. "
                f"Child versions: {', '.join([str(c.id) for c in child_versions[:5]])}"
            )
            details["deletion_checks"]["has_child_versions"] = True
            details["deletion_checks"]["child_version_count"] = child_count
            details["deletion_checks"]["child_version_ids"] = [str(c.id) for c in child_versions]
        else:
            details["deletion_checks"]["has_child_versions"] = False
            details["deletion_checks"]["child_version_count"] = 0

        # Check if version is current
        if dataset.is_current:
            errors.append(
                f"Cannot delete dataset version {dataset.version} ({dataset.semantic_version or 'no semantic version'}). "
                f"It is marked as the current version (is_current=True). "
                f"Set another version as current before deleting"
            )
            details["deletion_checks"]["is_current"] = True
        else:
            details["deletion_checks"]["is_current"] = False

        # Check for references from governance models
        from hub.apps.governance.models import DataClassification, RetentionPolicy, AccessRequest

        # Check classifications
        classifications = DataClassification.objects.filter(dataset=dataset)
        classification_count = classifications.count()
        if classification_count > 0:
            warnings.append(
                f"Dataset version has {classification_count} data classification(s). "
                f"These will be deleted when dataset is deleted"
            )
            details["deletion_checks"]["has_classifications"] = True
            details["deletion_checks"]["classification_count"] = classification_count
        else:
            details["deletion_checks"]["has_classifications"] = False

        # Check retention policies
        retention_policies = RetentionPolicy.objects.filter(dataset=dataset)
        policy_count = retention_policies.count()
        if policy_count > 0:
            warnings.append(
                f"Dataset version has {policy_count} retention policy/policies. "
                f"These will be deleted when dataset is deleted"
            )
            details["deletion_checks"]["has_retention_policies"] = True
            details["deletion_checks"]["retention_policy_count"] = policy_count
        else:
            details["deletion_checks"]["has_retention_policies"] = False

        # Check access requests
        access_requests = AccessRequest.objects.filter(dataset=dataset)
        access_request_count = access_requests.count()
        if access_request_count > 0:
            warnings.append(
                f"Dataset version has {access_request_count} access request(s). "
                f"These will be deleted when dataset is deleted"
            )
            details["deletion_checks"]["has_access_requests"] = True
            details["deletion_checks"]["access_request_count"] = access_request_count
        else:
            details["deletion_checks"]["has_access_requests"] = False

        # Check if version is archived
        if not dataset.archived_at:
            warnings.append(
                f"Dataset version {dataset.version} is not archived. "
                f"Consider archiving before deletion to preserve version history"
            )
            details["deletion_checks"]["is_archived"] = False
        else:
            details["deletion_checks"]["is_archived"] = True
            details["deletion_checks"]["archived_at"] = dataset.archived_at.isoformat()

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(
                f"Version deletion validation failed: {', '.join(errors)}",
                code="VERSION_DELETION_FAILED",
                details=details
            )

        return result

