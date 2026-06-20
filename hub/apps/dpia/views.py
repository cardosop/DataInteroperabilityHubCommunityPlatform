"""REST API for DPIA register — Phase 232.5."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.assets.models import Asset
from hub.apps.audit import event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.dpia.models import Dpia, DpiaStatus
from hub.apps.dpia.permissions import IsDpiaParticipant, IsDpiaReviewer
from hub.apps.dpia.serializers import (
    DpiaConsultSerializer,
    DpiaReviewSerializer,
    DpiaSerializer,
)

# 283.3.5.4 — DPIA views must carry throttle classes per CI contract
from hub.apps.dpia.throttles import DpiaTenantRateThrottle
from hub.apps.dpia.triggers import asset_requires_dpia
from hub.apps.dpia.workflow import (
    complete_consultation,
    create_follow_on_version,
    diff_wizard_payloads,
    review_dpia,
    submit_dpia,
)
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import get_request_tenant_id


class DpiaViewSet(viewsets.ModelViewSet):
    """CRUD + workflow actions for DPIA rows."""

    permission_classes = (IsAuthenticated, IsDpiaParticipant)
    throttle_classes = [DpiaTenantRateThrottle]
    serializer_class = DpiaSerializer
    http_method_names = ("get", "post", "put", "patch", "delete", "head", "options")
    lookup_field = "pk"

    def _tenant(self):
        tid = get_request_tenant_id(self.request)
        if not tid:
            return None
        return get_object_or_404(Tenant, pk=tid)

    def get_queryset(self):
        tid = get_request_tenant_id(self.request)
        if not tid:
            return Dpia.objects.none()
        qs = Dpia.objects.filter(tenant_id=tid).select_related("asset", "previous_version")
        st = self.request.query_params.get("status")
        if st:
            qs = qs.filter(status=st.upper())
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        tenant = self._tenant()
        if tenant is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "Tenant context required."})
        if not tenant.compliance_dpia_enabled:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("DPIA is disabled for this tenant.")
        dpia = serializer.save(tenant=tenant, created_by=self.request.user, status=DpiaStatus.DRAFT)

        # 285.12.8.6 8F — Pre-populate wizard_payload from asset compliance context
        if dpia.asset_id:
            self._prepopulate_from_asset(dpia)
        create_audit_event(
            resource_type="DPIA",
            action=event_types.DPIA_CREATED,
            actor_user=self.request.user,
            tenant=tenant,
            resource_id=dpia.id,
            details={
                "title": dpia.title,
                "asset_id": str(dpia.asset_id) if dpia.asset_id else None,
            },
        )

    def perform_update(self, serializer):
        if serializer.instance.status != DpiaStatus.DRAFT:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Only DRAFT DPIAs can be edited.")
        serializer.save()

    @staticmethod
    def _prepopulate_from_asset(dpia: Dpia) -> None:
        """285.12.8.6 8F — Pre-populate wizard_payload from asset context.

        When ``asset_id`` is provided at creation, auto-fills:
        - data_subject_categories from asset metadata
        - processing_purpose from asset description
        - jurisdictions from asset region + compliance regimes
        - risk_level from latest compliance scan
        """
        payload = dpia.wizard_payload or {}
        if payload.get("_prepopulated"):
            return  # already populated

        asset = dpia.asset
        categories = []
        purpose = ""
        jurisdictions = []
        risk_level = "UNKNOWN"

        # Extract from asset metadata
        if asset:
            if asset.domain:
                categories.append(asset.domain)
            if asset.description:
                purpose = asset.description[:500]
            if hasattr(asset, "region") and asset.region:
                jurisdictions.append(asset.region)

        # Extract from tenant compliance regimes
        try:
            from hub.apps.compliance.services import (
                get_tenant_compliance_regimes,
            )

            regimes = get_tenant_compliance_regimes(str(dpia.tenant_id))
            for r in regimes:
                if r not in jurisdictions:
                    jurisdictions.append(r)
        except Exception:
            pass

        # Extract risk_level from latest compliance run
        try:
            from hub.apps.compliance.models import ComplianceRun

            latest = (
                ComplianceRun.objects.filter(tenant_id=dpia.tenant_id, asset_id=dpia.asset_id)
                .exclude(risk_level__isnull=True)
                .order_by("-completed_at")
                .only("risk_level")
                .first()
            )
            if latest and latest.risk_level:
                risk_level = latest.risk_level
        except Exception:
            pass

        payload.update(
            {
                "data_subject_categories": categories,
                "processing_purpose": purpose,
                "jurisdictions": jurisdictions,
                "risk_level": risk_level,
                "_prepopulated": True,
            }
        )
        dpia.wizard_payload = payload
        dpia.save(update_fields=["wizard_payload"])

    def perform_destroy(self, instance: Dpia):
        if instance.status != DpiaStatus.DRAFT:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Only DRAFT DPIAs can be deleted.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        dpia = self.get_object()
        submit_dpia(dpia=dpia, actor=request.user)
        dpia.refresh_from_db()
        return Response(DpiaSerializer(dpia).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="review",
        permission_classes=(IsAuthenticated, IsDpiaReviewer),
    )
    def review(self, request, pk=None):
        dpia = self.get_object()
        ser = DpiaReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        review_dpia(
            dpia=dpia,
            actor=request.user,
            outcome=ser.validated_data["outcome"],
            risk_residual=ser.validated_data.get("risk_residual") or "",
            dpo_summary=ser.validated_data.get("dpo_summary") or "",
        )
        dpia.refresh_from_db()
        return Response(DpiaSerializer(dpia).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="consultation/complete",
        permission_classes=(IsAuthenticated, IsDpiaReviewer),
    )
    def consultation_complete(self, request, pk=None):
        dpia = self.get_object()
        ser = DpiaConsultSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        complete_consultation(dpia=dpia, actor=request.user, approve=ser.validated_data["approve"])
        dpia.refresh_from_db()
        return Response(DpiaSerializer(dpia).data)

    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        dpia = self.get_object()
        title = request.data.get("title")
        clone = create_follow_on_version(dpia=dpia, actor=request.user, title=title)
        return Response(DpiaSerializer(clone).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="diff")
    def diff(self, request, pk=None):
        dpia = self.get_object()
        prev = dpia.previous_version
        if prev is None:
            return Response({"detail": "No previous_version to compare.", "diff": None})
        body = diff_wizard_payloads(dpia.wizard_payload or {}, prev.wizard_payload or {})
        body["previous_id"] = str(prev.id)
        body["current_id"] = str(dpia.id)
        return Response(body)

    @action(
        detail=False,
        methods=["get"],
        url_path="asset-status",
        permission_classes=(IsAuthenticated,),
    )
    def asset_status(self, request):
        # Override the ViewSet's ``IsDpiaParticipant`` gate for this single
        # action: ``asset-status`` is read-only and serves the
        # AssetDetailPage DPIA badge ("Do I need a DPIA?"). It returns
        # info already implied by the asset the caller can read — there
        # is no privileged data exposed beyond what asset-list reveals.
        # Tenant isolation is preserved by the explicit
        # ``get_object_or_404(Asset, pk=aid, tenant=tenant)`` below.
        # Without this loosening, the SPA fires asset-status from
        # ``AssetDetailPage.tsx:156`` on every asset render and any user
        # outside the {TENANT_ADMIN, DPO, LEGAL_ADMIN} set 403s — 93
        # such 403s were logged per E2E batch on default-role users.
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        aid = request.query_params.get("asset_id")
        if not aid:
            return Response({"detail": "asset_id query parameter required"}, status=400)
        asset = get_object_or_404(Asset, pk=aid, tenant=tenant)
        enabled = tenant.compliance_dpia_enabled
        required = enabled and asset_requires_dpia(asset)
        open_row = (
            Dpia.objects.filter(
                tenant=tenant,
                asset=asset,
                status__in=(
                    DpiaStatus.DRAFT,
                    DpiaStatus.IN_REVIEW,
                    DpiaStatus.REQUIRES_CONSULTATION,
                ),
            )
            .order_by("-version")
            .first()
        )
        approved = Dpia.objects.filter(
            tenant=tenant, asset=asset, status=DpiaStatus.APPROVED
        ).exists()
        badge_message = ""
        if required and not approved and not open_row:
            badge_message = "DPIA required — processing profile suggests high-risk processing."
        elif open_row:
            badge_message = f"DPIA in progress ({open_row.status})."
        data = {
            "compliance_dpia_enabled": enabled,
            "dpia_required": required,
            "open_dpia_id": open_row.id if open_row else None,
            "badge_message": badge_message,
        }
        return Response(data)
