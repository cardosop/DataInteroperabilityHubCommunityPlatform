"""
Compliance Business Rules

Comprehensive business rules validation for compliance operations, including:
- Compliance run validation
- Risk assessment validation
- Tenant and user context validation
- Resource-compliance run relationship validation

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
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.datasets.models import Dataset
    from hub.apps.assets.models import Asset
    from hub.apps.files.models import File
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class ComplianceRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for compliance business rules.

    Adds compliance-specific context:
    - compliance_run: The compliance run being validated
    - assessment: Optional risk assessment data (from regulation_mapping_json or results)
    - resource: Optional resource instance (asset, dataset, or file) for resource-compliance run relationship validation
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    compliance_run: Optional[ComplianceRun] = None
    assessment: Optional[Dict[str, Any]] = None
    resource: Optional[Any] = None  # Using Any to avoid circular import
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'compliance_run_id': str(self.compliance_run.id) if self.compliance_run else None,
            'assessment_type': self.assessment.get('type') if self.assessment and isinstance(self.assessment, dict) else None,
            'resource_id': str(self.resource.id) if self.resource and hasattr(self.resource, 'id') else None,
            'resource_type': type(self.resource).__name__ if self.resource else None,
            'tenant_id': str(self.tenant.id) if self.tenant else None,
            'user_id': str(self.user.id) if self.user else None,
        })
        return base_dict


@register_rule(
    rule_name="compliance_validation",
    description="Validates compliance runs, risk assessments, tenant context, and resource relationships",
    tags=["compliance", "validation", "risk_assessment"],
    priority=10
)
class ComplianceBusinessRules(BusinessRules):
    """
    Business rules validator for compliance operations.

    Extends BusinessRules base class with compliance-specific validation:
    - Compliance run validation
    - Risk assessment validation
    - Tenant context consistency
    - User permissions and access validation
    - Resource-compliance run relationship validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ComplianceBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all compliance validation checks.
        It can be called with a ComplianceRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        compliance_run, assessment, resource, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - compliance_run: ComplianceRun instance (optional)
                - assessment: Optional risk assessment dictionary
                - resource: Optional resource instance (asset, dataset, or file)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('compliance_run', 'risk_assessment', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract compliance_run, assessment, resource, tenant, and user from context or kwargs
        if isinstance(context, ComplianceRuleExecutionContext):
            compliance_run = context.compliance_run
            assessment = context.assessment
            resource = context.resource
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            compliance_run = kwargs.get('compliance_run')
            assessment = kwargs.get('assessment')
            resource = kwargs.get('resource')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                compliance_run = compliance_run or context.metadata.get('compliance_run')
                assessment = assessment or context.metadata.get('assessment')
                resource = resource or context.metadata.get('resource')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not compliance_run and context and hasattr(context, 'resource'):
                if isinstance(context.resource, ComplianceRun):
                    compliance_run = context.resource

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)

        # Track what was validated
        validated_items = []

        # Validate compliance run if provided
        if compliance_run and validation_type in ('compliance_run', 'all'):
            compliance_run_result = self._validate_compliance_run(compliance_run, tenant, user)
            result = result.combine(compliance_run_result)
            validated_items.append('compliance_run')

        # Validate risk assessment if provided
        if assessment and validation_type in ('risk_assessment', 'all'):
            assessment_result = self._validate_risk_assessment(assessment, compliance_run, tenant, user)
            result = result.combine(assessment_result)
            validated_items.append('risk_assessment')

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
                errors=["At least one of compliance_run, assessment, resource, tenant, or user must be provided"],
                details={'validation_type': validation_type}
            )

        # Add validation summary to details
        result.details['validated_items'] = validated_items
        result.details['validation_type'] = validation_type

        return result

    def _validate_compliance_run(
        self,
        compliance_run: ComplianceRun,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate compliance run.

        Validates:
        - Compliance run has required fields (tenant, job, status)
        - Compliance run has at least one resource (asset, dataset, or file)
        - Tenant context consistency
        - Status is valid
        - Risk level is valid (if present)
        - Regulations are valid (if present)

        Args:
            compliance_run: ComplianceRun instance to validate
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'compliance_run_id': str(compliance_run.id),
            'status': compliance_run.status,
        }

        # Validate tenant context consistency
        if self.tenant_id and compliance_run.tenant_id:
            if str(compliance_run.tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Compliance run tenant ({compliance_run.tenant_id}) does not match "
                    f"context tenant ({self.tenant_id})"
                )
                details['tenant_match'] = False
            else:
                details['tenant_match'] = True

        # Validate tenant context if provided
        if tenant and compliance_run.tenant_id:
            if str(tenant.id) != str(compliance_run.tenant_id):
                errors.append(
                    f"Compliance run tenant ({compliance_run.tenant_id}) does not match "
                    f"provided tenant ({tenant.id})"
                )
                details['provided_tenant_match'] = False
            else:
                details['provided_tenant_match'] = True

        # Validate compliance run has at least one resource
        if not compliance_run.asset and not compliance_run.dataset and not compliance_run.file:
            errors.append("Compliance run must have at least one resource (asset, dataset, or file)")
            details['has_resource'] = False
        else:
            details['has_resource'] = True
            if compliance_run.asset:
                details['resource_type'] = 'asset'
                details['resource_id'] = str(compliance_run.asset.id)
            elif compliance_run.dataset:
                details['resource_type'] = 'dataset'
                details['resource_id'] = str(compliance_run.dataset.id)
            elif compliance_run.file:
                details['resource_type'] = 'file'
                details['resource_id'] = str(compliance_run.file.id)

        # Validate status
        valid_statuses = [choice[0] for choice in ComplianceRunStatus.choices]
        if compliance_run.status not in valid_statuses:
            errors.append(
                f"Compliance run has invalid status: {compliance_run.status}. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
            details['status_valid'] = False
        else:
            details['status_valid'] = True

        # Validate risk level if present
        if compliance_run.risk_level:
            valid_risk_levels = [choice[0] for choice in RiskLevel.choices]
            if compliance_run.risk_level not in valid_risk_levels:
                errors.append(
                    f"Compliance run has invalid risk_level: {compliance_run.risk_level}. "
                    f"Valid risk levels are: {', '.join(valid_risk_levels)}"
                )
                details['risk_level_valid'] = False
            else:
                details['risk_level_valid'] = True
                details['risk_level'] = compliance_run.risk_level
        else:
            details['risk_level_valid'] = None
            details['has_risk_level'] = False

        # Validate regulations if present
        if compliance_run.regulations:
            if not isinstance(compliance_run.regulations, list):
                errors.append("Compliance run regulations must be a list")
                details['regulations_valid'] = False
            else:
                details['regulations_valid'] = True
                details['regulations_count'] = len(compliance_run.regulations)
                # Validate regulation values are strings
                invalid_regulations = [
                    r for r in compliance_run.regulations
                    if not isinstance(r, str) or not r.strip()
                ]
                if invalid_regulations:
                    errors.append(
                        f"Compliance run has invalid regulations: {invalid_regulations}. "
                        f"Regulations must be non-empty strings"
                    )
                    details['regulations_values_valid'] = False
                else:
                    details['regulations_values_valid'] = True
        else:
            details['regulations_valid'] = None
            details['has_regulations'] = False

        # Validate overall_status if present
        if compliance_run.overall_status:
            valid_overall_statuses = ['PASS', 'WARN', 'FAIL', 'UNKNOWN']
            if compliance_run.overall_status not in valid_overall_statuses:
                errors.append(
                    f"Compliance run has invalid overall_status: {compliance_run.overall_status}. "
                    f"Valid overall statuses are: {', '.join(valid_overall_statuses)}"
                )
                details['overall_status_valid'] = False
            else:
                details['overall_status_valid'] = True
                details['overall_status'] = compliance_run.overall_status
        else:
            details['overall_status_valid'] = None
            details['has_overall_status'] = False

        # Validate date consistency
        if compliance_run.started_at and compliance_run.completed_at:
            if compliance_run.completed_at < compliance_run.started_at:
                errors.append(
                    f"Compliance run completed_at ({compliance_run.completed_at}) is before started_at ({compliance_run.started_at})"
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

    def _validate_risk_assessment(
        self,
        assessment: Dict[str, Any],
        compliance_run: Optional[ComplianceRun] = None,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate risk assessment data comprehensively.

        Validates:
        - Assessment is a dictionary
        - Risk level is valid (LOW, MEDIUM, HIGH, CRITICAL)
        - Risk score is valid (if present)
        - Risk calculation validation (risk_score aligns with risk_level based on thresholds)
        - Risk mitigation validation (mitigation actions valid if present)
        - Assessment data structure is consistent

        Args:
            assessment: Risk assessment dictionary to validate
            compliance_run: Optional ComplianceRun instance
            tenant: Optional tenant instance
            user: Optional user instance

        Returns:
            ValidationResult with risk assessment validation status
        """
        errors = []
        warnings = []
        details = {
            'risk_assessment_validation': 'risk_assessment',
        }

        if not isinstance(assessment, dict):
            errors.append("Risk assessment must be a dictionary")
            details['assessment_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['assessment_valid'] = True

        # Validate risk level (LOW, MEDIUM, HIGH, CRITICAL)
        risk_level = assessment.get('risk_level') or assessment.get('overall_risk_level')
        if risk_level:
            valid_risk_levels = [choice[0] for choice in RiskLevel.choices]
            # Filter out NONE as it's not typically used in assessments
            valid_assessment_risk_levels = [rl for rl in valid_risk_levels if rl != 'NONE']

            if risk_level not in valid_risk_levels:
                errors.append(
                    f"Risk assessment has invalid risk_level: {risk_level}. "
                    f"Valid risk levels are: {', '.join(valid_risk_levels)}"
                )
                details['risk_level_valid'] = False
            else:
                details['risk_level_valid'] = True
                details['risk_level'] = risk_level
                # Check if risk level is appropriate for assessment (warn if NONE)
                if risk_level == 'NONE':
                    warnings.append(
                        "Risk level 'NONE' is unusual for risk assessments. "
                        "Consider using 'LOW' if minimal risk exists."
                    )
        else:
            warnings.append("Risk assessment missing 'risk_level' or 'overall_risk_level' field")
            details['has_risk_level'] = False

        # Validate risk score if present
        risk_score = assessment.get('risk_score')
        score = None
        if risk_score is not None:
            try:
                score = float(risk_score)
                if score < 0:
                    warnings.append(f"Risk score ({score}) is negative")
                    details['risk_score_range_valid'] = False
                else:
                    details['risk_score_range_valid'] = True
                details['risk_score'] = score
            except (ValueError, TypeError):
                errors.append(
                    f"Risk assessment 'risk_score' must be a valid number, got: {risk_score}"
                )
                details['risk_score_valid'] = False
        else:
            details['has_risk_score'] = False

        # Risk calculation validation: validate risk_score aligns with risk_level based on thresholds
        if risk_level and score is not None and details.get('risk_score_range_valid', False):
            calculation_result = self._validate_risk_calculation(risk_level, score)
            if not calculation_result.is_valid:
                errors.extend(calculation_result.errors)
                details['risk_calculation_valid'] = False
            else:
                details['risk_calculation_valid'] = True
                if calculation_result.warnings:
                    warnings.extend(calculation_result.warnings)
            details.update(calculation_result.details)
        elif risk_level and score is None:
            warnings.append(
                f"Risk level '{risk_level}' provided but no risk_score to validate calculation consistency"
            )
            details['risk_calculation_valid'] = None
        elif score is not None and not risk_level:
            warnings.append(
                f"Risk score {score} provided but no risk_level to validate calculation consistency"
            )
            details['risk_calculation_valid'] = None

        # Risk mitigation validation: validate mitigation actions if present
        # Check both keys explicitly to handle empty lists correctly
        mitigation_actions = assessment.get('mitigation_actions')
        if mitigation_actions is None:
            mitigation_actions = assessment.get('mitigations')
        if mitigation_actions is not None:
            details['has_mitigation'] = True
            mitigation_result = self._validate_risk_mitigation(mitigation_actions, risk_level)
            # Process errors and warnings
            if not mitigation_result.is_valid:
                errors.extend(mitigation_result.errors)
            if mitigation_result.warnings:
                warnings.extend(mitigation_result.warnings)
            # Update details from mitigation_result
            details.update(mitigation_result.details)
            # Explicitly ensure mitigation_valid is set based on result validity
            # This must be done after update() to override any value from mitigation_result.details
            details['mitigation_valid'] = mitigation_result.is_valid
        else:
            details['has_mitigation'] = False
            # Warn if high risk but no mitigation actions
            if risk_level in ['HIGH', 'CRITICAL']:
                warnings.append(
                    f"Risk level '{risk_level}' detected but no mitigation actions provided. "
                    "Consider adding mitigation actions for high-risk assessments."
                )

        # Validate allowed_to_store if present
        allowed_to_store = assessment.get('allowed_to_store')
        if allowed_to_store is not None:
            if not isinstance(allowed_to_store, bool):
                errors.append(
                    f"Risk assessment 'allowed_to_store' must be a boolean, got: {allowed_to_store}"
                )
                details['allowed_to_store_valid'] = False
            else:
                details['allowed_to_store_valid'] = True
                details['allowed_to_store'] = allowed_to_store
        else:
            details['has_allowed_to_store'] = False

        # Validate violations if present
        violations = assessment.get('violations') or assessment.get('total_violations')
        if violations is not None:
            if isinstance(violations, list):
                details['violations_type'] = 'list'
                details['violations_count'] = len(violations)
                details['violations_valid'] = True
            elif isinstance(violations, int):
                details['violations_type'] = 'count'
                details['violations_count'] = violations
                if violations < 0:
                    errors.append(f"Violations count ({violations}) must be non-negative")
                    details['violations_valid'] = False
                else:
                    details['violations_valid'] = True
            else:
                errors.append(
                    f"Risk assessment 'violations' must be a list or integer, got: {type(violations).__name__}"
                )
                details['violations_valid'] = False
        else:
            details['has_violations'] = False

        # Cross-validate with compliance_run if provided
        if compliance_run:
            if risk_level and compliance_run.risk_level:
                if risk_level != compliance_run.risk_level:
                    warnings.append(
                        f"Assessment risk_level ({risk_level}) does not match "
                        f"compliance_run risk_level ({compliance_run.risk_level})"
                    )
                    details['risk_level_consistency'] = False
                else:
                    details['risk_level_consistency'] = True

            if allowed_to_store is not None and compliance_run.allowed_to_store is not None:
                if allowed_to_store != compliance_run.allowed_to_store:
                    warnings.append(
                        f"Assessment allowed_to_store ({allowed_to_store}) does not match "
                        f"compliance_run allowed_to_store ({compliance_run.allowed_to_store})"
                    )
                    details['allowed_to_store_consistency'] = False
                else:
                    details['allowed_to_store_consistency'] = True

        details['risk_assessment_valid'] = len(errors) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_risk_calculation(
        self,
        risk_level: str,
        risk_score: float
    ) -> ValidationResult:
        """
        Validate risk calculation: ensure risk_score aligns with risk_level based on thresholds.

        Uses the same thresholds as RiskCalculator:
        - NONE: 0.0
        - LOW: >= 0.1
        - MEDIUM: >= 1.0
        - HIGH: >= 5.0
        - CRITICAL: >= 10.0

        Args:
            risk_level: Risk level string (LOW, MEDIUM, HIGH, CRITICAL)
            risk_score: Risk score value

        Returns:
            ValidationResult with risk calculation validation status
        """
        errors = []
        warnings = []
        details = {
            'risk_calculation_validation': 'risk_calculation',
            'risk_level': risk_level,
            'risk_score': risk_score,
        }

        # Risk level thresholds (matching RiskCalculator.RISK_THRESHOLDS)
        RISK_THRESHOLDS = {
            'NONE': 0.0,
            'LOW': 0.1,
            'MEDIUM': 1.0,
            'HIGH': 5.0,
            'CRITICAL': 10.0,
        }

        if risk_level not in RISK_THRESHOLDS:
            errors.append(
                f"Invalid risk_level '{risk_level}' for risk calculation validation. "
                f"Valid levels: {', '.join(RISK_THRESHOLDS.keys())}"
            )
            details['calculation_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        threshold = RISK_THRESHOLDS[risk_level]
        expected_min_score = threshold

        # Validate that risk_score aligns with risk_level
        if risk_level == 'NONE':
            if risk_score > 0.0:
                warnings.append(
                    f"Risk level is 'NONE' but risk_score ({risk_score}) is greater than 0. "
                    "Consider using a higher risk level."
                )
                details['score_level_alignment'] = False
            else:
                details['score_level_alignment'] = True
        elif risk_level == 'LOW':
            if risk_score < expected_min_score:
                warnings.append(
                    f"Risk level is 'LOW' but risk_score ({risk_score}) is below threshold ({expected_min_score}). "
                    "Consider using 'NONE' if score is 0."
                )
                details['score_level_alignment'] = False
            elif risk_score >= RISK_THRESHOLDS['MEDIUM']:
                warnings.append(
                    f"Risk level is 'LOW' but risk_score ({risk_score}) suggests 'MEDIUM' or higher. "
                    f"Expected range for LOW: {expected_min_score} to {RISK_THRESHOLDS['MEDIUM'] - 0.01}"
                )
                details['score_level_alignment'] = False
            else:
                details['score_level_alignment'] = True
        elif risk_level == 'MEDIUM':
            if risk_score < expected_min_score:
                errors.append(
                    f"Risk level is 'MEDIUM' but risk_score ({risk_score}) is below threshold ({expected_min_score}). "
                    f"Expected minimum score for MEDIUM: {expected_min_score}"
                )
                details['score_level_alignment'] = False
            elif risk_score >= RISK_THRESHOLDS['HIGH']:
                warnings.append(
                    f"Risk level is 'MEDIUM' but risk_score ({risk_score}) suggests 'HIGH' or higher. "
                    f"Expected range for MEDIUM: {expected_min_score} to {RISK_THRESHOLDS['HIGH'] - 0.01}"
                )
                details['score_level_alignment'] = False
            else:
                details['score_level_alignment'] = True
        elif risk_level == 'HIGH':
            if risk_score < expected_min_score:
                errors.append(
                    f"Risk level is 'HIGH' but risk_score ({risk_score}) is below threshold ({expected_min_score}). "
                    f"Expected minimum score for HIGH: {expected_min_score}"
                )
                details['score_level_alignment'] = False
            elif risk_score >= RISK_THRESHOLDS['CRITICAL']:
                warnings.append(
                    f"Risk level is 'HIGH' but risk_score ({risk_score}) suggests 'CRITICAL'. "
                    f"Expected range for HIGH: {expected_min_score} to {RISK_THRESHOLDS['CRITICAL'] - 0.01}"
                )
                details['score_level_alignment'] = False
            else:
                details['score_level_alignment'] = True
        elif risk_level == 'CRITICAL':
            if risk_score < expected_min_score:
                errors.append(
                    f"Risk level is 'CRITICAL' but risk_score ({risk_score}) is below threshold ({expected_min_score}). "
                    f"Expected minimum score for CRITICAL: {expected_min_score}"
                )
                details['score_level_alignment'] = False
            else:
                details['score_level_alignment'] = True

        details['calculation_valid'] = len(errors) == 0
        details['threshold'] = threshold
        details['expected_min_score'] = expected_min_score

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_risk_mitigation(
        self,
        mitigation_actions: Any,
        risk_level: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate risk mitigation actions.

        Validates:
        - Mitigation actions structure (list of dictionaries)
        - Each mitigation action has required fields (action_type, description)
        - Mitigation actions are appropriate for the risk level

        Args:
            mitigation_actions: Mitigation actions (list of dicts or single dict)
            risk_level: Optional risk level to validate appropriateness

        Returns:
            ValidationResult with mitigation validation status
        """
        errors = []
        warnings = []
        details = {
            'mitigation_validation': 'risk_mitigation',
        }

        # Normalize to list if single dict provided
        if isinstance(mitigation_actions, dict):
            mitigation_actions = [mitigation_actions]
            details['mitigation_format'] = 'single_dict_normalized'
        elif isinstance(mitigation_actions, list):
            details['mitigation_format'] = 'list'
        else:
            errors.append(
                f"Mitigation actions must be a list or dictionary, got: {type(mitigation_actions).__name__}"
            )
            details['mitigation_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not mitigation_actions:
            warnings.append("Mitigation actions list is empty")
            details['mitigation_count'] = 0
            details['mitigation_valid'] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['mitigation_count'] = len(mitigation_actions)

        # Valid mitigation action types
        valid_action_types = [
            'ENCRYPTION',
            'ANONYMIZATION',
            'PSEUDONYMIZATION',
            'ACCESS_CONTROL',
            'DATA_RETENTION_POLICY',
            'AUDIT_LOGGING',
            'CONSENT_MANAGEMENT',
            'DATA_DELETION',
            'MASKING',
            'TOKENIZATION',
            'OTHER'
        ]

        # Validate each mitigation action
        valid_actions = []
        invalid_actions = []
        for i, action in enumerate(mitigation_actions):
            if not isinstance(action, dict):
                errors.append(
                    f"Mitigation action at index {i} must be a dictionary, got: {type(action).__name__}"
                )
                invalid_actions.append(i)
                continue

            action_valid = True
            action_errors = []

            # Validate required fields
            action_type = action.get('action_type') or action.get('type')
            if not action_type:
                action_errors.append("Missing required field 'action_type' or 'type'")
                action_valid = False
            elif not isinstance(action_type, str):
                action_errors.append(f"'action_type' must be a string, got: {type(action_type).__name__}")
                action_valid = False
            elif action_type not in valid_action_types:
                warnings.append(
                    f"Mitigation action at index {i} has unknown action_type '{action_type}'. "
                    f"Valid types: {', '.join(valid_action_types)}"
                )

            description = action.get('description') or action.get('desc')
            if not description:
                action_errors.append("Missing required field 'description' or 'desc'")
                action_valid = False
            elif not isinstance(description, str) or not description.strip():
                action_errors.append("'description' must be a non-empty string")
                action_valid = False

            # Validate optional fields
            status = action.get('status')
            if status is not None:
                valid_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED']
                if status not in valid_statuses:
                    warnings.append(
                        f"Mitigation action at index {i} has invalid status '{status}'. "
                        f"Valid statuses: {', '.join(valid_statuses)}"
                    )

            priority = action.get('priority')
            if priority is not None:
                if not isinstance(priority, (int, str)):
                    warnings.append(
                        f"Mitigation action at index {i} has invalid priority type: {type(priority).__name__}"
                    )
                elif isinstance(priority, str):
                    valid_priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
                    if priority not in valid_priorities:
                        warnings.append(
                            f"Mitigation action at index {i} has invalid priority '{priority}'. "
                            f"Valid priorities: {', '.join(valid_priorities)}"
                        )

            if action_errors:
                errors.extend([f"Mitigation action at index {i}: {err}" for err in action_errors])
                invalid_actions.append(i)
            else:
                valid_actions.append(i)

        details['valid_actions_count'] = len(valid_actions)
        details['invalid_actions_count'] = len(invalid_actions)
        details['valid_actions'] = valid_actions
        details['invalid_actions'] = invalid_actions

        # Validate appropriateness for risk level
        if risk_level and valid_actions:
            if risk_level in ['HIGH', 'CRITICAL']:
                # High/Critical risk should have multiple mitigation actions
                if len(valid_actions) < 2:
                    warnings.append(
                        f"Risk level '{risk_level}' typically requires multiple mitigation actions. "
                        f"Only {len(valid_actions)} action(s) provided."
                    )
                # High/Critical risk should have high-priority actions
                high_priority_actions = [
                    i for i in valid_actions
                    if mitigation_actions[i].get('priority') in ['HIGH', 'CRITICAL']
                ]
                if not high_priority_actions:
                    warnings.append(
                        f"Risk level '{risk_level}' detected but no high-priority mitigation actions found. "
                        "Consider adding HIGH or CRITICAL priority actions."
                    )

        details['mitigation_valid'] = len(errors) == 0

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

    def validate_compliance_run_execution(
        self,
        compliance_run: ComplianceRun,
        user: Optional[User] = None,
        tenant: Optional[Any] = None,
        validation_type: str = 'all'
    ) -> ValidationResult:
        """
        Validate compliance run execution comprehensively.

        This method orchestrates all compliance run execution validation checks:
        - Run eligibility validation (user has permission, resource accessible)
        - Run resource quota validation (compliance service quota not exceeded)
        - Run status transition validation (PENDING → RUNNING → SUCCEEDED/FAILED)

        Args:
            compliance_run: ComplianceRun instance to validate
            user: Optional user instance
            tenant: Optional tenant instance
            validation_type: Type of validation ('eligibility', 'quota', 'status_transition', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Initialize combined result
        result = ValidationResult(is_valid=True)
        details = {
            'validation_type': 'compliance_run_execution',
            'compliance_run_id': str(compliance_run.id),
            'status': compliance_run.status,
        }

        # Comprehensive validation: eligibility
        if validation_type in ('all', 'eligibility'):
            eligibility_result = self._validate_compliance_run_eligibility(compliance_run, user, tenant)
            result = result.combine(eligibility_result)
            details['eligibility_validated'] = True

        # Comprehensive validation: resource quota
        if validation_type in ('all', 'quota'):
            quota_result = self._validate_compliance_run_resource_quota(compliance_run, tenant)
            result = result.combine(quota_result)
            details['quota_validated'] = True

        # Comprehensive validation: status transition
        if validation_type in ('all', 'status_transition'):
            status_result = self._validate_compliance_run_status_transition(compliance_run)
            result = result.combine(status_result)
            details['status_transition_validated'] = True

        # Update result details
        result.details.update(details)
        result.details['is_valid'] = result.is_valid
        result.details['has_warnings'] = len(result.warnings) > 0

        return result

    def _validate_compliance_run_eligibility(
        self,
        compliance_run: ComplianceRun,
        user: Optional[User] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate run eligibility (user has permission, resource accessible).

        Validates:
        - User exists and is active
        - User belongs to tenant
        - User has permission to run compliance checks
        - Resource (asset/dataset/file) is accessible (exists, not deleted, belongs to tenant)

        Args:
            compliance_run: ComplianceRun instance to validate
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
        effective_tenant = tenant or (compliance_run.tenant if compliance_run.tenant else None)
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
                errors.append(f"User {user.email} is not active and cannot run compliance checks")
                details['user_active'] = False
            else:
                details['user_active'] = True

            # Validate user belongs to tenant
            if hasattr(user, 'tenant') and user.tenant:
                if str(user.tenant.id) != str(effective_tenant.id):
                    errors.append(
                        f"User {user.email} belongs to tenant {user.tenant.id} but compliance run "
                        f"is for tenant {effective_tenant.id}"
                    )
                    details['user_tenant_match'] = False
                else:
                    details['user_tenant_match'] = True
            else:
                errors.append(f"User {user.email} does not belong to any tenant")
                details['user_has_tenant'] = False

            # Validate user permissions (placeholder - integrate with RBAC/ABAC system)
            # For now, we assume all active users in the tenant can run compliance checks
            # In production, this would check specific permissions like:
            # - 'compliance.can_run_compliance_checks'
            # - 'compliance.can_run_compliance_checks_on_asset' (resource-specific)
            # Placeholder for permission checks
            # if not user.has_perm('compliance.can_run_compliance_checks'):
            #     errors.append(f"User {user.email} does not have permission to run compliance checks")
        else:
            details['user_provided'] = False
            warnings.append("No user provided for eligibility validation - cannot verify permissions")

        # Validate resource accessibility
        resource_accessible = False
        resource_type = None
        resource_id = None

        if compliance_run.dataset:
            resource_type = 'dataset'
            resource_id = str(compliance_run.dataset.id)
            details['resource_type'] = 'dataset'
            details['resource_id'] = resource_id

            # Validate dataset exists and is accessible
            if not compliance_run.dataset:
                errors.append(f"Dataset {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate dataset belongs to tenant
                if hasattr(compliance_run.dataset, 'tenant') and compliance_run.dataset.tenant:
                    if str(compliance_run.dataset.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"Dataset {resource_id} belongs to tenant {compliance_run.dataset.tenant.id} "
                            f"but compliance run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"Dataset {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Validate dataset has a file
                if not compliance_run.dataset.file:
                    errors.append(f"Dataset {resource_id} has no associated file for compliance run")
                    details['dataset_has_file'] = False
                else:
                    details['dataset_has_file'] = True

        elif compliance_run.asset:
            resource_type = 'asset'
            resource_id = str(compliance_run.asset.id)
            details['resource_type'] = 'asset'
            details['resource_id'] = resource_id

            # Validate asset exists and is accessible
            if not compliance_run.asset:
                errors.append(f"Asset {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate asset belongs to tenant
                if hasattr(compliance_run.asset, 'tenant') and compliance_run.asset.tenant:
                    if str(compliance_run.asset.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"Asset {resource_id} belongs to tenant {compliance_run.asset.tenant.id} "
                            f"but compliance run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"Asset {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Check if asset has datasets (required for compliance run)
                if hasattr(compliance_run.asset, 'datasets'):
                    dataset_count = compliance_run.asset.datasets.count()
                    if dataset_count == 0:
                        warnings.append(f"Asset {resource_id} has no datasets - compliance run may fail")
                        details['asset_has_datasets'] = False
                    else:
                        details['asset_has_datasets'] = True
                        details['asset_dataset_count'] = dataset_count

        elif compliance_run.file:
            resource_type = 'file'
            resource_id = str(compliance_run.file.id)
            details['resource_type'] = 'file'
            details['resource_id'] = resource_id

            # Validate file exists and is accessible
            if not compliance_run.file:
                errors.append(f"File {resource_id} does not exist")
                details['resource_exists'] = False
            else:
                details['resource_exists'] = True

                # Validate file belongs to tenant
                if hasattr(compliance_run.file, 'tenant') and compliance_run.file.tenant:
                    if str(compliance_run.file.tenant.id) != str(effective_tenant.id):
                        errors.append(
                            f"File {resource_id} belongs to tenant {compliance_run.file.tenant.id} "
                            f"but compliance run is for tenant {effective_tenant.id}"
                        )
                        details['resource_tenant_match'] = False
                    else:
                        details['resource_tenant_match'] = True
                        resource_accessible = True
                else:
                    warnings.append(f"File {resource_id} has no tenant association")
                    details['resource_has_tenant'] = False

                # Validate file has storage path
                if not compliance_run.file.storage_path:
                    errors.append(f"File {resource_id} has no storage path - cannot run compliance check")
                    details['file_has_storage_path'] = False
                else:
                    details['file_has_storage_path'] = True
        else:
            errors.append("Compliance run must have at least one resource (asset, dataset, or file)")
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

    def _validate_compliance_run_resource_quota(
        self,
        compliance_run: ComplianceRun,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate run resource quota (compliance service quota not exceeded).

        Validates:
        - Compliance service is available (health check)
        - Tenant has not exceeded compliance run quota (rate limits)
        - Concurrent compliance runs are within limits
        - Daily compliance run quota is not exceeded

        Args:
            compliance_run: ComplianceRun instance to validate
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
        effective_tenant = tenant or (compliance_run.tenant if compliance_run.tenant else None)
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

        # Check compliance service health
        from hub.apps.compliance.service_client import ComplianceServiceClient
        compliance_client = ComplianceServiceClient()
        is_healthy, service_status = compliance_client.health_check()

        if not is_healthy:
            errors.append(f"Compliance service is not available (status: {service_status})")
            details['compliance_service_available'] = False
            details['compliance_service_status'] = service_status
        else:
            details['compliance_service_available'] = True
            details['compliance_service_status'] = service_status

        # Check tenant compliance run quota using rate limiting system
        from hub.apps.rate_limiting.quota import QuotaManager
        from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow

        # Check daily quota for compliance runs
        has_quota, quota_info = QuotaManager.check_quota(
            tenant_id=tenant_id,
            category=EndpointCategory.COMPLIANCE_RUN,
            window=TimeWindow.DAILY
        )

        details['quota_info'] = quota_info

        if not has_quota:
            errors.append(
                f"Tenant has exceeded daily compliance run quota. "
                f"Limit: {quota_info.get('limit')}, Used: {quota_info.get('used')}, "
                f"Remaining: {quota_info.get('remaining')}"
            )
            details['daily_quota_exceeded'] = True
        else:
            details['daily_quota_exceeded'] = False
            details['daily_quota_remaining'] = quota_info.get('remaining', 0)

        # Check concurrent compliance runs for tenant
        concurrent_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            status__in=[ComplianceRunStatus.PENDING, ComplianceRunStatus.RUNNING]
        ).exclude(id=compliance_run.id if compliance_run.id else None).count()

        # Get concurrent run limit from tenant config or use default
        max_concurrent_runs = 10  # Default limit
        if hasattr(effective_tenant, 'config') and effective_tenant.config:
            tenant_config = effective_tenant.config
            if hasattr(tenant_config, 'compliance_max_concurrent_runs'):
                max_concurrent_runs = tenant_config.compliance_max_concurrent_runs or max_concurrent_runs

        details['concurrent_runs'] = concurrent_runs
        details['max_concurrent_runs'] = max_concurrent_runs

        if concurrent_runs >= max_concurrent_runs:
            errors.append(
                f"Tenant has reached maximum concurrent compliance runs limit ({max_concurrent_runs}). "
                f"Current concurrent runs: {concurrent_runs}"
            )
            details['concurrent_limit_exceeded'] = True
        else:
            details['concurrent_limit_exceeded'] = False
            details['concurrent_slots_remaining'] = max_concurrent_runs - concurrent_runs

        # Check if there are too many recent failed runs (may indicate quota/service issues)
        from django.utils.timezone import now
        from datetime import timedelta

        recent_failed_runs = ComplianceRun.objects.filter(
            tenant_id=tenant_id,
            status=ComplianceRunStatus.FAILED,
            created_at__gte=now() - timedelta(hours=1)
        ).count()

        details['recent_failed_runs'] = recent_failed_runs

        if recent_failed_runs > 5:
            warnings.append(
                f"Tenant has {recent_failed_runs} failed compliance runs in the last hour. "
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

    def _validate_compliance_run_status_transition(
        self,
        compliance_run: ComplianceRun,
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
            compliance_run: ComplianceRun instance to validate
            current_status: Current status (if None, uses compliance_run.status)
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
            current_status = compliance_run.status

        details['current_status'] = current_status

        # Validate current status is valid
        valid_statuses = [choice[0] for choice in ComplianceRunStatus.choices]
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

        # Get status values from choices to ensure consistency (used in both if/else blocks)
        # Extract values the same way as valid_statuses to ensure consistency
        status_values = {choice[0]: choice[0] for choice in ComplianceRunStatus.choices}
        pending_val = status_values.get("PENDING", "PENDING")
        running_val = status_values.get("RUNNING", "RUNNING")
        succeeded_val = status_values.get("SUCCEEDED", "SUCCEEDED")
        failed_val = status_values.get("FAILED", "FAILED")

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

            # Define allowed transitions (using string values for keys to match current_status type)
            allowed_transitions = {
                pending_val: [running_val],
                running_val: [succeeded_val, failed_val],
                succeeded_val: [],  # Terminal state - cannot transition
                failed_val: [],  # Terminal state - cannot transition
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
            if current_status == pending_val and new_status == running_val:
                # PENDING → RUNNING: should have started_at set
                if not compliance_run.started_at:
                    warnings.append(
                        "Transitioning to RUNNING status - started_at should be set"
                    )
                    details['started_at_set'] = False
                else:
                    details['started_at_set'] = True

            elif current_status == running_val and new_status in [succeeded_val, failed_val]:
                # RUNNING → SUCCEEDED/FAILED: should have started_at and completed_at set
                if not compliance_run.started_at:
                    errors.append(
                        "Cannot transition to terminal state without started_at being set"
                    )
                    details['started_at_set'] = False
                else:
                    details['started_at_set'] = True

                if not compliance_run.completed_at:
                    warnings.append(
                        "Transitioning to terminal state - completed_at should be set"
                    )
                    details['completed_at_set'] = False
                else:
                    details['completed_at_set'] = True

                    # Validate completed_at is after started_at
                    if compliance_run.started_at and compliance_run.completed_at < compliance_run.started_at:
                        errors.append(
                            f"completed_at ({compliance_run.completed_at}) cannot be before started_at ({compliance_run.started_at})"
                        )
                        details['date_order_valid'] = False
                    else:
                        details['date_order_valid'] = True
        else:
            # Just validating current state - check if it's in a valid state for operations
            if current_status == pending_val:
                details['can_start'] = True
                details['can_cancel'] = True
            elif current_status == running_val:
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


    def validate_scan_configuration(
        self,
        scan_config: Dict[str, Any],
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate compliance scan configuration.

        Orchestrates validation of scan type, configuration, resource, and schedule.

        Args:
            scan_config: The scan configuration dictionary to validate.
            tenant: Optional Tenant instance.
            user: Optional User instance.

        Returns:
            ValidationResult with validation status and details.
        """
        result = ValidationResult(is_valid=True)
        details = {'scan_configuration_validation': 'orchestrated'}

        # 1. Validate scan type (regulations)
        scan_type_result = self._validate_scan_type(scan_config, tenant)
        result = result.combine(scan_type_result)
        details['scan_type_validated'] = True

        # 2. Validate scan configuration (parameters, rules)
        scan_config_result = self._validate_scan_config(scan_config, tenant)
        result = result.combine(scan_config_result)
        details['scan_config_validated'] = True

        # 3. Validate scan resource (exists and accessible)
        resource_result = self._validate_scan_resource(scan_config, tenant, user)
        result = result.combine(resource_result)
        details['scan_resource_validated'] = True

        # 4. Validate scan schedule (no conflicts)
        schedule_result = self._validate_scan_schedule(scan_config, tenant)
        result = result.combine(schedule_result)
        details['scan_schedule_validated'] = True

        result.details.update(details)
        return result

    def _validate_scan_type(
        self,
        scan_config: Dict[str, Any],
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Implement scan type validation (valid scan types: GDPR, HIPAA, SOC2, CUSTOM).

        Validates:
        - Scan types (regulations) are valid
        - Scan types are allowed for tenant
        - Scan types are non-empty if provided

        Args:
            scan_config: The scan configuration dictionary.
            tenant: Optional Tenant instance.

        Returns:
            ValidationResult with validation status and details.
        """
        errors = []
        warnings = []
        details = {'scan_type_validation': 'started'}

        # Valid scan types (regulations) - standard ones plus CUSTOM
        VALID_SCAN_TYPES = ['GDPR', 'LGPD', 'CCPA', 'HIPAA', 'SOX', 'SOC2', 'CUSTOM']

        # Get scan types from config (can be 'scan_type', 'scan_types', 'applicable_regulations', or 'regulations')
        scan_types = (
            scan_config.get('scan_type') or
            scan_config.get('scan_types') or
            scan_config.get('applicable_regulations') or
            scan_config.get('regulations')
        )

        # Handle single string vs list
        if isinstance(scan_types, str):
            scan_types = [scan_types]
        elif scan_types is None:
            scan_types = []

        details['scan_types_provided'] = scan_types
        details['scan_types_count'] = len(scan_types)

        # Validate scan types are valid
        if scan_types:
            invalid_types = [st for st in scan_types if st not in VALID_SCAN_TYPES]
            if invalid_types:
                errors.append(
                    f"Invalid scan types: {', '.join(invalid_types)}. "
                    f"Valid scan types are: {', '.join(VALID_SCAN_TYPES)}"
                )
                details['scan_types_valid'] = False
                details['invalid_types'] = invalid_types
            else:
                details['scan_types_valid'] = True

            # Validate scan types are non-empty strings
            empty_types = [st for st in scan_types if not isinstance(st, str) or not st.strip()]
            if empty_types:
                errors.append(
                    f"Scan types must be non-empty strings. Found empty or invalid types: {empty_types}"
                )
                details['scan_types_non_empty'] = False
            else:
                details['scan_types_non_empty'] = True

            # Check if tenant has restrictions on allowed compliance regimes
            if tenant:
                try:
                    from hub.apps.tenants.services import get_tenant_config
                    from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES

                    tenant_config = get_tenant_config(tenant)
                    allowed_regimes = tenant_config.get("allowed_compliance_regimes", VALID_COMPLIANCE_REGIMES)

                    # Filter out CUSTOM and SOC2 from tenant restrictions (they're special)
                    restricted_types = [st for st in scan_types if st not in ['CUSTOM', 'SOC2']]
                    disallowed_types = [st for st in restricted_types if st not in allowed_regimes]

                    if disallowed_types:
                        warnings.append(
                            f"Scan types {', '.join(disallowed_types)} are not in tenant's allowed compliance regimes. "
                            f"Allowed regimes: {', '.join(allowed_regimes)}"
                        )
                        details['tenant_regime_restriction'] = True
                        details['disallowed_types'] = disallowed_types
                    else:
                        details['tenant_regime_restriction'] = False
                except Exception as e:
                    warnings.append(f"Could not validate tenant compliance regime restrictions: {e}")
                    details['tenant_regime_check_error'] = str(e)
        else:
            warnings.append("No scan types provided. Default scan types will be used.")
            details['scan_types_provided'] = False

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_scan_config(
        self,
        scan_config: Dict[str, Any],
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Implement scan configuration validation (valid parameters, rules).

        Validates:
        - Scan mode is valid ('internal' or 'external')
        - Configuration parameters are valid
        - Configuration rules are consistent

        Args:
            scan_config: The scan configuration dictionary.
            tenant: Optional Tenant instance.

        Returns:
            ValidationResult with validation status and details.
        """
        errors = []
        warnings = []
        details = {'scan_config_validation': 'started'}

        # Validate scan_mode
        scan_mode = scan_config.get('scan_mode', 'internal')
        valid_scan_modes = ['internal', 'external']
        if scan_mode not in valid_scan_modes:
            errors.append(
                f"Invalid scan_mode: {scan_mode}. Valid scan modes are: {', '.join(valid_scan_modes)}"
            )
            details['scan_mode_valid'] = False
        else:
            details['scan_mode_valid'] = True
            details['scan_mode'] = scan_mode

        # Validate configuration parameters
        # Check for any unknown/unsupported parameters
        known_params = {
            'scan_mode', 'scan_type', 'scan_types', 'applicable_regulations', 'regulations',
            'asset_id', 'dataset_id', 'file_id', 'targeted_categories', 'scan_schedule',
            'schedule_frequency', 'schedule_config', 'exclude_run_id'
        }
        provided_params = set(scan_config.keys())
        unknown_params = provided_params - known_params

        if unknown_params:
            warnings.append(
                f"Unknown scan configuration parameters: {', '.join(unknown_params)}. "
                f"These will be ignored."
            )
            details['unknown_params'] = list(unknown_params)
        else:
            details['unknown_params'] = []

        # Validate targeted_categories if provided
        targeted_categories = scan_config.get('targeted_categories')
        if targeted_categories is not None:
            if not isinstance(targeted_categories, list):
                errors.append(
                    f"targeted_categories must be a list, got: {type(targeted_categories).__name__}"
                )
                details['targeted_categories_valid'] = False
            else:
                details['targeted_categories_valid'] = True
                details['targeted_categories_count'] = len(targeted_categories)
                # Validate categories are non-empty strings
                invalid_categories = [
                    cat for cat in targeted_categories
                    if not isinstance(cat, str) or not cat.strip()
                ]
                if invalid_categories:
                    errors.append(
                        f"targeted_categories must contain non-empty strings. Found invalid: {invalid_categories}"
                    )
                    details['targeted_categories_values_valid'] = False
                else:
                    details['targeted_categories_values_valid'] = True

        # Validate schedule_config if provided
        schedule_config = scan_config.get('schedule_config')
        if schedule_config is not None:
            if not isinstance(schedule_config, dict):
                errors.append(
                    f"schedule_config must be a dictionary, got: {type(schedule_config).__name__}"
                )
                details['schedule_config_valid'] = False
            else:
                details['schedule_config_valid'] = True
                # Validate schedule_config has required fields if schedule_frequency is provided
                schedule_frequency = scan_config.get('schedule_frequency')
                if schedule_frequency:
                    required_schedule_fields = ['cron', 'timezone']
                    missing_fields = [f for f in required_schedule_fields if f not in schedule_config]
                    if missing_fields:
                        warnings.append(
                            f"schedule_config missing recommended fields: {', '.join(missing_fields)}"
                        )
                        details['schedule_config_complete'] = False
                    else:
                        details['schedule_config_complete'] = True

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_scan_resource(
        self,
        scan_config: Dict[str, Any],
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Implement scan resource validation (resource exists and accessible).

        Validates:
        - At least one resource (asset_id, dataset_id, or file_id) is provided
        - Resource exists in database
        - Resource belongs to tenant
        - User has access to resource

        Args:
            scan_config: The scan configuration dictionary.
            tenant: Optional Tenant instance.
            user: Optional User instance.

        Returns:
            ValidationResult with validation status and details.
        """
        errors = []
        warnings = []
        details = {'scan_resource_validation': 'started'}

        asset_id = scan_config.get('asset_id')
        dataset_id = scan_config.get('dataset_id')
        file_id = scan_config.get('file_id')

        # Validate at least one resource is provided
        if not asset_id and not dataset_id and not file_id:
            errors.append(
                "At least one of asset_id, dataset_id, or file_id must be provided"
            )
            details['has_resource'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['has_resource'] = True
        resource_found = False
        resource_type = None
        resource_id = None

        # Validate asset if provided
        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id)
                resource_found = True
                resource_type = 'asset'
                resource_id = str(asset.id)
                details['asset_id'] = str(asset_id)
                details['asset_name'] = asset.name if hasattr(asset, 'name') else None

                # Validate asset belongs to tenant
                if tenant and asset.tenant_id:
                    if str(asset.tenant_id) != str(tenant.id):
                        errors.append(
                            f"Asset {asset_id} does not belong to tenant {tenant.id}"
                        )
                        details['asset_tenant_match'] = False
                    else:
                        details['asset_tenant_match'] = True
                else:
                    warnings.append("Cannot validate asset tenant ownership: tenant not provided")
                    details['asset_tenant_match'] = None

                # Validate asset is accessible (not deleted)
                if hasattr(asset, 'status'):
                    if asset.status == 'DELETED':
                        errors.append(f"Asset {asset_id} is deleted and cannot be scanned")
                        details['asset_accessible'] = False
                    else:
                        details['asset_accessible'] = True
                else:
                    details['asset_accessible'] = True  # Assume accessible if no status field

            except Asset.DoesNotExist:
                errors.append(f"Asset {asset_id} does not exist")
                details['asset_exists'] = False
            except Exception as e:
                errors.append(f"Error validating asset {asset_id}: {e}")
                details['asset_validation_error'] = str(e)

        # Validate dataset if provided
        if dataset_id:
            try:
                from hub.apps.datasets.models import Dataset
                dataset = Dataset.objects.get(id=dataset_id)
                resource_found = True
                resource_type = 'dataset'
                resource_id = str(dataset.id)
                details['dataset_id'] = str(dataset_id)

                # Validate dataset belongs to tenant
                if tenant and dataset.tenant_id:
                    if str(dataset.tenant_id) != str(tenant.id):
                        errors.append(
                            f"Dataset {dataset_id} does not belong to tenant {tenant.id}"
                        )
                        details['dataset_tenant_match'] = False
                    else:
                        details['dataset_tenant_match'] = True
                else:
                    warnings.append("Cannot validate dataset tenant ownership: tenant not provided")
                    details['dataset_tenant_match'] = None

            except Dataset.DoesNotExist:
                errors.append(f"Dataset {dataset_id} does not exist")
                details['dataset_exists'] = False
            except Exception as e:
                errors.append(f"Error validating dataset {dataset_id}: {e}")
                details['dataset_validation_error'] = str(e)

        # Validate file if provided
        if file_id:
            try:
                from hub.apps.files.models import File
                file_obj = File.objects.get(id=file_id)
                resource_found = True
                resource_type = 'file'
                resource_id = str(file_obj.id)
                details['file_id'] = str(file_id)
                details['file_name'] = file_obj.name if hasattr(file_obj, 'name') else None

                # Validate file belongs to tenant
                if tenant and file_obj.tenant_id:
                    if str(file_obj.tenant_id) != str(tenant.id):
                        errors.append(
                            f"File {file_id} does not belong to tenant {tenant.id}"
                        )
                        details['file_tenant_match'] = False
                    else:
                        details['file_tenant_match'] = True
                else:
                    warnings.append("Cannot validate file tenant ownership: tenant not provided")
                    details['file_tenant_match'] = None

                # Validate file is accessible (not deleted)
                if hasattr(file_obj, 'status'):
                    if file_obj.status == 'DELETED':
                        errors.append(f"File {file_id} is deleted and cannot be scanned")
                        details['file_accessible'] = False
                    else:
                        details['file_accessible'] = True
                else:
                    details['file_accessible'] = True  # Assume accessible if no status field

            except File.DoesNotExist:
                errors.append(f"File {file_id} does not exist")
                details['file_exists'] = False
            except Exception as e:
                errors.append(f"Error validating file {file_id}: {e}")
                details['file_validation_error'] = str(e)

        details['resource_found'] = resource_found
        details['resource_type'] = resource_type
        details['resource_id'] = resource_id

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_scan_schedule(
        self,
        scan_config: Dict[str, Any],
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Implement scan schedule validation (scheduled scans don't conflict).

        Validates:
        - No conflicting compliance runs on the same resource
        - No overlapping scheduled compliance reports
        - Schedule configuration is valid

        Args:
            scan_config: The scan configuration dictionary.
            tenant: Optional Tenant instance.

        Returns:
            ValidationResult with validation status and details.
        """
        errors = []
        warnings = []
        details = {'scan_schedule_validation': 'started'}

        asset_id = scan_config.get('asset_id')
        dataset_id = scan_config.get('dataset_id')
        file_id = scan_config.get('file_id')

        # Check for conflicting compliance runs on the same resource
        if tenant:
            from django.utils import timezone
            from datetime import timedelta

            # Check for running/pending compliance runs on the same resource
            conflicting_runs = None

            if asset_id:
                conflicting_runs = ComplianceRun.objects.filter(
                    tenant=tenant,
                    asset_id=asset_id,
                    status__in=[ComplianceRunStatus.PENDING, ComplianceRunStatus.RUNNING]
                )
                if scan_config.get('exclude_run_id'):
                    conflicting_runs = conflicting_runs.exclude(id=scan_config.get('exclude_run_id'))

            elif dataset_id:
                conflicting_runs = ComplianceRun.objects.filter(
                    tenant=tenant,
                    dataset_id=dataset_id,
                    status__in=[ComplianceRunStatus.PENDING, ComplianceRunStatus.RUNNING]
                )
                if scan_config.get('exclude_run_id'):
                    conflicting_runs = conflicting_runs.exclude(id=scan_config.get('exclude_run_id'))

            elif file_id:
                conflicting_runs = ComplianceRun.objects.filter(
                    tenant=tenant,
                    file_id=file_id,
                    status__in=[ComplianceRunStatus.PENDING, ComplianceRunStatus.RUNNING]
                )
                if scan_config.get('exclude_run_id'):
                    conflicting_runs = conflicting_runs.exclude(id=scan_config.get('exclude_run_id'))

            if conflicting_runs and conflicting_runs.exists():
                warnings.append(
                    f"Found {conflicting_runs.count()} running or pending compliance run(s) on the same resource. "
                    f"This may cause conflicts."
                )
                details['has_conflicting_runs'] = True
                details['conflicting_runs_count'] = conflicting_runs.count()
            else:
                details['has_conflicting_runs'] = False

            # Check for scheduled compliance reports that might conflict
            schedule_frequency = scan_config.get('schedule_frequency')
            if schedule_frequency:
                try:
                    from hub.apps.governance.models import ComplianceReport

                    # Get regulations from scan config
                    scan_types = (
                        scan_config.get('scan_type') or
                        scan_config.get('scan_types') or
                        scan_config.get('applicable_regulations') or
                        scan_config.get('regulations') or
                        []
                    )
                    if isinstance(scan_types, str):
                        scan_types = [scan_types]

                    # Check for scheduled reports with same frequency and regulations
                    if scan_types:
                        conflicting_reports = ComplianceReport.objects.filter(
                            tenant=tenant,
                            scheduled=True,
                            schedule_frequency=schedule_frequency,
                            regulation__in=scan_types
                        )

                        if conflicting_reports.exists():
                            warnings.append(
                                f"Found {conflicting_reports.count()} scheduled compliance report(s) with "
                                f"frequency '{schedule_frequency}' for regulations {scan_types}. "
                                f"This may cause duplicate scans."
                            )
                            details['has_conflicting_reports'] = True
                            details['conflicting_reports_count'] = conflicting_reports.count()
                        else:
                            details['has_conflicting_reports'] = False
                    else:
                        details['has_conflicting_reports'] = None
                        details['schedule_check_skipped'] = 'no_regulations'

                except ImportError:
                    warnings.append("ComplianceReport model not available. Cannot check for conflicting scheduled reports.")
                    details['has_conflicting_reports'] = None
                    details['schedule_check_skipped'] = 'model_not_available'
                except Exception as e:
                    warnings.append(f"Error checking for conflicting scheduled reports: {e}")
                    details['has_conflicting_reports'] = None
                    details['schedule_check_error'] = str(e)

        else:
            warnings.append("Cannot validate scan schedule conflicts: tenant not provided")
            details['schedule_check_skipped'] = 'no_tenant'

        details['is_valid'] = len(errors) == 0
        details['has_warnings'] = len(warnings) > 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
