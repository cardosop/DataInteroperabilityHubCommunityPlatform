"""
Phase 234.1.5 – 234.1.7 — Merkle snapshot pipeline for the audit chain.

The pipeline runs hourly per tenant (driven by
:class:`hub.apps.jobs.models.JobType.AUDIT_MERKLE_SNAPSHOT`) and emits one
:class:`hub.apps.audit.models.AuditMerkleSnapshot` row per window:

    [period_start, period_end) →
        leaves = [event.chain_hash for event in window, sorted by chain_sequence]
        root_hex = SHA-256 Merkle root over leaves
        signature_hex = HMAC-SHA256(root_hex, signing_key)
        S3 upload: meshant-{env}-audit-merkle-roots
                   key:  {tenant_id}/{period_end_iso}/{snapshot_id}.json
                   mode: GOVERNANCE
                   until: now + (AUDIT_RETENTION_YEARS * 365 + 365) days
                                                          ^^^^^^^
                                                          per D234.6: outlive
                                                          retention by 1y so
                                                          the proof survives
                                                          the last archived row

Signing material lives in ``settings.AUDIT_CHAIN_SIGNING_KEYS_JSON`` —
same shape as ``CONSENT_SIGNING_KEYS_JSON``: a per-tenant rolling 3-key
list (index 0 = current, indices 1/2 = previous keys for verification).
Each key is a hex-encoded 32-byte secret rotated quarterly (90 days).

The pipeline is intentionally split across pure functions and an
orchestrator (:func:`snapshot_tenant_window`) so the test surface is
small and so the verifier (:func:`verify_root_signature`) can re-use
the same key resolution / HMAC code path the writer used.

No mocks of the chain or Merkle code. The S3 PUT is wrapped in a
defensive try/except (boto3 may be unavailable in dev / CI) — when it
fails the snapshot row is still persisted with empty ``s3_*`` fields so
the chain proof is locally durable; ops can re-shoot the PUT later.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.chain import merkle_root

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key resolution (rolling 3-key window per D234.6)
# ---------------------------------------------------------------------------


def _decode_hex_key(s: str) -> bytes:
    """Mirror of :func:`hub.apps.consent.signing._decode_hex_key`.

    Accepts an optional ``hex:`` prefix for parity with the consent key
    format so an operator who already understands one secret-management
    workflow doesn't have to learn a second.
    """
    key = s.strip()
    if key.startswith("hex:"):
        key = key[4:]
    raw = bytes.fromhex(key)
    if len(raw) < 16:
        raise ValueError("audit chain signing key must be at least 16 bytes (32 hex chars)")
    return raw


def get_signing_key_ring_for_tenant(tenant_id: str | None) -> list[bytes]:
    """Return up to 3 signing keys for ``tenant_id``, newest first.

    ``None`` (platform chain) falls back to the special ``"__platform__"``
    bucket so platform-level events can still produce signed snapshots
    without exposing tenant-scoped material.
    """
    raw = getattr(settings, "AUDIT_CHAIN_SIGNING_KEYS_JSON", None) or {}
    if isinstance(raw, str):
        # Defensive: an operator may set the env var as JSON-encoded JSON.
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        return []

    key_id = "__platform__" if tenant_id is None else str(tenant_id)
    entry: Any = raw.get(key_id)
    if entry is None:
        # Fallback: a default ring shared across tenants (NOT recommended
        # in production but useful for dev / CI). Same fallback hook the
        # consent signing layer used to support.
        entry = raw.get("__default__")
    if entry is None:
        return []
    if isinstance(entry, str):
        return [_decode_hex_key(entry)]
    if isinstance(entry, list):
        out: list[bytes] = []
        for item in entry[:3]:
            if isinstance(item, str):
                out.append(_decode_hex_key(item))
        return out
    if isinstance(entry, dict) and isinstance(entry.get("keys"), list):
        # Alternate shape: { "<tenant>": { "keys": ["hex1", "hex2", ...] } }.
        # Mirrors the optional dict form the consent signing module accepts.
        return [_decode_hex_key(k) for k in entry["keys"][:3] if isinstance(k, str)]
    return []


def sign_root(*, tenant_id: str | None, root_hex: str) -> tuple[str, int]:
    """Sign ``root_hex`` with the tenant's CURRENT key.

    Returns ``(signature_hex, key_index)`` where ``key_index`` is the
    index of the key in the ring (always 0 on the write path; the
    verifier searches the whole ring to support post-rotation reads).
    """
    ring = get_signing_key_ring_for_tenant(tenant_id)
    if not ring:
        raise RuntimeError(
            "AUDIT_CHAIN_SIGNING_KEYS_JSON has no key for tenant_id="
            f"{tenant_id!r}; cannot sign Merkle root."
        )
    signature = hmac.new(ring[0], root_hex.encode("utf-8"), hashlib.sha256).hexdigest()
    return signature, 0


def verify_root_signature(
    *,
    tenant_id: str | None,
    root_hex: str,
    signature_hex: str,
) -> bool:
    """Verify ``signature_hex`` against any key in the tenant's ring.

    Rolling-3-key window per D234.6: a signature produced under a
    just-rotated-out key must still verify, so we walk the whole ring.
    Returns False if the ring is empty or no key matches.
    """
    ring = get_signing_key_ring_for_tenant(tenant_id)
    if not ring:
        return False
    msg = root_hex.encode("utf-8")
    for key in ring:
        expected = hmac.new(key, msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature_hex):
            return True
    return False


# ---------------------------------------------------------------------------
# S3 Object Lock upload (best-effort, falls back to default_storage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _UploadResult:
    bucket: str
    key: str
    version_id: str


def _retention_until() -> datetime:
    years = int(getattr(settings, "AUDIT_RETENTION_YEARS", 3) or 3)
    extra_days = int(getattr(settings, "AUDIT_MERKLE_OBJECT_LOCK_EXTRA_DAYS", 365) or 365)
    return datetime.now(tz=UTC) + timedelta(days=years * 365 + extra_days)


def _build_proof_body(
    *,
    tenant_id: str | None,
    period_start: datetime,
    period_end: datetime,
    root_hex: str,
    signature_hex: str,
    signing_key_index: int,
    event_count: int,
    first_seq: int | None,
    last_seq: int | None,
) -> bytes:
    """Canonical JSON body uploaded to S3 (also stored locally on fallback)."""
    payload = {
        "schema": "audit.merkle.proof.v1",
        "tenant_id": str(tenant_id) if tenant_id else None,
        "period_start": period_start.astimezone(UTC).isoformat(),
        "period_end": period_end.astimezone(UTC).isoformat(),
        "event_count": event_count,
        "first_chain_sequence": first_seq,
        "last_chain_sequence": last_seq,
        "root_hex": root_hex,
        "signature_hex": signature_hex,
        "signing_key_index": signing_key_index,
        "produced_at": datetime.now(tz=UTC).isoformat(),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _upload_with_object_lock(
    *,
    bucket: str,
    key: str,
    body: bytes,
    until: datetime,
) -> _UploadResult:
    """Attempt an S3 PUT with Object Lock; raise on hard infra errors.

    Pattern mirrors ``hub/apps/breach/proof_storage.py:_try_put_object_lock``
    so an operator who has already tuned IAM for breach proofs gets the
    same surface for audit proofs.
    """
    try:
        import boto3  # type: ignore[import-not-found]  # optional dependency; ImportError handled below
        from botocore.exceptions import (
            ClientError,  # type: ignore[import-not-found]  # optional dependency; ImportError handled below
        )
    except ImportError:
        logger.warning(
            "audit_merkle_boto3_unavailable_falling_back_to_default_storage",
            extra={"key": key},
        )
        raise RuntimeError("boto3 unavailable") from None

    extra: dict[str, Any] = {}
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
    try:
        resp = client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=until,
        )
    except ClientError as exc:
        logger.warning(
            "audit_merkle_object_lock_put_failed_falling_back",
            extra={"bucket": bucket, "key": key, "error": str(exc)},
        )
        # Final fallback: try a plain PUT without Object Lock so we at
        # least get the object durably stored. The audit operator is on
        # the hook to fix the bucket policy.
        try:
            resp = client.put_object(Bucket=bucket, Key=key, Body=body)
        except ClientError as exc2:
            logger.error(
                "audit_merkle_s3_put_failed",
                extra={"key": key, "error": str(exc2)},
            )
            raise RuntimeError(f"S3 put_object failed: {exc2}") from exc2

    return _UploadResult(bucket=bucket, key=key, version_id=str(resp.get("VersionId") or ""))


def _upload_proof(
    *,
    tenant_id: str | None,
    snapshot_id: str,
    period_end: datetime,
    body: bytes,
) -> _UploadResult:
    """Resolve bucket, build object key, attempt Object-Lock PUT.

    Falls back to ``default_storage`` (FileSystemStorage in CI) when:
    * ``AUDIT_MERKLE_S3_BUCKET`` is empty (typical in dev), OR
    * boto3 is unavailable, OR
    * the PUT raises and the plain-PUT fallback also raised.

    Either way, the proof body is durable somewhere reachable from the
    Django app, and the ``AuditMerkleSnapshot`` row records exactly
    where (empty ``s3_*`` fields when stored via ``default_storage``).
    """
    bucket = (getattr(settings, "AUDIT_MERKLE_S3_BUCKET", "") or "").strip()
    tid = str(tenant_id) if tenant_id else "__platform__"
    period_end_iso = period_end.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    key = f"{tid}/{period_end_iso}/{snapshot_id}.json"

    if bucket:
        try:
            return _upload_with_object_lock(
                bucket=bucket, key=key, body=body, until=_retention_until()
            )
        except RuntimeError as exc:
            logger.warning(
                "audit_merkle_s3_upload_unavailable_local_only",
                extra={"key": key, "error": str(exc)},
            )

    # Local storage fallback. Use a distinct prefix so it doesn't collide
    # with arbitrary tenant assets in ``default_storage``.
    local_prefix = getattr(
        settings, "AUDIT_MERKLE_LOCAL_STORAGE_PREFIX", "audit-merkle-roots/"
    ).strip("/")
    local_path = f"{local_prefix}/{key}"
    default_storage.save(local_path, ContentFile(body))
    return _UploadResult(bucket="", key=local_path, version_id="")


# ---------------------------------------------------------------------------
# Snapshot orchestration
# ---------------------------------------------------------------------------


def _collect_chain_hashes(
    *,
    tenant_id: str | None,
    period_start: datetime,
    period_end: datetime,
) -> tuple[list[str], int | None, int | None]:
    """Return (chain_hashes, first_seq, last_seq) for the window.

    Uses ``AuditEvent.all_objects`` so archived rows participate in the
    Merkle root — the snapshot is a tamper-evidence artefact, not a
    user-facing list, and archival is metadata-only per Phase 232
    retention. Rows without ``chain_hash`` (pre-backfill) are skipped:
    the backfill job is the authoritative way to bring them into the
    chain, and a snapshot job would silently produce wrong leaves if
    it folded in raw NULLs.
    """
    from hub.apps.audit.models import AuditEvent

    qs = AuditEvent.all_objects.filter(
        tenant_id=tenant_id,
        timestamp__gte=period_start,
        timestamp__lt=period_end,
        chain_hash__isnull=False,
    ).order_by("chain_sequence")
    rows = list(qs.values_list("chain_sequence", "chain_hash"))
    if not rows:
        return [], None, None
    first_seq = rows[0][0]
    last_seq = rows[-1][0]
    return [h for _seq, h in rows], first_seq, last_seq


def snapshot_tenant_window(
    *,
    tenant: Any,
    period_start: datetime,
    period_end: datetime,
) -> Any:
    """Build + persist + upload a Merkle snapshot for one tenant + window.

    Returns the :class:`AuditMerkleSnapshot` row (created or pre-existing
    on idempotent re-run). Safe to call from a Celery task — the
    ``UniqueConstraint`` on (tenant, period_start, period_end) makes the
    re-run case a SELECT not a duplicate INSERT.

    Ordering (Phase 234.1 audit-fix Gap E)
    --------------------------------------
    We reserve the DB row FIRST (with empty ``s3_*`` fields), then upload
    to S3, then update the row with the upload result. The previous order
    (upload then INSERT) could leave orphan S3 objects on a UniqueConstraint
    race: two racers each uploaded under unique snapshot UUIDs, but only
    one INSERT won, leaving the loser's object with no DB pointer. Object
    Lock would keep that orphan around for the full retention window with
    no way to attribute it. The DB-first ordering means the LOSING racer
    never reaches the S3 PUT.
    """
    from hub.apps.audit.metrics import time_merkle_snapshot
    from hub.apps.audit.models import AuditMerkleSnapshot

    tenant_id = getattr(tenant, "id", None) if tenant is not None else None
    tenant_id_str = str(tenant_id) if tenant_id else None

    # Idempotency check. If a row already exists for this window we hand
    # it back unchanged so the caller's retry behaviour is well-defined.
    existing = AuditMerkleSnapshot.objects.filter(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
    ).first()
    if existing is not None:
        return existing

    # Phase 234.7.2 — time the snapshot pipeline. The wrap covers the
    # hash-tree build + signing + (later in the function) the S3
    # Object-Lock PUT so the histogram reflects the full wall-clock
    # cost the on-call sees during an outage. Observation fires on
    # ``finally`` so a snapshot that fails (e.g. S3 PUT 5xx) still
    # contributes to the latency curve — same contract as the FTS
    # timer in :func:`hub.apps.audit.metrics.time_search_query`.
    metric_tenant_label = tenant_id_str or "__platform__"
    with time_merkle_snapshot(tenant_id=metric_tenant_label):
        return _snapshot_tenant_window_inner(
            tenant=tenant,
            tenant_id=tenant_id,
            tenant_id_str=tenant_id_str,
            period_start=period_start,
            period_end=period_end,
        )


def _snapshot_tenant_window_inner(
    *,
    tenant: Any,
    tenant_id: Any,
    tenant_id_str: str | None,
    period_start: datetime,
    period_end: datetime,
) -> Any:
    """Inner body of :func:`snapshot_tenant_window` (split for metric wrapping)."""
    from hub.apps.audit.models import AuditMerkleSnapshot

    leaves, first_seq, last_seq = _collect_chain_hashes(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
    )
    root_hex = merkle_root(leaves)
    signature_hex, key_index = sign_root(tenant_id=tenant_id_str, root_hex=root_hex)

    # Step 1 — RESERVE the snapshot row (empty S3 fields). Two concurrent
    # jobs collapse to a single row here via the UniqueConstraint; the
    # loser falls back to SELECT and bails before any S3 PUT happens.
    with transaction.atomic():
        row, created = AuditMerkleSnapshot.objects.get_or_create(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            defaults=dict(
                event_count=len(leaves),
                first_chain_sequence=first_seq,
                last_chain_sequence=last_seq,
                root_hex=root_hex,
                signature_hex=signature_hex,
                signing_key_index=key_index,
                s3_bucket="",
                s3_key="",
                s3_version_id="",
            ),
        )

    if not created:
        # Lost the race; the winner already has (or will have) the S3
        # object. Returning the existing row is the correct idempotent
        # outcome.
        logger.info(
            "audit_merkle_snapshot_race_resolved",
            extra={"tenant_id": tenant_id_str, "snapshot_id": str(row.id)},
        )
        return row

    # Step 2 — only the WINNER uploads to S3. Any failure here is
    # logged but does not roll back the row: the proof is still
    # cryptographically verifiable from the in-DB ``root_hex`` +
    # ``signature_hex``, and ops can re-shoot the PUT (e.g. via a
    # ``--tenant-id`` re-snap once the bucket comes back).
    body = _build_proof_body(
        tenant_id=tenant_id_str,
        period_start=period_start,
        period_end=period_end,
        root_hex=root_hex,
        signature_hex=signature_hex,
        signing_key_index=key_index,
        event_count=len(leaves),
        first_seq=first_seq,
        last_seq=last_seq,
    )
    try:
        upload = _upload_proof(
            tenant_id=tenant_id_str,
            snapshot_id=str(row.id),
            period_end=period_end,
            body=body,
        )
    except Exception as exc:
        logger.warning(
            "audit_merkle_snapshot_upload_failed_db_proof_remains",
            extra={"snapshot_id": str(row.id), "error": str(exc)},
        )
        return row

    # Step 3 — record where the proof landed. Single-field UPDATE so we
    # don't tread on any other column.
    AuditMerkleSnapshot.objects.filter(pk=row.pk).update(
        s3_bucket=upload.bucket,
        s3_key=upload.key,
        s3_version_id=upload.version_id,
    )
    row.s3_bucket = upload.bucket
    row.s3_key = upload.key
    row.s3_version_id = upload.version_id
    return row


def snapshot_all_tenants_now(window_hours: int = 1) -> list[Any]:
    """Iterate every tenant + the platform chain; snapshot the last *window_hours*.

    Driven by the hourly job dispatcher; safe to call ad-hoc from a
    management command for backfill or audit. Returns the list of
    ``AuditMerkleSnapshot`` rows produced (or pre-existing on idempotent
    re-run).

    Resilience contract (Phase 234.1 audit-fix)
    -------------------------------------------
    A tenant whose keys aren't yet provisioned MUST NOT break the hourly
    sweep for the rest of the fleet. We catch ``RuntimeError`` (the
    explicit signal :func:`sign_root` emits on a missing key) per
    tenant, log the operational signal, and continue. Other exceptions
    still propagate — they indicate code bugs the operator needs to
    see immediately.
    """
    from hub.apps.audit.models import AuditEvent
    from hub.apps.tenants.models import Tenant

    now = timezone.now()
    # Window is bucketed to the top of the hour so concurrent runs at
    # different sub-second offsets produce the SAME window key.
    period_end = now.replace(minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(hours=window_hours)

    out: list[Any] = []
    failures: list[dict[str, str]] = []

    def _snap(target_tenant):
        try:
            row = snapshot_tenant_window(
                tenant=target_tenant,
                period_start=period_start,
                period_end=period_end,
            )
        except RuntimeError as exc:
            # Missing signing key — operational misconfiguration, not a
            # code bug. Log + record + continue.
            tid = str(target_tenant.id) if target_tenant is not None else "__platform__"
            logger.warning(
                "audit_merkle_snapshot_skipped_no_key",
                extra={"tenant_id": tid, "error": str(exc)},
            )
            failures.append({"tenant_id": tid, "reason": str(exc)})
            return
        out.append(row)

    # Tenants. The platform chain (tenant=None) needs an explicit pass —
    # we detect "any platform rows in window?" first to avoid a no-op
    # snapshot when nothing has happened.
    for tenant in Tenant.objects.all():
        _snap(tenant)
    platform_has_rows = AuditEvent.all_objects.filter(
        tenant__isnull=True,
        timestamp__gte=period_start,
        timestamp__lt=period_end,
        chain_hash__isnull=False,
    ).exists()
    if platform_has_rows:
        _snap(None)
    if failures:
        logger.warning(
            "audit_merkle_snapshot_partial_sweep",
            extra={"skipped": len(failures), "produced": len(out)},
        )
    return out
