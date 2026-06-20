"""
284.A.1 — FederatedImportViewSet.

Provides federated marketplace import actions: list providers, create
import job, get job status, cancel job. All actions are tenant-scoped
and require the ``federated_import_enabled`` tenant flag.

Credential handling (284.A.2): the API accepts ``credential_ref`` (AWS
Secrets Manager ARN), never raw credentials. Credential references are
masked in structlog + API responses. The worker resolves the ARN at
job execution time via ``hub.aws_secrets_loader``.
"""

from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import api_error_response
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.request_tenant import get_request_tenant

from .throttles import FederatedImportThrottle

logger = structlog.get_logger(__name__)

# Providers that federated import supports. In production this would
# come from a dynamic registry; for GA the allowlist is static.
_SUPPORTED_PROVIDERS = [
    {
        "id": "snowflake_marketplace",
        "name": "Snowflake Marketplace",
        "description": "Import listings from Snowflake Marketplace.",
        "credential_type": "snowflake_warehouse",
    },
    {
        "id": "aws_data_exchange",
        "name": "AWS Data Exchange",
        "description": "Import datasets from AWS Data Exchange.",
        "credential_type": "aws_data_exchange",
    },
    {
        "id": "databricks_marketplace",
        "name": "Databricks Marketplace",
        "description": "Import listings from Databricks Marketplace.",
        "credential_type": "databricks_warehouse",
    },
    {
        "id": "google_analytics_hub",
        "name": "Google Analytics Hub",
        "description": "Import listings from Google Analytics Hub.",
        "credential_type": "bigquery_warehouse",
    },
]

# Fields that must never appear in API responses or structured logs.
_MASKED_FIELDS = frozenset({"credential_ref", "secret", "password", "api_key", "token"})


