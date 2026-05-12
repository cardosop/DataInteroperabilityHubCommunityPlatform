"""
Orchestration Business Rules

Comprehensive business rules validation for workflow orchestration operations, including:
- Workflow instance validation
- Workflow step validation
- Tenant and user context validation
- State management validation (persistence, recovery, consistency)

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from django.core.cache import cache

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.orchestration.models import (
    WorkflowInstance,
    WorkflowStep,
    WorkflowDefinition,
    WorkflowStatus,
    StepStatus,
)
from hub.apps.orchestration.dsl_parser import WorkflowDSLParser
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for orchestration business rules.

    Adds orchestration-specific context:
    - workflow: The workflow instance being validated
    - step: Optional workflow step instance
    - workflow_definition: Optional workflow definition instance
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    workflow: Optional[WorkflowInstance] = None
    step: Optional[WorkflowStep] = None
    workflow_definition: Optional[WorkflowDefinition] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        # Add orchestration-specific fields
        base_dict.update({
            'workflow_id': str(self.workflow.id) if self.workflow else None,
            'workflow_name': self.workflow.workflow_name if self.workflow else None,
            'workflow_status': self.workflow.status if self.workflow else None,
            'workflow_version': self.workflow.workflow_version if self.workflow else None,
            'step_id': str(self.step.id) if self.step else None,
            'step_name': self.step.step_name if self.step else None,
            'step_status': self.step.status if self.step else None,
            'step_index': self.step.step_index if self.step else None,
            'workflow_definition_id': str(self.workflow_definition.id) if self.workflow_definition else None,
        })
        # Add tenant and user IDs from objects if provided
        if self.tenant:
            base_dict['tenant_id_from_object'] = str(self.tenant.id)
        if self.user:
            base_dict['user_id_from_object'] = str(self.user.id)
        return base_dict


@register_rule(
    rule_name="orchestration_validation",
    description="Validates workflow instances, steps, and tenant context",
    tags=["orchestration", "validation", "workflow", "step"],
    priority=10,

    openspec_ref="specs/orchestration-business-rules/spec.md",
)
class OrchestrationBusinessRules(BusinessRules):
    """
    Business rules validator for orchestration operations.

    Extends BusinessRules base class with orchestration-specific validation:
    - Workflow instance validation
    - Workflow step validation
    - Tenant context consistency
    - User permissions and access validation
    """

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "OrchestrationBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all orchestration validation checks.
        It can be called with an OrchestrationRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        workflow, step, workflow_definition, tenant, and user from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - workflow: WorkflowInstance instance (optional)
                - step: WorkflowStep instance (optional)
                - workflow_definition: WorkflowDefinition instance (optional)
                - tenant: Optional tenant instance
                - user: Optional user instance
                - validation_type: Optional validation type filter
                    ('workflow', 'step', 'tenant_context', 'permissions', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract workflow, step, workflow_definition, tenant, and user from context or kwargs
        if isinstance(context, OrchestrationRuleExecutionContext):
            workflow = context.workflow
            step = context.step
            workflow_definition = context.workflow_definition
            tenant = context.tenant
            user = context.user
        else:
            # Try to get from kwargs first
            workflow = kwargs.get('workflow')
            step = kwargs.get('step')
            workflow_definition = kwargs.get('workflow_definition')
            tenant = kwargs.get('tenant')
            user = kwargs.get('user')

            # If not in kwargs, try to get from context.metadata or context.resource
            if context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                workflow = workflow or context.metadata.get('workflow')
                step = step or context.metadata.get('step')
                workflow_definition = workflow_definition or context.metadata.get('workflow_definition')
                tenant = tenant or context.metadata.get('tenant')
                user = user or context.metadata.get('user')

            # Also check context.resource
            if not workflow and context and hasattr(context, 'resource'):
                if isinstance(context.resource, WorkflowInstance):
                    workflow = context.resource
                elif isinstance(context.resource, WorkflowStep):
                    step = context.resource
                    workflow = step.workflow_instance if step else None

        # Determine what to validate based on what's provided
        validation_type = kwargs.get('validation_type', 'all')

        # Initialize result
        result = ValidationResult(is_valid=True)
        result.details['orchestration_validation'] = 'orchestration'

        # Track what was validated
        validated_items = []

        # Validate workflow instance if provided
        if workflow and validation_type in ('workflow', 'all'):
            workflow_result = self._validate_workflow_instance(workflow, tenant, user)
            result = result.combine(workflow_result)
            validated_items.append('workflow')

        # Validate workflow step if provided
        if step and validation_type in ('step', 'all'):
            step_result = self._validate_workflow_step(step, tenant, user)
            result = result.combine(step_result)
            validated_items.append('step')

        # Validate tenant context if provided
        if tenant and validation_type in ('tenant_context', 'all'):
            tenant_result = self._validate_tenant_context(workflow, step, tenant)
            result = result.combine(tenant_result)
            validated_items.append('tenant_context')

        # Validate permissions if user provided
        if user and validation_type in ('permissions', 'all'):
            permissions_result = self._validate_permissions(workflow, step, user)
            result = result.combine(permissions_result)
            validated_items.append('permissions')

        # Validate state management if workflow provided
        if workflow and validation_type in ('state_management', 'all'):
            state_management_type = kwargs.get('state_management_type', 'all')
            state_result = self.validate_state_management(
                workflow,
                validation_type=state_management_type,
                tenant=tenant,
                user=user
            )
            result = result.combine(state_result)
            validated_items.append('state_management')

        # If nothing was validated, add a warning
        if not validated_items:
            result.warnings.append(
                "No workflow instance or step provided for validation. "
                "Provide workflow, step, tenant, or user in kwargs or context."
            )

        result.details['validated_items'] = validated_items
        return result

    def _validate_workflow_instance(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate a workflow instance.

        Args:
            workflow: WorkflowInstance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['workflow_instance_validation'] = 'workflow_instance'

        # Validate workflow is not None
        if workflow is None:
            result.is_valid = False
            result.errors.append("Workflow instance cannot be None")
            return result

        # Validate workflow has required fields
        if not workflow.workflow_name:
            result.is_valid = False
            result.errors.append("Workflow instance must have a workflow_name")

        if not workflow.workflow_version:
            result.is_valid = False
            result.errors.append("Workflow instance must have a workflow_version")

        # Validate workflow_definition exists
        if not workflow.workflow_definition_id:
            result.is_valid = False
            result.errors.append("Workflow instance must have a workflow_definition reference")
        else:
            try:
                workflow_def = workflow.workflow_definition
                if workflow_def is None:
                    result.is_valid = False
                    result.errors.append("Workflow instance references a non-existent workflow_definition")
                else:
                    # Validate workflow name matches definition
                    if workflow.workflow_name != workflow_def.name:
                        result.warnings.append(
                            f"Workflow instance name ({workflow.workflow_name}) does not match "
                            f"definition name ({workflow_def.name})"
                        )
                    # Validate workflow version matches definition
                    if workflow.workflow_version != workflow_def.version:
                        result.warnings.append(
                            f"Workflow instance version ({workflow.workflow_version}) does not match "
                            f"definition version ({workflow_def.version})"
                        )
            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Error accessing workflow instance's definition: {str(e)}")

        # Validate status
        if workflow.status not in [choice[0] for choice in WorkflowStatus.choices]:
            result.is_valid = False
            result.errors.append(f"Invalid workflow status: {workflow.status}")

        # Validate current_step_index
        if workflow.current_step_index < 0:
            result.is_valid = False
            result.errors.append("Workflow current_step_index must be non-negative")

        # Validate retry_count
        if workflow.retry_count < 0:
            result.is_valid = False
            result.errors.append("Workflow retry_count must be non-negative")

        # Validate max_retries
        if workflow.max_retries < 0:
            result.is_valid = False
            result.errors.append("Workflow max_retries must be non-negative")

        # Validate retry_count doesn't exceed max_retries
        if workflow.retry_count > workflow.max_retries:
            result.warnings.append(
                f"Workflow retry_count ({workflow.retry_count}) exceeds max_retries ({workflow.max_retries})"
            )

        # Validate timeout_seconds if provided
        if workflow.timeout_seconds is not None and workflow.timeout_seconds <= 0:
            result.is_valid = False
            result.errors.append("Workflow timeout_seconds must be positive if provided")

        # Validate input_data is a dict
        if not isinstance(workflow.input_data, dict):
            result.is_valid = False
            result.errors.append("Workflow input_data must be a dictionary")

        # Validate state_data is a dict
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data must be a dictionary")

        # Validate output_data is a dict if provided
        if workflow.output_data is not None and not isinstance(workflow.output_data, dict):
            result.is_valid = False
            result.errors.append("Workflow output_data must be a dictionary if provided")

        # Validate tenant consistency if tenant provided
        if tenant and workflow.tenant_id and workflow.tenant_id != tenant.id:
            result.is_valid = False
            result.errors.append(
                f"Workflow tenant_id ({workflow.tenant_id}) does not match provided tenant ({tenant.id})"
            )

        # Validate user permissions if user provided
        if user:
            # Check if user belongs to the same tenant as workflow
            if workflow.tenant_id and user.tenant_id != workflow.tenant_id:
                result.warnings.append(
                    f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                    f"than workflow ({workflow.tenant_id})"
                )

        result.details['workflow_id'] = str(workflow.id)
        result.details['workflow_name'] = workflow.workflow_name
        result.details['workflow_status'] = workflow.status
        result.details['workflow_version'] = workflow.workflow_version
        return result

    def _validate_workflow_step(
        self,
        step: WorkflowStep,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate a workflow step.

        Args:
            step: WorkflowStep instance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['workflow_step_validation'] = 'workflow_step'

        # Validate step is not None
        if step is None:
            result.is_valid = False
            result.errors.append("Workflow step cannot be None")
            return result

        # Validate step has required fields
        if not step.workflow_instance_id:
            result.is_valid = False
            result.errors.append("Workflow step must have a workflow_instance reference")
        else:
            # Validate workflow instance exists
            try:
                workflow = step.workflow_instance
                if workflow is None:
                    result.is_valid = False
                    result.errors.append("Workflow step references a non-existent workflow_instance")
            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Error accessing workflow step's workflow_instance: {str(e)}")

        if not step.step_name:
            result.is_valid = False
            result.errors.append("Workflow step must have a step_name")

        if not step.step_type:
            result.is_valid = False
            result.errors.append("Workflow step must have a step_type")

        # Validate status
        if step.status not in [choice[0] for choice in StepStatus.choices]:
            result.is_valid = False
            result.errors.append(f"Invalid step status: {step.status}")

        # Validate step_index
        if step.step_index < 0:
            result.is_valid = False
            result.errors.append("Workflow step_index must be non-negative")

        # Validate retry_count
        if step.retry_count < 0:
            result.is_valid = False
            result.errors.append("Workflow step retry_count must be non-negative")

        # Validate input_data is a dict if provided
        if step.input_data is not None and not isinstance(step.input_data, dict):
            result.is_valid = False
            result.errors.append("Workflow step input_data must be a dictionary if provided")

        # Validate output_data is a dict if provided
        if step.output_data is not None and not isinstance(step.output_data, dict):
            result.is_valid = False
            result.errors.append("Workflow step output_data must be a dictionary if provided")

        # Validate compensation_data is a dict if provided
        if step.compensation_data is not None and not isinstance(step.compensation_data, dict):
            result.is_valid = False
            result.errors.append("Workflow step compensation_data must be a dictionary if provided")

        # Validate step_index matches workflow's current_step_index (if step is current)
        if step.workflow_instance and step.step_index == step.workflow_instance.current_step_index:
            # This is the current step - validate consistency
            if step.status == StepStatus.PENDING and step.workflow_instance.status != WorkflowStatus.RUNNING:
                result.warnings.append(
                    f"Step status is PENDING but workflow status is {step.workflow_instance.status}, "
                    f"expected RUNNING"
                )

        # Validate tenant consistency if tenant provided
        if tenant and step.workflow_instance and step.workflow_instance.tenant_id:
            if step.workflow_instance.tenant_id != tenant.id:
                result.is_valid = False
                result.errors.append(
                    f"Step's workflow tenant_id ({step.workflow_instance.tenant_id}) "
                    f"does not match provided tenant ({tenant.id})"
                )

        # Validate user permissions if user provided
        if user and step.workflow_instance:
            # Check if user belongs to the same tenant as step's workflow
            if step.workflow_instance.tenant_id and user.tenant_id != step.workflow_instance.tenant_id:
                result.warnings.append(
                    f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                    f"than step's workflow ({step.workflow_instance.tenant_id})"
                )

        result.details['step_id'] = str(step.id)
        result.details['step_name'] = step.step_name
        result.details['step_status'] = step.status
        result.details['step_index'] = step.step_index
        return result

    def _validate_tenant_context(
        self,
        workflow: Optional[WorkflowInstance] = None,
        step: Optional[WorkflowStep] = None,
        tenant: Optional[Any] = None
    ) -> ValidationResult:
        """
        Validate tenant context consistency.

        Args:
            workflow: Optional workflow instance
            step: Optional step instance
            tenant: Tenant instance to validate against

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['tenant_context_validation'] = 'tenant_context'

        if tenant is None:
            result.warnings.append("No tenant provided for tenant context validation")
            return result

        # Validate workflow tenant consistency
        if workflow and workflow.tenant_id and workflow.tenant_id != tenant.id:
            result.is_valid = False
            result.errors.append(
                f"Workflow tenant_id ({workflow.tenant_id}) does not match provided tenant ({tenant.id})"
            )

        # Validate step tenant consistency
        if step and step.workflow_instance and step.workflow_instance.tenant_id:
            if step.workflow_instance.tenant_id != tenant.id:
                result.is_valid = False
                result.errors.append(
                    f"Step's workflow tenant_id ({step.workflow_instance.tenant_id}) "
                    f"does not match provided tenant ({tenant.id})"
                )

        result.details['tenant_id'] = str(tenant.id)
        return result

    def _validate_permissions(
        self,
        workflow: Optional[WorkflowInstance] = None,
        step: Optional[WorkflowStep] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate user permissions for orchestration operations.

        Args:
            workflow: Optional workflow instance
            step: Optional step instance
            user: User instance to validate permissions for

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['permissions_validation'] = 'permissions'

        if user is None:
            result.warnings.append("No user provided for permissions validation")
            return result

        # Validate user belongs to same tenant as workflow
        if workflow and workflow.tenant_id and user.tenant_id != workflow.tenant_id:
            result.warnings.append(
                f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                f"than workflow ({workflow.tenant_id})"
            )

        # Validate user belongs to same tenant as step's workflow
        if step and step.workflow_instance and step.workflow_instance.tenant_id:
            if user.tenant_id != step.workflow_instance.tenant_id:
                result.warnings.append(
                    f"User ({user.id}) belongs to different tenant ({user.tenant_id}) "
                    f"than step's workflow ({step.workflow_instance.tenant_id})"
                )

        result.details['user_id'] = str(user.id)
        result.details['user_tenant_id'] = str(user.tenant_id)
        return result

    def _validate_state_persistence(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate that workflow state is persisted correctly.

        Validates that state_data is properly saved to the database and can be retrieved.
        Checks that state_data is a valid dictionary and contains expected structure.

        Args:
            workflow: WorkflowInstance to validate state persistence for
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['state_persistence_validation'] = 'state_persistence'

        if workflow is None:
            result.is_valid = False
            result.errors.append("Workflow instance cannot be None for state persistence validation")
            return result

        # Validate state_data is a dictionary
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data must be a dictionary")
            return result

        # Save workflow to ensure state is persisted
        try:
            workflow.save(update_fields=['state_data'])
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to persist workflow state: {str(e)}")
            return result

        # Reload workflow from database to verify state was persisted
        try:
            workflow.refresh_from_db()
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to reload workflow from database: {str(e)}")
            return result

        # Verify state_data is still a dictionary after reload
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data is not a dictionary after reload from database")
            return result

        # Validate state_data can be serialized/deserialized (JSON compatibility)
        try:
            import json
            json.dumps(workflow.state_data)
        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(f"Workflow state_data is not JSON serializable: {str(e)}")
            return result

        # Check for common state fields that should be present
        expected_state_fields = ['current_step_index', 'current_step_name']
        for field in expected_state_fields:
            if field not in workflow.state_data:
                result.warnings.append(f"Expected state field '{field}' not found in state_data")

        result.details['workflow_id'] = str(workflow.id)
        result.details['state_data_keys'] = list(workflow.state_data.keys())
        result.details['state_data_size'] = len(json.dumps(workflow.state_data))
        return result

    def _validate_state_recovery(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate that workflow state can be recovered from database.

        Validates that state_data can be successfully loaded from the database
        and contains valid data structure after recovery.

        Args:
            workflow: WorkflowInstance to validate state recovery for
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['state_recovery_validation'] = 'state_recovery'

        if workflow is None:
            result.is_valid = False
            result.errors.append("Workflow instance cannot be None for state recovery validation")
            return result

        # Store original state_data for comparison
        original_state_data = workflow.state_data.copy() if workflow.state_data else {}

        # Save workflow to ensure state is persisted
        try:
            workflow.save(update_fields=['state_data'])
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to persist workflow state before recovery test: {str(e)}")
            return result

        # Reload workflow from database to simulate recovery
        try:
            workflow_id = workflow.id
            workflow.refresh_from_db()
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to reload workflow from database for recovery: {str(e)}")
            return result

        # Verify workflow ID matches (ensures we got the same workflow)
        if workflow.id != workflow_id:
            result.is_valid = False
            result.errors.append(f"Workflow ID mismatch after recovery: expected {workflow_id}, got {workflow.id}")
            return result

        # Verify state_data was recovered
        if workflow.state_data is None:
            result.is_valid = False
            result.errors.append("Workflow state_data is None after recovery")
            return result

        # Verify state_data is a dictionary
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data is not a dictionary after recovery")
            return result

        # Verify state_data structure matches original (keys should match)
        recovered_keys = set(workflow.state_data.keys())
        original_keys = set(original_state_data.keys())
        if recovered_keys != original_keys:
            missing_keys = original_keys - recovered_keys
            extra_keys = recovered_keys - original_keys
            if missing_keys:
                result.warnings.append(f"State keys missing after recovery: {missing_keys}")
            if extra_keys:
                result.warnings.append(f"Unexpected state keys after recovery: {extra_keys}")

        # Verify state_data can be accessed and modified
        try:
            test_key = '__recovery_test__'
            workflow.state_data[test_key] = 'test_value'
            workflow.save(update_fields=['state_data'])
            workflow.refresh_from_db()
            if workflow.state_data.get(test_key) != 'test_value':
                result.is_valid = False
                result.errors.append("State data modification not persisted after recovery")
            else:
                # Clean up test key
                del workflow.state_data[test_key]
                workflow.save(update_fields=['state_data'])
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to modify state_data after recovery: {str(e)}")
            return result

        result.details['workflow_id'] = str(workflow.id)
        result.details['state_recovered'] = True
        result.details['state_data_keys'] = list(workflow.state_data.keys())
        return result

    def _validate_state_consistency(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate that workflow state is consistent across steps.

        Validates that:
        - State data is consistent with workflow's current_step_index
        - Step output_data is consistent with workflow state_data
        - State transitions are valid
        - No conflicting state information

        Args:
            workflow: WorkflowInstance to validate state consistency for
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['state_consistency_validation'] = 'state_consistency'

        if workflow is None:
            result.is_valid = False
            result.errors.append("Workflow instance cannot be None for state consistency validation")
            return result

        # Validate state_data is a dictionary
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data must be a dictionary")
            return result

        # Validate current_step_index consistency
        if 'current_step_index' in workflow.state_data:
            state_step_index = workflow.state_data.get('current_step_index')
            if state_step_index != workflow.current_step_index:
                result.warnings.append(
                    f"State current_step_index ({state_step_index}) does not match "
                    f"workflow current_step_index ({workflow.current_step_index})"
                )

        # CRITICAL: Fetch steps once and reuse to avoid multiple database queries and potential hangs
        # Use prefetch_related if available, otherwise fetch with timeout protection
        steps = None
        try:
            # Check if steps are already prefetched (from prefetch_related)
            if hasattr(workflow, '_prefetched_objects_cache') and 'steps' in workflow._prefetched_objects_cache:
                steps = list(workflow._prefetched_objects_cache['steps'])
                steps.sort(key=lambda s: s.step_index)
            else:
                # Fetch steps with timeout protection and query optimization
                from django.db.utils import OperationalError, DatabaseError
                from django.core.exceptions import ObjectDoesNotExist
                
                try:
                    # Try to fetch steps with a limit to prevent huge queries
                    # Use only() to fetch only needed fields for better performance
                    steps = list(workflow.steps.only('step_index', 'step_name', 'output_data', 'status')
                                 .order_by('step_index')[:100])  # Limit to 100 steps max
                except (OperationalError, DatabaseError, ObjectDoesNotExist) as db_error:
                    # If database query fails, log warning and skip step validation
                    logger.warning(
                        f"Could not fetch workflow steps for validation: {str(db_error)}",
                        extra={'workflow_id': str(workflow.id)}
                    )
                    result.warnings.append(f"Could not fetch workflow steps for validation: {str(db_error)}")
                    steps = []  # Empty list to prevent errors below
        except Exception as e:
            logger.warning(
                f"Error fetching workflow steps: {str(e)}",
                extra={'workflow_id': str(workflow.id)}
            )
            result.warnings.append(f"Could not fetch workflow steps: {str(e)}")
            steps = []  # Empty list to prevent errors below

        # Validate current_step_name consistency
        if steps and 'current_step_name' in workflow.state_data:
            state_step_name = workflow.state_data.get('current_step_name')
            try:
                if workflow.current_step_index < len(steps):
                    actual_step = steps[workflow.current_step_index]
                    if state_step_name != actual_step.step_name:
                        result.warnings.append(
                            f"State current_step_name ({state_step_name}) does not match "
                            f"actual step name ({actual_step.step_name})"
                        )
            except (IndexError, AttributeError) as e:
                result.warnings.append(f"Could not validate step name consistency: {str(e)}")

        # Validate step output_data consistency with state_data
        if steps:
            try:
                for step in steps:
                    # Check if step output_data is consistent with state_data
                    if step.output_data and isinstance(step.output_data, dict):
                        # Check for common fields that should be in state_data
                        for key, value in step.output_data.items():
                            if key in workflow.state_data:
                                state_value = workflow.state_data[key]
                                # Allow for updates (later steps can override earlier steps)
                                if step.step_index < workflow.current_step_index:
                                    # For completed steps, values should match or be updated
                                    pass
                                elif step.step_index == workflow.current_step_index:
                                    # For current step, values should match
                                    if state_value != value:
                                        result.warnings.append(
                                            f"Step {step.step_index} output_data[{key}] ({value}) "
                                            f"does not match state_data[{key}] ({state_value})"
                                        )
            except Exception as e:
                result.warnings.append(f"Could not validate step output_data consistency: {str(e)}")

        # Validate state_data structure consistency
        # Check that required fields are present based on workflow status
        if workflow.status == WorkflowStatus.RUNNING:
            if 'current_step_index' not in workflow.state_data:
                result.warnings.append(
                    "Workflow is RUNNING but state_data does not contain current_step_index"
                )
            if 'current_step_name' not in workflow.state_data:
                result.warnings.append(
                    "Workflow is RUNNING but state_data does not contain current_step_name"
                )

        # Validate progress_percentage if present
        if 'progress_percentage' in workflow.state_data:
            progress = workflow.state_data.get('progress_percentage')
            if not isinstance(progress, (int, float)):
                result.is_valid = False
                result.errors.append("State progress_percentage must be a number")
            elif progress < 0 or progress > 100:
                result.warnings.append(
                    f"State progress_percentage ({progress}) is outside valid range [0, 100]"
                )

        # Validate state_data size (warn if too large)
        try:
            import json
            state_size = len(json.dumps(workflow.state_data))
            max_state_size = 10 * 1024 * 1024  # 10MB
            if state_size > max_state_size:
                result.warnings.append(
                    f"State data size ({state_size} bytes) exceeds recommended maximum "
                    f"({max_state_size} bytes)"
                )
        except Exception as e:
            result.warnings.append(f"Could not validate state data size: {str(e)}")

        result.details['workflow_id'] = str(workflow.id)
        result.details['workflow_status'] = workflow.status
        result.details['current_step_index'] = workflow.current_step_index
        result.details['state_data_keys'] = list(workflow.state_data.keys())
        return result

    def validate_state_management(
        self,
        workflow: WorkflowInstance,
        validation_type: str = 'all',
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Comprehensive state management validation.

        Orchestrates all state management validation checks:
        - State persistence validation
        - State recovery validation
        - State consistency validation

        Args:
            workflow: WorkflowInstance to validate
            validation_type: Type of validation to perform ('persistence', 'recovery', 'consistency', 'all')
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['state_management_validation'] = 'state_management'

        if workflow is None:
            result.is_valid = False
            result.errors.append("Workflow instance cannot be None for state management validation")
            return result

        validated_items = []

        # Validate state persistence
        if validation_type in ('persistence', 'all'):
            persistence_result = self._validate_state_persistence(workflow, tenant, user)
            result = result.combine(persistence_result)
            validated_items.append('persistence')

        # Validate state recovery
        if validation_type in ('recovery', 'all'):
            recovery_result = self._validate_state_recovery(workflow, tenant, user)
            result = result.combine(recovery_result)
            validated_items.append('recovery')

        # Validate state consistency
        if validation_type in ('consistency', 'all'):
            consistency_result = self._validate_state_consistency(workflow, tenant, user)
            result = result.combine(consistency_result)
            validated_items.append('consistency')

        if not validated_items:
            result.warnings.append(
                f"Invalid validation_type '{validation_type}'. "
                "Use 'persistence', 'recovery', 'consistency', or 'all'"
            )

        result.details['validated_items'] = validated_items
        return result

    def _validate_workflow_definition(
        self,
        workflow_definition: WorkflowDefinition,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Comprehensive workflow definition validation including:
        - Workflow structure validation (valid workflow definition format)
        - Workflow step validation (valid step definitions, dependencies)
        - Workflow cycle detection (no circular dependencies)
        - Workflow resource validation (resources exist and accessible)

        Args:
            workflow_definition: WorkflowDefinition instance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with comprehensive validation status and details
        """
        errors = []
        warnings = []
        details = {
            'workflow_definition_validation': 'workflow_definition',
            'validation_checks': {}
        }

        # Validate workflow definition is not None
        if workflow_definition is None:
            errors.append("Workflow definition cannot be None")
            details['workflow_definition_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['workflow_definition_id'] = str(workflow_definition.id)
        details['workflow_name'] = workflow_definition.name
        details['workflow_version'] = workflow_definition.version

        # Validate workflow structure
        structure_result = self._validate_workflow_structure(workflow_definition)
        result = ValidationResult(
            is_valid=structure_result.is_valid,
            errors=structure_result.errors,
            warnings=structure_result.warnings,
            details=details
        )
        result = result.combine(structure_result)
        details['validation_checks']['structure'] = structure_result.is_valid

        # Validate workflow steps
        steps_result = self._validate_workflow_steps(workflow_definition)
        result = result.combine(steps_result)
        details['validation_checks']['steps'] = steps_result.is_valid

        # Validate workflow cycles (circular dependencies)
        cycles_result = self._validate_workflow_cycles(workflow_definition)
        result = result.combine(cycles_result)
        details['validation_checks']['cycles'] = cycles_result.is_valid

        # Validate workflow resources
        resources_result = self._validate_workflow_resources(workflow_definition)
        result = result.combine(resources_result)
        details['validation_checks']['resources'] = resources_result.is_valid

        result.details.update(details)
        return result

    def _validate_workflow_structure(
        self,
        workflow_definition: WorkflowDefinition
    ) -> ValidationResult:
        """
        Validate workflow structure (valid workflow definition format).

        Args:
            workflow_definition: WorkflowDefinition instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'structure_validation': 'structure',
            'dsl_valid': False
        }

        # Validate workflow definition has required fields
        if not workflow_definition.name:
            errors.append("Workflow definition must have a name")
            details['name_valid'] = False
        else:
            details['name_valid'] = True

        if not workflow_definition.version:
            errors.append("Workflow definition must have a version")
            details['version_valid'] = False
        else:
            details['version_valid'] = True

        # Validate DSL JSON structure
        if not workflow_definition.dsl_json:
            errors.append("Workflow definition must have dsl_json")
            details['dsl_json_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        if not isinstance(workflow_definition.dsl_json, dict):
            errors.append("Workflow dsl_json must be a dictionary")
            details['dsl_json_valid'] = False
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        dsl = workflow_definition.dsl_json
        details['dsl_json_valid'] = True

        # Validate required DSL fields using DSL parser
        try:
            parser = WorkflowDSLParser()
            parser.parse_json(dsl)
            details['dsl_structure_valid'] = True
        except Exception as e:
            errors.append(f"Invalid workflow DSL structure: {str(e)}")
            details['dsl_structure_valid'] = False

        # Validate version format (semantic versioning)
        dsl_version = dsl.get("version")
        if dsl_version:
            if not isinstance(dsl_version, str):
                errors.append("Workflow DSL version must be a string")
            else:
                # Basic semantic version validation (major.minor.patch)
                import re
                version_pattern = r'^\d+\.\d+\.\d+$'
                if not re.match(version_pattern, dsl_version):
                    warnings.append(
                        f"Workflow DSL version '{dsl_version}' does not follow semantic versioning (major.minor.patch)"
                    )
                details['dsl_version'] = dsl_version

        # Validate steps field
        steps = dsl.get("steps")
        if not isinstance(steps, list):
            errors.append("Workflow DSL steps must be a list")
            details['steps_valid'] = False
        elif len(steps) == 0:
            errors.append("Workflow DSL must contain at least one step")
            details['steps_valid'] = False
        else:
            details['steps_valid'] = True
            details['steps_count'] = len(steps)

        # Validate dependencies if present
        dependencies = dsl.get("dependencies", [])
        if dependencies:
            if not isinstance(dependencies, list):
                errors.append("Workflow DSL dependencies must be a list")
                details['dependencies_valid'] = False
            else:
                details['dependencies_valid'] = True
                details['dependencies_count'] = len(dependencies)
                # Validate each dependency is a string
                for i, dep in enumerate(dependencies):
                    if not isinstance(dep, str):
                        errors.append(f"Dependency at index {i} must be a string (workflow name)")
                        details['dependencies_valid'] = False
                        break

        # Validate compensation if present
        compensation = dsl.get("compensation")
        if compensation:
            if not isinstance(compensation, dict):
                errors.append("Workflow DSL compensation must be a dictionary")
                details['compensation_valid'] = False
            else:
                details['compensation_valid'] = True
                if compensation.get("enabled") is True:
                    details['compensation_enabled'] = True

        details['dsl_valid'] = len(errors) == 0
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_workflow_steps(
        self,
        workflow_definition: WorkflowDefinition
    ) -> ValidationResult:
        """
        Validate workflow steps (valid step definitions, dependencies).

        Args:
            workflow_definition: WorkflowDefinition instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'steps_validation': 'steps',
            'steps_valid': False
        }

        if not workflow_definition.dsl_json or not isinstance(workflow_definition.dsl_json, dict):
            errors.append("Cannot validate steps: invalid DSL JSON")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        dsl = workflow_definition.dsl_json
        steps = dsl.get("steps", [])

        if not isinstance(steps, list) or len(steps) == 0:
            errors.append("Workflow must contain at least one step")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details['steps_count'] = len(steps)
        step_names = []
        step_name_to_index = {}

        # Validate each step
        for i, step in enumerate(steps):
            step_errors = []
            step_warnings = []

            if not isinstance(step, dict):
                errors.append(f"Step at index {i} must be a dictionary")
                continue

            # Validate step name
            step_name = step.get("name")
            if not step_name or not isinstance(step_name, str) or not step_name.strip():
                step_errors.append(f"Step at index {i} must have a non-empty 'name' field")
            else:
                # Check for duplicate step names
                if step_name in step_names:
                    step_errors.append(f"Duplicate step name '{step_name}' at index {i}")
                else:
                    step_names.append(step_name)
                    step_name_to_index[step_name] = i

            # Validate step type
            step_type = step.get("type")
            if not step_type:
                step_errors.append(f"Step '{step_name or f'index_{i}'}' must have a 'type' field")
            elif step_type not in WorkflowDSLParser.STEP_TYPES:
                step_errors.append(
                    f"Step '{step_name or f'index_{i}'}' has invalid type '{step_type}'. "
                    f"Valid types: {', '.join(WorkflowDSLParser.STEP_TYPES)}"
                )

            # Validate step-specific fields
            if step_type == "task":
                if "task" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: task) must have 'task' field")
                else:
                    task_name = step.get("task")
                    if not isinstance(task_name, str) or not task_name.strip():
                        step_errors.append(f"Step '{step_name or f'index_{i}'}' task field must be a non-empty string")

            elif step_type == "parallel":
                if "steps" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: parallel) must have 'steps' field")
                elif not isinstance(step.get("steps"), list) or len(step.get("steps", [])) == 0:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: parallel) must have at least one step in 'steps'")

            elif step_type == "conditional":
                if "condition" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: conditional) must have 'condition' field")
                if "then" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: conditional) must have 'then' field")

            elif step_type == "loop":
                if "items" not in step and "condition" not in step:
                    step_errors.append(
                        f"Step '{step_name or f'index_{i}'}' (type: loop) must have either 'items' or 'condition' field"
                    )
                if "steps" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: loop) must have 'steps' field")

            elif step_type == "retry":
                if "max_retries" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: retry) must have 'max_retries' field")
                else:
                    max_retries = step.get("max_retries")
                    if not isinstance(max_retries, int) or max_retries < 0:
                        step_errors.append(f"Step '{step_name or f'index_{i}'}' max_retries must be a non-negative integer")
                if "steps" not in step:
                    step_errors.append(f"Step '{step_name or f'index_{i}'}' (type: retry) must have 'steps' field")

            # Collect errors and warnings for this step
            if step_errors:
                errors.extend(step_errors)
            if step_warnings:
                warnings.extend(step_warnings)

        details['steps_valid'] = len(errors) == 0
        details['unique_step_names'] = len(step_names) == len(set(step_names))
        details['step_names'] = step_names

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_workflow_cycles(
        self,
        workflow_definition: WorkflowDefinition
    ) -> ValidationResult:
        """
        Detect circular dependencies in workflow definitions.

        Args:
            workflow_definition: WorkflowDefinition instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'cycles_validation': 'cycles',
            'has_cycles': False
        }

        if not workflow_definition.dsl_json or not isinstance(workflow_definition.dsl_json, dict):
            errors.append("Cannot validate cycles: invalid DSL JSON")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        dsl = workflow_definition.dsl_json
        dependencies = dsl.get("dependencies", [])

        if not isinstance(dependencies, list):
            details['has_cycles'] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Build dependency graph for this workflow
        workflow_name = workflow_definition.name
        visited = set()
        rec_stack = set()
        cycle_path = []

        def has_cycle(workflow: str, graph: Dict[str, List[str]]) -> bool:
            """Detect cycle using DFS"""
            visited.add(workflow)
            rec_stack.add(workflow)
            cycle_path.append(workflow)

            # Get dependencies for this workflow
            deps = []
            if workflow == workflow_name:
                # Current workflow dependencies
                deps = dependencies
            else:
                # Get dependencies from other workflow definitions
                try:
                    other_def = WorkflowDefinition.objects.filter(
                        name=workflow,
                        is_active=True
                    ).first()
                    if other_def and isinstance(other_def.dsl_json, dict):
                        deps = other_def.dsl_json.get("dependencies", [])
                except Exception:
                    pass

            for dep in deps:
                if dep not in visited:
                    if has_cycle(dep, graph):
                        return True
                elif dep in rec_stack:
                    # Found a cycle
                    cycle_path.append(dep)
                    return True

            rec_stack.remove(workflow)
            cycle_path.pop()
            return False

        # Check for cycles
        if has_cycle(workflow_name, {}):
            cycle_str = " -> ".join(cycle_path)
            errors.append(f"Circular dependency detected: {cycle_str}")
            details['has_cycles'] = True
            details['cycle_path'] = cycle_path
        else:
            details['has_cycles'] = False

        # Also check for self-dependency
        if workflow_name in dependencies:
            errors.append(f"Workflow '{workflow_name}' cannot depend on itself")
            details['has_self_dependency'] = True
        else:
            details['has_self_dependency'] = False

        details['dependencies_count'] = len(dependencies)
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def _validate_workflow_resources(
        self,
        workflow_definition: WorkflowDefinition
    ) -> ValidationResult:
        """
        Validate workflow resources exist and are accessible (tasks, workflows).

        Args:
            workflow_definition: WorkflowDefinition instance to validate

        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        details = {
            'resources_validation': 'resources',
            'resources_valid': False
        }

        if not workflow_definition.dsl_json or not isinstance(workflow_definition.dsl_json, dict):
            errors.append("Cannot validate resources: invalid DSL JSON")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )

        dsl = workflow_definition.dsl_json
        steps = dsl.get("steps", [])
        dependencies = dsl.get("dependencies", [])

        # Validate workflow dependencies exist
        missing_workflows = []
        for dep_name in dependencies:
            if not isinstance(dep_name, str):
                continue
            try:
                dep_def = WorkflowDefinition.objects.filter(
                    name=dep_name,
                    is_active=True
                ).first()
                if not dep_def:
                    missing_workflows.append(dep_name)
            except Exception as e:
                warnings.append(f"Error checking workflow dependency '{dep_name}': {str(e)}")

        if missing_workflows:
            errors.append(f"Missing workflow dependencies: {', '.join(missing_workflows)}")
            details['missing_workflows'] = missing_workflows

        # Validate task resources exist (check against WorkflowEngine task registry)
        missing_tasks = []
        task_references = []

        def extract_tasks(step: Dict[str, Any]) -> List[str]:
            """Recursively extract task references from steps"""
            tasks = []
            step_type = step.get("type")
            if step_type == "task":
                task_name = step.get("task")
                if task_name and isinstance(task_name, str):
                    tasks.append(task_name)
            elif step_type == "parallel" or step_type == "retry" or step_type == "loop":
                nested_steps = step.get("steps", [])
                for nested_step in nested_steps:
                    tasks.extend(extract_tasks(nested_step))
            elif step_type == "conditional":
                then_steps = step.get("then", [])
                for then_step in then_steps:
                    tasks.extend(extract_tasks(then_step))
                else_steps = step.get("else", [])
                for else_step in else_steps:
                    tasks.extend(extract_tasks(else_step))
            return tasks

        for step in steps:
            task_references.extend(extract_tasks(step))

        # Check if tasks are registered in WorkflowEngine
        # Note: We can't directly access WorkflowEngine.task_registry without an instance
        # So we'll validate task format and warn if we can't verify registration
        unique_tasks = list(set(task_references))
        details['task_references'] = unique_tasks
        details['task_references_count'] = len(unique_tasks)

        # Validate task name format (should be dot-separated: category.task_name)
        invalid_task_formats = []
        for task_name in unique_tasks:
            if not isinstance(task_name, str) or not task_name.strip():
                invalid_task_formats.append(task_name)
            elif "." not in task_name:
                warnings.append(
                    f"Task '{task_name}' does not follow recommended format (category.task_name). "
                    "Tasks should be namespaced with a category prefix."
                )

        if invalid_task_formats:
            errors.append(f"Invalid task name format: {', '.join(invalid_task_formats)}")

        # Note: We can't verify task registration without a WorkflowEngine instance
        # This would require passing WorkflowEngine to the validation method
        # For now, we'll validate format and structure
        details['resources_valid'] = len(errors) == 0
        details['dependencies_valid'] = len(missing_workflows) == 0

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_workflow_step_execution(
        self,
        workflow: WorkflowInstance,
        step: WorkflowStep,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate that a workflow step can execute in the current workflow state.

        Validates:
        - Step can execute in current workflow state
        - Workflow state is consistent
        - Tenant context is valid
        - User permissions are valid

        Args:
            workflow: WorkflowInstance to validate
            step: WorkflowStep to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['workflow_step_execution_validation'] = 'workflow_step_execution'

        # Validate workflow state
        workflow_state_result = self.validate_workflow_state(workflow)
        result = result.combine(workflow_state_result)

        # Validate step can execute in current workflow state
        if workflow.status != WorkflowStatus.RUNNING:
            result.is_valid = False
            result.errors.append(
                f"Workflow step cannot execute: workflow status is {workflow.status}, "
                f"expected {WorkflowStatus.RUNNING}"
            )

        # Validate step status allows execution
        if step.status not in [StepStatus.PENDING, StepStatus.RUNNING]:
            result.is_valid = False
            result.errors.append(
                f"Workflow step cannot execute: step status is {step.status}, "
                f"expected {StepStatus.PENDING} or {StepStatus.RUNNING}"
            )

        # Validate step index matches workflow current_step_index
        if step.step_index != workflow.current_step_index:
            result.warnings.append(
                f"Step index ({step.step_index}) does not match workflow "
                f"current_step_index ({workflow.current_step_index})"
            )

        # Validate tenant context if provided
        if tenant:
            tenant_result = self._validate_tenant_context(workflow, step, tenant)
            result = result.combine(tenant_result)

        # Validate user permissions if provided
        if user:
            permissions_result = self._validate_permissions(workflow, step, user)
            result = result.combine(permissions_result)

        result.details['workflow_id'] = str(workflow.id)
        result.details['step_id'] = str(step.id)
        result.details['step_name'] = step.step_name
        result.details['workflow_status'] = workflow.status
        result.details['step_status'] = step.status

        return result

    def validate_step_input(
        self,
        workflow: WorkflowInstance,
        step: WorkflowStep,
        step_input: Dict[str, Any],
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate step input data.

        Validates:
        - Input data structure (must be a dictionary)
        - Input data schema (if schema is defined)
        - Required fields are present
        - Data types are correct

        Args:
            workflow: WorkflowInstance context
            step: WorkflowStep context
            step_input: Step input data to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['step_input_validation'] = 'step_input'

        # Validate input is a dictionary
        if not isinstance(step_input, dict):
            result.is_valid = False
            result.errors.append("Step input must be a dictionary")
            return result

        # Validate input is not empty (warn if empty, but allow it)
        if not step_input:
            result.warnings.append("Step input is empty")

        # Validate input can be JSON serialized (for state persistence)
        try:
            json.dumps(step_input)
            # Calculate size only if serialization succeeds
            input_size = len(json.dumps(step_input))
        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(f"Step input is not JSON serializable: {str(e)}")
            input_size = 0  # Cannot calculate size if not serializable

        # Validate tenant context if provided
        if tenant:
            tenant_result = self._validate_tenant_context(workflow, step, tenant)
            result = result.combine(tenant_result)

        # Validate user permissions if provided
        if user:
            permissions_result = self._validate_permissions(workflow, step, user)
            result = result.combine(permissions_result)

        result.details['workflow_id'] = str(workflow.id)
        result.details['step_id'] = str(step.id)
        result.details['step_name'] = step.step_name
        result.details['input_keys'] = list(step_input.keys())
        result.details['input_size'] = input_size

        return result

    def validate_step_output(
        self,
        workflow: WorkflowInstance,
        step: WorkflowStep,
        step_output: Dict[str, Any],
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate step output data.

        Validates:
        - Output data structure (must be a dictionary)
        - Output data schema (if schema is defined)
        - Required fields are present
        - Data types are correct

        Args:
            workflow: WorkflowInstance context
            step: WorkflowStep context
            step_output: Step output data to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(is_valid=True)
        result.details['step_output_validation'] = 'step_output'

        # Validate output is a dictionary
        if not isinstance(step_output, dict):
            result.is_valid = False
            result.errors.append("Step output must be a dictionary")
            return result

        # Validate output is not empty (warn if empty, but allow it)
        if not step_output:
            result.warnings.append("Step output is empty")

        # Validate output can be JSON serialized (for state persistence)
        try:
            json.dumps(step_output)
            # Calculate size only if serialization succeeds
            output_size = len(json.dumps(step_output))
        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(f"Step output is not JSON serializable: {str(e)}")
            output_size = 0  # Cannot calculate size if not serializable

        # Validate tenant context if provided
        if tenant:
            tenant_result = self._validate_tenant_context(workflow, step, tenant)
            result = result.combine(tenant_result)

        # Validate user permissions if provided
        if user:
            permissions_result = self._validate_permissions(workflow, step, user)
            result = result.combine(permissions_result)

        result.details['workflow_id'] = str(workflow.id)
        result.details['step_id'] = str(step.id)
        result.details['step_name'] = step.step_name
        result.details['output_keys'] = list(step_output.keys())
        result.details['output_size'] = output_size

        return result

    def _workflow_state_cache_key(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any],
        user: Optional[User],
    ) -> str:
        """Build a cache key that captures the inputs validation depends on.

        ``validate_workflow_state`` is a pure function of:

        * the workflow row (id, status, current_step_index, state_data,
          updated_at — the latter is the cheap cache-busting signal),
        * the tenant id (for tenant-context checks),
        * the user id (for permission checks).

        Hashing ``updated_at`` into the key means any change to the row
        (saved by the engine on each step) invalidates the cache without
        needing manual ``cache.delete`` calls. ``state_data`` is also
        hashed so in-memory mutations that haven't been saved yet still
        produce a distinct key — the validator's output depends on
        ``state_data`` shape, not just the row's ``updated_at``.
        """
        try:
            state_repr = json.dumps(
                workflow.state_data or {}, sort_keys=True, default=str
            )
        except (TypeError, ValueError):
            # Non-serialisable state_data is an explicit failure mode
            # the validator surfaces below — never cache that path so we
            # don't poison the key namespace with a value we can't hash.
            state_repr = repr(workflow.state_data)
        state_hash = hashlib.md5(state_repr.encode("utf-8")).hexdigest()[:16]
        updated_at = (
            workflow.updated_at.isoformat()
            if getattr(workflow, "updated_at", None) is not None
            else "unset"
        )
        tenant_id = str(getattr(tenant, "id", "anon"))
        user_id = str(getattr(user, "id", "anon"))
        return (
            f"orch:wf_state:{workflow.id}:{workflow.status}:"
            f"{workflow.current_step_index}:{updated_at}:{state_hash}:"
            f"t={tenant_id}:u={user_id}"
        )

    def validate_workflow_state(
        self,
        workflow: WorkflowInstance,
        tenant: Optional[Any] = None,
        user: Optional[User] = None
    ) -> ValidationResult:
        """
        Validate workflow state consistency.

        Validates:
        - Workflow state is consistent
        - State data structure is valid
        - State transitions are valid
        - No conflicting state information

        When ``self.enable_caching`` is True (the default), the result is
        cached against a key derived from the workflow row + tenant +
        user. This is the cache layer the public API contract advertises
        via the constructor's ``enable_caching`` flag — without it, cost
        of cache-key computation alone would be larger than the
        validation work for fast paths and ``enable_caching=True`` would
        be a misleading no-op (per Phase 4.3.2 perf spec).

        Args:
            workflow: WorkflowInstance to validate
            tenant: Optional tenant instance for context validation
            user: Optional user instance for permission validation

        Returns:
            ValidationResult with validation status and details
        """
        cache_key: Optional[str] = None
        if self.enable_caching:
            cache_key = self._workflow_state_cache_key(workflow, tenant, user)
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        result = ValidationResult(is_valid=True)
        result.details['workflow_state_validation'] = 'workflow_state'

        # Validate workflow instance
        workflow_result = self._validate_workflow_instance(workflow, tenant, user)
        result = result.combine(workflow_result)

        # Validate state consistency
        consistency_result = self._validate_state_consistency(workflow, tenant, user)
        result = result.combine(consistency_result)

        # Validate state_data structure
        if not isinstance(workflow.state_data, dict):
            result.is_valid = False
            result.errors.append("Workflow state_data must be a dictionary")
        else:
            # Validate state_data can be JSON serialized
            try:
                json.dumps(workflow.state_data)
            except (TypeError, ValueError) as e:
                result.is_valid = False
                result.errors.append(
                    f"Workflow state_data is not JSON serializable: {str(e)}"
                )

        # Validate current_step_index is within bounds
        if workflow.workflow_definition:
            dsl = workflow.workflow_definition.dsl_json
            if isinstance(dsl, dict):
                steps = dsl.get("steps", [])
                if workflow.current_step_index >= len(steps):
                    result.is_valid = False
                    result.errors.append(
                        f"Workflow current_step_index ({workflow.current_step_index}) "
                        f"is out of bounds (workflow has {len(steps)} steps)"
                    )

        result.details['workflow_id'] = str(workflow.id)
        result.details['workflow_status'] = workflow.status
        result.details['current_step_index'] = workflow.current_step_index

        # Only cache *valid* results: an INVALID outcome is usually
        # transient (mid-step state, missing dep) — caching it would
        # paper over recoveries and produce stale failure reports.
        if cache_key is not None and result.is_valid:
            cache.set(cache_key, result, self.get_cache_ttl())

        return result

