"""
Integration tests for event bus client library.
"""
import pytest
import os
import sys
import django
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root and services to path
project_root = Path(__file__).parent.parent.parent.parent
services_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(services_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from django.test import TestCase, override_settings
# Import client module using importlib to handle hyphen in directory name
import importlib.util
client_module_path = Path(__file__).parent.parent / "client.py"
client_spec = importlib.util.spec_from_file_location("event_bus_client", str(client_module_path))
event_bus_client = importlib.util.module_from_spec(client_spec)
client_spec.loader.exec_module(event_bus_client)
EventBusClient = event_bus_client.EventBusClient
get_event_bus_client = event_bus_client.get_event_bus_client
from hub.apps.core.events.bus import EventBus


class EventBusClientTest(TestCase):
    """Test event bus client functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use mock Redis client
        self.redis_client = Mock()
        self.redis_client.publish.return_value = 1
        self.redis_client.ping.return_value = True
        
        # Mock connection pool
        self.connection_pool = Mock()
        self.connection_pool.created_connections = 5
        self.connection_pool.max_connections = 100
        self.connection_pool._available_connections = [Mock(), Mock(), Mock()]
        self.redis_client.connection_pool = self.connection_pool
        
        self.client = EventBusClient(redis_client=self.redis_client)
    
    def test_client_initialization(self):
        """Test client initialization."""
        self.assertIsNotNone(self.client.event_bus)
        self.assertIsNotNone(self.client.redis_client)
    
    def test_publish_event(self):
        """Test publishing an event."""
        import uuid
        event_id = self.client.publish(
            event_type="contract.created",
            data={"contract_id": str(uuid.uuid4())}
        )
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)
    
    def test_health_check_healthy(self):
        """Test health check when all systems are healthy."""
        health_status = self.client.health_check()
        
        self.assertEqual(health_status["status"], "healthy")
        self.assertIn("checks", health_status)
        self.assertEqual(health_status["checks"]["redis"]["status"], "ok")
    
    def test_health_check_redis_failure(self):
        """Test health check when Redis fails."""
        self.redis_client.ping.side_effect = Exception("Redis connection failed")
        
        health_status = self.client.health_check()
        
        self.assertEqual(health_status["status"], "unhealthy")
        self.assertEqual(health_status["checks"]["redis"]["status"], "error")
    
    def test_get_connection_pool_stats(self):
        """Test getting connection pool statistics."""
        stats = self.client.get_connection_pool_stats()
        
        self.assertEqual(stats["created_connections"], 5)
        self.assertEqual(stats["max_connections"], 100)
        self.assertEqual(stats["available_connections"], 3)
        self.assertEqual(stats["in_use_connections"], 2)
        self.assertIn("connection_utilization", stats)
    
    def test_get_connection_pool_stats_no_pool(self):
        """Test getting stats when connection pool is not available."""
        # Create a new client with no connection pool
        redis_client_no_pool = Mock()
        redis_client_no_pool.connection_pool = None
        client_no_pool = EventBusClient(redis_client=redis_client_no_pool)
        
        stats = client_no_pool.get_connection_pool_stats()
        
        self.assertIn("error", stats)
    
    def test_subscribe(self):
        """Test subscribing to events."""
        handler = Mock()
        
        # Patch the event bus subscribe method to verify it's called
        with patch.object(self.client._event_bus, 'subscribe') as mock_subscribe:
            self.client.subscribe(
                subscriber_name="test_subscriber",
                event_type_pattern="contract.*",
                handler=handler
            )
            
            # Verify subscription was registered
            mock_subscribe.assert_called_once_with(
                subscriber_name="test_subscriber",
                event_type_pattern="contract.*",
                handler=handler,
                is_active=True
            )
    
    def test_replay_events(self):
        """Test replaying events."""
        events = self.client.replay_events(limit=10)
        
        self.assertIsInstance(events, list)
    
    @override_settings(EVENT_BUS_REDIS_POOL_SIZE=25)
    @override_settings(EVENT_BUS_REDIS_MAX_CONNECTIONS=50)
    def test_connection_pool_configuration(self):
        """Test connection pool configuration from settings."""
        # Create new client to pick up settings
        import redis as redis_module
        with patch.object(redis_module, 'ConnectionPool') as mock_pool_class, \
             patch.object(redis_module, 'Redis') as mock_redis_class:
            mock_pool = Mock()
            mock_pool.max_connections = 50
            mock_pool.created_connections = 0
            mock_pool._available_connections = []
            mock_pool_class.from_url.return_value = mock_pool
            mock_redis_client = Mock()
            mock_redis_client.connection_pool = mock_pool
            mock_redis_client.ping.return_value = True
            mock_redis_class.return_value = mock_redis_client
            
            client = EventBusClient()
            
            # Verify connection pool was created with correct settings
            mock_pool_class.from_url.assert_called_once()
            call_kwargs = mock_pool_class.from_url.call_args[1]
            self.assertEqual(call_kwargs['max_connections'], 50)


class EventBusClientIntegrationTest(TestCase):
    """Integration tests for event bus client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = get_event_bus_client()
    
    def test_get_event_bus_client_singleton(self):
        """Test that get_event_bus_client returns singleton."""
        client1 = get_event_bus_client()
        client2 = get_event_bus_client()
        
        self.assertIs(client1, client2)
    
    def test_client_properties(self):
        """Test client properties."""
        self.assertIsNotNone(self.client.event_bus)
        self.assertIsNotNone(self.client.redis_client)
        self.assertIsInstance(self.client.event_bus, EventBus)

