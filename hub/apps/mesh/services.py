"""
Data Mesh Service

Service layer for Data Mesh operations.
Provides business logic for domain management, policy applications, and compliance reporting.
"""
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from django.db import transaction
from django.utils import timezone

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError, ConflictError
from hub.apps.core.events.service_publishers import DataMeshEventPublisher
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
    PolicyApplication,
    PolicyApplicationStatus,
    ComplianceReport,
    MeshComplianceStatus,
)
from hub.apps.mesh.metrics import (
    mesh_domain_created_total,
    mesh_domain_updated_total,
    mesh_domain_deleted_total,
    mesh_domain_creation_duration_seconds,
    mesh_domain_update_duration_seconds,
    mesh_policy_applied_total,
    mesh_policy_revoked_total,
    mesh_policy_application_duration_seconds,
    mesh_compliance_check_duration_seconds,
    mesh_compliance_violations_total,
    mesh_compliance_checks_total,
    mesh_compliance_report_generated_total,
    mesh_topology_update_duration_seconds,
    mesh_topology_updates_total,
    mesh_topology_update_failures_total,
    mesh_domain_count,
    mesh_relationship_count,
    mesh_domain_health_status,
    mesh_domain_health_status_changes_total,
    mesh_domain_health_check_duration_seconds,
    get_tenant_id,
    get_domain_id,
)
import time

if TYPE_CHECKING:
    from hub.apps.orchestration.models import WorkflowInstance


