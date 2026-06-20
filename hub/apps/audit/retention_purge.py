"""
Phase 234.4 — Permanent deletion of archived audit events after grace.

After Phase 234.3 archives audit events older than the configured retention
window (default 3 years), this sweep hard-deletes the archived rows past
a 90-day grace period. This closes the loop on GDPR's right-to-erasure on
the audit trail itself, while the Phase 234.1.5 Merkle-snapshot proofs in
S3 Object Lock preserve cryptographic evidence even after the raw rows
are gone.

RLS contract (audit-fix Gap 1)
==============================

``audit_events`` has Row-Level Security ENABLED (Phase 234.1 migration
``0005_enable_rls_audit_events``). The policy is:

* SELECT (USING)     — soft: returns row when
                       ``app.rls_audit_events_enabled != 'true'`` OR
                       ``tenant_id::text == current_setting('app.current_tenant_id')``.
* INSERT/DELETE/UPDATE (WITH CHECK) — strict: row must satisfy
                       ``tenant_id::text == current_setting('app.current_tenant_id')``.

Consequences for THIS module:

* DELETE on tenant-scoped rows from a connection without ``app.current_tenant_id``
  set to that tenant FAILS the policy silently (zero rows affected).
* DELETE on platform-chain rows (``tenant_id IS NULL``) ALWAYS fails the
  policy because ``NULL::text = ''`` is NULL (not TRUE) — only BYPASSRLS
  connections can purge these.

Resolution: ALL ORM operations in this module run on the ``admin`` DB
alias (``meshant_admin``, BYPASSRLS — see ``hub/db_router.py`` and
``hub/settings.py:DATABASES['admin']``). This is the same pattern the
``create_audit_event`` helper uses for the ``tenant=None`` write path,
and the canonical shape for cross-tenant management commands per
``CLAUDE.md``. Routing through admin works regardless of whether the
caller is the Kubernetes CronJob (``manage.py audit_permanent_delete_sweep``
with ``HUB_USE_ADMIN_DB_FOR_COMMANDS=1``) or the RQ dispatcher (no
env-var; default routing).

Atomicity contract (audit-fix Gap 2)
====================================

Meta-audit emission and the bulk delete must succeed or fail together —
audit-replay must not show a ``AUDIT_RETENTION_PURGED`` row claiming N
deletions that didn't actually happen. Both operations run inside a
single ``transaction.atomic(using="admin")`` block. If the delete
raises, the meta-audit row is rolled back too.

Chunking contract (audit-fix Gap 3)
===================================

``id__in`` clauses with >1k elements stress the Postgres planner and
risk a lock spike. The bulk delete is chunked at
:data:`_DELETE_CHUNK_SIZE` rows per statement; chunks run sequentially
within the atomic block so a mid-sweep failure rolls back the entire
operation cleanly.

Algorithm
=========

For each tenant (+ the platform chain via ``tenant_id IS NULL``):

1.  Skip the entire tenant if ANY active legal-hold ``RetentionPolicy``
    exists for it (``legal_hold=True`` AND either no expiry, or expiry
    in the future). Legal hold is interpreted broadly: a freeze on one
    resource implies "freeze the paper trail" too, since audit history
    is what regulators inspect when discovery is in scope.
2.  Select archived rows where ``archived_at < now() - <age_threshold>d``
    (default 90 days). Recent archive rows still inside the grace window
    are skipped.
3.  Per-row: if the audit event points at a typed resource
    (``resource_type`` ∈ {ASSET, DATASET, FILE} with a ``resource_id``),
    consult the standard governance helper
    :func:`resource_blocked_by_open_dsar_restriction`. Skip if blocked.
4.  Emit ONE ``AUDIT_RETENTION_PURGED`` meta-audit event BEFORE the
    bulk delete (same transaction). The meta-event is the durable
    receipt of the deletion; written as a fresh (non-archived) row so
    the sweep itself cannot purge it. The chain-position invariant
    therefore holds: the meta-audit's ``chain_sequence`` is strictly
    greater than every deleted row's ``chain_sequence``, because the
    chain head at meta-emit time IS the latest pre-delete row.
5.  Chunked ``QuerySet.delete()`` for the hard-delete. The
    ``AuditEvent.delete`` *instance* method raises ``ValueError`` to
    keep the model append-only; queryset-level delete is the
    legitimate bypass — this module is the only authorized caller,
    alongside the Phase 234.1.9 backfill command's ``QuerySet.update()``
    for chain fields.

Chain integrity is preserved by Phase 234.1's verifier: the gaps
introduced by this sweep are reported as informational ``erasure_gap``
entries (not ``prev_link_mismatch`` tamper signals) per the
234.1 × 232.2 × 234.4 cross-spec contract.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import structlog
from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import _sanitize_audit_payload_values

logger = structlog.get_logger(__name__)

#: Default grace window between archive and permanent delete.
DEFAULT_AGE_THRESHOLD_DAYS: int = 90

#: Cap on the number of deleted-event IDs persisted in the meta-audit
#: ``details_json``. ``deleted_count`` carries the authoritative
#: telemetry; the ID sample is for forensic spot-checks only.
_DELETED_ID_SAMPLE_CAP: int = 100

#: Rows deleted per chunked statement. Sized to stay well below the
#: Postgres parameter limit (~32k) and to bound the per-statement
#: lock footprint on the audit_events table.
_DELETE_CHUNK_SIZE: int = 1_000

#: Connection alias used for ALL ORM operations in this module. The
#: alias has BYPASSRLS on the role so DELETE statements aren't blocked
#: by the WITH CHECK policy on ``audit_events`` — see module docstring.
_ADMIN: str = "admin"


# ---------------------------------------------------------------------------
# Tenant-wide legal-hold check (broader than per-resource).
# ---------------------------------------------------------------------------


def _tenant_has_active_legal_hold(tenant_id: uuid.UUID | str | None) -> bool:
    """Return True if any RetentionPolicy on this tenant has an active legal hold.

    A hold is "active" when ``legal_hold=True`` AND either
    ``legal_hold_expires_at`` is NULL (indefinite) or in the future.
    Platform-chain rows (``tenant_id=None``) are never blocked by
    tenant-scoped legal holds — they're system-level audit history.
    """
    if tenant_id is None:
        return False

    from hub.apps.governance.models import RetentionPolicy

    now = timezone.now()
    qs = RetentionPolicy.objects.using(_ADMIN).filter(tenant_id=tenant_id, legal_hold=True)
    for policy in qs.iterator():
        if policy.legal_hold_expires_at is None or policy.legal_hold_expires_at > now:
            return True
    return False


# ---------------------------------------------------------------------------
# Per-row DSAR-restriction check.
# ---------------------------------------------------------------------------


_TYPED_RESOURCE_KINDS: frozenset[str] = frozenset({"ASSET", "DATASET", "FILE"})


def _row_blocked_by_dsar(
    *,
    tenant_id: uuid.UUID | str | None,
    resource_type: str | None,
    resource_id: Any,
) -> bool:
    """Return True iff an open RESTRICTION DSAR covers this row's resource."""
    if tenant_id is None or not resource_id or not resource_type:
        return False
    rt = resource_type.upper()
    if rt not in _TYPED_RESOURCE_KINDS:
        return False

    from hub.apps.governance.dsar_retention_block import (
        resource_blocked_by_open_dsar_restriction,
    )

    rid_str = str(resource_id)
    return resource_blocked_by_open_dsar_restriction(
        tenant_id=str(tenant_id),
        asset_id=rid_str if rt == "ASSET" else None,
        dataset_id=rid_str if rt == "DATASET" else None,
        file_id=rid_str if rt == "FILE" else None,
    )


