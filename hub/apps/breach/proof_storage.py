"""Archive immutable breach delivery proofs (Phase 232.3.10 / D232.15 Object Lock hook)."""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Mapping

import structlog
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProofArchiveResult:
    sha256_hex: str
    storage_path: str
    s3_version_id: str


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _try_put_object_lock(
    *,
    bucket: str,
    key: str,
    body: bytes,
    retention_days: int,
) -> str:
    """Return S3 VersionId when Object Lock put succeeds; else ``\"\"``."""
    if retention_days <= 0:
        return ""
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        logger.warning("boto3_unavailable_object_lock_skipped", key=key)
        return ""

    extra = {}
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if endpoint:
        extra["endpoint_url"] = endpoint
    client = boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None) or "us-east-1",
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        **extra,
    )
    until = datetime.now(tz=dt_timezone.utc) + timedelta(days=retention_days)
    kwargs: dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": body,
        "ObjectLockMode": "GOVERNANCE",
        "ObjectLockRetainUntilDate": until,
    }
    try:
        resp = client.put_object(**kwargs)
        return str(resp.get("VersionId") or "")
    except ClientError as exc:
        logger.warning(
            "breach_proof_object_lock_put_failed_falling_back",
            error=str(exc),
            key=key,
        )
        try:
            resp = client.put_object(Bucket=bucket, Key=key, Body=body)
            return str(resp.get("VersionId") or "")
        except ClientError as exc2:
            logger.warning("breach_proof_s377_put_failed", error=str(exc2), key=key)
            return ""


def archive_breach_notification_proof(
    *,
    tenant_id: str,
    notification_id: str,
    payload: Mapping[str, Any],
) -> ProofArchiveResult:
    """
    Persist canonical JSON + SHA-256. When ``USE_S3`` and retention > 0, attempt
    WORM-style governance retention via S3 Object Lock on the primary bucket.
    """
    raw = _canonical_json_bytes(payload)
    digest = hashlib.sha256(raw).hexdigest()
    prefix = getattr(settings, "BREACH_PROOF_STORAGE_PREFIX", "breach-proofs/").strip("/")
    key = f"{prefix}/{tenant_id}/{notification_id}.json"
    retention = int(getattr(settings, "BREACH_PROOF_OBJECT_LOCK_RETENTION_DAYS", 0) or 0)
    version_id = ""
    use_s3 = getattr(settings, "USE_S3", False)
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") or ""

    if use_s3 and bucket and retention > 0:
        version_id = _try_put_object_lock(bucket=bucket, key=key, body=raw, retention_days=retention)
        if version_id:
            return ProofArchiveResult(sha256_hex=digest, storage_path=key, s3_version_id=version_id)

    path = default_storage.save(key, ContentFile(raw))
    return ProofArchiveResult(sha256_hex=digest, storage_path=path, s3_version_id=version_id)
