"""
Event Bus Client Library

Provides a high-level client library for the event bus with connection pooling,
health checks, and monitoring capabilities.
"""
import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

import redis
import time
import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from hub.apps.core.events.bus import EventBus, EventBusError, EventPublishError

logger = logging.getLogger(__name__)


class EventBusClient:
    """
    High-level event bus client with connection pooling and health checks.
    
    Provides a wrapper around EventBus with additional features:
    - Connection pooling management
    - Health check capabilities
    - Connection retry logic
    - Metrics and monitoring
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize event bus client.
        
        Args:
            redis_client: Optional Redis client (creates new with pooling if not provided)
        """
        self._event_bus = EventBus(redis_client=redis_client)
        self._redis_client = self._event_bus.redis_client
        self._last_health_check = None
        self._health_check_interval = getattr(settings, 'EVENT_BUS_HEALTH_CHECK_INTERVAL', 30)
    
    @property
    def event_bus(self) -> EventBus:
        """Get underlying EventBus instance."""
        return self._event_bus
    
    @property
    def redis_client(self) -> redis.Redis:
        """Get Redis client."""
        return self._redis_client
    
    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        event_version: str = "1.0.0"
    ) -> str:
        """
        Publish an event to the event bus.
        
        Args:
            event_type: Event type (e.g., 'contract.created')
            data: Event data payload
            tenant_id: Tenant UUID (optional)
            user_id: User UUID (optional)
            request_id: Request ID for tracing (optional)
            correlation_id: Correlation ID for tracing (optional)
            causation_id: Event ID that caused this event (optional)
            tags: Tags for filtering (optional)
            event_version: Schema version (default: '1.0.0')
            
        Returns:
            Event ID (UUID string)
            
        Raises:
            EventPublishError: If event publishing fails
        """
        return self._event_bus.publish(
            event_type=event_type,
            data=data,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            tags=tags,
            event_version=event_version
        )
    
    def subscribe(
        self,
        subscriber_name: str,
        event_type_pattern: str,
        handler: callable,
        is_active: bool = True
    ) -> None:
        """
        Subscribe to events matching a pattern.
        
        Args:
            subscriber_name: Unique subscriber identifier
            event_type_pattern: Event type pattern (supports wildcards)
            handler: Callback function to handle events
            is_active: Whether subscription is active
        """
        self._event_bus.subscribe(
            subscriber_name=subscriber_name,
            event_type_pattern=event_type_pattern,
            handler=handler,
            is_active=is_active
        )
    
    def start_listening(
        self,
        subscriber_name: str,
        handler: callable
    ) -> None:
        """
        Start listening for events (blocking).
        
        Args:
            subscriber_name: Subscriber identifier
            handler: Event handler function
        """
        self._event_bus.start_listening(subscriber_name=subscriber_name, handler=handler)
    
    def replay_events(
        self,
        event_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        start_time: Optional[Any] = None,
        end_time: Optional[Any] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Replay events from persistence store.
        
        Args:
            event_type: Filter by event type (optional)
            tenant_id: Filter by tenant ID (optional)
            start_time: Start time for replay (optional)
            end_time: End time for replay (optional)
            limit: Maximum number of events to replay
            
        Returns:
            List of event dictionaries
        """
        return self._event_bus.replay_events(
            event_type=event_type,
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on event bus.
        
        Checks:
        - Redis connection
        - Connection pool status
        - Database connection (for persistence)
        
        Returns:
            Health check result dictionary
        """
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {}
        }
        
        # Check Redis connection
        try:
            start_time = time.time()
            self._redis_client.ping()
            redis_latency = (time.time() - start_time) * 1000  # Convert to ms
            
            health_status["checks"]["redis"] = {
                "status": "ok",
                "latency_ms": round(redis_latency, 2)
            }
            
            # Check connection pool
            if hasattr(self._redis_client, 'connection_pool'):
                pool = self._redis_client.connection_pool
                health_status["checks"]["redis"]["pool"] = {
                    "created_connections": pool.created_connections,
                    "available_connections": len(pool._available_connections),
                    "in_use_connections": pool.created_connections - len(pool._available_connections),
                    "max_connections": pool.max_connections
                }
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["checks"]["redis"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Check database connection (for persistence)
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status["checks"]["database"] = {
                "status": "ok"
            }
        except Exception as e:
            health_status["status"] = "degraded"  # Degraded, not unhealthy (Redis is critical)
            health_status["checks"]["database"] = {
                "status": "error",
                "error": str(e)
            }
        
        self._last_health_check = time.time()
        return health_status
    
    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.
        
        Returns:
            Connection pool statistics dictionary
        """
        if not hasattr(self._redis_client, 'connection_pool') or self._redis_client.connection_pool is None:
            return {"error": "Connection pool not available"}
        
        pool = self._redis_client.connection_pool
        return {
            "created_connections": pool.created_connections,
            "available_connections": len(pool._available_connections),
            "in_use_connections": pool.created_connections - len(pool._available_connections),
            "max_connections": pool.max_connections,
            "connection_utilization": round(
                (pool.created_connections / pool.max_connections * 100) if pool.max_connections > 0 else 0,
                2
            )
        }


# Global event bus client instance
_event_bus_client: Optional[EventBusClient] = None


def get_event_bus_client() -> EventBusClient:
    """Get global event bus client instance."""
    global _event_bus_client
    if _event_bus_client is None:
        _event_bus_client = EventBusClient()
    return _event_bus_client

