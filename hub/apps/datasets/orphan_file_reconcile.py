"""
Phase 260.1.B — Orphan-file soft-delete once the last referencing Dataset goes away.

Deletes batched onto ``transaction.on_commit`` so bulk ``Dataset.objects.delete()`` does
not amplify work (multiple ``post_delete`` → one reconcile pass per committing txn).

Votes are accumulated as lightweight **fragments** tagged with the same snapshot of
savepoint identifiers Django records for ``on_commit`` callbacks. Hooks installed via
:class:`install_dataset_orphan_file_hooks` discard fragments when a matching
``savepoint_rollback`` or full ``rollback`` occurs, avoiding stale merges after partial
txn aborts (same contract as Django’s ``run_on_commit`` queue).

MVP tenancy policy (260.1.B / D260.4): only **within-tenant** ``Dataset`` rows act as the
 refcount; there is **no cross-tenant** dedup across ``content_sha256``.

Eligibility gates (fail-closed when mixed):
* Each deleted ``Dataset`` row in this transaction must have had either **no asset**,
  a **missing** parent ``Asset`` row, or a **RETIRED** parent ``Asset``.
* If **any** row in the burst carried a **present, non-retired** asset, the aggregate
  vote is **False** (no automatic file soft-delete).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass

from django.db import connections, router, transaction
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.asyncio import async_unsafe

from hub.apps.audit.utils import create_audit_event
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context

logger = logging.getLogger(__name__)

_PENDING_ATTR = "_meshant_dataset_orphan_frags_v1"

_ORIG_SAVEPOINT_ROLLBACK = BaseDatabaseWrapper.savepoint_rollback
_ORIG_ROLLBACK = BaseDatabaseWrapper.rollback
_ORIG_CONNECT = BaseDatabaseWrapper.connect
_ORIG_CLOSE = BaseDatabaseWrapper.close

_DATASET_ORPHAN_DB_HOOKS_INSTALLED = False

REASON_ASSET_LESS_DATASET = "dataset_asset_was_null"
REASON_PARENT_ASSET_MISSING = "dataset_parent_asset_missing"
REASON_PARENT_ASSET_RETIRED = "dataset_parent_asset_retired"


@dataclass(frozen=True, slots=True)
class _OrphanFrag:
    """One Dataset deletion vote; mirrors Django's on_commit (sids snapshot + payload)."""

    sids_snap: frozenset
    tenant_id: str
    file_id: str
    gate_allow: bool
    snapshot_reason: str


def _delete_context_gate_allows(asset_id, tenant_id) -> bool:
    if tenant_id is None:
        return False

    tid = str(tenant_id)

    if asset_id is None:
        return True

    from hub.apps.assets.models import Asset, AssetStatus

    with tenant_context(tid):
        row = Asset.objects.filter(pk=asset_id).only("status").first()
    if row is None:
        return True
    return row.status == AssetStatus.RETIRED


def _snapshot_reason(asset_id, tenant_id) -> str:
    if asset_id is None:
        return REASON_ASSET_LESS_DATASET

    from hub.apps.assets.models import Asset, AssetStatus

    with tenant_context(str(tenant_id)):
        row = Asset.objects.filter(pk=asset_id).only("status").first()
    if row is None:
        return REASON_PARENT_ASSET_MISSING
    if row.status == AssetStatus.RETIRED:
        return REASON_PARENT_ASSET_RETIRED
    return "dataset_parent_asset_active"


class _OrphanVote:
    __slots__ = ("allow", "reasons")

    def __init__(self) -> None:
        self.allow = True
        self.reasons: set[str] = set()


def _pending_frags(connection) -> list[_OrphanFrag]:
    lst = getattr(connection, _PENDING_ATTR, None)
    if lst is None:
        lst = []
        setattr(connection, _PENDING_ATTR, lst)
    return lst


def _discard_orphan_frags_matching_savepoint(connection, rolled_back_sid) -> None:
    lst = getattr(connection, _PENDING_ATTR, None)
    if not lst:
        return
    setattr(
        connection,
        _PENDING_ATTR,
        [
            frag
            for frag in lst
            if rolled_back_sid not in frag.sids_snap
            # Mirrors Django ``run_on_commit`` filtering in savepoint_rollback.
        ],
    )


def _clear_all_orphan_frags(connection) -> None:
    setattr(connection, _PENDING_ATTR, [])


@async_unsafe
def _patched_savepoint_rollback(self, sid):
    _discard_orphan_frags_matching_savepoint(self, sid)
    return _ORIG_SAVEPOINT_ROLLBACK(self, sid)


@async_unsafe
def _patched_rollback(self):
    try:
        return _ORIG_ROLLBACK(self)
    finally:
        _clear_all_orphan_frags(self)


