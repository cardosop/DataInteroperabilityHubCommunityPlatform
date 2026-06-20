"""
Retention Policy Views

REST API views for retention policy management.
"""

import structlog
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.tenants.request_tenant import get_request_tenant, get_request_tenant_id

from .models import RetentionPolicy
from .serializers import RetentionPolicySerializer
from .services import GovernanceService

logger = structlog.get_logger(__name__)


class RetentionPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for retention policy management.

    Tenant-scoped: users can only see/manage retention policies in their tenant.
    """

    queryset = RetentionPolicy.objects.all()
    serializer_class = RetentionPolicySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all retention policies
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = RetentionPolicy.objects.all()
        else:
            # Use central helper for tenant resolution (Phase 10.1.11)
            tenant_id = get_request_tenant_id(self.request)
            if tenant_id:
                queryset = RetentionPolicy.objects.filter(tenant_id=tenant_id)
            else:
                queryset = RetentionPolicy.objects.none()

        # Apply filters
        asset_id = self.request.query_params.get("asset_id")
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        dataset_id = self.request.query_params.get("dataset_id")
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)

        file_id = self.request.query_params.get("file_id")
        if file_id:
            queryset = queryset.filter(file_id=file_id)

        enabled = self.request.query_params.get("enabled")
        if enabled is not None:
            queryset = queryset.filter(enabled=enabled.lower() == "true")

        return queryset.order_by("-created_at")

    @transaction.atomic
    def create(self, request):
        """
        Create a retention policy via service layer (Phase 12.1.2).

        POST /api/v1/governance/retention-policies/
        Body: {
            "name": "string" (required),
            "description": "string" (optional),
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional),
            "policy_type": "TIME_BASED" | "EVENT_BASED" (required),
            "retention_period_days": int (required for TIME_BASED),
            "event_trigger": "string" (required for EVENT_BASED),
            "action": "SOFT_DELETE" | "HARD_DELETE" | "ARCHIVE" (optional, default: SOFT_DELETE),
            "grace_period_days": int (optional, default: 30),
            "legal_hold": bool (optional, default: false),
            "legal_hold_reason": "string" (optional),
            "legal_hold_expires_at": "ISO datetime" (optional),
            "enabled": bool (optional, default: true)
        }
        """
        # Use central helper for tenant resolution (Phase 10.1.11)
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create retention policies"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate request data via serializer (request validation only)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract IDs from request data (serializer may convert to objects, but we need IDs for service)
        # Try to get from validated_data first (if serializer converted to objects), then fallback to request.data
        asset_id = None
        if serializer.validated_data.get("asset"):
            asset_id = str(serializer.validated_data["asset"].id)
        elif request.data.get("asset_id"):
            asset_id = request.data.get("asset_id")

        dataset_id = None
        if serializer.validated_data.get("dataset"):
            dataset_id = str(serializer.validated_data["dataset"].id)
        elif request.data.get("dataset_id"):
            dataset_id = request.data.get("dataset_id")

        file_id = None
        if serializer.validated_data.get("file"):
            file_id = str(serializer.validated_data["file"].id)
        elif request.data.get("file_id"):
            file_id = request.data.get("file_id")

        # Create retention policy via service layer (Phase 12.1.2)
        # Service handles validation, persistence, and audit event emission
        try:
            service = GovernanceService(tenant_id=str(tenant.id), user_id=str(request.user.id))
            policy = service.create_retention_policy(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id),
                name=serializer.validated_data["name"],
                policy_type=serializer.validated_data["policy_type"],
                asset_id=str(asset_id) if asset_id else None,
                dataset_id=str(dataset_id) if dataset_id else None,
                file_id=str(file_id) if file_id else None,
                description=serializer.validated_data.get("description"),
                retention_period_days=serializer.validated_data.get("retention_period_days"),
                event_trigger=serializer.validated_data.get("event_trigger"),
                action=serializer.validated_data.get("action", "SOFT_DELETE"),
                grace_period_days=serializer.validated_data.get("grace_period_days", 30),
                legal_hold=serializer.validated_data.get("legal_hold", False),
                legal_hold_reason=serializer.validated_data.get("legal_hold_reason"),
                legal_hold_expires_at=serializer.validated_data.get("legal_hold_expires_at"),
                enabled=serializer.validated_data.get("enabled", True),
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        except NotFoundError as e:
            return handle_service_exception(e)

        # Return serialized response
        response_serializer = RetentionPolicySerializer(policy)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update retention policy via service layer (Phase 12.1.2).

        Service handles validation, persistence, and audit event emission.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Validate request data via serializer (request validation only)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Update retention policy via service layer (Phase 12.1.2)
        # Service handles validation, persistence, and audit event emission
        try:
            service = GovernanceService(
                tenant_id=str(instance.tenant.id), user_id=str(request.user.id)
            )
            policy = service.update_retention_policy(
                policy_id=str(instance.id),
                tenant_id=str(instance.tenant.id),
                user_id=str(request.user.id),
                **serializer.validated_data,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        except NotFoundError as e:
            return handle_service_exception(e)

        # Return serialized response
        response_serializer = RetentionPolicySerializer(policy)
        return Response(response_serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete retention policy"""
        instance = self.get_object()

        # Log audit event before deletion
        create_audit_event(
            resource_type="RETENTION_POLICY",
            action="RETENTION_POLICY_DELETED",
            actor_user=request.user,
            tenant=instance.tenant,
            resource_id=str(instance.id),
            details={"name": instance.name},
            request=request,
        )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
