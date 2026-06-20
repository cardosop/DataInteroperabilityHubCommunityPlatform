"""REST API for processor agreement tracker (Phase 232.6)."""

from __future__ import annotations

from typing import cast

from rest_framework import permissions, viewsets

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.consent.permissions import IsTenantScoped
from hub.apps.processor_agreements.models import (
    AssetProcessorMembership,
    Processor,
    ProcessorAgreement,
)
from hub.apps.processor_agreements.permissions import IsTenantAdminProcessorAgreements
from hub.apps.processor_agreements.serializers import (
    AssetProcessorLinkSerializer,
    ProcessorAgreementSerializer,
    ProcessorSerializer,
)
from hub.apps.processor_agreements.services import notify_subprocessor_change
from hub.apps.processor_agreements.throttles import ProcessorAgreementUserThrottle
from hub.apps.users.models import User


def _tenant(request):
    return getattr(request, "tenant", None) or getattr(request.user, "tenant", None)


class ProcessorViewSet(viewsets.ModelViewSet):
    permission_classes = [
        permissions.IsAuthenticated,
        IsTenantScoped,
        IsTenantAdminProcessorAgreements,
    ]
    throttle_classes = [ProcessorAgreementUserThrottle]  # 283.3.6.4
    serializer_class = ProcessorSerializer
    lookup_field = "id"

    def get_queryset(self):
        t = _tenant(self.request)
        if not t:
            return Processor.objects.none()
        return Processor.objects.filter(tenant=t).order_by("name")

    def perform_create(self, serializer):
        tenant = _tenant(self.request)
        proc = serializer.save(tenant=tenant)
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR",
            action=audit_event_types.PROCESSOR_REGISTERED,
            actor_user=user,
            tenant=tenant,
            resource_id=str(proc.id),
            details={"name": proc.name},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR",
            action=audit_event_types.PROCESSOR_UPDATED,
            actor_user=user,
            tenant=_tenant(self.request),
            resource_id=str(instance.id),
            details={"name": instance.name},
        )

    def perform_destroy(self, instance):
        tid = str(instance.id)
        t = instance.tenant
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR",
            action=audit_event_types.PROCESSOR_REMOVED,
            actor_user=user,
            tenant=t,
            resource_id=tid,
            details={"name": instance.name},
        )
        instance.delete()


class ProcessorAgreementViewSet(viewsets.ModelViewSet):
    permission_classes = [
        permissions.IsAuthenticated,
        IsTenantScoped,
        IsTenantAdminProcessorAgreements,
    ]
    throttle_classes = [ProcessorAgreementUserThrottle]  # 283.3.6.4
    serializer_class = ProcessorAgreementSerializer
    lookup_field = "id"

    def get_queryset(self):
        t = _tenant(self.request)
        if not t:
            return ProcessorAgreement.objects.none()
        return ProcessorAgreement.objects.filter(tenant=t).select_related("processor")

    def perform_create(self, serializer):
        serializer.save()
        obj = serializer.instance
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR_AGREEMENT",
            action=audit_event_types.PROCESSOR_AGREEMENT_CREATED,
            actor_user=user,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            details={
                "processor_id": str(obj.processor_id),
                "agreement_type": obj.agreement_type,
            },
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        prev_sub = list(instance.sub_processors_declared or [])
        serializer.save()
        obj = serializer.instance
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR_AGREEMENT",
            action=audit_event_types.PROCESSOR_AGREEMENT_UPDATED,
            actor_user=user,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            details={"processor_id": str(obj.processor_id)},
        )
        notify_subprocessor_change(
            agreement=obj,
            previous=prev_sub,
            actor=user,
        )

    def perform_destroy(self, instance):
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="PROCESSOR_AGREEMENT",
            action=audit_event_types.PROCESSOR_AGREEMENT_DELETED,
            actor_user=user,
            tenant=instance.tenant,
            resource_id=str(instance.id),
            details={
                "processor_id": str(instance.processor_id),
                "agreement_type": instance.agreement_type,
            },
        )
        instance.delete()


class AssetProcessorLinkViewSet(viewsets.ModelViewSet):
    permission_classes = [
        permissions.IsAuthenticated,
        IsTenantScoped,
        IsTenantAdminProcessorAgreements,
    ]
    throttle_classes = [ProcessorAgreementUserThrottle]  # 283.3.6.4
    serializer_class = AssetProcessorLinkSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    lookup_field = "id"

    def get_queryset(self):
        t = _tenant(self.request)
        if not t:
            return AssetProcessorMembership.objects.none()
        return AssetProcessorMembership.objects.filter(tenant=t).select_related(
            "asset", "processor"
        )

    def perform_create(self, serializer):
        serializer.save()
        user = cast("User", self.request.user)
        create_audit_event(
            resource_type="ASSET",
            action=audit_event_types.PROCESSOR_AGREEMENT_UPDATED,
            actor_user=user,
            tenant=_tenant(self.request),
            resource_id=str(serializer.instance.asset_id),
            details={
                "event": "asset_processor_linked",
                "processor_id": str(serializer.instance.processor_id),
                "link_id": str(serializer.instance.id),
            },
        )
