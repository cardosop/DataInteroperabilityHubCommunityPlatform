import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.health.services import HealthService

logger = logging.getLogger(__name__)


def liveness(_request):
    """Liveness: process is up (no DB/Redis). Use for Docker/K8s liveness probe."""
    return JsonResponse({"status": "ok"}, status=200)


def health_check(_request):
    """Health check endpoint for Docker and load balancers"""
    service = HealthService()
    status = service.get_overall_health_status()

    # Extract http_status and create a copy without it for response
    http_status = status.get("http_status", 200)
    response_data = {k: v for k, v in status.items() if k != "http_status"}

    return JsonResponse(response_data, status=http_status)


def business_rules_health(_request):
    """GET /api/v1/health/business-rules — business-rules subsystem health.

    Phase P.8 D4 — the handler existed in
    ``hub.apps.core.business_rules.health`` since Phase 274.16.12 but no
    URL configuration exposed it. Payload contract (documented in
    docs/BUSINESS_RULES_FRAMEWORK_GUIDE.md): ``{status, degraded_rules,
    degraded_count}``; an SRE alert reads ``degraded_count > 0``. Plain
    Django view (like ``/health/`` and ``/health/live/``) so the probe
    needs no credentials and the DRF schema is unaffected.
    """
    from hub.apps.core.business_rules.health import health_check

    return JsonResponse(health_check(), status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def circuit_breaker_status(_request):
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
