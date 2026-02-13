"""
Data Mesh Domain Creation Workflow

Orchestrates the data mesh domain creation process with proper error handling,
retry logic, and compensation. Manages domain validation, resource allocation,
policy application, and analytics initialization.
"""

from typing import Any, Dict, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from hub.apps.core.events.service_publishers import EventPublisher
from hub.apps.mesh.business_rules import DataMeshBusinessRules
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine

logger = structlog.get_logger(__name__)


class DataMeshWorkflow:
    """
    Data mesh domain creation workflow orchestrator.

    Manages the complete domain creation process:
    1. Validate domain configuration
    2. Allocate resources
    3. Create domain record
    4. Apply default policies
    5. Initialize analytics
    6. Complete workflow
    """

    WORKFLOW_NAME = "data_mesh"
    WORKFLOW_VERSION = "1.0.0"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the data mesh workflow definition.

        This method is idempotent - safe to call multiple times.
        The registry.register_workflow method handles checking for existing workflows.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                {"name": "validate_domain", "type": "task", "task": "data_mesh.validate_domain"},
                {
                    "name": "allocate_resources",
                    "type": "task",
                    "task": "data_mesh.allocate_resources",
                    "compensation": {
                        "type": "task",
                        "task": "data_mesh.rollback_resource_allocation",
                    },
                },
                {
                    "name": "create_domain",
                    "type": "task",
                    "task": "data_mesh.create_domain",
                    "compensation": {"type": "task", "task": "data_mesh.rollback_domain_creation"},
                },
                {
                    "name": "apply_default_policies",
                    "type": "task",
                    "task": "data_mesh.apply_default_policies",
                    "compensation": {
                        "type": "task",
                        "task": "data_mesh.rollback_policy_application",
                    },
                },
                {
                    "name": "initialize_analytics",
                    "type": "task",
                    "task": "data_mesh.initialize_analytics",
                },
                {"name": "audit_logging", "type": "task", "task": "data_mesh.audit_logging"},
                {"name": "complete", "type": "task", "task": "data_mesh.complete"},
            ],
            "compensation": {"enabled": True},
        }
        # Register workflow (idempotent - registry handles existing workflows)
        try:
            registry.register_workflow(
                workflow_name=cls.WORKFLOW_NAME,
                dsl_json=workflow_dsl,
                description="Orchestrates data mesh domain creation with policy application and analytics initialization",
                version=cls.WORKFLOW_VERSION,
            )
        except Exception as e:
            # If workflow registration fails with "already exists", that's OK - workflow exists
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                logger.debug(
                    f"Workflow {cls.WORKFLOW_NAME} version {cls.WORKFLOW_VERSION} already exists, continuing"
                )
                pass  # Workflow exists, which is fine
            else:
                # Re-raise other errors
                raise

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow tasks with the engine.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task("data_mesh.validate_domain", cls._validate_domain_task)
        engine.register_task("data_mesh.allocate_resources", cls._allocate_resources_task)
        engine.register_task(
            "data_mesh.rollback_resource_allocation", cls._rollback_resource_allocation_task
        )
        engine.register_task("data_mesh.create_domain", cls._create_domain_task)
        engine.register_task(
            "data_mesh.rollback_domain_creation", cls._rollback_domain_creation_task
        )
        engine.register_task("data_mesh.apply_default_policies", cls._apply_default_policies_task)
        engine.register_task(
            "data_mesh.rollback_policy_application", cls._rollback_policy_application_task
        )
        engine.register_task("data_mesh.initialize_analytics", cls._initialize_analytics_task)
        engine.register_task("data_mesh.audit_logging", cls._audit_logging_task)
        engine.register_task("data_mesh.complete", cls._complete_task)

    @staticmethod
    def _update_progress(instance: WorkflowInstance, progress: int, step_name: str) -> None:
        """
        Update workflow progress and publish custom data mesh event.

        Args:
            instance: Workflow instance
            progress: Progress percentage (0-100)
            step_name: Current step name
        """
        if instance.state_data is None:
            instance.state_data = {}
        instance.state_data["progress_percentage"] = progress
        instance.state_data["current_step_name"] = step_name
        instance.save(update_fields=["state_data"])

        # Publish custom data mesh workflow event
        try:
            tenant_id = instance.tenant_id
            user_id = instance.created_by_id

            event_publisher = EventPublisher(
                service_name="data_mesh_service",
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )

            # Calculate elapsed time if available
            elapsed_time_ms = None
            if instance.started_at:
                elapsed = timezone.now() - instance.started_at
                elapsed_time_ms = int(elapsed.total_seconds() * 1000)

            # Get total steps from workflow definition
            total_steps = len(instance.workflow_definition.dsl_json.get("steps", []))
            completed_steps = int((progress / 100.0) * total_steps) if total_steps > 0 else None

            event_publisher.publish(
                event_type="workflow.data_mesh.domain_creation.step_completed",
                data={
                    "workflow_instance_id": str(instance.id),
                    "step_name": step_name,
                    "progress_percentage": progress,
                    "total_steps": total_steps if total_steps > 0 else None,
                    "completed_steps": completed_steps,
                    "elapsed_time_ms": elapsed_time_ms,
                    "status": (
                        instance.status.value
                        if hasattr(instance.status, "value")
                        else str(instance.status)
                    ),
                },
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None,
            )
        except Exception as e:
            # Log but don't fail progress update if event publishing fails
            logger.warning(
                "Failed to publish data mesh workflow progress event",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True,
            )

    @staticmethod
    def _validate_domain_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Validate domain configuration.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        name = input_data.get("name")
        description = input_data.get("description")
        owner_id = input_data.get("owner_id")
        boundaries = input_data.get("boundaries")
        capabilities = input_data.get("capabilities")
        resource_quota = input_data.get("resource_quota")

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not name or not name.strip():
            raise ValueError("Domain name is required")

        from hub.apps.core.services.base import ValidationError
        from hub.apps.mesh.models import DataMeshDomain
        from hub.apps.tenants.models import Tenant

        # Validate tenant exists
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Check for duplicate domain name
        if DataMeshDomain.objects.filter(tenant_id=tenant_id, name=name.strip()).exists():
            raise ValueError(f"Domain with name '{name}' already exists for tenant")

        # Validate owner belongs to tenant if provided
        if owner_id:
            from hub.apps.users.models import User

            try:
                owner = User.objects.get(id=owner_id, tenant_id=tenant_id)
            except User.DoesNotExist:
                raise ValueError(f"Owner user {owner_id} not found or does not belong to tenant")

        # Validate boundaries structure if provided
        if boundaries:
            if not isinstance(boundaries, dict):
                raise ValueError("Boundaries must be a dictionary")
            if "data_products" in boundaries and not isinstance(boundaries["data_products"], list):
                raise ValueError("boundaries.data_products must be a list")
            if "schemas" in boundaries and not isinstance(boundaries["schemas"], list):
                raise ValueError("boundaries.schemas must be a list")
            if "access_patterns" in boundaries and not isinstance(
                boundaries["access_patterns"], list
            ):
                raise ValueError("boundaries.access_patterns must be a list")

        # Validate capabilities structure if provided
        if capabilities:
            if not isinstance(capabilities, dict):
                raise ValueError("Capabilities must be a dictionary")

        # Validate resource_quota structure if provided
        if resource_quota:
            if not isinstance(resource_quota, dict):
                raise ValueError("Resource quota must be a dictionary")
            for key, value in resource_quota.items():
                if not isinstance(value, (int, float)):
                    raise ValueError(f"Resource quota '{key}' must be a number")
                if value < 0:
                    raise ValueError(f"Resource quota '{key}' cannot be negative")

        # Validate domain configuration using DataMeshBusinessRules
        mesh_rules = DataMeshBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(owner_id) if owner_id else None,
        )

        # Create temporary domain object for validation (not saved yet)
        temp_domain = DataMeshDomain(
            tenant=tenant,
            name=name.strip(),
            description=description,
            owner_id=owner_id,
            boundaries=boundaries or {},
            capabilities=capabilities or {},
            resource_quota=resource_quota or {},
            status=DomainStatus.ACTIVE,
        )

        # Validate domain structure
        domain_structure_result = mesh_rules.validate_domain_structure(
            temp_domain, raise_on_error=False
        )
        if not domain_structure_result.is_valid:
            error_messages = domain_structure_result.errors
            raise ValueError(f"Domain structure validation failed: {'; '.join(error_messages)}")

        # Validate boundaries if provided
        if boundaries:
            boundaries_result = mesh_rules.validate_boundaries(boundaries, raise_on_error=False)
            if not boundaries_result.is_valid:
                error_messages = boundaries_result.errors
                raise ValueError(
                    f"Domain boundaries validation failed: {'; '.join(error_messages)}"
                )

        # Log validation warnings if any
        if domain_structure_result.warnings:
            logger.warning(
                "Domain structure validation warnings",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                warnings=domain_structure_result.warnings,
            )
        if boundaries and boundaries_result.warnings:
            logger.warning(
                "Domain boundaries validation warnings",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                warnings=boundaries_result.warnings,
            )

        # Store validated data in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["validated_name"] = name.strip()
        instance.state_data["validated_description"] = description
        instance.state_data["validated_owner_id"] = owner_id
        instance.state_data["validated_boundaries"] = boundaries or {}
        instance.state_data["validated_capabilities"] = capabilities or {}
        instance.state_data["validated_resource_quota"] = resource_quota or {}
        instance.save(update_fields=["state_data"])

        # Update progress (step 1 of 6 = ~17%)
        DataMeshWorkflow._update_progress(instance, 17, "validate_domain")

        logger.info(
            "Domain validation completed",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            domain_name=name,
        )

        # Return validated data so workflow engine can merge it into state_data
        return {
            "validated": True,
            "domain_name": name.strip(),
            "validated_name": name.strip(),
            "validated_description": description,
            "validated_owner_id": owner_id,
            "validated_boundaries": boundaries or {},
            "validated_capabilities": capabilities or {},
            "validated_resource_quota": resource_quota or {},
        }

    @staticmethod
    def _allocate_resources_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Allocate resources for the domain.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with allocated resources
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        resource_quota = (
            instance.state_data.get("validated_resource_quota")
            or input_data.get("resource_quota")
            or {}
        )

        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.core.services.base import ValidationError
        from hub.apps.governance.services import GovernanceService

        # Use GovernanceService to validate and allocate resources
        governance_service = GovernanceService(
            tenant_id=tenant_id,
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
        )

        # Validate resource quota allocation
        allocated_quota = {}
        if resource_quota:
            try:
                allocated_quota = governance_service.validate_resource_quota_allocation(
                    tenant_id=tenant_id, requested_quota=resource_quota
                )
            except ValidationError as e:
                logger.error(
                    "Resource quota allocation validation failed",
                    workflow_instance_id=str(instance.id),
                    tenant_id=tenant_id,
                    error=str(e),
                )
                raise ValueError(f"Resource quota allocation failed: {str(e)}")

        # Initialize resource usage tracking
        resource_usage = {}
        for key in allocated_quota.keys():
            resource_usage[f"{key}_used"] = 0

        # Store allocated resources in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["allocated_resource_quota"] = allocated_quota
        instance.state_data["resource_usage"] = resource_usage
        instance.save(update_fields=["state_data"])

        # Update progress (step 2 of 6 = ~33%)
        DataMeshWorkflow._update_progress(instance, 33, "allocate_resources")

        logger.info(
            "Resource allocation completed",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            allocated_quota=allocated_quota,
        )

        return {"allocated_quota": allocated_quota, "resource_usage": resource_usage}

    @staticmethod
    def _rollback_resource_allocation_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Rollback resource allocation (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        # Resource allocation is typically just validation, so rollback is a no-op
        # In a production system with actual resource allocation, this would release resources
        logger.info(
            "Resource allocation rollback completed (no-op)", workflow_instance_id=str(instance.id)
        )
        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _create_domain_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create domain record.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with domain_id
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data (lines 342-355)
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        # Also check input_data as fallback (workflow engine merges step output into state_data)
        name = (
            instance.state_data.get("validated_name") 
            or instance.state_data.get("domain_name")  # From validation step output
            or input_data.get("name")  # Fallback to original input
        )
        description = (
            instance.state_data.get("validated_description")
            or input_data.get("description")
        )
        owner_id = (
            instance.state_data.get("validated_owner_id")
            or input_data.get("owner_id")
        )
        boundaries = instance.state_data.get("validated_boundaries", {}) or input_data.get("boundaries", {})
        capabilities = instance.state_data.get("validated_capabilities", {}) or input_data.get("capabilities", {})
        allocated_quota = instance.state_data.get("allocated_resource_quota", {})
        resource_usage = instance.state_data.get("resource_usage", {})

        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not name:
            # Debug: log state_data to understand what's available
            logger.error(
                "Domain name not found in state_data",
                workflow_instance_id=str(instance.id),
                state_data_keys=list(instance.state_data.keys()) if instance.state_data else [],
                input_data_keys=list(input_data.keys()) if input_data else [],
            )
            raise ValueError("Domain name is required (from validation step)")

        from hub.apps.mesh.models import DataMeshDomain, DomainStatus
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        # Validate domain before creation using DataMeshBusinessRules
        mesh_rules = DataMeshBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(owner_id) if owner_id else None,
        )

        # Create temporary domain object for validation (not saved yet)
        temp_domain = DataMeshDomain(
            tenant=tenant,
            name=name,
            description=description,
            owner_id=owner_id,
            boundaries=boundaries,
            capabilities=capabilities,
            resource_quota=allocated_quota,
            resource_usage=resource_usage,
            status=DomainStatus.ACTIVE,
        )

        # Validate domain structure before creation
        domain_structure_result = mesh_rules.validate_domain_structure(
            temp_domain, raise_on_error=False
        )
        if not domain_structure_result.is_valid:
            error_messages = domain_structure_result.errors
            raise ValueError(f"Domain creation validation failed: {'; '.join(error_messages)}")

        # Log validation warnings if any
        if domain_structure_result.warnings:
            logger.warning(
                "Domain creation validation warnings",
                workflow_instance_id=str(instance.id),
                tenant_id=tenant_id,
                warnings=domain_structure_result.warnings,
            )

        # Create domain
        domain = DataMeshDomain.objects.create(
            tenant=tenant,
            name=name,
            description=description,
            owner_id=owner_id,
            boundaries=boundaries,
            capabilities=capabilities,
            resource_quota=allocated_quota,
            resource_usage=resource_usage,
            status=DomainStatus.ACTIVE,
        )

        # Validate created domain using DataMeshBusinessRules
        created_domain_validation_result = mesh_rules.validate_domain_structure(
            domain, raise_on_error=False
        )
        if not created_domain_validation_result.is_valid:
            error_messages = created_domain_validation_result.errors
            # Log errors but don't fail - domain is already created
            logger.warning(
                "Domain validation errors after creation",
                workflow_instance_id=str(instance.id),
                domain_id=str(domain.id),
                errors=error_messages,
            )
        elif created_domain_validation_result.warnings:
            logger.warning(
                "Domain validation warnings after creation",
                workflow_instance_id=str(instance.id),
                domain_id=str(domain.id),
                warnings=created_domain_validation_result.warnings,
            )

        # Store domain_id in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["domain_id"] = str(domain.id)
        instance.save(update_fields=["state_data"])

        # Update progress (step 3 of 7 = ~43%)
        DataMeshWorkflow._update_progress(instance, 43, "create_domain")

        logger.info(
            "Domain created",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            domain_id=str(domain.id),
            domain_name=name,
        )

        return {"domain_id": str(domain.id), "domain_name": domain.name, "status": domain.status}

    @staticmethod
    @transaction.atomic
    def _rollback_domain_creation_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Rollback domain creation (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        domain_id = instance.state_data.get("domain_id")

        if domain_id:
            try:
                from hub.apps.mesh.models import DataMeshDomain

                domain = DataMeshDomain.objects.get(id=domain_id)
                domain.delete()
                logger.info(
                    "Domain creation rolled back (domain deleted)",
                    workflow_instance_id=str(instance.id),
                    domain_id=domain_id,
                )
            except DataMeshDomain.DoesNotExist:
                logger.warning(
                    "Domain not found during rollback",
                    workflow_instance_id=str(instance.id),
                    domain_id=domain_id,
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _apply_default_policies_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Apply default policies to the domain.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with applied policies
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        # Get domain_id from state_data (from create_domain step output) with fallback
        domain_id = (
            instance.state_data.get("domain_id")
            or input_data.get("domain_id")  # Fallback to input_data
        )

        if not domain_id:
            # Debug: log state_data to understand what's available
            logger.error(
                "Domain ID not found in state_data",
                workflow_instance_id=str(instance.id),
                state_data_keys=list(instance.state_data.keys()) if instance.state_data else [],
                input_data_keys=list(input_data.keys()) if input_data else [],
            )
            raise ValueError("domain_id is required (from create_domain step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.governance.models import AccessPolicy
        from hub.apps.mesh.models import DataMeshDomain
        from hub.apps.mesh.services import DataMeshService

        domain = DataMeshDomain.objects.get(id=domain_id)

        # Get default policies for the tenant
        # Default policies are tenant-wide policies (asset and dataset are null) that should be applied to all domains
        from django.db.models import Q

        default_policies = AccessPolicy.objects.filter(
            tenant_id=tenant_id, enabled=True, asset__isnull=True, dataset__isnull=True
        ).order_by("priority")

        applied_policies = []
        failed_policies = []

        # Use DataMeshService to apply policies
        mesh_service = DataMeshService(
            tenant_id=tenant_id,
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
        )

        for policy in default_policies:
            try:
                policy_application = mesh_service.apply_policy(
                    domain_id=domain_id, policy_id=str(policy.id), tenant_id=tenant_id
                )
                applied_policies.append(
                    {
                        "policy_id": str(policy.id),
                        "policy_name": policy.name,
                        "application_id": str(policy_application.id),
                    }
                )
                logger.info(
                    "Default policy applied to domain",
                    workflow_instance_id=str(instance.id),
                    domain_id=domain_id,
                    policy_id=str(policy.id),
                    policy_name=policy.name,
                )
            except Exception as e:
                failed_policies.append(
                    {"policy_id": str(policy.id), "policy_name": policy.name, "error": str(e)}
                )
                logger.warning(
                    "Failed to apply default policy",
                    workflow_instance_id=str(instance.id),
                    domain_id=domain_id,
                    policy_id=str(policy.id),
                    error=str(e),
                )
                # Continue applying other policies even if one fails

        # Store applied policies in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["applied_policies"] = applied_policies
        instance.state_data["failed_policies"] = failed_policies
        instance.save(update_fields=["state_data"])

        # Update progress (step 4 of 6 = ~67%)
        DataMeshWorkflow._update_progress(instance, 67, "apply_default_policies")

        logger.info(
            "Default policies application completed",
            workflow_instance_id=str(instance.id),
            domain_id=domain_id,
            applied_count=len(applied_policies),
            failed_count=len(failed_policies),
        )

        return {"applied_policies": applied_policies, "failed_policies": failed_policies}

    @staticmethod
    @transaction.atomic
    def _rollback_policy_application_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Rollback policy application (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        applied_policies = instance.state_data.get("applied_policies", [])
        # Get domain_id from state_data (from create_domain step output) with fallback
        domain_id = (
            instance.state_data.get("domain_id")
            or input_data.get("domain_id")  # Fallback to input_data
        )

        if not domain_id:
            return {"rolled_back": True, "reason": "No domain_id in state"}

        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus

        # Revoke applied policies
        for policy_info in applied_policies:
            application_id = policy_info.get("application_id")
            if application_id:
                try:
                    policy_application = PolicyApplication.objects.get(
                        id=application_id, domain_id=domain_id
                    )
                    policy_application.status = PolicyApplicationStatus.REVOKED
                    policy_application.save(update_fields=["status"])
                    logger.info(
                        "Policy application revoked during rollback",
                        workflow_instance_id=str(instance.id),
                        domain_id=domain_id,
                        application_id=application_id,
                    )
                except PolicyApplication.DoesNotExist:
                    logger.warning(
                        "Policy application not found during rollback",
                        workflow_instance_id=str(instance.id),
                        application_id=application_id,
                    )

        logger.info(
            "Policy application rollback completed",
            workflow_instance_id=str(instance.id),
            domain_id=domain_id,
            revoked_count=len(applied_policies),
        )

        return {"rolled_back": True, "revoked_count": len(applied_policies)}

    @staticmethod
    def _initialize_analytics_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Initialize analytics for the domain.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with analytics initialization status
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        # Get domain_id from state_data (from create_domain step output) with fallback
        domain_id = (
            instance.state_data.get("domain_id")
            or input_data.get("domain_id")  # Fallback to input_data
        )

        if not domain_id:
            # Debug: log state_data to understand what's available
            logger.error(
                "Domain ID not found in state_data",
                workflow_instance_id=str(instance.id),
                state_data_keys=list(instance.state_data.keys()) if instance.state_data else [],
                input_data_keys=list(input_data.keys()) if input_data else [],
            )
            raise ValueError("domain_id is required (from create_domain step)")

        from hub.apps.mesh.models import DataMeshDomain

        domain = DataMeshDomain.objects.get(id=domain_id)

        # Initialize analytics tracking
        # In a production system, this would:
        # 1. Create analytics dashboard
        # 2. Set up metrics collection
        # 3. Configure monitoring alerts
        # 4. Initialize usage tracking

        # For now, we'll just mark analytics as initialized
        analytics_initialized = True

        # Store analytics status in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["analytics_initialized"] = analytics_initialized
        instance.save(update_fields=["state_data"])

        # Update progress (step 5 of 6 = ~83%)
        DataMeshWorkflow._update_progress(instance, 83, "initialize_analytics")

        logger.info(
            "Analytics initialization completed",
            workflow_instance_id=str(instance.id),
            domain_id=domain_id,
        )

        return {"analytics_initialized": analytics_initialized}

    @staticmethod
    def _complete_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Complete workflow and publish final events.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with completion status
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        # Get domain_id from state_data (from create_domain step output) with fallback
        domain_id = (
            instance.state_data.get("domain_id")
            or input_data.get("domain_id")  # Fallback to input_data
        )

        if not domain_id:
            # Debug: log state_data to understand what's available
            logger.error(
                "Domain ID not found in state_data",
                workflow_instance_id=str(instance.id),
                state_data_keys=list(instance.state_data.keys()) if instance.state_data else [],
                input_data_keys=list(input_data.keys()) if input_data else [],
            )
            raise ValueError("domain_id is required (from create_domain step)")

        from hub.apps.mesh.models import DataMeshDomain

        domain = DataMeshDomain.objects.get(id=domain_id)

        # Publish workflow.data_mesh.domain_creation.started event (if not already published)
        # This is typically published when workflow starts, but we ensure it's published here
        try:
            tenant_id_str = str(tenant_id) if tenant_id else None
            user_id_str = str(instance.created_by_id) if instance.created_by_id else None

            event_publisher = EventPublisher(
                service_name="data_mesh_service", tenant_id=tenant_id_str, user_id=user_id_str
            )

            # Calculate elapsed time
            elapsed_time_ms = None
            if instance.started_at:
                elapsed = timezone.now() - instance.started_at
                elapsed_time_ms = int(elapsed.total_seconds() * 1000)

            # Publish domain creation started event (if not already published)
            event_publisher.publish(
                event_type="workflow.data_mesh.domain_creation.started",
                data={
                    "workflow_instance_id": str(instance.id),
                    "domain_id": domain_id,
                    "domain_name": domain.name,
                    "tenant_id": tenant_id_str,
                },
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )

            # Publish domain creation completed event
            event_publisher.publish(
                event_type="workflow.data_mesh.domain_creation.completed",
                data={
                    "workflow_instance_id": str(instance.id),
                    "domain_id": domain_id,
                    "domain_name": domain.name,
                    "duration_ms": elapsed_time_ms,
                    "applied_policies_count": len(instance.state_data.get("applied_policies", [])),
                },
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(
                "Failed to publish data mesh workflow events",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True,
            )

        # Update progress (step 7 of 7 = 100%)
        DataMeshWorkflow._update_progress(instance, 100, "complete")

        # Store completion status in state_data
        instance.state_data = instance.state_data or {}
        instance.state_data["completed"] = True
        instance.state_data["completed_at"] = timezone.now().isoformat()
        instance.save(update_fields=["state_data"])

        logger.info(
            "Data mesh workflow completed",
            workflow_instance_id=str(instance.id),
            domain_id=domain_id,
            domain_name=domain.name,
        )

        return {"completed": True, "domain_id": domain_id, "domain_name": domain.name}

    @staticmethod
    def _audit_logging_task(
        input_data: Dict[str, Any], instance: WorkflowInstance, step
    ) -> Dict[str, Any]:
        """
        Create audit log entry for domain creation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit_event_id
        """
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        created_by_id = instance.created_by_id
        
        # Note: We don't refresh_from_db() here because:
        # 1. We're inside a transaction with select_for_update lock
        # 2. The workflow engine already merges step outputs into state_data
        # 3. Refreshing inside a locked transaction can cause deadlocks/timeouts
        # 4. The instance.state_data is already up-to-date from the workflow engine's merge
        # Get domain_id from state_data (from create_domain step output) with fallback
        domain_id = (
            instance.state_data.get("domain_id")
            or input_data.get("domain_id")  # Fallback to input_data
        )

        if not domain_id:
            # Debug: log state_data to understand what's available
            logger.error(
                "Domain ID not found in state_data",
                workflow_instance_id=str(instance.id),
                state_data_keys=list(instance.state_data.keys()) if instance.state_data else [],
                input_data_keys=list(input_data.keys()) if input_data else [],
            )
            raise ValueError("domain_id is required (from create_domain step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from django.contrib.auth import get_user_model

        from hub.apps.audit.utils import create_audit_event
        from hub.apps.mesh.models import DataMeshDomain
        from hub.apps.tenants.models import Tenant

        User = get_user_model()
        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=created_by_id) if created_by_id else None
        domain = DataMeshDomain.objects.get(id=domain_id)

        # Create audit event
        audit_details = {
            "domain_id": str(domain.id),
            "domain_name": domain.name,
            "status": domain.status,
            "owner_id": str(domain.owner_id) if domain.owner_id else None,
            "tenant_id": tenant_id,
            "has_boundaries": bool(domain.boundaries),
            "has_capabilities": bool(domain.capabilities),
            "has_resource_quota": bool(domain.resource_quota),
            "workflow_instance_id": str(instance.id),
        }

        if domain.boundaries:
            audit_details["boundaries_keys"] = list(domain.boundaries.keys())

        if domain.resource_quota:
            audit_details["resource_quota_keys"] = list(domain.resource_quota.keys())

        audit_event = create_audit_event(
            resource_type="DATA_MESH_DOMAIN",
            action="DOMAIN_CREATED",
            actor_user=created_by,
            tenant=tenant,
            resource_id=str(domain.id),
            result="SUCCESS",
            details=audit_details,
        )

        logger.info(
            "Audit log created",
            workflow_instance_id=str(instance.id),
            domain_id=domain_id,
            audit_event_id=str(audit_event.id),
        )

        return {"audit_event_id": str(audit_event.id), "domain_id": domain_id}

    @classmethod
    def execute(
        cls,
        tenant_id: str,
        name: str,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        boundaries: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
        created_by_id: Optional[str] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None,
    ) -> Dict[str, Any]:
        """
        Execute data mesh domain creation workflow.

        Args:
            tenant_id: Tenant ID
            name: Domain name (must be unique per tenant)
            description: Optional domain description
            owner_id: Optional owner user ID
            boundaries: Optional domain boundaries as JSON
            capabilities: Optional domain capabilities as JSON
            resource_quota: Optional resource quotas as JSON
            created_by_id: User ID who created the workflow
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Validate tenant exists before creating workflow instance
        from hub.apps.tenants.models import Tenant

        try:
            Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant matching query does not exist: {tenant_id}")

        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "name": name,
        }
        if description is not None:
            workflow_input["description"] = description
        if owner_id is not None:
            workflow_input["owner_id"] = owner_id
        if boundaries is not None:
            workflow_input["boundaries"] = boundaries
        if capabilities is not None:
            workflow_input["capabilities"] = capabilities
        if resource_quota is not None:
            workflow_input["resource_quota"] = resource_quota

        # Create workflow instance
        try:
            workflow_instance = engine.create_instance(
                workflow_name=cls.WORKFLOW_NAME,
                input_data=workflow_input,
                tenant_id=tenant_id,
                created_by_id=created_by_id,
            )
        except Exception as e:
            # Catch database integrity errors and convert to ValueError
            from django.db import IntegrityError

            if isinstance(e, IntegrityError) or "foreign key constraint" in str(e).lower():
                raise ValueError(f"Invalid tenant_id: {tenant_id}") from e
            raise

        # Publish workflow.data_mesh.domain_creation.started event
        try:
            tenant_id_str = str(tenant_id) if tenant_id else None
            user_id_str = str(created_by_id) if created_by_id else None

            event_publisher = EventPublisher(
                service_name="data_mesh_service", tenant_id=tenant_id_str, user_id=user_id_str
            )

            event_publisher.publish(
                event_type="workflow.data_mesh.domain_creation.started",
                data={
                    "workflow_instance_id": str(workflow_instance.id),
                    "domain_name": name,
                    "tenant_id": tenant_id_str,
                },
                tenant_id=tenant_id_str,
                user_id=user_id_str,
            )
        except Exception as e:
            logger.warning(
                "Failed to publish workflow.data_mesh.domain_creation.started event",
                workflow_instance_id=str(workflow_instance.id),
                error=str(e),
            )

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Data mesh workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                domain_id=workflow_instance.state_data.get("domain_id"),
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "domain_id": workflow_instance.state_data.get("domain_id"),
                "output_data": workflow_instance.output_data,
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"

            # Publish workflow.data_mesh.domain_creation.failed event
            try:
                tenant_id_str = str(tenant_id) if tenant_id else None
                user_id_str = str(created_by_id) if created_by_id else None

                event_publisher = EventPublisher(
                    service_name="data_mesh_service", tenant_id=tenant_id_str, user_id=user_id_str
                )

                event_publisher.publish(
                    event_type="workflow.data_mesh.domain_creation.failed",
                    data={
                        "workflow_instance_id": str(workflow_instance.id),
                        "error_message": error_message,
                        "domain_name": name,
                    },
                    tenant_id=tenant_id_str,
                    user_id=user_id_str,
                )
            except Exception as e:
                logger.warning(
                    "Failed to publish workflow.data_mesh.domain_creation.failed event",
                    workflow_instance_id=str(workflow_instance.id),
                    error=str(e),
                )

            logger.error(
                "Data mesh workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                error=error_message,
            )
            raise ValueError(f"Data mesh workflow failed: {error_message}")
