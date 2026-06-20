"""
285.6.2 / 285.6.5.1 — Internal Worker API for dlt pipeline execution.

Called by Prefect workers to fetch pipeline config and report results.
NOT exposed to external clients — gated by INTERNAL_API_KEY header.
"""

from __future__ import annotations

import structlog
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hub.apps.scheduled_export.models import ScheduledExport
from hub.apps.scheduled_ingestion.models import ScheduledIngestion

logger = structlog.get_logger(__name__)

_INTERNAL_API_KEY = "x-internal-api-key"


def _verify_internal(request: HttpRequest) -> bool:
    """Verify the request comes from an authorized internal worker."""
    from django.conf import settings

    expected = getattr(settings, "INTERNAL_API_KEY", None)
    if not expected:
        return True  # dev mode — no key configured
    return request.headers.get(_INTERNAL_API_KEY) == expected


@csrf_exempt
@require_http_methods(["GET"])
def internal_pipeline_config(
    request: HttpRequest, direction: str, resource_id: str
) -> JsonResponse:
    """
    285.6.5.1 — Worker fetches pipeline config for a scheduled run.

    GET /api/v1/data-movement/internal/config/{direction}/{id}/
    """
    if not _verify_internal(request):
        return JsonResponse({"error": "unauthorized"}, status=403)

    try:
        if direction == "ingestion":
            from hub.data_movement.dlt_credentials import resolve_credentials
            from hub.data_movement.dlt_pipeline import SOURCE_MAP

            obj = ScheduledIngestion.objects.get(id=resource_id)
            config = obj.source_config or {}
            source_type = obj.source_type
            credential_ref = getattr(obj, "credential_ref", None)
            dlt_source = SOURCE_MAP.get(source_type, "filesystem")
            return JsonResponse(
                {
                    "direction": direction,
                    "resource_id": resource_id,
                    "source_type": source_type,
                    "dlt_source": dlt_source,
                    "config": config,
                    "credential_ref": credential_ref,
                    "credentials": resolve_credentials(credential_ref),
                    "tenant_id": str(obj.tenant_id),
                }
            )
        else:
            from hub.data_movement.dlt_credentials import resolve_credentials
            from hub.data_movement.dlt_pipeline import DESTINATION_MAP

            obj = ScheduledExport.objects.get(id=resource_id)
            config = obj.destination_config or {}
            destination_type = obj.destination_type
            credential_ref = getattr(obj, "credential_ref", None)
            dlt_dest = DESTINATION_MAP.get(destination_type, "filesystem")
            return JsonResponse(
                {
                    "direction": direction,
                    "resource_id": resource_id,
                    "destination_type": destination_type,
                    "dlt_destination": dlt_dest,
                    "config": config,
                    "credential_ref": credential_ref,
                    "credentials": resolve_credentials(credential_ref),
                    "tenant_id": str(obj.tenant_id),
                }
            )
    except (ScheduledIngestion.DoesNotExist, ScheduledExport.DoesNotExist):
        return JsonResponse({"error": "not found"}, status=404)
    except Exception as e:
        logger.error(
            "internal_pipeline_config_failed",
            direction=direction,
            resource_id=resource_id,
            error=str(e),
        )
        return JsonResponse({"error": str(e)}, status=500)
