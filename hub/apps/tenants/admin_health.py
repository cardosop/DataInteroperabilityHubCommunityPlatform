"""
Phase TR.C — PLATFORM_ADMIN health endpoint (mounted at ``/api/v1/admin/health/``).

Returns component-level health status (database, Redis, cache, queue) with
per-service detail that the public ``/health/`` endpoint intentionally omits
for security. Requires PLATFORM_ADMIN authentication.
"""

from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.health.services import HealthService
from hub.apps.tenants.permissions import IsPlatformAdmin


class AdminHealthView(APIView):
    """PLATFORM_ADMIN health-check endpoint.

    GET /api/v1/admin/health/

    Returns complete component status including per-instance Redis
    health and ClamAV/BaaS status when configured.  This endpoint is
    more detailed than the public /health/ — it exposes per-component
    health with error messages for ops debugging during incidents.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get(self, request):
        service = HealthService()
        result = service.get_overall_health_status()
        http_status = result.pop("http_status", status.HTTP_200_OK)
        return Response(result, status=http_status)
