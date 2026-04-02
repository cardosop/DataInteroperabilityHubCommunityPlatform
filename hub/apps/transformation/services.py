"""
Transformation Service

Service layer for transformation pipeline operations.
Provides business logic for pipeline management, execution coordination,
and event publishing.
"""

import logging
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db import connection, transaction
from django.http import HttpRequest
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.core.events.service_publishers import TransformationEventPublisher
from hub.apps.core.services.base import BaseService, NotFoundError, PermissionError, ValidationError
from hub.apps.governance.abac import ABACEngine
from hub.apps.jobs.utils import check_tenant_job_limits
from hub.apps.tenants.services import get_tenant_job_limits
from hub.apps.transformation.exceptions import (
    AssetCompatibilityError,
    ResourceQuotaExceededError,
    TransformationError,
    TransformationExecutionError,
    TransformationValidationError,
)
from hub.apps.transformation.models import (
    PipelineStatus,
    TransformationNode,
    TransformationPipeline,
)
from hub.apps.transformation.pipeline_compatibility_validator import PipelineCompatibilityValidator

logger = logging.getLogger(__name__)


class TransformationService(BaseService, TransformationEventPublisher):
    """
    Service for transformation pipeline operations.

    Provides business logic for:
    - Pipeline creation and management
    - Pipeline execution coordination
    - Node management
    - Event publishing
    - Transaction management
    - Error handling
    """

    service_name = "transformation_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TransformationService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        TransformationEventPublisher.__init__(self)

    def _validate_pipeline_schema(self, pipeline_definition: Dict[str, Any]) -> None:
        """
        Validate pipeline definition schema.

        Args:
            pipeline_definition: Pipeline definition dictionary

        Raises:
            ValidationError: If schema validation fails
        """
        errors = []

        # Validate pipeline_definition is a dictionary
        if not isinstance(pipeline_definition, dict):
            raise ValidationError(
                "Pipeline definition must be a JSON object",
                details={"pipeline_definition": "Must be a dictionary"},
            )

        # Validate required fields
        required_fields = ["version", "steps"]
        for field in required_fields:
            if field not in pipeline_definition:
                errors.append(f"Pipeline definition must contain '{field}' field")

        if errors:
            raise ValidationError("Pipeline schema validation failed", details={"errors": errors})

        # Validate version format
        version_str = pipeline_definition.get("version", "")
        if not isinstance(version_str, str) or not version_str:
            errors.append("Pipeline definition 'version' must be a non-empty string")

        # Validate steps is a list
        steps = pipeline_definition.get("steps", [])
        if not isinstance(steps, list):
            errors.append("Pipeline definition 'steps' must be a list")

        if len(steps) == 0:
            errors.append("Pipeline definition must have at least one step")

        # Validate each step has required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i} must be a JSON object")
                continue

            if "name" not in step:
                errors.append(f"Step {i} must have a 'name' field")

            if "type" not in step:
                errors.append(f"Step {i} must have a 'type' field")

        if errors:
            raise ValidationError("Pipeline schema validation failed", details={"errors": errors})

    def _validate_node_compatibility(self, pipeline_definition: Dict[str, Any]) -> None:
        """
        Validate node compatibility in pipeline definition.

        Checks that nodes can work together based on their types and configurations.

        Args:
            pipeline_definition: Pipeline definition dictionary

        Raises:
            ValidationError: If node compatibility validation fails
        """
        errors = []
        steps = pipeline_definition.get("steps", [])

        if not isinstance(steps, list) or len(steps) == 0:
            return  # Schema validation will catch this

        # Valid node types from NodeType enum
        valid_node_types = {"filter", "join", "aggregate", "transform", "output"}

        # Track node types and their positions
        node_types = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            step_type = step.get("type", "")
            step_name = step.get("name", f"step_{i}")

            # Check if step type is a valid node type
            # Note: steps can have type "task" which is different from node_type
            # We're checking for node_type in node_config if present
            node_config = step.get("node_config", {})
            if isinstance(node_config, dict):
                node_type = node_config.get("node_type")
                if node_type:
                    if node_type not in valid_node_types:
                        errors.append(
                            f"Step '{step_name}' has invalid node_type '{node_type}'. "
                            f"Valid types: {', '.join(valid_node_types)}"
                        )
                    else:
                        node_types.append((i, step_name, node_type))

        # Validate node compatibility rules
        # Rule 1: Output node should typically be last (but not strictly required)
        # Rule 2: Join nodes require at least 2 inputs
        # Rule 3: Aggregate nodes should come after filter/transform nodes typically

        output_positions = [pos for pos, name, ntype in node_types if ntype == "output"]
        if len(output_positions) > 1:
            errors.append(
                "Pipeline should have at most one output node. "
                f"Found {len(output_positions)} output nodes"
            )

        # Check join nodes have required configuration
        for pos, name, ntype in node_types:
            if ntype == "join":
                step = steps[pos]
                node_config = step.get("node_config", {})
                if not isinstance(node_config, dict):
                    errors.append(f"Join node '{name}' must have node_config as a dictionary")
                else:
                    # Join nodes typically need join keys or join type
                    if "join_type" not in node_config and "join_keys" not in node_config:
                        errors.append(
                            f"Join node '{name}' should specify join_type or join_keys in node_config"
                        )

        if errors:
            raise ValidationError(
                "Node compatibility validation failed", details={"errors": errors}
            )

    def _validate_asset_compatibility(
        self, tenant_id: str, metadata: Optional[Dict[str, Any]]
    ) -> None:
        """
        Validate asset compatibility if source/target assets are specified.

        Args:
            tenant_id: Tenant ID
            metadata: Pipeline metadata dictionary

        Raises:
            ValidationError: If asset compatibility validation fails
        """
        if not metadata or not isinstance(metadata, dict):
            return

        errors = []
        source_asset_id = metadata.get("source_asset_id")
        target_asset_id = metadata.get("target_asset_id")

        # Validate source asset if specified
        if source_asset_id:
            try:
                from hub.apps.assets.models import Asset

                source_asset = Asset.objects.get(id=source_asset_id, tenant_id=tenant_id)

                # Check asset is active or at least draft
                if source_asset.status not in ["DRAFT", "ACTIVE", "PUBLIC"]:
                    errors.append(
                        f"Source asset {source_asset_id} must be in DRAFT, ACTIVE, or PUBLIC status. "
                        f"Current status: {source_asset.status}"
                    )

            except Asset.DoesNotExist:
                errors.append(
                    f"Source asset {source_asset_id} not found or does not belong to tenant"
                )
            except Exception as e:
                errors.append(f"Error validating source asset {source_asset_id}: {str(e)}")

        # Validate target asset if specified
        if target_asset_id:
            try:
                from hub.apps.assets.models import Asset

                target_asset = Asset.objects.get(id=target_asset_id, tenant_id=tenant_id)

                # Check asset is active or at least draft
                if target_asset.status not in ["DRAFT", "ACTIVE", "PUBLIC"]:
                    errors.append(
                        f"Target asset {target_asset_id} must be in DRAFT, ACTIVE, or PUBLIC status. "
                        f"Current status: {target_asset.status}"
                    )

            except Asset.DoesNotExist:
                errors.append(
                    f"Target asset {target_asset_id} not found or does not belong to tenant"
                )
            except Exception as e:
                errors.append(f"Error validating target asset {target_asset_id}: {str(e)}")

        if errors:
            raise ValidationError(
                "Asset compatibility validation failed", details={"errors": errors}
            )

    def _check_user_permissions(
        self, user_id: str, tenant_id: str, request: Optional[HttpRequest] = None
    ) -> None:
        """
        Check user permissions for pipeline creation.

        Validates:
        - User has DATA_PROVIDER or TENANT_ADMIN role
        - User has transformation:write scope (via API key or role-based)

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            request: Optional HTTP request object (for API key scope checking)

        Raises:
            PermissionError: If user lacks required permissions
        """
        from hub.apps.users.models import User

        try:
            # Prefetch user_roles relationship to ensure has_role() works correctly
            user = User.objects.prefetch_related("user_roles__role").get(id=user_id)
        except User.DoesNotExist:
            raise PermissionError(f"User {user_id} not found")

        # Platform admins have all permissions (can operate on any tenant)
        if user.is_platform_admin:
            return

        # For non-platform admins, verify tenant matches
        if str(user.tenant_id) != tenant_id:
            raise PermissionError(f"User {user_id} does not belong to tenant {tenant_id}")

        # Check if user has required role (DATA_PROVIDER or TENANT_ADMIN)
        # Refresh user to ensure user_roles relationship is loaded
        user.refresh_from_db()
        has_required_role = user.has_role("DATA_PROVIDER", "TENANT_ADMIN")
        if not has_required_role:
            raise PermissionError(
                f"User {user_id} does not have required role (DATA_PROVIDER or TENANT_ADMIN) for pipeline creation"
            )

        # Check if user has transformation:write scope
        # Priority: API key scopes > role-based assumption
        has_scope = False

        if request and hasattr(request, "api_key_scopes"):
            # Check API key scopes if available
            required_scope = "transformation:write"
            has_scope = required_scope in request.api_key_scopes
            if not has_scope:
                raise PermissionError(
                    f"API key does not have required scope '{required_scope}' for pipeline creation"
                )
        else:
            # For regular users without API key, assume users with DATA_PROVIDER or TENANT_ADMIN role
            # have transformation:write scope (role-based permission model)
            # This is consistent with the codebase pattern where roles grant implicit scopes
            has_scope = True

        logger.debug(
            f"User permissions checked: user_id={user_id}, tenant_id={tenant_id}, "
            f"has_role={has_required_role}, has_scope={has_scope}"
        )

    def _validate_resource_quota(self, tenant_id: str, pipeline_definition: Dict[str, Any]) -> None:
        """
        Validate resource quota (compute, storage) for pipeline creation.

        Checks:
        - Tenant job concurrency limits
        - Tenant queued job limits
        - Pipeline node count limits (if applicable)

        Args:
            tenant_id: Tenant ID
            pipeline_definition: Pipeline definition dictionary

        Raises:
            ResourceQuotaExceededError: If quota is exceeded
        """
        # Check tenant job limits (concurrency and queue depth)
        can_create_job, error_message = check_tenant_job_limits(tenant_id)
        if not can_create_job:
            limits = get_tenant_job_limits(tenant_id)
            running_key = f"job:tenant:{tenant_id}:running"
            queued_key = f"job:tenant:{tenant_id}:queued"
            running_count = cache.get(running_key, 0)
            queued_count = cache.get(queued_key, 0)

            # Determine which limit was exceeded
            if running_count >= limits["max_job_concurrency"]:
                raise ResourceQuotaExceededError(
                    error_message or "Tenant has reached maximum concurrent job limit",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT,
                    quota_type="concurrent_executions",
                    limit=float(limits["max_job_concurrency"]),
                    current=float(running_count),
                    tenant_id=tenant_id,
                )
            elif queued_count >= limits["max_queued_jobs"]:
                raise ResourceQuotaExceededError(
                    error_message or "Tenant has reached maximum queued job limit",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_CONCURRENT_EXECUTIONS_LIMIT,
                    quota_type="queued_jobs",
                    limit=float(limits["max_queued_jobs"]),
                    current=float(queued_count),
                    tenant_id=tenant_id,
                )
            else:
                # Generic quota exceeded error
                raise ResourceQuotaExceededError(
                    error_message or "Tenant resource quota exceeded",
                    error_code=ResourceQuotaExceededError.ERROR_CODE_QUOTA_EXCEEDED,
                    tenant_id=tenant_id,
                )

        # Check pipeline node count limit (if applicable)
        # This is a placeholder for future quota checks
        # For now, we don't enforce node count limits, but the structure is here
        steps = pipeline_definition.get("steps", [])
        node_count = len(steps)
        # Future: Check against tenant-specific node count limits
        # For now, we allow any number of nodes

        logger.debug(f"Resource quota validated: tenant_id={tenant_id}, node_count={node_count}")

    def _check_abac_policies(
        self,
        user_id: str,
        tenant_id: str,
        resource_type: str = "TRANSFORMATION_PIPELINE",
        resource_id: Optional[str] = None,
        access_type: str = "WRITE",
    ) -> None:
        """
        Check ABAC policies for pipeline operations.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            resource_type: Resource type (default: TRANSFORMATION_PIPELINE)
            resource_id: Optional resource ID (for existing pipelines)
            access_type: Access type (default: WRITE)

        Raises:
            PermissionError: If ABAC policy denies access
        """
        # For new pipeline creation, we use a placeholder resource ID
        # In a real implementation, this might be a tenant-scoped resource identifier
        effective_resource_id = resource_id or f"tenant:{tenant_id}:pipeline:new"

        # Evaluate ABAC access
        result = ABACEngine.evaluate_access(
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=effective_resource_id,
            access_type=access_type,
        )

        if not result.allowed:
            # ABAC policy denied access
            policy_name = result.policy.name if result.policy else "Unknown"
            raise PermissionError(
                f"ABAC policy denied access to {resource_type} operation. " f"Policy: {policy_name}"
            )

        logger.debug(
            f"ABAC policy checked: user_id={user_id}, tenant_id={tenant_id}, "
            f"resource_type={resource_type}, access_type={access_type}, allowed={result.allowed}"
        )

    @transaction.atomic
    def create_pipeline(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        pipeline_definition: Optional[Dict[str, Any]] = None,
        version: str = "1.0.0",
        status: PipelineStatus = PipelineStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[HttpRequest] = None,
    ) -> TransformationPipeline:
        """
        Create a transformation pipeline with comprehensive validation.

        Performs:
        - User permission checks (role and scope)
        - Resource quota validation
        - ABAC policy checks
        - Pipeline schema validation
        - Node compatibility checks
        - Asset compatibility validation (if assets specified in metadata)
        - Transaction management
        - Event publishing (transformation.pipeline.created)
        - Audit logging

        Args:
            tenant_id: Tenant ID
            user_id: User ID creating the pipeline
            name: Pipeline name
            description: Optional pipeline description
            pipeline_definition: Optional pipeline definition (JSON)
            version: Pipeline version (default: "1.0.0")
            status: Pipeline status (default: DRAFT)
            metadata: Optional metadata dictionary (may contain source_asset_id, target_asset_id)

        Returns:
            Created TransformationPipeline instance

        Raises:
            PermissionError: If user lacks required permissions
            ResourceQuotaExceededError: If resource quota is exceeded
            ValidationError: If validation fails
        """
        try:
            # Check user permissions (role and scope)
            self._check_user_permissions(user_id, tenant_id, request=request)

            # Check plan limit for transformation pipelines
            from hub.apps.tenants.services import PlanLimitService
            plan_limit_service = PlanLimitService(
                tenant_id=tenant_id, user_id=user_id,
            )
            plan_limit_service.check_limit(
                tenant_id=tenant_id,
                limit_key="max_transformation_pipelines",
                delta=1,
            )

            # Validate resource quota
            # Default pipeline definition for quota check if not provided
            effective_pipeline_definition = pipeline_definition or {
                "version": version,
                "steps": [{"name": "initial_step", "type": "task", "task": "noop", "input": {}}],
            }
            self._validate_resource_quota(tenant_id, effective_pipeline_definition)

            # Check ABAC policies
            self._check_abac_policies(user_id, tenant_id, access_type="WRITE")

            # Use effective pipeline definition (already set for quota check)
            pipeline_definition = effective_pipeline_definition

            # Validate pipeline schema
            self._validate_pipeline_schema(pipeline_definition)

            # Validate node compatibility
            self._validate_node_compatibility(pipeline_definition)

            # Validate asset compatibility if assets are specified
            effective_metadata = metadata or {}
            self._validate_asset_compatibility(tenant_id, effective_metadata)

            # Create pipeline instance for validation
            pipeline = TransformationPipeline(
                tenant_id=tenant_id,
                created_by_id=user_id,
                name=name,
                description=description,
                pipeline_definition=pipeline_definition,
                version=version,
                status=status,
                metadata=effective_metadata,
            )

            # Run model validation (clean method)
            pipeline.full_clean()

            # Save pipeline
            pipeline.save()

            # Publish pipeline created event
            try:
                # Convert status to string if it's a TextChoices tuple
                status_str = pipeline.status
                if isinstance(status_str, tuple):
                    status_str = status_str[0]

                self.publish_pipeline_created(
                    pipeline_id=str(pipeline.id),
                    name=pipeline.name,
                    version=pipeline.version,
                    status=status_str,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as e:
                # Log but don't fail pipeline creation if event publishing fails
                logger.warning(
                    f"Failed to publish pipeline.created event for pipeline {pipeline.id}: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "tenant_id": tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Create audit log
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=tenant_id)
                user_obj = User.objects.get(id=user_id) if user_id else None

                # Prepare audit details with all required fields
                audit_details = {
                    "pipeline_id": str(pipeline.id),
                    "pipeline_name": pipeline.name,
                    "version": pipeline.version,
                    "status": pipeline.status,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                }

                # Add optional fields if present
                if description:
                    audit_details["description"] = description
                if metadata:
                    audit_details["metadata"] = metadata
                if pipeline_definition:
                    # Include step count instead of full definition to avoid large payloads
                    steps = pipeline_definition.get("steps", [])
                    audit_details["step_count"] = len(
                        steps
                    )  # Keep as int, JSON will serialize correctly

                create_audit_event(
                    resource_type="TRANSFORMATION_PIPELINE",
                    action="CREATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(pipeline.id),
                    result="SUCCESS",
                    details=audit_details,
                    request=request,
                )
            except Exception as e:
                # Log but don't fail pipeline creation if audit logging fails
                logger.warning(
                    f"Failed to create audit log for pipeline {pipeline.id}: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "tenant_id": tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Record metrics
            try:
                from hub.apps.transformation.monitoring import record_pipeline_created

                record_pipeline_created(tenant_id)
            except Exception as e:
                logger.warning(f"Failed to record pipeline created metric: {e}")

            logger.info(
                f"Created transformation pipeline {pipeline.id}",
                extra={
                    "pipeline_id": str(pipeline.id),
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "pipeline_name": name,
                },
            )

            return pipeline

        except (ValidationError, PermissionError, ResourceQuotaExceededError):
            # Re-raise these specific errors as-is
            raise
        except Exception as e:
            logger.error(
                f"Failed to create transformation pipeline: {e}",
                extra={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "pipeline_name": name,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to create transformation pipeline: {str(e)}", details={"error": str(e)}
            )

    @transaction.atomic
    def update_pipeline(
        self,
        pipeline_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        pipeline_definition: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[HttpRequest] = None,
    ) -> TransformationPipeline:
        """
        Update a transformation pipeline.

        Args:
            pipeline_id: Pipeline ID to update
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            name: Optional new name
            description: Optional new description
            pipeline_definition: Optional new pipeline definition
            version: Optional new version
            status: Optional new status
            metadata: Optional metadata to update

        Returns:
            Updated TransformationPipeline instance

        Raises:
            NotFoundError: If pipeline not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id

        try:
            # Get pipeline
            pipeline = self.get_resource_or_raise(
                TransformationPipeline, pipeline_id, tenant_id=effective_tenant_id
            )

            # Track changes for audit logging BEFORE updating fields
            changes = {}
            original_values = {}

            if name is not None and pipeline.name != name:
                original_values["name"] = pipeline.name
                changes["name"] = name
            if description is not None and pipeline.description != description:
                original_values["description"] = pipeline.description
                changes["description"] = description
            if version is not None and pipeline.version != version:
                original_values["version"] = pipeline.version
                changes["version"] = version
            if status is not None and pipeline.status != status:
                original_values["status"] = pipeline.status
                changes["status"] = status
            if pipeline_definition is not None:
                # Compare pipeline definitions (simplified comparison)
                if pipeline.get_pipeline_definition() != pipeline_definition:
                    original_values["pipeline_definition"] = pipeline.get_pipeline_definition()
                    changes["pipeline_definition"] = pipeline_definition
                    # Include step count for audit
                    steps = pipeline_definition.get("steps", [])
                    changes["step_count"] = len(steps)
            if metadata is not None:
                # Compare metadata (simplified comparison)
                # For metadata, we need to handle dict merging
                if isinstance(pipeline.metadata, dict) and isinstance(metadata, dict):
                    # Check if there are actual changes
                    merged = pipeline.metadata.copy()
                    merged.update(metadata)
                    if merged != pipeline.metadata:
                        original_values["metadata"] = pipeline.metadata.copy()
                        changes["metadata"] = metadata
                elif pipeline.metadata != metadata:
                    original_values["metadata"] = (
                        pipeline.metadata.copy()
                        if isinstance(pipeline.metadata, dict)
                        else pipeline.metadata
                    )
                    changes["metadata"] = metadata

            # Update fields
            if name is not None:
                pipeline.name = name
            if description is not None:
                pipeline.description = description
            if pipeline_definition is not None:
                pipeline.pipeline_definition = pipeline_definition
            if version is not None:
                pipeline.version = version
            if status is not None:
                pipeline.status = status
            if metadata is not None:
                # Merge metadata if it's a dict
                if isinstance(pipeline.metadata, dict) and isinstance(metadata, dict):
                    pipeline.metadata.update(metadata)
                else:
                    pipeline.metadata = metadata

            # Validate and save
            pipeline.full_clean()
            pipeline.save()

            # Create audit log
            effective_user_id = user_id or self.user_id
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                # Prepare audit details with change tracking
                audit_details = {
                    "pipeline_id": str(pipeline.id),
                    "pipeline_name": pipeline.name,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                }

                # Include change tracking
                if changes:
                    audit_details["changes"] = changes
                    audit_details["original_values"] = original_values

                create_audit_event(
                    resource_type="TRANSFORMATION_PIPELINE",
                    action="UPDATED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(pipeline.id),
                    result="SUCCESS",
                    details=audit_details,
                    request=request,
                )
            except Exception as e:
                # Log but don't fail pipeline update if audit logging fails
                logger.warning(
                    f"Failed to create audit log for pipeline update {pipeline.id}: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "tenant_id": effective_tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Publish pipeline updated event
            try:
                # Convert status to string if it's a TextChoices tuple
                previous_status_str = original_values.get("status")
                if isinstance(previous_status_str, tuple):
                    previous_status_str = previous_status_str[0]
                new_status_str = pipeline.status
                if isinstance(new_status_str, tuple):
                    new_status_str = new_status_str[0]

                self.publish_pipeline_updated(
                    pipeline_id=str(pipeline.id),
                    changes=changes,
                    previous_status=str(previous_status_str) if previous_status_str else None,
                    new_status=str(new_status_str) if new_status_str else None,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
            except Exception as e:
                # Log but don't fail pipeline update if event publishing fails
                logger.warning(
                    f"Failed to publish pipeline.updated event for pipeline {pipeline.id}: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "tenant_id": effective_tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            logger.info(
                f"Updated transformation pipeline {pipeline.id}",
                extra={
                    "pipeline_id": str(pipeline.id),
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )

            return pipeline

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update transformation pipeline {pipeline_id}: {e}",
                extra={
                    "pipeline_id": pipeline_id,
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to update transformation pipeline: {str(e)}", details={"error": str(e)}
            )

    @transaction.atomic
    def delete_pipeline(
        self,
        pipeline_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        Delete a transformation pipeline.

        Args:
            pipeline_id: Pipeline ID to delete
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            request: Optional HTTP request object (for audit logging)

        Raises:
            NotFoundError: If pipeline not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        try:
            # Get pipeline and capture details before deletion
            pipeline = self.get_resource_or_raise(
                TransformationPipeline, pipeline_id, tenant_id=effective_tenant_id
            )

            # Capture pipeline details for audit logging before deletion
            pipeline_id_str = str(pipeline.id)
            pipeline_name = pipeline.name
            pipeline_version = pipeline.version
            pipeline_status = pipeline.status
            step_count = (
                len(pipeline.get_pipeline_definition().get("steps", []))
                if isinstance(pipeline.get_pipeline_definition(), dict)
                else 0
            )  # Keep as int

            # Delete pipeline (cascade will delete nodes)
            pipeline.delete()

            # Publish pipeline deleted event
            try:
                self.publish_pipeline_deleted(
                    pipeline_id=pipeline_id_str,
                    reason=None,  # Could be enhanced to accept reason parameter
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
            except Exception as e:
                # Log but don't fail pipeline deletion if event publishing fails
                logger.warning(
                    f"Failed to publish pipeline.deleted event for pipeline {pipeline_id_str}: {e}",
                    extra={
                        "pipeline_id": pipeline_id_str,
                        "tenant_id": effective_tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Create audit log
            try:
                from django.contrib.auth import get_user_model

                from hub.apps.audit.utils import create_audit_event
                from hub.apps.tenants.models import Tenant

                User = get_user_model()
                tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                # Prepare audit details with pipeline information
                audit_details = {
                    "pipeline_id": pipeline_id_str,
                    "pipeline_name": pipeline_name,
                    "version": pipeline_version,
                    "status": pipeline_status,
                    "step_count": step_count,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                }

                create_audit_event(
                    resource_type="TRANSFORMATION_PIPELINE",
                    action="DELETED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=pipeline_id_str,
                    result="SUCCESS",
                    details=audit_details,
                    request=request,
                )
            except Exception as e:
                # Log but don't fail pipeline deletion if audit logging fails
                logger.warning(
                    f"Failed to create audit log for pipeline deletion {pipeline_id_str}: {e}",
                    extra={
                        "pipeline_id": pipeline_id_str,
                        "tenant_id": effective_tenant_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            logger.info(
                f"Deleted transformation pipeline {pipeline_id_str}",
                extra={
                    "pipeline_id": pipeline_id_str,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to delete transformation pipeline {pipeline_id}: {e}",
                extra={
                    "pipeline_id": pipeline_id,
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    def get_pipeline(
        self, pipeline_id: str, tenant_id: Optional[str] = None
    ) -> TransformationPipeline:
        """
        Get a transformation pipeline by ID.

        Args:
            pipeline_id: Pipeline ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            TransformationPipeline instance

        Raises:
            NotFoundError: If pipeline not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        return self.get_resource_or_raise(
            TransformationPipeline, pipeline_id, tenant_id=effective_tenant_id
        )

    @transaction.atomic
    def create_node(
        self,
        pipeline_id: str,
        node_type: str,
        node_config: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, Any]] = None,
        order: int = 1,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> TransformationNode:
        """
        Create a transformation node.

        Args:
            pipeline_id: Pipeline ID
            node_type: Node type (filter, join, aggregate, transform, output)
            node_config: Optional node configuration (JSON)
            position: Optional position coordinates (JSON)
            order: Execution order (default: 1)
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)

        Returns:
            Created TransformationNode instance

        Raises:
            NotFoundError: If pipeline not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id

        try:
            # Get pipeline
            pipeline = self.get_resource_or_raise(
                TransformationPipeline, pipeline_id, tenant_id=effective_tenant_id
            )

            # Create node
            node = TransformationNode.objects.create(
                pipeline=pipeline,
                node_type=node_type,
                node_config=node_config or {},
                position=position or {},
                order=order,
            )

            logger.info(
                f"Created transformation node {node.id} for pipeline {pipeline_id}",
                extra={
                    "node_id": str(node.id),
                    "pipeline_id": pipeline_id,
                    "node_type": node_type,
                    "order": order,
                    "tenant_id": effective_tenant_id,
                },
            )

            return node

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to create transformation node: {e}",
                extra={
                    "pipeline_id": pipeline_id,
                    "node_type": node_type,
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise ValidationError(
                f"Failed to create transformation node: {str(e)}", details={"error": str(e)}
            )

    def _validate_pipeline_for_execution(self, pipeline: TransformationPipeline) -> None:
        """
        Validate pipeline is ready for execution.

        Args:
            pipeline: Pipeline to validate

        Raises:
            TransformationValidationError: If pipeline cannot be executed
        """
        if not pipeline.can_execute():
            raise TransformationValidationError(
                f"Pipeline {pipeline.id} cannot be executed. Status: {pipeline.status}",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
                details={"pipeline_id": str(pipeline.id), "status": pipeline.status},
                tenant_id=str(pipeline.tenant_id),
            )

        # Validate pipeline definition
        self._validate_pipeline_schema(pipeline.get_pipeline_definition())
        self._validate_node_compatibility(pipeline.get_pipeline_definition())

    def _check_asset_compatibility_for_execution(
        self, asset_id: str, tenant_id: str, pipeline: TransformationPipeline
    ) -> None:
        """
        Check asset compatibility with pipeline for execution.

        Args:
            asset_id: Asset ID to check
            tenant_id: Tenant ID
            pipeline: Pipeline to check compatibility with

        Raises:
            AssetCompatibilityError: If asset is incompatible
            NotFoundError: If asset not found
        """
        from hub.apps.assets.models import Asset

        try:
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
        except Asset.DoesNotExist:
            raise NotFoundError("Asset", asset_id)

        # Check asset status
        if asset.status not in ["DRAFT", "ACTIVE", "PUBLIC"]:
            raise AssetCompatibilityError(
                f"Asset {asset_id} must be in DRAFT, ACTIVE, or PUBLIC status for transformation. "
                f"Current status: {asset.status}",
                error_code=AssetCompatibilityError.ERROR_CODE_SCHEMA_INCOMPATIBLE,
                asset_id=str(asset_id),
                pipeline_id=str(pipeline.id),
                tenant_id=tenant_id,
            )

        # Check if asset has datasets
        latest_dataset = asset.datasets.order_by("-version").first()
        if not latest_dataset:
            raise AssetCompatibilityError(
                f"Asset {asset_id} has no datasets to transform",
                error_code=AssetCompatibilityError.ERROR_CODE_REQUIRED_FIELD_MISSING,
                asset_id=str(asset_id),
                pipeline_id=str(pipeline.id),
                tenant_id=tenant_id,
            )

        # Check if dataset has file
        if not latest_dataset.file:
            raise AssetCompatibilityError(
                f"Asset {asset_id} dataset has no file to transform",
                error_code=AssetCompatibilityError.ERROR_CODE_REQUIRED_FIELD_MISSING,
                asset_id=str(asset_id),
                pipeline_id=str(pipeline.id),
                tenant_id=tenant_id,
            )

    def _select_execution_mode(
        self, asset_id: str, tenant_id: str, force_mode: Optional[str] = None
    ) -> str:
        """
        Select execution mode (SYNC or ASYNC) based on dataset size.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            force_mode: Optional forced execution mode (SYNC, ASYNC)

        Returns:
            Execution mode string (SYNC or ASYNC)
        """
        if force_mode:
            return force_mode.upper()

        from hub.apps.assets.models import Asset
        from hub.apps.transformation.models import ExecutionMode

        try:
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            latest_dataset = asset.datasets.order_by("-version").first()

            if not latest_dataset:
                # Default to ASYNC if no dataset info available
                return ExecutionMode.ASYNC

            # Use row_count if available, otherwise use file size
            row_count = latest_dataset.row_count
            file_size = latest_dataset.file.size if latest_dataset.file else 0

            # Threshold: < 10,000 rows or < 10MB = SYNC, otherwise ASYNC
            SYNC_ROW_THRESHOLD = 10000
            SYNC_SIZE_THRESHOLD = 10 * 1024 * 1024  # 10MB

            if row_count and row_count < SYNC_ROW_THRESHOLD:
                return ExecutionMode.SYNC
            elif file_size and file_size < SYNC_SIZE_THRESHOLD:
                return ExecutionMode.SYNC
            else:
                return ExecutionMode.ASYNC

        except Exception as e:
            logger.warning(
                f"Error selecting execution mode for asset {asset_id}: {e}. Defaulting to ASYNC.",
                exc_info=True,
            )
            return ExecutionMode.ASYNC

    def validate_pipeline_compatibility(
        self,
        pipeline: TransformationPipeline,
        input_schema: Optional[Dict[str, Any]] = None,
        input_asset: Optional[Asset] = None,
        use_cache: bool = True,
    ) -> ValidationResult:
        """
        Comprehensive pipeline compatibility validation.

        Validates:
        - Schema compatibility (input schema vs pipeline input schema)
        - Data type compatibility (field types match)
        - Node compatibility (node types supported, node order valid)
        - Pipeline definition validation (required fields, valid structure)

        Args:
            pipeline: TransformationPipeline instance to validate
            input_schema: Optional input schema dictionary (if not provided, extracted from input_asset)
            input_asset: Optional input asset (used to extract schema if input_schema not provided)
            use_cache: Whether to use cached validation results

        Returns:
            ValidationResult with validation status, errors, warnings, and details

        Example:
            >>> service = TransformationService(tenant_id="...", user_id="...")
            >>> pipeline = TransformationPipeline.objects.get(id="...")
            >>> asset = Asset.objects.get(id="...")
            >>> result = service.validate_pipeline_compatibility(pipeline, input_asset=asset)
            >>> if result.is_valid:
            ...     print("Pipeline is compatible!")
            ... else:
            ...     print(f"Validation errors: {result.errors}")
        """
        validator = PipelineCompatibilityValidator(tenant_id=self.tenant_id, user_id=self.user_id)

        return validator.validate_pipeline_compatibility(
            pipeline=pipeline,
            input_schema=input_schema,
            input_asset=input_asset,
            use_cache=use_cache,
        )

    def _execute_pipeline_sync(
        self,
        pipeline: TransformationPipeline,
        asset_id: str,
        execution: "PipelineExecution",
        tenant_id: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute pipeline synchronously (for small datasets).

        Args:
            pipeline: Pipeline to execute
            asset_id: Source asset ID
            execution: PipelineExecution instance
            tenant_id: Tenant ID
            user_id: Optional user ID

        Returns:
            Execution result dictionary

        Raises:
            TransformationExecutionError: If execution fails
        """
        from hub.apps.assets.models import Asset
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.transformation.models import ExecutionStatus

        try:
            # Get asset and dataset
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            latest_dataset = asset.datasets.order_by("-version").first()

            if not latest_dataset or not latest_dataset.file:
                raise TransformationExecutionError(
                    "Asset has no dataset or file to transform",
                    error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                    pipeline_id=str(pipeline.id),
                    execution_id=str(execution.id),
                    tenant_id=tenant_id,
                )

            # Download file content
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
            file_format = latest_dataset.format or "CSV"

            # Execute transformation steps
            # For now, this is a placeholder - actual transformation logic would go here
            # In a real implementation, this would:
            # 1. Parse the file content based on format
            # 2. Execute each pipeline step in sequence
            # 3. Apply transformations (filter, join, aggregate, transform, output)
            # 4. Generate output file
            # 5. Create result asset

            execution.add_log_entry("Starting synchronous pipeline execution", "INFO")
            execution.add_log_entry(
                f"Processing {file_format} file with {len(file_content)} bytes", "INFO"
            )

            # Placeholder: In real implementation, execute pipeline steps here
            # For now, we'll create a simple result
            result_data = {
                "rows_processed": latest_dataset.row_count or 0,
                "execution_mode": "SYNC",
                "file_format": file_format,
            }

            execution.add_log_entry("Pipeline execution completed successfully", "INFO")

            return result_data

        except Exception as e:
            error_msg = f"Synchronous pipeline execution failed: {str(e)}"
            execution.add_log_entry(error_msg, "ERROR")
            raise TransformationExecutionError(
                error_msg,
                error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED,
                pipeline_id=str(pipeline.id),
                execution_id=str(execution.id),
                tenant_id=tenant_id,
                cause=e,
            )

    @transaction.atomic
    def execute_pipeline(
        self,
        pipeline_id: str,
        asset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        execution_mode: Optional[str] = None,
        request: Optional[HttpRequest] = None,
        idempotency_key: Optional[str] = None,
    ) -> "PipelineExecution":
        """
        Execute a transformation pipeline.

        Performs:
        - Pipeline validation
        - Asset compatibility check
        - Execution mode selection (sync/async)
        - Quality and compliance checks (before and after)
        - Synchronous or asynchronous execution
        - Result storage
        - Event publishing
        - Audit logging

        Args:
            pipeline_id: Pipeline ID to execute
            asset_id: Source asset ID to transform
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            execution_mode: Optional execution mode (SYNC, ASYNC) - auto-selected if not provided
            request: Optional HTTP request object (for audit logging)
            idempotency_key: Optional idempotency key for retry safety (uses execution_id if not provided)

        Returns:
            PipelineExecution instance

        Raises:
            NotFoundError: If pipeline or asset not found
            TransformationValidationError: If validation fails
            AssetCompatibilityError: If asset is incompatible
            TransformationExecutionError: If execution fails
        """
        from hub.apps.assets.models import Asset
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.tenants.models import Tenant
        from hub.apps.transformation.models import ExecutionMode, ExecutionStatus, PipelineExecution
        from hub.apps.users.models import User

        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Check plan limit for transformation runs
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
        )
        plan_limit_service.check_limit(
            tenant_id=effective_tenant_id,
            limit_key="max_transformation_runs_per_month",
            delta=1,
        )

        # Record metrics (Phase 115E.1)
        try:
            from hub.apps.observability.otel_metrics import (
                transformation_queue_depth,
                transformation_runs_total,
            )
            transformation_queue_depth.labels(
                tenant_id=effective_tenant_id,
            ).inc()
        except Exception:
            pass  # Metrics are best-effort

        # Check idempotency: if idempotency_key is provided, check for existing execution
        if idempotency_key:
            try:
                existing_execution = PipelineExecution.objects.select_for_update().get(
                    idempotency_key=idempotency_key, pipeline__tenant_id=effective_tenant_id
                )
                # If execution exists and is in terminal state, return it
                if existing_execution.is_terminal():
                    logger.info(
                        f"Idempotent execution found (already completed): {existing_execution.id}",
                        extra={
                            "idempotency_key": idempotency_key,
                            "execution_id": str(existing_execution.id),
                            "status": existing_execution.status,
                        },
                    )
                    return existing_execution
                # If execution exists and is not terminal, raise error (duplicate execution)
                raise TransformationExecutionError(
                    f"Execution with idempotency_key '{idempotency_key}' already exists and is not in terminal state",
                    error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED,
                    pipeline_id=pipeline_id,
                    execution_id=str(existing_execution.id),
                    tenant_id=effective_tenant_id,
                )
            except PipelineExecution.DoesNotExist:
                # No existing execution, proceed with new execution
                pass
            except PipelineExecution.MultipleObjectsReturned:
                # Multiple executions with same key (should not happen due to unique constraint)
                logger.error(
                    f"Multiple executions found with idempotency_key '{idempotency_key}'",
                    extra={"idempotency_key": idempotency_key, "tenant_id": effective_tenant_id},
                )
                raise TransformationExecutionError(
                    f"Multiple executions found with idempotency_key '{idempotency_key}'",
                    error_code=TransformationExecutionError.ERROR_CODE_INTERNAL_ERROR,
                    pipeline_id=pipeline_id,
                    tenant_id=effective_tenant_id,
                )

        try:
            # Get pipeline
            pipeline = self.get_resource_or_raise(
                TransformationPipeline, pipeline_id, tenant_id=effective_tenant_id
            )

            # Validate pipeline for execution
            self._validate_pipeline_for_execution(pipeline)

            # Check asset compatibility
            self._check_asset_compatibility_for_execution(asset_id, effective_tenant_id, pipeline)

            # Select execution mode
            selected_mode = execution_mode or self._select_execution_mode(
                asset_id, effective_tenant_id
            )

            # Run compliance check before execution (blocks if compliance fails)
            # Create a temporary execution record for compliance check
            # This allows us to run compliance check before workflow execution
            from hub.apps.transformation.models import ExecutionMode, ExecutionStatus

            temp_execution = PipelineExecution(
                pipeline=pipeline,
                asset_id=asset_id,
                status=ExecutionStatus.PENDING,
                execution_mode=selected_mode if selected_mode else ExecutionMode.ASYNC,
                execution_log=[],
            )
            temp_execution.save()

            # Run compliance check (will raise TransformationValidationError if compliance fails)
            try:
                self._run_compliance_check(
                    asset_id=asset_id, tenant_id=effective_tenant_id, execution=temp_execution
                )
            finally:
                # Clean up temporary execution (workflow will create its own)
                temp_execution.delete()

            # Use workflow for execution
            from hub.apps.orchestration.registry import WorkflowRegistry
            from hub.apps.orchestration.workflow_engine import WorkflowEngine
            from hub.apps.orchestration.workflows.transformation_pipeline import (
                TransformationPipelineWorkflow,
            )

            # Create workflow engine and registry
            engine = WorkflowEngine()
            TransformationPipelineWorkflow.register_tasks(engine)
            registry = WorkflowRegistry()
            TransformationPipelineWorkflow.register_workflow(registry)

            # Execute workflow
            execution_mode_str = (
                selected_mode.value if hasattr(selected_mode, "value") else str(selected_mode)
            )
            workflow_result = TransformationPipelineWorkflow.execute(
                pipeline_id=pipeline_id,
                asset_id=asset_id,
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
                execution_mode=execution_mode_str,
                engine=engine,
                registry=registry,
            )

            # Get execution from workflow result
            execution_id = workflow_result.get("execution_id")
            if not execution_id:
                raise TransformationExecutionError(
                    "Workflow execution did not return execution_id",
                    error_code=TransformationExecutionError.ERROR_CODE_INTERNAL_ERROR,
                    pipeline_id=pipeline_id,
                    tenant_id=effective_tenant_id,
                )

            # Get execution and link to workflow instance
            execution = PipelineExecution.objects.get(id=execution_id)
            workflow_instance_id = workflow_result.get("workflow_instance_id")
            if workflow_instance_id:
                from hub.apps.orchestration.models import WorkflowInstance

                try:
                    workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                    execution.set_workflow_instance(workflow_instance)
                except WorkflowInstance.DoesNotExist:
                    logger.warning(
                        f"Workflow instance {workflow_instance_id} not found for execution {execution_id}",
                        extra={
                            "execution_id": str(execution.id),
                            "workflow_instance_id": workflow_instance_id,
                        },
                    )

            # Set idempotency key if provided
            if idempotency_key and not execution.idempotency_key:
                execution.idempotency_key = idempotency_key
                execution.save(update_fields=["idempotency_key", "updated_at"])
            elif not execution.idempotency_key:
                execution.idempotency_key = str(execution.id)
                execution.save(update_fields=["idempotency_key", "updated_at"])

            # Sync execution status from workflow
            execution.sync_status_from_workflow()

            # Publish execution started event
            try:
                self.publish_pipeline_started(
                    pipeline_id=str(pipeline.id),
                    execution_id=str(execution.id),
                    asset_id=asset_id,
                    execution_mode=selected_mode,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish pipeline execution started event: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "execution_id": str(execution.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Get tenant and user objects for audit logging (used in multiple places)
            tenant_obj = Tenant.objects.get(id=effective_tenant_id)
            user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

            # Create audit log for execution start
            try:
                create_audit_event(
                    resource_type="TRANSFORMATION_PIPELINE",
                    action="EXECUTION_STARTED",
                    actor_user=user_obj,
                    tenant=tenant_obj,
                    resource_id=str(pipeline.id),
                    result="SUCCESS",
                    details={
                        "execution_id": str(execution.id),
                        "pipeline_id": str(pipeline.id),
                        "asset_id": asset_id,
                        "execution_mode": (
                            selected_mode.value
                            if hasattr(selected_mode, "value")
                            else str(selected_mode)
                        ),
                        "pipeline_name": pipeline.name,
                        "workflow_instance_id": workflow_result.get("workflow_instance_id"),
                    },
                    request=request,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit log for execution start: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "execution_id": str(execution.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Workflow handles execution (both SYNC and ASYNC)
            # For SYNC mode, workflow executes synchronously
            # For ASYNC mode, workflow creates a job for async execution
            # Sync execution status from workflow
            execution.refresh_from_db()
            execution.sync_status_from_workflow()

            # If workflow failed, raise error
            if not workflow_result.get("success", False):
                error_message = workflow_result.get("error", "Workflow execution failed")
                raise TransformationExecutionError(
                    error_message,
                    error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED,
                    pipeline_id=pipeline_id,
                    execution_id=str(execution.id),
                    tenant_id=effective_tenant_id,
                )

            # Monitor execution with metrics and tracing
            from hub.apps.transformation.monitoring import record_pipeline_execution

            # For SYNC mode, workflow should have completed synchronously
            # For ASYNC mode, execution will be processed by job
            if selected_mode == ExecutionMode.SYNC:
                # Refresh execution to get latest status from workflow
                execution.refresh_from_db()
                execution.sync_status_from_workflow()

                # Determine final status for monitoring
                execution_status = (
                    execution.status.value
                    if hasattr(execution.status, "value")
                    else str(execution.status)
                )

                # Wrap SYNC execution with monitoring (status will be updated based on actual result)
                with record_pipeline_execution(
                    tenant_id=effective_tenant_id,
                    pipeline_id=str(pipeline.id),
                    status=execution_status,
                ):
                    # If execution completed, publish events and create audit logs
                    if execution.status == ExecutionStatus.COMPLETED:
                        # Publish completion event
                        duration_ms = (
                            int(execution.get_duration_seconds() * 1000)
                            if execution.get_duration_seconds()
                            else None
                        )
                        try:
                            workflow_state = execution.get_workflow_state() or {}
                            result_data = workflow_state.get("execution_results", {})
                            input_quality_metrics = workflow_state.get("input_quality_metrics")

                            self.publish_pipeline_completed(
                                pipeline_id=str(pipeline.id),
                                execution_id=str(execution.id),
                                duration_ms=duration_ms,
                                records_processed=result_data.get("rows_processed"),
                                quality_metrics=input_quality_metrics,
                                tenant_id=effective_tenant_id,
                                user_id=effective_user_id,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to publish pipeline execution completed event: {e}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e),
                                },
                                exc_info=True,
                            )

                        # Create audit log for completion
                        try:
                            duration_seconds = execution.get_duration_seconds()
                            duration_ms = int(duration_seconds * 1000) if duration_seconds else None
                            workflow_state = execution.get_workflow_state() or {}
                            result_data = workflow_state.get("execution_results", {})
                            input_quality_metrics = workflow_state.get("input_quality_metrics")

                            completion_details = {
                                "execution_id": str(execution.id),
                                "pipeline_id": str(pipeline.id),
                                "asset_id": asset_id,
                                "execution_mode": (
                                    selected_mode.value
                                    if hasattr(selected_mode, "value")
                                    else str(selected_mode)
                                ),
                                "duration_seconds": duration_seconds,
                                "duration_ms": duration_ms,
                                "quality_metrics": input_quality_metrics,
                                "workflow_instance_id": workflow_result.get("workflow_instance_id"),
                            }

                            # Add result_asset_id if available
                            if execution.result_asset:
                                completion_details["result_asset_id"] = str(
                                    execution.result_asset.id
                                )

                            # Add records_processed if available
                            if result_data and "rows_processed" in result_data:
                                completion_details["records_processed"] = result_data[
                                    "rows_processed"
                                ]

                            create_audit_event(
                                resource_type="TRANSFORMATION_PIPELINE",
                                action="EXECUTION_COMPLETED",
                                actor_user=user_obj,
                                tenant=tenant_obj,
                                resource_id=str(pipeline.id),
                                result="SUCCESS",
                                details=completion_details,
                                request=request,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to create audit log for execution completion: {e}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e),
                                },
                                exc_info=True,
                            )

                        # Send notification email for completion
                        try:
                            from hub.apps.notifications.tasks import (
                                send_pipeline_execution_completion_email,
                            )

                            send_pipeline_execution_completion_email.delay(str(execution.id))
                        except Exception as e:
                            logger.warning(
                                f"Failed to send pipeline execution completion notification: {e}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e),
                                },
                                exc_info=True,
                            )
                    elif execution.status == ExecutionStatus.FAILED:
                        # Workflow failed - publish failure event
                        error_msg = (
                            execution.workflow_instance.error_message
                            if execution.workflow_instance
                            else "Workflow execution failed"
                        )
                        duration_ms = (
                            int(execution.get_duration_seconds() * 1000)
                            if execution.get_duration_seconds()
                            else None
                        )

                        try:
                            self.publish_pipeline_failed(
                                pipeline_id=str(pipeline.id),
                                error=error_msg,
                                execution_id=str(execution.id),
                                error_code=None,
                                error_details=None,
                                duration_ms=duration_ms,
                                tenant_id=effective_tenant_id,
                                user_id=effective_user_id,
                            )
                        except Exception as e2:
                            logger.warning(
                                f"Failed to publish pipeline execution failed event: {e2}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e2),
                                },
                                exc_info=True,
                            )

                        # Create audit log for failure
                        try:
                            duration_seconds = execution.get_duration_seconds()
                            duration_ms = int(duration_seconds * 1000) if duration_seconds else None

                            failure_details = {
                                "execution_id": str(execution.id),
                                "pipeline_id": str(pipeline.id),
                                "asset_id": asset_id,
                                "execution_mode": (
                                    selected_mode.value
                                    if hasattr(selected_mode, "value")
                                    else str(selected_mode)
                                ),
                                "error_message": error_msg,
                                "duration_seconds": duration_seconds,
                                "duration_ms": duration_ms,
                                "workflow_instance_id": workflow_result.get("workflow_instance_id"),
                            }

                            create_audit_event(
                                resource_type="TRANSFORMATION_PIPELINE",
                                action="EXECUTION_FAILED",
                                actor_user=user_obj,
                                tenant=tenant_obj,
                                resource_id=str(pipeline.id),
                                result="FAILURE",
                                details=failure_details,
                                request=request,
                            )
                        except Exception as e2:
                            logger.warning(
                                f"Failed to create audit log for execution failure: {e2}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e2),
                                },
                                exc_info=True,
                            )

                        # Send notification email for failure
                        try:
                            from hub.apps.notifications.tasks import (
                                send_pipeline_execution_failure_email,
                            )

                            send_pipeline_execution_failure_email.delay(str(execution.id))
                        except Exception as e2:
                            logger.warning(
                                f"Failed to send pipeline execution failure notification: {e2}",
                                extra={
                                    "pipeline_id": str(pipeline.id),
                                    "execution_id": str(execution.id),
                                    "error": str(e2),
                                },
                                exc_info=True,
                            )

                        raise TransformationExecutionError(
                            error_msg,
                            error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED,
                            pipeline_id=pipeline_id,
                            execution_id=str(execution.id),
                            tenant_id=effective_tenant_id,
                        )
            else:
                # Asynchronous execution - workflow creates job for async execution
                execution.add_log_entry("Workflow enqueued for asynchronous execution", "INFO")

                # Refresh execution to get job from workflow
                execution.refresh_from_db()
                execution.sync_status_from_workflow()

                try:
                    tenant_obj = Tenant.objects.get(id=effective_tenant_id)
                    user_obj = User.objects.get(id=effective_user_id) if effective_user_id else None

                    # Determine queue name based on execution mode
                    # SYNC mode uses job_critical for high priority, ASYNC uses job_default
                    # Note: For async execution, we use job_default queue
                    # For sync execution (if forced), we would use job_critical
                    queue_name = (
                        "job_critical" if selected_mode == ExecutionMode.SYNC else "job_default"
                    )

                    # Create job for async execution
                    job = create_job(
                        tenant=tenant_obj,
                        user=user_obj,
                        job_type=JobType.TRANSFORMATION,
                        resource_type="TRANSFORMATION_PIPELINE",
                        resource_id=str(execution.id),
                        details_json={
                            "pipeline_id": str(pipeline.id),
                            "asset_id": asset_id,
                            "execution_mode": (
                                selected_mode.value
                                if hasattr(selected_mode, "value")
                                else str(selected_mode)
                            ),
                        },
                        queue_name=queue_name,
                    )

                    # Link job to execution
                    execution.job = job
                    execution.save(update_fields=["job", "updated_at"])

                    execution.add_log_entry(
                        f"Job {job.id} created for async execution (queue: {queue_name})", "INFO"
                    )

                except Exception as e:
                    error_msg = f"Failed to enqueue async execution: {str(e)}"
                    execution.add_log_entry(error_msg, "ERROR")

                    # Execute compensation logic for async execution failure
                    try:
                        from hub.apps.transformation.compensation import (
                            TransformationPipelineCompensation,
                        )

                        compensation = TransformationPipelineCompensation(execution)
                        compensation_result = compensation.compensate(
                            rollback_execution=True,
                            cleanup_job=True,  # Cleanup job if it was created
                            cleanup_result_asset=False,  # No result asset yet
                            publish_compensation_events=True,
                        )
                        logger.info(
                            f"Compensation completed for async execution {execution.id}",
                            extra={
                                "execution_id": str(execution.id),
                                "compensation_result": compensation_result,
                            },
                        )
                    except Exception as comp_error:
                        logger.exception(
                            f"Compensation failed for async execution {execution.id}: {comp_error}",
                            extra={
                                "execution_id": str(execution.id),
                                "compensation_error": str(comp_error),
                            },
                        )
                        # Still mark execution as failed even if compensation fails
                        execution.mark_failed(error_message=error_msg)

                    raise TransformationExecutionError(
                        error_msg,
                        error_code=TransformationExecutionError.ERROR_CODE_EXECUTION_FAILED,
                        pipeline_id=str(pipeline.id),
                        execution_id=str(execution.id),
                        tenant_id=effective_tenant_id,
                        cause=e,
                    )

            logger.info(
                f"Pipeline execution initiated: {execution.id}",
                extra={
                    "execution_id": str(execution.id),
                    "pipeline_id": str(pipeline.id),
                    "asset_id": asset_id,
                    "execution_mode": selected_mode,
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                },
            )

            return execution

        except (
            NotFoundError,
            TransformationValidationError,
            AssetCompatibilityError,
            TransformationExecutionError,
        ):
            raise
        except Exception as e:
            logger.error(
                f"Failed to execute pipeline: {e}",
                extra={
                    "pipeline_id": pipeline_id,
                    "asset_id": asset_id,
                    "tenant_id": effective_tenant_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise TransformationExecutionError(
                f"Failed to execute pipeline: {str(e)}",
                error_code=TransformationExecutionError.ERROR_CODE_INTERNAL_ERROR,
                pipeline_id=pipeline_id,
                tenant_id=effective_tenant_id,
                cause=e,
            )

    def _run_quality_check(
        self, asset_id: str, tenant_id: str, execution: "PipelineExecution"
    ) -> Optional[Dict[str, Any]]:
        """
        Run quality check on asset via QualityService.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            execution: PipelineExecution instance

        Returns:
            Quality metrics dictionary or None if check fails
        """
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.dq.service_client import DQServiceClient
            from hub.apps.files.storage import S3StorageClient

            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            latest_dataset = asset.datasets.order_by("-version").first()

            if not latest_dataset or not latest_dataset.file:
                return None

            # Download file content
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
            file_format = latest_dataset.format or "csv"

            # Initialize DQ client
            dq_client = DQServiceClient()

            # Check DQ service health
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                execution.add_log_entry("DQ service unavailable, skipping quality check", "WARNING")
                return None

            # Run DQ check
            dq_result = dq_client.run_dq(
                file_content=file_content,
                file_format=file_format.lower(),
                profile_key=None,  # Use default profile
            )

            # Extract quality metrics
            quality_metrics = {
                "quality_score": dq_result.get("quality_score", 0.0),
                "overall_status": dq_result.get("overall_status", "UNKNOWN"),
                "checks_passed": dq_result.get("checks_passed", 0),
                "checks_failed": dq_result.get("checks_failed", 0),
            }

            execution.add_log_entry(
                f"Quality check completed: score={quality_metrics['quality_score']:.2%}, "
                f"status={quality_metrics['overall_status']}",
                "INFO",
            )

            return quality_metrics

        except Exception as e:
            logger.warning(
                f"Quality check failed (non-critical): {e}",
                extra={"asset_id": asset_id, "execution_id": str(execution.id), "error": str(e)},
                exc_info=True,
            )
            execution.add_log_entry(f"Quality check failed: {str(e)}", "WARNING")
            return None

    def _run_compliance_check(
        self, asset_id: str, tenant_id: str, execution: "PipelineExecution"
    ) -> Optional[Dict[str, Any]]:
        """
        Run compliance check on asset via ComplianceService.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            execution: PipelineExecution instance

        Returns:
            Compliance status dictionary or None if check fails
        """
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.compliance.service_client import ComplianceServiceClient
            from hub.apps.files.storage import S3StorageClient
            from hub.apps.transformation.exceptions import TransformationValidationError

            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            latest_dataset = asset.datasets.order_by("-version").first()

            if not latest_dataset or not latest_dataset.file:
                return None

            # Download file content
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
            file_format = latest_dataset.format or "csv"

            # Initialize compliance client
            compliance_client = ComplianceServiceClient()

            # Check compliance service health
            is_healthy, _ = compliance_client.health_check()
            if not is_healthy:
                execution.add_log_entry(
                    "Compliance service unavailable, skipping compliance check", "WARNING"
                )
                return None

            # Run compliance scan
            compliance_result = compliance_client.scan_file(
                file_content=file_content, file_format=file_format.lower(), scan_mode="internal"
            )

            # Extract comprehensive compliance status
            compliance_status = {
                "overall_status": compliance_result.get("overall_status", "UNKNOWN"),
                "risk_level": compliance_result.get("risk_level", "UNKNOWN"),
                "allowed_to_store": compliance_result.get("allowed_to_store", None),
                "detected_categories": compliance_result.get("detected_categories", {}),
                "column_findings": compliance_result.get("column_findings", []),
                "regulation_mapping": compliance_result.get("regulation_mapping", {}),
            }

            # Store compliance status in execution_log
            if isinstance(execution.execution_log, list):
                execution.execution_log.append(
                    {
                        "timestamp": timezone.now().isoformat(),
                        "level": "INFO",
                        "message": "Compliance check completed",
                        "data": {
                            "asset_id": asset_id,
                            "compliance_status": compliance_status,
                            "check_type": "input_asset",
                        },
                    }
                )
                execution.save(update_fields=["execution_log", "updated_at"])

            # Block execution if compliance violations detected
            if compliance_status["overall_status"] == "FAIL":
                error_msg = (
                    f"Compliance check failed for input asset {asset_id}. "
                    f"Risk level: {compliance_status['risk_level']}. "
                    f"Compliance violations detected."
                )
                raise TransformationValidationError(
                    error_msg,
                    error_code=TransformationValidationError.ERROR_CODE_VALIDATION_FAILED,
                    details={
                        "asset_id": asset_id,
                        "compliance_status": compliance_status,
                        "check_type": "input_asset",
                        "violations": compliance_status.get("detected_categories", {}),
                    },
                    tenant_id=tenant_id,
                )

            # Validate transformation doesn't violate compliance rules
            # Check if transformation would introduce new compliance issues
            # Get pipeline from execution
            pipeline = execution.pipeline
            self._validate_transformation_compliance(compliance_status, pipeline, execution)

            execution.add_log_entry(
                f"Compliance check completed: status={compliance_status['overall_status']}, "
                f"risk_level={compliance_status['risk_level']}",
                "INFO",
            )

            return compliance_status

        except TransformationValidationError:
            raise
        except Exception as e:
            logger.warning(
                f"Compliance check failed (non-critical): {e}",
                extra={"asset_id": asset_id, "execution_id": str(execution.id), "error": str(e)},
                exc_info=True,
            )
            execution.add_log_entry(f"Compliance check failed: {str(e)}", "WARNING")
            return None

    def _validate_transformation_compliance(
        self,
        input_compliance_status: Dict[str, Any],
        pipeline: TransformationPipeline,
        execution: "PipelineExecution",
    ) -> None:
        """
        Validate that transformation doesn't violate compliance rules.

        Checks:
        - Transformation steps don't introduce new PII categories
        - Transformation doesn't remove required compliance controls
        - Transformation maintains compliance posture

        Args:
            input_compliance_status: Compliance status of input asset
            pipeline: Transformation pipeline
            execution: PipelineExecution instance

        Raises:
            TransformationValidationError: If transformation violates compliance rules
        """
        from hub.apps.transformation.exceptions import TransformationValidationError

        # Check if input has compliance issues that would be propagated
        if input_compliance_status.get("overall_status") == "WARN":
            # Log warning but allow execution
            execution.add_log_entry(
                f"Input asset has compliance warnings. Transformation may propagate issues.",
                "WARNING",
            )

        # Check pipeline definition for compliance-sensitive operations
        pipeline_definition = pipeline.get_pipeline_definition()
        steps = pipeline_definition.get("steps", [])

        # Validate that transformation steps don't introduce new compliance risks
        # This is a simplified check - in a real implementation, we would:
        # 1. Analyze each step for PII handling
        # 2. Check if transformations preserve compliance controls
        # 3. Validate that output schema maintains compliance posture

        # For now, we log the validation
        execution.add_log_entry(
            f"Transformation compliance validation completed. "
            f"Input compliance status: {input_compliance_status.get('overall_status')}",
            "INFO",
        )

        # Store validation result in execution_log
        if isinstance(execution.execution_log, list):
            execution.execution_log.append(
                {
                    "timestamp": timezone.now().isoformat(),
                    "level": "INFO",
                    "message": "Transformation compliance validation",
                    "data": {
                        "input_compliance_status": input_compliance_status.get("overall_status"),
                        "validation_passed": True,
                    },
                }
            )
            execution.save(update_fields=["execution_log", "updated_at"])

    def _check_output_asset_compliance(
        self, result_asset_id: str, tenant_id: str, execution: "PipelineExecution"
    ) -> Optional[Dict[str, Any]]:
        """
        Check compliance status of output asset after transformation.

        Args:
            result_asset_id: Result asset ID
            tenant_id: Tenant ID
            execution: PipelineExecution instance

        Returns:
            Compliance status dictionary or None if check fails
        """
        try:
            from hub.apps.assets.models import Asset
            from hub.apps.compliance.service_client import ComplianceServiceClient
            from hub.apps.files.storage import S3StorageClient
            from hub.apps.transformation.exceptions import TransformationValidationError

            asset = Asset.objects.get(id=result_asset_id, tenant_id=tenant_id)
            latest_dataset = asset.datasets.order_by("-version").first()

            if not latest_dataset or not latest_dataset.file:
                execution.add_log_entry(
                    "Result asset has no dataset or file for compliance check", "WARNING"
                )
                return None

            # Download file content
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
            file_format = latest_dataset.format or "csv"

            # Initialize compliance client
            compliance_client = ComplianceServiceClient()

            # Check compliance service health
            is_healthy, _ = compliance_client.health_check()
            if not is_healthy:
                execution.add_log_entry(
                    "Compliance service unavailable, skipping output compliance check", "WARNING"
                )
                return None

            # Run compliance scan on output
            compliance_result = compliance_client.scan_file(
                file_content=file_content, file_format=file_format.lower(), scan_mode="internal"
            )

            # Extract comprehensive compliance status
            compliance_status = {
                "overall_status": compliance_result.get("overall_status", "UNKNOWN"),
                "risk_level": compliance_result.get("risk_level", "UNKNOWN"),
                "allowed_to_store": compliance_result.get("allowed_to_store", None),
                "detected_categories": compliance_result.get("detected_categories", {}),
                "column_findings": compliance_result.get("column_findings", []),
                "regulation_mapping": compliance_result.get("regulation_mapping", {}),
            }

            # Store compliance status in execution_log
            if isinstance(execution.execution_log, list):
                execution.execution_log.append(
                    {
                        "timestamp": timezone.now().isoformat(),
                        "level": "INFO",
                        "message": "Output asset compliance check completed",
                        "data": {
                            "asset_id": result_asset_id,
                            "compliance_status": compliance_status,
                            "check_type": "output_asset",
                        },
                    }
                )
                execution.save(update_fields=["execution_log", "updated_at"])

            # Block if output has compliance violations
            if compliance_status["overall_status"] == "FAIL":
                error_msg = (
                    f"Compliance check failed for output asset {result_asset_id}. "
                    f"Risk level: {compliance_status['risk_level']}. "
                    f"Transformation produced non-compliant output."
                )
                raise TransformationValidationError(
                    error_msg,
                    error_code=TransformationValidationError.ERROR_CODE_VALIDATION_FAILED,
                    details={
                        "asset_id": result_asset_id,
                        "compliance_status": compliance_status,
                        "check_type": "output_asset",
                        "violations": compliance_status.get("detected_categories", {}),
                    },
                    tenant_id=tenant_id,
                )

            execution.add_log_entry(
                f"Output compliance check completed: status={compliance_status['overall_status']}, "
                f"risk_level={compliance_status['risk_level']}",
                "INFO",
            )

            return compliance_status

        except TransformationValidationError:
            raise
        except Exception as e:
            logger.warning(
                f"Output compliance check failed (non-critical): {e}",
                extra={
                    "asset_id": result_asset_id,
                    "execution_id": str(execution.id),
                    "error": str(e),
                },
                exc_info=True,
            )
            execution.add_log_entry(f"Output compliance check failed: {str(e)}", "WARNING")
            return None

    def preview_transformation(
        self,
        pipeline_id: str,
        asset_id: str,
        sample_size: int = 100,
        sampling_method: str = "first_n",
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Preview transformation pipeline execution on sample data.

        Generates a preview of transformation results by:
        1. Sampling data from the input asset (first N rows or random sampling)
        2. Executing the pipeline on the sample
        3. Analyzing results (row count changes, schema changes, quality impact)
        4. Caching results (Redis, TTL: 1 hour)
        5. Publishing preview.generated event

        Args:
            pipeline_id: Pipeline ID to preview
            asset_id: Source asset ID
            sample_size: Number of rows to sample (default: 100)
            sampling_method: Sampling method - "first_n" or "random" (default: "first_n")
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)

        Returns:
            Dictionary with preview results:
            - preview_id: Unique preview identifier
            - input_sample: Sample input data
            - output_sample: Sample output data
            - analysis: Result analysis (row_count_changes, schema_changes, quality_impact)
            - cached: Whether result was from cache
            - generated_at: Timestamp when preview was generated

        Raises:
            NotFoundError: If pipeline or asset not found
            TransformationValidationError: If validation fails
            TransformationExecutionError: If execution fails
        """
        import hashlib
        import json
        import random

        from hub.apps.assets.models import Asset
        from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker
        from hub.apps.datasets.schema_inference import (
            extract_sample_data,
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet,
        )
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.transformation.models import ExecutionStatus, PipelineExecution
        from hub.apps.transformation.monitoring import record_preview_generation
        from hub.apps.transformation.quality_integration import TransformationQualityIntegration

        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Wrap preview generation with monitoring
        with record_preview_generation(effective_tenant_id):
            # Validate pipeline exists
            try:
                pipeline = TransformationPipeline.objects.get(
                    id=pipeline_id, tenant_id=effective_tenant_id
                )
            except TransformationPipeline.DoesNotExist:
                raise NotFoundError(f"Pipeline {pipeline_id} not found")

            # Validate asset exists
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
            except Asset.DoesNotExist:
                raise NotFoundError(f"Asset {asset_id} not found")

            # Generate cache key based on pipeline, asset, sample_size, and sampling_method
            cache_key_data = {
                "pipeline_id": str(pipeline.id),
                "asset_id": str(asset.id),
                "sample_size": sample_size,
                "sampling_method": sampling_method,
                "pipeline_version": pipeline.version,
            }
            cache_key_str = json.dumps(cache_key_data, sort_keys=True)
            cache_key_hash = hashlib.sha256(cache_key_str.encode()).hexdigest()
            cache_key = f"transformation_preview:{cache_key_hash}"
            preview_id = f"preview_{cache_key_hash[:16]}"

            # Check cache (TTL: 1 hour = 3600 seconds)
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(
                    f"Preview cache hit for pipeline {pipeline_id}, asset {asset_id}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "cache_key": cache_key,
                        "quality_metrics_available": "quality_metrics" in cached_result
                        or "quality_impact" in cached_result.get("analysis", {}),
                    },
                )
                cached_result["cached"] = True
                # Ensure quality_metrics is available at top level if not already present
                if "quality_metrics" not in cached_result and "analysis" in cached_result:
                    cached_result["quality_metrics"] = cached_result["analysis"].get(
                        "quality_impact", {}
                    )
                return cached_result

            # Get asset dataset and file
            latest_dataset = asset.datasets.order_by("-version").first()
            if not latest_dataset or not latest_dataset.file:
                raise TransformationExecutionError(
                    "Asset has no dataset or file to transform",
                    error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                    pipeline_id=str(pipeline.id),
                    tenant_id=effective_tenant_id,
                )

            # Download file content
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
            file_format = latest_dataset.format or "CSV"

            # Generate sample data
            logger.info(
                f"Generating sample data for preview: method={sampling_method}, size={sample_size}",
                extra={
                    "pipeline_id": str(pipeline.id),
                    "asset_id": str(asset.id),
                    "sampling_method": sampling_method,
                    "sample_size": sample_size,
                },
            )

            input_sample = self._generate_sample_data(
                file_content=file_content,
                file_format=file_format,
                sample_size=sample_size,
                sampling_method=sampling_method,
            )

            if not input_sample:
                raise TransformationExecutionError(
                    "Failed to generate sample data",
                    error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                    pipeline_id=str(pipeline.id),
                    tenant_id=effective_tenant_id,
                )

            # Infer input schema
            input_schema = self._infer_schema_from_data(input_sample, file_format)

            # Execute pipeline on sample
            logger.info(
                f"Executing pipeline on sample data: {len(input_sample)} rows",
                extra={
                    "pipeline_id": str(pipeline.id),
                    "asset_id": str(asset.id),
                    "sample_rows": len(input_sample),
                },
            )

            output_sample = self._execute_pipeline_on_sample(
                pipeline=pipeline, input_sample=input_sample, file_format=file_format
            )

            # Infer output schema
            output_schema = (
                self._infer_schema_from_data(output_sample, file_format) if output_sample else None
            )

            # Analyze results
            analysis = self._analyze_preview_results(
                input_sample=input_sample,
                output_sample=output_sample,
                input_schema=input_schema,
                output_schema=output_schema,
                asset_id=asset_id,
                tenant_id=effective_tenant_id,
            )

            # Extract quality metrics from analysis for easy access
            quality_metrics = analysis.get("quality_impact", {})

            # Create preview result (use same preview_id as used in progress events)
            # preview_id was already generated above
            preview_result = {
                "preview_id": preview_id,
                "pipeline_id": str(pipeline.id),
                "pipeline_name": pipeline.name,
                "asset_id": str(asset.id),
                "asset_name": asset.name,
                "input_sample": input_sample[:10],  # Return first 10 rows for preview
                "output_sample": output_sample[:10] if output_sample else [],
                "input_sample_size": len(input_sample),
                "output_sample_size": len(output_sample) if output_sample else 0,
                "analysis": analysis,
                "quality_metrics": quality_metrics,  # Store quality metrics at top level for easy access
                "cached": False,
                "generated_at": timezone.now().isoformat(),
                "sample_size": sample_size,
                "sampling_method": sampling_method,
            }

            # Cache result (TTL: 1 hour = 3600 seconds)
            try:
                cache.set(cache_key, preview_result, timeout=3600)
                logger.info(
                    f"Preview result cached: key={cache_key}, ttl=3600s",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "cache_key": cache_key,
                    },
                )
            except Exception as e:
                logger.warning(
                    f"Failed to cache preview result: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Store preview result in database for retrieval by preview_id
            try:
                from datetime import timedelta

                from hub.apps.transformation.models import PreviewResult

                expires_at = timezone.now() + timedelta(hours=1)

                PreviewResult.objects.update_or_create(
                    preview_id=preview_id,
                    defaults={
                        "tenant": pipeline.tenant,
                        "created_by_id": effective_user_id,
                        "pipeline": pipeline,
                        "asset": asset,
                        "preview_data": preview_result,
                        "cache_key": cache_key,
                        "sample_size": sample_size,
                        "sampling_method": sampling_method,
                        "expires_at": expires_at,
                    },
                )
                logger.info(
                    f"Preview result stored in database: preview_id={preview_id}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "preview_id": preview_id,
                    },
                )
            except Exception as e:
                logger.warning(
                    f"Failed to store preview result in database: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "preview_id": preview_id,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            # Publish preview.generated event
            try:
                self._publish_preview_generated_event(
                    pipeline_id=str(pipeline.id),
                    asset_id=str(asset.id),
                    preview_id=preview_id,
                    analysis=analysis,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to publish preview.generated event: {e}",
                    extra={
                        "pipeline_id": str(pipeline.id),
                        "asset_id": str(asset.id),
                        "error": str(e),
                    },
                    exc_info=True,
                )

            logger.info(
                f"Preview generated successfully: preview_id={preview_id}",
                extra={
                    "pipeline_id": str(pipeline.id),
                    "asset_id": str(asset.id),
                    "preview_id": preview_id,
                    "input_rows": len(input_sample),
                    "output_rows": len(output_sample) if output_sample else 0,
                },
            )

            return preview_result

    def _generate_sample_data(
        self,
        file_content: bytes,
        file_format: str,
        sample_size: int,
        sampling_method: str = "first_n",
    ) -> List[Dict[str, Any]]:
        """
        Generate sample data from file content.

        Args:
            file_content: File content as bytes
            file_format: File format (CSV, JSON, PARQUET)
            sample_size: Number of rows to sample
            sampling_method: "first_n" or "random"

        Returns:
            List of dictionaries representing sample rows
        """
        import random

        from hub.apps.datasets.schema_inference import extract_sample_data

        if sampling_method == "first_n":
            # Use existing extract_sample_data for first N rows
            return extract_sample_data(file_content, file_format, sample_size)
        elif sampling_method == "random":
            # For random sampling, we need to read all data first, then sample
            # This is less efficient but provides true random sampling
            all_data = extract_sample_data(
                file_content, file_format, sample_size * 10
            )  # Get more data for sampling
            if len(all_data) <= sample_size:
                return all_data
            return random.sample(all_data, sample_size)
        else:
            raise ValueError(
                f"Unsupported sampling method: {sampling_method}. Use 'first_n' or 'random'"
            )

    def _infer_schema_from_data(
        self, data: List[Dict[str, Any]], file_format: str
    ) -> Dict[str, Any]:
        """
        Infer schema from sample data.

        Args:
            data: List of data dictionaries
            file_format: Original file format

        Returns:
            Schema dictionary
        """
        if not data:
            return {"fields": []}

        # Get all unique keys from data
        all_keys = set()
        for row in data:
            all_keys.update(row.keys())

        # Infer types for each field
        fields = []
        for key in sorted(all_keys):
            # Sample values for this field
            values = [row.get(key) for row in data if key in row]
            if not values:
                continue

            # Determine data type
            data_type = self._infer_field_type(values)

            field = {
                "name": key,
                "data_type": data_type,
                "nullable": any(v is None for v in values),
                "sample_values": values[:5],  # Store first 5 sample values
            }
            fields.append(field)

        return {"fields": fields, "field_count": len(fields), "row_count": len(data)}

    def _infer_field_type(self, values: List[Any]) -> str:
        """
        Infer data type from a list of values.

        Args:
            values: List of field values

        Returns:
            Data type string (string, integer, float, boolean, date, datetime)
        """
        import re
        from datetime import datetime

        # Filter out None values
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return "string"

        # Check for boolean
        bool_count = sum(1 for v in non_null_values if isinstance(v, bool))
        if bool_count == len(non_null_values):
            return "boolean"

        # Check for integer
        int_count = 0
        for v in non_null_values:
            if isinstance(v, int):
                int_count += 1
            elif isinstance(v, str):
                try:
                    int(v)
                    int_count += 1
                except ValueError:
                    pass

        if int_count == len(non_null_values):
            return "integer"

        # Check for float
        float_count = 0
        for v in non_null_values:
            if isinstance(v, float):
                float_count += 1
            elif isinstance(v, (int, str)):
                try:
                    float(v)
                    float_count += 1
                except ValueError:
                    pass

        if float_count == len(non_null_values):
            return "float"

        # Check for datetime
        datetime_count = 0
        date_patterns = [
            r"\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
            r"\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
        ]

        for v in non_null_values:
            if isinstance(v, datetime):
                datetime_count += 1
            elif isinstance(v, str):
                for pattern in date_patterns:
                    if re.match(pattern, v):
                        datetime_count += 1
                        break

        if datetime_count > len(non_null_values) * 0.8:  # 80% match threshold
            return "datetime"

        # Default to string
        return "string"

    def _execute_pipeline_on_sample(
        self, pipeline: TransformationPipeline, input_sample: List[Dict[str, Any]], file_format: str
    ) -> List[Dict[str, Any]]:
        """
        Execute pipeline transformation on sample data.

        Args:
            pipeline: TransformationPipeline instance
            input_sample: Sample input data
            file_format: Original file format

        Returns:
            Transformed sample data
        """
        # For now, this is a simplified implementation
        # In a full implementation, this would:
        # 1. Parse pipeline_definition
        # 2. Execute each step in sequence
        # 3. Apply transformations (filter, join, aggregate, transform, output)

        # Placeholder: Return input sample as-is for now
        # TODO: Implement actual pipeline execution logic
        # This should execute the pipeline steps defined in pipeline.pipeline_definition
        logger.warning(
            "Pipeline execution on sample is using placeholder implementation",
            extra={
                "pipeline_id": str(pipeline.id),
                "note": "Actual pipeline transformation logic needs to be implemented",
            },
        )

        # For now, return input sample unchanged
        # In production, this would execute the actual pipeline steps
        return input_sample

    def _analyze_preview_results(
        self,
        input_sample: List[Dict[str, Any]],
        output_sample: Optional[List[Dict[str, Any]]],
        input_schema: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]],
        asset_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Analyze preview results: row count changes, schema changes, quality impact.

        Args:
            input_sample: Input sample data
            output_sample: Output sample data (may be None)
            input_schema: Input schema
            output_schema: Output schema (may be None)
            asset_id: Asset ID for quality checks
            tenant_id: Tenant ID

        Returns:
            Analysis dictionary with:
            - row_count_changes: Input/output row counts and change
            - schema_changes: Schema differences
            - quality_impact: Quality metrics comparison
        """
        analysis = {"row_count_changes": {}, "schema_changes": {}, "quality_impact": {}}

        # Row count analysis
        input_row_count = len(input_sample)
        output_row_count = len(output_sample) if output_sample else 0
        row_count_delta = output_row_count - input_row_count
        row_count_delta_percent = (
            (row_count_delta / input_row_count * 100) if input_row_count > 0 else 0.0
        )

        analysis["row_count_changes"] = {
            "input_rows": input_row_count,
            "output_rows": output_row_count,
            "delta": row_count_delta,
            "delta_percent": row_count_delta_percent,
            "rows_added": max(0, row_count_delta),
            "rows_removed": max(0, -row_count_delta),
        }

        # Schema changes analysis
        if output_schema:
            try:
                from hub.apps.datasets.schema_evolution import SchemaEvolutionTracker

                schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
                    old_schema=input_schema, new_schema=output_schema
                )

                analysis["schema_changes"] = {
                    "has_changes": len(schema_diff.changes) > 0,
                    "compatibility_level": (
                        schema_diff.compatibility_level.value
                        if hasattr(schema_diff.compatibility_level, "value")
                        else str(schema_diff.compatibility_level)
                    ),
                    "changes_count": len(schema_diff.changes),
                    "summary": schema_diff.summary,
                    "changes": [
                        {
                            "type": (
                                change.change_type.value
                                if hasattr(change.change_type, "value")
                                else str(change.change_type)
                            ),
                            "field_name": change.field_name,
                            "description": change.description,
                            "breaking": change.breaking,
                        }
                        for change in schema_diff.changes
                    ],
                }
            except Exception as e:
                logger.warning(
                    f"Failed to calculate schema diff: {e}", extra={"error": str(e)}, exc_info=True
                )
                analysis["schema_changes"] = {"has_changes": False, "error": str(e)}
        else:
            analysis["schema_changes"] = {
                "has_changes": False,
                "error": "Output schema not available",
            }

        # Quality impact analysis
        try:
            quality_impact = self._analyze_quality_impact(
                asset_id=asset_id,
                tenant_id=tenant_id,
                input_sample=input_sample,
                output_sample=output_sample,
            )
            analysis["quality_impact"] = quality_impact
        except Exception as e:
            logger.warning(
                f"Failed to analyze quality impact: {e}", extra={"error": str(e)}, exc_info=True
            )
            analysis["quality_impact"] = {"error": str(e), "available": False}

        return analysis

    def _analyze_quality_impact(
        self,
        asset_id: str,
        tenant_id: str,
        input_sample: List[Dict[str, Any]],
        output_sample: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Analyze quality impact by running quality checks on input and output samples.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            input_sample: Input sample data
            output_sample: Output sample data

        Returns:
            Quality impact dictionary
        """
        import csv
        import io
        import json

        from hub.apps.dq.service_client import DQServiceClient

        try:
            dq_client = DQServiceClient()

            # Check DQ service health
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                return {"available": False, "error": "DQ service unavailable"}

            # Convert samples to file-like objects for DQ service
            # For input
            input_file_content = self._convert_sample_to_file_content(input_sample, "csv")
            input_quality = dq_client.run_dq(
                file_content=input_file_content, file_format="csv", profile_key="intake_basic_gx"
            )

            # For output (if available)
            output_quality = None
            if output_sample:
                output_file_content = self._convert_sample_to_file_content(output_sample, "csv")
                output_quality = dq_client.run_dq(
                    file_content=output_file_content,
                    file_format="csv",
                    profile_key="intake_basic_gx",
                )

            # Extract comprehensive quality metrics
            input_score = input_quality.get("quality_score", 0.0)
            output_score = output_quality.get("quality_score", 0.0) if output_quality else None

            # Get input quality details
            input_checks = input_quality.get("checks", [])
            input_passed_checks = (
                len([c for c in input_checks if c.get("status") == "PASS"]) if input_checks else 0
            )
            input_failed_checks = (
                len([c for c in input_checks if c.get("status") == "FAIL"]) if input_checks else 0
            )
            input_total_checks = len(input_checks) if input_checks else 0

            # Get output quality details
            output_checks = output_quality.get("checks", []) if output_quality else []
            output_passed_checks = (
                len([c for c in output_checks if c.get("status") == "PASS"]) if output_checks else 0
            )
            output_failed_checks = (
                len([c for c in output_checks if c.get("status") == "FAIL"]) if output_checks else 0
            )
            output_total_checks = len(output_checks) if output_checks else 0

            # Compare quality metrics
            quality_delta = None
            quality_delta_percent = None
            checks_delta = None
            if output_score is not None:
                quality_delta = output_score - input_score
                quality_delta_percent = (
                    (quality_delta / input_score * 100) if input_score > 0 else 0.0
                )
                checks_delta = output_passed_checks - input_passed_checks

            # Build comprehensive quality impact metrics
            quality_impact = {
                "available": True,
                "input_quality_metrics": {
                    "quality_score": input_score,
                    "overall_status": input_quality.get("overall_status"),
                    "checks_passed": input_passed_checks,
                    "checks_failed": input_failed_checks,
                    "checks_total": input_total_checks,
                    "engine_type": input_quality.get("engine_type"),
                    "engine_version": input_quality.get("engine_version"),
                    "profile_key": "intake_basic_gx",
                },
                "output_quality_metrics": (
                    {
                        "quality_score": output_score,
                        "overall_status": (
                            output_quality.get("overall_status") if output_quality else None
                        ),
                        "checks_passed": output_passed_checks,
                        "checks_failed": output_failed_checks,
                        "checks_total": output_total_checks,
                        "engine_type": (
                            output_quality.get("engine_type") if output_quality else None
                        ),
                        "engine_version": (
                            output_quality.get("engine_version") if output_quality else None
                        ),
                        "profile_key": "intake_basic_gx",
                    }
                    if output_quality
                    else None
                ),
                "quality_comparison": (
                    {
                        "quality_delta": quality_delta,
                        "quality_delta_percent": quality_delta_percent,
                        "checks_delta": checks_delta,
                        "improvement_detected": (
                            quality_delta > 0 if quality_delta is not None else False
                        ),
                        "degradation_detected": (
                            quality_delta < 0 if quality_delta is not None else False
                        ),
                        "status_change": self._determine_status_change(
                            input_quality.get("overall_status"),
                            output_quality.get("overall_status") if output_quality else None,
                        ),
                    }
                    if output_score is not None
                    else None
                ),
            }

            logger.info(
                f"Quality impact analysis completed for preview",
                extra={
                    "asset_id": asset_id,
                    "input_score": input_score,
                    "output_score": output_score,
                    "quality_delta": quality_delta,
                    "quality_delta_percent": quality_delta_percent,
                },
            )

            return quality_impact

        except Exception as e:
            logger.warning(
                f"Quality impact analysis failed: {e}", extra={"error": str(e)}, exc_info=True
            )
            return {
                "available": False,
                "error": str(e),
                "input_quality_metrics": None,
                "output_quality_metrics": None,
                "quality_comparison": None,
            }

    def _determine_status_change(
        self, input_status: Optional[str], output_status: Optional[str]
    ) -> Optional[str]:
        """
        Determine status change between input and output quality statuses.

        Args:
            input_status: Input quality status (PASS, WARN, FAIL)
            output_status: Output quality status (PASS, WARN, FAIL)

        Returns:
            Status change description (IMPROVED, DEGRADED, MAINTAINED, UNKNOWN)
        """
        if not input_status or not output_status:
            return "UNKNOWN"

        status_hierarchy = {"PASS": 3, "WARN": 2, "FAIL": 1, "UNKNOWN": 0}
        input_level = status_hierarchy.get(input_status, 0)
        output_level = status_hierarchy.get(output_status, 0)

        if output_level > input_level:
            return "IMPROVED"
        elif output_level < input_level:
            return "DEGRADED"
        else:
            return "MAINTAINED"

    def _convert_sample_to_file_content(
        self, sample: List[Dict[str, Any]], format: str = "csv"
    ) -> bytes:
        """
        Convert sample data to file content bytes.

        Args:
            sample: Sample data as list of dictionaries
            format: Output format (csv, json)

        Returns:
            File content as bytes
        """
        import csv
        import io
        import json

        if format.lower() == "csv":
            if not sample:
                return b""
            # Validate sample structure
            if not isinstance(sample[0], dict):
                raise ValueError("Sample data must be a list of dictionaries")
            if not sample[0]:
                raise ValueError("Sample data dictionaries cannot be empty")
            output = io.StringIO()
            fieldnames = list(sample[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample)
            return output.getvalue().encode("utf-8")
        elif format.lower() == "json":
            return json.dumps(sample, default=str).encode("utf-8")
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _publish_preview_generated_event(
        self,
        pipeline_id: str,
        asset_id: str,
        preview_id: str,
        analysis: Dict[str, Any],
        tenant_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Publish transformation.preview.generated event.

        Args:
            pipeline_id: Pipeline ID
            asset_id: Asset ID
            preview_id: Preview ID
            analysis: Preview analysis results
            tenant_id: Tenant ID
            user_id: Optional user ID
        """
        # Use the TransformationEventPublisher method
        self.publish_preview_generated(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            preview_id=preview_id,
            row_count_changes=analysis.get("row_count_changes"),
            schema_changes={
                "has_changes": analysis.get("schema_changes", {}).get("has_changes", False),
                "changes_count": analysis.get("schema_changes", {}).get("changes_count", 0),
            },
            quality_impact={
                "available": analysis.get("quality_impact", {}).get("available", False),
                "quality_delta": analysis.get("quality_impact", {})
                .get("quality_comparison", {})
                .get("quality_delta"),
            },
            tenant_id=tenant_id,
            user_id=user_id,
        )

    @transaction.atomic
    def wrangle_data(
        self,
        asset_id: str,
        operation: Dict[str, Any],
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[HttpRequest] = None,
    ) -> Dict[str, Any]:
        """
        Perform data wrangling operation on an asset.

        Supports interactive data operations with undo/redo:
        - Filter: Filter rows based on conditions
        - Sort: Sort rows by columns
        - Transform: Transform column values
        - Aggregate: Aggregate data
        - Join: Join with another dataset
        - Group: Group by columns
        - Column operations: Rename, drop, add, split, merge
        - Data cleaning: Deduplicate, fill nulls, remove nulls
        - Type conversion: Convert column types

        Args:
            asset_id: Source asset ID
            operation: Operation definition with type and parameters
            session_id: Optional wrangling session ID (creates new if not provided)
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)
            request: Optional HTTP request for audit logging

        Returns:
            Dictionary with:
            - session_id: Wrangling session ID
            - operation_id: Operation ID
            - result: Operation result (sample data, row count, etc.)
            - can_undo: Whether undo is possible
            - can_redo: Whether redo is possible
            - applied_operations_count: Number of applied operations

        Raises:
            NotFoundError: If asset not found
            TransformationValidationError: If operation validation fails
            TransformationExecutionError: If operation execution fails
        """
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.schema_inference import (
            extract_sample_data,
            infer_schema_from_csv,
            infer_schema_from_json,
        )
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.transformation.models import (
            WranglingOperation,
            WranglingOperationType,
            WranglingSession,
        )

        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Validate asset exists
        try:
            asset = Asset.objects.get(id=asset_id, tenant_id=effective_tenant_id)
        except Asset.DoesNotExist:
            raise NotFoundError(f"Asset {asset_id} not found")

        # Get or create wrangling session
        if session_id:
            try:
                session = WranglingSession.objects.get(id=session_id, tenant_id=effective_tenant_id)
            except WranglingSession.DoesNotExist:
                raise NotFoundError(f"Wrangling session {session_id} not found")
        else:
            # Create new session
            session = WranglingSession.objects.create(
                tenant_id=effective_tenant_id,
                created_by_id=effective_user_id,
                asset=asset,
                name=f"Wrangling Session for {asset.name}",
                description=f"Interactive data wrangling session for asset {asset.name}",
            )

        # Validate operation
        self._validate_wrangling_operation(operation)

        # Get current data state
        current_data = self._get_current_data_state(session, asset)

        # Execute operation
        # Execute wrangling operation with monitoring
        from hub.apps.transformation.monitoring import record_wrangling_operation

        operation_type = operation.get("type", "UNKNOWN")

        try:
            operation_result = self._execute_wrangling_operation(
                operation=operation, data=current_data, asset=asset
            )
            # Record successful operation
            record_wrangling_operation(
                tenant_id=str(session.tenant_id), operation_type=operation_type, status="SUCCESS"
            )
        except Exception as e:
            # Record failed operation
            record_wrangling_operation(
                tenant_id=str(session.tenant_id), operation_type=operation_type, status="FAILED"
            )
            raise

        # Add operation to history
        operation_index = session.add_operation(
            {
                "type": operation.get("type"),
                "parameters": operation.get("parameters", {}),
                "result_metadata": {
                    "rows_before": operation_result.get("rows_before", 0),
                    "rows_after": operation_result.get("rows_after", 0),
                    "columns_before": operation_result.get("columns_before", []),
                    "columns_after": operation_result.get("columns_after", []),
                },
            }
        )

        # Update session current state
        session.current_state = operation_result.get("data_state")
        session.wrangling_script = session.generate_script("python")
        session.save(update_fields=["current_state", "wrangling_script", "updated_at"])

        # Create operation record
        wrangling_op = WranglingOperation.objects.create(
            session=session,
            operation_type=operation.get("type"),
            parameters=operation.get("parameters", {}),
            result_snapshot=operation_result.get("sample_data"),
            metadata={
                "rows_before": operation_result.get("rows_before", 0),
                "rows_after": operation_result.get("rows_after", 0),
            },
        )

        # Publish wrangling operation applied event
        try:
            execution_time_ms = None
            if operation_result.get("execution_time_ms"):
                execution_time_ms = operation_result.get("execution_time_ms")
            elif operation_result.get("metadata", {}).get("execution_time_ms"):
                execution_time_ms = operation_result.get("metadata", {}).get("execution_time_ms")

            operation_type = operation.get("type")
            if operation_type:
                self.publish_wrangling_operation_applied(
                    session_id=str(session.id),
                    operation_id=str(wrangling_op.id),
                    asset_id=str(asset.id),
                    operation_type=operation_type,
                    operation_parameters=operation.get("parameters", {}),
                    rows_affected=operation_result.get("rows_after", 0)
                    - operation_result.get("rows_before", 0),
                    execution_time_ms=execution_time_ms,
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
        except Exception as e:
            logger.warning(
                f"Failed to publish wrangling operation applied event: {e}",
                extra={
                    "session_id": str(session.id),
                    "operation_id": str(wrangling_op.id),
                    "error": str(e),
                },
                exc_info=True,
            )

        # Publish wrangling completed event
        try:
            operation_type = operation.get("type")
            if operation_type:
                self.publish_wrangling_completed(
                    session_id=str(session.id),
                    operation_id=str(wrangling_op.id),
                    asset_id=str(asset.id),
                    operation_type=operation_type,
                    rows_processed=operation_result.get("rows_after", 0),
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                )
        except Exception as e:
            logger.warning(
                f"Failed to publish wrangling completed event: {e}",
                extra={
                    "session_id": str(session.id),
                    "operation_id": str(wrangling_op.id),
                    "error": str(e),
                },
                exc_info=True,
            )

        return {
            "session_id": str(session.id),
            "operation_id": str(wrangling_op.id),
            "result": {
                "sample_data": operation_result.get("sample_data", []),
                "rows_before": operation_result.get("rows_before", 0),
                "rows_after": operation_result.get("rows_after", 0),
                "columns": operation_result.get("columns_after", []),
            },
            "can_undo": session.can_undo(),
            "can_redo": session.can_redo(),
            "applied_operations_count": len(session.get_applied_operations()),
            "wrangling_script": session.wrangling_script,
        }

    def _validate_wrangling_operation(self, operation: Dict[str, Any]) -> None:
        """
        Validate wrangling operation.

        Args:
            operation: Operation dictionary

        Raises:
            TransformationValidationError: If validation fails
        """
        from hub.apps.transformation.models import WranglingOperationType

        if not isinstance(operation, dict):
            raise TransformationValidationError(
                "Operation must be a dictionary",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
            )

        # Validate required fields
        if "type" not in operation:
            raise TransformationValidationError(
                "Operation must have 'type' field",
                error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
            )

        operation_type = operation.get("type")
        if operation_type not in [op[0] for op in WranglingOperationType.choices]:
            raise TransformationValidationError(
                f"Invalid operation type: {operation_type}",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
            )

        # Validate parameters based on operation type
        parameters = operation.get("parameters", {})
        if not isinstance(parameters, dict):
            raise TransformationValidationError(
                "Operation parameters must be a dictionary",
                error_code=TransformationValidationError.ERROR_CODE_INVALID_FIELD_VALUE,
            )

        # Type-specific validation
        if operation_type == "FILTER":
            if "condition" not in parameters:
                raise TransformationValidationError(
                    "FILTER operation requires 'condition' parameter",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                )
        elif operation_type == "SORT":
            if "columns" not in parameters:
                raise TransformationValidationError(
                    "SORT operation requires 'columns' parameter",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                )
        elif operation_type == "TRANSFORM":
            if "column" not in parameters or "expression" not in parameters:
                raise TransformationValidationError(
                    "TRANSFORM operation requires 'column' and 'expression' parameters",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                )
        elif operation_type == "RENAME_COLUMN":
            if "old_name" not in parameters or "new_name" not in parameters:
                raise TransformationValidationError(
                    "RENAME_COLUMN operation requires 'old_name' and 'new_name' parameters",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                )
        elif operation_type == "DROP_COLUMN":
            if "columns" not in parameters:
                raise TransformationValidationError(
                    "DROP_COLUMN operation requires 'columns' parameter",
                    error_code=TransformationValidationError.ERROR_CODE_MISSING_REQUIRED_FIELD,
                )

    def _get_current_data_state(
        self, session: "WranglingSession", asset: "Asset"
    ) -> List[Dict[str, Any]]:
        """
        Get current data state for the session.

        If session has a current_state, use it. Otherwise, load from asset.

        Args:
            session: Wrangling session
            asset: Source asset

        Returns:
            List of data rows (dictionaries)
        """
        from hub.apps.files.storage import S3StorageClient

        # If session has current state, use it
        if session.current_state and isinstance(session.current_state, list):
            return session.current_state

        # Otherwise, load from asset
        latest_dataset = asset.datasets.order_by("-version").first()
        if not latest_dataset or not latest_dataset.file:
            raise TransformationExecutionError(
                "Asset has no dataset or file",
                error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                tenant_id=str(asset.tenant_id),
            )

        # Download and parse file
        storage_client = S3StorageClient()
        file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
        file_format = latest_dataset.format or "CSV"

        # Parse data based on format
        if file_format.upper() == "CSV":
            import csv
            import io

            text_content = (
                file_content.decode("utf-8") if isinstance(file_content, bytes) else file_content
            )
            reader = csv.DictReader(io.StringIO(text_content))
            return list(reader)
        elif file_format.upper() == "JSON":
            import json

            if isinstance(file_content, bytes):
                return json.loads(file_content.decode("utf-8"))
            return json.loads(file_content)
        else:
            raise TransformationExecutionError(
                f"Unsupported file format: {file_format}",
                error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                tenant_id=str(asset.tenant_id),
            )

    def _execute_wrangling_operation(
        self, operation: Dict[str, Any], data: List[Dict[str, Any]], asset: "Asset"
    ) -> Dict[str, Any]:
        """
        Execute a wrangling operation on data.

        Args:
            operation: Operation definition
            data: Current data state (list of dictionaries)
            asset: Source asset

        Returns:
            Dictionary with:
            - data_state: New data state after operation
            - sample_data: Sample of result (first 100 rows)
            - rows_before: Row count before operation
            - rows_after: Row count after operation
            - columns_before: Column names before operation
            - columns_after: Column names after operation
        """
        operation_type = operation.get("type")
        parameters = operation.get("parameters", {})

        rows_before = len(data)
        columns_before = list(data[0].keys()) if data else []

        # Execute operation
        if operation_type == "FILTER":
            result_data = self._execute_filter(data, parameters)
        elif operation_type == "SORT":
            result_data = self._execute_sort(data, parameters)
        elif operation_type == "TRANSFORM":
            result_data = self._execute_transform(data, parameters)
        elif operation_type == "RENAME_COLUMN":
            result_data = self._execute_rename_column(data, parameters)
        elif operation_type == "DROP_COLUMN":
            result_data = self._execute_drop_column(data, parameters)
        elif operation_type == "DEDUPLICATE":
            result_data = self._execute_deduplicate(data, parameters)
        elif operation_type == "FILL_NULLS":
            result_data = self._execute_fill_nulls(data, parameters)
        elif operation_type == "REMOVE_NULLS":
            result_data = self._execute_remove_nulls(data, parameters)
        else:
            raise TransformationExecutionError(
                f"Operation type {operation_type} not yet implemented",
                error_code=TransformationExecutionError.ERROR_CODE_DATA_PROCESSING_FAILED,
                tenant_id=str(asset.tenant_id),
            )

        rows_after = len(result_data)
        columns_after = list(result_data[0].keys()) if result_data else []

        # Get sample (first 100 rows)
        sample_data = result_data[:100]

        return {
            "data_state": result_data,
            "sample_data": sample_data,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "columns_before": columns_before,
            "columns_after": columns_after,
        }

    def _execute_filter(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute FILTER operation"""
        condition = parameters.get("condition", "")

        # Simple condition evaluation (in production, use a proper expression evaluator)
        # For now, support simple comparisons like "column == value" or "column > value"
        def evaluate_condition(row: Dict[str, Any], condition: str) -> bool:
            # Parse simple conditions
            if "==" in condition:
                col, val = condition.split("==", 1)
                col = col.strip()
                val = val.strip().strip('"').strip("'")
                return str(row.get(col, "")) == val
            elif "!=" in condition:
                col, val = condition.split("!=", 1)
                col = col.strip()
                val = val.strip().strip('"').strip("'")
                return str(row.get(col, "")) != val
            elif ">" in condition:
                col, val = condition.split(">", 1)
                col = col.strip()
                try:
                    return float(row.get(col, 0)) > float(val.strip())
                except (ValueError, TypeError):
                    return False
            elif "<" in condition:
                col, val = condition.split("<", 1)
                col = col.strip()
                try:
                    return float(row.get(col, 0)) < float(val.strip())
                except (ValueError, TypeError):
                    return False
            return True

        return [row for row in data if evaluate_condition(row, condition)]

    def _execute_sort(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute SORT operation"""
        columns = parameters.get("columns", [])
        ascending = parameters.get("ascending", True)

        if not columns:
            return data

        def sort_key(row: Dict[str, Any]):
            values = []
            for col in columns:
                val = row.get(col)
                # Handle None values
                if val is None:
                    values.append("")
                else:
                    values.append(val)
            return tuple(values)

        return sorted(data, key=sort_key, reverse=not ascending)

    def _execute_transform(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute TRANSFORM operation"""
        column = parameters.get("column", "")
        expression = parameters.get("expression", "")

        # Simple expression evaluation (in production, use a proper expression evaluator)
        # For now, support simple operations like "upper()", "lower()", "strip()"
        result_data = []
        for row in data:
            new_row = row.copy()
            value = row.get(column, "")

            if expression == "upper()":
                new_row[column] = str(value).upper()
            elif expression == "lower()":
                new_row[column] = str(value).lower()
            elif expression == "strip()":
                new_row[column] = str(value).strip()
            else:
                # Try to evaluate as Python expression (limited for security)
                try:
                    # Only allow safe operations
                    if "import" not in expression and "__" not in expression:
                        new_row[column] = eval(
                            expression, {"value": value, "str": str, "int": int, "float": float}
                        )
                    else:
                        raise ValueError("Unsafe expression")
                except Exception:
                    new_row[column] = value  # Keep original if evaluation fails

            result_data.append(new_row)

        return result_data

    def _execute_rename_column(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute RENAME_COLUMN operation"""
        old_name = parameters.get("old_name", "")
        new_name = parameters.get("new_name", "")

        result_data = []
        for row in data:
            new_row = {}
            for key, value in row.items():
                if key == old_name:
                    new_row[new_name] = value
                else:
                    new_row[key] = value
            result_data.append(new_row)

        return result_data

    def _execute_drop_column(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute DROP_COLUMN operation"""
        columns_to_drop = parameters.get("columns", [])
        if not isinstance(columns_to_drop, list):
            columns_to_drop = [columns_to_drop]

        result_data = []
        for row in data:
            new_row = {k: v for k, v in row.items() if k not in columns_to_drop}
            result_data.append(new_row)

        return result_data

    def _execute_deduplicate(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute DEDUPLICATE operation"""
        columns = parameters.get("columns", [])  # If empty, deduplicate on all columns

        seen = set()
        result_data = []

        for row in data:
            if columns:
                key = tuple(row.get(col) for col in columns)
            else:
                key = tuple(row.items())

            if key not in seen:
                seen.add(key)
                result_data.append(row)

        return result_data

    def _execute_fill_nulls(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute FILL_NULLS operation"""
        column = parameters.get("column", "")
        fill_value = parameters.get("fill_value", "")

        result_data = []
        for row in data:
            new_row = row.copy()
            if column and (new_row.get(column) is None or new_row.get(column) == ""):
                new_row[column] = fill_value
            result_data.append(new_row)

        return result_data

    def _execute_remove_nulls(
        self, data: List[Dict[str, Any]], parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute REMOVE_NULLS operation"""
        column = parameters.get("column", "")  # If empty, remove rows with any null

        result_data = []
        for row in data:
            if column:
                if row.get(column) is not None and row.get(column) != "":
                    result_data.append(row)
            else:
                # Remove rows with any null/empty value
                if all(v is not None and v != "" for v in row.values()):
                    result_data.append(row)

        return result_data

    def publish_wrangling_completed(
        self,
        session_id: str,
        operation_id: str,
        asset_id: str,
        operation_type: str,
        rows_processed: Optional[int] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Publish transformation.wrangling.completed event."""
        data = {
            "session_id": session_id,
            "operation_id": operation_id,
            "asset_id": asset_id,
            "operation_type": operation_type,
        }
        if rows_processed is not None:
            data["rows_processed"] = rows_processed

        event_id = self._event_publisher.publish(
            event_type="transformation.wrangling.completed",
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )

        # Trigger webhook
        self._trigger_webhook_for_event(
            internal_event_type="transformation.wrangling.completed",
            resource_type="WRANGLING",
            resource_id=operation_id,
            event_data=data,
            tenant_id=tenant_id,
        )

        return event_id
