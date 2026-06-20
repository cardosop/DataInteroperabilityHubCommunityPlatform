"""
Proof-of-Concept: Apache Kafka Event Bus Implementation

This is a proof-of-concept implementation demonstrating how the event bus
could be migrated to Apache Kafka. It maintains API compatibility with
the current Redis Pub/Sub implementation.

Requirements:
    pip install kafka-python

Usage:
    from hub.apps.core.events.kafka_poc import KafkaEventBus

    bus = KafkaEventBus()
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

# Try to import kafka-python
try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.errors import KafkaError

    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    KafkaProducer = None
    KafkaConsumer = None
    KafkaError = Exception


class KafkaEventBusError(Exception):
    """Base exception for Kafka event bus errors."""


class KafkaEventBus:
    """
    Proof-of-Concept: Apache Kafka Event Bus Implementation.

    This implementation demonstrates Kafka integration while maintaining
    API compatibility with the current Redis Pub/Sub event bus.

    Features:
    - Kafka topics for event delivery
    - Built-in persistence (Kafka log)
    - Offset-based replay
    - Consumer groups for parallel processing
    - Partition-based ordering
    """

    def __init__(self, bootstrap_servers: list[str] | None = None):
        """
        Initialize Kafka event bus.

        Args:
            bootstrap_servers: List of Kafka broker addresses (default: from settings)
        """
        if not KAFKA_AVAILABLE:
            raise KafkaEventBusError(
                "kafka-python not installed. Install with: pip install kafka-python"
            )

        # Get Kafka configuration from settings
        self.bootstrap_servers = bootstrap_servers or getattr(
            settings, "KAFKA_BOOTSTRAP_SERVERS", ["localhost:9092"]
        )
        self.topic_prefix = getattr(settings, "KAFKA_TOPIC_PREFIX", "events")
        self.default_topic = f"{self.topic_prefix}.all"

        # Producer configuration
        self.producer_config = {
            "bootstrap_servers": self.bootstrap_servers,
            "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
            "key_serializer": lambda k: k.encode("utf-8") if k else None,
            "acks": "all",  # Wait for all replicas
            "retries": 3,
            "max_in_flight_requests_per_connection": 1,  # Ensure ordering
            "enable_idempotence": True,  # Exactly-once semantics
        }

        # Consumer configuration
        self.consumer_config = {
            "bootstrap_servers": self.bootstrap_servers,
            "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
            "key_deserializer": lambda k: k.decode("utf-8") if k else None,
            "auto_offset_reset": "earliest",  # Start from beginning if no offset
            "enable_auto_commit": False,  # Manual offset management
            "group_id": None,  # Set per subscription
        }

        self.producer: KafkaProducer | None = None
        self.consumers: dict[str, KafkaConsumer] = {}

    def _get_producer(self) -> KafkaProducer:
        """Get or create Kafka producer."""
        if self.producer is None:
            self.producer = KafkaProducer(**self.producer_config)
        return self.producer

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
        Publish an event to Kafka.

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
            logger.error("kafka_event_validation_failed", event_type=event_type, error=str(e))
            raise KafkaEventBusError(f"Event validation failed: {e}")

        # Determine topic and partition key
        # Use event_type as partition key for ordering within event type
        topic = self._get_topic_for_event_type(event_type)
        partition_key = event_type  # Ensures ordering within event type

        # Publish to Kafka
        producer = self._get_producer()
        try:
            future = producer.send(topic=topic, key=partition_key, value=event)
            # Wait for acknowledgment
            record_metadata = future.get(timeout=10)

            logger.debug(
                "kafka_event_published",
                event_id=event_id,
                event_type=event_type,
                topic=topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset,
            )

            return event_id

        except KafkaError as e:
            logger.error(
                "kafka_event_publish_failed", event_id=event_id, event_type=event_type, error=str(e)
            )
            raise KafkaEventBusError(f"Failed to publish event: {e}")

    def _get_topic_for_event_type(self, event_type: str) -> str:
        """
        Get Kafka topic for event type.

        Strategy: Use domain from event_type (e.g., 'contract.created' -> 'events.contract')
        """
        # Extract domain from event_type (e.g., 'contract.created' -> 'contract')
        domain = event_type.split(".")[0] if "." in event_type else "default"
        return f"{self.topic_prefix}.{domain}"

    def subscribe(
        self,
        subscriber_name: str,
        event_type_pattern: str,
        handler: Callable[[dict[str, Any]], None],
        is_active: bool = True,
        consumer_group: str | None = None,
        start_from_beginning: bool = False,
    ) -> None:
        """
        Subscribe to events matching a pattern.

        Args:
            subscriber_name: Unique subscriber identifier
            event_type_pattern: Event type pattern (supports wildcards, e.g., 'contract.*')
            handler: Handler function
            is_active: Whether subscription is active
            consumer_group: Kafka consumer group ID (default: subscriber_name)
            start_from_beginning: If True, start from beginning of topic
        """
        if not is_active:
            logger.debug(
                "kafka_subscription_inactive",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
            )
            return

        # Determine topics to subscribe to
        topics = self._get_topics_for_pattern(event_type_pattern)

        # Create consumer group
        group_id = consumer_group or subscriber_name

        # Create consumer
        consumer_config = self.consumer_config.copy()
        consumer_config["group_id"] = group_id

        if start_from_beginning:
            consumer_config["auto_offset_reset"] = "earliest"
        else:
            consumer_config["auto_offset_reset"] = "latest"

        consumer = KafkaConsumer(*topics, **consumer_config)

        # Store consumer
        self.consumers[subscriber_name] = consumer

        logger.info(
            "kafka_subscription_registered",
            subscriber_name=subscriber_name,
            event_type_pattern=event_type_pattern,
            topics=topics,
            consumer_group=group_id,
        )

        # Start consuming in background (would need threading/async in production)
        # For POC, we'll just register the subscription
        # In production, this would start a background consumer loop

    def _get_topics_for_pattern(self, pattern: str) -> list[str]:
        """
        Get Kafka topics for event type pattern.

        For POC, we subscribe to all event topics and filter in handler.
        In production, could use topic naming conventions.
        """
        # For POC, subscribe to all event topics
        # In production, could use more sophisticated topic routing
        return [f"{self.topic_prefix}.all"]

    def start_consuming(
        self,
        subscriber_name: str,
        handler: Callable[[dict[str, Any]], None],
        timeout_ms: int = 1000,
    ) -> None:
        """
        Start consuming events for a subscriber.

        This is a blocking call and should be run in a background thread/worker.

        Args:
            subscriber_name: Subscriber name
            handler: Handler function
            timeout_ms: Poll timeout in milliseconds
        """
        if subscriber_name not in self.consumers:
            raise KafkaEventBusError(f"Subscriber {subscriber_name} not found")

        consumer = self.consumers[subscriber_name]

        logger.info("kafka_consumer_started", subscriber_name=subscriber_name)

        try:
            while True:
                # Poll for messages
                message_pack = consumer.poll(timeout_ms=timeout_ms)

                for topic_partition, messages in message_pack.items():
                    for message in messages:
                        try:
                            # Extract event
                            event = message.value

                            # Call handler
                            handler(event)

                            # Commit offset after successful processing
                            consumer.commit()

                        except Exception as e:
                            logger.error(
                                "kafka_event_processing_failed",
                                subscriber_name=subscriber_name,
                                topic=topic_partition.topic,
                                partition=topic_partition.partition,
                                offset=message.offset,
                                error=str(e),
                            )
                            # In production, would send to dead letter queue
                            # For POC, we continue processing

        except KeyboardInterrupt:
            logger.info("kafka_consumer_stopped", subscriber_name=subscriber_name)
        finally:
            consumer.close()

    def close(self) -> None:
        """Close all connections."""
        if self.producer:
            self.producer.close()
            self.producer = None

        for consumer in self.consumers.values():
            consumer.close()

        self.consumers.clear()

        logger.info("kafka_event_bus_closed")


def get_kafka_event_bus() -> KafkaEventBus:
    """Get global Kafka event bus instance."""
    if not hasattr(get_kafka_event_bus, "_instance"):
        get_kafka_event_bus._instance = KafkaEventBus()
    return get_kafka_event_bus._instance