class DataMeshService(BaseService, DataMeshEventPublisher):
    """
    Service for Data Mesh operations.

    Provides business logic for:
    - Domain creation and management
    - Policy application and management
    - Compliance reporting
    """

    service_name = "data_mesh_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize DataMeshService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        DataMeshEventPublisher.__init__(self)

    def get_domain(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
    ) -> DataMeshDomain:
        """
        Get domain by ID.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            DataMeshDomain instance

        Raises:
            NotFoundError: If domain not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_domain",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                DataMeshDomain,
                domain_id,
                tenant_id=effective_tenant_id,
            ),
        )

    def get_domains(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[DomainStatus] = None,
        owner_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[DataMeshDomain]:
        """
        Get domains with optional filtering.

        Args:
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            status: Optional status filter
            owner_id: Optional owner ID filter
            limit: Optional limit on results
            offset: Pagination offset

        Returns:
            List of DataMeshDomain instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_domains():
            queryset = DataMeshDomain.objects.filter(tenant_id=effective_tenant_id)

            if status:
                queryset = queryset.filter(status=status)

            if owner_id:
                queryset = queryset.filter(owner_id=owner_id)

            queryset = queryset.order_by("-created_at")

            if offset:
                queryset = queryset[offset:]

            if limit:
                queryset = queryset[:limit]

            return list(queryset)

        return self.execute_with_metrics(
            operation="get_domains",
            tenant_id=effective_tenant_id,
            func=_get_domains,
        )

    def _validate_boundaries(self, boundaries: Dict[str, Any]) -> None:
        """
        Validate domain boundaries structure and content.

        Args:
            boundaries: Boundaries dictionary to validate

        Raises:
            ValidationError: If boundaries are invalid
        """
        if not isinstance(boundaries, dict):
            raise ValidationError("Boundaries must be a dictionary")

        # Validate common boundary fields if present
        if "data_products" in boundaries:
            if not isinstance(boundaries["data_products"], list):
                raise ValidationError("boundaries.data_products must be a list")

        if "schemas" in boundaries:
            if not isinstance(boundaries["schemas"], list):
                raise ValidationError("boundaries.schemas must be a list")

        if "access_patterns" in boundaries:
            if not isinstance(boundaries["access_patterns"], list):
                raise ValidationError("boundaries.access_patterns must be a list")

    def _validate_resource_quota(self, resource_quota: Dict[str, Any]) -> None:
        """
        Validate resource quota structure and values.

        Args:
            resource_quota: Resource quota dictionary to validate

        Raises:
            ValidationError: If resource quota is invalid
        """
        if not isinstance(resource_quota, dict):
            raise ValidationError("Resource quota must be a dictionary")

        # Validate quota values are non-negative numbers
        for key, value in resource_quota.items():
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Resource quota '{key}' must be a number")
            if value < 0:
                raise ValidationError(f"Resource quota '{key}' cannot be negative")

    def _allocate_resource_quota(
        self,
        tenant_id: str,
        resource_quota: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Allocate resource quota for the domain.

        This method validates that the tenant has sufficient quota available
        and allocates resources for the domain. In a production system, this
        would interact with a quota management service.

        Args:
            tenant_id: Tenant ID
            resource_quota: Requested resource quota

        Returns:
            Allocated resource quota (may be adjusted based on tenant limits)

        Raises:
            ValidationError: If quota allocation fails
        """
        if not resource_quota:
            return {}

        # Validate quota structure
        self._validate_resource_quota(resource_quota)

        # In a real system, this would:
        # 1. Check tenant's total available quota
        # 2. Check tenant's current quota usage across all domains
        # 3. Validate that requested quota doesn't exceed available quota
        # 4. Allocate the quota

        # For now, we'll just validate and return the requested quota
        # Future enhancement: Integrate with tenant quota management service
        allocated_quota = resource_quota.copy()

        # Initialize resource_usage to track actual usage
        resource_usage = {}
        for key in allocated_quota.keys():
            resource_usage[f"{key}_used"] = 0

        return allocated_quota

    @transaction.atomic
    def create_domain(
        self,
        tenant_id: str,
        name: str,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        boundaries: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
        status: DomainStatus = DomainStatus.ACTIVE,
    ) -> DataMeshDomain:
        """
        Create a new data mesh domain using the orchestration workflow.

        This method delegates to the DataMeshWorkflow which orchestrates:
        - Domain validation
        - Resource quota allocation
        - Domain creation
        - Default policy application
        - Analytics initialization

        Args:
            tenant_id: Tenant ID
            name: Domain name (must be unique per tenant)
            description: Optional domain description
            owner_id: Optional owner user ID
            boundaries: Optional domain boundaries as JSON (data products, schemas, access patterns)
            capabilities: Optional domain capabilities as JSON (APIs, services, data products)
            resource_quota: Optional resource quotas as JSON (storage_gb, compute_hours, api_calls_per_day, etc.)
            status: Domain status (default: ACTIVE) - Note: workflow sets status to ACTIVE

        Returns:
            Created DataMeshDomain instance with workflow_instance linked

        Raises:
            ValidationError: If validation fails
            ConflictError: If domain name already exists for tenant
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        if not name or not name.strip():
            raise ValidationError("Domain name is required")

        # Execute workflow
        from hub.apps.orchestration.workflows.data_mesh import DataMeshWorkflow
        from hub.apps.orchestration.workflow_engine import WorkflowEngine
        from hub.apps.orchestration.registry import WorkflowRegistry

        # Create engine and registry
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        # Register workflow (idempotent - safe to call multiple times)
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug("Registering data mesh workflow before domain creation")
            DataMeshWorkflow.register_workflow(registry)
            logger.debug("Successfully registered data mesh workflow")
        except Exception as e:
            # If workflow registration fails, convert to appropriate error type
            import logging
            from django.core.exceptions import ValidationError as DjangoValidationError
            logger = logging.getLogger(__name__)
            error_msg = str(e)
            error_type = type(e).__name__
            logger.debug(f"Exception during workflow registration: {error_type}: {error_msg}")

            # Handle "already exists" errors - these are expected with idempotent registration
            if "already exists" in error_msg.lower():
                logger.debug("Workflow already exists (expected with idempotent registration), continuing")
                # Try to get the existing workflow to ensure it's registered
                try:
                    existing = registry.get_workflow("data_mesh", version="1.0.0")
                    if existing:
                        logger.debug(f"Confirmed workflow exists: {existing.id}")
                    else:
                        logger.warning("Workflow reported as existing but not found in registry - this is OK, workflow exists")
                except Exception as lookup_error:
                    logger.warning(f"Error looking up existing workflow: {lookup_error} - this is OK, workflow exists")
                # Continue - workflow exists, which is fine. Don't raise any error.
                pass
            # Handle ValidationError types (both Django and custom)
            elif isinstance(e, DjangoValidationError) or isinstance(e, ValidationError):
                # Re-raise other validation errors
                logger.error(f"Validation error during workflow registration: {error_msg}")
                raise ValidationError(f"Failed to register workflow: {error_msg}") from e
            # Handle RuntimeError (from registry when workflow can't be found)
            elif isinstance(e, RuntimeError) and "transaction isolation" in error_msg.lower():
                # This is a transient transaction isolation issue - workflow exists, just not visible yet
                logger.warning(f"Transaction isolation issue during workflow registration: {error_msg}. Continuing as workflow exists.")
                pass  # Don't raise - workflow exists, will be available shortly
            else:
                # Re-raise other errors
                logger.error(f"Unexpected error during workflow registration: {error_type}: {error_msg}")
                raise ValidationError(f"Failed to register workflow: {error_msg}") from e
        DataMeshWorkflow.register_tasks(engine)

        # Execute workflow with metrics tracking
        start_time = time.time()
        try:
            workflow_result = DataMeshWorkflow.execute(
                tenant_id=effective_tenant_id,
                name=name.strip(),
                description=description,
                owner_id=owner_id,
                boundaries=boundaries,
                capabilities=capabilities,
                resource_quota=resource_quota,
                created_by_id=self.user_id,
                engine=engine,
                registry=registry
            )
            creation_duration = time.time() - start_time
            creation_status = "success"
        except ValueError as e:
            # Convert ValueError to appropriate exception types
            creation_duration = time.time() - start_time
            creation_status = "failed"
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                raise ConflictError(error_msg) from e
            raise ValidationError(error_msg) from e
        except Exception as e:
            creation_duration = time.time() - start_time
            creation_status = "failed"
            raise

        # Get domain from workflow result
        domain_id = workflow_result.get("domain_id")
        if not domain_id:
            raise ValidationError("Workflow completed but domain_id not found in result")

        # Retrieve domain and link workflow instance
        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        # Link workflow instance to domain
        workflow_instance_id = workflow_result.get("workflow_instance_id")
        if workflow_instance_id:
            from hub.apps.orchestration.models import WorkflowInstance
            try:
                workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                domain.workflow_instance = workflow_instance
                domain.save(update_fields=['workflow_instance'])
            except WorkflowInstance.DoesNotExist:
                # Log warning but don't fail - workflow instance may have been deleted
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Workflow instance {workflow_instance_id} not found for domain {domain_id}",
                    extra={
                        "domain_id": domain_id,
                        "workflow_instance_id": workflow_instance_id
                    }
                )

        # Update status if different from default (workflow sets to ACTIVE)
        if status != DomainStatus.ACTIVE and domain.status != status:
            domain.status = status
            domain.save(update_fields=['status'])

        # Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        try:
            mesh_domain_created_total.labels(
                tenant_id=tenant_label,
                status=domain.status
            ).inc()

            mesh_domain_creation_duration_seconds.labels(
                tenant_id=tenant_label,
                status=creation_status
            ).observe(creation_duration)

            # Update domain count gauge
            mesh_domain_count.labels(
                tenant_id=tenant_label,
                status=domain.status
            ).inc(1)
        except Exception as e:
            # Log error but don't fail domain creation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to record metrics for domain creation {domain.id}: {e}",
                exc_info=True,
            )

        # Publish domain.created and mesh.domain.created events
        try:
            # Publish legacy domain.created event for backward compatibility
            self.publish_domain_created(
                domain_id=str(domain.id),
                name=domain.name,
                status=domain.status,
                owner_id=str(domain.owner_id) if domain.owner_id else None,
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
            # Publish mesh.domain.created event
            self.publish_mesh_domain_created(
                domain_id=str(domain.id),
                name=domain.name,
                status=domain.status,
                owner_id=str(domain.owner_id) if domain.owner_id else None,
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail domain creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to publish domain.created event for domain {domain.id}: {e}",
                exc_info=True,
            )

        return domain

    def get_domain_workflow_instance(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional['WorkflowInstance']:
        """
        Get workflow instance that created the domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            WorkflowInstance if found, None otherwise
        """
        domain = self.get_domain(domain_id, tenant_id=tenant_id)
        return domain.workflow_instance

    def get_domain_workflow_state(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get workflow state data for the domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Workflow state data dictionary if workflow instance exists, None otherwise
        """
        workflow_instance = self.get_domain_workflow_instance(domain_id, tenant_id=tenant_id)
        if workflow_instance:
            return workflow_instance.state_data
        return None

    def get_domain_workflow_status(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get workflow status for the domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Workflow status string if workflow instance exists, None otherwise
        """
        workflow_instance = self.get_domain_workflow_instance(domain_id, tenant_id=tenant_id)
        if workflow_instance:
            # Convert TextChoices to string value
            status = workflow_instance.status
            if hasattr(status, 'value'):
                return status.value
            return str(status)
        return None

    def get_domain_workflow_progress(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Get workflow progress percentage for the domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Progress percentage (0-100) if workflow instance exists, None otherwise
        """
        workflow_state = self.get_domain_workflow_state(domain_id, tenant_id=tenant_id)
        if workflow_state:
            return workflow_state.get("progress_percentage")
        return None

    @transaction.atomic
    def update_domain(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        owner_id: Optional[str] = None,
        boundaries: Optional[Dict[str, Any]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        resource_quota: Optional[Dict[str, Any]] = None,
        status: Optional[DomainStatus] = None,
        _owner_id_provided: bool = False,  # Internal flag to distinguish None from not provided
    ) -> DataMeshDomain:
        """
        Update an existing data mesh domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            name: Optional new domain name
            description: Optional new description
            owner_id: Optional new owner user ID
            boundaries: Optional new boundaries
            capabilities: Optional new capabilities
            resource_quota: Optional new resource quota
            status: Optional new status

        Returns:
            Updated DataMeshDomain instance

        Raises:
            NotFoundError: If domain not found
            ValidationError: If validation fails
            ConflictError: If new name conflicts with existing domain
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        # Track changes for event and metrics
        changes = {}
        previous_status = domain.status
        update_start_time = time.time()

        # Update fields if provided
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationError("Domain name cannot be empty")
            # Check for duplicate if name changed
            if name != domain.name:
                if DataMeshDomain.objects.filter(tenant_id=effective_tenant_id, name=name).exists():
                    raise ConflictError(f"Domain with name '{name}' already exists for tenant")
                changes["name"] = {"old": domain.name, "new": name}
                domain.name = name

        if description is not None:
            changes["description"] = {"old": domain.description, "new": description}
            domain.description = description

        # Handle owner_id: _owner_id_provided flag distinguishes None (remove) from not provided (don't change)
        # If owner_id is explicitly provided (not None), treat it as provided
        if owner_id is not None:
            _owner_id_provided = True

        if _owner_id_provided:
            if owner_id is None:
                # Explicitly remove owner
                changes["owner_id"] = {"old": str(domain.owner_id) if domain.owner_id else None, "new": None}
                domain.owner_id = None
            else:
                # Validate owner belongs to tenant
                from hub.apps.users.models import User
                try:
                    owner = User.objects.get(id=owner_id, tenant_id=effective_tenant_id)
                except User.DoesNotExist:
                    raise ValidationError(
                        f"Owner user {owner_id} not found or does not belong to tenant"
                    )
                changes["owner_id"] = {"old": str(domain.owner_id) if domain.owner_id else None, "new": str(owner_id)}
                domain.owner_id = owner_id

        if boundaries is not None:
            changes["boundaries"] = {"old": domain.boundaries, "new": boundaries}
            domain.boundaries = boundaries

        if capabilities is not None:
            changes["capabilities"] = {"old": domain.capabilities, "new": capabilities}
            domain.capabilities = capabilities

        if resource_quota is not None:
            changes["resource_quota"] = {"old": domain.resource_quota, "new": resource_quota}
            domain.resource_quota = resource_quota

        if status is not None and status != domain.status:
            changes["status"] = {"old": domain.status, "new": status}
            domain.status = status

        # Run model validation
        domain.full_clean()
        domain.save()

        # Create audit log for domain update
        if changes:
            try:
                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant
                from django.contrib.auth import get_user_model

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                actor_user = None
                if self.user_id:
                    try:
                        actor_user = User.objects.get(id=self.user_id, tenant_id=effective_tenant_id)
                    except User.DoesNotExist:
                        pass  # Continue without actor_user if not found

                # Check if ownership was transferred
                ownership_transferred = "owner_id" in changes

                # Create audit log for ownership transfer if applicable
                if ownership_transferred:
                    audit_details_ownership = {
                        "domain_id": str(domain.id),
                        "domain_name": domain.name,
                        "owner_id": str(domain.owner_id) if domain.owner_id else None,
                        "tenant_id": effective_tenant_id,
                        "previous_owner_id": changes["owner_id"]["old"],
                        "new_owner_id": changes["owner_id"]["new"],
                    }

                    create_audit_event(
                        resource_type="DATA_MESH_DOMAIN",
                        action="OWNERSHIP_TRANSFERRED",
                        actor_user=actor_user,
                        tenant=tenant_obj,
                        resource_id=str(domain.id),
                        result="SUCCESS",
                        details=audit_details_ownership,
                    )

                # Create audit log for general update
                audit_details = {
                    "domain_id": str(domain.id),
                    "domain_name": domain.name,
                    "status": domain.status,
                    "owner_id": str(domain.owner_id) if domain.owner_id else None,
                    "tenant_id": effective_tenant_id,
                    "changes": changes,
                    "previous_status": previous_status,
                    "new_status": domain.status,
                }

                create_audit_event(
                    resource_type="DATA_MESH_DOMAIN",
                    action="UPDATED",
                    actor_user=actor_user,
                    tenant=tenant_obj,
                    resource_id=str(domain.id),
                    result="SUCCESS",
                    details=audit_details,
                )
            except Exception as e:
                # Log error but don't fail domain update if audit logging fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to create audit log for domain update {domain.id}: {e}",
                    exc_info=True,
                )

        # Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        if changes:
            update_duration = time.time() - update_start_time
            try:
                mesh_domain_updated_total.labels(
                    tenant_id=tenant_label
                ).inc()

                mesh_domain_update_duration_seconds.labels(
                    tenant_id=tenant_label
                ).observe(update_duration)

                # Update domain count gauge if status changed
                if "status" in changes:
                    mesh_domain_count.labels(
                        tenant_id=tenant_label,
                        status=previous_status
                    ).dec(1)
                    mesh_domain_count.labels(
                        tenant_id=tenant_label,
                        status=domain.status
                    ).inc(1)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to record metrics for domain update {domain.id}: {e}",
                    exc_info=True,
                )

        # Publish event if there were changes
        if changes:
            try:
                # Publish both domain.updated and mesh.domain.updated events
                self.publish_domain_updated(
                    domain_id=str(domain.id),
                    changes=changes,
                    previous_status=previous_status,
                    new_status=domain.status,
                    tenant_id=effective_tenant_id,
                    user_id=self.user_id,
                )
                self.publish_mesh_domain_updated(
                    domain_id=str(domain.id),
                    changes=changes,
                    previous_status=previous_status,
                    new_status=domain.status,
                    tenant_id=effective_tenant_id,
                    user_id=self.user_id,
                )
            except Exception as e:
                # Log error but don't fail domain update
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to publish domain.updated event for domain {domain.id}: {e}",
                    exc_info=True,
                )

        return domain

    @transaction.atomic
    def delete_domain(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Delete a data mesh domain.

        Args:
            domain_id: Domain ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            reason: Optional reason for deletion

        Raises:
            NotFoundError: If domain not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        domain_id_str = str(domain.id)
        domain_name = domain.name
        owner_id_str = str(domain.owner_id) if domain.owner_id else None

        # Create audit log before deletion
        try:
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant
            from django.contrib.auth import get_user_model

            User = get_user_model()
            tenant_obj = Tenant.objects.get(id=effective_tenant_id)
            actor_user = None
            if self.user_id:
                try:
                    actor_user = User.objects.get(id=self.user_id, tenant_id=effective_tenant_id)
                except User.DoesNotExist:
                    pass  # Continue without actor_user if not found

            audit_details = {
                "domain_id": domain_id_str,
                "domain_name": domain_name,
                "owner_id": owner_id_str,
                "tenant_id": effective_tenant_id,
                "status": domain.status,
                "reason": reason,
            }

            create_audit_event(
                resource_type="DATA_MESH_DOMAIN",
                action="DELETED",
                actor_user=actor_user,
                tenant=tenant_obj,
                resource_id=domain_id_str,
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log error but don't fail deletion if audit logging fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to create audit log for domain deletion {domain_id_str}: {e}",
                exc_info=True,
            )

        # Record metrics before deletion
        tenant_label = get_tenant_id(effective_tenant_id)
        try:
            mesh_domain_deleted_total.labels(
                tenant_id=tenant_label,
                reason=reason or "no_reason"
            ).inc()

            # Decrease domain count gauge
            mesh_domain_count.labels(
                tenant_id=tenant_label,
                status=domain.status
            ).dec(1)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to record metrics for domain deletion {domain_id_str}: {e}",
                exc_info=True,
            )

        # Delete domain (cascade will handle related objects)
        domain.delete()

        # Publish event
        try:
            self.publish_domain_deleted(
                domain_id=domain_id_str,
                reason=reason or "",
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail deletion
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to publish domain.deleted event for domain {domain_id_str}: {e}",
                exc_info=True,
            )

    @transaction.atomic
    def apply_policy(
        self,
        domain_id: str,
        policy_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> PolicyApplication:
        """
        Apply a policy to a data mesh domain.

        This method performs comprehensive validation, policy application with overrides,
        compliance checking, and event publishing for policy application.

        Args:
            domain_id: Domain ID
            policy_id: Policy ID to apply
            overrides: Optional policy overrides as JSON (conditions, effect, priority, etc.)
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Created PolicyApplication instance

        Raises:
            NotFoundError: If domain or policy not found
            ValidationError: If validation fails (policy disabled, domain inactive, tenant mismatch, invalid overrides)
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        import logging
        logger = logging.getLogger(__name__)

        # 1. Validate and get domain
        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        # 2. Validate domain is active
        if domain.status != DomainStatus.ACTIVE:
            raise ValidationError(
                f"Domain must be ACTIVE to apply policies. Current status: {domain.status}"
            )

        # 3. Validate and get policy
        from hub.apps.governance.models import AccessPolicy
        try:
            policy = AccessPolicy.objects.get(id=policy_id, tenant_id=effective_tenant_id)
        except AccessPolicy.DoesNotExist:
            raise NotFoundError(f"Policy with id '{policy_id}' not found")

        # 4. Validate policy is enabled
        if not policy.enabled:
            raise ValidationError(
                f"Policy '{policy.name}' is disabled and cannot be applied"
            )

        # 5. Validate domain and policy belong to same tenant
        if policy.tenant_id != domain.tenant_id:
            raise ValidationError(
                f"Policy must belong to the same tenant as the domain. "
                f"Policy tenant: {policy.tenant_id}, Domain tenant: {domain.tenant_id}"
            )

        # 6. Validate overrides structure
        overrides_dict = overrides or {}
        if not isinstance(overrides_dict, dict):
            raise ValidationError("Overrides must be a dictionary")

        # Track policy application start time for metrics
        policy_application_start_time = time.time()

        # 7. Validate applied_by user if provided
        applied_by_user = None
        if self.user_id:
            from hub.apps.users.models import User
            try:
                applied_by_user = User.objects.get(id=self.user_id, tenant_id=effective_tenant_id)
            except User.DoesNotExist:
                logger.warning(
                    f"User {self.user_id} not found for policy application, "
                    f"continuing without applied_by",
                    extra={
                        "user_id": self.user_id,
                        "tenant_id": effective_tenant_id,
                        "domain_id": str(domain.id),
                        "policy_id": str(policy.id)
                    }
                )
                # Continue without applied_by_user if not found (nullable field)

        # 8. Create PolicyApplication record
        policy_application = PolicyApplication(
            domain=domain,
            policy=policy,
            applied_by=applied_by_user,
            overrides=overrides_dict,
            status=PolicyApplicationStatus.APPLIED,
        )

        # Run model validation (includes tenant validation)
        policy_application.full_clean()
        policy_application.save()

        # 9. Check compliance (create or update compliance report)
        try:
            self._check_compliance_for_domain(domain, policy_application)
        except Exception as e:
            # Log compliance check error but don't fail policy application
            logger.warning(
                f"Compliance check failed for policy application {policy_application.id}: {e}",
                extra={
                    "policy_application_id": str(policy_application.id),
                    "domain_id": str(domain.id),
                    "policy_id": str(policy.id),
                    "tenant_id": effective_tenant_id
                },
                exc_info=True
            )

        # 10. Create audit log
        try:
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant
            from django.contrib.auth import get_user_model

            User = get_user_model()
            tenant_obj = Tenant.objects.get(id=effective_tenant_id)

            audit_details = {
                "policy_application_id": str(policy_application.id),
                "domain_id": str(domain.id),
                "domain_name": domain.name,
                "policy_id": str(policy.id),
                "policy_name": policy.name,
                "applied_by_id": str(applied_by_user.id) if applied_by_user else None,
                "tenant_id": effective_tenant_id,
                "overrides": overrides_dict,
                "status": policy_application.status,
            }

            create_audit_event(
                resource_type="DATA_MESH_POLICY",
                action="APPLIED",
                actor_user=applied_by_user,
                tenant=tenant_obj,
                resource_id=str(policy_application.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log error but don't fail policy application if audit logging fails
            logger.warning(
                f"Failed to create audit log for policy application {policy_application.id}: {e}",
                exc_info=True,
            )

        # 11. Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        domain_label = get_domain_id(str(domain.id))
        policy_application_duration = time.time() - policy_application_start_time
        try:
            mesh_policy_applied_total.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                policy_id=str(policy.id),
                status=policy_application.status
            ).inc()

            mesh_policy_application_duration_seconds.labels(
                tenant_id=tenant_label,
                status=policy_application.status
            ).observe(policy_application_duration)
        except Exception as e:
            logger.warning(
                f"Failed to record metrics for policy application {policy_application.id}: {e}",
                exc_info=True,
            )

        # 12. Publish event
        try:
            # Publish both policy.applied and mesh.policy.applied events
            self.publish_policy_applied(
                policy_application_id=str(policy_application.id),
                domain_id=str(domain.id),
                policy_id=str(policy.id),
                status=policy_application.status,
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
            self.publish_mesh_policy_applied(
                policy_application_id=str(policy_application.id),
                domain_id=str(domain.id),
                policy_id=str(policy.id),
                status=policy_application.status,
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail policy application
            logger.error(
                f"Failed to publish policy.applied event for application {policy_application.id}: {e}",
                exc_info=True,
            )

        return policy_application

    def _check_compliance_for_domain(
        self,
        domain: DataMeshDomain,
        policy_application: PolicyApplication
    ) -> Optional[ComplianceReport]:
        """
        Check compliance for a domain after policy application.

        This method creates or updates a compliance report for the domain
        based on the applied policy and domain state.

        Args:
            domain: DataMeshDomain instance
            policy_application: PolicyApplication instance

        Returns:
            ComplianceReport instance or None if no report needed
        """
        # Get all applied policies for the domain
        applied_policies = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # Check if domain has any violations
        violations = []
        compliance_status = MeshComplianceStatus.COMPLIANT

        # Basic compliance check: ensure domain is active and has valid policies
        if domain.status != DomainStatus.ACTIVE:
            violations.append({
                "type": "DOMAIN_INACTIVE",
                "severity": "HIGH",
                "description": f"Domain {domain.name} is not active",
                "policy_application_id": str(policy_application.id)
            })
            compliance_status = MeshComplianceStatus.NON_COMPLIANT

        # Check if any applied policies are disabled
        for app in applied_policies:
            if app.policy and not app.policy.enabled:
                violations.append({
                    "type": "POLICY_DISABLED",
                    "severity": "MEDIUM",
                    "description": f"Applied policy {app.policy.name} is disabled",
                    "policy_application_id": str(app.id),
                    "policy_id": str(app.policy.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

        # Create or update compliance report
        compliance_report, created = ComplianceReport.objects.update_or_create(
            domain=domain,
            asset=None,  # Domain-level report
            defaults={
                "compliance_status": compliance_status,
                "violations": {"items": violations} if violations else {}
            }
        )

        return compliance_report

    @transaction.atomic
    def revoke_policy(
        self,
        policy_application_id: str,
        reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> PolicyApplication:
        """
        Revoke a policy application from a data mesh domain.

        This method revokes an applied policy, updates compliance, and publishes events.

        Args:
            policy_application_id: Policy application ID to revoke
            reason: Optional reason for revocation
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Updated PolicyApplication instance with status REVOKED

        Raises:
            NotFoundError: If policy application not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        import logging
        logger = logging.getLogger(__name__)

        # 1. Get policy application
        try:
            policy_application = PolicyApplication.objects.select_related(
                'domain', 'policy', 'applied_by'
            ).get(id=policy_application_id, domain__tenant_id=effective_tenant_id)
        except PolicyApplication.DoesNotExist:
            raise NotFoundError(f"Policy application with id '{policy_application_id}' not found")

        domain = policy_application.domain
        policy = policy_application.policy

        # 2. Validate policy application can be revoked
        if policy_application.status == PolicyApplicationStatus.REVOKED:
            raise ValidationError(
                f"Policy application {policy_application_id} is already revoked"
            )

        # 3. Get revoking user if provided
        revoked_by_user = None
        if self.user_id:
            from hub.apps.users.models import User
            try:
                revoked_by_user = User.objects.get(id=self.user_id, tenant_id=effective_tenant_id)
            except User.DoesNotExist:
                logger.warning(
                    f"User {self.user_id} not found for policy revocation, "
                    f"continuing without revoked_by",
                    extra={
                        "user_id": self.user_id,
                        "tenant_id": effective_tenant_id,
                        "policy_application_id": str(policy_application.id)
                    }
                )

        # 4. Update policy application status to REVOKED
        previous_status = policy_application.status
        policy_application.status = PolicyApplicationStatus.REVOKED
        policy_application.full_clean()
        policy_application.save()

        # 5. Update compliance report
        try:
            self._check_compliance_for_domain(domain, policy_application)
        except Exception as e:
            # Log compliance check error but don't fail revocation
            logger.warning(
                f"Compliance check failed for policy revocation {policy_application.id}: {e}",
                extra={
                    "policy_application_id": str(policy_application.id),
                    "domain_id": str(domain.id),
                    "tenant_id": effective_tenant_id
                },
                exc_info=True
            )

        # 6. Create audit log
        try:
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.tenants.models import Tenant
            from django.contrib.auth import get_user_model

            User = get_user_model()
            tenant_obj = Tenant.objects.get(id=effective_tenant_id)

            audit_details = {
                "policy_application_id": str(policy_application.id),
                "domain_id": str(domain.id),
                "domain_name": domain.name,
                "policy_id": str(policy.id) if policy else None,
                "policy_name": policy.name if policy else "Unknown Policy",
                "applied_by_id": str(policy_application.applied_by.id) if policy_application.applied_by else None,
                "revoked_by_id": str(revoked_by_user.id) if revoked_by_user else None,
                "tenant_id": effective_tenant_id,
                "previous_status": previous_status,
                "reason": reason,
                "status": policy_application.status,
            }

            create_audit_event(
                resource_type="DATA_MESH_POLICY",
                action="REMOVED",
                actor_user=revoked_by_user,
                tenant=tenant_obj,
                resource_id=str(policy_application.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log error but don't fail policy revocation if audit logging fails
            logger.warning(
                f"Failed to create audit log for policy revocation {policy_application.id}: {e}",
                exc_info=True,
            )

        # 7. Publish event
        try:
            self.publish_policy_revoked(
                policy_application_id=str(policy_application.id),
                domain_id=str(domain.id),
                policy_id=str(policy.id) if policy else None,
                reason=reason or "No reason provided",
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail policy revocation
            logger.error(
                f"Failed to publish policy.revoked event for application {policy_application.id}: {e}",
                exc_info=True,
            )

        return policy_application

    @transaction.atomic
    def check_compliance(
        self,
        domain_id: str,
        tenant_id: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> ComplianceReport:
        """
        Check compliance for a data mesh domain.

        This method performs comprehensive compliance checking by:
        1. Retrieving all applied policies for the domain
        2. Validating assets within the domain (if applicable)
        3. Flagging violations based on policy rules
        4. Generating a compliance report

        Args:
            domain_id: Domain ID to check compliance for
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            asset_id: Optional asset ID for asset-specific compliance check

        Returns:
            ComplianceReport instance with compliance status and violations

        Raises:
            NotFoundError: If domain not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        import logging
        logger = logging.getLogger(__name__)

        # 1. Get domain
        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        # Track compliance check start time for metrics
        compliance_check_start_time = time.time()

        # 2. Get asset if provided
        asset = None
        if asset_id:
            from hub.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
            except Asset.DoesNotExist:
                raise NotFoundError(f"Asset with id '{asset_id}' not found")

        # 3. Retrieve all applied policies for the domain
        applied_policies = PolicyApplication.objects.filter(
            domain=domain,
            status=PolicyApplicationStatus.APPLIED
        ).select_related('policy')

        # 4. Initialize violations list and compliance status
        violations = []
        compliance_status = MeshComplianceStatus.COMPLIANT

        # 5. Check domain-level compliance
        if domain.status != DomainStatus.ACTIVE:
            violations.append({
                "type": "DOMAIN_INACTIVE",
                "severity": "HIGH",
                "description": f"Domain {domain.name} is not active",
                "domain_id": str(domain.id)
            })
            compliance_status = MeshComplianceStatus.NON_COMPLIANT

        # 6. Check policy compliance
        for policy_app in applied_policies:
            policy = policy_app.policy
            if not policy:
                violations.append({
                    "type": "POLICY_MISSING",
                    "severity": "MEDIUM",
                    "description": f"Policy application {policy_app.id} references missing policy",
                    "policy_application_id": str(policy_app.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL
                continue

            # Check if policy is enabled
            if not policy.enabled:
                violations.append({
                    "type": "POLICY_DISABLED",
                    "severity": "MEDIUM",
                    "description": f"Applied policy {policy.name} is disabled",
                    "policy_application_id": str(policy_app.id),
                    "policy_id": str(policy.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

            # Check policy expiration (if applicable)
            if hasattr(policy_app, 'expires_at') and policy_app.expires_at:
                from django.utils import timezone
                if policy_app.expires_at < timezone.now():
                    violations.append({
                        "type": "POLICY_EXPIRED",
                        "severity": "HIGH",
                        "description": f"Policy {policy.name} has expired",
                        "policy_application_id": str(policy_app.id),
                        "policy_id": str(policy.id),
                        "expires_at": policy_app.expires_at.isoformat()
                    })
                    compliance_status = MeshComplianceStatus.NON_COMPLIANT

        # 7. Validate assets if asset_id provided or check domain assets
        if asset:
            # Asset-specific compliance check
            # Check asset status
            if asset.status not in ["ACTIVE", "PUBLIC"]:
                violations.append({
                    "type": "ASSET_INACTIVE",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} is not active or public",
                    "asset_id": str(asset.id),
                    "asset_status": asset.status
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

            # Check asset compliance status
            if asset.compliance_status == "FAIL":
                violations.append({
                    "type": "ASSET_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Asset {asset.name} has compliance failures",
                    "asset_id": str(asset.id)
                })
                compliance_status = MeshComplianceStatus.NON_COMPLIANT
            elif asset.compliance_status == "WARN":
                violations.append({
                    "type": "ASSET_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Asset {asset.name} has compliance warnings",
                    "asset_id": str(asset.id)
                })
                if compliance_status == MeshComplianceStatus.COMPLIANT:
                    compliance_status = MeshComplianceStatus.PARTIAL

        else:
            # Domain-level asset validation: check all assets in domain
            from hub.apps.assets.models import Asset
            domain_assets = Asset.objects.filter(
                tenant_id=effective_tenant_id,
                domain=domain.name  # Assets have domain as string field
            )

            # Check for assets with compliance issues
            failed_assets = domain_assets.filter(compliance_status="FAIL")
            if failed_assets.exists():
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_FAIL",
                    "severity": "HIGH",
                    "description": f"Domain has {failed_assets.count()} assets with compliance failures",
                    "failed_asset_count": failed_assets.count(),
                    "failed_asset_ids": [str(a.id) for a in failed_assets[:10]]  # Limit to first 10
                })
                compliance_status = MeshComplianceStatus.NON_COMPLIANT

            warned_assets = domain_assets.filter(compliance_status="WARN")
            if warned_assets.exists() and compliance_status == MeshComplianceStatus.COMPLIANT:
                violations.append({
                    "type": "DOMAIN_ASSETS_COMPLIANCE_WARN",
                    "severity": "MEDIUM",
                    "description": f"Domain has {warned_assets.count()} assets with compliance warnings",
                    "warned_asset_count": warned_assets.count()
                })
                compliance_status = MeshComplianceStatus.PARTIAL

        # 8. Create or update compliance report
        # Store violations in format expected by get_violation_count()
        violations_dict = {}
        if violations:
            violations_dict = {"items": violations}

        compliance_report, created = ComplianceReport.objects.update_or_create(
            domain=domain,
            asset=asset,
            defaults={
                "compliance_status": compliance_status,
                "violations": violations_dict
            }
        )

        # 9. Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        domain_label = get_domain_id(str(domain.id))
        compliance_check_duration = time.time() - compliance_check_start_time
        # Convert compliance status to string if it's a TextChoices instance
        if hasattr(compliance_status, 'value'):
            compliance_status_str = compliance_status.value
        elif hasattr(compliance_status, '__str__'):
            compliance_status_str = str(compliance_status)
        else:
            compliance_status_str = compliance_status if isinstance(compliance_status, str) else str(compliance_status)

        try:
            mesh_compliance_checks_total.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                compliance_status=compliance_status_str
            ).inc()

            mesh_compliance_check_duration_seconds.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                compliance_status=compliance_status_str
            ).observe(compliance_check_duration)

            # Record violations
            for violation in violations:
                violation_type = violation.get("type", "UNKNOWN")
                severity = violation.get("severity", "UNKNOWN")
                mesh_compliance_violations_total.labels(
                    tenant_id=tenant_label,
                    domain_id=domain_label,
                    violation_type=violation_type,
                    severity=severity
                ).inc()

            # Record compliance report generation
            mesh_compliance_report_generated_total.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                compliance_status=compliance_status_str
            ).inc()
        except Exception as e:
            logger.warning(
                f"Failed to record metrics for compliance check {domain.id}: {e}",
                exc_info=True,
            )

        # 10. Publish compliance.checked event
        try:
            from django.utils import timezone
            # Publish both mesh.compliance.checked events
            self.publish_mesh_compliance_checked(
                domain_id=str(domain.id),
                compliance_status=compliance_status_str,
                violation_count=len(violations),
                checked_at=timezone.now().isoformat(),
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail compliance check
            logger.warning(
                f"Failed to publish compliance.checked event for domain {domain.id}: {e}",
                exc_info=True,
            )

        # 11. Publish compliance.report.generated event
        try:
            self.publish_compliance_report_generated(
                compliance_report_id=str(compliance_report.id),
                domain_id=str(domain.id),
                compliance_status=compliance_status_str,
                asset_id=str(asset.id) if asset else None,
                violation_count=len(violations),
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail compliance check
            logger.warning(
                f"Failed to publish compliance.report.generated event for domain {domain.id}: {e}",
                exc_info=True,
            )

        return compliance_report

    def get_topology(
        self,
        tenant_id: Optional[str] = None,
        include_health_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Get data mesh topology for a tenant.

        This method generates a comprehensive topology view including:
        1. All domains in the tenant
        2. Relationships between domains (based on shared assets, policies, etc.)
        3. Health metrics for each domain
        4. Overall topology graph structure

        Args:
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            include_health_metrics: Whether to include health metrics (default: True)

        Returns:
            Dictionary containing topology graph with nodes (domains) and edges (relationships),
            health metrics, and summary statistics

        Raises:
            ValidationError: If tenant_id is required but not provided
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        import logging
        logger = logging.getLogger(__name__)

        # Track topology update start time for metrics
        topology_update_start_time = time.time()

        # 1. Retrieve all domains for the tenant
        domains = DataMeshDomain.objects.filter(
            tenant_id=effective_tenant_id
        ).select_related('owner', 'tenant').prefetch_related(
            'policy_applications',
            'compliance_reports'
        )

        # 2. Build domain nodes
        nodes = []
        domain_map = {}  # Map domain_id to index in nodes list

        for idx, domain in enumerate(domains):
            node = {
                "id": str(domain.id),
                "name": domain.name,
                "description": domain.description,
                "status": domain.status,
                "owner_id": str(domain.owner.id) if domain.owner else None,
                "created_at": domain.created_at.isoformat() if domain.created_at else None,
            }

            # Add health metrics if requested
            if include_health_metrics:
                # Get policy count
                policy_count = domain.policy_applications.filter(
                    status=PolicyApplicationStatus.APPLIED
                ).count()

                # Get latest compliance report
                latest_compliance = domain.compliance_reports.order_by('-generated_at').first()
                compliance_status = latest_compliance.compliance_status if latest_compliance else MeshComplianceStatus.UNKNOWN
                violation_count = latest_compliance.get_violation_count() if latest_compliance else 0

                # Calculate health score (0-100)
                health_score = 100
                if domain.status != DomainStatus.ACTIVE:
                    health_score -= 30
                if compliance_status == MeshComplianceStatus.NON_COMPLIANT:
                    health_score -= 40
                elif compliance_status == MeshComplianceStatus.PARTIAL:
                    health_score -= 20
                if violation_count > 0:
                    health_score -= min(10 * violation_count, 30)  # Max 30 points deduction
                health_score = max(0, health_score)  # Ensure non-negative

                node["health_metrics"] = {
                    "health_score": health_score,
                    "policy_count": policy_count,
                    "compliance_status": compliance_status,
                    "violation_count": violation_count,
                    "is_active": domain.status == DomainStatus.ACTIVE,
                }

            nodes.append(node)
            domain_map[str(domain.id)] = idx

        # 3. Calculate relationships between domains
        edges = []
        from hub.apps.assets.models import Asset

        # For each domain, find related domains through shared policies
        for domain in domains:
            for other_domain in domains:
                if other_domain.id == domain.id:
                    continue

                # Check if domains share policies (simplified check)
                domain_policies = set(
                    domain.policy_applications.filter(
                        status=PolicyApplicationStatus.APPLIED
                    ).values_list('policy_id', flat=True)
                )
                other_policies = set(
                    other_domain.policy_applications.filter(
                        status=PolicyApplicationStatus.APPLIED
                    ).values_list('policy_id', flat=True)
                )

                if domain_policies & other_policies:  # Shared policies
                    source_idx = domain_map.get(str(domain.id))
                    target_idx = domain_map.get(str(other_domain.id))
                    if source_idx is not None and target_idx is not None:
                        edges.append({
                            "source": str(domain.id),
                            "target": str(other_domain.id),
                            "type": "SHARED_POLICY",
                            "weight": len(domain_policies & other_policies)
                        })

        # 4. Build topology graph
        from django.utils import timezone
        topology = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "tenant_id": effective_tenant_id,
                "domain_count": len(nodes),
                "relationship_count": len(edges),
                "generated_at": timezone.now().isoformat(),
            }
        }

        # 5. Calculate summary statistics
        summary = {
            "total_domains": len(nodes),
            "active_domains": sum(1 for n in nodes if n.get("status") == DomainStatus.ACTIVE),
            "total_relationships": len(edges),
            "average_health_score": sum(
                n.get("health_metrics", {}).get("health_score", 0) for n in nodes
            ) / len(nodes) if nodes and include_health_metrics else None,
        }

        topology["summary"] = summary

        # 6. Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        topology_update_duration = time.time() - topology_update_start_time
        try:
            mesh_topology_updates_total.labels(
                tenant_id=tenant_label
            ).inc()

            mesh_topology_update_duration_seconds.labels(
                tenant_id=tenant_label
            ).observe(topology_update_duration)

            # Update domain and relationship count gauges
            for node in nodes:
                node_status = node.get("status", "UNKNOWN")
                mesh_domain_count.labels(
                    tenant_id=tenant_label,
                    status=node_status
                ).set(len([n for n in nodes if n.get("status") == node_status]))

            mesh_relationship_count.labels(
                tenant_id=tenant_label
            ).set(len(edges))
        except Exception as e:
            logger.warning(
                f"Failed to record metrics for topology update {effective_tenant_id}: {e}",
                exc_info=True,
            )

        # 7. Publish topology.updated event
        try:
            from django.utils import timezone
            self.publish_topology_updated(
                tenant_id=effective_tenant_id,
                domain_count=len(nodes),
                relationship_count=len(edges),
                updated_at=timezone.now().isoformat(),
                user_id=self.user_id,
            )
        except Exception as e:
            # Log error but don't fail topology generation
            logger.warning(
                f"Failed to publish topology.updated event for tenant {effective_tenant_id}: {e}",
                exc_info=True,
            )

        return topology

    def update_domain_health_status(
        self,
        domain_id: str,
        health_status: str,
        health_metrics: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Update domain health status and record metrics.

        This is a helper method that can be called by health check services
        or scheduled tasks to update domain health status and publish events.

        Args:
            domain_id: Domain ID
            health_status: Health status (HEALTHY, DEGRADED, UNHEALTHY)
            health_metrics: Optional health metrics dictionary
            tenant_id: Tenant ID (uses service tenant_id if not provided)
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        domain = self.get_domain(domain_id, tenant_id=effective_tenant_id)

        # Get previous health status (if stored in domain capabilities or boundaries)
        # For now, we'll use a simple approach - store in a separate field if available
        # or use capabilities JSON field
        previous_health_status = None
        if domain.capabilities and isinstance(domain.capabilities, dict):
            previous_health_status = domain.capabilities.get('health_status')

        # Update domain capabilities with health status
        if not domain.capabilities:
            domain.capabilities = {}
        elif not isinstance(domain.capabilities, dict):
            domain.capabilities = {}

        domain.capabilities['health_status'] = health_status
        if health_metrics:
            domain.capabilities['health_metrics'] = health_metrics
        domain.save(update_fields=['capabilities'])

        # Record metrics
        tenant_label = get_tenant_id(effective_tenant_id)
        domain_label = get_domain_id(str(domain.id))
        health_check_start_time = time.time()

        try:
            # Update health status gauge (1=healthy, 0.5=degraded, 0=unhealthy)
            health_value = 1.0 if health_status == "HEALTHY" else (0.5 if health_status == "DEGRADED" else 0.0)
            mesh_domain_health_status.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                health_status=health_status
            ).set(health_value)

            # Record health status change
            if previous_health_status and previous_health_status != health_status:
                mesh_domain_health_status_changes_total.labels(
                    tenant_id=tenant_label,
                    domain_id=domain_label,
                    previous_status=previous_health_status,
                    new_status=health_status
                ).inc()

            # Record health check duration (simplified - assume 0.1s for now)
            mesh_domain_health_check_duration_seconds.labels(
                tenant_id=tenant_label,
                domain_id=domain_label,
                health_status=health_status
            ).observe(0.1)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to record metrics for health status update {domain.id}: {e}",
                exc_info=True,
            )

        # Publish health status changed event
        try:
            self.publish_mesh_health_status_changed(
                domain_id=str(domain.id),
                previous_status=previous_health_status,
                new_status=health_status,
                health_metrics=health_metrics,
                tenant_id=effective_tenant_id,
                user_id=self.user_id,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to publish health status changed event for domain {domain.id}: {e}",
                exc_info=True,
            )

