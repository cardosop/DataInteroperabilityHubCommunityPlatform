from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.ropa.cache import (
    current_cache_version,
    get_cached_preview,
    set_cached_preview,
)
from hub.apps.ropa.models import RopaGeneration, RopaGenerationStatus, RopaOutputFormat
from hub.apps.ropa.permissions import IsRopaHandler
from hub.apps.ropa.serializers import RopaGenerationSerializer
from hub.apps.ropa.services.generator import build_ropa_payload, estimate_json_bytes
from hub.apps.ropa.services.pipeline import (
    materialize_generation,
    ropa_large_export_bytes_threshold,
    ropa_storage_client,
)
from hub.apps.ropa.throttles import RopaUserThrottle
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import get_request_tenant_id


class RopaGenerationViewSet(viewsets.ReadOnlyModelViewSet):
    """CRUD + download endpoints for tenant RoPA artefacts (283.3.3)."""

    permission_classes = (IsAuthenticated, IsRopaHandler)
    throttle_classes = [RopaUserThrottle]  # 283.3.3.4 — G8 Rate gate
    serializer_class = RopaGenerationSerializer
    queryset = RopaGeneration.objects.none()
    lookup_field = "pk"

    def _tenant(self):
        tid = get_request_tenant_id(self.request)
        if not tid:
            return None
        return get_object_or_404(Tenant, pk=tid)

    def get_queryset(self):
        """Filter by active request tenant (``X-Tenant-Id`` / membership switch), not only ``user.tenant``."""
        tid = get_request_tenant_id(self.request)
        if not tid:
            return RopaGeneration.objects.none()
        return RopaGeneration.objects.filter(tenant_id=tid).order_by("-created_at")

    def _require_ropa_gate(self, tenant: Tenant) -> Response | None:
        if not tenant.compliance_ropa_enabled:
            return Response(
                {"detail": "RoPA is disabled for this tenant.", "code": "ROPA_DISABLED"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=False, methods=["get"], url_path="preview")
    def preview(self, request):
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        gate = self._require_ropa_gate(tenant)
        if gate is not None:
            return gate
        regulation = (request.query_params.get("regulation") or "GDPR").upper()
        tid = str(tenant.id)
        cv = current_cache_version(tid)
        cached = get_cached_preview(tid, regulation, cv)
        if cached is not None:
            return Response({**cached, "cache_hit": True})
        payload = build_ropa_payload(tenant_id=tid, regulation=regulation)
        body = {
            "regulation": regulation,
            "gaps": payload.get("gaps") or [],
            "summary": {
                "asset_count": (payload.get("meta") or {}).get("asset_count"),
                "gap_count": len(payload.get("gaps") or []),
            },
            "cache_version": cv,
        }
        set_cached_preview(tid, regulation, cv, body)
        return Response({**body, "cache_hit": False})

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        gate = self._require_ropa_gate(tenant)
        if gate is not None:
            return gate
        regulation = (request.query_params.get("regulation") or "GDPR").upper()
        fmt_raw = (request.query_params.get("format") or "json").lower()
        valid_formats = {c.value for c in RopaOutputFormat}
        if fmt_raw not in valid_formats:
            return Response({"detail": f"Unsupported format: {fmt_raw}"}, status=400)

        payload = build_ropa_payload(tenant_id=str(tenant.id), regulation=regulation)
        est = estimate_json_bytes(payload)
        gen = RopaGeneration.objects.create(
            tenant=tenant,
            regulation=regulation,
            output_format=fmt_raw,
            status=RopaGenerationStatus.PENDING,
            gaps_json=payload.get("gaps") or [],
            summary_json={
                "asset_count": (payload.get("meta") or {}).get("asset_count"),
            },
            created_by=request.user if request.user.is_authenticated else None,
            cache_generation=current_cache_version(str(tenant.id)),
        )

        threshold = ropa_large_export_bytes_threshold()
        async_path = est > threshold
        if async_path:
            job = create_job(
                tenant=tenant,
                user=request.user,
                job_type=JobType.ROPA_GENERATE,
                resource_type="ROPA_GENERATION",
                resource_id=str(gen.id),
                details_json={"ropa_generation_id": str(gen.id)},
            )
            gen.job = job
            gen.save(update_fields=["job"])
            return Response(
                {
                    "ropa_generation_id": str(gen.id),
                    "job_id": str(job.id),
                    "status": gen.status,
                    "async": True,
                    "estimated_source_bytes": est,
                    "threshold_bytes": threshold,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # materialize_generation() emits ROPA_GENERATED internally (pipeline.py:72).
        materialize_generation(generation=gen, actor_user=request.user)
        return Response(
            RopaGenerationSerializer(gen).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        gate = self._require_ropa_gate(tenant)
        if gate is not None:
            return gate
        gen = get_object_or_404(RopaGeneration, pk=pk, tenant=tenant)
        if gen.status != RopaGenerationStatus.COMPLETED or not gen.object_key:
            return Response(
                {"detail": "Artefact is not ready yet.", "status": gen.status},
                status=status.HTTP_409_CONFLICT,
            )
        fname = (gen.summary_json or {}).get("download_filename") or "ropa-download"
        client = ropa_storage_client()
        url = client.generate_presigned_download_url(
            key=gen.object_key,
            expires_in=3600,
            filename=fname,
        )
        return Response({"download_url": url, "expires_in": 3600})

    @action(detail=True, methods=["delete"], url_path="delete")
    def remove(self, request, pk=None):
        """Delete a RoPA generation (DPO / TENANT_ADMIN / LEGAL_ADMIN)."""
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        gate = self._require_ropa_gate(tenant)
        if gate is not None:
            return gate
        gen = get_object_or_404(RopaGeneration, pk=pk, tenant=tenant)
        gen_id = str(gen.id)
        gen.delete()
        create_audit_event(
            resource_type="ROPA_GENERATION",
            action=audit_event_types.ROPA_DELETED,
            actor_user=request.user if request.user.is_authenticated else None,
            tenant=tenant,
            resource_id=gen_id,
            details={"regulation": gen.regulation},
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["patch"], url_path="update")
    def update_metadata(self, request, pk=None):
        """Update generation metadata (notes/tags)."""
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant context required"}, status=400)
        gate = self._require_ropa_gate(tenant)
        if gate is not None:
            return gate
        gen = get_object_or_404(RopaGeneration, pk=pk, tenant=tenant)
        ser = RopaGenerationSerializer(gen, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
