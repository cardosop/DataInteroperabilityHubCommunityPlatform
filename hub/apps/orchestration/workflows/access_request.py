"""
Access Request Workflow

Orchestrates the access request process with proper error handling,
approval routing, timeout handling, escalation, and compensation.
"""

from datetime import timedelta
from typing import Any

import structlog
from dateutil import parser as date_parser
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.governance.business_rules import GovernanceBusinessRules
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
    ClassificationCategory,
    DataClassification,
)
from hub.apps.notifications.models import EmailType
from hub.apps.notifications.tasks import send_email_async
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine

logger = structlog.get_logger(__name__)


class AccessRequestWorkflow:
    """
    Access request workflow orchestrator.

    Manages the complete access request process:
    1. Create access request
    2. Classify request (auto-classification based on resource)
    3. Route to approvers (single/multi-step based on classification)
    4. Wait for approvals (with timeout and escalation)
    5. Grant access (if approved)
    6. Send notifications
    7. Audit logging
    """

    WORKFLOW_NAME = "access_request"

    # Default timeout for approval steps (in hours)
    DEFAULT_APPROVAL_TIMEOUT_HOURS = 48

    # Escalation delay (in hours) before escalating
    ESCALATION_DELAY_HOURS = 24

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the access request workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "create_access_request",
                    "type": "task",
                    "task": "access_request.create_access_request",
                },
                {
                    "name": "classify_request",
                    "type": "task",
                    "task": "access_request.classify_request",
                },
                {
                    "name": "route_to_approvers",
                    "type": "task",
                    "task": "access_request.route_to_approvers",
                },
                {
                    "name": "wait_for_approvals",
                    "type": "conditional",
                    "condition": {
                        "operator": "equals",
                        "field": "requires_approval",
                        "value": True,
                    },
                    "then": [
                        {
                            "name": "process_approval_steps",
                            "type": "loop",
                            "items": "${approval_steps}",
                            "steps": [
                                {
                                    "name": "wait_for_step_approval",
                                    "type": "task",
                                    "task": "access_request.wait_for_step_approval",
                                    "retry": {
                                        "max_retries": 1,
                                        "delay_seconds": 3600,  # Check every hour
                                    },
                                },
                                {
                                    "name": "escalate_if_timeout",
                                    "type": "task",
                                    "task": "access_request.escalate_approval",
                                },
                            ],
                        }
                    ],
                    "else": [],
                },
                {
                    "name": "grant_access",
                    "type": "conditional",
                    "condition": {"operator": "equals", "field": "status", "value": "APPROVED"},
                    "then": [
                        {
                            "name": "grant_access_task",
                            "type": "task",
                            "task": "access_request.grant_access",
                            "compensation": {
                                "type": "task",
                                "task": "access_request.revoke_access",
                            },
                        }
                    ],
                    "else": [],
                },
                {
                    "name": "send_notifications",
                    "type": "task",
                    "task": "access_request.send_notifications",
                },
                {"name": "audit_logging", "type": "task", "task": "access_request.audit_logging"},
            ],
            "compensation": {"enabled": True},
        }
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates access request creation, classification, approval routing, and access granting",
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow tasks.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task(
            "access_request.create_access_request", cls._create_access_request_task
        )
        engine.register_task("access_request.classify_request", cls._classify_request_task)
        engine.register_task("access_request.route_to_approvers", cls._route_to_approvers_task)
        engine.register_task(
            "access_request.wait_for_step_approval", cls._wait_for_step_approval_task
        )
        engine.register_task("access_request.escalate_approval", cls._escalate_approval_task)
        engine.register_task("access_request.grant_access", cls._grant_access_task)
        engine.register_task("access_request.revoke_access", cls._revoke_access_task)
        engine.register_task("access_request.send_notifications", cls._send_notifications_task)
        engine.register_task("access_request.audit_logging", cls._audit_logging_task)

    @staticmethod
    def _create_access_request_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Create access request record.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with access request details
        """
        tenant_id = input_data.get("tenant_id")
        requested_by_id = input_data.get("requested_by_id")
        asset_id = input_data.get("asset_id")
        dataset_id = input_data.get("dataset_id")
        file_id = input_data.get("file_id")
        reason = input_data.get("reason") or "Access request"
        requested_access_type = input_data.get("requested_access_type", "READ")
        expires_at_str = input_data.get("expires_at")

        if not tenant_id or not requested_by_id:
            raise ValueError("tenant_id and requested_by_id are required")

        if not asset_id and not dataset_id and not file_id:
            raise ValueError("At least one of asset_id, dataset_id, or file_id must be provided")

        # Get resource objects
        # Note: For cross-tenant access requests, assets/datasets/files may belong to different tenants
        # We allow lookups without tenant filtering, but the access request itself belongs to the requesting tenant
        asset = None
        dataset = None
        file_obj = None

        if asset_id:
            from hub.apps.assets.models import Asset

            try:
                asset = Asset.objects.get(id=asset_id)
            except Asset.DoesNotExist:
                raise ValueError(f"Asset with id {asset_id} not found")

        if dataset_id:
            from hub.apps.datasets.models import Dataset

            try:
                dataset = Dataset.objects.get(id=dataset_id)
            except Dataset.DoesNotExist:
                raise ValueError(f"Dataset with id {dataset_id} not found")

        if file_id:
            from hub.apps.files.models import File

            try:
                file_obj = File.objects.get(id=file_id)
            except File.DoesNotExist:
                raise ValueError(f"File with id {file_id} not found")

        # Parse expiration date if provided
        expires_at = None
        if expires_at_str:
            expires_at = date_parser.parse(expires_at_str)

        # Create access request (approval workflow will be determined later)
        access_request = AccessRequest.objects.create(
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            reason=reason,
            requested_access_type=requested_access_type,
            requires_approval=True,  # Will be determined by classification
            expires_at=expires_at,
            status=AccessRequestStatus.PENDING.value,
        )

        # Validate access request using GovernanceBusinessRules
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=requested_by_id)

        governance_rules = GovernanceBusinessRules(
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(requested_by_id) if requested_by_id else None,
        )

        # Validate access request
        access_request_validation_result = governance_rules.validate(
            access_request=access_request,
            tenant=tenant,
            user=user,
            validation_type="access_request",
        )

        if not access_request_validation_result.is_valid:
            error_messages = access_request_validation_result.errors
            # Log errors but don't fail - access request is already created
            logger.warning(
                "Access request validation errors after creation",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                errors=error_messages,
            )
        elif access_request_validation_result.warnings:
            logger.warning(
                "Access request validation warnings",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                warnings=access_request_validation_result.warnings,
            )

        logger.info(
            "Access request created",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            tenant_id=tenant_id,
            requested_by_id=requested_by_id,
        )

        # Store access_request_id in state_data for subsequent steps
        instance.state_data["access_request_id"] = str(access_request.id)
        instance.save(update_fields=["state_data"])

        return {
            "access_request_id": str(access_request.id),
            "tenant_id": tenant_id,
            "requested_by_id": requested_by_id,
            "asset_id": asset_id,
            "dataset_id": dataset_id,
            "file_id": file_id,
            "reason": reason,
            "requested_access_type": requested_access_type,
            "expires_at": expires_at_str,
            "status": AccessRequestStatus.PENDING.value,
        }

    @staticmethod
    def _classify_request_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Classify access request based on resource classification.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with classification details
        """
        access_request_id = input_data.get("access_request_id")
        if not access_request_id:
            # Get from previous step output
            access_request_id = instance.state_data.get("access_request_id")

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)

        # Determine resource type and get classifications
        resource_type = None
        resource_id = None
        highest_classification = None

        if access_request.asset:
            resource_type = "ASSET"
            resource_id = str(access_request.asset.id)
            # Get highest classification for asset
            classifications = DataClassification.objects.filter(
                tenant_id=access_request.tenant_id, asset_id=resource_id, status="APPROVED"
            )
        elif access_request.dataset:
            resource_type = "DATASET"
            resource_id = str(access_request.dataset.id)
            classifications = DataClassification.objects.filter(
                tenant_id=access_request.tenant_id, dataset_id=resource_id, status="APPROVED"
            )
        elif access_request.file:
            resource_type = "FILE"
            resource_id = str(access_request.file.id)
            # File has reverse relation 'datasets' (Dataset.file FK), not 'dataset'
            dataset_for_file = access_request.file.datasets.first()
            if dataset_for_file:
                classifications = DataClassification.objects.filter(
                    tenant_id=access_request.tenant_id,
                    dataset_id=str(dataset_for_file.id),
                    status="APPROVED",
                )
            else:
                classifications = DataClassification.objects.none()
        else:
            raise ValueError("No resource found for classification")

        # Get highest classification
        if classifications.exists():
            classification_priority = {
                ClassificationCategory.PUBLIC: 1,
                ClassificationCategory.INTERNAL: 2,
                ClassificationCategory.CONFIDENTIAL: 3,
                ClassificationCategory.RESTRICTED: 4,
                ClassificationCategory.PII: 5,
                ClassificationCategory.PHI: 5,
                ClassificationCategory.PCI: 5,
            }
            highest = max(classifications, key=lambda c: classification_priority.get(c.category, 0))
            highest_classification = highest.category

        # Determine if approval is required: caller override or classification-based
        requires_approval = True
        caller_requires_approval = input_data.get("requires_approval")
        if caller_requires_approval is False:
            requires_approval = False
        elif caller_requires_approval is True:
            requires_approval = True
        elif (
            highest_classification
            in [
                ClassificationCategory.PUBLIC,
                ClassificationCategory.INTERNAL,
            ]
            and access_request.requested_access_type == "READ"
        ):
            requires_approval = False

        logger.info(
            "Access request classified",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            resource_type=resource_type,
            highest_classification=highest_classification,
            requires_approval=requires_approval,
        )

        return {
            "access_request_id": str(access_request.id),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "highest_classification": highest_classification,
            "requires_approval": requires_approval,
        }

    @staticmethod
    def _route_to_approvers_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Route access request to approvers based on classification and workflow rules.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with approval workflow details
        """
        access_request_id = instance.state_data.get("access_request_id")
        if not access_request_id:
            access_request_id = input_data.get("access_request_id")

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)
        requires_approval = instance.state_data.get("requires_approval", True)
        highest_classification = instance.state_data.get("highest_classification")

        # If no approval required, auto-approve
        if not requires_approval:
            access_request.requires_approval = False
            access_request.status = AccessRequestStatus.APPROVED.value
            access_request.approved_by_id = access_request.requested_by_id
            access_request.approved_at = timezone.now()
            access_request.access_granted_at = timezone.now()
            access_request.save()

            logger.info(
                "Access request auto-approved",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
            )

            return {
                "access_request_id": str(access_request.id),
                "requires_approval": False,
                "approval_steps": [],
                "status": AccessRequestStatus.APPROVED.value,
            }

        # Determine approval workflow based on classification
        approval_workflow = []

        if highest_classification in [
            ClassificationCategory.CONFIDENTIAL,
            ClassificationCategory.RESTRICTED,
        ]:
            # Multi-step approval: Data Owner -> Compliance Officer
            # Get data owner from asset/dataset
            approvers_step1 = []
            approvers_step2 = []

            if access_request.asset and access_request.asset.created_by:
                approvers_step1.append(str(access_request.asset.created_by.id))
            elif (
                access_request.dataset
                and access_request.dataset.asset
                and access_request.dataset.asset.created_by
            ):
                approvers_step1.append(str(access_request.dataset.asset.created_by.id))

            # Get compliance officer (tenant admin or designated compliance role)
            from hub.apps.users.models import Role, User, UserRole

            compliance_role = Role.objects.filter(
                tenant_id=access_request.tenant_id, name="COMPLIANCE_OFFICER"
            ).first()

            if compliance_role:
                compliance_users = UserRole.objects.filter(role=compliance_role)
                approvers_step2 = [str(ur.user.id) for ur in compliance_users]

            if approvers_step1:
                approval_workflow.append(
                    {
                        "step": 0,
                        "approvers": approvers_step1,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Data Owner Approval",
                    }
                )

            if approvers_step2:
                approval_workflow.append(
                    {
                        "step": 1,
                        "approvers": approvers_step2,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Compliance Officer Approval",
                    }
                )

        elif highest_classification in [
            ClassificationCategory.RESTRICTED,
            ClassificationCategory.PII,
            ClassificationCategory.PHI,
            ClassificationCategory.PCI,
        ]:
            # Multi-step approval: Data Owner -> Compliance Officer -> Security Officer
            approvers_step1 = []
            approvers_step2 = []
            approvers_step3 = []

            if access_request.asset and access_request.asset.created_by:
                approvers_step1.append(str(access_request.asset.created_by.id))
            elif (
                access_request.dataset
                and access_request.dataset.asset
                and access_request.dataset.asset.created_by
            ):
                approvers_step1.append(str(access_request.dataset.asset.created_by.id))

            from hub.apps.users.models import Role, User, UserRole

            compliance_role = Role.objects.filter(
                tenant_id=access_request.tenant_id, name="COMPLIANCE_OFFICER"
            ).first()

            if compliance_role:
                compliance_users = UserRole.objects.filter(role=compliance_role)
                approvers_step2 = [str(ur.user.id) for ur in compliance_users]

            security_role = Role.objects.filter(
                tenant_id=access_request.tenant_id, name="SECURITY_OFFICER"
            ).first()

            if security_role:
                security_users = UserRole.objects.filter(role=security_role)
                approvers_step3 = [str(ur.user.id) for ur in security_users]

            if approvers_step1:
                approval_workflow.append(
                    {
                        "step": 0,
                        "approvers": approvers_step1,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Data Owner Approval",
                    }
                )

            if approvers_step2:
                approval_workflow.append(
                    {
                        "step": 1,
                        "approvers": approvers_step2,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Compliance Officer Approval",
                    }
                )

            if approvers_step3:
                approval_workflow.append(
                    {
                        "step": 2,
                        "approvers": approvers_step3,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Security Officer Approval",
                    }
                )

        else:
            # Single-step approval: Tenant Admin or Data Owner
            approvers = []

            if access_request.asset and access_request.asset.created_by:
                approvers.append(str(access_request.asset.created_by.id))
            elif (
                access_request.dataset
                and access_request.dataset.asset
                and access_request.dataset.asset.created_by
            ):
                approvers.append(str(access_request.dataset.asset.created_by.id))

            # Fallback to tenant admin if no owner
            if not approvers:
                from hub.apps.users.models import Role, User, UserRole

                tenant_admin_role = Role.objects.filter(
                    tenant_id=access_request.tenant_id, name="TENANT_ADMIN"
                ).first()

                if tenant_admin_role:
                    tenant_admin_users = UserRole.objects.filter(role=tenant_admin_role)
                    approvers = [
                        str(ur.user.id) for ur in tenant_admin_users[:1]
                    ]  # Take first admin
                else:
                    # Fallback: use any user in tenant (for testing)
                    fallback_users = User.objects.filter(tenant_id=access_request.tenant_id)
                    approvers = [str(user.id) for user in fallback_users[:1]]

            if approvers:
                approval_workflow.append(
                    {
                        "step": 0,
                        "approvers": approvers,
                        "timeout_hours": AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS,
                        "escalation_hours": AccessRequestWorkflow.ESCALATION_DELAY_HOURS,
                        "step_name": "Approver Approval",
                    }
                )

        # Update access request with approval workflow
        access_request.requires_approval = True
        access_request.approval_workflow = approval_workflow
        access_request.approvers = approval_workflow[0]["approvers"] if approval_workflow else []
        access_request.current_approval_step = 0
        access_request.save()

        # Store approval steps in workflow state for loop processing
        instance.state_data["approval_steps"] = approval_workflow
        instance.state_data["requires_approval"] = True
        instance.save(update_fields=["state_data"])

        logger.info(
            "Access request routed to approvers",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            approval_steps=len(approval_workflow),
            highest_classification=highest_classification,
        )

        return {
            "access_request_id": str(access_request.id),
            "requires_approval": True,
            "approval_steps": approval_workflow,
            "current_step": 0,
            "status": AccessRequestStatus.PENDING.value,
        }

    @staticmethod
    def _wait_for_step_approval_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Wait for approval step to complete (check status, handle timeout).

        This task checks the current status of the access request. If approved/rejected,
        it returns the status. If still pending, it checks for timeout and returns status.

        Args:
            input_data: Workflow input data (contains loop_item with step info)
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with approval status
        """
        access_request_id = instance.state_data.get("access_request_id")
        loop_item = instance.state_data.get("loop_item", {})

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)
        step_index = loop_item.get("step", access_request.current_approval_step)
        step_info = loop_item

        # Check if request is already approved (all steps completed)
        if access_request.status == AccessRequestStatus.APPROVED.value:
            # Mark step as completed
            instance.state_data[f"step_{step_index}_completed_at"] = timezone.now().isoformat()
            instance.save(update_fields=["state_data"])

            return {
                "access_request_id": str(access_request.id),
                "step_index": step_index,
                "approved": True,
                "step_timed_out": False,
                "status": AccessRequestStatus.APPROVED.value,
            }

        # Check if request is rejected
        if access_request.status == AccessRequestStatus.REJECTED.value:
            return {
                "access_request_id": str(access_request.id),
                "step_index": step_index,
                "approved": False,
                "rejected": True,
                "status": AccessRequestStatus.REJECTED.value,
            }

        # Check if current step is ahead of this step (already approved this step)
        if access_request.current_approval_step > step_index:
            # This step was already completed, move to next
            instance.state_data[f"step_{step_index}_completed_at"] = timezone.now().isoformat()
            instance.save(update_fields=["state_data"])

            return {
                "access_request_id": str(access_request.id),
                "step_index": step_index,
                "approved": True,
                "step_timed_out": False,
                "status": "STEP_COMPLETED",
            }

        # Check if this step is currently active (current_approval_step matches)
        if access_request.current_approval_step != step_index:
            # Step not yet active, skip
            return {
                "access_request_id": str(access_request.id),
                "step_index": step_index,
                "approved": False,
                "step_timed_out": False,
                "status": "STEP_NOT_ACTIVE",
                "current_step": access_request.current_approval_step,
            }

        # Step is active, check timeout
        timeout_hours = step_info.get(
            "timeout_hours", AccessRequestWorkflow.DEFAULT_APPROVAL_TIMEOUT_HOURS
        )
        step_start_time = access_request.created_at
        if step_index > 0:
            # Get previous step completion time from state
            prev_step_completion = instance.state_data.get(f"step_{step_index - 1}_completed_at")
            if prev_step_completion:
                step_start_time = date_parser.parse(prev_step_completion)

        time_elapsed = timezone.now() - step_start_time
        timeout_delta = timedelta(hours=timeout_hours)

        step_timed_out = time_elapsed >= timeout_delta

        if step_timed_out:
            logger.warning(
                "Approval step timed out",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                step_index=step_index,
                time_elapsed_hours=time_elapsed.total_seconds() / 3600,
                timeout_hours=timeout_hours,
            )

        # Still waiting for approval
        # Store timeout status in state for escalation task
        instance.state_data["step_timed_out"] = step_timed_out
        instance.save(update_fields=["state_data"])

        return {
            "access_request_id": str(access_request.id),
            "step_index": step_index,
            "approved": False,
            "step_timed_out": step_timed_out,
            "time_elapsed_hours": time_elapsed.total_seconds() / 3600,
            "timeout_hours": timeout_hours,
            "status": AccessRequestStatus.PENDING.value,
        }

    @staticmethod
    def _escalate_approval_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Escalate approval step to next level or notify administrators.

        This task checks if the step has timed out and escalates if needed.
        If not timed out, it's a no-op.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with escalation details
        """
        access_request_id = instance.state_data.get("access_request_id")
        loop_item = instance.state_data.get("loop_item", {})
        step_index = loop_item.get("step", 0)
        step_timed_out = instance.state_data.get("step_timed_out", False)

        if not access_request_id:
            raise ValueError("access_request_id is required")

        # Only escalate if timed out
        if not step_timed_out:
            return {
                "access_request_id": access_request_id,
                "step_index": step_index,
                "escalated": False,
                "escalation_approvers": [],
            }

        access_request = AccessRequest.objects.get(id=access_request_id)

        # Get escalation approvers (next level up)
        escalation_approvers = []

        # Try to escalate to tenant admin
        from hub.apps.users.models import Role, User, UserRole

        tenant_admin_role = Role.objects.filter(
            tenant_id=access_request.tenant_id, name="TENANT_ADMIN"
        ).first()

        escalation_approvers = []
        if tenant_admin_role:
            tenant_admin_users = UserRole.objects.filter(role=tenant_admin_role)
            escalation_approvers = [str(ur.user.id) for ur in tenant_admin_users]
        else:
            # Fallback: use any user in tenant (for testing)
            fallback_users = User.objects.filter(tenant_id=access_request.tenant_id)
            escalation_approvers = [str(user.id) for user in fallback_users[:1]]

        # Update approval workflow to include escalation approvers
        if access_request.approval_workflow and step_index < len(access_request.approval_workflow):
            step_info = dict(access_request.approval_workflow[step_index])  # Make a copy
            original_approvers = step_info.get("approvers", [])

            # Add escalation approvers if not already in list
            updated_approvers = list(original_approvers)
            for esc_approver in escalation_approvers:
                if esc_approver not in updated_approvers:
                    updated_approvers.append(esc_approver)

            step_info["approvers"] = updated_approvers
            step_info["escalated"] = True
            step_info["escalated_at"] = timezone.now().isoformat()

            # Update the workflow list
            updated_workflow = list(access_request.approval_workflow)
            updated_workflow[step_index] = step_info
            access_request.approval_workflow = updated_workflow
            access_request.approvers = updated_approvers
            access_request.save()

        # Send escalation notification
        try:
            from hub.apps.notifications.models import EmailType
            from hub.apps.notifications.tasks import send_email_async

            for approver_id in escalation_approvers:
                approver = User.objects.get(id=approver_id)
                approver_email = getattr(approver, "email", None)
                if approver_email:
                    send_email_async(
                        email_type=EmailType.JOB_COMPLETION,
                        to_email=approver_email,
                        subject="Access Request Escalated",
                        template_name="notifications/emails/access_request_escalation.html",
                        context={
                            "access_request_id": str(access_request.id),
                            "step_index": step_index,
                            "resource": str(
                                access_request.asset
                                or access_request.dataset
                                or access_request.file
                            ),
                            "requested_by": (
                                getattr(access_request.requested_by, "email", "Unknown")
                                if access_request.requested_by
                                else "Unknown"
                            ),
                        },
                        tenant_id=str(access_request.tenant.id),
                        user_id=str(approver.id),
                    )
        except Exception as e:
            logger.warning(
                "Failed to send escalation notification",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                error=str(e),
            )

        logger.info(
            "Approval step escalated",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            step_index=step_index,
            escalation_approvers=escalation_approvers,
        )

        return {
            "access_request_id": str(access_request.id),
            "step_index": step_index,
            "escalated": True,
            "escalation_approvers": escalation_approvers,
        }

    @staticmethod
    def _grant_access_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Grant access to the requested resource.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with access grant details
        """
        access_request_id = instance.state_data.get("access_request_id")

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)

        if access_request.status != AccessRequestStatus.APPROVED.value:
            raise ValueError(f"Access request is not approved (status: {access_request.status})")

        # Validate access request before granting access using GovernanceBusinessRules
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=access_request.tenant_id)
        user = access_request.requested_by

        governance_rules = GovernanceBusinessRules(
            tenant_id=str(access_request.tenant_id) if access_request.tenant_id else None,
            user_id=str(instance.created_by_id) if instance.created_by_id else None,
        )

        # Validate access request status transition
        access_request_validation_result = governance_rules.validate(
            access_request=access_request,
            tenant=tenant,
            user=user,
            validation_type="access_request",
        )

        if not access_request_validation_result.is_valid:
            error_messages = access_request_validation_result.errors
            raise ValueError(
                f"Access request validation failed before granting access: {'; '.join(error_messages)}"
            )

        # Log validation warnings if any
        if access_request_validation_result.warnings:
            logger.warning(
                "Access request validation warnings before granting access",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                warnings=access_request_validation_result.warnings,
            )

        # Access is already granted (status set to APPROVED in approve step)
        # This task ensures proper access grant and records timestamp
        if not access_request.access_granted_at:
            access_request.access_granted_at = timezone.now()
            access_request.save()

        # Note: ABAC policies are evaluated dynamically, no need to create explicit grants
        # The access request record itself serves as the access grant record

        logger.info(
            "Access granted",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            requested_by_id=str(access_request.requested_by.id),
            access_type=access_request.requested_access_type,
        )

        return {
            "access_request_id": str(access_request.id),
            "access_granted": True,
            "access_granted_at": (
                access_request.access_granted_at.isoformat()
                if access_request.access_granted_at
                else None
            ),
            "expires_at": (
                access_request.expires_at.isoformat() if access_request.expires_at else None
            ),
        }

    @staticmethod
    def _revoke_access_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Revoke access (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with revocation details
        """
        access_request_id = instance.state_data.get("access_request_id")

        if not access_request_id:
            return {"revoked": False, "reason": "access_request_id not found"}

        try:
            access_request = AccessRequest.objects.get(id=access_request_id)

            if access_request.status == AccessRequestStatus.APPROVED.value:
                access_request.status = AccessRequestStatus.REVOKED.value
                access_request.save()

                # Access revocation is handled by status change
                # ABAC policies are evaluated dynamically based on access request status

            return {"revoked": True}
        except AccessRequest.DoesNotExist:
            return {"revoked": False, "reason": "access_request not found"}

    @staticmethod
    def _send_notifications_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Send notifications to relevant parties.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with notification details
        """
        access_request_id = instance.state_data.get("access_request_id")

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)

        notifications_sent = []

        # Notify requester
        if access_request.requested_by:
            requester_email = getattr(access_request.requested_by, "email", None)
            if requester_email:
                try:
                    # Use JOB_COMPLETION as a generic notification type (access request email types don't exist yet)
                    status_text = (
                        "approved"
                        if access_request.status == AccessRequestStatus.APPROVED.value
                        else (
                            "rejected"
                            if access_request.status == AccessRequestStatus.REJECTED.value
                            else "pending"
                        )
                    )
                    send_email_async(
                        email_type=EmailType.JOB_COMPLETION,
                        to_email=requester_email,
                        subject=f"Access Request {status_text.title()}",
                        template_name="notifications/emails/access_request_status.html",
                        context={
                            "access_request_id": str(access_request.id),
                            "status": access_request.status,
                            "status_text": status_text,
                            "resource": str(
                                access_request.asset
                                or access_request.dataset
                                or access_request.file
                            ),
                            "rejection_reason": (
                                access_request.rejection_reason
                                if access_request.status == AccessRequestStatus.REJECTED.value
                                else None
                            ),
                        },
                        tenant_id=str(access_request.tenant.id),
                        user_id=str(access_request.requested_by.id),
                    )
                    notifications_sent.append("requester")
                except Exception as e:
                    logger.warning(
                        "Failed to send notification to requester",
                        workflow_instance_id=str(instance.id),
                        access_request_id=str(access_request.id),
                        error=str(e),
                    )

        # Notify approvers if pending
        if access_request.status == AccessRequestStatus.PENDING.value and access_request.approvers:
            try:
                from hub.apps.users.models import User

                approvers_list = access_request.approvers
                if isinstance(approvers_list, str):
                    # Handle case where approvers is stored as JSON string
                    import json

                    approvers_list = json.loads(approvers_list)

                for approver_id in approvers_list:
                    try:
                        approver = User.objects.get(id=approver_id)
                        approver_email = getattr(approver, "email", None)
                        if approver_email:
                            send_email_async(
                                email_type=EmailType.JOB_COMPLETION,
                                to_email=approver_email,
                                subject="Access Request Pending Approval",
                                template_name="notifications/emails/access_request_pending.html",
                                context={
                                    "access_request_id": str(access_request.id),
                                    "resource": str(
                                        access_request.asset
                                        or access_request.dataset
                                        or access_request.file
                                    ),
                                    "requested_by": (
                                        getattr(access_request.requested_by, "email", "Unknown")
                                        if access_request.requested_by
                                        else "Unknown"
                                    ),
                                    "reason": access_request.reason,
                                },
                                tenant_id=str(access_request.tenant.id),
                                user_id=str(approver.id),
                            )
                            notifications_sent.append(f"approver_{approver_id}")
                    except User.DoesNotExist:
                        pass
                    except Exception as e:
                        logger.warning(
                            "Failed to send notification to approver",
                            workflow_instance_id=str(instance.id),
                            access_request_id=str(access_request.id),
                            approver_id=approver_id,
                            error=str(e),
                        )
            except Exception as e:
                logger.warning(
                    "Failed to send notifications to approvers",
                    workflow_instance_id=str(instance.id),
                    access_request_id=str(access_request.id),
                    error=str(e),
                )

        logger.info(
            "Notifications sent",
            workflow_instance_id=str(instance.id),
            access_request_id=str(access_request.id),
            notifications_sent=len(notifications_sent),
        )

        return {
            "access_request_id": str(access_request.id),
            "notifications_sent": notifications_sent,
            "notification_count": len(notifications_sent),
        }

    @staticmethod
    def _audit_logging_task(
        input_data: dict[str, Any], instance: WorkflowInstance, step
    ) -> dict[str, Any]:
        """
        Create audit log entry for access request.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with audit log details
        """
        access_request_id = instance.state_data.get("access_request_id")

        if not access_request_id:
            raise ValueError("access_request_id is required")

        access_request = AccessRequest.objects.get(id=access_request_id)

        # Create audit event
        try:
            audit_event = create_audit_event(
                resource_type="ACCESS_REQUEST",
                action="ACCESS_REQUEST_" + access_request.status,
                actor_user=access_request.requested_by,
                tenant=access_request.tenant,
                resource_id=str(access_request.id),
                details={
                    "access_request_id": str(access_request.id),
                    "status": access_request.status,
                    "requested_access_type": access_request.requested_access_type,
                    "resource": {
                        "asset_id": str(access_request.asset.id) if access_request.asset else None,
                        "dataset_id": (
                            str(access_request.dataset.id) if access_request.dataset else None
                        ),
                        "file_id": str(access_request.file.id) if access_request.file else None,
                    },
                    "approved_by": (
                        str(access_request.approved_by.id) if access_request.approved_by else None
                    ),
                    "rejected_by": (
                        str(access_request.rejected_by.id) if access_request.rejected_by else None
                    ),
                    "expires_at": (
                        access_request.expires_at.isoformat() if access_request.expires_at else None
                    ),
                },
            )

            logger.info(
                "Audit log created",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                audit_event_id=str(audit_event.id) if audit_event else None,
            )

            return {
                "access_request_id": str(access_request.id),
                "audit_event_id": str(audit_event.id) if audit_event else None,
                "audit_logged": True,
            }
        except Exception as e:
            logger.error(
                "Failed to create audit log",
                workflow_instance_id=str(instance.id),
                access_request_id=str(access_request.id),
                error=str(e),
                exc_info=True,
            )
            return {
                "access_request_id": str(access_request.id),
                "audit_logged": False,
                "error": str(e),
            }

    @classmethod
    @transaction.atomic
    def execute(
        cls,
        tenant_id: str,
        requested_by_id: str,
        asset_id: str | None = None,
        dataset_id: str | None = None,
        file_id: str | None = None,
        reason: str = "",
        requested_access_type: str = "READ",
        expires_at: str | None = None,
        requires_approval: bool | None = None,
        engine: WorkflowEngine | None = None,
        registry: WorkflowRegistry | None = None,
    ) -> dict[str, Any]:
        """
        Execute access request workflow.

        Args:
            tenant_id: Tenant ID
            requested_by_id: User ID requesting access
            asset_id: Optional asset ID
            dataset_id: Optional dataset ID
            file_id: Optional file ID
            reason: Reason for access request
            requested_access_type: Type of access (READ, WRITE, DOWNLOAD)
            expires_at: Optional expiration date (ISO format)
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

        # Prepare workflow input
        workflow_input = {
            "tenant_id": tenant_id,
            "requested_by_id": requested_by_id,
            "asset_id": asset_id,
            "dataset_id": dataset_id,
            "file_id": file_id,
            "reason": reason,
            "requested_access_type": requested_access_type,
            "expires_at": expires_at,
            "requires_approval": requires_approval,
        }

        # Create workflow instance
        workflow_instance = engine.create_instance(
            workflow_name=cls.WORKFLOW_NAME,
            input_data=workflow_input,
            tenant_id=tenant_id,
            created_by_id=requested_by_id,
        )

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Access request workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                requested_by_id=requested_by_id,
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "output_data": workflow_instance.output_data,
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Access request workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                requested_by_id=requested_by_id,
                error=error_message,
            )
            raise ValueError(f"Access request workflow failed: {error_message}")

    @classmethod
    @transaction.atomic
    def approve_access_request(
        cls, access_request_id: str, approved_by_id: str, step_index: int | None = None
    ) -> AccessRequest:
        """
        Approve an access request (can be called externally when approver acts).

        Args:
            access_request_id: AccessRequest UUID
            approved_by_id: User UUID approving
            step_index: Step index for multi-step approval (optional)

        Returns:
            Updated AccessRequest instance
        """
        access_request = AccessRequest.objects.get(id=access_request_id)

        if access_request.status != AccessRequestStatus.PENDING.value:
            raise ValueError(f"Access request is not pending (status: {access_request.status})")

        # Check if multi-step approval
        if access_request.approval_workflow and len(access_request.approval_workflow) > 1:
            # Multi-step approval
            if step_index is None:
                step_index = access_request.current_approval_step

            workflow_step = access_request.approval_workflow[step_index]
            approvers = workflow_step.get("approvers", [])

            if approved_by_id not in approvers:
                raise ValueError(f"User {approved_by_id} is not an approver for step {step_index}")

            # Check if all steps are approved
            if step_index < len(access_request.approval_workflow) - 1:
                # Not the last step, move to next
                access_request.current_approval_step = step_index + 1
                access_request.approvers = access_request.approval_workflow[step_index + 1].get(
                    "approvers", []
                )
                access_request.save()
                return access_request
            else:
                # Last step, approve the request
                access_request.status = AccessRequestStatus.APPROVED.value
                access_request.approved_by_id = approved_by_id
                access_request.approved_at = timezone.now()
                access_request.access_granted_at = timezone.now()
                access_request.save()
                return access_request
        else:
            # Single-step approval
            if access_request.approvers and approved_by_id not in access_request.approvers:
                raise ValueError(f"User {approved_by_id} is not an approver")

            access_request.status = AccessRequestStatus.APPROVED.value
            access_request.approved_by_id = approved_by_id
            access_request.approved_at = timezone.now()
            access_request.access_granted_at = timezone.now()
            access_request.save()
            return access_request

    @classmethod
    @transaction.atomic
    def reject_access_request(
        cls, access_request_id: str, rejected_by_id: str, rejection_reason: str
    ) -> AccessRequest:
        """
        Reject an access request (can be called externally when approver acts).

        Args:
            access_request_id: AccessRequest UUID
            rejected_by_id: User UUID rejecting
            rejection_reason: Reason for rejection

        Returns:
            Updated AccessRequest instance
        """
        access_request = AccessRequest.objects.get(id=access_request_id)

        if access_request.status != AccessRequestStatus.PENDING.value:
            raise ValueError(f"Access request is not pending (status: {access_request.status})")

        access_request.status = AccessRequestStatus.REJECTED.value
        access_request.rejected_by_id = rejected_by_id
        access_request.rejected_at = timezone.now()
        access_request.rejection_reason = rejection_reason
        access_request.save()

        return access_request
