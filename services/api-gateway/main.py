"""
API Gateway Service

FastAPI service that provides API Gateway functionality:
- Request routing to backend services
- API key authentication and validation
- Rate limiting (per-tier, per-tenant, per-user)
- Request/response logging
- Distributed tracing (OpenTelemetry)
- Error handling and transformation
"""
import os
import sys
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import structlog

# Setup Django before importing models (for API key manager)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

# Import shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.metrics import get_metrics_response, get_status_class, normalize_route
from shared.tracing import setup_opentelemetry_fastapi

# Import service modules
# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from rate_limiter import RateLimiter
from api_key_manager import APIKeyManager
from middleware import APIGatewayMiddleware
from routing import ROUTE_CONFIG, validate_route_config

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="API Gateway Service",
    version="1.0.0",
    description="API Gateway with authentication, rate limiting, and request routing"
)

SERVICE_NAME = "api-gateway"

# Setup OpenTelemetry tracing
tracer = setup_opentelemetry_fastapi(SERVICE_NAME)
if tracer:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        logger.warning("OpenTelemetry FastAPI instrumentation not available")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize rate limiter and API key manager
rate_limiter = RateLimiter()
api_key_manager = APIKeyManager()

# Validate route configuration on startup
try:
    validate_route_config(ROUTE_CONFIG)
    logger.info(
        "route_config_validated",
        route_count=len(ROUTE_CONFIG),
        routes=list(ROUTE_CONFIG.keys())
    )
except ValueError as e:
    logger.error("route_config_validation_failed", error=str(e))
    raise

# Add API Gateway middleware
app.add_middleware(
    APIGatewayMiddleware,
    rate_limiter=rate_limiter,
    api_key_manager=api_key_manager
)


@app.get("/health")
async def health_check():
    """Health check endpoint for API Gateway"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0"
    }


@app.get("/api/v1/health")
async def aggregate_health_check():
    """
    Aggregate health check endpoint that checks all backend services.

    Returns health status of all backend services configured in routing.
    """
    import httpx
    from routing import ROUTE_CONFIG

    health_status = {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "backend_services": {}
    }

    # Get unique backend service URLs from route config
    backend_urls = set(ROUTE_CONFIG.values())

    # Check health of each backend service
    async with httpx.AsyncClient(timeout=5.0) as client:
        for backend_url in backend_urls:
            service_name = backend_url.split('//')[1].split(':')[0] if '//' in backend_url else backend_url
            try:
                # Try health check endpoint
                health_url = f"{backend_url.rstrip('/')}/health"
                response = await client.get(health_url)
                health_status["backend_services"][service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code,
                    "url": backend_url
                }
            except Exception as e:
                health_status["backend_services"][service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "url": backend_url
                }
                health_status["status"] = "degraded"

    # Determine overall status
    unhealthy_count = sum(
        1 for svc in health_status["backend_services"].values()
        if svc.get("status") != "healthy"
    )

    if unhealthy_count > 0:
        health_status["status"] = "degraded"
        health_status["unhealthy_services"] = unhealthy_count

    return health_status


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    metrics_data, content_type = get_metrics_response()
    return Response(content=metrics_data, media_type=content_type)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', '8088'))
    uvicorn.run(app, host="0.0.0.0", port=port)
