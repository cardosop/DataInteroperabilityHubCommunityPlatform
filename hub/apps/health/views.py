from django.http import JsonResponse

from hub.apps.health.services import HealthService


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


def circuit_breaker_status(request):
    """
    Circuit breaker status endpoint for monitoring.

    Returns status of all circuit breakers or a specific one if service_name is provided.

    Query parameters:
        service_name: Optional service name to get status for specific circuit breaker
    """
    service = HealthService()
    service_name = request.GET.get("service_name", None)

    try:
        status = service.get_circuit_breaker_status(service_name=service_name)

        # Extract http_status and create a copy without it for response
        http_status = status.get("http_status", 500)
        response_data = {k: v for k, v in status.items() if k != "http_status"}

        return JsonResponse(response_data, status=http_status)

    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
