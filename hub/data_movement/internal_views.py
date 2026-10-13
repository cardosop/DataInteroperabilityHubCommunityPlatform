"""
285.6.2 / 285.6.5.1 — Internal Worker API for dlt pipeline execution.

Called by Prefect workers to fetch pipeline config and report results.
NOT exposed to external clients — gated by INTERNAL_API_KEY header.

W3.7 (R2-P6) — FAIL-CLOSED auth (no dev fallback: without
``INTERNAL_API_KEY`` configured the endpoint rejects every request —
the pre-fix fallback returned 200 to anyone) and MASKED output (the
sibling-endpoint contract: the config leaves the hub masked via the
app CredentialManagers and NO resolved credential material is ever
returned).
"""

from __future__ import annotations

import hmac

import structlog
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hub.apps.scheduled_export.models import ScheduledExport
from hub.apps.scheduled_ingestion.models import ScheduledIngestion

logger = structlog.get_logger(__name__)

_INTERNAL_API_KEY = "x-internal-api-key"


def _verify_internal(request: HttpRequest) -> bool:
    """Verify the request comes from an authorized internal worker.

    Fail-closed: no ``INTERNAL_API_KEY`` configured → every request is
    rejected (the endpoint is unavailable until the operator provisions
    the key — never a dev fallback). The comparison is timing-safe
    (P.8 — a shared secret compared with a plain ``==`` leaks prefix
    information over the network).
    """
    from django.conf import settings

    expected = getattr(settings, "INTERNAL_API_KEY", None)
    if not expected:
        return False
    presented = request.headers.get(_INTERNAL_API_KEY) or ""
    return hmac.compare_digest(presented, expected)


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
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        if direction == "ingestion":
            from hub.data_movement.dlt_pipeline import SOURCE_MAP

            obj = ScheduledIngestion.objects.get(id=resource_id)
            # W3.7 — the sibling-endpoint masking contract: the DECRYPTED
            # config (legacy plaintext rows included) leaves masked; the
            # resolved credential material is never returned.
            from hub.apps.scheduled_ingestion.credential_manager import CredentialManager

            config = CredentialManager.get_masked_credentials(obj)
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
                    "tenant_id": str(obj.tenant_id),
                }
            )
        else:
            from hub.data_movement.dlt_pipeline import DESTINATION_MAP

            obj = ScheduledExport.objects.get(id=resource_id)
            # W3.7 — the sibling-endpoint masking contract (see the
            # ingestion branch).
            from hub.apps.scheduled_export.credential_manager import CredentialManager

            config = CredentialManager.get_masked_credentials(obj)
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
                    "tenant_id": str(obj.tenant_id),
                }
            )
    except (ScheduledIngestion.DoesNotExist, ScheduledExport.DoesNotExist):
        return JsonResponse({"error": "not found"}, status=404)
    except Exception as e:
        logger.exception(
            "internal_pipeline_config_failed",
            direction=direction,
            resource_id=resource_id,
            error=str(e),
        )
        return JsonResponse({"error": str(e)}, status=500)
