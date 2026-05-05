"""
Contract Security Views

Security audit log and incident management viewsets.

SAVING CHECKPOINT: This module contains security-related viewsets.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from hub.apps.observability.cross_tenant_metrics import cross_tenant_denied
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .models import SecurityAuditLog, SecurityIncident
from .pagination import ContractPageNumberPagination
from .serializers import (
    SecurityAuditLogSerializer,
    SecurityIncidentResolveSerializer,
    SecurityIncidentSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List security audit logs",
        description="""
        List security audit logs with filtering and pagination.

        **Filtering:**
        - `event_type`: Filter by event type (e.g., EXTERNAL_REF_FETCH,
          RATE_LIMIT_EXCEEDED, CACHE_HIT, CACHE_MISS, CACHE_EVICTION,
          SECURITY_VIOLATION)
        - `tenant_id`: Filter by tenant ID
        - `user_id`: Filter by user ID
        - `ref_type`: Filter by ref type (internal, local, external)
        - `cache_operation`: Filter by cache operation (hit, miss, eviction)
        - `start_date`: Filter by start date (ISO 8601 format)
        - `end_date`: Filter by end date (ISO 8601 format)

        **Sorting:**
        - `ordering`: Comma-separated list of fields to sort by
          (e.g., -timestamp,event_type)
        - Default: `-timestamp` (newest first)

        **Access:**
        - Admin only (platform admins)
        """,
        parameters=[
            OpenApiParameter(
                name="event_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by event type",
                required=False,
            ),
            OpenApiParameter(
                name="tenant_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by tenant ID",
                required=False,
            ),
            OpenApiParameter(
                name="user_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Filter by user ID",
                required=False,
            ),
            OpenApiParameter(
                name="ref_type",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by ref type (internal, local, external)",
                required=False,
            ),
            OpenApiParameter(
                name="cache_operation",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by cache operation (hit, miss, eviction)",
                required=False,
            ),
            OpenApiParameter(
                name="start_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter by start date (ISO 8601 format)",
                required=False,
            ),
            OpenApiParameter(
                name="end_date",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="Filter by end date (ISO 8601 format)",
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Comma-separated list of fields to sort by",
                required=False,
            ),
        ],
        tags=["Security"],
    ),
)
class SecurityAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for security audit logs (read-only).

    Provides queryable access to security audit logs with filtering and
    pagination.
    Admin only access.
    """

    queryset = SecurityAuditLog.objects.all()
    serializer_class = SecurityAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ContractPageNumberPagination
    filterset_fields = ["event_type", "ref_type", "cache_operation"]
    ordering_fields = ["timestamp", "event_type", "severity"]
    ordering = ["-timestamp"]

    def get_permissions(self):
        """Require platform admin for all actions."""
        from hub.apps.tenants.permissions import IsPlatformAdmin

        return [permissions.IsAuthenticated(), IsPlatformAdmin()]

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = SecurityAuditLog.objects.all()

        request_tenant_id = get_request_tenant_id(self.request)

        # Filter by event_type
        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by tenant_id
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id and request_tenant_id and str(tenant_id) != str(request_tenant_id):
            cross_tenant_denied(
                endpoint="contracts.security_audit_logs",
                reason="query_tenant_mismatch",
                request=self.request,
                requested_tenant_id=tenant_id,
                actual_tenant_id=request_tenant_id,
            )
            raise PermissionDenied(
                detail={
                    "code": "CROSS_TENANT_FORBIDDEN",
                    "detail": "tenant_id query parameter does not match request tenant",
                }
            )
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        elif request_tenant_id:
            queryset = queryset.filter(tenant_id=request_tenant_id)

        # Filter by user_id
        user_id = self.request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        # Filter by ref_type
        ref_type = self.request.query_params.get("ref_type")
        if ref_type:
            queryset = queryset.filter(ref_type=ref_type)

        # Filter by cache_operation
        cache_operation = self.request.query_params.get("cache_operation")
        if cache_operation:
            queryset = queryset.filter(cache_operation=cache_operation)

        # Filter by time range
        start_date = self.request.query_params.get("start_date")
        if start_date:
            try:
                from django.utils.dateparse import parse_datetime

                start_dt = parse_datetime(start_date)
                if start_dt:
                    queryset = queryset.filter(timestamp__gte=start_dt)
            except (ValueError, TypeError):
                pass

        end_date = self.request.query_params.get("end_date")
        if end_date:
            try:
                from django.utils.dateparse import parse_datetime

                end_dt = parse_datetime(end_date)
                if end_dt:
                    queryset = queryset.filter(timestamp__lte=end_dt)
            except (ValueError, TypeError):
                pass

        # Apply ordering
        ordering_param = self.request.query_params.get("ordering")
        if ordering_param:
            # Parse comma-separated ordering string
            ordering = ordering_param.split(",")
            queryset = queryset.order_by(*ordering)
        else:
            # Use default ordering (already a list)
            queryset = queryset.order_by(*self.ordering)

        return queryset


class SecurityIncidentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for security incident management.

    Provides read-only access to security incidents with filtering by
    severity, status, and time range.
    Admin-only access for security incident resolution.
    """

    queryset = SecurityIncident.objects.all()
    serializer_class = SecurityIncidentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "event_type"]
    ordering_fields = [
        "first_detected_at",
        "severity",
        "status",
        "violation_count",
    ]
    ordering = ["-first_detected_at"]

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters."""
        from django.utils import timezone

        queryset = SecurityIncident.objects.all()

        # Platform admins can see all incidents
        if hasattr(self.request.user, "is_platform_admin") and self.request.user.is_platform_admin:
            pass  # No filtering needed
        else:
            # Regular users can only see incidents for their tenant
            tenant = getattr(self.request, "tenant", None)
            if tenant is None and hasattr(self.request.user, "tenant"):
                tenant = self.request.user.tenant
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            else:
                queryset = queryset.none()

        # Filter by severity
        severity = self.request.query_params.get("severity")
        if severity:
            queryset = queryset.filter(severity=severity.upper())

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        # Filter by event_type
        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by time range
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            try:
                start_dt = timezone.datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                queryset = queryset.filter(first_detected_at__gte=start_dt)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = timezone.datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                queryset = queryset.filter(first_detected_at__lte=end_dt)
            except ValueError:
                pass

        return queryset

    def get_permissions(self):
        """Return appropriate permissions based on action."""
        from hub.apps.tenants.permissions import IsPlatformAdmin

        if self.action == "resolve":
            # Only platform admins can resolve incidents
            return [permissions.IsAuthenticated(), IsPlatformAdmin()]
        return [permissions.IsAuthenticated()]

    @extend_schema(
        summary="Resolve security incident",
        description="Mark a security incident as resolved. Admin only.",
        request=SecurityIncidentResolveSerializer,
        responses={
            200: SecurityIncidentSerializer,
            403: OpenApiResponse(description="Forbidden - Admin access required"),
            404: OpenApiResponse(description="Incident not found"),
        },
        tags=["Security"],
    )
    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, id=None):
        """Resolve a security incident."""
        incident = self.get_object()
        serializer = SecurityIncidentResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resolution_notes = serializer.validated_data.get("resolution_notes", "")
        incident.resolve(resolved_by_user=request.user, resolution_notes=resolution_notes)

        response_serializer = self.get_serializer(incident)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
