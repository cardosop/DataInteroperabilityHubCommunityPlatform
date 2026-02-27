"""
Platform Admin Views

Platform-level administration endpoints for tenant management.
Unit tests: hub/apps/platform/tests/test_views.py (Gap #2, task 1.5).
"""

import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.permissions import IsPlatformAdmin
from hub.apps.tenants.serializers import (
    TenantSerializer,
    TenantSuspendSerializer,
)
from hub.apps.tenants.services import TenantLifecycleService, TenantUsageService

logger = logging.getLogger(__name__)


class PlatformTenantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Platform admin ViewSet for tenant management.

    Platform admins only - provides tenant suspend/resume and usage monitoring.
    """

    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    lookup_field = "id"

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, id=None):
        """
        Suspend a tenant (platform admin only).

        POST /api/v1/platform/tenants/{id}/suspend/
        Body: {
            "reason": "Optional reason for suspension"
        }
        """
        tenant = self.get_object()

        serializer = TenantSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = TenantLifecycleService(user_id=str(request.user.id))
        try:
            tenant = service.suspend_tenant(
                tenant_id=str(tenant.id), reason=serializer.validated_data.get("reason")
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, id=None):
        """
        Resume a suspended tenant (platform admin only).

        POST /api/v1/platform/tenants/{id}/resume/
        """
        tenant = self.get_object()

        service = TenantLifecycleService(user_id=str(request.user.id))
        try:
            tenant = service.resume_tenant(tenant_id=str(tenant.id))
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        return Response(TenantSerializer(tenant).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="usage")
    def usage(self, request):
        """
        Get usage summary for all tenants (platform admin only).

        GET /api/v1/platform/tenants/usage/

        Returns list of tenants with usage summary for current period.
        """
        from datetime import datetime

        from django.utils import timezone

        from hub.apps.tenants.models import Tenant

        # Get current month
        now = timezone.now()
        month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)

        # Get all tenants
        tenants = Tenant.objects.filter(status="ACTIVE").order_by("name")

        usage_service = TenantUsageService()
        results = []

        for tenant in tenants:
            try:
                # Get usage summary for current month
                usage_summary = usage_service.get_usage_summary(
                    tenant_id=str(tenant.id), period_start=month_start
                )

                # Get plan limits
                plan_limits = {}
                if tenant.plan:
                    plan_limits = tenant.plan.limits_json.copy()

                results.append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.name,
                        "tenant_slug": tenant.slug,
                        "plan_slug": tenant.plan.slug if tenant.plan else None,
                        "plan_tier": tenant.plan.tier if tenant.plan else None,
                        "usage": {
                            "api_calls_count": usage_summary.api_calls_count,
                            "asset_count": usage_summary.asset_count,
                            "dataset_count": usage_summary.dataset_count,
                            "scheduled_ingestion_runs_count": usage_summary.scheduled_ingestion_runs_count,
                            "scheduled_export_runs_count": usage_summary.scheduled_export_runs_count,
                            "storage_bytes": usage_summary.storage_bytes,
                            "storage_gb": usage_summary.get_storage_gb(),
                        },
                        "plan_limits": plan_limits,
                        "period_start": usage_summary.period_start.isoformat(),
                        "period_end": usage_summary.period_end.isoformat(),
                    }
                )
            except Exception as e:
                logger.warning(
                    "failed_to_get_usage_for_tenant",
                    tenant_id=str(tenant.id),
                    error=str(e),
                    message=f"Failed to get usage for tenant {tenant.id}: {e}",
                )
                # Continue with other tenants

        return Response(
            {
                "count": len(results),
                "results": results,
                "period_start": month_start.isoformat(),
                "period_end": usage_summary.period_end.isoformat() if results else None,
            },
            status=status.HTTP_200_OK,
        )


class PlatformUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Platform admin ViewSet for user management.

    Platform admins only - provides user erasure requests.
    """

    from django.contrib.auth import get_user_model

    from hub.apps.users.serializers import UserSerializer

    User = get_user_model()
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    lookup_field = "id"

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="request-erasure")
    def request_erasure(self, request, id=None):
        """
        Create erasure request for a user (platform admin only).

        POST /api/v1/platform/users/{id}/request-erasure/
        """
        user = self.get_object()

        from hub.apps.gdpr.services import ErasureService

        service = ErasureService(user_id=str(request.user.id))
        try:
            erasure_request = service.create_request(user_id=str(user.id))

            # Execute erasure immediately
            try:
                erasure_request = service.execute_erasure(request_id=str(erasure_request.id))
            except Exception as e:
                logger.warning(f"Failed to execute erasure immediately: {e}")

            return Response(
                {
                    "request_id": str(erasure_request.id),
                    "status": erasure_request.status,
                    "requested_at": erasure_request.requested_at.isoformat(),
                    "completed_at": (
                        erasure_request.completed_at.isoformat()
                        if erasure_request.completed_at
                        else None
                    ),
                },
                status=status.HTTP_201_CREATED,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

    @transaction.atomic
    @action(detail=True, methods=["get"], url_path="erasure-requests")
    def erasure_requests(self, request, id=None):
        """
        List erasure requests for a user (platform admin only).

        GET /api/v1/platform/users/{id}/erasure-requests/
        """
        user = self.get_object()

        from hub.apps.gdpr.models import ErasureRequest
        from hub.apps.gdpr.serializers import ErasureRequestSerializer

        requests = ErasureRequest.objects.filter(user=user).order_by("-requested_at")

        serializer = ErasureRequestSerializer(requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
