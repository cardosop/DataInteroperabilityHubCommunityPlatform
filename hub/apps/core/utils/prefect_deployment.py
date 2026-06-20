"""
Phase 25.9.1 — Shared helper for deleting Prefect deployments via the
integration service.

Used by:
  - scheduled_ingestion/views.py (DELETE handler)
  - scheduled_export/views.py    (DELETE handler)
  - jobs/management/commands/purge_orphan_prefect_deployments.py (CronJob)
"""

import logging
import os

logger = logging.getLogger(__name__)


def _build_headers() -> dict:
    """Return request headers including the internal API key when configured."""
    headers = {"Content-Type": "application/json"}
    from django.conf import settings

    internal_key = getattr(settings, "INTERNAL_API_KEY", "") or os.getenv("INTERNAL_API_KEY", "")
    if internal_key:
        headers["X-Internal-Api-Key"] = internal_key
    return headers


def delete_prefect_deployment(
    deployment_id: str,
    resource_id: str,
    resource_type: str,
    tenant_id: str,
    timeout_seconds: int = 15,
) -> bool:
    """
    Call prefect-integration-service ``DELETE /deployments/delete``.

    *resource_type* must be ``"scheduled_ingestion"`` or
    ``"scheduled_export"``.

    Returns ``True`` when it is safe to proceed with the DB deletion:
      - 2xx response (deployment deleted or already absent)
      - Integration service URL not configured (nothing to delete remotely)

    Returns ``False`` on any transient/server failure so the caller can
    abort the DB delete and let the purge CronJob retry later.
    """
    base_url = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base_url:
        return True

    import requests

    # The integration service expects {scheduled_ingestion_id, tenant_id}
    # or {scheduled_export_id, tenant_id} — NOT deployment_id.
    payload = {
        f"{resource_type}_id": resource_id,
        "tenant_id": tenant_id,
    }
    try:
        resp = requests.delete(
            f"{base_url}/deployments/delete",
            json=payload,
            headers=_build_headers(),
            timeout=timeout_seconds,
        )
        if resp.ok:
            logger.info(
                "Prefect deployment %s deleted for %s %s",
                deployment_id,
                resource_type,
                resource_id,
            )
            return True
        if resp.status_code == 404:
            logger.info(
                "Prefect deployment %s already gone for %s %s (404)",
                deployment_id,
                resource_type,
                resource_id,
            )
            return True
        logger.warning(
            "Integration service delete failed for %s %s: HTTP %s %s",
            resource_type,
            resource_id,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as e:
        logger.error(
            "Failed to call integration service delete for %s %s: %s",
            resource_type,
            resource_id,
            e,
            exc_info=True,
        )
        return False
