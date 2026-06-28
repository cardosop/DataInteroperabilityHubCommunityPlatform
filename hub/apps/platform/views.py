"""
Platform Admin Views

Platform-level administration endpoints for tenant management.
Unit tests: hub/apps/platform/tests/test_views.py (Gap #2, task 1.5).
"""

import logging
import uuid

from django.db import transaction
from drf_spectacular.utils import extend_schema
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

    @extend_schema(
        summary="List all tenants",
        description="Platform-admin only. Returns paginated list of all tenants.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve a tenant",
        description="Platform-admin only. Returns a single tenant by ID.",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

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
        from datetime import datetime, timedelta

        from django.utils import timezone

        from hub.apps.tenants.models import Tenant, TenantStatus
        from hub.apps.tenants.request_tenant import tenant_context

        # Get current month
        now = timezone.now()
        month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        if month_start.month == 12:
            period_end = datetime(
                month_start.year + 1, 1, 1, tzinfo=month_start.tzinfo
            ) - timedelta(seconds=1)
        else:
            period_end = datetime(
                month_start.year,
                month_start.month + 1,
                1,
                tzinfo=month_start.tzinfo,
            ) - timedelta(seconds=1)

        # Optional tenant_id filter for O(1) single-tenant lookup
        # (used by integration tests to avoid O(n) iteration over
        # thousands of --reuse-db tenants).
        tenant_id_filter = request.query_params.get("tenant_id")
        if tenant_id_filter:
            try:
                uuid.UUID(tenant_id_filter)
            except (ValueError, AttributeError):
                return Response(
                    {"error": "tenant_id must be a valid UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Get all tenants (ACTIVE and SUSPENDED for usage visibility)
        tenant_qs = Tenant.objects.filter(
            status__in=[TenantStatus.ACTIVE, TenantStatus.SUSPENDED]
        ).order_by("name")
        if tenant_id_filter:
            tenant_qs = tenant_qs.filter(id=tenant_id_filter)
        tenants = tenant_qs

        usage_service = TenantUsageService()
        results = []

        for tenant in tenants:
            try:
                # Switch RLS context to this tenant so the usage-summary
                # lookup passes the tenant_isolation RLS policy on
                # tenant_usage_summaries.
                with tenant_context(str(tenant.id)):
                    usage_summary = usage_service.get_usage_summary(
                        tenant_id=str(tenant.id), period_start=month_start
                    )

                    plan_limits = {}
                    if tenant.plan and tenant.plan.limits_json:
                        plan_limits = dict(tenant.plan.limits_json)

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
            except (ServiceValidationError, NotFoundError) as e:
                logger.warning(
                    "Failed to get usage for tenant %s: %s",
                    tenant.id,
                    e,
                )
                continue
            except Exception as e:
                logger.error(
                    "Unexpected error getting usage for tenant %s: %s",
                    tenant.id,
                    e,
                    exc_info=True,
                )
                # Track the failure but continue processing remaining tenants.
                # Include failure metadata in results so callers can detect
                # partial responses (Phase 274 health contract).
                results.append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.name,
                        "tenant_slug": tenant.slug,
                        "error": "USAGE_CALCULATION_FAILED",
                        "error_detail": str(e)[:256],
                    }
                )
                continue

        return Response(
            {
                "count": len(results),
                "results": results,
                "period_start": month_start.isoformat(),
                "period_end": period_end.isoformat(),
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
            execution_error = None
            try:
                erasure_request = service.execute_erasure(request_id=str(erasure_request.id))
            except (ServiceValidationError, NotFoundError) as e:
                execution_error = str(e)[:256]
                logger.warning(
                    "Erasure execution deferred for request %s: %s",
                    erasure_request.id,
                    e,
                )
            except Exception:
                execution_error = "Internal erasure execution error"
                logger.error(
                    "Unexpected error executing erasure for request %s",
                    erasure_request.id,
                    exc_info=True,
                )

            response_data = {
                "request_id": str(erasure_request.id),
                "status": erasure_request.status,
                "requested_at": erasure_request.requested_at.isoformat(),
                "completed_at": (
                    erasure_request.completed_at.isoformat()
                    if erasure_request.completed_at
                    else None
                ),
            }
            if execution_error:
                response_data["execution_error"] = execution_error
            return Response(response_data, status=status.HTTP_201_CREATED)
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
