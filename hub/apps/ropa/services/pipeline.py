"""Shared RoPA materialisation logic (sync API path + worker job handler)."""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.utils import timezone

from hub.apps.audit import event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.files.storage import S3StorageClient
from hub.apps.ropa.models import RopaGeneration, RopaGenerationStatus
from hub.apps.ropa.services.generator import build_ropa_payload
from hub.apps.ropa.services.renderers import render_by_format


def ropa_large_export_bytes_threshold() -> int:
    return int(getattr(settings, "ROPA_LARGE_EXPORT_BYTES_THRESHOLD", 10 * 1024 * 1024))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ropa_storage_client() -> S3StorageClient:
    return S3StorageClient()


def materialize_generation(
    *,
    generation: RopaGeneration,
    actor_user,
) -> RopaGeneration:
    """Populate ``generation`` artefact bytes in S3 and mark COMPLETED."""
    tenant_id = str(generation.tenant_id)
    generation.status = RopaGenerationStatus.PROCESSING
    generation.save(update_fields=["status"])

    payload = build_ropa_payload(tenant_id=tenant_id, regulation=generation.regulation)
    blob, mime, filename = render_by_format(generation.output_format.lower(), payload)
    digest = sha256_hex(blob)
    prefix = getattr(settings, "ROPA_S3_KEY_PREFIX", "ropa/")
    key = f"{prefix}{generation.tenant_id}/ropa_exports/{generation.id}/{filename}"

    client = ropa_storage_client()
    client.upload_file(key, blob, mime)

    now = timezone.now()
    generation.object_key = key
    generation.content_sha256 = digest
    generation.byte_size = len(blob)
    generation.gaps_json = payload.get("gaps") or []
    generation.summary_json = {
        "asset_count": (payload.get("meta") or {}).get("asset_count"),
        "regulation": generation.regulation,
        "mime": mime,
        "download_filename": filename,
    }
    generation.status = RopaGenerationStatus.COMPLETED
    generation.completed_at = now
    generation.error_message = ""
    generation.cache_generation = int((payload.get("meta") or {}).get("cache_version") or 0)
    generation.save()

    actor = (
        actor_user
        if (actor_user is not None and getattr(actor_user, "is_authenticated", False))
        else None
    )
    create_audit_event(
        resource_type="ROPA_GENERATION",
        action=event_types.ROPA_GENERATED,
        actor_user=actor,
        tenant=generation.tenant,
        resource_id=str(generation.id),
        details={
            "regulation": generation.regulation,
            "format": generation.output_format,
            "byte_size": generation.byte_size,
            "artifact_key": generation.object_key,
            "gap_count": len(generation.gaps_json or []),
        },
    )
    return generation


def failure_generation(generation: RopaGeneration, message: str) -> None:
    generation.status = RopaGenerationStatus.FAILED
    generation.error_message = message[:8000]
    generation.completed_at = timezone.now()
    generation.save(update_fields=["status", "error_message", "completed_at"])