# ---------------------------------------------------------------------------
# Meta-audit emission (admin connection, direct save to keep the write on
# the same connection as the bulk delete — see Atomicity contract above).
# ---------------------------------------------------------------------------


def _emit_purge_meta_audit(
    *,
    tenant_obj,
    tenant_label: str,
    deleted_ids: list[str],
    blocked_dsar: int,
    age_threshold_days: int,
    dry_run: bool,
) -> AuditEvent:
    """Persist the ``AUDIT_RETENTION_PURGED`` meta-audit row on the admin alias.

    Bypasses :func:`hub.apps.audit.utils.create_audit_event` so the write
    lands on the same connection (``admin``) as the bulk delete, making
    them atomic. We still apply the input-sanitisation step that
    ``create_audit_event`` performs — the payload here contains no
    user-supplied data, but sanitisation is cheap and keeps the audit
    surface uniform.
    """
    details = _sanitize_audit_payload_values(
        {
            "tenant_id": tenant_label,
            "deleted_count": len(deleted_ids),
            "deleted_event_ids": deleted_ids[:_DELETED_ID_SAMPLE_CAP],
            "dry_run": dry_run,
            "age_threshold_days": age_threshold_days,
            "skipped_dsar_restriction": blocked_dsar,
        }
    )

    event = AuditEvent(
        tenant=tenant_obj,
        actor_user=None,
        resource_type="JOB",
        resource_id=None,
        action=_audit_et.AUDIT_RETENTION_PURGED,
        result="SUCCESS",
        details_json=details,
        full_details_json=None,
    )
    event.save(using=_ADMIN)

    # Best-effort metric — mirrors the counter emission in
    # ``create_audit_event``. Wrapped so a metric-backend outage can't
    # block the sweep.
    try:
        from hub.apps.observability.otel_metrics import audit_events_total

        audit_events_total.labels(
            action=_audit_et.AUDIT_RETENTION_PURGED,
            resource_type="JOB",
            result="SUCCESS",
        ).inc()
    except Exception:  # pragma: no cover — observability never gates audit
        pass

    return event


