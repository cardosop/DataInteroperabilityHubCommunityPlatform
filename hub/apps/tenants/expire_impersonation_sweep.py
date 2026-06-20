"""
Phase 235.4.10 — Impersonation-session expiration sweep.

Walks every ``ImpersonationSession`` in ``ACTIVE`` status whose
``expires_at`` has elapsed and:

1. Atomically locks the row via ``select_for_update(skip_locked=True)``
   so a concurrent operator-driven exit cannot race with the sweep.
2. Re-validates that ``status == ACTIVE`` AND ``expires_at < now()``
   under the lock — defends against a flapping clock or a manual
   exit that beat us to the lock.
3. Calls ``session.end(reason="expired")``.
4. Emits one ``IMPERSONATION_ENDED`` audit row under the impersonated
   tenant's context (the auditor-facing surface).

Operationally similar to the Phase 235.3
``tenant_hard_delete_sweep`` (same row-locking + per-row revalidation
pattern), but driven every 5 minutes vs daily because the
session-expiry contract is "the JWT MUST not be usable a meaningful
time after the session is supposed to have ended".

Idempotency
===========

Re-running the sweep is a no-op: a session already moved to ENDED
by the previous run is filtered out by the ``status=ACTIVE`` clause
in the candidate enumeration AND by the under-lock revalidation.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.utils import create_audit_event

from .models import ImpersonationSession, ImpersonationSessionStatus

logger = logging.getLogger(__name__)


def _expire_one_session(*, session_id, sweep_run_id: str | None) -> dict[str, Any] | None:
    """Atomically re-lock + re-validate + end one session.

    Mirrors the Phase 235.3 ``_hard_delete_one_tenant`` shape: lookup
    via ``select_for_update(skip_locked=True)`` so two concurrent
    sweep instances can't both end the same session and both emit
    duplicate audit rows.

    Routes via the ``admin`` BYPASSRLS connection alias because the
    sweep is a cross-tenant management operation (per CLAUDE.md:
    "Management commands are cross-tenant by default and MUST use
    ``DATABASES['admin']``"). Without this the RLS USING clause on
    ``impersonation_sessions`` would only return rows whose
    ``impersonated_tenant_id`` matches the worker's
    ``app.current_tenant_id`` GUC — which is unset for system jobs.

    Returns the summary entry on a successful end, or ``None`` if
    the row was locked by another sweep / no longer eligible /
    already ENDED.
    """
    now = timezone.now()
    try:
        with transaction.atomic(using="admin"):
            try:
                sess = (
                    ImpersonationSession.objects.using("admin")
                    .select_for_update(skip_locked=True)
                    .select_related("impersonated_tenant", "impersonator_tenant")
                    .get(pk=session_id)
                )
            except ImpersonationSession.DoesNotExist:
                return None

            if sess.status != ImpersonationSessionStatus.ACTIVE or sess.expires_at > now:
                return None

            sess.end(reason="expired")
            create_audit_event(
                resource_type="IMPERSONATION_SESSION",
                action=_audit_et.IMPERSONATION_ENDED,
                actor_user=None,  # system-driven sweep
                tenant=sess.impersonated_tenant,
                resource_id=str(sess.id),
                result="SUCCESS",
                details={
                    "impersonation_session_id": str(sess.id),
                    "impersonator_user_id": str(sess.impersonator_id),
                    "impersonated_user_id": str(sess.impersonated_user_id),
                    "impersonator_tenant_id": (
                        str(sess.impersonator_tenant_id) if sess.impersonator_tenant_id else None
                    ),
                    "impersonated_tenant_id": str(sess.impersonated_tenant_id),
                    "end_reason": sess.end_reason,
                    "started_at": sess.started_at.isoformat(),
                    "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                    "sweep_run_id": sweep_run_id,
                },
                infer_tenant_from_actor=False,
            )
    except Exception:
        raise

    return {
        "session_id": str(sess.id),
        "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
        "end_reason": sess.end_reason,
    }


def run_expire_impersonation_sessions(
    *,
    sweep_run_id: str | None = None,
) -> dict[str, Any]:
    """Walk every expired-but-still-ACTIVE session and end it.

    Returns a summary dict::

        {
            "evaluated_count": int,
            "expired_count": int,
            "expired": [{"session_id": ..., "end_reason": ..., ...}, ...],
            "skipped": [{"session_id": ..., "reason": ...}, ...],
        }
    """
    now = timezone.now()
    # Phase 235.4 audit-fix Gap 3 — read candidate IDs via the
    # ``admin`` BYPASSRLS alias for the same reason the per-row
    # lookup does: the sweep is cross-tenant management work and
    # would otherwise see an empty list under any future RLS-enabled
    # rollout.
    candidates = list(
        ImpersonationSession.objects.using("admin")
        .filter(
            status=ImpersonationSessionStatus.ACTIVE,
            expires_at__lt=now,
        )
        .order_by("expires_at")
        .values_list("pk", flat=True)
    )

    expired: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for pk in candidates:
        try:
            result = _expire_one_session(session_id=pk, sweep_run_id=sweep_run_id)
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception(
                "impersonation_expire_sweep_session_failed",
                extra={"session_id": str(pk), "error": str(exc)},
            )
            skipped.append({"session_id": str(pk), "reason": "exception", "error": str(exc)})
            continue
        if result is None:
            skipped.append(
                {
                    "session_id": str(pk),
                    "reason": "lock_contention_or_state_drift",
                }
            )
            continue
        expired.append(result)

    summary = {
        "evaluated_count": len(candidates),
        "expired_count": len(expired),
        "expired": expired,
        "skipped": skipped,
    }
    logger.info("impersonation_expire_sweep_finished", extra={"summary": summary})
    return summary
