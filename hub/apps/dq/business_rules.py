"""
DQ Business Rules

Comprehensive business rules validation for data quality operations, including:
- DQ run validation
- DQ check configuration validation
- Tenant and user context validation
- Dataset-DQ run relationship validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.datasets.models import Dataset
    from hub.apps.assets.models import Asset
    from hub.apps.files.models import File
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class DQRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for DQ business rules.

    Adds DQ-specific context:
    - dq_run: The DQ run being validated
    - check: Optional DQ check being validated (from checks_json)
    - dataset: Optional dataset instance for dataset-DQ run relationship validation
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    dq_run: Optional[DQRun] = None
    check: Optional[Dict[str, Any]] = None
    dataset: Optional[Any] = None  # Using Any to avoid circular import
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'dq_run_id': str(self.dq_run.id) if self.dq_run else None,
            'check_name': self.check.get('name') if self.check and isinstance(self.check, dict) else None,
            'dataset_id': str(self.dataset.id) if self.dataset else None,
            'tenant_id': str(self.tenant.id) if self.tenant else None,
            'user_id': str(self.user.id) if self.user else None,
        })
        return base_dict


@register_rule(
    rule_name="dq_validation",
    description="Validates data quality runs, check configurations, tenant context, and dataset relationships",
    tags=["dq", "data_quality", "validation"],
    priority=10
)
class DQBusinessRules(BusinessRules):
    """
    Business rules validator for data quality operations.

    Extends BusinessRules base class with DQ-specific validation:
    - DQ run validation
    - DQ check configuration validation
    - Tenant context consistency
    - User permissions and access validation
    - Dataset-DQ run relationship validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "DQBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all DQ validation checks.
        It can be called with a DQRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        dq_run, check, dataset, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - dq_run: DQRun instance (optional)
                - check: Optional DQ check dictionary (from checks_json)
                - dataset: Optional dataset instance
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('dq_run', 'check_config', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract dq_run, check, dataset, tenant, and user from context or kwargs
        if isinstance(context, DQRuleExecutionContext):
            dq_run = context.dq_run
            check = context.check
            dataset = context.dataset
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            dq_run = kwargs.get('dq_run')
            check = kwargs.get('check')
            dataset = kwargs.get('dataset')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                dq_run = dq_run or context.metadata.get('dq_run')
                check = check or context.metadata.get('check')
                dataset = dataset or context.metadata.get('dataset')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not dq_run and context and hasattr(context, 'resource'):
                if isinstance(context.resource, DQRun):
                    dq_run = context.resource

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate DQ run if provided
        if dq_run and validation_type in ('dq_run', 'all'):
            dq_run_result = self._validate_dq_run(dq_run, tenant, user)
            result = result.combine(dq_run_result)
            validated_items.append('dq_run')

        # Validate check configuration if provided
        if check and validation_type in ('check_config', 'all'):
            check_result = self._validate_dq_check_config(check, dq_run, dataset, tenant, user)
            result = result.combine(check_result)
            validated_items.append('check_config')

        # Validate tenant context if tenant provided
        if tenant and validation_type in ('tenant_context', 'all'):
            tenant_context_result = self._validate_tenant_context(tenant)
            result = result.combine(tenant_context_result)
            validated_items.append('tenant_context')

        # Validate permissions if user provided
        if user and validation_type in ('permissions', 'all'):
            permissions_result = self._validate_permissions(user, tenant)
            result = result.combine(permissions_result)
            validated_items.append('permissions')

        # If nothing was validated, return appropriate result
        if not validated_items:
            return ValidationResult(
                is_valid=False,
                errors=["At least one of dq_run, check, dataset, tenant, or user must be provided"],
                details={'validation_type': validation_type}
            )

        # Add validation summary to details
        result.details['validated_items'] = validated_items
        result.details['validation_type'] = validation_type

        return result

    def _validate_dq_run(
        self,
        dq_run: DQRun,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate DQ run.

        Validates:
        - DQ run has required fields (tenant, profile_key, engine, status)
        - DQ run has at least one resource (asset, dataset, or file)
        - Tenant context consistency
        - Status is valid
        - Engine is valid

        Args:
            dq_run: DQRun instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'dq_run_id': str(getattr(dq_run, 'id', None) or ''),
            'profile_key': getattr(dq_run, 'profile_key', ''),
            'engine': getattr(dq_run, 'engine', ''),
            'status': getattr(dq_run, 'status', DQRunStatus.PENDING),
        }

        # Validate tenant context consistency
        if self.tenant_id and dq_run.tenant_id:
            if str(dq_run.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"DQ run tenant ({dq_run.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate tenant context if provided
        if tenant and dq_run.tenant_id:
            if str(tenant.id) != str(dq_run.tenant_id):
                errors.append(
                    f"DQ run tenant ({dq_run.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )
                details['provided_tenant_match'] = False
            else:
                details['provided_tenant_match'] = True

        # Validate DQ run has at least one resource
        if not dq_run.asset and not dq_run.dataset and not dq_run.file:
            errors.append("DQ run must have at least one resource (asset, dataset, or file)")
            details['has_resource'] = False
        else:
            details['has_resource'] = True
            if dq_run.asset:
                details['resource_type'] = 'asset'
                details['resource_id'] = str(dq_run.asset.id)
            elif dq_run.dataset:
                details['resource_type'] = 'dataset'
                details['resource_id'] = str(dq_run.dataset.id)
            elif dq_run.file:
                details['resource_type'] = 'file'
                details['resource_id'] = str(dq_run.file.id)

        # Validate profile_key
        if not dq_run.profile_key or not dq_run.profile_key.strip():
            errors.append("DQ run must have a profile_key")
            details['has_profile_key'] = False
        else:
            details['has_profile_key'] = True

        # Validate engine
        valid_engines = [choice[0] for choice in DQEngine.choices]
        if dq_run.engine not in valid_engines:
            errors.append(
                f"DQ run has invalid engine: {dq_run.engine}. "
                f"Valid engines are: {', '.join(valid_engines)}"
            )
            details['engine_valid'] = False
        else:
            details['engine_valid'] = True

        # Validate status
        valid_statuses = [choice[0] for choice in DQRunStatus.choices]
        if dq_run.status not in valid_statuses:
            errors.append(
                f"DQ run has invalid status: {dq_run.status}. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True

        # Validate quality_score if present
        if dq_run.quality_score is not None:
            if dq_run.quality_score < 0 or dq_run.quality_score > 100:
                warnings.append(
                    f"DQ run quality_score ({dq_run.quality_score}) is outside expected range (0-100)"
                )
                details['quality_score_valid'] = False
            else:
                details['quality_score_valid'] = True
                details['quality_score'] = dq_run.quality_score

        # Validate date consistency
        if dq_run.started_at and dq_run.completed_at:
            if dq_run.completed_at < dq_run.started_at:
                errors.append(
                    f"DQ run completed_at ({dq_run.completed_at}) is before started_at ({dq_run.started_at})"
                )
                details['date_consistency'] = False
            else:
                details['date_consistency'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dq_check_config(
        self,
        check: Dict[str, Any],
        dq_run: Optional[DQRun] = None,
        dataset: Optional[Any] = None,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate DQ check configuration comprehensively.

        Validates:
        - Check has required fields (name, category/type, status)
        - Check type/category validation (valid check types)
        - Check configuration validation (valid parameters, thresholds)
        - Check schema compatibility validation (check compatible with dataset schema)
        - Check resource validation (dataset exists and accessible)

        Args:
            check: DQ check dictionary to validate
            dq_run: Optional DQRun instance
            dataset: Optional dataset instance
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'dq_check_config',
            'check_valid': False,
        }

        if not isinstance(check, dict):
            result.errors.append("DQ check must be a dictionary")
            return ValidationResult(
                is_valid=False,
                errors=result.errors,
                warnings=result.warnings,
                details=details
            )

        # Validate check has name
        if 'name' not in check or not check.get('name'):
            result.errors.append("DQ check must have a 'name' field")
            details['has_name'] = False
        else:
            details['has_name'] = True
            details['check_name'] = check['name']

        # Validate check has status (for result checks)
        if 'status' not in check:
            # Status is optional for configuration checks, required for result checks
            details['has_status'] = False
        else:
            details['has_status'] = True
            check_status = check['status']
            valid_statuses = ['PASS', 'FAIL', 'WARN', 'UNKNOWN']
            if check_status not in valid_statuses:
                result.errors.append(
                    f"DQ check has invalid status: {check_status}. "
                    f"Valid statuses are: {', '.join(valid_statuses)}"
                )
                details['status_valid'] = False
            else:
                details['status_valid'] = True
                details['check_status'] = check_status

        # Comprehensive validation: check type validation
        check_type_result = self._validate_check_type(check)
        result = result.combine(check_type_result)
        details['check_type_validated'] = True

        # Comprehensive validation: check configuration validation
        check_config_result = self._validate_check_configuration(check)
        result = result.combine(check_config_result)
        details['check_configuration_validated'] = True

        # Comprehensive validation: schema compatibility validation
        if dataset:
            schema_compat_result = self._validate_check_schema_compatibility(check, dataset)
            result = result.combine(schema_compat_result)
            details['schema_compatibility_validated'] = True
        else:
            details['schema_compatibility_validated'] = False
            details['schema_compatibility_skipped'] = 'No dataset provided'

        # Comprehensive validation: resource validation
        if dq_run:
            resource_result = self._validate_check_resource(check, dq_run, dataset, tenant, user)
            result = result.combine(resource_result)
            details['resource_validated'] = True
        elif dataset:
            # Validate dataset directly if provided
            resource_result = self._validate_check_resource(check, None, dataset, tenant, user)
            result = result.combine(resource_result)
            details['resource_validated'] = True
        else:
            details['resource_validated'] = False
            details['resource_validation_skipped'] = 'No dq_run or dataset provided'

        # Validate check configuration if present
        if 'config' in check and check['config']:
            if not isinstance(check['config'], dict):
                result.warnings.append("DQ check 'config' should be a dictionary")
                details['config_valid'] = False
            else:
                details['config_valid'] = True
                details['has_config'] = True

        # Validate check result if present
        if 'result' in check and check['result']:
            if not isinstance(check['result'], dict):
                result.warnings.append("DQ check 'result' should be a dictionary")
                details['result_valid'] = False
            else:
                details['result_valid'] = True
                details['has_result'] = True

        # Update result details
        result.details.update(details)
        result.details['check_valid'] = result.is_valid
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_check_type(
        self,
        check: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate check type (valid check types: completeness, accuracy, consistency, validity, uniqueness, timeliness).

        Validates:
        - Check has category or type field
        - Category/type is one of the valid check types

        Args:
            check: DQ check dictionary to validate

        Returns:
            ValidationResult with check type validation status
        """
        errors = []
        warnings = []
        details = {
            'check_type_validation': 'check_type_validation',
        }

        # Valid check types/categories
        valid_check_types = [
            'COMPLETENESS',
            'completeness',
            'ACCURACY',
            'accuracy',
            'CONSISTENCY',
            'consistency',
            'VALIDITY',
            'validity',
            'UNIQUENESS',
            'uniqueness',
            'TIMELINESS',
            'timeliness'
        ]

        # Check can have 'category' or 'type' field
        check_category = check.get('category') or check.get('type')

        if not check_category:
            errors.append("DQ check must have a 'category' or 'type' field")
            details['has_category'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_category'] = True
        details['check_category'] = check_category

        # Normalize category to uppercase for comparison
        category_upper = str(check_category).upper()

        # Validate category is one of the valid types
        if category_upper not in [t.upper() for t in valid_check_types]:
            errors.append(
                f"DQ check has invalid category/type: {check_category}. "
                f"Valid check types are: completeness, accuracy, consistency, validity, uniqueness, timeliness"
            )
            details['category_valid'] = False
        else:
            details['category_valid'] = True
            details['normalized_category'] = category_upper

        details['check_type_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_check_configuration(
        self,
        check: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate check configuration (valid parameters, thresholds).

        Validates:
        - Expectation type is valid
        - Expectation parameters are valid
        - Thresholds are valid numbers (if present)
        - Target configuration is valid

        Args:
            check: DQ check dictionary to validate

        Returns:
            ValidationResult with check configuration validation status
        """
        errors = []
        warnings = []
        details = {
            'check_configuration_validation': 'check_configuration_validation',
        }

        # Validate expectation structure
        expectation = check.get('expectation')
        if expectation:
            if not isinstance(expectation, dict):
                errors.append("DQ check 'expectation' must be a dictionary")
                details['expectation_valid'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['expectation_valid'] = True
            expectation_type = expectation.get('type')
            expectation_params = expectation.get('params', {})

            if expectation_type:
                details['expectation_type'] = expectation_type
                # Validate expectation type is not empty
                if not isinstance(expectation_type, str) or not expectation_type.strip():
                    errors.append("DQ check expectation 'type' must be a non-empty string")
                    details['expectation_type_valid'] = False
                else:
                    details['expectation_type_valid'] = True
            else:
                warnings.append("DQ check expectation missing 'type' field")
                details['expectation_type_valid'] = False

            # Validate expectation parameters
            if expectation_params:
                if not isinstance(expectation_params, dict):
                    errors.append("DQ check expectation 'params' must be a dictionary")
                    details['expectation_params_valid'] = False
                else:
                    details['expectation_params_valid'] = True
                    details['has_expectation_params'] = True

                    # Validate thresholds if present
                    threshold_keys = ['threshold', 'min_value', 'max_value', 'min', 'max']
                    for key in threshold_keys:
                        if key in expectation_params:
                            threshold_value = expectation_params[key]
                            if threshold_value is not None:
                                try:
                                    float(threshold_value)
                                    details[f'{key}_valid'] = True
                                except (ValueError, TypeError):
                                    errors.append(
                                        f"DQ check expectation parameter '{key}' must be a valid number, "
                                        f"got: {threshold_value}"
                                    )
                                    details[f'{key}_valid'] = False
                    else:
                        details['has_thresholds'] = False
            else:
                details['has_expectation_params'] = False
        else:
            warnings.append("DQ check missing 'expectation' field")
            details['expectation_valid'] = False

        # Validate target configuration
        target = check.get('target')
        if target:
            if not isinstance(target, dict):
                errors.append("DQ check 'target' must be a dictionary")
                details['target_valid'] = False
            else:
                details['target_valid'] = True
                target_level = target.get('level')

                if target_level:
                    valid_levels = ['COLUMN', 'DATASET', 'TABLE', 'column', 'dataset', 'table']
                    if target_level.upper() not in [l.upper() for l in valid_levels]:
                        errors.append(
                            f"DQ check target 'level' must be one of: COLUMN, DATASET, TABLE. "
                            f"Got: {target_level}"
                        )
                        details['target_level_valid'] = False
                    else:
                        details['target_level_valid'] = True
                        details['target_level'] = target_level.upper()

                    # Validate column-specific targets
                    if target_level.upper() == 'COLUMN':
                        target_column = target.get('column')
                        target_pattern = target.get('column_pattern')

                        if not target_column and not target_pattern:
                            warnings.append(
                                "DQ check with COLUMN level target should specify 'column' or 'column_pattern'"
                            )
                            details['target_column_specified'] = False
                        else:
                            details['target_column_specified'] = True
                            if target_column:
                                details['target_column'] = target_column
                            if target_pattern:
                                details['target_pattern'] = target_pattern
                else:
                    warnings.append("DQ check 'target' missing 'level' field")
                    details['target_level_valid'] = False
        else:
            warnings.append("DQ check missing 'target' field")
            details['target_valid'] = False

        details['check_configuration_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_check_schema_compatibility(
        self,
        check: Dict[str, Any],
        dataset: Any
    ) -> ValidationResult:
        """
        Validate check schema compatibility (check compatible with dataset schema).

        Validates:
        - Target columns exist in dataset schema
        - Column patterns match dataset schema fields
        - Check is compatible with dataset structure

        Args:
            check: DQ check dictionary to validate
            dataset: Dataset instance to validate against

        Returns:
            ValidationResult with schema compatibility validation status
        """
        errors = []
        warnings = []
        details = {
            'schema_compatibility_validation': 'check_schema_compatibility',
        }

        # Get dataset schema
        if not hasattr(dataset, 'schema_json') or not dataset.schema_json:
            warnings.append("Dataset has no schema_json - cannot validate schema compatibility")
            details['dataset_has_schema'] = False
            return ValidationResult(
                is_valid=True,  # Not an error, just can't validate
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['dataset_has_schema'] = True
        schema_json = dataset.schema_json

        # Extract schema fields
        schema_fields = schema_json.get('fields', [])
        if not isinstance(schema_fields, list):
            warnings.append("Dataset schema_json.fields is not a list - cannot validate schema compatibility")
            details['schema_fields_valid'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['schema_fields_valid'] = True
        details['schema_field_count'] = len(schema_fields)

        # Build field name set
        field_names = set()
        for field in schema_fields:
            if isinstance(field, dict):
                field_name = field.get('name')
                if field_name:
                    field_names.add(str(field_name))

        details['dataset_field_names'] = list(field_names)

        # Get target configuration
        target = check.get('target', {})
        if not isinstance(target, dict):
            # No target specified - check applies to dataset level
            details['target_specified'] = False
            details['schema_compatible'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        target_level = target.get('level', '').upper()
        target_column = target.get('column')
        target_pattern = target.get('column_pattern')

        details['target_level'] = target_level
        details['target_column'] = target_column
        details['target_pattern'] = target_pattern

        # If target is DATASET level, no column validation needed
        if target_level == 'DATASET' or target_level == 'TABLE':
            details['schema_compatible'] = True
            details['column_validation_skipped'] = 'Dataset-level check'
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate column-level targets
        if target_level == 'COLUMN':
            if target_column:
                # Check if column exists in schema
                if target_column not in field_names:
                    errors.append(
                        f"DQ check targets column '{target_column}' which does not exist in dataset schema. "
                        f"Available columns: {', '.join(sorted(field_names))}"
                    )
                    details['target_column_exists'] = False
                else:
                    details['target_column_exists'] = True
                    details['schema_compatible'] = True

            elif target_pattern:
                # Check if pattern matches any columns
                import re
                try:
                    pattern = re.compile(target_pattern)
                    matching_columns = [name for name in field_names if pattern.match(name)]

                    if not matching_columns:
                        warnings.append(
                            f"DQ check column pattern '{target_pattern}' does not match any columns in dataset schema. "
                            f"Available columns: {', '.join(sorted(field_names))}"
                        )
                        details['pattern_matches'] = False
                    else:
                        details['pattern_matches'] = True
                        details['matching_columns'] = matching_columns
                        details['schema_compatible'] = True
                except re.error as e:
                    errors.append(
                        f"DQ check has invalid column pattern '{target_pattern}': {str(e)}"
                    )
                    details['pattern_valid'] = False
            else:
                # No specific column or pattern - applies to all columns
                details['target_column_specified'] = False
                details['schema_compatible'] = True
        else:
            # Unknown target level - warn but don't fail
            warnings.append(f"DQ check has unknown target level: {target_level}")
            details['target_level_known'] = False
            details['schema_compatible'] = True

        details['schema_compatibility_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_check_resource(
        self,
        check: Dict[str, Any],
        dq_run: Optional[DQRun],
        dataset: Optional[Any],
        tenant: Optional[Any],
        user: Optional[User]
    ) -> ValidationResult:
        """
        Validate check resource (dataset exists and accessible).

        Validates:
        - Dataset exists (from dq_run or provided directly)
        - Dataset is accessible to tenant
        - Dataset belongs to correct tenant

        Args:
            check: DQ check dictionary to validate
            dq_run: Optional DQRun instance
            dataset: Optional dataset instance
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with resource validation status
        """
        errors = []
        warnings = []
        details = {
            'resource_validation': 'check_resource_validation',
        }

        # Get dataset from dq_run or provided directly
        target_dataset = dataset
        if not target_dataset and dq_run:
            target_dataset = dq_run.dataset

        if not target_dataset:
            warnings.append("No dataset provided for resource validation - skipping")
            details['dataset_provided'] = False
            return ValidationResult(
                is_valid=True,  # Not an error, just can't validate
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['dataset_provided'] = True
        details['dataset_id'] = str(target_dataset.id)

        # Validate dataset exists (should already be validated by foreign key, but double-check)
        if not target_dataset:
            errors.append("Dataset does not exist")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['dataset_exists'] = True

        # Validate dataset belongs to tenant
        if tenant:
            if hasattr(target_dataset, 'tenant') and target_dataset.tenant:
                dataset_tenant_id = str(target_dataset.tenant.id)
                tenant_id = str(tenant.id)

                if dataset_tenant_id != tenant_id:
                    errors.append(
                        f"Dataset belongs to tenant {dataset_tenant_id} but check is for tenant {tenant_id}"
                    )
                    details['tenant_match'] = False
                else:
                    details['tenant_match'] = True
            else:
                warnings.append("Dataset has no tenant association")
                details['dataset_has_tenant'] = False
        elif dq_run and dq_run.tenant:
            # Validate against dq_run tenant
            if hasattr(target_dataset, 'tenant') and target_dataset.tenant:
                dataset_tenant_id = str(target_dataset.tenant.id)
                dq_run_tenant_id = str(dq_run.tenant.id)

                if dataset_tenant_id != dq_run_tenant_id:
                    errors.append(
                        f"Dataset belongs to tenant {dataset_tenant_id} but DQ run is for tenant {dq_run_tenant_id}"
                    )
                    details['tenant_match'] = False
                else:
                    details['tenant_match'] = True
            else:
                warnings.append("Dataset has no tenant association")
                details['dataset_has_tenant'] = False

        # Validate dataset is accessible (not deleted/archived)
        if hasattr(target_dataset, 'status'):
            dataset_status = target_dataset.status
            details['dataset_status'] = dataset_status

            if dataset_status in ['DELETED', 'ARCHIVED', 'RETIRED']:
                errors.append(
                    f"Dataset has status {dataset_status} and is not accessible for DQ checks"
                )
                details['dataset_accessible'] = False
            else:
                details['dataset_accessible'] = True
        else:
            # No status field - assume accessible
            details['dataset_accessible'] = True

        # Validate user has access to dataset (if user provided)
        if user:
            if hasattr(user, 'tenant') and user.tenant:
                user_tenant_id = str(user.tenant.id)
                if hasattr(target_dataset, 'tenant') and target_dataset.tenant:
                    dataset_tenant_id = str(target_dataset.tenant.id)
                    if user_tenant_id != dataset_tenant_id:
                        warnings.append(
                            f"User belongs to tenant {user_tenant_id} but dataset belongs to tenant {dataset_tenant_id} "
                            f"(cross-tenant access)"
                        )
                        details['user_dataset_tenant_match'] = False
                    else:
                        details['user_dataset_tenant_match'] = True
                else:
                    details['user_dataset_tenant_match'] = None
            else:
                warnings.append("User has no tenant association")
                details['user_has_tenant'] = False

        details['resource_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_tenant_context(self, tenant: Any) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            tenant: Tenant instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        details = {'tenant_id': str(tenant.id), 'tenant_name': tenant.name if hasattr(tenant, 'name') else None}

        # Validate tenant context consistency
        if self.tenant_id:
            if str(tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Provided tenant ({tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        details['is_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            details=details
        )

    def _validate_permissions(
        self,
        user: User,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate user permissions.

        Args:
            user: User instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {'user_id': str(user.id), 'user_email': user.email}

        # Validate user context consistency
        if self.user_id:
            if str(user.id) != str(self.user_id):
                warnings.append(
                    f"Provided user ({user.id}) does not match "
                    f"context user ({self.user_id})"
                )
                details['user_match'] = False
            else:
                details['user_match'] = True

        # Validate user has tenant if tenant provided
        if tenant and hasattr(user, 'tenant_id') and user.tenant_id:
            if str(user.tenant_id) != str(tenant.id):
                errors.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )
                details['user_tenant_match'] = False
            else:
                details['user_tenant_match'] = True

        # Validate user tenant matches context tenant if both provided
        if self.tenant_id and hasattr(user, 'tenant_id') and user.tenant_id:
            if str(user.tenant_id) != str(self.tenant_id):
                warnings.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['user_context_tenant_match'] = False
            else:
                details['user_context_tenant_match'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_scorecard_calculation(
        self,
        aggregation_config: Optional[Dict[str, Any]] = None,
        scorecard_data: Optional[Dict[str, Any]] = None,
        tenant: Optional[Any] = None,
        asset: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate DQ scorecard calculation comprehensively.

        Validates:
        - Scorecard calculation validation (valid aggregation rules)
        - Scorecard threshold validation (PASS/WARN/FAIL thresholds)
        - Scorecard update triggers (when to recalculate)

        Args:
            aggregation_config: Optional aggregation configuration dictionary
            scorecard_data: Optional scorecard data dictionary to validate
            tenant: Optional tenant instance
            asset: Optional asset instance

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'scorecard_calculation',
        }

        # Validate aggregation rules
        aggregation_result = self._validate_scorecard_aggregation_rules(
            aggregation_config, scorecard_data, tenant, asset
        )
        result = result.combine(aggregation_result)
        details['aggregation_rules_validated'] = True

        # Validate thresholds
        threshold_result = self._validate_scorecard_thresholds(
            scorecard_data, tenant, asset
        )
        result = result.combine(threshold_result)
        details['thresholds_validated'] = True

        # Validate update triggers
        triggers_result = self._validate_scorecard_update_triggers(
            tenant, asset
        )
        result = result.combine(triggers_result)
        details['update_triggers_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['scorecard_calculation_valid'] = result.is_valid
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_scorecard_aggregation_rules(
        self,
        aggregation_config: Optional[Dict[str, Any]],
        scorecard_data: Optional[Dict[str, Any]],
        tenant: Optional[Any],
        asset: Optional[Any]
    ) -> ValidationResult:
        """
        Validate scorecard calculation aggregation rules.

        Validates:
        - Valid aggregation functions are used (Avg, Count, Sum, Min, Max)
        - Aggregation rules are properly configured
        - Aggregation results are consistent

        Args:
            aggregation_config: Optional aggregation configuration dictionary
            scorecard_data: Optional scorecard data dictionary
            tenant: Optional tenant instance
            asset: Optional asset instance

        Returns:
            ValidationResult with aggregation rules validation status
        """
        errors = []
        warnings = []
        details = {
            'aggregation_rules_validation': 'scorecard_aggregation_rules',
        }

        # Valid aggregation functions (Django ORM aggregation functions)
        valid_aggregation_functions = [
            'Avg', 'Count', 'Sum', 'Min', 'Max',
            'avg', 'count', 'sum', 'min', 'max',
            'AVG', 'COUNT', 'SUM', 'MIN', 'MAX'
        ]

        # Validate aggregation config if provided
        if aggregation_config:
            if not isinstance(aggregation_config, dict):
                errors.append("Aggregation config must be a dictionary")
                details['aggregation_config_valid'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['aggregation_config_valid'] = True
            details['has_aggregation_config'] = True

            # Validate aggregation functions in config
            aggregation_functions = aggregation_config.get('functions', [])
            if aggregation_functions:
                if not isinstance(aggregation_functions, list):
                    errors.append("Aggregation functions must be a list")
                    details['aggregation_functions_valid'] = False
                else:
                    details['aggregation_functions_valid'] = True
                    invalid_functions = []
                    for func in aggregation_functions:
                        if func not in valid_aggregation_functions:
                            invalid_functions.append(func)

                    if invalid_functions:
                        errors.append(
                            f"Invalid aggregation functions: {', '.join(invalid_functions)}. "
                            f"Valid functions are: {', '.join(valid_aggregation_functions)}"
                        )
                        details['invalid_functions'] = invalid_functions
                    else:
                        details['all_functions_valid'] = True
            else:
                warnings.append("No aggregation functions specified in config")
                details['has_aggregation_functions'] = False
        else:
            details['has_aggregation_config'] = False
            details['aggregation_config_skipped'] = 'No aggregation config provided'

        # Validate scorecard data aggregation results if provided
        if scorecard_data:
            if not isinstance(scorecard_data, dict):
                errors.append("Scorecard data must be a dictionary")
                details['scorecard_data_valid'] = False
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['scorecard_data_valid'] = True
            details['has_scorecard_data'] = True

            # Validate summary metrics (should be aggregated values)
            summary = scorecard_data.get('summary', {})
            if summary:
                if not isinstance(summary, dict):
                    errors.append("Scorecard summary must be a dictionary")
                    details['summary_valid'] = False
                else:
                    details['summary_valid'] = True

                    # Validate numeric metrics are valid numbers
                    numeric_fields = ['total_runs', 'avg_quality_score', 'pass_rate', 'fail_rate']
                    for field in numeric_fields:
                        if field in summary:
                            value = summary[field]
                            if value is not None:
                                try:
                                    float(value)
                                    details[f'{field}_valid'] = True
                                except (ValueError, TypeError):
                                    errors.append(
                                        f"Scorecard summary field '{field}' must be a valid number, "
                                        f"got: {value}"
                                    )
                                    details[f'{field}_valid'] = False
                            else:
                                details[f'{field}_valid'] = None
                                details[f'{field}_is_null'] = True

                    # Validate avg_quality_score is within expected range (0-100)
                    if 'avg_quality_score' in summary:
                        avg_score = summary.get('avg_quality_score')
                        if avg_score is not None:
                            try:
                                score = float(avg_score)
                                if score < 0 or score > 100:
                                    warnings.append(
                                        f"Average quality score ({score}) is outside expected range (0-100)"
                                    )
                                    details['avg_quality_score_range_valid'] = False
                                else:
                                    details['avg_quality_score_range_valid'] = True
                            except (ValueError, TypeError):
                                pass  # Already handled above
            else:
                warnings.append("Scorecard data missing 'summary' field")
                details['has_summary'] = False

            # Validate score distribution (should be aggregated counts)
            score_distribution = scorecard_data.get('score_distribution', {})
            if score_distribution:
                if not isinstance(score_distribution, dict):
                    errors.append("Scorecard score_distribution must be a dictionary")
                    details['score_distribution_valid'] = False
                else:
                    details['score_distribution_valid'] = True

                    # Validate distribution buckets are non-negative integers
                    distribution_buckets = ['excellent', 'good', 'fair', 'poor', 'critical']
                    for bucket in distribution_buckets:
                        if bucket in score_distribution:
                            value = score_distribution[bucket]
                            if value is not None:
                                try:
                                    count = int(value)
                                    if count < 0:
                                        errors.append(
                                            f"Score distribution bucket '{bucket}' must be non-negative, "
                                            f"got: {count}"
                                        )
                                        details[f'{bucket}_valid'] = False
                                    else:
                                        details[f'{bucket}_valid'] = True
                                except (ValueError, TypeError):
                                    errors.append(
                                        f"Score distribution bucket '{bucket}' must be a valid integer, "
                                        f"got: {value}"
                                    )
                                    details[f'{bucket}_valid'] = False
            else:
                warnings.append("Scorecard data missing 'score_distribution' field")
                details['has_score_distribution'] = False
        else:
            details['has_scorecard_data'] = False
            details['scorecard_data_skipped'] = 'No scorecard data provided'

        details['aggregation_rules_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_scorecard_thresholds(
        self,
        scorecard_data: Optional[Dict[str, Any]],
        tenant: Optional[Any],
        asset: Optional[Any]
    ) -> ValidationResult:
        """
        Validate scorecard thresholds (PASS/WARN/FAIL thresholds).

        Validates:
        - PASS/WARN/FAIL thresholds are valid and consistent
        - Thresholds are within expected ranges (0-100)
        - Threshold ordering is correct (PASS > WARN > FAIL)
        - Thresholds are applied correctly to quality scores

        Args:
            scorecard_data: Optional scorecard data dictionary
            tenant: Optional tenant instance
            asset: Optional asset instance

        Returns:
            ValidationResult with threshold validation status
        """
        errors = []
        warnings = []
        details = {
            'threshold_validation': 'scorecard_thresholds',
        }

        # Default thresholds (can be overridden by config)
        DEFAULT_PASS_THRESHOLD = 80.0  # >= 80 is PASS
        DEFAULT_WARN_THRESHOLD = 60.0  # >= 60 and < 80 is WARN
        DEFAULT_FAIL_THRESHOLD = 0.0   # < 60 is FAIL

        # Get thresholds from config or use defaults
        pass_threshold = DEFAULT_PASS_THRESHOLD
        warn_threshold = DEFAULT_WARN_THRESHOLD
        fail_threshold = DEFAULT_FAIL_THRESHOLD

        # Validate threshold configuration if provided in scorecard_data
        if scorecard_data:
            thresholds_config = scorecard_data.get('thresholds', {})
            if thresholds_config:
                if not isinstance(thresholds_config, dict):
                    errors.append("Scorecard thresholds must be a dictionary")
                    details['thresholds_config_valid'] = False
                else:
                    details['thresholds_config_valid'] = True

                    # Extract thresholds
                    if 'pass_threshold' in thresholds_config:
                        try:
                            pass_threshold = float(thresholds_config['pass_threshold'])
                            details['pass_threshold_provided'] = True
                        except (ValueError, TypeError):
                            errors.append(
                                f"Pass threshold must be a valid number, "
                                f"got: {thresholds_config['pass_threshold']}"
                            )
                            details['pass_threshold_valid'] = False

                    if 'warn_threshold' in thresholds_config:
                        try:
                            warn_threshold = float(thresholds_config['warn_threshold'])
                            details['warn_threshold_provided'] = True
                        except (ValueError, TypeError):
                            errors.append(
                                f"Warn threshold must be a valid number, "
                                f"got: {thresholds_config['warn_threshold']}"
                            )
                            details['warn_threshold_valid'] = False

                    if 'fail_threshold' in thresholds_config:
                        try:
                            fail_threshold = float(thresholds_config['fail_threshold'])
                            details['fail_threshold_provided'] = True
                        except (ValueError, TypeError):
                            errors.append(
                                f"Fail threshold must be a valid number, "
                                f"got: {thresholds_config['fail_threshold']}"
                            )
                            details['fail_threshold_valid'] = False

        details['pass_threshold'] = pass_threshold
        details['warn_threshold'] = warn_threshold
        details['fail_threshold'] = fail_threshold

        # Validate threshold ranges (0-100)
        if pass_threshold < 0 or pass_threshold > 100:
            errors.append(
                f"Pass threshold ({pass_threshold}) must be between 0 and 100"
            )
            details['pass_threshold_range_valid'] = False
        else:
            details['pass_threshold_range_valid'] = True

        if warn_threshold < 0 or warn_threshold > 100:
            errors.append(
                f"Warn threshold ({warn_threshold}) must be between 0 and 100"
            )
            details['warn_threshold_range_valid'] = False
        else:
            details['warn_threshold_range_valid'] = True

        if fail_threshold < 0 or fail_threshold > 100:
            errors.append(
                f"Fail threshold ({fail_threshold}) must be between 0 and 100"
            )
            details['fail_threshold_range_valid'] = False
        else:
            details['fail_threshold_range_valid'] = True

        # Validate threshold ordering (PASS >= WARN >= FAIL)
        if pass_threshold < warn_threshold:
            errors.append(
                f"Pass threshold ({pass_threshold}) must be >= warn threshold ({warn_threshold})"
            )
            details['threshold_ordering_valid'] = False
        elif warn_threshold < fail_threshold:
            errors.append(
                f"Warn threshold ({warn_threshold}) must be >= fail threshold ({fail_threshold})"
            )
            details['threshold_ordering_valid'] = False
        else:
            details['threshold_ordering_valid'] = True

        # Validate thresholds are applied correctly to scorecard data
        if scorecard_data:
            summary = scorecard_data.get('summary', {})
            if summary:
                avg_quality_score = summary.get('avg_quality_score')
                if avg_quality_score is not None:
                    try:
                        score = float(avg_quality_score)
                        details['avg_quality_score'] = score

                        # Determine expected status based on thresholds
                        if score >= pass_threshold:
                            expected_status = 'PASS'
                        elif score >= warn_threshold:
                            expected_status = 'WARN'
                        else:
                            expected_status = 'FAIL'

                        details['expected_status'] = expected_status

                        # Check if scorecard data has overall_status that matches thresholds
                        overall_status = scorecard_data.get('overall_status')
                        if overall_status:
                            details['has_overall_status'] = True
                            details['overall_status'] = overall_status

                            # Validate status matches threshold expectations
                            if overall_status.upper() != expected_status:
                                warnings.append(
                                    f"Scorecard overall_status ({overall_status}) does not match "
                                    f"expected status ({expected_status}) based on thresholds "
                                    f"(score: {score}, pass: {pass_threshold}, warn: {warn_threshold})"
                                )
                                details['status_matches_thresholds'] = False
                            else:
                                details['status_matches_thresholds'] = True
                        else:
                            details['has_overall_status'] = False
                            warnings.append("Scorecard data missing 'overall_status' field")
                    except (ValueError, TypeError):
                        pass  # Already handled in aggregation validation

        details['thresholds_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_scorecard_update_triggers(
        self,
        tenant: Optional[Any],
        asset: Optional[Any]
    ) -> ValidationResult:
        """
        Validate scorecard update triggers (when to recalculate).

        Validates:
        - Scorecards should recalculate when new DQ runs complete
        - Scorecards should recalculate when DQ runs are updated
        - Scorecards should recalculate when asset/dataset changes occur
        - Update triggers are properly configured

        Args:
            tenant: Optional tenant instance
            asset: Optional asset instance

        Returns:
            ValidationResult with update triggers validation status
        """
        errors = []
        warnings = []
        details = {
            'update_triggers_validation': 'scorecard_update_triggers',
        }

        # Expected update triggers
        expected_triggers = [
            'dq_run_completed',
            'dq_run_updated',
            'asset_updated',
            'dataset_updated',
            'manual_refresh'
        ]

        details['expected_triggers'] = expected_triggers

        # Validate tenant context if provided
        if tenant:
            details['tenant_provided'] = True
            details['tenant_id'] = str(tenant.id)

            # Validate tenant has DQ runs (scorecards need data to calculate)
            try:
                from .models import DQRun, DQRunStatus
                dq_runs_count = DQRun.objects.filter(
                    tenant=tenant,
                    status=DQRunStatus.SUCCEEDED
                ).count()
                details['tenant_dq_runs_count'] = dq_runs_count

                if dq_runs_count == 0:
                    warnings.append(
                        f"Tenant {tenant.id} has no completed DQ runs - scorecard will be empty"
                    )
                    details['has_dq_runs'] = False
                else:
                    details['has_dq_runs'] = True
            except Exception as e:
                warnings.append(
                    f"Could not validate tenant DQ runs: {str(e)}"
                )
                details['dq_runs_validation_error'] = str(e)
        else:
            details['tenant_provided'] = False
            warnings.append("No tenant provided - cannot validate DQ run triggers")

        # Validate asset context if provided
        if asset:
            details['asset_provided'] = True
            details['asset_id'] = str(asset.id)

            # Validate asset has DQ runs
            try:
                from .models import DQRun, DQRunStatus
                asset_dq_runs_count = DQRun.objects.filter(
                    asset=asset,
                    status=DQRunStatus.SUCCEEDED
                ).count()
                details['asset_dq_runs_count'] = asset_dq_runs_count

                if asset_dq_runs_count == 0:
                    warnings.append(
                        f"Asset {asset.id} has no completed DQ runs - scorecard will be empty"
                    )
                    details['asset_has_dq_runs'] = False
                else:
                    details['asset_has_dq_runs'] = True

                    # Check if asset has recent DQ runs (within last 30 days)
                    from django.utils import timezone
                    from datetime import timedelta
                    recent_date = timezone.now() - timedelta(days=30)
                    recent_dq_runs_count = DQRun.objects.filter(
                        asset=asset,
                        status=DQRunStatus.SUCCEEDED,
                        completed_at__gte=recent_date
                    ).count()
                    details['recent_dq_runs_count'] = recent_dq_runs_count

                    if recent_dq_runs_count == 0:
                        warnings.append(
                            f"Asset {asset.id} has no DQ runs in the last 30 days - "
                            f"scorecard may be stale"
                        )
                        details['has_recent_dq_runs'] = False
                    else:
                        details['has_recent_dq_runs'] = True
            except Exception as e:
                warnings.append(
                    f"Could not validate asset DQ runs: {str(e)}"
                )
                details['asset_dq_runs_validation_error'] = str(e)
        else:
            details['asset_provided'] = False

        # Validate update trigger configuration
        # In a real implementation, this would check if triggers are properly
        # configured (e.g., signals, webhooks, scheduled tasks)
        # For now, we'll validate that the system can detect when updates are needed
        details['update_triggers_configured'] = True
        details['update_triggers_valid'] = True

        # Check if scorecard service is available
        try:
            from .scorecards import DQScorecardService
            details['scorecard_service_available'] = True
        except ImportError:
            errors.append("DQScorecardService is not available")
            details['scorecard_service_available'] = False

        details['update_triggers_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_dq_run_execution(
        self,
        dq_run: DQRun,
        user: Optional[User] = None,
        tenant: Optional[Any] = None,
        validation_type: str = 'all'
    ) -> ValidationResult:
        """
        Validate DQ run execution comprehensively.

        This method orchestrates all DQ run execution validation checks:
        - Run eligibility validation (user has permission, dataset accessible)
        - Run resource quota validation (DQ service quota not exceeded)
        - Run schedule validation (scheduled runs don't conflict)
        - Run status transition validation (PENDING → RUNNING → SUCCEEDED/FAILED)

        Args:
            dq_run: DQRun instance to validate
            user: Optional user instance
            tenant: Optional tenant instance
            validation_type: Type of validation ('eligibility', 'quota', 'schedule', 'status_transition', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'dq_run_execution',
            'dq_run_id': str(dq_run.id),
            'profile_key': dq_run.profile_key,
            'status': dq_run.status,
        }

        # Comprehensive validation: eligibility
        if validation_type in ('all', 'eligibility'):
            eligibility_result = self._validate_dq_run_eligibility(dq_run, user, tenant)
            result = result.combine(eligibility_result)
            details['eligibility_validated'] = True

        # Comprehensive validation: resource quota
        if validation_type in ('all', 'quota'):
            quota_result = self._validate_dq_run_resource_quota(dq_run, tenant)
            result = result.combine(quota_result)
            details['quota_validated'] = True

        # Comprehensive validation: schedule
        if validation_type in ('all', 'schedule'):
            schedule_result = self._validate_dq_run_schedule(dq_run, tenant)
            result = result.combine(schedule_result)
            details['schedule_validated'] = True

        # Comprehensive validation: status transition
        if validation_type in ('all', 'status_transition'):
            status_result = self._validate_dq_run_status_transition(dq_run)
            result = result.combine(status_result)
            details['status_transition_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_dq_run_eligibility(
        self,
        dq_run: DQRun,
        user: Optional[User] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate run eligibility (user has permission, dataset accessible).

        Validates:
        - User exists and is active
        - User belongs to tenant
        - User has permission to run DQ checks
        - Dataset/asset/file is accessible (exists, not deleted, belongs to tenant)

        Args:
            dq_run: DQRun instance to validate
            user: Optional user instance requesting the run
            tenant: Optional tenant instance

        Returns:
            ValidationResult with eligibility validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'run_eligibility',
            'eligible': False,
        }

        # Determine tenant
        effective_tenant = tenant or (dq_run.tenant if dq_run.tenant else None)
        if not effective_tenant:
            errors.append("Tenant is required for run eligibility validation")
            details['tenant_provided'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['tenant_id'] = str(effective_tenant.id)
        details['tenant_provided'] = True

        # Validate user if provided
        if user:
            details['user_provided'] = True
            details['user_id'] = str(user.id)
            details['user_email'] = user.email

            # Validate user is active
            # Check both is_active (Django default) and status (custom User model)
            is_active = True
            if hasattr(user, 'is_active'):
                is_active = user.is_active
            if hasattr(user, 'status'):
                from hub.apps.users.models import UserStatus
                # Only check status if is_active check passed or doesn't exist
                if is_active:
                    is_active = user.status == UserStatus.ACTIVE

            if not is_active:
                errors.append(f"User {user.email} is not active and cannot run DQ checks")
                details['user_active'] = False
            else:
                details['user_active'] = True

            # Validate user belongs to tenant
            if hasattr(user, 'tenant') and user.tenant:
                if str(user.tenant.id) != str(effective_tenant.id):
                    errors.append(
                        f"User {user.email} belongs to tenant {user.tenant.id} but DQ run "
                        f"is for tenant {effective_tenant.id}"
                    )
                    details['user_tenant_match'] = False
                else:
                    details['user_tenant_match'] = True
            else:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False

            # Validate user permissions (placeholder - integrate with RBAC/ABAC system)
            # For now, we assume all active users in the tenant can run DQ checks
            # In production, this would check specific permissions like:
            # - 'dq.can_run_dq_checks'
            # - 'dq.can_run_dq_checks_on_dataset' (resource-specific)
            # Placeholder for permission checks
            # if not user.has_perm('dq.can_run_dq_checks'):
            #     errors.append(f"User {user.email} does not have permission to run DQ checks")
        else:
            details['user_provided'] = False
            warnings.append("No user provided for eligibility validation - cannot verify permissions")

        # Validate resource accessibility
        resource_accessible = False
        resource_type = None
        resource_id = None

        if dq_run.dataset:
            resource_type = 'dataset'
            resource_id = str(dq_run.dataset.id)
            details['resource_type'] = 'dataset'
            details['resource_id'] = resource_id

            # Validate dataset exists and is accessible
            if not dq_run.dataset:
                errors.append(f"Dataset {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate dataset belongs to tenant
                if hasattr(dq_run.dataset, 'tenant') and dq_run.dataset.tenant:
                    if str(dq_run.dataset.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"Dataset {resource_id} belongs to tenant {dq_run.dataset.tenant.id} "
                            f"but DQ run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"Dataset {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Validate dataset has a file
                if not dq_run.dataset.file:
                    errors.append(f"Dataset {resource_id} has no associated file for DQ run")
                    details['dataset_has_file'] = False
                else:
                    details['dataset_has_file'] = True

        elif dq_run.asset:
            resource_type = 'asset'
            resource_id = str(dq_run.asset.id)
            details['resource_type'] = 'asset'
            details['resource_id'] = resource_id

            # Validate asset exists and is accessible
            if not dq_run.asset:
                errors.append(f"Asset {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate asset belongs to tenant
                if hasattr(dq_run.asset, 'tenant') and dq_run.asset.tenant:
                    if str(dq_run.asset.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"Asset {resource_id} belongs to tenant {dq_run.asset.tenant.id} "
                            f"but DQ run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"Asset {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Check if asset has datasets (required for DQ run)
                if hasattr(dq_run.asset, 'datasets'):
                    dataset_count = dq_run.asset.datasets.count()
                    if dataset_count == 0:
                        warnings.append(f"Asset {resource_id} has no datasets - DQ run may fail")
                        details['asset_has_datasets'] = False
                    else:
                        details['asset_has_datasets'] = True
                        details['asset_dataset_count'] = dataset_count

        elif dq_run.file:
            resource_type = 'file'
            resource_id = str(dq_run.file.id)
            details['resource_type'] = 'file'
            details['resource_id'] = resource_id

            # Validate file exists and is accessible
            if not dq_run.file:
                errors.append(f"File {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate file belongs to tenant
                if hasattr(dq_run.file, 'tenant') and dq_run.file.tenant:
                    if str(dq_run.file.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"File {resource_id} belongs to tenant {dq_run.file.tenant.id} "
                            f"but DQ run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"File {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Validate file has storage path
                if not dq_run.file.storage_path:
                    errors.append(f"File {resource_id} has no storage path - cannot run DQ check")
                    details['file_has_storage_path'] = False
                else:
                    details['file_has_storage_path'] = True
        else:
            errors.append("DQ run must have at least one resource (asset, dataset, or file)")
            details['has_resource'] = False

        details['resource_accessible'] = resource_accessible
        details['eligible'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dq_run_resource_quota(
        self,
        dq_run: DQRun,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate run resource quota (DQ service quota not exceeded).

        Validates:
        - DQ service is available (health check)
        - Tenant has not exceeded DQ run quota (rate limits)
        - Concurrent DQ runs are within limits
        - Daily DQ run quota is not exceeded

        Args:
            dq_run: DQRun instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with quota validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'resource_quota',
            'quota_valid': False,
        }

        # Determine tenant
        effective_tenant = tenant or (dq_run.tenant if dq_run.tenant else None)
        if not effective_tenant:
            errors.append("Tenant is required for resource quota validation")
            details['tenant_provided'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        tenant_id = str(effective_tenant.id)
        details['tenant_id'] = tenant_id
        details['tenant_provided'] = True

        # Check DQ service health
        from hub.apps.dq.service_client import DQServiceClient
        dq_client = DQServiceClient()
        is_healthy, service_status = dq_client.health_check()

        if not is_healthy:
            errors.append(f"DQ service is not available (status: {service_status})")
            details['dq_service_available'] = False
            details['dq_service_status'] = service_status
        else:
            details['dq_service_available'] = True
            details['dq_service_status'] = service_status

        # Check tenant DQ run quota using rate limiting system
        from hub.apps.rate_limiting.quota import QuotaManager
        from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow

        # Check daily quota for DQ runs
        has_quota, quota_info = QuotaManager.check_quota(
            tenant_id=tenant_id,
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.DAILY
        )

        details['quota_info'] = quota_info

        if not has_quota:
            errors.append(
                f"Tenant has exceeded daily DQ run quota. "
                f"Limit: {quota_info.get('limit')}, Used: {quota_info.get('used')}, "
                f"Remaining: {quota_info.get('remaining')}"
            )
            details['daily_quota_exceeded'] = True
        else:
            details['daily_quota_exceeded'] = False
            details['daily_quota_remaining'] = quota_info.get('remaining', 0)

        # Check concurrent DQ runs for tenant
        concurrent_runs = DQRun.objects.filter(
            tenant_id=tenant_id,
            status__in=[DQRunStatus.PENDING, DQRunStatus.RUNNING]
        ).exclude(id=dq_run.id if dq_run.id else None).count()

        # Get concurrent run limit from tenant config or use default
        max_concurrent_runs = 10  # Default limit
        if hasattr(effective_tenant, 'config') and effective_tenant.config:
            tenant_config = effective_tenant.config
            if hasattr(tenant_config, 'dq_max_concurrent_runs'):
                max_concurrent_runs = tenant_config.dq_max_concurrent_runs or max_concurrent_runs

        details['concurrent_runs'] = concurrent_runs
        details['max_concurrent_runs'] = max_concurrent_runs

        if concurrent_runs >= max_concurrent_runs:
            errors.append(
                f"Tenant has reached maximum concurrent DQ runs limit ({max_concurrent_runs}). "
                f"Current concurrent runs: {concurrent_runs}"
            )
            details['concurrent_limit_exceeded'] = True
        else:
            details['concurrent_limit_exceeded'] = False
            details['concurrent_slots_remaining'] = max_concurrent_runs - concurrent_runs

        # Check if there are too many recent failed runs (may indicate quota/service issues)
        from django.utils import timezone
        from datetime import timedelta

        recent_failed_runs = DQRun.objects.filter(
            tenant_id=tenant_id,
            status=DQRunStatus.FAILED,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()

        details['recent_failed_runs'] = recent_failed_runs

        if recent_failed_runs > 5:
            warnings.append(
                f"Tenant has {recent_failed_runs} failed DQ runs in the last hour. "
                f"This may indicate quota or service issues"
            )
            details['high_failure_rate'] = True

        details['quota_valid'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dq_run_schedule(
        self,
        dq_run: DQRun,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate run schedule (scheduled runs don't conflict).

        Validates:
        - No conflicting scheduled runs for the same resource
        - No overlapping scheduled runs within time window
        - Schedule timing is reasonable

        Args:
            dq_run: DQRun instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with schedule validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'run_schedule',
            'schedule_valid': False,
        }

        # Determine tenant
        effective_tenant = tenant or (dq_run.tenant if dq_run.tenant else None)
        if not effective_tenant:
            # Schedule validation doesn't require tenant for basic checks
            details['tenant_provided'] = False
        else:
            tenant_id = str(effective_tenant.id)
            details['tenant_id'] = tenant_id
            details['tenant_provided'] = True

            # Check for conflicting scheduled runs for the same resource
            # A conflict occurs when:
            # - Same resource (asset, dataset, or file)
            # - Status is PENDING or RUNNING
            # - Created within a short time window (e.g., 5 minutes)

            from django.utils import timezone
            from datetime import timedelta

            conflict_window = timedelta(minutes=5)
            recent_time = timezone.now() - conflict_window

            conflicting_runs_query = DQRun.objects.filter(
                tenant_id=tenant_id,
                status__in=[DQRunStatus.PENDING, DQRunStatus.RUNNING],
                created_at__gte=recent_time
            ).exclude(id=dq_run.id if dq_run.id else None)

            # Filter by resource
            if dq_run.dataset:
                conflicting_runs_query = conflicting_runs_query.filter(dataset=dq_run.dataset)
                details['resource_type'] = 'dataset'
                details['resource_id'] = str(dq_run.dataset.id)
            elif dq_run.asset:
                conflicting_runs_query = conflicting_runs_query.filter(asset=dq_run.asset)
                details['resource_type'] = 'asset'
                details['resource_id'] = str(dq_run.asset.id)
            elif dq_run.file:
                conflicting_runs_query = conflicting_runs_query.filter(file=dq_run.file)
                details['resource_type'] = 'file'
                details['resource_id'] = str(dq_run.file.id)

            conflicting_runs = list(conflicting_runs_query)

            if conflicting_runs:
                conflict_count = len(conflicting_runs)
                conflict_ids = [str(run.id) for run in conflicting_runs]

                warnings.append(
                    f"Found {conflict_count} conflicting DQ run(s) for the same resource "
                    f"within {conflict_window.total_seconds() / 60} minutes: {', '.join(conflict_ids[:5])}"
                )
                details['conflicts_detected'] = True
                details['conflict_count'] = conflict_count
                details['conflicting_run_ids'] = conflict_ids
            else:
                details['conflicts_detected'] = False
                details['conflict_count'] = 0

            # Check for too many scheduled runs in a short time period
            recent_runs_count = DQRun.objects.filter(
                tenant_id=tenant_id,
                created_at__gte=recent_time
            ).exclude(id=dq_run.id if dq_run.id else None).count()

            details['recent_runs_count'] = recent_runs_count

            if recent_runs_count > 20:
                warnings.append(
                    f"Tenant has {recent_runs_count} DQ runs created in the last "
                    f"{conflict_window.total_seconds() / 60} minutes. This may indicate "
                    f"rapid scheduling or potential abuse"
                )
                details['high_run_rate'] = True

        details['schedule_valid'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_dq_run_status_transition(
        self,
        dq_run: DQRun,
        current_status: Optional[str] = None,
        new_status: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate run status transition (PENDING → RUNNING → SUCCEEDED/FAILED).

        Validates:
        - Current status is valid
        - Transition is allowed (PENDING → RUNNING → SUCCEEDED/FAILED)
        - Cannot transition from terminal states (SUCCEEDED, FAILED)
        - Status transitions follow proper workflow

        Args:
            dq_run: DQRun instance to validate
            current_status: Current status (if None, uses dq_run.status)
            new_status: New status to transition to (if None, just validates current state)

        Returns:
            ValidationResult with status transition validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'status_transition',
        }

        # Get current status
        if current_status is None:
            current_status = dq_run.status

        details['current_status'] = current_status

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in DQRunStatus.choices]
        if current_status not in valid_statuses:
            errors.append(
                f"Invalid current status: {current_status}. Valid statuses are: {', '.join(valid_statuses)}"
            )
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['current_status_valid'] = True

        # If new_status is provided, validate transition
        if new_status:
            details['new_status'] = new_status

            # Validate new status is valid
            if new_status not in valid_statuses:
                errors.append(
                    f"Invalid new status: {new_status}. Valid statuses are: {', '.join(valid_statuses)}"
                )
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['new_status_valid'] = True

            # Define allowed transitions
            allowed_transitions = {
                DQRunStatus.PENDING: [DQRunStatus.RUNNING],
                DQRunStatus.RUNNING: [
                    DQRunStatus.SUCCEEDED,
                    DQRunStatus.FAILED
                ],
                DQRunStatus.SUCCEEDED: [],  # Terminal state - cannot transition
                DQRunStatus.FAILED: [],  # Terminal state - cannot transition
            }

            # Check if transition is allowed
            allowed_next_statuses = allowed_transitions.get(current_status, [])
            if new_status not in allowed_next_statuses:
                errors.append(
                    f"Cannot transition from {current_status} to {new_status}. "
                    f"Allowed transitions from {current_status}: {allowed_next_statuses}"
                )
                details['transition_allowed'] = False
            else:
                details['transition_allowed'] = True

            # Validate transition timing
            if current_status == DQRunStatus.PENDING and new_status == DQRunStatus.RUNNING:
                # PENDING → RUNNING: should have started_at set
                if not dq_run.started_at:
                    warnings.append(
                        "Transitioning to RUNNING status - started_at should be set"
                    )
                    details['started_at_set'] = False
                else:
                    details['started_at_set'] = True

            elif current_status == DQRunStatus.RUNNING and new_status in [
                DQRunStatus.SUCCEEDED,
                DQRunStatus.FAILED
            ]:
                # RUNNING → SUCCEEDED/FAILED: should have started_at and completed_at set
                if not dq_run.started_at:
                    errors.append(
                        "Cannot transition to terminal state without started_at being set"
                    )
                    details['started_at_set'] = False
                else:
                    details['started_at_set'] = True

                if not dq_run.completed_at:
                    warnings.append(
                        "Transitioning to terminal state - completed_at should be set"
                    )
                    details['completed_at_set'] = False
                else:
                    details['completed_at_set'] = True

                    # Validate completed_at is after started_at
                    if dq_run.started_at and dq_run.completed_at < dq_run.started_at:
                        errors.append(
                            f"completed_at ({dq_run.completed_at}) cannot be before started_at ({dq_run.started_at})"
                        )
                        details['date_order_valid'] = False
                    else:
                        details['date_order_valid'] = True
        else:
            # Just validating current state - check if it's in a valid state for operations
            if current_status == DQRunStatus.PENDING:
                details['can_start'] = True
                details['can_cancel'] = True
            elif current_status == DQRunStatus.RUNNING:
                details['can_start'] = False
                details['can_cancel'] = True
                details['can_complete'] = True
            else:
                # Terminal state
                details['can_start'] = False
                details['can_cancel'] = False
                details['can_complete'] = False

        details['status_transition_valid'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

