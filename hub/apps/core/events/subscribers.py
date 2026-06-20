"""
Event Subscribers

Pre-built event subscribers for common use cases (webhooks, notifications, workflows).
"""

from typing import Any

import structlog

from .bus import get_event_bus
from .subscriber import EventSubscriber, event_subscriber

# Import models here to avoid circular imports
try:
    from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
except ImportError:
    # For testing or when orchestration app is not available
    WorkflowInstance = None
    WorkflowStatus = None

logger = structlog.get_logger(__name__)


class WebhookSubscriber:
    """
    Subscriber for webhook delivery.

    Listens to events and delivers them to configured webhook endpoints.
    """

    def __init__(self, webhook_service=None):
        """
        Initialize webhook subscriber.

        Args:
            webhook_service: Optional webhook service instance
        """
        self.webhook_service = webhook_service
        self.subscriber = EventSubscriber(
            subscriber_name="webhook_subscriber", event_bus=get_event_bus()
        )

    def start(self):
        """Start listening for events."""
        self.subscriber.subscribe(
            event_type_pattern="*.*", handler=self._handle_event, is_active=True
        )

    def _handle_event(self, event: dict[str, Any]):
        """Handle event and deliver to webhooks."""
        try:
            if self.webhook_service:
                # Deliver to webhook service
                self.webhook_service.deliver_webhook(event)
            else:
                logger.info(
                    "webhook_event_received",
                    event_type=event.get("event_type"),
                    event_id=event.get("event_id"),
                )
        except Exception as e:
            logger.error(
                "webhook_delivery_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )


class NotificationSubscriber:
    """
    Subscriber for notification delivery.

    Listens to events and sends notifications (email, SMS, etc.).
    """

    def __init__(self, notification_service=None):
        """
        Initialize notification subscriber.

        Args:
            notification_service: Optional notification service instance
        """
        self.notification_service = notification_service
        self.subscriber = EventSubscriber(
            subscriber_name="notification_subscriber", event_bus=get_event_bus()
        )

    def start(self):
        """Start listening for events."""
        # Subscribe to events that require notifications
        notification_events = [
            "access.requested",
            "access.granted",
            "access.revoked",
            "workflow.failed",
            "workflow.completed",
            "quality.anomaly.detected",
            "compliance.check.failed",
            "marketplace.order.created",
            "marketplace.order.approved",
            "marketplace.order.rejected",
        ]

        for event_type in notification_events:
            self.subscriber.subscribe(
                event_type_pattern=event_type, handler=self._handle_event, is_active=True
            )

    def _handle_event(self, event: dict[str, Any]):
        """Handle event and send notification."""
        try:
            if self.notification_service:
                # Send notification via service
                self.notification_service.send_notification(event)
            else:
                logger.info(
                    "notification_event_received",
                    event_type=event.get("event_type"),
                    event_id=event.get("event_id"),
                )
        except Exception as e:
            logger.error(
                "notification_delivery_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )


class WorkflowTriggerSubscriber:
    """
    Subscriber for triggering workflows based on events.

    Listens to events and triggers workflows accordingly.
    Supports event-triggered workflow starts.
    """

    def __init__(self, workflow_engine=None):
        """
        Initialize workflow trigger subscriber.

        Args:
            workflow_engine: Optional workflow engine instance
        """
        self.workflow_engine = workflow_engine
        self.subscriber = EventSubscriber(subscriber_name="workflow_trigger_subscriber")
        # Event type to workflow name mapping
        self.workflow_mapping = {}

    def register_workflow_trigger(self, event_type: str, workflow_name: str):
        """
        Register a workflow trigger for an event type.

        Args:
            event_type: Event type pattern (e.g., "contract.created", "asset.*")
            workflow_name: Workflow name to trigger
        """
        self.workflow_mapping[event_type] = workflow_name
        self.subscriber.subscribe(
            event_type_pattern=event_type, handler=self._handle_event, is_active=True
        )

    def start(self):
        """Start listening for events."""
        # Subscribe to events that trigger workflows
        workflow_trigger_events = [
            "asset.created",
            "contract.created",
            "dataset.created",
            "ingestion.completed",
            "quality.check.completed",
            "compliance.check.completed",
        ]

        for event_type in workflow_trigger_events:
            self.subscriber.subscribe(
                event_type_pattern=event_type, handler=self._handle_event, is_active=True
            )

    def _handle_event(self, event: dict[str, Any]):
        """Handle event and trigger workflow."""
        try:
            if not self.workflow_engine:
                logger.warning(
                    "workflow_engine_not_configured",
                    event_type=event.get("event_type"),
                    event_id=event.get("event_id"),
                )
                return

            event_type = event.get("event_type")
            event_data = event.get("data", {})
            source = event.get("source", {})
            tenant_id = source.get("tenant_id")
            user_id = source.get("user_id")

            # Check if this event type has a registered workflow
            workflow_name = self.workflow_mapping.get(event_type)

            # If not found, try default mapping
            if not workflow_name:
                default_mapping = {
                    "asset.created": "asset_activation",
                    "contract.created": "contract_validation",
                    "dataset.created": "dataset_quality_check",
                    "ingestion.completed": "ingestion_post_processing",
                    "quality.check.completed": "quality_review",
                    "compliance.check.completed": "compliance_review",
                }
                workflow_name = default_mapping.get(event_type)

            if workflow_name:
                # Create workflow instance
                workflow_instance = self.workflow_engine.create_instance(
                    workflow_name=workflow_name,
                    input_data=event_data,
                    tenant_id=tenant_id,
                    created_by_id=user_id,
                )

                # Start workflow execution (this will publish workflow.started event)
                self.workflow_engine.start_instance(str(workflow_instance.id))

                # Execute workflow (this will publish step events)
                self.workflow_engine.execute_instance(str(workflow_instance.id))

                logger.info(
                    "workflow_triggered_from_event",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                    workflow_instance_id=str(workflow_instance.id),
                    workflow_name=workflow_name,
                )
            else:
                logger.debug(
                    "no_workflow_mapping_for_event",
                    event_type=event_type,
                    event_id=event.get("event_id"),
                )
        except Exception as e:
            logger.error(
                "workflow_trigger_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )


class WorkflowStepSubscriber:
    """
    Subscriber for event-based workflow step execution.

    Listens to workflow.step.completed events and triggers next steps.
    """

    def __init__(self, workflow_engine=None):
        """
        Initialize workflow step subscriber.

        Args:
            workflow_engine: Optional workflow engine instance
        """
        self.workflow_engine = workflow_engine
        self.subscriber = EventSubscriber(subscriber_name="workflow_step_subscriber")

    def start(self):
        """Start listening for workflow step events."""
        # Subscribe to workflow.step.completed events
        self.subscriber.subscribe(
            event_type_pattern="workflow.step.completed",
            handler=self._handle_step_completed,
            is_active=True,
        )

        # Subscribe to workflow.started events to start execution
        self.subscriber.subscribe(
            event_type_pattern="workflow.started",
            handler=self._handle_workflow_started,
            is_active=True,
        )

    def _handle_workflow_started(self, event: dict[str, Any]):
        """Handle workflow.started event and begin execution."""
        try:
            if not self.workflow_engine:
                logger.warning(
                    "workflow_engine_not_configured",
                    event_type=event.get("event_type"),
                    event_id=event.get("event_id"),
                )
                return

            event_data = event.get("data", {})
            workflow_instance_id = event_data.get("workflow_instance_id")

            if workflow_instance_id:
                # Execute workflow instance (this will process steps and publish step events)
                self.workflow_engine.execute_instance(workflow_instance_id)

                logger.info(
                    "workflow_execution_started_from_event",
                    workflow_instance_id=workflow_instance_id,
                    event_id=event.get("event_id"),
                )
        except Exception as e:
            logger.error(
                "workflow_execution_start_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )

    def _handle_step_completed(self, event: dict[str, Any]):
        """Handle workflow.step.completed event and trigger next step if needed."""
        try:
            if not self.workflow_engine:
                logger.warning(
                    "workflow_engine_not_configured",
                    event_type=event.get("event_type"),
                    event_id=event.get("event_id"),
                )
                return

            event_data = event.get("data", {})
            workflow_instance_id = event_data.get("workflow_instance_id")

            if workflow_instance_id:
                # Check if workflow is still running and has more steps
                if WorkflowInstance is None:
                    logger.warning("WorkflowInstance model not available")
                    return

                try:
                    instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                    if instance.status == WorkflowStatus.RUNNING:
                        # Continue execution (this will process next steps)
                        self.workflow_engine.execute_instance(workflow_instance_id)

                        logger.debug(
                            "workflow_step_execution_continued",
                            workflow_instance_id=workflow_instance_id,
                            step_index=event_data.get("step_index"),
                            event_id=event.get("event_id"),
                        )
                except WorkflowInstance.DoesNotExist:
                    logger.warning(
                        "workflow_instance_not_found",
                        workflow_instance_id=workflow_instance_id,
                        event_id=event.get("event_id"),
                    )
        except Exception as e:
            logger.error(
                "workflow_step_execution_failed",
                event_type=event.get("event_type"),
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )


# Decorator-based subscribers for easy registration
@event_subscriber("contract_event_handler", "contract.*")
def handle_contract_events(event: dict[str, Any]):
    """Handle all contract events."""
    logger.info(
        "contract_event_received",
        event_type=event.get("event_type"),
        contract_id=event.get("data", {}).get("contract_id"),
    )


@event_subscriber("asset_event_handler", "asset.*")
def handle_asset_events(event: dict[str, Any]):
    """Handle all asset events."""
    logger.info(
        "asset_event_received",
        event_type=event.get("event_type"),
        asset_id=event.get("data", {}).get("asset_id"),
    )


@event_subscriber("workflow_event_handler", "workflow.*")
def handle_workflow_events(event: dict[str, Any]):
    """Handle all workflow events."""
    logger.info(
        "workflow_event_received",
        event_type=event.get("event_type"),
        workflow_instance_id=event.get("data", {}).get("workflow_instance_id"),
    )
