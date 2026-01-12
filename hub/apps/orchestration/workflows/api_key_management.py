"""
API Key Management Workflow

Orchestrates API key creation and revocation operations with proper error handling,
retry logic, compensation, and progress tracking.

Workflow Steps for API Key Creation:
1. validate_request - Validate API key creation request
2. check_permissions - Check user permissions
3. check_quota - Check tenant quota limits
4. generate_key - Generate secure API key
5. store_key - Store API key (hashed) in database
6. notify_user - Send notification to user
7. complete - Mark workflow as completed

Workflow Steps for API Key Revocation:
1. validate_revocation - Validate revocation request
2. revoke_key - Mark API key as revoked
3. notify_user - Send notification to user
4. complete - Mark workflow as completed
"""
import structlog
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.baas.models import APIKey, APITierModel
from hub.apps.baas.business_rules import BaaSBusinessRules
from hub.apps.core.events.publisher import EventPublisher
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)

User = get_user_model()


class APIKeyManagementWorkflow:
    """
    API key management workflow orchestrator.

    Manages the complete API key lifecycle:
    1. API key creation with validation, quota checks, and notifications
    2. API key revocation with validation and notifications
    """

    WORKFLOW_NAME = "api_key_management"
    WORKFLOW_VERSION = "1.0.0"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the API key management workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                # Creation workflow steps (skipped for revocation)
                {
                    "name": "validate_request",
                    "type": "task",
                    "task": "api_key_management.validate_request"
                },
                {
                    "name": "check_permissions",
                    "type": "task",
                    "task": "api_key_management.check_permissions"
                },
                {
                    "name": "check_quota",
                    "type": "task",
                    "task": "api_key_management.check_quota"
                },
                {
                    "name": "generate_key",
                    "type": "task",
                    "task": "api_key_management.generate_key",
                    "compensation": {
                        "type": "task",
                        "task": "api_key_management.rollback_key_generation"
                    }
                },
                {
                    "name": "store_key",
                    "type": "task",
                    "task": "api_key_management.store_key",
                    "compensation": {
                        "type": "task",
                        "task": "api_key_management.rollback_key_generation"
                    }
                },
                # Revocation workflow steps (skipped for creation)
                {
                    "name": "validate_revocation",
                    "type": "task",
                    "task": "api_key_management.validate_revocation"
                },
                {
                    "name": "revoke_key",
                    "type": "task",
                    "task": "api_key_management.revoke_key",
                    "compensation": {
                        "type": "task",
                        "task": "api_key_management.rollback_key_revocation"
                    }
                },
                # Common steps (executed for both operations)
                {
                    "name": "notify_user",
                    "type": "task",
                    "task": "api_key_management.notify_user"
                },
                {
                    "name": "complete",
                    "type": "task",
                    "task": "api_key_management.complete"
                }
            ],
            "compensation": {
                "enabled": True
            }
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates API key creation and revocation with validation, quota checks, and notifications"
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow task functions.

        Args:
            engine: WorkflowEngine instance
        """
        # API key creation tasks
        engine.register_task("api_key_management.validate_request", cls._validate_request_task)
        engine.register_task("api_key_management.check_permissions", cls._check_permissions_task)
        engine.register_task("api_key_management.check_quota", cls._check_quota_task)
        engine.register_task("api_key_management.generate_key", cls._generate_key_task)
        engine.register_task("api_key_management.store_key", cls._store_key_task)
        engine.register_task("api_key_management.notify_user", cls._notify_user_task)
        engine.register_task("api_key_management.complete", cls._complete_task)

        # API key revocation tasks
        engine.register_task("api_key_management.validate_revocation", cls._validate_revocation_task)
        engine.register_task("api_key_management.revoke_key", cls._revoke_key_task)

        # Compensation tasks
        engine.register_task("api_key_management.rollback_key_generation", cls._rollback_key_generation_task)
        engine.register_task("api_key_management.rollback_key_revocation", cls._rollback_key_revocation_task)

    @staticmethod
    def _validate_request_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate API key creation request.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        operation = input_data.get("operation", "create")

        # Skip if not a creation operation
        if operation != "create":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        tenant_id = input_data.get("tenant_id")
        user_id = input_data.get("user_id")
        name = input_data.get("name")
        tier_name = input_data.get("tier", "FREE")
        expires_at = input_data.get("expires_at")

        # Validate required fields
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not user_id:
            raise ValueError("user_id is required")
        if not name:
            raise ValueError("name is required")

        # Get tenant and user
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant {tenant_id} not found")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User {user_id} not found")

        # Validate tier exists
        try:
            tier = APITierModel.objects.get(name=tier_name)
        except APITierModel.DoesNotExist:
            raise ValidationError(f"Invalid tier: {tier_name}")

        # Parse expires_at if it's a string (ISO format)
        expires_at_parsed = None
        if expires_at:
            if isinstance(expires_at, str):
                # Parse ISO string to datetime
                from django.utils.dateparse import parse_datetime
                expires_at_parsed = parse_datetime(expires_at)
                if not expires_at_parsed:
                    # Try alternative parsing with dateutil
                    try:
                        from dateutil import parser as date_parser
                        expires_at_parsed = date_parser.parse(expires_at)
                    except ImportError:
                        # dateutil not available, try manual parsing
                        from datetime import datetime
                        expires_at_parsed = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            else:
                # Already a datetime object
                expires_at_parsed = expires_at

        # Validate using business rules
        rules = BaaSBusinessRules(tenant_id=str(tenant_id), user_id=str(user_id))

        # Create temporary API key object for validation (not saved)
        temp_api_key = APIKey(
            tenant=tenant,
            user=user,
            tier=tier,
            name=name,
            expires_at=expires_at_parsed,
            key_hash=""  # Placeholder, will be set during generation
        )

        validation_result = rules.validate_api_key_creation(
            api_key=temp_api_key,
            tenant=tenant,
            user=user
        )

        if not validation_result.is_valid:
            raise ValidationError(
                f"API key creation validation failed: {', '.join(validation_result.errors)}",
                code="API_KEY_CREATION_VALIDATION_FAILED",
                details=validation_result.details
            )

        logger.info(
            "API key creation request validated",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            user_id=user_id,
            tier=tier_name
        )

        # Publish workflow started event
        try:
            event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=tenant_id,
                user_id=user_id
            )
            event_publisher.publish(
                event_type="workflow.api_key_management.started",
                data={
                    "workflow_instance_id": str(instance.id),
                    "operation": "create",
                    "status": "started"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish workflow started event: {e}")

        # Handle expires_at - it may be a datetime object or ISO string
        expires_at_str = None
        if expires_at:
            if isinstance(expires_at, str):
                # Already an ISO string, use as-is
                expires_at_str = expires_at
            else:
                # datetime object, convert to ISO string
                expires_at_str = expires_at.isoformat()

        return {
            "validated": True,
            "state": {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "name": name,
                "tier_name": tier_name,
                "tier_id": str(tier.id),
                "expires_at": expires_at_str,
                "operation": "create"
            }
        }

    @staticmethod
    def _check_permissions_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Check user permissions for API key creation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with permission check results
        """
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))

        # Skip if not a creation operation
        if operation != "create":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")

        # Get tenant and user
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        # Check permissions using business rules
        rules = BaaSBusinessRules(tenant_id=str(tenant_id), user_id=str(user_id))

        # Create temporary API key for permission check
        temp_api_key = APIKey(
            tenant=tenant,
            user=user,
            key_hash=""
        )

        permissions_result = rules.validate_api_key_permissions(
            api_key=temp_api_key,
            tenant=tenant,
            user=user
        )

        if not permissions_result.is_valid:
            raise ValidationError(
                f"Permission check failed: {', '.join(permissions_result.errors)}",
                code="PERMISSION_CHECK_FAILED",
                details=permissions_result.details
            )

        logger.info(
            "User permissions checked",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id,
            user_id=user_id
        )

        return {
            "permissions_checked": True,
            "state": {
                "permissions_valid": True
            }
        }

    @staticmethod
    def _check_quota_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Check tenant quota limits for API key creation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with quota check results
        """
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))

        # Skip if not a creation operation
        if operation != "create":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        tier_id = instance.state_data.get("tier_id")

        # Get tenant
        tenant = Tenant.objects.get(id=tenant_id)

        # Get tier
        if tier_id:
            tier = APITierModel.objects.get(id=tier_id)
        else:
            # Fallback to FREE tier if not specified
            tier = APITierModel.objects.get(name="FREE")

        # Check quota using business rules
        rules = BaaSBusinessRules(tenant_id=str(tenant_id), user_id=str(user_id))

        # Create temporary API key for quota check
        temp_api_key = APIKey(
            tenant=tenant,
            user=User.objects.get(id=user_id),
            tier=tier,
            key_hash=""
        )

        quota_result = rules.validate_quota(
            api_key=temp_api_key,
            tenant=tenant,
            user=temp_api_key.user
        )

        if not quota_result.is_valid:
            raise ValidationError(
                f"Quota check failed: {', '.join(quota_result.errors)}",
                code="QUOTA_CHECK_FAILED",
                details=quota_result.details
            )

        logger.info(
            "Tenant quota checked",
            workflow_instance_id=str(instance.id),
            tenant_id=tenant_id
        )

        return {
            "quota_checked": True,
            "state": {
                "quota_valid": True
            }
        }

    @staticmethod
    def _generate_key_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Generate secure API key.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with generated key
        """
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))

        # Skip if not a creation operation
        if operation != "create":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        # Generate secure API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        logger.info(
            "API key generated",
            workflow_instance_id=str(instance.id)
        )

        return {
            "plaintext_key": plaintext_key,
            "key_hash": key_hash,
            "state": {
                "plaintext_key": plaintext_key,
                "key_hash": key_hash
            }
        }

    @staticmethod
    @transaction.atomic
    def _store_key_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Store API key (hashed) in database.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with stored API key ID
        """
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))

        # Skip if not a creation operation
        if operation != "create":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        name = instance.state_data.get("name")
        tier_id = instance.state_data.get("tier_id")
        expires_at_str = instance.state_data.get("expires_at")
        key_hash = instance.state_data.get("key_hash")

        if not key_hash:
            raise ValueError("key_hash is required for storing API key")

        # Get tenant, user, and tier
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
        tier = APITierModel.objects.get(id=tier_id)

        # Parse expires_at if provided
        expires_at = None
        if expires_at_str:
            from django.utils.dateparse import parse_datetime
            expires_at = parse_datetime(expires_at_str)

        # Create API key
        api_key = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            tier=tier,
            name=name,
            expires_at=expires_at
        )

        logger.info(
            "API key stored",
            workflow_instance_id=str(instance.id),
            api_key_id=str(api_key.id),
            tenant_id=tenant_id
        )

        return {
            "api_key_id": str(api_key.id),
            "state": {
                "api_key_id": str(api_key.id)
            }
        }

    @staticmethod
    def _notify_user_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Send notification to user.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with notification results
        """
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        api_key_id = instance.state_data.get("api_key_id")
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))  # "create" or "revoke"

        # Get user
        user = User.objects.get(id=user_id)

        # Publish workflow step completed event
        try:
            event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=tenant_id,
                user_id=user_id
            )
            event_publisher.publish(
                event_type="workflow.api_key_management.step_completed",
                data={
                    "workflow_instance_id": str(instance.id),
                    "step": "notify_user",
                    "operation": operation,
                    "api_key_id": api_key_id,
                    "status": "completed"
                }
            )
        except Exception as e:
            # Log but don't fail on event publishing failure
            logger.warning(
                "Failed to publish notification event",
                workflow_instance_id=str(instance.id),
                error=str(e)
            )

        # Send email notification (non-blocking, async)
        try:
            from hub.apps.notifications.tasks import send_email_async
            from hub.apps.notifications.models import EmailType

            if operation == "create":
                send_email_async.delay(
                    email_type=EmailType.API_KEY_CREATED,
                    to_email=user.email,
                    subject="API Key Created",
                    template_name="notifications/emails/api_key_created.html",
                    context={
                        "user_name": user.get_full_name() or user.email,
                        "api_key_name": instance.state_data.get("name", "API Key"),
                        "tenant_name": Tenant.objects.get(id=tenant_id).name
                    },
                    tenant_id=tenant_id,
                    user_id=user_id
                )
            elif operation == "revoke":
                send_email_async.delay(
                    email_type=EmailType.API_KEY_REVOKED,
                    to_email=user.email,
                    subject="API Key Revoked",
                    template_name="notifications/emails/api_key_revoked.html",
                    context={
                        "user_name": user.get_full_name() or user.email,
                        "api_key_name": instance.state_data.get("name", "API Key"),
                        "tenant_name": Tenant.objects.get(id=tenant_id).name
                    },
                    tenant_id=tenant_id,
                    user_id=user_id
                )
        except Exception as e:
            # Log but don't fail on notification failure (non-critical)
            logger.warning(
                "Failed to send notification email",
                workflow_instance_id=str(instance.id),
                error=str(e)
            )

        logger.info(
            "User notification sent",
            workflow_instance_id=str(instance.id),
            operation=operation
        )

        return {
            "notified": True,
            "state": {
                "notification_sent": True
            }
        }

    @staticmethod
    def _complete_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Mark workflow as completed.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with completion status
        """
        tenant_id = instance.state_data.get("tenant_id")
        user_id = instance.state_data.get("user_id")
        api_key_id = instance.state_data.get("api_key_id")
        operation = instance.state_data.get("operation", input_data.get("operation", "create"))

        # Publish workflow completion event
        try:
            event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=tenant_id,
                user_id=user_id
            )

            event_publisher.publish(
                event_type="workflow.api_key_management.completed",
                data={
                    "workflow_instance_id": str(instance.id),
                    "operation": operation,
                    "api_key_id": api_key_id,
                    "status": "completed"
                }
            )
        except Exception as e:
            logger.warning(
                "Failed to publish workflow completion event",
                workflow_instance_id=str(instance.id),
                error=str(e)
            )

        logger.info(
            "API key management workflow completed",
            workflow_instance_id=str(instance.id),
            operation=operation,
            api_key_id=api_key_id
        )

        return {
            "completed": True,
            "state": {
                "workflow_completed": True
            }
        }

    # API Key Revocation Tasks

    @staticmethod
    def _validate_revocation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate revocation request.

        This task is called for revocation operations. It validates the revocation request
        and sets up the workflow state for revocation steps.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation results
        """
        operation = input_data.get("operation", "revoke")

        # Only process revocation operations
        if operation != "revoke":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        api_key_id = input_data.get("api_key_id")
        tenant_id = input_data.get("tenant_id")
        user_id = input_data.get("user_id")

        if not api_key_id:
            raise ValueError("api_key_id is required for revocation")

        # Get API key
        try:
            api_key = APIKey.objects.select_related('tenant', 'user').get(id=api_key_id)
        except APIKey.DoesNotExist:
            raise NotFoundError(f"API key {api_key_id} not found")

        # Validate tenant isolation
        if tenant_id and str(api_key.tenant_id) != str(tenant_id):
            raise ValidationError(
                "Cannot revoke API key from different tenant",
                code="TENANT_MISMATCH"
            )

        # Check if already revoked
        if api_key.revoked_at is not None:
            raise ValidationError(
                "API key is already revoked",
                code="ALREADY_REVOKED"
            )

        # Publish workflow started event for revocation
        try:
            event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=str(api_key.tenant_id),
                user_id=str(api_key.user_id)
            )
            event_publisher.publish(
                event_type="workflow.api_key_management.started",
                data={
                    "workflow_instance_id": str(instance.id),
                    "operation": "revoke",
                    "status": "started"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish workflow started event: {e}")

        logger.info(
            "API key revocation request validated",
            workflow_instance_id=str(instance.id),
            api_key_id=api_key_id
        )

        return {
            "validated": True,
            "state": {
                "api_key_id": api_key_id,
                "tenant_id": str(api_key.tenant_id),
                "user_id": str(api_key.user_id),
                "name": api_key.name,
                "operation": "revoke"
            }
        }

    @staticmethod
    @transaction.atomic
    def _revoke_key_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Mark API key as revoked.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with revocation results
        """
        operation = instance.state_data.get("operation", input_data.get("operation", "revoke"))

        # Only process revocation operations
        if operation != "revoke":
            return {
                "skipped": True,
                "reason": f"Step not applicable for operation: {operation}"
            }

        api_key_id = instance.state_data.get("api_key_id")

        # Get API key
        api_key = APIKey.objects.get(id=api_key_id)

        # Revoke the key
        api_key.revoke()

        # Publish step completed event
        try:
            event_publisher = EventPublisher(
                service_name="workflow_engine",
                tenant_id=str(api_key.tenant_id),
                user_id=str(api_key.user_id)
            )
            event_publisher.publish(
                event_type="workflow.api_key_management.step_completed",
                data={
                    "workflow_instance_id": str(instance.id),
                    "step": "revoke_key",
                    "operation": "revoke",
                    "api_key_id": api_key_id,
                    "status": "completed"
                }
            )
        except Exception as e:
            logger.warning(f"Failed to publish step completed event: {e}")

        logger.info(
            "API key revoked",
            workflow_instance_id=str(instance.id),
            api_key_id=api_key_id
        )

        return {
            "revoked": True,
            "state": {
                "revoked_at": api_key.revoked_at.isoformat() if api_key.revoked_at else None
            }
        }

    # Compensation Tasks

    @staticmethod
    @transaction.atomic
    def _rollback_key_generation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback key generation - delete generated key if storage fails.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback results
        """
        api_key_id = instance.state_data.get("api_key_id")

        if api_key_id:
            try:
                api_key = APIKey.objects.get(id=api_key_id)
                api_key.delete()
                logger.info(
                    "API key generation rolled back (deleted)",
                    workflow_instance_id=str(instance.id),
                    api_key_id=api_key_id
                )
            except APIKey.DoesNotExist:
                logger.warning(
                    "API key not found for rollback",
                    workflow_instance_id=str(instance.id),
                    api_key_id=api_key_id
                )

        return {"rolled_back": True}

    @staticmethod
    @transaction.atomic
    def _rollback_key_revocation_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback key revocation - restore revoked key if notification fails.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback results
        """
        api_key_id = instance.state_data.get("api_key_id")

        if api_key_id:
            try:
                api_key = APIKey.objects.get(id=api_key_id)
                if api_key.revoked_at is not None:
                    api_key.revoked_at = None
                    api_key.save(update_fields=['revoked_at', 'updated_at'])
                    logger.info(
                        "API key revocation rolled back (restored)",
                        workflow_instance_id=str(instance.id),
                        api_key_id=api_key_id
                    )
            except APIKey.DoesNotExist:
                logger.warning(
                    "API key not found for rollback",
                    workflow_instance_id=str(instance.id),
                    api_key_id=api_key_id
                )

        return {"rolled_back": True}
