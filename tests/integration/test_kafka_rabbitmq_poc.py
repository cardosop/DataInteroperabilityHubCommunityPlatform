"""
Proof-of-Concept Tests: Kafka and RabbitMQ Event Bus Implementations

These tests validate the proof-of-concept implementations of Kafka and RabbitMQ
as alternatives to the current Redis Pub/Sub event bus.

Tests verify:
- API compatibility with current event bus
- Basic publish/subscribe functionality
- Performance characteristics
- Error handling

Note: These tests require Kafka and RabbitMQ to be running (or will skip gracefully).
"""

import time
import uuid
from typing import Any

import pytest
from django.test import TestCase

# Try to import POC implementations
try:
    from hub.apps.core.events.kafka_poc import KAFKA_AVAILABLE, KafkaEventBus
except ImportError:
    KAFKA_AVAILABLE = False
    KafkaEventBus = None

try:
    from hub.apps.core.events.rabbitmq_poc import RABBITMQ_AVAILABLE, RabbitMQEventBus
except ImportError:
    RABBITMQ_AVAILABLE = False
    RabbitMQEventBus = None

# Import current event bus for comparison
from hub.apps.core.events.bus import get_event_bus


@pytest.mark.django_db(transaction=True)
class KafkaPOCTest(TestCase):
    """Proof-of-concept tests for Kafka event bus implementation"""

    def setUp(self):
        """Set up test fixtures"""
        if not KAFKA_AVAILABLE:
            pytest.skip("kafka-python not installed")

        # Generate valid UUIDs for testing
        self.test_tenant_id = str(uuid.uuid4())
        self.test_user_id = str(uuid.uuid4())

        # Check if Kafka is available
        try:
            self.kafka_bus = KafkaEventBus()
            # Try to create producer to test connection
            self.kafka_bus._get_producer()
            # If we get here, Kafka is available
            self.kafka_available = True
        except Exception as e:
            self.kafka_available = False
            pytest.skip(f"Kafka not available: {e}")

    def tearDown(self):
        """Clean up"""
        if hasattr(self, "kafka_bus") and self.kafka_bus:
            self.kafka_bus.close()

    def test_kafka_publish_basic(self):
        """Test basic event publishing to Kafka"""
        event_id = self.kafka_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        self.assertEqual(len(event_id), 36)  # UUID length

    def test_kafka_publish_with_metadata(self):
        """Test publishing event with full metadata"""
        event_id = self.kafka_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
            user_id=self.test_user_id,
            request_id="test-request",
            correlation_id="test-correlation",
            causation_id=str(uuid.uuid4()),
            tags=["tag1", "tag2"],
        )

        self.assertIsNotNone(event_id)

    def test_kafka_subscribe_basic(self):
        """Test basic subscription to Kafka"""
        received_events = []

        def handler(event: dict[str, Any]):
            received_events.append(event)

        # Subscribe (registration only, not consuming)
        self.kafka_bus.subscribe(
            subscriber_name="test-subscriber", event_type_pattern="contract.*", handler=handler
        )

        # Verify subscription registered
        self.assertIn("test-subscriber", self.kafka_bus.consumers)

    def test_kafka_api_compatibility(self):
        """Test that Kafka POC maintains API compatibility"""
        # Test that publish signature matches current EventBus
        event_id = self.kafka_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)


@pytest.mark.django_db(transaction=True)
class RabbitMQPOCTest(TestCase):
    """Proof-of-concept tests for RabbitMQ event bus implementation"""

    def setUp(self):
        """Set up test fixtures"""
        if not RABBITMQ_AVAILABLE:
            pytest.skip("pika not installed")

        # Generate valid UUIDs for testing
        self.test_tenant_id = str(uuid.uuid4())
        self.test_user_id = str(uuid.uuid4())

        # Check if RabbitMQ is available
        try:
            self.rabbitmq_bus = RabbitMQEventBus()
            # Try to establish connection
            self.rabbitmq_bus._ensure_connection()
            # If we get here, RabbitMQ is available
            self.rabbitmq_available = True
        except Exception as e:
            self.rabbitmq_available = False
            pytest.skip(f"RabbitMQ not available: {e}")

    def tearDown(self):
        """Clean up"""
        if hasattr(self, "rabbitmq_bus") and self.rabbitmq_bus:
            self.rabbitmq_bus.close()

    def test_rabbitmq_publish_basic(self):
        """Test basic event publishing to RabbitMQ"""
        event_id = self.rabbitmq_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
        self.assertEqual(len(event_id), 36)  # UUID length

    def test_rabbitmq_publish_with_metadata(self):
        """Test publishing event with full metadata"""
        event_id = self.rabbitmq_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
            user_id=self.test_user_id,
            request_id="test-request",
            correlation_id="test-correlation",
            causation_id=str(uuid.uuid4()),
            tags=["tag1", "tag2"],
        )

        self.assertIsNotNone(event_id)

    def test_rabbitmq_subscribe_basic(self):
        """Test basic subscription to RabbitMQ"""
        received_events = []

        def handler(event: dict[str, Any]):
            received_events.append(event)

        # Subscribe
        self.rabbitmq_bus.subscribe(
            subscriber_name="test-subscriber", event_type_pattern="contract.*", handler=handler
        )

        # Verify subscription registered
        self.assertIn("test-subscriber", self.rabbitmq_bus.queues)

    def test_rabbitmq_api_compatibility(self):
        """Test that RabbitMQ POC maintains API compatibility"""
        # Test that publish signature matches current EventBus
        event_id = self.rabbitmq_bus.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())},
            tenant_id=self.test_tenant_id,
        )

        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)