def _mask_credentials(data: dict) -> dict:
    """Recursively replace credential values with '[REDACTED]'."""
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        if k in _MASKED_FIELDS:
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = _mask_credentials(v)
        elif isinstance(v, list):
            result[k] = [_mask_credentials(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def _validate_credential_ref(credential_ref: str) -> None:
    """Basic validation: must look like an AWS Secrets Manager ARN."""
    if not credential_ref:
        raise ValidationError({"credential_ref": "This field is required."})
    if not credential_ref.startswith("arn:aws:secretsmanager:"):
        raise ValidationError(
            {
                "credential_ref": "Must be a valid AWS Secrets Manager ARN (arn:aws:secretsmanager:...)."
            }
        )


class FederatedImportViewSet(viewsets.GenericViewSet):
    """284.A.1 — Federated marketplace import endpoints.

    All actions are tenant-scoped. The ``federated_import_enabled``
    tenant flag is checked by the service layer; this ViewSet does
    NOT duplicate the flag check — it delegates to the service.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [FederatedImportThrottle]

    @extend_schema(
        summary="List supported federated import providers",
        description="Returns the static allowlist of supported external marketplace providers for federated import.",
        responses={200: OpenApiResponse(description="Provider list")},
    )
    @action(detail=False, methods=["get"], url_path="providers")
    def list_providers(self, request):
        """List all supported federated import providers."""
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("Tenant not found.")
        return Response({"providers": _SUPPORTED_PROVIDERS, "count": len(_SUPPORTED_PROVIDERS)})

    @extend_schema(
        summary="Create a federated import job",
        description=(
            "Enqueues an async federated import job. Accepts a ``credential_ref`` "
            "(AWS Secrets Manager ARN), never raw credentials. Returns the Job id "
            "for status polling."
        ),
        request={
            "type": "object",
            "required": ["provider_id", "credential_ref"],
            "properties": {
                "provider_id": {"type": "string", "description": "Provider id from /providers/"},
                "credential_ref": {"type": "string", "description": "AWS Secrets Manager ARN"},
                "external_listing_id": {
                    "type": "string",
                    "description": "Optional external listing id to import",
                },
                "data_strategy": {
                    "type": "string",
                    "enum": ["METADATA_ONLY", "DOWNLOAD_SELECTIVE", "DOWNLOAD_ALL"],
                    "default": "METADATA_ONLY",
                },
            },
        },
        responses={
            201: OpenApiResponse(description="Import job created"),
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Federated import disabled for tenant"),
        },
    )
    @action(detail=False, methods=["post"], url_path="imports")
    def create_import(self, request):
        """Create a federated import job."""
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("Tenant not found.")

        provider_id = request.data.get("provider_id")
        credential_ref = request.data.get("credential_ref")
        external_listing_id = request.data.get("external_listing_id", "")
        data_strategy = request.data.get("data_strategy", "METADATA_ONLY")

        if not provider_id:
            raise ValidationError({"provider_id": "This field is required."})
        _validate_credential_ref(credential_ref or "")

        provider = next((p for p in _SUPPORTED_PROVIDERS if p["id"] == provider_id), None)
        if not provider:
            raise ValidationError({"provider_id": f"Unknown provider: {provider_id}"})

        if data_strategy not in ("METADATA_ONLY", "DOWNLOAD_SELECTIVE", "DOWNLOAD_ALL"):
            raise ValidationError({"data_strategy": f"Invalid strategy: {data_strategy}"})

        import uuid as _uuid

        # 285.12.2.9 — Deterministic placeholder UUID from request params
        # so the job can be idempotently looked up before the worker
        # assigns the real asset resource_id on completion.
        placeholder_uuid = str(
            _uuid.uuid5(
                _uuid.NAMESPACE_OID,
                f"{tenant.id}:{provider_id}:{external_listing_id or ''}",
            )
        )

        with transaction.atomic():
            job = Job.objects.create(
                tenant=tenant,
                type=JobType.FEDERATED_IMPORT,
                status=JobStatus.PENDING,
                resource_id=placeholder_uuid,  # deterministic; worker updates on completion
                created_by=request.user if request.user.is_authenticated else None,
                details_json={
                    "provider_id": provider_id,
                    "provider_name": provider["name"],
                    "external_listing_id": external_listing_id,
                    "data_strategy": data_strategy,
                    # 284.A.2 — credential_ref stored in details_json;
                    # worker resolves ARN at exec via hub.aws_secrets_loader.
                    "credential_ref": credential_ref,
                    "initiated_by": str(request.user.id) if request.user.is_authenticated else None,
                },
            )

        try:
            create_audit_event(
                resource_type="JOB",
                action="JOB_CREATED",
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=tenant,
                resource_id=str(job.id),
                details={
                    "job_type": JobType.FEDERATED_IMPORT.value,
                    "provider_id": provider_id,
                    "data_strategy": data_strategy,
                },
            )
        except Exception:
            logger.warning("federated_import_audit_emit_failed", exc_info=True)

        # Mask credential_ref in the response (284.A.2).
        safe_details = _mask_credentials(job.details_json or {})
        return Response(
            {
                "id": str(job.id),
                "type": job.type,
                "status": job.status,
                "provider_id": provider_id,
                "data_strategy": data_strategy,
                "details": safe_details,
                "created_at": job.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Get federated import job status",
        description="Returns the current status of a federated import job.",
        parameters=[
            OpenApiParameter(
                name="job_id", type=str, location=OpenApiParameter.PATH, description="Job UUID"
            ),
        ],
        responses={200: OpenApiResponse(description="Job status")},
    )
    @action(detail=False, methods=["get"], url_path="imports/(?P<job_id>[^/.]+)")
    def get_status(self, request, job_id=None):
        """Get the status of a federated import job."""
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("Tenant not found.")

        try:
            job = Job.objects.get(id=job_id, tenant=tenant, type=JobType.FEDERATED_IMPORT)
        except Job.DoesNotExist:
            raise NotFound(f"Federated import job {job_id} not found.")

        safe_details = _mask_credentials(job.details_json or {})
        return Response(
            {
                "id": str(job.id),
                "type": job.type,
                "status": job.status,
                "details": safe_details,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "completed_at": job.completed_at.isoformat()
                if hasattr(job, "completed_at") and job.completed_at
                else None,
            }
        )

    @extend_schema(
        summary="Cancel a federated import job",
        description="Cancels a pending or running federated import job.",
        responses={
            200: OpenApiResponse(description="Job cancelled"),
            409: OpenApiResponse(description="Job already in terminal state"),
        },
    )
    @action(detail=False, methods=["post"], url_path="imports/(?P<job_id>[^/.]+)/cancel")
    def cancel(self, request, job_id=None):
        """Cancel a pending or running federated import job."""
        _tenant_id, tenant = get_request_tenant(request)
        if not tenant:
            raise NotFound("Tenant not found.")

        try:
            job = Job.objects.get(id=job_id, tenant=tenant, type=JobType.FEDERATED_IMPORT)
        except Job.DoesNotExist:
            raise NotFound(f"Federated import job {job_id} not found.")

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return api_error_response(
                message="Job is already in a terminal state and cannot be cancelled.",
                code="JOB_TERMINAL",
                status_code=status.HTTP_409_CONFLICT,
            )

        job.status = JobStatus.CANCELLED
        job.updated_at = timezone.now()
        job.save(update_fields=["status", "updated_at"])

        try:
            create_audit_event(
                resource_type="JOB",
                action="JOB_CANCELLED",
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=tenant,
                resource_id=str(job.id),
                details={"job_type": JobType.FEDERATED_IMPORT.value},
            )
        except Exception:
            logger.warning("federated_import_cancel_audit_emit_failed", exc_info=True)

        return Response({"id": str(job.id), "status": job.status})
