"""HTTP API for breach incidents, notifications, templates (Phase 232.3)."""

from __future__ import annotations
from typing import Any, cast

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes

# 283.3.4.4 — Breach views must carry throttle classes per CI contract
from hub.apps.breach.throttles import BreachTenantRateThrottle
from rest_framework.request import Request
from rest_framework.response import Response

from hub.apps.breach.dashboard import breach_dashboard_summary
from hub.apps.breach.default_templates import PLATFORM_BREACH_TEMPLATES
from hub.apps.breach.models import BreachIncident, BreachNotification, BreachTenantTemplateOverride
from hub.apps.breach.permissions import IsBreachResponder
from hub.apps.breach.serializers import (
    BreachIncidentCreateSerializer,
    BreachIncidentSerializer,
    BreachIncidentStatusSerializer,
    BreachMarkSentSerializer,
    BreachNotificationSerializer,
    BreachTenantTemplateOverrideSerializer,
    BreachTenantTemplateWriteSerializer,
)
from hub.apps.breach.template_service import merged_template_for_tenant
from hub.apps.breach.workflow import (
    create_breach_incident,
    mark_notification_sent,
    transition_incident_status,
)
from hub.apps.consent.permissions import IsTenantScoped
from hub.apps.users.models import User


def _tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class BreachIncidentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTenantScoped, IsBreachResponder]
    throttle_classes = [BreachTenantRateThrottle]
    lookup_field = "id"
    http_method_names = ["get", "post", "head", "options", "patch"]

    def get_queryset(self):
        t = _tenant(self.request)
        if not t:
            return BreachIncident.objects.none()
        return BreachIncident.objects.filter(tenant=t).prefetch_related("notifications")

    def get_serializer_class(self):
        if self.action == "create":
            return BreachIncidentCreateSerializer
        return BreachIncidentSerializer

    def create(self, request, *args, **kwargs):
        tenant = _tenant(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        if not tenant.compliance_breach_enabled:
            return Response(
                {"error": "Breach workflow disabled for this tenant"},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = BreachIncidentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = cast(dict[str, Any], ser.validated_data)
        user = request.user
        assert user.is_authenticated
        try:
            inc = create_breach_incident(
                tenant=tenant,
                actor=cast(User, user),
                title=str(vd["title"]),
                summary=str(vd.get("summary") or ""),
                regimes=list(vd["regimes"]),
                discovered_at=vd["discovered_at"],
            )
        except DjangoValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BreachIncidentSerializer(inc).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"], url_path="status")
    def transition_status(self, request, id=None):
        inc = self.get_object()
        ser = BreachIncidentStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = cast(dict[str, Any], ser.validated_data)
        user = request.user
        assert user.is_authenticated
        try:
            transition_incident_status(
                inc,
                str(vd["status"]),
                actor=cast(User, user),
                notes=str(vd.get("notes") or ""),
            )
        except DjangoValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        inc.refresh_from_db()
        return Response(BreachIncidentSerializer(inc).data)


class BreachNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BreachNotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantScoped, IsBreachResponder]
    throttle_classes = [BreachTenantRateThrottle]
    lookup_field = "id"

    def get_queryset(self):
        tenant = _tenant(self.request)
        if not tenant:
            return BreachNotification.objects.none()
        qs = BreachNotification.objects.filter(tenant=tenant).select_related("incident")
        req = cast(Request, self.request)
        inc = req.query_params.get("incident")
        if inc:
            qs = qs.filter(incident_id=inc)
        return qs.order_by("regime", "supervisory_authority_id")

    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, id=None):
        tenant = _tenant(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        row = self.get_object()
        ser = BreachMarkSentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = cast(dict[str, Any], ser.validated_data)
        user = request.user
        assert user.is_authenticated
        try:
            mark_notification_sent(
                row,
                actor=cast(User, user),
                outbound_reference=str(vd["outbound_reference"]),
            )
        except DjangoValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        row.refresh_from_db()
        return Response(BreachNotificationSerializer(row).data)


class BreachTenantTemplateOverrideViewSet(
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BreachTenantTemplateOverrideSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantScoped, IsBreachResponder]
    throttle_classes = [BreachTenantRateThrottle]
    lookup_field = "id"

    def get_queryset(self):
        tenant = _tenant(self.request)
        if not tenant:
            return BreachTenantTemplateOverride.objects.none()
        return BreachTenantTemplateOverride.objects.filter(tenant=tenant).order_by("regime")

    @action(detail=False, methods=["post"], url_path="upsert")
    def upsert(self, request):
        tenant = _tenant(request)
        if not tenant:
            return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
        ser = BreachTenantTemplateWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = cast(dict[str, Any], ser.validated_data)

        regime = str(vd["regime"]).upper().strip()
        user = request.user
        assert user.is_authenticated
        existing = BreachTenantTemplateOverride.objects.filter(tenant=tenant, regime=regime).first()
        if existing:
            existing.subject_template = str(vd.get("subject_template") or "")
            existing.body_template = str(vd.get("body_template") or "")
            existing.template_version = existing.template_version + 1
            existing.updated_by = cast(User, user)
            existing.save(
                update_fields=[
                    "subject_template",
                    "body_template",
                    "template_version",
                    "updated_by",
                    "updated_at",
                ]
            )
            return Response(BreachTenantTemplateOverrideSerializer(existing).data)
        row = BreachTenantTemplateOverride.objects.create(
            tenant=tenant,
            regime=regime,
            subject_template=str(vd.get("subject_template") or ""),
            body_template=str(vd.get("body_template") or ""),
            template_version=1,
            updated_by=cast(User, user),
        )
        return Response(
            BreachTenantTemplateOverrideSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsTenantScoped, IsBreachResponder])
def breach_dashboard(request):
    tenant = _tenant(request)
    if not tenant:
        return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(breach_dashboard_summary(tenant=tenant))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsTenantScoped, IsBreachResponder])
def breach_template_catalog(request):
    tenant = _tenant(request)
    if not tenant:
        return Response({"error": "Tenant required"}, status=status.HTTP_400_BAD_REQUEST)
    out = []
    for regime in sorted(PLATFORM_BREACH_TEMPLATES.keys()):
        ver, subj, body = merged_template_for_tenant(tenant_id=str(tenant.id), regime=regime)
        out.append(
            {
                "regime": regime,
                "template_version": ver,
                "subject_template": subj,
                "body_template": body,
            }
        )
    return Response({"templates": out})
