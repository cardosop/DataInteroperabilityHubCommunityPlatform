"""
Governance Business Rules

Comprehensive business rules validation for governance operations, including:
- Access request validation
- Policy validation
- Classification validation
- Tenant and user context validation
- Access control validation

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
from hub.apps.governance.models import (
    AccessRequest,
    AccessPolicy,
    DataClassification,
    AccessRequestStatus,
    ClassificationCategory,
    ClassificationStatus,
    ComplianceReport,
)
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class GovernanceRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for governance business rules.

    Adds governance-specific context:
    - policy: The access policy being validated
    - access_request: The access request being validated
    - classification: The data classification being validated
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    policy: Optional[AccessPolicy] = None
    access_request: Optional[AccessRequest] = None
    classification: Optional[DataClassification] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'policy_id': str(self.policy.id) if self.policy else None,
            'access_request_id': str(self.access_request.id) if self.access_request else None,
            'classification_id': str(self.classification.id) if self.classification else None,
            'tenant_id': str(self.tenant.id) if self.tenant else None,
            'user_id': str(self.user.id) if self.user else None,
        })
        return base_dict


@register_rule(
    rule_name="governance_validation",
    description="Validates governance policies, access requests, classifications, and access control",
    tags=["governance", "validation"],
    priority=10
)
class GovernanceBusinessRules(BusinessRules):
    """
    Business rules validator for governance operations.

    Extends BusinessRules base class with governance-specific validation:
    - Access request validation
    - Policy validation
    - Classification validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "GovernanceBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all governance validation checks.
        It can be called with a GovernanceRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        policy, access_request, classification, tenant, and user from kwargs
        or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - policy: AccessPolicy instance (optional)
                - access_request: AccessRequest instance (optional)
                - classification: DataClassification instance (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('policy', 'access_request', 'classification', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract policy, access_request, classification, tenant, and user from context or kwargs
        if isinstance(context, GovernanceRuleExecutionContext):
            policy = context.policy
            access_request = context.access_request
            classification = context.classification
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            policy = kwargs.get('policy')
            access_request = kwargs.get('access_request')
            classification = kwargs.get('classification')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                policy = policy or context.metadata.get('policy')
                access_request = access_request or context.metadata.get('access_request')
                classification = classification or context.metadata.get('classification')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate policy if provided
        if policy and validation_type in ('policy', 'all'):
            policy_result = self._validate_policy(policy, tenant, user)
            result = result.combine(policy_result)
            validated_items.append('policy')

        # Validate access request if provided
        if access_request and validation_type in ('access_request', 'all'):
            access_request_result = self._validate_access_request(access_request, tenant, user)
            result = result.combine(access_request_result)
            validated_items.append('access_request')

        # Validate access request approval if provided (approver in kwargs)
        approver = kwargs.get('approver')
        if access_request and approver and validation_type == 'approval':
            approval_result = self._validate_access_request_approval(
                access_request, approver, tenant
            )
            result = result.combine(approval_result)
            validated_items.append('approval')

        # Validate classification if provided
        if classification and validation_type in ('classification', 'all'):
            classification_result = self._validate_classification(classification, tenant, user)
            result = result.combine(classification_result)
            validated_items.append('classification')

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
                errors=["At least one of policy, access_request, or classification must be provided"],
                details={'validation_type': validation_type}
            )

        # Add validation summary to details
        result.details['validated_items'] = validated_items
        result.details['validation_type'] = validation_type

        return result

    def _validate_policy(
        self,
        policy: AccessPolicy,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate access policy comprehensively.

        This method orchestrates all ABAC policy validation checks:
        - Policy structure validation (valid ABAC policy format)
        - Policy rule validation (valid conditions, actions, effects)
        - Policy conflict detection (conflicting rules identified)
        - Policy precedence validation (priority rules)

        Args:
            policy: AccessPolicy instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'policy_id': str(policy.id),
            'policy_name': policy.name,
            'validation_checks': []
        }

        # Validate tenant context consistency
        if self.tenant_id and policy.tenant_id:
            if str(policy.tenant_id) != str(self.tenant_id):
                result.errors.append(
                    f"Policy tenant ({policy.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )

        # Validate tenant context if provided
        if tenant and policy.tenant_id:
            if str(tenant.id) != str(policy.tenant_id):
                result.errors.append(
                    f"Policy tenant ({policy.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )

        # Comprehensive validation: policy structure
        structure_result = self._validate_policy_structure(policy)
        result = result.combine(structure_result)
        details['structure_validated'] = True
        details['validation_checks'].append('structure')

        # Comprehensive validation: policy rules
        rules_result = self._validate_policy_rules(policy)
        result = result.combine(rules_result)
        details['rules_validated'] = True
        details['validation_checks'].append('rules')

        # Comprehensive validation: policy conflicts (only if policy has valid structure)
        if structure_result.is_valid:
            conflicts_result = self._validate_policy_conflicts(policy, tenant)
            result = result.combine(conflicts_result)
            details['conflicts_validated'] = True
            details['validation_checks'].append('conflicts')

        # Comprehensive validation: policy precedence
        precedence_result = self._validate_policy_precedence(policy, tenant)
        result = result.combine(precedence_result)
        details['precedence_validated'] = True
        details['validation_checks'].append('precedence')

        # Validate policy is enabled (warning, not error)
        if not policy.enabled:
            result.warnings.append(f"Policy '{policy.name}' is disabled")

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_policy_structure(
        self,
        policy: AccessPolicy
    ) -> ValidationResult:
        """
        Validate ABAC policy structure (valid ABAC policy format).

        Validates:
        - Policy has required fields (name, conditions, effect)
        - Conditions is a valid dictionary
        - Conditions structure matches ABAC format (user, resource, environment sections)
        - Effect is valid (ALLOW or DENY)
        - Priority is a valid integer

        Args:
            policy: AccessPolicy instance to validate

        Returns:
            ValidationResult with structure validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'policy_structure',
            'structure_valid': False
        }

        # Validate policy has name
        if not policy.name or not policy.name.strip():
            errors.append("Policy must have a non-empty name")
            details['has_name'] = False
        else:
            details['has_name'] = True
            details['name_length'] = len(policy.name)

        # Validate policy has conditions
        if not policy.conditions:
            errors.append(f"Policy '{policy.name}' must have conditions defined")
            details['has_conditions'] = False
        elif not isinstance(policy.conditions, dict):
            errors.append(
                f"Policy '{policy.name}' conditions must be a dictionary, "
                f"got {type(policy.conditions).__name__}"
            )
            details['has_conditions'] = False
            details['conditions_type'] = type(policy.conditions).__name__
        else:
            details['has_conditions'] = True
            details['conditions_keys'] = list(policy.conditions.keys())

            # Validate conditions structure matches ABAC format
            # Valid sections: user, resource, environment, resource_type
            valid_sections = {'user', 'resource', 'environment', 'resource_type'}
            condition_keys = set(policy.conditions.keys())
            invalid_keys = condition_keys - valid_sections

            if invalid_keys:
                warnings.append(
                    f"Policy '{policy.name}' has unknown condition keys: {', '.join(invalid_keys)}. "
                    f"Valid keys are: {', '.join(valid_sections)}"
                )
                details['invalid_keys'] = list(invalid_keys)

            # Validate each section structure
            for section in ['user', 'resource', 'environment']:
                if section in policy.conditions:
                    section_value = policy.conditions[section]
                    if not isinstance(section_value, dict):
                        errors.append(
                            f"Policy '{policy.name}' condition section '{section}' must be a dictionary, "
                            f"got {type(section_value).__name__}"
                        )
                        details[f'{section}_valid'] = False
                    else:
                        details[f'{section}_valid'] = True
                        details[f'{section}_keys'] = list(section_value.keys())

        # Validate policy effect
        if policy.effect not in ['ALLOW', 'DENY']:
            errors.append(
                f"Policy '{policy.name}' has invalid effect: {policy.effect}. "
                f"Valid effects are: ALLOW, DENY"
            )
            details['effect_valid'] = False
        else:
            details['effect_valid'] = True
            details['effect'] = policy.effect

        # Validate priority
        if not isinstance(policy.priority, int):
            errors.append(
                f"Policy '{policy.name}' priority must be an integer, "
                f"got {type(policy.priority).__name__}"
            )
            details['priority_valid'] = False
        else:
            details['priority_valid'] = True
            details['priority'] = policy.priority

            # Warn if priority is outside reasonable range
            if policy.priority < 0:
                warnings.append(
                    f"Policy '{policy.name}' has negative priority ({policy.priority}). "
                    f"Consider using positive values (lower number = higher priority)"
                )
            elif policy.priority > 10000:
                warnings.append(
                    f"Policy '{policy.name}' has very high priority ({policy.priority}). "
                    f"Consider using values between 0-1000"
                )

        details['structure_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_policy_rules(
        self,
        policy: AccessPolicy
    ) -> ValidationResult:
        """
        Validate policy rules (valid conditions, actions, effects).

        Validates:
        - Condition operators are valid ($gte, $lte, $gt, $lt)
        - Condition values are valid types
        - User condition attributes are valid
        - Resource condition attributes are valid
        - Environment condition attributes are valid
        - Comparison operators are used correctly

        Args:
            policy: AccessPolicy instance to validate

        Returns:
            ValidationResult with rule validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'policy_rules',
            'rules_valid': False
        }

        if not policy.conditions or not isinstance(policy.conditions, dict):
            # Structure validation will catch this, skip rule validation
            return ValidationResult(
                is_valid=False,
                errors=["Cannot validate rules: invalid conditions structure"],
                details=details
            )

        # Valid comparison operators
        valid_operators = {'$gte', '$lte', '$gt', '$lt', '$eq', '$ne', '$in', '$nin'}

        # Validate user conditions
        if 'user' in policy.conditions:
            user_conditions = policy.conditions['user']
            if isinstance(user_conditions, dict):
                for key, value in user_conditions.items():
                    if isinstance(value, dict):
                        # Check for comparison operators
                        operator_keys = set(value.keys())
                        invalid_operators = operator_keys - valid_operators
                        if invalid_operators:
                            errors.append(
                                f"Policy '{policy.name}' user condition '{key}' has invalid operators: "
                                f"{', '.join(invalid_operators)}. Valid operators: {', '.join(valid_operators)}"
                            )
                        else:
                            # Validate operator values
                            for op, op_value in value.items():
                                if op in ['$gte', '$lte', '$gt', '$lt']:
                                    if not isinstance(op_value, (int, float)):
                                        errors.append(
                                            f"Policy '{policy.name}' user condition '{key}' operator '{op}' "
                                            f"requires numeric value, got {type(op_value).__name__}"
                                        )
                                elif op in ['$in', '$nin']:
                                    if not isinstance(op_value, list):
                                        errors.append(
                                            f"Policy '{policy.name}' user condition '{key}' operator '{op}' "
                                            f"requires list value, got {type(op_value).__name__}"
                                        )
                    elif isinstance(value, list):
                        # List value is valid (e.g., user_roles: ["admin", "manager"])
                        pass
                    elif not isinstance(value, (str, int, float, bool)):
                        warnings.append(
                            f"Policy '{policy.name}' user condition '{key}' has unusual value type: "
                            f"{type(value).__name__}"
                        )

        # Validate resource conditions
        if 'resource' in policy.conditions:
            resource_conditions = policy.conditions['resource']
            if isinstance(resource_conditions, dict):
                for key, value in resource_conditions.items():
                    if isinstance(value, dict):
                        # Check for comparison operators
                        operator_keys = set(value.keys())
                        invalid_operators = operator_keys - valid_operators
                        if invalid_operators:
                            errors.append(
                                f"Policy '{policy.name}' resource condition '{key}' has invalid operators: "
                                f"{', '.join(invalid_operators)}. Valid operators: {', '.join(valid_operators)}"
                            )
                        else:
                            # Validate operator values
                            for op, op_value in value.items():
                                if op in ['$gte', '$lte', '$gt', '$lt']:
                                    if not isinstance(op_value, (int, float)):
                                        errors.append(
                                            f"Policy '{policy.name}' resource condition '{key}' operator '{op}' "
                                            f"requires numeric value, got {type(op_value).__name__}"
                                        )
                                elif op in ['$in', '$nin']:
                                    if not isinstance(op_value, list):
                                        errors.append(
                                            f"Policy '{policy.name}' resource condition '{key}' operator '{op}' "
                                            f"requires list value, got {type(op_value).__name__}"
                                        )
                    elif not isinstance(value, (str, int, float, bool, list)):
                        warnings.append(
                            f"Policy '{policy.name}' resource condition '{key}' has unusual value type: "
                            f"{type(value).__name__}"
                        )

        # Validate environment conditions
        if 'environment' in policy.conditions:
            environment_conditions = policy.conditions['environment']
            if isinstance(environment_conditions, dict):
                for key, value in environment_conditions.items():
                    if isinstance(value, dict):
                        # Check for comparison operators
                        operator_keys = set(value.keys())
                        invalid_operators = operator_keys - valid_operators
                        if invalid_operators:
                            errors.append(
                                f"Policy '{policy.name}' environment condition '{key}' has invalid operators: "
                                f"{', '.join(invalid_operators)}. Valid operators: {', '.join(valid_operators)}"
                            )
                        else:
                            # Validate operator values
                            for op, op_value in value.items():
                                if op in ['$gte', '$lte', '$gt', '$lt']:
                                    if not isinstance(op_value, (int, float)):
                                        errors.append(
                                            f"Policy '{policy.name}' environment condition '{key}' operator '{op}' "
                                            f"requires numeric value, got {type(op_value).__name__}"
                                        )
                                    # Validate range operators make sense
                                    if op == '$gte' and '$lte' in value:
                                        if value['$gte'] > value['$lte']:
                                            errors.append(
                                                f"Policy '{policy.name}' environment condition '{key}' has invalid range: "
                                                f"$gte ({value['$gte']}) > $lte ({value['$lte']})"
                                            )
                                    if op == '$gt' and '$lt' in value:
                                        if value['$gt'] >= value['$lt']:
                                            errors.append(
                                                f"Policy '{policy.name}' environment condition '{key}' has invalid range: "
                                                f"$gt ({value['$gt']}) >= $lt ({value['$lt']})"
                                            )
                                elif op in ['$in', '$nin']:
                                    if not isinstance(op_value, list):
                                        errors.append(
                                            f"Policy '{policy.name}' environment condition '{key}' operator '{op}' "
                                            f"requires list value, got {type(op_value).__name__}"
                                        )
                    elif not isinstance(value, (str, int, float, bool, list)):
                        warnings.append(
                            f"Policy '{policy.name}' environment condition '{key}' has unusual value type: "
                            f"{type(value).__name__}"
                        )

        # Validate resource_type condition
        if 'resource_type' in policy.conditions:
            resource_type_value = policy.conditions['resource_type']
            if not isinstance(resource_type_value, str):
                errors.append(
                    f"Policy '{policy.name}' resource_type condition must be a string, "
                    f"got {type(resource_type_value).__name__}"
                )
            else:
                valid_resource_types = {'ASSET', 'DATASET', 'FILE',
                                      'DATA_MESH_DOMAIN', 'VIRTUAL_DATASET'}
                if resource_type_value not in valid_resource_types:
                    warnings.append(
                        f"Policy '{policy.name}' resource_type '{resource_type_value}' is not a standard type. "
                        f"Standard types: {', '.join(valid_resource_types)}"
                    )

        details['rules_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_policy_conflicts(
        self,
        policy: AccessPolicy,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate policy conflicts (conflicting rules identified).

        Detects conflicts with existing policies:
        - Effect conflicts (ALLOW vs DENY with overlapping conditions)
        - Condition overlaps that could create ambiguity
        - Same priority conflicts

        Args:
            policy: AccessPolicy instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with conflict validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'policy_conflicts',
            'conflicts_valid': False,
            'conflicts': []
        }

        # Determine tenant ID
        tenant_id = str(tenant.id) if tenant else (str(policy.tenant_id) if policy.tenant_id else self.tenant_id)
        if not tenant_id:
            # Cannot check conflicts without tenant context
            warnings.append("Cannot check policy conflicts: no tenant context")
            details['conflicts_valid'] = True  # Not an error, just can't validate
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                details=details
            )

        # Get existing policies for the same tenant and resource scope
        from django.db.models import Q

        queryset = AccessPolicy.objects.filter(
            tenant_id=tenant_id,
            enabled=True
        )

        # Exclude self if policy has been saved
        if policy.id:
            queryset = queryset.exclude(id=policy.id)

        # Filter by resource scope
        if policy.asset:
            queryset = queryset.filter(
                Q(asset=policy.asset) | Q(asset__isnull=True)
            )
        elif policy.dataset:
            queryset = queryset.filter(
                Q(dataset=policy.dataset) | Q(dataset__isnull=True)
            )
        else:
            # Tenant-wide policy - check against all tenant-wide and resource-specific policies
            pass

        existing_policies = list(queryset)

        if not existing_policies:
            details['conflicts_valid'] = True
            details['no_existing_policies'] = True
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                details=details
            )

        # Check for conflicts with each existing policy
        for existing_policy in existing_policies:
            conflict_info = self._check_policy_conflict(policy, existing_policy)
            if conflict_info['has_conflict']:
                details['conflicts'].append(conflict_info)

                # Determine severity based on conflict type
                if conflict_info['conflict_type'] == 'EFFECT_CONFLICT':
                    if conflict_info['same_priority']:
                        errors.append(
                            f"Policy '{policy.name}' conflicts with existing policy '{existing_policy.name}': "
                            f"Both have same priority ({policy.priority}) and overlapping conditions, "
                            f"but different effects ({policy.effect} vs {existing_policy.effect})"
                        )
                    else:
                        warnings.append(
                            f"Policy '{policy.name}' may conflict with existing policy '{existing_policy.name}': "
                            f"Overlapping conditions with different effects ({policy.effect} vs {existing_policy.effect}). "
                            f"Priority difference: {policy.priority} vs {existing_policy.priority}"
                        )
                elif conflict_info['conflict_type'] == 'SAME_PRIORITY':
                    warnings.append(
                        f"Policy '{policy.name}' has same priority ({policy.priority}) as existing policy "
                        f"'{existing_policy.name}' with overlapping conditions. This may cause ambiguity."
                    )
                elif conflict_info['conflict_type'] == 'CONDITION_OVERLAP':
                    warnings.append(
                        f"Policy '{policy.name}' has overlapping conditions with existing policy "
                        f"'{existing_policy.name}'. Consider reviewing to avoid ambiguity."
                    )

        details['conflicts_valid'] = len(errors) == 0
        details['conflict_count'] = len(details['conflicts'])

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _check_policy_conflict(
        self,
        policy1: AccessPolicy,
        policy2: AccessPolicy
    ) -> Dict[str, Any]:
        """
        Check if two policies conflict.

        Args:
            policy1: First policy
            policy2: Second policy

        Returns:
            Dictionary with conflict information
        """
        conflict_info = {
            'policy1_id': str(policy1.id),
            'policy1_name': policy1.name,
            'policy2_id': str(policy2.id),
            'policy2_name': policy2.name,
            'has_conflict': False,
            'conflict_type': None,
            'same_priority': policy1.priority == policy2.priority,
            'overlapping_conditions': False
        }

        # Check if conditions overlap
        if not policy1.conditions or not policy2.conditions:
            return conflict_info

        if not isinstance(policy1.conditions, dict) or not isinstance(policy2.conditions, dict):
            return conflict_info

        # Use condition overlap detection logic (similar to DataMeshBusinessRules)
        overlap_result = self._check_condition_overlap(policy1.conditions, policy2.conditions)
        conflict_info['overlapping_conditions'] = overlap_result['overlaps']

        if not overlap_result['overlaps']:
            return conflict_info

        conflict_info['has_conflict'] = True

        # Determine conflict type
        if policy1.effect != policy2.effect:
            conflict_info['conflict_type'] = 'EFFECT_CONFLICT'
        elif policy1.priority == policy2.priority:
            conflict_info['conflict_type'] = 'SAME_PRIORITY'
        else:
            conflict_info['conflict_type'] = 'CONDITION_OVERLAP'

        conflict_info['overlap_details'] = overlap_result

        return conflict_info

    def _check_condition_overlap(
        self,
        conditions1: Dict[str, Any],
        conditions2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if two policy conditions overlap.

        Args:
            conditions1: First policy conditions
            conditions2: Second policy conditions

        Returns:
            Dictionary with overlap information
        """
        overlaps = False
        overlapping_keys = []

        if not isinstance(conditions1, dict) or not isinstance(conditions2, dict):
            return {
                'overlaps': False,
                'overlapping_keys': []
            }

        # Check for overlapping keys with matching values
        for key, value1 in conditions1.items():
            if key in conditions2:
                value2 = conditions2[key]
                overlap_detail = self._check_value_overlap(value1, value2)

                if overlap_detail['overlaps']:
                    overlaps = True
                    overlapping_keys.append({
                        'key': key,
                        'value1': value1,
                        'value2': value2,
                        'overlap_type': overlap_detail['type']
                    })

        # Also check nested structures (user, resource, environment)
        for section in ['user', 'resource', 'environment']:
            if section in conditions1 and section in conditions2:
                section_overlap = self._check_condition_overlap(
                    conditions1[section], conditions2[section]
                )
                if section_overlap['overlaps']:
                    overlaps = True
                    overlapping_keys.extend([
                        {**key_info, 'section': section}
                        for key_info in section_overlap['overlapping_keys']
                    ])

        return {
            'overlaps': overlaps,
            'overlapping_keys': overlapping_keys
        }

    def _check_value_overlap(
        self,
        value1: Any,
        value2: Any
    ) -> Dict[str, Any]:
        """
        Check if two values overlap (could match the same attributes).

        Args:
            value1: First value
            value2: Second value

        Returns:
            Dictionary with overlap status and type
        """
        # Handle list values (e.g., user_roles)
        if isinstance(value1, list) and isinstance(value2, list):
            overlap_set = set(value1) & set(value2)
            return {
                'overlaps': len(overlap_set) > 0,
                'type': 'LIST_INTERSECTION',
                'overlap_values': list(overlap_set)
            }
        elif isinstance(value1, list):
            return {
                'overlaps': value2 in value1,
                'type': 'VALUE_IN_LIST'
            }
        elif isinstance(value2, list):
            return {
                'overlaps': value1 in value2,
                'type': 'VALUE_IN_LIST'
            }
        elif isinstance(value1, dict) and isinstance(value2, dict):
            # Nested dict - recursively check overlap
            nested_overlap = self._check_condition_overlap(value1, value2)
            return {
                'overlaps': nested_overlap['overlaps'],
                'type': 'NESTED_DICT'
            }
        elif value1 == value2:
            return {
                'overlaps': True,
                'type': 'EXACT_MATCH'
            }
        else:
            return {
                'overlaps': False,
                'type': 'NO_MATCH'
            }

    def _validate_policy_precedence(
        self,
        policy: AccessPolicy,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate policy precedence (priority rules).

        Validates:
        - Priority is unique within same resource scope (or warns if duplicate)
        - Priority ordering makes sense (lower number = higher priority)
        - No ambiguous priority conflicts

        Args:
            policy: AccessPolicy instance to validate
            tenant: Optional tenant instance

        Returns:
            ValidationResult with precedence validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'policy_precedence',
            'precedence_valid': False
        }

        # Determine tenant ID
        tenant_id = str(tenant.id) if tenant else (str(policy.tenant_id) if policy.tenant_id else self.tenant_id)
        if not tenant_id:
            # Cannot check precedence without tenant context
            warnings.append("Cannot check policy precedence: no tenant context")
            details['precedence_valid'] = True  # Not an error, just can't validate
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                details=details
            )

        # Validate priority is a valid integer before querying
        # Use try-except to handle cases where priority is an invalid value
        # (e.g., string "not an int") that Django's IntegerField can't convert
        try:
            priority_value = policy.priority
            if not isinstance(priority_value, int):
                # Invalid priority type - structure validation will catch this
                # Skip precedence validation for invalid priorities
                details['precedence_valid'] = True
                details['priority_invalid'] = True
                details['skip_precedence_check'] = True
                return ValidationResult(
                    is_valid=True,
                    warnings=warnings,
                    details=details
                )
        except (ValueError, TypeError) as e:
            # Django's IntegerField raised an error trying to convert invalid value
            # This is expected for invalid structure tests - skip precedence validation
            details['precedence_valid'] = True
            details['priority_invalid'] = True
            details['skip_precedence_check'] = True
            details['priority_error'] = str(e)
            return ValidationResult(
                is_valid=True,
                warnings=warnings,
                details=details
            )

        # Get existing policies with same priority and resource scope
        from django.db.models import Q

        queryset = AccessPolicy.objects.filter(
            tenant_id=tenant_id,
            priority=priority_value,
            enabled=True
        )

        # Exclude self if policy has been saved
        if policy.id:
            queryset = queryset.exclude(id=policy.id)

        # Filter by resource scope
        if policy.asset:
            queryset = queryset.filter(
                Q(asset=policy.asset) | Q(asset__isnull=True)
            )
        elif policy.dataset:
            queryset = queryset.filter(
                Q(dataset=policy.dataset) | Q(dataset__isnull=True)
            )

        same_priority_policies = list(queryset)

        if same_priority_policies:
            policy_names = [p.name for p in same_priority_policies]
            warnings.append(
                f"Policy '{policy.name}' has same priority ({policy.priority}) as {len(same_priority_policies)} "
                f"other policy/policies: {', '.join(policy_names)}. "
                f"Policies with same priority are evaluated in creation order, which may cause ambiguity."
            )
            details['same_priority_count'] = len(same_priority_policies)
            details['same_priority_policies'] = [
                {'id': str(p.id), 'name': p.name} for p in same_priority_policies
            ]

        # Check for priority ordering issues
        # Get all policies for comparison
        all_policies = AccessPolicy.objects.filter(
            tenant_id=tenant_id,
            enabled=True
        )

        # Exclude self if policy has been saved
        if policy.id:
            all_policies = all_policies.exclude(id=policy.id)

        # Filter by resource scope
        if policy.asset:
            all_policies = all_policies.filter(
                Q(asset=policy.asset) | Q(asset__isnull=True)
            )
        elif policy.dataset:
            all_policies = all_policies.filter(
                Q(dataset=policy.dataset) | Q(dataset__isnull=True)
            )

        # Check if there are policies with very close priorities that might be confusing
        close_priority_threshold = 5
        close_priority_policies = [
            p for p in all_policies
            if abs(p.priority - policy.priority) <= close_priority_threshold
            and p.priority != policy.priority
        ]

        if close_priority_policies:
            details['close_priority_count'] = len(close_priority_policies)
            details['close_priority_policies'] = [
                {'id': str(p.id), 'name': p.name, 'priority': p.priority}
                for p in close_priority_policies
            ]

        details['precedence_valid'] = True  # Precedence validation doesn't fail, only warns

        return ValidationResult(
            is_valid=True,  # Precedence issues are warnings, not errors
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_access_request(
        self,
        access_request: AccessRequest,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate access request.

        This method orchestrates comprehensive access request validation including:
        - Eligibility validation (user can request access)
        - Resource access validation (resource exists and is accessible)
        - Status transition validation (valid state transitions)
        - Approval validation (approver has permission)

        Args:
            access_request: AccessRequest instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'access_request_id': str(getattr(access_request, 'id', None) or ''),
            'status': getattr(access_request, 'status', AccessRequestStatus.PENDING.value),
        }

        # Validate tenant context consistency
        if self.tenant_id and access_request.tenant_id:
            if str(access_request.tenant_id) != str(self.tenant_id):
                result.errors.append(
                    f"Access request tenant ({access_request.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )

        # Validate access request has a resource
        if not access_request.asset and not access_request.dataset and not access_request.file:
            result.errors.append("Access request must have at least one resource (asset, dataset, or file)")

        # Validate access request has a reason
        if not access_request.reason or not access_request.reason.strip():
            result.errors.append("Access request must have a reason")

        # Validate access request has requested access type
        if not access_request.requested_access_type or not access_request.requested_access_type.strip():
            result.errors.append("Access request must have a requested access type")

        # Validate tenant context if provided
        if tenant and access_request.tenant_id:
            if str(tenant.id) != str(access_request.tenant_id):
                result.errors.append(
                    f"Access request tenant ({access_request.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )

        # Validate user context if provided
        if user and access_request.requested_by_id:
            if str(user.id) != str(access_request.requested_by_id):
                result.warnings.append(
                    f"Access request requested_by ({access_request.requested_by_id}) does not match "
                    f"provided user ({user.id})"
                )

        # Comprehensive validation: eligibility
        eligibility_result = self._validate_access_request_eligibility(access_request, tenant, user)
        result = result.combine(eligibility_result)
        details['eligibility_validated'] = True

        # Comprehensive validation: resource access
        resource_result = self._validate_resource_access(access_request, tenant, user)
        result = result.combine(resource_result)
        details['resource_access_validated'] = True

        # Comprehensive validation: status transition (only if status is being changed)
        # This is typically validated when approving/rejecting, but we validate current state
        status_result = self._validate_access_request_status_transition(
            access_request,
            current_status=access_request.status,
            new_status=None  # Not transitioning, just validating current state
        )
        result = result.combine(status_result)
        details['status_transition_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_access_request_eligibility(
        self,
        access_request: AccessRequest,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate access request eligibility (user can request access).

        Validates:
        - User exists and is active
        - User belongs to tenant (if tenant provided)
        - User has permission to request access (not blocked/banned)

        Args:
            access_request: AccessRequest instance to validate
            tenant: Optional tenant instance
            user: Optional user instance (if not provided, fetches from access_request.requested_by)

        Returns:
            ValidationResult with eligibility validation status
        """
        errors = []
        warnings = []
        details = {
            'eligibility_check': 'user_eligibility',
            'user_provided': user is not None,
        }

        # Get user from access_request if not provided
        if not user:
            try:
                user = access_request.requested_by
            except Exception as e:
                errors.append(f"Failed to retrieve user from access request: {str(e)}")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

        if not user:
            errors.append("User not found for access request eligibility validation")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['user_id'] = str(user.id)
        details['user_email'] = user.email

        # Validate user is active
        if hasattr(user, 'is_active') and not user.is_active:
            errors.append(f"User {user.email} is not active and cannot request access")
            details['user_active'] = False
        else:
            details['user_active'] = True

        # Validate user belongs to tenant
        if tenant:
            if not hasattr(user, 'tenant') or not user.tenant:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False
            elif str(user.tenant.id) != str(tenant.id):
                errors.append(
                    f"User {user.email} belongs to tenant {user.tenant.id} but access request "
                    f"is for tenant {tenant.id}"
                )
                details['user_tenant_match'] = False
            else:
                details['user_has_tenant'] = True
                details['user_tenant_match'] = True
        elif access_request.tenant:
            # Validate against access_request tenant
            if not hasattr(user, 'tenant') or not user.tenant:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False
            elif str(user.tenant.id) != str(access_request.tenant.id):
                errors.append(
                    f"User {user.email} belongs to tenant {user.tenant.id} but access request "
                    f"is for tenant {access_request.tenant.id}"
                )
                details['user_tenant_match'] = False
            else:
                details['user_has_tenant'] = True
                details['user_tenant_match'] = True

        # Validate user is not blocked (check for any blocking flags)
        # This is a placeholder - actual implementation depends on user model structure
        if hasattr(user, 'is_blocked') and user.is_blocked:
            errors.append(f"User {user.email} is blocked and cannot request access")
            details['user_blocked'] = True
        else:
            details['user_blocked'] = False

        details['eligibility_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_resource_access(
        self,
        access_request: AccessRequest,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate resource access (resource exists and is accessible).

        Validates:
        - Resource exists (asset, dataset, or file)
        - Resource belongs to tenant (or cross-tenant access is allowed)
        - Resource is accessible (not deleted, not archived)

        Args:
            access_request: AccessRequest instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with resource access validation status
        """
        errors = []
        warnings = []
        details = {
            'resource_access_check': 'resource_exists_and_accessible',
        }

        # Determine which resource is being requested
        resource = None
        resource_type = None
        resource_id = None

        if access_request.asset:
            resource = access_request.asset
            resource_type = 'asset'
            resource_id = str(access_request.asset.id)
        elif access_request.dataset:
            resource = access_request.dataset
            resource_type = 'dataset'
            resource_id = str(access_request.dataset.id)
        elif access_request.file:
            resource = access_request.file
            resource_type = 'file'
            resource_id = str(access_request.file.id)
        else:
            errors.append("Access request has no resource (asset, dataset, or file)")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['resource_type'] = resource_type
        details['resource_id'] = resource_id

        # Validate resource exists (should already be validated by foreign key, but double-check)
        if not resource:
            errors.append(f"{resource_type.capitalize()} {resource_id} does not exist")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['resource_exists'] = True

        # Validate resource belongs to tenant
        resource_tenant_id = None
        if hasattr(resource, 'tenant') and resource.tenant:
            resource_tenant_id = str(resource.tenant.id)
            details['resource_tenant_id'] = resource_tenant_id

            # Check tenant match
            if tenant:
                if str(tenant.id) != resource_tenant_id:
                    # Cross-tenant access - check if allowed
                    # For now, we allow cross-tenant access requests (they may require approval)
                    warnings.append(
                        f"{resource_type.capitalize()} belongs to tenant {resource_tenant_id} "
                        f"but access request is for tenant {tenant.id} (cross-tenant access)"
                    )
                    details['cross_tenant_access'] = True
                else:
                    details['cross_tenant_access'] = False
                    details['tenant_match'] = True
            elif access_request.tenant:
                if str(access_request.tenant.id) != resource_tenant_id:
                    warnings.append(
                        f"{resource_type.capitalize()} belongs to tenant {resource_tenant_id} "
                        f"but access request is for tenant {access_request.tenant.id} (cross-tenant access)"
                    )
                    details['cross_tenant_access'] = True
                else:
                    details['cross_tenant_access'] = False
                    details['tenant_match'] = True
        else:
            warnings.append(f"{resource_type.capitalize()} has no tenant association")
            details['resource_has_tenant'] = False

        # Validate resource is accessible (not deleted/archived)
        # Check for common status fields
        if hasattr(resource, 'status'):
            resource_status = resource.status
            details['resource_status'] = resource_status

            # Check for deleted/archived statuses (implementation depends on resource model)
            if resource_status in ['DELETED', 'ARCHIVED', 'RETIRED']:
                errors.append(
                    f"{resource_type.capitalize()} {resource_id} has status {resource_status} and is not accessible"
                )
                details['resource_accessible'] = False
            else:
                details['resource_accessible'] = True
        else:
            # No status field - assume accessible
            details['resource_accessible'] = True

        details['resource_access_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_access_request_status_transition(
        self,
        access_request: AccessRequest,
        current_status: Optional[str] = None,
        new_status: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate access request status transition (PENDING → APPROVED/REJECTED).

        Validates:
        - Current status is valid
        - Transition is allowed (PENDING → APPROVED/REJECTED)
        - Cannot transition from non-PENDING states (unless REVOKED)

        Args:
            access_request: AccessRequest instance to validate
            current_status: Current status (if None, uses access_request.status)
            new_status: New status to transition to (if None, just validates current state)

        Returns:
            ValidationResult with status transition validation status
        """
        errors = []
        warnings = []
        details = {
            'status_transition_check': 'status_transition_validation',
        }

        # Get current status
        if current_status is None:
            current_status = access_request.status

        details['current_status'] = current_status

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in AccessRequestStatus.choices]
        if current_status not in valid_statuses:
            errors.append(f"Invalid current status: {current_status}. Valid statuses: {valid_statuses}")
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
                errors.append(f"Invalid new status: {new_status}. Valid statuses: {valid_statuses}")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )

            details['new_status_valid'] = True

            # Define allowed transitions (using string values)
            allowed_transitions = {
                AccessRequestStatus.PENDING.value: [AccessRequestStatus.APPROVED.value, AccessRequestStatus.REJECTED.value],
                AccessRequestStatus.APPROVED.value: [AccessRequestStatus.REVOKED.value],  # Can revoke approved requests
                AccessRequestStatus.REJECTED.value: [],  # Cannot transition from rejected
                AccessRequestStatus.EXPIRED.value: [],  # Cannot transition from expired
                AccessRequestStatus.REVOKED.value: [],  # Cannot transition from revoked
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
        else:
            # Just validating current state - check if it's in a valid state for operations
            if current_status == AccessRequestStatus.PENDING.value:
                details['can_be_approved'] = True
                details['can_be_rejected'] = True
            elif current_status == AccessRequestStatus.APPROVED.value:
                details['can_be_approved'] = False
                details['can_be_rejected'] = False
                details['can_be_revoked'] = True
            else:
                details['can_be_approved'] = False
                details['can_be_rejected'] = False
                details['can_be_revoked'] = False

        details['status_transition_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_access_request_approval(
        self,
        access_request: AccessRequest,
        approver: User,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate access request approval (approver has permission).

        Validates:
        - Approver exists and is active
        - Approver belongs to tenant
        - Approver is in approvers list (for single-step approval)
        - Approver is in current step approvers (for multi-step approval)
        - Approver has required role/permission

        Args:
            access_request: AccessRequest instance to validate
            approver: User instance approving the request
            tenant: Optional tenant instance

        Returns:
            ValidationResult with approval validation status
        """
        errors = []
        warnings = []
        details = {
            'approval_check': 'approver_permission_validation',
            'approver_id': str(approver.id),
            'approver_email': approver.email,
        }

        # Validate approver is active
        if hasattr(approver, 'is_active') and not approver.is_active:
            errors.append(f"Approver {approver.email} is not active")
            details['approver_active'] = False
        else:
            details['approver_active'] = True

        # Validate approver belongs to tenant
        if tenant:
            if not hasattr(approver, 'tenant') or not approver.tenant:
                errors.append(f"Approver {approver.email} does not belong to any tenant")
                details['approver_has_tenant'] = False
            elif str(approver.tenant.id) != str(tenant.id):
                errors.append(
                    f"Approver {approver.email} belongs to tenant {approver.tenant.id} but "
                    f"access request is for tenant {tenant.id}"
                )
                details['approver_tenant_match'] = False
            else:
                details['approver_has_tenant'] = True
                details['approver_tenant_match'] = True
        elif access_request.tenant:
            if not hasattr(approver, 'tenant') or not approver.tenant:
                errors.append(f"Approver {approver.email} does not belong to any tenant")
                details['approver_has_tenant'] = False
            elif str(approver.tenant.id) != str(access_request.tenant.id):
                errors.append(
                    f"Approver {approver.email} belongs to tenant {approver.tenant.id} but "
                    f"access request is for tenant {access_request.tenant.id}"
                )
                details['approver_tenant_match'] = False
            else:
                details['approver_has_tenant'] = True
                details['approver_tenant_match'] = True

        # Validate access request is pending
        if access_request.status != AccessRequestStatus.PENDING.value:
            errors.append(
                f"Access request is not pending (status: {access_request.status}). "
                f"Only pending requests can be approved"
            )
            details['request_is_pending'] = False
        else:
            details['request_is_pending'] = True

        # Validate approver is authorized
        approver_id_str = str(approver.id)
        is_authorized = False

        # Check multi-step approval workflow
        if access_request.approval_workflow and len(access_request.approval_workflow) > 0:
            details['approval_type'] = 'multi_step'
            current_step = access_request.current_approval_step

            if current_step < len(access_request.approval_workflow):
                step_approvers = access_request.approval_workflow[current_step].get('approvers', [])
                details['current_step'] = current_step
                details['step_approvers'] = step_approvers

                if approver_id_str in step_approvers:
                    is_authorized = True
                    details['approver_in_step'] = True
                else:
                    errors.append(
                        f"Approver {approver.email} is not authorized for step {current_step} of "
                        f"multi-step approval workflow"
                    )
                    details['approver_in_step'] = False
            else:
                errors.append(
                    f"Current approval step {current_step} is out of bounds for workflow "
                    f"with {len(access_request.approval_workflow)} steps"
                )
                details['step_valid'] = False
        else:
            # Single-step approval
            details['approval_type'] = 'single_step'

            if access_request.approvers:
                if approver_id_str in access_request.approvers:
                    is_authorized = True
                    details['approver_in_list'] = True
                else:
                    errors.append(
                        f"Approver {approver.email} is not in the approvers list. "
                        f"Approvers: {access_request.approvers}"
                    )
                    details['approver_in_list'] = False
            else:
                # No approvers list - check if user has tenant admin role
                if hasattr(approver, 'has_role'):
                    if approver.has_role('TENANT_ADMIN'):
                        is_authorized = True
                        details['approver_has_admin_role'] = True
                        warnings.append(
                            f"No approvers list specified, allowing approval by tenant admin {approver.email}"
                        )
                    else:
                        errors.append(
                            f"Approver {approver.email} is not in approvers list and does not have "
                            f"TENANT_ADMIN role"
                        )
                        details['approver_has_admin_role'] = False
                else:
                    # Fallback: if no approvers list, allow approval (workflow will determine)
                    is_authorized = True
                    warnings.append(
                        f"No approvers list specified and cannot check roles, allowing approval"
                    )
                    details['approver_has_admin_role'] = None

        details['approver_authorized'] = is_authorized

        # Phase 272.6 — delegation check.
        # If the approver is not directly authorized, check for an
        # active ApprovalDelegation from someone who IS authorized.
        if not is_authorized:
            from django.utils import timezone
            from hub.apps.governance.models import ApprovalDelegation

            now = timezone.now()
            active_delegation = ApprovalDelegation.objects.filter(
                tenant=access_request.tenant,
                delegate_id=approver.id,
                start_at__lte=now,
                end_at__gte=now,
            ).first()

            if active_delegation:
                is_authorized = True
                details['delegation_used'] = True
                details['delegator_id'] = str(active_delegation.delegator_id)
                warnings.append(
                    f"Approver {approver.email} is acting as delegate for "
                    f"user {active_delegation.delegator_id}"
                )

        # Check if approver is platform admin (has all permissions)
        if hasattr(approver, 'is_platform_admin') and approver.is_platform_admin:
            details['approver_is_platform_admin'] = True
            if not is_authorized:
                # Platform admin can approve even if not in list
                warnings.append(
                    f"Approver {approver.email} is a platform admin and can approve any request"
                )
                is_authorized = True
        else:
            details['approver_is_platform_admin'] = False

        details['approval_valid'] = len(errors) == 0 and is_authorized

        return ValidationResult(
            is_valid=len(errors) == 0 and is_authorized,
            errors=errors,
            warnings=warnings,
            details=details
        )

    @staticmethod
    def _get_classification_priority(category: str) -> int:
        """
        Get classification priority (higher = more sensitive).

        Args:
            category: Classification category string

        Returns:
            Priority integer (higher = more sensitive)
        """
        priorities = {
            ClassificationCategory.PUBLIC.value: 1,
            ClassificationCategory.INTERNAL.value: 2,
            ClassificationCategory.CONFIDENTIAL.value: 3,
            ClassificationCategory.RESTRICTED.value: 4,
            ClassificationCategory.PII.value: 5,
            ClassificationCategory.PHI.value: 6,
            ClassificationCategory.PCI.value: 6,
            ClassificationCategory.FINANCIAL.value: 4,
            ClassificationCategory.LEGAL.value: 4,
        }
        return priorities.get(category, 2)

    def _validate_classification_level(
        self,
        classification: DataClassification
    ) -> ValidationResult:
        """
        Validate classification level (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED, etc.).

        Args:
            classification: DataClassification instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'classification_level',
            'category': classification.category,
        }

        # Validate classification category exists
        if not classification.category:
            errors.append("Classification category is required")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate category is a valid choice
        valid_categories = [choice[0] for choice in ClassificationCategory.choices]
        if classification.category not in valid_categories:
            errors.append(
                f"Invalid classification category: {classification.category}. "
                f"Valid categories are: {', '.join(valid_categories)}"
            )
            details['valid_categories'] = valid_categories
        else:
            details['category_valid'] = True
            details['priority'] = self._get_classification_priority(classification.category)

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_classification_consistency(
        self,
        classification: DataClassification
    ) -> ValidationResult:
        """
        Validate classification consistency across related resources.

        Validates:
        - Asset-level classifications are consistent with dataset-level classifications
        - Dataset-level classifications are consistent with field-level classifications
        - Related resources (datasets of same asset, fields of same dataset) have consistent classifications

        Args:
            classification: DataClassification instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'classification_consistency',
            'resource_type': None,
            'resource_id': None,
        }

        # Determine resource type
        if classification.asset:
            resource = classification.asset
            resource_type = 'asset'
            resource_id = str(classification.asset.id)
            details['resource_type'] = 'asset'
            details['resource_id'] = resource_id

            # Check dataset-level classifications for this asset
            if classification.field_name:
                # Field-level classification - check consistency with dataset-level
                if classification.dataset:
                    dataset_classifications = DataClassification.objects.filter(
                        tenant=classification.tenant,
                        dataset=classification.dataset,
                        field_name__isnull=True  # Dataset-level classifications
                    ).exclude(id=classification.id)

                    for ds_class in dataset_classifications:
                        ds_priority = self._get_classification_priority(ds_class.category)
                        field_priority = self._get_classification_priority(classification.category)

                        # Field should be at least as sensitive as dataset
                        if field_priority < ds_priority:
                            warnings.append(
                                f"Field '{classification.field_name}' classification "
                                f"({classification.category}, priority={field_priority}) is less sensitive "
                                f"than dataset classification ({ds_class.category}, priority={ds_priority})"
                            )
                            details['inconsistency_detected'] = True
                            details['inconsistency_type'] = 'field_less_sensitive_than_dataset'
                else:
                    errors.append(
                        "Field-level classification requires a dataset reference"
                    )
            else:
                # Asset-level or dataset-level classification
                if classification.dataset:
                    # Dataset-level classification - check consistency with asset-level
                    asset_classifications = DataClassification.objects.filter(
                        tenant=classification.tenant,
                        asset=classification.asset,
                        dataset__isnull=True,  # Asset-level classifications
                        field_name__isnull=True
                    ).exclude(id=classification.id)

                    for asset_class in asset_classifications:
                        asset_priority = self._get_classification_priority(asset_class.category)
                        dataset_priority = self._get_classification_priority(classification.category)

                        # Dataset should be at least as sensitive as asset
                        if dataset_priority < asset_priority:
                            warnings.append(
                                f"Dataset classification ({classification.category}, priority={dataset_priority}) "
                                f"is less sensitive than asset classification "
                                f"({asset_class.category}, priority={asset_priority})"
                            )
                            details['inconsistency_detected'] = True
                            details['inconsistency_type'] = 'dataset_less_sensitive_than_asset'

                    # Check consistency with other datasets of the same asset
                    other_dataset_classifications = DataClassification.objects.filter(
                        tenant=classification.tenant,
                        asset=classification.asset,
                        dataset__isnull=False,
                        field_name__isnull=True
                    ).exclude(id=classification.id).exclude(dataset=classification.dataset)

                    for other_ds_class in other_dataset_classifications:
                        other_priority = self._get_classification_priority(other_ds_class.category)
                        current_priority = self._get_classification_priority(classification.category)

                        # Significant difference in sensitivity
                        if abs(current_priority - other_priority) > 2:
                            warnings.append(
                                f"Dataset classification ({classification.category}, priority={current_priority}) "
                                f"has significant sensitivity difference from other dataset "
                                f"({other_ds_class.category}, priority={other_priority}) in the same asset"
                            )
                            details['inconsistency_detected'] = True
                            details['inconsistency_type'] = 'dataset_sensitivity_mismatch'
                else:
                    # Asset-level classification - check consistency with datasets
                    dataset_classifications = DataClassification.objects.filter(
                        tenant=classification.tenant,
                        asset=classification.asset,
                        dataset__isnull=False,
                        field_name__isnull=True
                    ).exclude(id=classification.id)

                    asset_priority = self._get_classification_priority(classification.category)

                    for ds_class in dataset_classifications:
                        ds_priority = self._get_classification_priority(ds_class.category)

                        # Datasets should be at least as sensitive as asset
                        if ds_priority < asset_priority:
                            warnings.append(
                                f"Dataset classification ({ds_class.category}, priority={ds_priority}) "
                                f"is less sensitive than asset classification "
                                f"({classification.category}, priority={asset_priority})"
                            )
                            details['inconsistency_detected'] = True
                            details['inconsistency_type'] = 'dataset_less_sensitive_than_asset'

        elif classification.dataset:
            # Dataset-level classification without asset, or field-level classification
            resource_type = 'dataset'
            resource_id = str(classification.dataset.id)
            details['resource_type'] = 'dataset'
            details['resource_id'] = resource_id

            if classification.field_name:
                # Field-level classification - check consistency with dataset-level
                dataset_classifications = DataClassification.objects.filter(
                    tenant=classification.tenant,
                    dataset=classification.dataset,
                    field_name__isnull=True  # Dataset-level classifications
                ).exclude(id=classification.id)

                field_priority = self._get_classification_priority(classification.category)

                for ds_class in dataset_classifications:
                    ds_priority = self._get_classification_priority(ds_class.category)

                    # Field should be at least as sensitive as dataset
                    if field_priority < ds_priority:
                        warnings.append(
                            f"Field '{classification.field_name}' classification "
                            f"({classification.category}, priority={field_priority}) is less sensitive "
                            f"than dataset classification ({ds_class.category}, priority={ds_priority})"
                        )
                        details['inconsistency_detected'] = True
                        details['inconsistency_type'] = 'field_less_sensitive_than_dataset'
            else:
                # Dataset-level classification - check field-level classifications for this dataset
                field_classifications = DataClassification.objects.filter(
                    tenant=classification.tenant,
                    dataset=classification.dataset,
                    field_name__isnull=False
                ).exclude(id=classification.id)

                dataset_priority = self._get_classification_priority(classification.category)

                for field_class in field_classifications:
                    field_priority = self._get_classification_priority(field_class.category)

                    # Fields should be at least as sensitive as dataset
                    if field_priority < dataset_priority:
                        warnings.append(
                            f"Field '{field_class.field_name}' classification "
                            f"({field_class.category}, priority={field_priority}) is less sensitive "
                            f"than dataset classification ({classification.category}, priority={dataset_priority})"
                        )
                        details['inconsistency_detected'] = True
                        details['inconsistency_type'] = 'field_less_sensitive_than_dataset'
        else:
            errors.append("Classification must have at least one resource (asset or dataset)")

        if not details.get('inconsistency_detected'):
            details['consistent'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_classification_change(
        self,
        classification: DataClassification,
        previous_category: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate classification change (cannot downgrade without approval).

        A downgrade is moving from a higher sensitivity level to a lower one.
        This requires approval (status must be APPROVED or MANUAL_REVIEW).

        Args:
            classification: DataClassification instance to validate
            previous_category: Optional previous category (if None, fetched from DB if classification has pk)

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'classification_change',
            'current_category': classification.category,
            'is_change': False,
            'is_downgrade': False,
        }

        # Get previous category if not provided
        if previous_category is None and classification.pk:
            try:
                previous_classification = DataClassification.objects.get(pk=classification.pk)
                previous_category = previous_classification.category
            except DataClassification.DoesNotExist:
                # New classification, no previous category
                previous_category = None

        # If no previous category, this is a new classification (no change)
        if previous_category is None:
            details['is_new'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Check if category changed
        if previous_category == classification.category:
            details['is_change'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['is_change'] = True
        details['previous_category'] = previous_category

        # Get priorities
        previous_priority = self._get_classification_priority(previous_category)
        current_priority = self._get_classification_priority(classification.category)

        details['previous_priority'] = previous_priority
        details['current_priority'] = current_priority

        # Check if this is a downgrade (lower priority = less sensitive)
        if current_priority < previous_priority:
            details['is_downgrade'] = True

            # Downgrade requires approval
            if classification.status not in [
                ClassificationStatus.APPROVED.value,
                ClassificationStatus.MANUAL_REVIEW.value
            ]:
                errors.append(
                    f"Classification downgrade from {previous_category} (priority={previous_priority}) "
                    f"to {classification.category} (priority={current_priority}) requires approval. "
                    f"Current status: {classification.status}. "
                    f"Status must be {ClassificationStatus.APPROVED.value} or "
                    f"{ClassificationStatus.MANUAL_REVIEW.value}"
                )
                details['requires_approval'] = True
            else:
                details['approved'] = True
        elif current_priority > previous_priority:
            # Upgrade (higher priority = more sensitive) - allowed but log as info
            details['is_upgrade'] = True
            details['upgrade_allowed'] = True
        else:
            # Same priority but different category (e.g., RESTRICTED to FINANCIAL)
            details['same_priority_change'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_classification_inheritance(
        self,
        classification: DataClassification
    ) -> ValidationResult:
        """
        Validate classification inheritance (child resources inherit parent classification).

        Validates:
        - Dataset classifications inherit from asset (if asset exists)
        - Field classifications inherit from dataset (if dataset exists)
        - Child resources should be at least as sensitive as parent

        Args:
            classification: DataClassification instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'classification_inheritance',
            'inheritance_validated': False,
        }

        current_priority = self._get_classification_priority(classification.category)
        details['current_category'] = classification.category
        details['current_priority'] = current_priority

        # Check inheritance based on resource type
        if classification.dataset and classification.asset:
            # Dataset-level classification - should inherit from asset
            asset_classifications = DataClassification.objects.filter(
                tenant=classification.tenant,
                asset=classification.asset,
                dataset__isnull=True,
                field_name__isnull=True
            ).exclude(id=classification.id)

            if asset_classifications.exists():
                # Get the most restrictive asset classification
                asset_priorities = [
                    self._get_classification_priority(ac.category)
                    for ac in asset_classifications
                ]
                max_asset_priority = max(asset_priorities) if asset_priorities else 0
                most_restrictive_asset = max(
                    asset_classifications,
                    key=lambda ac: self._get_classification_priority(ac.category)
                )

                details['parent_type'] = 'asset'
                details['parent_category'] = most_restrictive_asset.category
                details['parent_priority'] = max_asset_priority

                # Dataset should be at least as sensitive as asset
                if current_priority < max_asset_priority:
                    errors.append(
                        f"Dataset classification ({classification.category}, priority={current_priority}) "
                        f"is less sensitive than parent asset classification "
                        f"({most_restrictive_asset.category}, priority={max_asset_priority}). "
                        f"Child resources must be at least as sensitive as parent."
                    )
                    details['inheritance_violation'] = True
                else:
                    details['inheritance_valid'] = True

        elif classification.dataset and classification.field_name:
            # Field-level classification - should inherit from dataset
            dataset_classifications = DataClassification.objects.filter(
                tenant=classification.tenant,
                dataset=classification.dataset,
                field_name__isnull=True
            ).exclude(id=classification.id)

            if dataset_classifications.exists():
                # Get the most restrictive dataset classification
                dataset_priorities = [
                    self._get_classification_priority(dc.category)
                    for dc in dataset_classifications
                ]
                max_dataset_priority = max(dataset_priorities) if dataset_priorities else 0
                most_restrictive_dataset = max(
                    dataset_classifications,
                    key=lambda dc: self._get_classification_priority(dc.category)
                )

                details['parent_type'] = 'dataset'
                details['parent_category'] = most_restrictive_dataset.category
                details['parent_priority'] = max_dataset_priority

                # Field should be at least as sensitive as dataset
                if current_priority < max_dataset_priority:
                    errors.append(
                        f"Field '{classification.field_name}' classification "
                        f"({classification.category}, priority={current_priority}) "
                        f"is less sensitive than parent dataset classification "
                        f"({most_restrictive_dataset.category}, priority={max_dataset_priority}). "
                        f"Child resources must be at least as sensitive as parent."
                    )
                    details['inheritance_violation'] = True
                else:
                    details['inheritance_valid'] = True
            else:
                # No dataset-level classification - field can have any classification
                details['no_parent_classification'] = True
                details['inheritance_valid'] = True

        elif classification.asset and not classification.dataset:
            # Asset-level classification - no parent to inherit from
            details['root_level'] = True
            details['inheritance_valid'] = True

        elif classification.dataset and not classification.field_name:
            # Dataset-level classification without asset - no parent to inherit from
            details['root_level'] = True
            details['inheritance_valid'] = True

        else:
            # Field-level classification without dataset - invalid
            errors.append(
                "Field-level classification requires a dataset reference"
            )

        details['inheritance_validated'] = True
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_classification(
        self,
        classification: DataClassification,
        tenant: Optional[Any] = None,
        user: Optional[User] = None,
        previous_category: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate data classification comprehensively.

        This method orchestrates all classification validation checks:
        - Classification level validation
        - Classification consistency validation
        - Classification change validation
        - Classification inheritance validation

        Args:
            classification: DataClassification instance to validate
            tenant: Optional tenant instance
            user: Optional user instance
            previous_category: Optional previous category for change validation

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'classification_id': str(classification.id) if classification.pk else 'new',
            'category': classification.category,
            'status': classification.status,
        }

        # Validate tenant context consistency
        if self.tenant_id and classification.tenant_id:
            if str(classification.tenant_id) != str(self.tenant_id):
                result.errors.append(
                    f"Classification tenant ({classification.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )

        # Validate classification has a resource
        if not classification.asset and not classification.dataset:
            result.errors.append("Classification must have at least one resource (asset or dataset)")

        # Validate tenant context if provided
        if tenant and classification.tenant_id:
            if str(tenant.id) != str(classification.tenant_id):
                result.errors.append(
                    f"Classification tenant ({classification.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )

        # Comprehensive validation: classification level
        level_result = self._validate_classification_level(classification)
        result = result.combine(level_result)
        details['level_validated'] = True

        # Comprehensive validation: classification consistency
        consistency_result = self._validate_classification_consistency(classification)
        result = result.combine(consistency_result)
        details['consistency_validated'] = True

        # Comprehensive validation: classification change
        change_result = self._validate_classification_change(classification, previous_category)
        result = result.combine(change_result)
        details['change_validated'] = True

        # Comprehensive validation: classification inheritance
        inheritance_result = self._validate_classification_inheritance(classification)
        result = result.combine(inheritance_result)
        details['inheritance_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_tenant_context(self, tenant: Any) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            tenant: Tenant instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        details = {'tenant_id': str(tenant.id), 'tenant_name': tenant.name}

        # Validate tenant context consistency
        if self.tenant_id:
            if str(tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Provided tenant ({tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )

        details['is_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            details=details
        )

    def _validate_compliance_report_generation_eligibility(
        self,
        user: Optional[User] = None,
        tenant: Optional[Any] = None,
        regulation: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate report generation eligibility (user has permission).

        Validates:
        - User exists and is active
        - User belongs to tenant
        - User has permission to generate compliance reports
        - User has permission for specific regulation (if provided)

        Args:
            user: User instance requesting report generation
            tenant: Tenant instance
            regulation: Optional regulation type (GDPR, HIPAA, SOX, LGPD, CCPA)

        Returns:
            ValidationResult with eligibility validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'report_generation_eligibility',
            'eligible': False,
        }

        if not user:
            errors.append("User is required for report generation eligibility validation")
            details['user_provided'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['user_provided'] = True
        details['user_id'] = str(user.id)
        details['user_email'] = user.email

        # Validate user is active
        if hasattr(user, 'is_active') and not user.is_active:
            errors.append(f"User {user.email} is not active and cannot generate compliance reports")
            details['user_active'] = False
        else:
            details['user_active'] = True

        # Validate user belongs to tenant
        if tenant:
            if not hasattr(user, 'tenant') or not user.tenant:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False
            elif str(user.tenant.id) != str(tenant.id):
                errors.append(
                    f"User {user.email} belongs to tenant {user.tenant.id} but report generation "
                    f"is for tenant {tenant.id}"
                )
                details['user_tenant_match'] = False
            else:
                details['user_has_tenant'] = True
                details['user_tenant_match'] = True
        elif self.tenant_id:
            # Validate against rule's tenant_id
            if not hasattr(user, 'tenant') or not user.tenant:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False
            elif str(user.tenant.id) != str(self.tenant_id):
                errors.append(
                    f"User {user.email} belongs to tenant {user.tenant.id} but report generation "
                    f"is for tenant {self.tenant_id}"
                )
                details['user_tenant_match'] = False
            else:
                details['user_has_tenant'] = True
                details['user_tenant_match'] = True

        # Validate user permissions (placeholder - integrate with RBAC/ABAC system)
        # For now, we assume all active users in the tenant can generate reports
        # In production, this would check specific permissions like:
        # - 'governance.can_generate_compliance_reports'
        # - 'governance.can_generate_gdpr_reports' (regulation-specific)
        if regulation:
            details['regulation'] = regulation
            # Placeholder for regulation-specific permission checks
            # if not user.has_perm(f'governance.can_generate_{regulation.lower()}_reports'):
            #     errors.append(f"User {user.email} does not have permission to generate {regulation} reports")
        else:
            # Placeholder for general report generation permission
            # if not user.has_perm('governance.can_generate_compliance_reports'):
            #     errors.append(f"User {user.email} does not have permission to generate compliance reports")
            pass

        details['eligible'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_compliance_report_scope(
        self,
        report: Optional[ComplianceReport] = None,
        tenant: Optional[Any] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        regulation: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate report scope (valid resource scope).

        Validates:
        - Tenant scope is valid
        - Date range is valid (start_date < end_date)
        - Date range is reasonable (not too far in past/future)
        - Regulation is valid (if provided)

        Args:
            report: Optional ComplianceReport instance
            tenant: Optional tenant instance
            start_date: Optional start date for report period
            end_date: Optional end date for report period
            regulation: Optional regulation type

        Returns:
            ValidationResult with scope validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'report_scope',
            'scope_valid': False,
        }

        from django.utils import timezone
        from datetime import timedelta

        # Get values from report if provided
        if report:
            tenant = tenant or report.tenant
            start_date = start_date or report.start_date
            end_date = end_date or report.end_date
            regulation = regulation or report.regulation
            details['report_id'] = str(report.id)

        # Validate tenant scope
        if tenant:
            details['tenant_id'] = str(tenant.id)
            details['tenant_name'] = tenant.name if hasattr(tenant, 'name') else None

            # Validate tenant context consistency
            if self.tenant_id and str(tenant.id) != str(self.tenant_id):
                errors.append(
                    f"Report tenant ({tenant.id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True
        elif self.tenant_id:
            details['tenant_id'] = str(self.tenant_id)
            details['tenant_match'] = True
        else:
            errors.append("Tenant is required for report scope validation")
            details['tenant_provided'] = False

        # Validate regulation
        if regulation:
            valid_regulations = {'GDPR', 'HIPAA', 'SOX', 'LGPD', 'CCPA'}
            if regulation not in valid_regulations:
                errors.append(
                    f"Invalid regulation: {regulation}. "
                    f"Valid regulations are: {', '.join(valid_regulations)}"
                )
                details['regulation_valid'] = False
            else:
                details['regulation_valid'] = True
                details['regulation'] = regulation

        # Validate date range
        if start_date and end_date:
            # Ensure dates are timezone-aware
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)

            details['start_date'] = start_date.isoformat()
            details['end_date'] = end_date.isoformat()

            # Validate start_date < end_date
            if start_date >= end_date:
                errors.append(
                    f"Start date ({start_date.date()}) must be before end date ({end_date.date()})"
                )
                details['date_range_valid'] = False
            else:
                details['date_range_valid'] = True
                date_range_days = (end_date - start_date).days
                details['date_range_days'] = date_range_days

                # Warn if date range is very large
                if date_range_days > 365:
                    warnings.append(
                        f"Report date range is very large ({date_range_days} days). "
                        f"Consider using smaller ranges for better performance"
                    )
                    details['large_date_range'] = True

                # Warn if date range is very small
                if date_range_days < 1:
                    warnings.append(
                        f"Report date range is very small ({date_range_days} days). "
                        f"Consider using at least 1 day range"
                    )
                    details['small_date_range'] = True

                # Validate dates are not too far in the past
                max_past_days = 365 * 10  # 10 years
                if start_date < timezone.now() - timedelta(days=max_past_days):
                    warnings.append(
                        f"Start date ({start_date.date()}) is more than {max_past_days} days in the past. "
                        f"Data may not be available"
                    )
                    details['very_old_start_date'] = True

                # Validate dates are not in the future
                if start_date > timezone.now():
                    errors.append(
                        f"Start date ({start_date.date()}) cannot be in the future"
                    )
                    details['future_start_date'] = True

                if end_date > timezone.now():
                    errors.append(
                        f"End date ({end_date.date()}) cannot be in the future"
                    )
                    details['future_end_date'] = True
        elif start_date or end_date:
            errors.append("Both start_date and end_date must be provided for report scope validation")
            details['date_range_complete'] = False

        details['scope_valid'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_compliance_report_format(
        self,
        report: Optional[ComplianceReport] = None,
        report_type: Optional[str] = None,
        regulation: Optional[str] = None,
        export_format: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate report format (valid export formats).

        Validates:
        - Report type is valid (STANDARD, SUMMARY, DETAILED)
        - Regulation is valid (GDPR, HIPAA, SOX, LGPD, CCPA)
        - Export format is valid (if provided: JSON, CSV, PDF, EXCEL)

        Args:
            report: Optional ComplianceReport instance
            report_type: Optional report type
            regulation: Optional regulation type
            export_format: Optional export format

        Returns:
            ValidationResult with format validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'report_format',
            'format_valid': False,
        }

        # Get values from report if provided
        if report:
            report_type = report_type or report.report_type
            regulation = regulation or report.regulation
            details['report_id'] = str(report.id)

        # Validate report type
        if report_type:
            valid_report_types = {'STANDARD', 'SUMMARY', 'DETAILED'}
            if report_type not in valid_report_types:
                errors.append(
                    f"Invalid report type: {report_type}. "
                    f"Valid report types are: {', '.join(valid_report_types)}"
                )
                details['report_type_valid'] = False
            else:
                details['report_type_valid'] = True
                details['report_type'] = report_type

        # Validate regulation
        if regulation:
            valid_regulations = {'GDPR', 'HIPAA', 'SOX', 'LGPD', 'CCPA'}
            if regulation not in valid_regulations:
                errors.append(
                    f"Invalid regulation: {regulation}. "
                    f"Valid regulations are: {', '.join(valid_regulations)}"
                )
                details['regulation_valid'] = False
            else:
                details['regulation_valid'] = True
                details['regulation'] = regulation

        # Validate export format (if provided)
        if export_format:
            valid_export_formats = {'JSON', 'CSV', 'PDF', 'EXCEL', 'XLSX'}
            export_format_upper = export_format.upper()
            if export_format_upper not in valid_export_formats:
                errors.append(
                    f"Invalid export format: {export_format}. "
                    f"Valid export formats are: {', '.join(valid_export_formats)}"
                )
                details['export_format_valid'] = False
            else:
                details['export_format_valid'] = True
                details['export_format'] = export_format_upper

                # Warn about format-specific considerations
                if export_format_upper == 'PDF':
                    warnings.append(
                        "PDF export format may require additional processing time and resources"
                    )
                elif export_format_upper in ['EXCEL', 'XLSX']:
                    warnings.append(
                        "Excel export format may have limitations with very large datasets"
                    )

        details['format_valid'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_compliance_report_access(
        self,
        report: ComplianceReport,
        user: Optional[User] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate report access (user can access report).

        Validates:
        - Report exists
        - User belongs to same tenant as report
        - User has permission to access compliance reports
        - User has permission to access specific regulation (if applicable)

        Args:
            report: ComplianceReport instance to validate access for
            user: User instance requesting access
            tenant: Optional tenant instance

        Returns:
            ValidationResult with access validation status
        """
        errors = []
        warnings = []
        details = {
            'validation_type': 'report_access',
            'access_granted': False,
            'report_id': str(report.id),
            'regulation': report.regulation,
        }

        if not user:
            errors.append("User is required for report access validation")
            details['user_provided'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['user_provided'] = True
        details['user_id'] = str(user.id)
        details['user_email'] = user.email

        # Validate user is active
        if hasattr(user, 'is_active') and not user.is_active:
            errors.append(f"User {user.email} is not active and cannot access compliance reports")
            details['user_active'] = False
        else:
            details['user_active'] = True

        # Validate user belongs to same tenant as report
        if not hasattr(user, 'tenant') or not user.tenant:
            errors.append(f"User {user.email} does not belong to any tenant")
            details['user_has_tenant'] = False
        else:
            details['user_has_tenant'] = True
            user_tenant_id = str(user.tenant.id)
            report_tenant_id = str(report.tenant.id)

            if user_tenant_id != report_tenant_id:
                errors.append(
                    f"User {user.email} belongs to tenant {user_tenant_id} but report belongs to "
                    f"tenant {report_tenant_id}. Users can only access reports from their own tenant"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate tenant context consistency if provided
        if tenant:
            if str(tenant.id) != str(report.tenant.id):
                errors.append(
                    f"Provided tenant ({tenant.id}) does not match report tenant ({report.tenant.id})"
                )
                details['provided_tenant_match'] = False
            else:
                details['provided_tenant_match'] = True

        # Validate user permissions (placeholder - integrate with RBAC/ABAC system)
        # For now, we assume all active users in the tenant can access reports
        # In production, this would check specific permissions like:
        # - 'governance.can_view_compliance_reports'
        # - 'governance.can_view_gdpr_reports' (regulation-specific)
        # Placeholder for regulation-specific permission checks
        # if not user.has_perm(f'governance.can_view_{report.regulation.lower()}_reports'):
        #     errors.append(f"User {user.email} does not have permission to view {report.regulation} reports")

        # Check if report was created by the user (they should always have access)
        if report.created_by and str(report.created_by.id) == str(user.id):
            details['is_creator'] = True
            details['access_granted'] = True
        else:
            details['is_creator'] = False

        # Validate report has data
        if not report.report_data or (isinstance(report.report_data, dict) and len(report.report_data) == 0):
            warnings.append("Report has no data. Report may not have been generated successfully")
            details['has_data'] = False
        else:
            details['has_data'] = True

        details['access_granted'] = len(errors) == 0
        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_compliance_report(
        self,
        report: Optional[ComplianceReport] = None,
        user: Optional[User] = None,
        tenant: Optional[Any] = None,
        regulation: Optional[str] = None,
        report_type: Optional[str] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        export_format: Optional[str] = None,
        validation_type: str = 'all'
    ) -> ValidationResult:
        """
        Validate compliance report comprehensively.

        This method orchestrates all compliance report validation checks:
        - Report generation eligibility validation
        - Report scope validation
        - Report format validation
        - Report access validation (if report exists)

        Args:
            report: Optional ComplianceReport instance
            user: Optional user instance
            tenant: Optional tenant instance
            regulation: Optional regulation type
            report_type: Optional report type
            start_date: Optional start date
            end_date: Optional end date
            export_format: Optional export format
            validation_type: Type of validation ('eligibility', 'scope', 'format', 'access', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'compliance_report_comprehensive',
            'report_id': str(report.id) if report else None,
        }

        # Comprehensive validation: eligibility (if user provided and not just accessing existing report)
        if validation_type in ['all', 'eligibility'] and user and not report:
            eligibility_result = self._validate_compliance_report_generation_eligibility(
                user, tenant, regulation
            )
            result = result.combine(eligibility_result)
            details['eligibility_validated'] = True

        # Comprehensive validation: scope
        if validation_type in ['all', 'scope']:
            scope_result = self._validate_compliance_report_scope(
                report, tenant, start_date, end_date, regulation
            )
            result = result.combine(scope_result)
            details['scope_validated'] = True

        # Comprehensive validation: format
        if validation_type in ['all', 'format']:
            format_result = self._validate_compliance_report_format(
                report, report_type, regulation, export_format
            )
            result = result.combine(format_result)
            details['format_validated'] = True

        # Comprehensive validation: access (if report exists)
        if validation_type in ['all', 'access'] and report and user:
            access_result = self._validate_compliance_report_access(report, user, tenant)
            result = result.combine(access_result)
            details['access_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

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

        # Validate user has tenant if tenant provided
        if tenant and user.tenant_id:
            if str(user.tenant_id) != str(tenant.id):
                errors.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )

        # Validate user tenant matches context tenant if both provided
        if self.tenant_id and user.tenant_id:
            if str(user.tenant_id) != str(self.tenant_id):
                warnings.append(
                    f"User tenant ({user.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

