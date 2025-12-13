"""
Health check endpoints for event bus service.

Provides HTTP endpoints for health checks and monitoring.
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

from fastapi import FastAPI, HTTPException, Response
from typing import Dict, Any
import time

# Import event bus client using importlib to handle hyphen in module name
import importlib.util
client_module_path = Path(__file__).parent / "client.py"
spec = importlib.util.spec_from_file_location("event_bus_client", str(client_module_path))
client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client_module)
get_event_bus_client = client_module.get_event_bus_client

app = FastAPI(title="Event Bus Health Service", version="1.0.0")
SERVICE_NAME = "event-bus-service"

# Initialize event bus client
event_bus_client = get_event_bus_client()


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns health status of event bus including Redis and database connections.
    """
    health_status = event_bus_client.health_check()
    
    if health_status["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


@app.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint (Kubernetes-style).
    
    Returns 200 OK if service is running.
    """
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "timestamp": time.time()
    }


@app.get("/ready")
async def ready():
    """
    Readiness probe endpoint (Kubernetes-style).
    
    Returns 200 OK if event bus is ready to accept traffic.
    """
    health_status = event_bus_client.health_check()
    
    # Check if Redis is available (critical dependency)
    redis_status = health_status.get("checks", {}).get("redis", {}).get("status")
    
    if redis_status != "ok":
        raise HTTPException(status_code=503, detail=health_status)
    
    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "checks": health_status["checks"],
        "timestamp": time.time()
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns connection pool statistics, health metrics, and event bus metrics.
    """
    pool_stats = event_bus_client.get_connection_pool_stats()
    health_status = event_bus_client.health_check()
    
    # Get event bus metrics from OpenTelemetry registry
    try:
        from hub.apps.observability.otel_metrics import REGISTRY, CONTENT_TYPE_LATEST
        from prometheus_client import generate_latest
        
        if REGISTRY is not None:
            # Generate metrics from OpenTelemetry registry (includes event bus metrics)
            otel_metrics = generate_latest(REGISTRY).decode('utf-8')
        else:
            otel_metrics = ""
    except Exception:
        otel_metrics = ""
    
    # Format as Prometheus metrics
    metrics_lines = []
    
    # Connection pool metrics
    if "error" not in pool_stats:
        metrics_lines.append(f"# HELP event_bus_redis_pool_created_connections Number of created Redis connections")
        metrics_lines.append(f"# TYPE event_bus_redis_pool_created_connections gauge")
        metrics_lines.append(f"event_bus_redis_pool_created_connections {pool_stats['created_connections']}")
        
        metrics_lines.append(f"# HELP event_bus_redis_pool_available_connections Number of available Redis connections")
        metrics_lines.append(f"# TYPE event_bus_redis_pool_available_connections gauge")
        metrics_lines.append(f"event_bus_redis_pool_available_connections {pool_stats['available_connections']}")
        
        metrics_lines.append(f"# HELP event_bus_redis_pool_in_use_connections Number of in-use Redis connections")
        metrics_lines.append(f"# TYPE event_bus_redis_pool_in_use_connections gauge")
        metrics_lines.append(f"event_bus_redis_pool_in_use_connections {pool_stats['in_use_connections']}")
        
        metrics_lines.append(f"# HELP event_bus_redis_pool_max_connections Maximum number of Redis connections")
        metrics_lines.append(f"# TYPE event_bus_redis_pool_max_connections gauge")
        metrics_lines.append(f"event_bus_redis_pool_max_connections {pool_stats['max_connections']}")
        
        metrics_lines.append(f"# HELP event_bus_redis_pool_utilization_percent Redis connection pool utilization percentage")
        metrics_lines.append(f"# TYPE event_bus_redis_pool_utilization_percent gauge")
        metrics_lines.append(f"event_bus_redis_pool_utilization_percent {pool_stats['connection_utilization']}")
    
    # Health check metrics
    redis_check = health_status.get("checks", {}).get("redis", {})
    if redis_check.get("status") == "ok":
        metrics_lines.append(f"# HELP event_bus_redis_latency_ms Redis ping latency in milliseconds")
        metrics_lines.append(f"# TYPE event_bus_redis_latency_ms gauge")
        metrics_lines.append(f"event_bus_redis_latency_ms {redis_check.get('latency_ms', 0)}")
    
    metrics_lines.append(f"# HELP event_bus_health_status Event bus health status (1=healthy, 0=unhealthy)")
    metrics_lines.append(f"# TYPE event_bus_health_status gauge")
    health_value = 1 if health_status["status"] == "healthy" else 0
    metrics_lines.append(f"event_bus_health_status {health_value}")
    
    # Combine custom metrics with OpenTelemetry metrics
    custom_metrics = "\n".join(metrics_lines)
    if otel_metrics:
        metrics_content = custom_metrics + "\n" + otel_metrics
    else:
        metrics_content = custom_metrics
    
    return Response(content=metrics_content, media_type="text/plain")


@app.get("/stats")
async def stats():
    """
    Get event bus statistics.
    
    Returns connection pool stats and health information.
    """
    pool_stats = event_bus_client.get_connection_pool_stats()
    health_status = event_bus_client.health_check()
    
    return {
        "connection_pool": pool_stats,
        "health": health_status,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("EVENT_BUS_HEALTH_PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)

