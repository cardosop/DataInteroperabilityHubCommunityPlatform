"""
Proof-of-Concept: RabbitMQ Event Bus Implementation

This is a proof-of-concept implementation demonstrating how the event bus
could be migrated to RabbitMQ. It maintains API compatibility with
the current Redis Pub/Sub implementation.

Requirements:
    pip install pika

Usage:
    from hub.apps.core.events.rabbitmq_poc import RabbitMQEventBus

    bus = RabbitMQEventBus()
    event_id = bus.publish("contract.created", {"contract_id": "..."})
    bus.subscribe("contract.*", handler_function)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import structlog
from django.conf import settings

from .event_types import validate_event_data
from .schema import EventSchema

logger = structlog.get_logger(__name__)

# Try to import pika (RabbitMQ client)
try:
    import pika
    from pika.exceptions import AMQPChannelError, AMQPConnectionError

    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False
    pika = None
    AMQPConnectionError = Exception
    AMQPChannelError = Exception


class RabbitMQEventBusError(Exception):
    """Base exception for RabbitMQ event bus errors."""


class RabbitMQEventBus:
    """
    Proof-of-Concept: RabbitMQ Event Bus Implementation.

    This implementation demonstrates RabbitMQ integration while maintaining
    API compatibility with the current Redis Pub/Sub event bus.

    Features:
    - RabbitMQ exchanges for event routing
    - Queue-based delivery
    - Built-in persistence (optional)
    - Dead letter queues for failed messages
    - Advanced routing (direct, topic, fanout exchanges)
    """

    def __init__(self, connection_url: str | None = None):
        """
        Initialize RabbitMQ event bus.

        Args:
            connection_url: RabbitMQ connection URL (default: from settings)
        """
        if not RABBITMQ_AVAILABLE:
            raise RabbitMQEventBusError("pika not installed. Install with: pip install pika")

        # Get RabbitMQ configuration from settings
        self.connection_url = connection_url or getattr(
            settings, "RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"
        )
        self.exchange_name = getattr(settings, "RABBITMQ_EXCHANGE_NAME", "events")
        self.exchange_type = "topic"  # Use topic exchange for pattern matching

        # Connection and channel
        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.channel.Channel | None = None

        # Queue bindings
        self.queues: dict[str, str] = {}  # subscriber_name -> queue_name

    def _ensure_connection(self) -> None:
        """Ensure RabbitMQ connection is established."""
        if self.connection is None or self.connection.is_closed:
            try:
                parameters = pika.URLParameters(self.connection_url)
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Declare exchange
                self.channel.exchange_declare(
                    exchange=self.exchange_name,
                    exchange_type=self.exchange_type,
                    durable=True,  # Survive broker restart
                )

                logger.info("rabbitmq_connection_established", exchange=self.exchange_name)
            except AMQPConnectionError as e:
                logger.error("rabbitmq_connection_failed", error=str(e))
                raise RabbitMQEventBusError(f"Failed to connect to RabbitMQ: {e}")

    def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        tenant_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Publish an event to RabbitMQ.

        Args:
            event_type: Event type (e.g., 'contract.created')
            data: Event data payload
            tenant_id: Tenant ID
            user_id: User ID
            request_id: Request ID for tracing
            correlation_id: Correlation ID for tracing
            causation_id: Event ID that caused this event
            tags: Tags for filtering

        Returns:
            Event ID (UUID)
        """
        import uuid

        # Build event using schema
        event_id = str(uuid.uuid4())
        event = EventSchema.build_event(
            event_id=event_id,
            event_type=event_type,
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            tags=tags,
        )

        # Validate event
        try:
            validate_event_data(event_type, data)
        except Exception as e:
            logger.error("rabbitmq_event_validation_failed", event_type=event_type, error=str(e))
            raise RabbitMQEventBusError(f"Event validation failed: {e}")

        # Ensure connection
        self._ensure_connection()

        # Publish to exchange with routing key = event_type
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=event_type,  # Use event_type as routing key
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type="application/json",
                    message_id=event_id,
                    correlation_id=correlation_id or event_id,
                    headers={
                        "event_type": event_type,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "request_id": request_id,
                    },
                ),
            )

            logger.debug(
                "rabbitmq_event_published",
                event_id=event_id,
                event_type=event_type,
                exchange=self.exchange_name,
                routing_key=event_type,
            )

            return event_id

        except AMQPChannelError as e:
            logger.error(
                "rabbitmq_event_publish_failed",
                event_id=event_id,
                event_type=event_type,
                error=str(e),
            )
            raise RabbitMQEventBusError(f"Failed to publish event: {e}")

    def subscribe(
        self,
        subscriber_name: str,
        event_type_pattern: str,
        handler: Callable[[dict[str, Any]], None],
        is_active: bool = True,
    ) -> None:
        """
        Subscribe to events matching a pattern.

        Args:
            subscriber_name: Unique subscriber identifier
            event_type_pattern: Event type pattern (supports wildcards, e.g., 'contract.*')
            handler: Handler function
            is_active: Whether subscription is active
        """
        if not is_active:
            logger.debug(
                "rabbitmq_subscription_inactive",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
            )
            return

        # Ensure connection
        self._ensure_connection()

        # Create queue for subscriber
        queue_name = f"{self.exchange_name}.{subscriber_name}"

        # Declare queue
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,  # Survive broker restart
        )

        # Convert pattern to RabbitMQ routing pattern
        # 'contract.*' -> 'contract.*'
        # 'contract.created' -> 'contract.created'
        routing_pattern = event_type_pattern

        # Bind queue to exchange with routing pattern
        self.channel.queue_bind(
            exchange=self.exchange_name, queue=queue_name, routing_key=routing_pattern
        )

        # Store queue name
        self.queues[subscriber_name] = queue_name

        # Set up consumer
        def callback(ch, method, properties, body):
            """Callback for received messages."""
            try:
                # Parse event
                event = json.loads(body)

                # Call handler
                handler(event)

                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                logger.error(
                    "rabbitmq_event_processing_failed",
                    subscriber_name=subscriber_name,
                    queue=queue_name,
                    error=str(e),
                )
                # Reject message (would go to dead letter queue if configured)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        # Set up consumer
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=False,  # Manual acknowledgment
        )

        logger.info(
            "rabbitmq_subscription_registered",
            subscriber_name=subscriber_name,
            event_type_pattern=event_type_pattern,
            queue=queue_name,
            routing_pattern=routing_pattern,
        )

    def start_consuming(self, subscriber_name: str | None = None) -> None:
        """
        Start consuming events.

        This is a blocking call and should be run in a background thread/worker.

        Args:
            subscriber_name: Specific subscriber to consume for (None = all)
        """
        if self.channel is None:
            raise RabbitMQEventBusError("No active connection")

        logger.info("rabbitmq_consumer_started", subscriber_name=subscriber_name or "all")

        try:
            # Start consuming (blocking)
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("rabbitmq_consumer_stopped", subscriber_name=subscriber_name or "all")
            self.channel.stop_consuming()

    def close(self) -> None:
        """Close all connections."""
        if self.channel and not self.channel.is_closed:
            self.channel.close()
            self.channel = None

        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.connection = None

        self.queues.clear()

        logger.info("rabbitmq_event_bus_closed")


def get_rabbitmq_event_bus() -> RabbitMQEventBus:
    """Get global RabbitMQ event bus instance."""
    if not hasattr(get_rabbitmq_event_bus, "_instance"):
        get_rabbitmq_event_bus._instance = RabbitMQEventBus()
    return get_rabbitmq_event_bus._instance