# ---------------------------------------------------------------------------
# Chunked bulk delete.
# ---------------------------------------------------------------------------


def _chunked_hard_delete(
    *,
    tenant_id: uuid.UUID | None,
    ids: list[str],
) -> int:
    """Hard-delete ``ids`` in chunks of :data:`_DELETE_CHUNK_SIZE`.

    Returns the total number of rows the ORM reports deleted. Runs on
    the admin alias so the WITH CHECK RLS policy is bypassed regardless
    of tenant scope (including the ``tenant_id IS NULL`` platform chain).
    """
    total = 0
    for start in range(0, len(ids), _DELETE_CHUNK_SIZE):
        chunk = ids[start : start + _DELETE_CHUNK_SIZE]
        deleted, _per_model = (
            AuditEvent.all_objects.using(_ADMIN).filter(tenant_id=tenant_id, id__in=chunk).delete()
        )
        total += int(deleted or 0)
    return total


# ---------------------------------------------------------------------------
# Per-tenant sweep.
# ---------------------------------------------------------------------------


def _sweep_one_tenant(
    *,
    tenant_id: uuid.UUID | None,
    cutoff,
    age_threshold_days: int,
    dry_run: bool,
) -> dict[str, Any]:
    """Sweep a single tenant chain (or the platform chain when ``tenant_id`` is None).

    Returns a per-tenant summary dict. Always emits the meta-audit row
    (even in dry-run + zero-deletion cases) so audit-replay can prove
    the sweep RAN.
    """
    tenant_label = "__platform__" if tenant_id is None else str(tenant_id)

    # Discover eligible candidates on the admin alias. ``all_objects``
    # is required because the default manager filters out archived rows
    # — which is exactly the set we're sweeping.
    candidate_qs = (
        AuditEvent.all_objects.using(_ADMIN)
        .filter(
            tenant_id=tenant_id,
            is_archived=True,
            archived_at__lt=cutoff,
        )
        .order_by("archived_at", "id")
    )

    deleted_ids: list[str] = []
    blocked_dsar = 0

    # First pass: classify each candidate. We collect IDs before the
    # delete so the meta-audit emission knows the exact set and so we
    # can chunk the delete deterministically.
    for row in candidate_qs.values("id", "resource_type", "resource_id").iterator(chunk_size=500):
        if _row_blocked_by_dsar(
            tenant_id=tenant_id,
            resource_type=row.get("resource_type"),
            resource_id=row.get("resource_id"),
        ):
            blocked_dsar += 1
            continue
        deleted_ids.append(str(row["id"]))

    deleted_count = len(deleted_ids)

    # Resolve the tenant ORM row for the meta-audit FK (None ⇒ platform).
    tenant_obj = None
    if tenant_id is not None:
        from hub.apps.tenants.models import Tenant

        tenant_obj = Tenant.objects.using(_ADMIN).filter(id=tenant_id).first()

    # Single atomic block on the admin alias — meta-audit + delete must
    # commit or roll back together. See "Atomicity contract" in the
    # module docstring.
    with transaction.atomic(using=_ADMIN):
        _emit_purge_meta_audit(
            tenant_obj=tenant_obj,
            tenant_label=tenant_label,
            deleted_ids=deleted_ids,
            blocked_dsar=blocked_dsar,
            age_threshold_days=age_threshold_days,
            dry_run=dry_run,
        )

        actually_deleted = 0
        if not dry_run and deleted_ids:
            actually_deleted = _chunked_hard_delete(tenant_id=tenant_id, ids=deleted_ids)

    # Phase 234.7.2 — emit ``audit_retention_purged_total`` counter.
    # Increment by ``deleted_count`` (NOT 1-per-call) so the rate query
    # ``sum(rate(audit_retention_purged_total[1h]))`` yields "deletions
    # per hour" — the authoritative deletion-rate signal for the audit
    # trail. Dry-run is reported with ``dry_run="true"`` so Grafana can
    # show preview-vs-actual side-by-side; alerts filter on
    # ``dry_run="false"``.
    if deleted_count > 0:
        from hub.apps.audit.metrics import observe_retention_purged

        observe_retention_purged(
            tenant_id=tenant_label,
            deleted_count=deleted_count,
            dry_run=dry_run,
        )

    logger.info(
        "audit_permanent_delete_sweep_tenant",
        tenant=tenant_label,
        deleted_count=deleted_count,
        actually_deleted=actually_deleted if not dry_run else 0,
        blocked_dsar=blocked_dsar,
        dry_run=dry_run,
    )

    return {
        "tenant_id": tenant_label,
        "deleted_count": deleted_count,
        "skipped_dsar_restriction": blocked_dsar,
    }


