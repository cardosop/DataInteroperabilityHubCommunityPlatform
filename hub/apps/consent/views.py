"""REST API for consent purposes, records, and DPO dashboard."""

from __future__ import annotations
import structlog
from typing import cast

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.consent.models import ConsentPurpose, ConsentRecord
from hub.apps.consent.permissions import IsTenantAdmin, IsTenantAdminOrDPO, IsTenantScoped
from hub.apps.consent.serializers import (
    ConsentPurposeSerializer,
    ConsentRecordCreateSerializer,
    ConsentRecordSerializer,
    ConsentRecordUpdateSerializer,
)
from hub.apps.consent.services import ConsentService, dashboard_summary
from hub.apps.consent.throttles import ConsentDashboardThrottle, ConsentUserThrottle
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import User, UserRole

logger = structlog.get_logger(__name__)


def _tenant_from_request(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


def _user_is_privileged_consent(request) -> bool:
    tenant = _tenant_from_request(request)
    if not tenant or not request.user.is_authenticated:
        return False
    if getattr(request.user, "is_platform_admin", False):
        return True
    return UserRole.objects.filter(
        user=request.user,
        tenant=tenant,
        role__name__in=["DPO", "TENANT_ADMIN"],
    ).exists()


class ConsentPurposeViewSet(viewsets.ModelViewSet):
    """
    CRUD consent purposes (TENANT_ADMIN).

    Routes: /api/v1/governance/consent-purposes/
    """

    serializer_class = ConsentPurposeSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantScoped]
    throttle_classes = [ConsentUserThrottle]  # 283.3.1.2 — G8 Rate gate
    lookup_field = "id"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated(), IsTenantScoped()]
        return [permissions.IsAuthenticated(), IsTenantScoped(), IsTenantAdmin()]

    def get_queryset(self):
        tenant = _tenant_from_request(self.request)
        if not tenant:
            return ConsentPurpose.objects.none()
        return ConsentPurpose.objects.filter(tenant=tenant).order_by("key")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        t = _tenant_from_request(self.request)
        if t:
            ctx["tenant"] = t
        return ctx

    def perform_update(self, serializer):
        # 277.B.086 — detect substance-changing fields and auto-bump version
        _SUBSTANCE_FIELDS = frozenset({"name", "description", "retention_days", "iab_purpose_id"})
        before = {f: getattr(serializer.instance, f) for f in ("name", "description", "is_active", "retention_days", "iab_purpose_id", "version")}
        substance_changed = any(
            serializer.validated_data.get(f, getattr(serializer.instance, f)) != getattr(serializer.instance, f)
            for f in _SUBSTANCE_FIELDS
            if f in serializer.validated_data or hasattr(serializer.instance, f)
        )
        if substance_changed:
            serializer.validated_data["version"] = serializer.instance.version + 1

        tenant = serializer.instance.tenant
        assert tenant is not None
        with tenant_context(str(tenant.id)):
            super().perform_update(serializer)
        after = serializer.instance
        user = self.request.user
        assert user.is_authenticated
        create_audit_event(
            resource_type="CONSENT_PURPOSE",
            action=audit_event_types.CONSENT_PURPOSE_CHANGED,
            actor_user=cast(User, user),
            tenant=tenant,
            resource_id=str(after.id),
            details={
                "purpose_key": after.key,
                "before": before,
                "after": {
                    "name": after.name,
                    "description": after.description,
                    "is_active": after.is_active,
                    "retention_days": after.retention_days,
                    "version": after.version,
                },
                "version_bumped": substance_changed,
            },
            request=self.request,
        )

    def perform_create(self, serializer):
        tenant = _tenant_from_request(self.request)
        assert tenant is not None
        user = self.request.user
        assert user.is_authenticated
        with tenant_context(str(tenant.id)):
            super().perform_create(serializer)
        inst = serializer.instance
        create_audit_event(
            resource_type="CONSENT_PURPOSE",
            action=audit_event_types.CONSENT_PURPOSE_CHANGED,
            actor_user=cast(User, user),
            tenant=inst.tenant,
            resource_id=str(inst.id),
            details={
                "operation": "created",
                "purpose_key": inst.key,
                "after": {
                    "name": inst.name,
                    "description": inst.description,
                    "is_active": inst.is_active,
                    "retention_days": inst.retention_days,
                },
            },
            request=self.request,
        )


class ConsentRecordViewSet(viewsets.ModelViewSet):
    """
    Consent records (subject self-service + DPO read).

    Routes: /api/v1/governance/consent-records/
    """

    permission_classes = [permissions.IsAuthenticated, IsTenantScoped]
    throttle_classes = [ConsentUserThrottle]  # 283.3.1.2 — G8 Rate gate
    lookup_field = "id"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        tenant = _tenant_from_request(self.request)
        if not tenant:
            return ConsentRecord.objects.none()
        qs = ConsentRecord.objects.filter(tenant=tenant).select_related("purpose", "user")
        if _user_is_privileged_consent(self.request):
            return qs.order_by("-updated_at")
        return qs.filter(user=self.request.user).order_by("-updated_at")

    def get_serializer_class(self):
        if self.action == "create":
            return ConsentRecordCreateSerializer
        if self.action == "partial_update":
            return ConsentRecordUpdateSerializer
        return ConsentRecordSerializer

    def create(self, request, *args, **kwargs):
        tenant = _tenant_from_request(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        ser = ConsentRecordCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = cast(dict[str, object], ser.validated_data)
        purpose = ConsentPurpose.objects.filter(
            id=data["purpose_id"], tenant=tenant
        ).first()
        if not purpose:
            return Response({"error": "Purpose not found"}, status=status.HTTP_404_NOT_FOUND)
        if not purpose.is_active:
            return Response({"error": "Purpose is not active"}, status=status.HTTP_400_BAD_REQUEST)
        payload_raw = data.get("payload")
        payload: dict[str, object] = (
            dict(payload_raw) if isinstance(payload_raw, dict) else {}
        )
        user = request.user
        assert user.is_authenticated
        try:
            record = ConsentService().grant(
                tenant=tenant,
                user=cast(User, user),
                purpose=purpose,
                payload=payload,
                actor_user=cast(User, user),
                request=request,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        return Response(ConsentRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """Re-grant / refresh proof with a new payload (same purpose, same subject)."""
        tenant = _tenant_from_request(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        record = self.get_object()
        user = request.user
        assert user.is_authenticated
        if str(record.user_id) != str(user.id) and not _user_is_privileged_consent(request):
            return Response(
                {"error": "Cannot update another subject's consent without privileged role"},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = ConsentRecordUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = cast(dict[str, object], ser.validated_data)
        payload_raw = data.get("payload")
        payload: dict[str, object] = (
            dict(payload_raw) if isinstance(payload_raw, dict) else {}
        )
        try:
            updated = ConsentService().grant(
                tenant=tenant,
                user=record.user,
                purpose=record.purpose,
                payload=payload,
                actor_user=cast(User, user),
                request=request,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        return Response(ConsentRecordSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, id=None):
        tenant = _tenant_from_request(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        record = self.get_object()
        user = request.user
        assert user.is_authenticated
        try:
            ConsentService().revoke(
                tenant=tenant,
                record=record,
                actor_user=cast(User, user),
                request=request,
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        record.refresh_from_db()
        return Response(ConsentRecordSerializer(record).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsTenantScoped, IsTenantAdminOrDPO])
@throttle_classes([ConsentDashboardThrottle])
def consent_dashboard(request):
    tenant = _tenant_from_request(request)
    if not tenant:
        return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(dashboard_summary(tenant=tenant))
