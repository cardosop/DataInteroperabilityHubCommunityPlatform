"""
GDPR Views

API views for data portability and erasure requests.
"""

import logging

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.gdpr.models import DataExportJob, ErasureRequest
from hub.apps.gdpr.serializers import DataExportJobSerializer, ErasureRequestSerializer
from hub.apps.gdpr.services import (
    GDPR_EXPORT_FORMAT_VERSION,
    DataPortabilityService,
    ErasureService,
)
from hub.apps.tenants.request_tenant import get_request_tenant_id

logger = logging.getLogger(__name__)


class DataExportJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for data export jobs.

    Users can only see their own export jobs.
    """

    serializer_class = DataExportJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset by user"""
        return DataExportJob.objects.filter(user=self.request.user)

    @extend_schema(
        description=(
            "Request a GDPR Article 20 data export.\n\n"
            "Returns a job descriptor whose `download_url` resolves to a ZIP "
            "archive once `status == COMPLETED`. The archive layout is the "
            "public contract for downstream consumers:\n\n"
            "**Archive contents**\n"
            "- `user_data.json` — JSON envelope (UTF-8). Top-level keys: "
            "`format_version` (semver), `exported_at` (ISO-8601), "
            "`user_profile`, `audit_events`, `assets`, `datasets`, `contracts`. "
            "Additive changes (new keys, new resource types) are non-breaking; "
            "renamed/removed keys or changed semantics bump the **major** "
            f"component of `format_version` (currently `{GDPR_EXPORT_FORMAT_VERSION}`).\n"
            "- `README.txt` — human-readable cover sheet.\n\n"
            "Consumers should branch on the major version of `format_version` "
            "and tolerate unknown keys. Encryption-at-rest of the archive is "
            "out of scope for v1 — delivery is over HTTPS via short-lived "
            "presigned URL."
        ),
    )
    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="export-data")
    def export_data(self, request):
        """
        Request data export (GDPR Article 20 - Data Portability).

        POST /api/v1/users/me/export-data/

        Creates a data export job and returns job information.
        """
        service = DataPortabilityService(
            tenant_id=get_request_tenant_id(request), user_id=str(request.user.id)
        )

        try:
            job = service.create_export_job(user_id=str(request.user.id))

            return Response(
                {
                    "job_id": str(job.id),
                    "status": job.status,
                    "download_url": job.download_url,
                    "download_url_expires_at": (
                        job.download_url_expires_at.isoformat()
                        if job.download_url_expires_at
                        else None
                    ),
                    "created_at": job.created_at.isoformat(),
                },
                status=status.HTTP_201_CREATED,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)


class ErasureRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for erasure requests.

    Users can only see their own erasure requests.
    """

    serializer_class = ErasureRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter queryset by user"""
        return ErasureRequest.objects.filter(user=self.request.user)

    @transaction.atomic
    @action(detail=False, methods=["post"], url_path="request-erasure")
    def request_erasure(self, request):
        """
        Request data erasure (GDPR Article 17 - Right to be Forgotten).

        POST /api/v1/users/me/request-erasure/

        Creates an erasure request.
        """
        service = ErasureService(
            tenant_id=get_request_tenant_id(request), user_id=str(request.user.id)
        )

        try:
            erasure_request = service.create_request(user_id=str(request.user.id))

            # Execute erasure immediately (in production, this might be async)
            try:
                erasure_request = service.execute_erasure(request_id=str(erasure_request.id))
            except Exception as e:
                logger.warning(f"Failed to execute erasure immediately: {e}")
                # Request is created, execution can be retried

            return Response(
                {
                    "request_id": str(erasure_request.id),
                    "status": erasure_request.status,
                    "requested_at": erasure_request.requested_at.isoformat(),
                    "completed_at": (
                        erasure_request.completed_at.isoformat()
                        if erasure_request.completed_at
                        else None
                    ),
                },
                status=status.HTTP_201_CREATED,
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)