@async_unsafe
def _patched_connect(self):
    _clear_all_orphan_frags(self)
    return _ORIG_CONNECT(self)


@async_unsafe
def _patched_close(self):
    _clear_all_orphan_frags(self)
    return _ORIG_CLOSE(self)


def install_dataset_orphan_file_hooks() -> None:
    """
    Register DB-wrapper hooks so stale orphan votes disappear with txn abort semantics.

    Idempotent — safe across repeated ``AppConfig.ready`` / test runner imports.
    """
    global _DATASET_ORPHAN_DB_HOOKS_INSTALLED
    if _DATASET_ORPHAN_DB_HOOKS_INSTALLED:
        return

    BaseDatabaseWrapper.connect = _patched_connect
    BaseDatabaseWrapper.close = _patched_close
    BaseDatabaseWrapper.savepoint_rollback = _patched_savepoint_rollback
    BaseDatabaseWrapper.rollback = _patched_rollback

    _DATASET_ORPHAN_DB_HOOKS_INSTALLED = True


def schedule_orphan_file_check_after_dataset_delete(
    *,
    tenant_id,
    file_id,
    dataset_asset_id,
    using: str | None = None,
) -> None:
    """Record one Dataset-delete vote; flush runs ``on_commit`` (may dedupe empties)."""
    if not file_id or not tenant_id:
        return

    alias = using or router.db_for_write(File)
    conn = connections[alias]
    tid = str(tenant_id)
    fid = str(file_id)

    gate = _delete_context_gate_allows(dataset_asset_id, tenant_id)
    snapshot_reason = _snapshot_reason(dataset_asset_id, tenant_id)
    # Match Django ``BaseDatabaseWrapper.on_commit``: ``set(connection.savepoint_ids)``.
    sids_snap = frozenset(set(conn.savepoint_ids))

    frag = _OrphanFrag(
        sids_snap=sids_snap,
        tenant_id=tid,
        file_id=fid,
        gate_allow=gate,
        snapshot_reason=snapshot_reason,
    )
    _pending_frags(conn).append(frag)

    def _flush_this_connection_batch() -> None:
        flush_connection = connections[alias]
        _flush_pending_fragments(flush_connection, alias)

    transaction.on_commit(_flush_this_connection_batch, using=alias)


def _flush_pending_fragments(connection, alias: str) -> None:
    lst = getattr(connection, _PENDING_ATTR, None) or []
    setattr(connection, _PENDING_ATTR, [])

    merged: dict[tuple[str, str], _OrphanVote] = {}
    for frag in lst:
        key = (frag.tenant_id, frag.file_id)
        vote = merged.get(key)
        if vote is None:
            vote = _OrphanVote()
            merged[key] = vote
        vote.allow &= frag.gate_allow
        vote.reasons.add(frag.snapshot_reason)

    for (tenant_key, file_key), accum in merged.items():
        try:
            _reconcile_accumulated_vote(
                tenant_id_str=tenant_key,
                file_id_str=file_key,
                allow=accum.allow,
                reasons=sorted(accum.reasons),
                using=alias,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "dataset_orphan_reconcile_failed tenant_id=%s file_id=%s error=%s",
                tenant_key,
                file_key,
                exc,
                exc_info=True,
            )


def _reconcile_accumulated_vote(
    *,
    tenant_id_str: str,
    file_id_str: str,
    allow: bool,
    reasons: list[str],
    using: str,
) -> None:
    if not allow:
        return

    from hub.apps.audit import event_types as audit_event_types
    from hub.apps.datasets.models import Dataset

    exists_ds = Exists(
        Dataset.objects.using(using).filter(
            tenant_id=tenant_id_str,
            file_id=OuterRef("pk"),
        ),
    )
    with tenant_context(tenant_id_str):
        with transaction.atomic(using=using):
            qs = (
                File.objects.using(using)
                .filter(pk=file_id_str, tenant_id=tenant_id_str)
                .annotate(_has_ds=exists_ds)
            )
            candidates = qs.filter(_has_ds=False).select_for_update(of=("self",))
            picked = candidates.first()
            if picked is None:
                return
            if not picked.is_active():
                return

            tenant = Tenant.objects.using(using).get(pk=tenant_id_str)
            now_ts = timezone.now()
            candidates.update(
                status=FileStatus.DELETED.value,
                deleted_at=now_ts,
                updated_at=now_ts,
            )
            create_audit_event(
                resource_type="FILE",
                action=audit_event_types.FILE_ORPHAN_DETECTED,
                actor_user=None,
                tenant=tenant,
                resource_id=file_id_str,
                result="SUCCESS",
                details={
                    "file_id": file_id_str,
                    "tenant_id": tenant_id_str,
                    "reason": "eligible_dataset_burst_removed_last_ref",
                    "reason_codes": reasons,
                },
            )
