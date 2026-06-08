"""
Phase 231.4 — Anonymous signed GET for scrubbed compliance run summary.

Opened via ``report_presigned_url`` embedded in the ``compliance.completed`` webhook.
"""

from __future__ import annotations
from typing import ClassVar, Sequence, Type

from django.core.signing import BadSignature
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from hub.apps.compliance.models import ComplianceRun
from hub.apps.compliance.webhook_emission import (
    build_compliance_completed_webhook_data,
    build_report_presigned_url_for_run,
    decode_report_presigned_token,
)
from hub.apps.tenants.request_tenant import tenant_context


class ComplianceWebhookReportSummaryThrottle(ScopedRateThrottle):
    scope = "compliance_webhook_report"


class ComplianceWebhookReportSummaryView(APIView):
    """
    Redeem ``?token=`` from ``report_presigned_url`` (TTL 7 days).

    Response mirrors the webhook ``data`` envelope (whitelist fields only).
    """

    authentication_classes: ClassVar[Sequence[Type[BaseAuthentication]]] = ()
    permission_classes: ClassVar[Sequence[type]] = (AllowAny,)
    throttle_classes: ClassVar[Sequence[type]] = (
        ComplianceWebhookReportSummaryThrottle,
    )

    def get(self, request, *_args, **_kwargs):
        raw = request.query_params.get("token") or ""
        if not raw:
            return Response({"detail": "token required"}, status=400)
        try:
            run_id, tenant_id = decode_report_presigned_token(raw)
        except BadSignature:
            return Response({"detail": "invalid or expired token"}, status=403)

        with tenant_context(tenant_id):
            run = (
                ComplianceRun.objects.filter(pk=run_id, tenant_id=tenant_id)
                .only(
                    "id",
                    "tenant_id",
                    "status",
                    "risk_level",
                    "asset_id",
                    "completed_at",
                )
                .first()
            )
        if not run:
            return Response({"detail": "not found"}, status=404)

        report_url = build_report_presigned_url_for_run(run)
        payload = build_compliance_completed_webhook_data(
            run,
            report_presigned_url=report_url,
        )
        return Response(payload)
