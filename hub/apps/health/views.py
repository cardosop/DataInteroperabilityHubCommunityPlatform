import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.health.services import HealthService

logger = logging.getLogger(__name__)


def liveness(request):
    """Liveness: process is up (no DB/Redis). Use for Docker/K8s liveness probe."""
    return JsonResponse({"status": "ok"}, status=200)


def health_check(request):
    """Health check endpoint for Docker and load balancers"""
    service = HealthService()
    status = service.get_overall_health_status()

    # Extract http_status and create a copy without it for response
    http_status = status.get("http_status", 200)
    response_data = {k: v for k, v in status.items() if k != "http_status"}

    return JsonResponse(response_data, status=http_status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def circuit_breaker_status(request):
    """
    Circuit breaker aggregate status endpoint for monitoring.

    Phase 221.3.1 — Requires authentication (JWT or API key).
    Kubernetes probes use /health/ and /health/live/ which remain public.

    Phase 221.3.2 — Returns only aggregate counts (total_breakers,
    open_breakers, status).  Individual service names and the
    ?service_name= query parameter have been removed to avoid exposing
    internal service architecture to authenticated but non-admin users.
    """
    service = HealthService()

    try:
        status = service.get_circuit_breaker_status()

        http_status = status.get("http_status", 500)

        # Phase 221.3.2 — Only expose aggregate data; strip service names.
        response_data = {
            "status": status.get("status", "unknown"),
            "total_breakers": status.get("total_breakers", 0),
            "open_breakers": status.get("open_breakers", 0),
        }

        return Response(response_data, status=http_status)

    except Exception:
        # Phase 221.3 — Log the real error server-side; return a generic
        # message to avoid leaking internal paths, class names, or
        # connection strings in the HTTP response.
        logger.exception("circuit_breaker_status_error")
        return Response(
            {"status": "error", "error": "Circuit breaker status unavailable"},
            status=500,
        )
