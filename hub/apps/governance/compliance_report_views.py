"""
Compliance report REST surface under /governance/compliance-reports/.

The SDK (``GovernanceAPI.generate_compliance_report`` /
``get_compliance_report``) targets ``governance/compliance-reports/``;
this viewset provides that contract.  Report EXECUTION stays in the
compliance app (``/compliance/runs/`` + workflow orchestration) — rows
created here are PENDING and picked up by the same pipeline.
"""

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.serializers import ComplianceRunSerializer
from hub.apps.core.responses import api_error_response
from hub.apps.tenants.request_tenant import get_request_tenant_id

REGIME_CHOICES = {"GDPR", "HIPAA", "SOX", "LGPD", "CCPA"}


class ComplianceReportViewSet(viewsets.GenericViewSet):
    """
    ViewSet for governance compliance reports.

    POST /governance/compliance-reports/          — create runs per asset
    GET  /governance/compliance-reports/{id}/     — read one run's status
    """

    queryset = ComplianceRun.objects.all()
    serializer_class = ComplianceRunSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_platform_admin", False):
            return ComplianceRun.objects.select_related("tenant", "asset").all()
        tenant_id = get_request_tenant_id(self.request)
        if not tenant_id:
            return ComplianceRun.objects.none()
        return ComplianceRun.objects.select_related("tenant", "asset").filter(
            tenant_id=tenant_id
        )

    @transaction.atomic
    def create(self, request):
        """
        Create compliance runs for the requested regime + assets.

        Body: {"regime": "GDPR", "asset_ids": ["uuid", ...]}
        """
        from hub.apps.assets.models import Asset

        regime = (request.data or {}).get("regime")
        if not regime or str(regime).upper() not in REGIME_CHOICES:
            return api_error_response(
                message=f"Invalid regime: {regime}. Valid regimes: "
                f"{', '.join(sorted(REGIME_CHOICES))}",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_REGIME",
            )

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return api_error_response(
                message="Tenant context is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TENANT_REQUIRED",
            )

        asset_ids = (request.data or {}).get("asset_ids") or []
        created = []
        for asset_id in asset_ids:
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except (Asset.DoesNotExist, ValueError, TypeError):
                continue  # Skip unknown/foreign assets — the run set must stay tenant-scoped.
            run = ComplianceRun.objects.create(
                tenant_id=tenant_id,
                asset=asset,
                regulations=[str(regime).upper()],
                status=ComplianceRunStatus.PENDING,
            )
            created.append(run)

        if not created:
            # ComplianceRun requires at least one of asset/dataset/file —
            # a tenant-level run without a resource is invalid.
            return api_error_response(
                message="At least one asset_id must reference an asset in your tenant",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ASSET_REQUIRED",
            )

        first = created[0]
        return Response(
            {
                "id": str(first.id),
                "report_id": str(first.id),
                "regime": str(regime).upper(),
                "status": first.status,
                "asset_ids": [str(run.asset_id) for run in created if run.asset_id],
                "run_ids": [str(run.id) for run in created],
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        """Read one compliance run's status."""
        run = self.get_object()
        serializer = self.get_serializer(run)
        data = serializer.data
        data["report_id"] = str(run.id)
        return Response(data)