@pytest.mark.django_db(transaction=True)
class PerformanceComparisonTest(TestCase):
    """Performance comparison tests between Redis Pub/Sub, Kafka, and RabbitMQ"""

    def setUp(self):
        """Set up test fixtures"""
        # Generate valid UUIDs for testing
        self.test_tenant_id = str(uuid.uuid4())
        self.test_user_id = str(uuid.uuid4())

        # Current Redis Pub/Sub event bus
        self.redis_bus = get_event_bus()

        # Kafka bus (if available)
        if KAFKA_AVAILABLE:
            try:
                self.kafka_bus = KafkaEventBus()
                self.kafka_bus._get_producer()  # Test connection
                self.kafka_available = True
            except Exception:
                self.kafka_available = False
        else:
            self.kafka_available = False

        # RabbitMQ bus (if available)
        if RABBITMQ_AVAILABLE:
            try:
                self.rabbitmq_bus = RabbitMQEventBus()
                self.rabbitmq_bus._ensure_connection()
                self.rabbitmq_available = True
            except Exception:
                self.rabbitmq_available = False
        else:
            self.rabbitmq_available = False

    def tearDown(self):
        """Clean up"""
        if hasattr(self, "kafka_bus") and self.kafka_bus:
            self.kafka_bus.close()
        if hasattr(self, "rabbitmq_bus") and self.rabbitmq_bus:
            self.rabbitmq_bus.close()

    def test_publish_throughput_comparison(self):
        """Compare publish throughput between implementations"""
        num_events = 100

        results = {}

        # Test Redis Pub/Sub
        start_time = time.time()
        for _i in range(num_events):
            # Generate new contract_id for each event
            event_data = {"contract_id": str(uuid.uuid4())}
            self.redis_bus.publish(
                event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
            )
        redis_time = time.time() - start_time
        results["redis"] = {
            "time": redis_time,
            "throughput": num_events / redis_time if redis_time > 0 else 0,
        }

        # Test Kafka (if available)
        if self.kafka_available:
            start_time = time.time()
            for _i in range(num_events):
                # Generate new contract_id for each event
                event_data = {"contract_id": str(uuid.uuid4())}
                self.kafka_bus.publish(
                    event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
                )
            kafka_time = time.time() - start_time
            results["kafka"] = {
                "time": kafka_time,
                "throughput": num_events / kafka_time if kafka_time > 0 else 0,
            }

        # Test RabbitMQ (if available)
        if self.rabbitmq_available:
            start_time = time.time()
            for _i in range(num_events):
                # Generate new contract_id for each event
                event_data = {"contract_id": str(uuid.uuid4())}
                self.rabbitmq_bus.publish(
                    event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
                )
            rabbitmq_time = time.time() - start_time
            results["rabbitmq"] = {
                "time": rabbitmq_time,
                "throughput": num_events / rabbitmq_time if rabbitmq_time > 0 else 0,
            }

        # Log results
        print(f"\n=== Publish Throughput Comparison ({num_events} events) ===")
        for impl, metrics in results.items():
            print(
                f"{impl.upper()}: {metrics['throughput']:.2f} events/sec ({metrics['time']:.3f}s)"
            )

        # Verify all implementations completed
        self.assertIn("redis", results)
        if self.kafka_available:
            self.assertIn("kafka", results)
        if self.rabbitmq_available:
            self.assertIn("rabbitmq", results)

    def test_publish_latency_comparison(self):
        """Compare publish latency between implementations"""
        num_events = 50

        results = {}

        # Test Redis Pub/Sub
        latencies = []
        for _i in range(num_events):
            # Generate new contract_id for each event
            event_data = {"contract_id": str(uuid.uuid4())}
            start = time.time()
            self.redis_bus.publish(
                event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
            )
            latencies.append((time.time() - start) * 1000)  # Convert to ms

        results["redis"] = {
            "avg": sum(latencies) / len(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "p95": sorted(latencies)[int(len(latencies) * 0.95)],
        }

        # Test Kafka (if available)
        if self.kafka_available:
            latencies = []
            for _i in range(num_events):
                # Generate new contract_id for each event
                event_data = {"contract_id": str(uuid.uuid4())}
                start = time.time()
                self.kafka_bus.publish(
                    event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
                )
                latencies.append((time.time() - start) * 1000)

            results["kafka"] = {
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            }

        # Test RabbitMQ (if available)
        if self.rabbitmq_available:
            latencies = []
            for _i in range(num_events):
                # Generate new contract_id for each event
                event_data = {"contract_id": str(uuid.uuid4())}
                start = time.time()
                self.rabbitmq_bus.publish(
                    event_type="contract.created", data=event_data, tenant_id=self.test_tenant_id
                )
                latencies.append((time.time() - start) * 1000)

            results["rabbitmq"] = {
                "avg": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            }

        # Log results
        print(f"\n=== Publish Latency Comparison ({num_events} events) ===")
        for impl, metrics in results.items():
            print(
                f"{impl.upper()}: avg={metrics['avg']:.2f}ms, min={metrics['min']:.2f}ms, max={metrics['max']:.2f}ms, p95={metrics['p95']:.2f}ms"
            )

        # Verify all implementations completed
        self.assertIn("redis", results)
        if self.kafka_available:
            self.assertIn("kafka", results)
        if self.rabbitmq_available:
            self.assertIn("rabbitmq", results)