# ---------------------------------------------------------------------------
# Tenant fan-out (the public entry point).
# ---------------------------------------------------------------------------


def _resolve_tenants(tenant_id: str | None) -> Iterable[uuid.UUID | None]:
    """Return the iterable of tenant_ids to sweep.

    ``tenant_id`` semantics mirror the audit-merkle-snapshot sweep:

    * ``None`` — every tenant that has at least one archived AuditEvent
      row, plus the platform chain (``tenant_id IS NULL``).
    * ``"__platform__"`` or ``""`` — only the platform chain.
    * a UUID string — only that tenant.

    Discovery runs on the admin alias so we see rows for tenants the
    caller would normally have no read access to — required for the
    cross-tenant sweep semantics.
    """
    if tenant_id is None:
        ids = list(
            AuditEvent.all_objects.using(_ADMIN)
            .filter(is_archived=True)
            .order_by()
            .values_list("tenant_id", flat=True)
            .distinct()
        )
        return ids

    normalized = (tenant_id or "").strip()
    if normalized in ("", "__platform__"):
        return [None]
    return [uuid.UUID(normalized)]


def run_audit_permanent_delete_sweep(
    *,
    dry_run: bool = False,
    tenant_id: str | None = None,
    age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS,
) -> dict[str, Any]:
    """Phase 234.4 entry point.

    Sweeps every tenant whose audit trail has archived rows past the
    ``age_threshold_days`` cutoff. Returns a top-level summary dict:

    .. code-block:: python

        {
            "dry_run": bool,
            "age_threshold_days": int,
            "deleted_count": int,                    # cross-tenant total
            "skipped_dsar_restriction": int,         # cross-tenant total
            "skipped_tenants_legal_hold": [...],     # tenant_ids (str)
            "tenants_swept": int,
            "per_tenant": [
                {"tenant_id": ..., "deleted_count": ..., ...},
                ...
            ],
        }

    The function is idempotent: running it twice in succession produces
    one meta-audit per (tenant, run) and zero additional deletions on
    the second run, because the freshly-emitted meta-audit isn't
    archived (and even if archived, would be < grace-window-old).
    """
    if age_threshold_days < 1:
        raise ValueError("age_threshold_days must be >= 1")

    cutoff = timezone.now() - timedelta(days=age_threshold_days)
    tenants = list(_resolve_tenants(tenant_id))

    per_tenant: list[dict[str, Any]] = []
    skipped_legal_hold: list[str] = []
    total_deleted = 0
    total_blocked_dsar = 0

    for tid in tenants:
        if _tenant_has_active_legal_hold(tid):
            label = "__platform__" if tid is None else str(tid)
            skipped_legal_hold.append(label)
            logger.info(
                "audit_permanent_delete_sweep_skipped_legal_hold",
                tenant=label,
            )
            continue

        report = _sweep_one_tenant(
            tenant_id=tid,
            cutoff=cutoff,
            age_threshold_days=age_threshold_days,
            dry_run=dry_run,
        )
        per_tenant.append(report)
        total_deleted += report["deleted_count"]
        total_blocked_dsar += report["skipped_dsar_restriction"]

    summary = {
        "dry_run": dry_run,
        "age_threshold_days": age_threshold_days,
        "deleted_count": total_deleted,
        "skipped_dsar_restriction": total_blocked_dsar,
        "skipped_tenants_legal_hold": skipped_legal_hold,
        "tenants_swept": len(per_tenant),
        "per_tenant": per_tenant,
    }
    logger.info("audit_permanent_delete_sweep_finished", summary=summary)
    return summary
