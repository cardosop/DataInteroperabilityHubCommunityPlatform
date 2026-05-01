"""
Phase 228.F3.9 (REQ-LIN-F3-005) — Lineage Impact Dispatcher.

Consumes ``contract.updated`` events emitted by the post_save
signal (REQ-LIN-F3-001) and routes them through to the
``UserNotification`` + email pipeline.

Pipeline:

1. Compute the diff between the old and new lineage states
   (REQ-LIN-F5-002 helper — for v1 we hold the diff to a
   structurally-simple form; the heavy walker lives in F5).
2. Classify severity via :func:`lineage_severity.classify`.
3. Walk downstream lineage edges (from the ``LineageEdge`` table)
   to collect the set of contracts whose subscriptions might
   match.
4. Filter subscriptions by severity threshold + per-source
   visibility.
5. Apply the **per-(subscriber, source)** debounce — Redis SETEX
   key ``lineage:debounce:{subscriber_id}:{source_id}`` with TTL =
   ``F3_DEBOUNCE_TTL_SECONDS`` (default 1 hour).
6. Apply the **per-tenant** rate limit — Redis INCR + EXPIRE key
   ``lineage:rate:{tenant_id}`` with TTL = 3600 (max 1000/hour).
   Drops emit an audit row.
7. For cross-tenant notifications, the body is downgraded to
   "summary-only" (no transformation_ref, no field names) per
   F1 entitlement parity (REQ-LIN-F3-005 scenario "Cross-tenant
   content respects detail tier").
8. Enqueue ``UserNotification`` rows + email jobs.

Capability flag: ``lineage.change_notifications``.  When OFF, the
dispatcher logs the event and returns without dispatching — a
convenient kill-switch.

The dispatcher is ENTERED **synchronously from
``transaction.on_commit``**.  For F3 v1 the dispatch is
in-process — fast enough for the realistic per-event subscriber
count (≤ 1000 per the load-test target).  When the queue grows
past that, we hand off to django-rq via the ``@job('job_low')``
decorator below; the function is the same either way.

Metrics emitted (Prometheus client present in the project):

* ``lineage_subscription_dispatched_total{severity,channel,result}``
* ``lineage_subscription_debounced_total``
* ``lineage_severity_classified_total{severity}``
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from hub.apps.api.capabilities import is_capability_enabled
from hub.apps.contracts.lineage_severity import (
    ContractDiff,
    LineageDiff,
    Severity,
    classify,
)


logger = logging.getLogger(__name__)


# Debounce window: a subscriber receives at most one notification per
# source contract in this window.  REQ-LIN-F3-005 default 1 hour.
F3_DEBOUNCE_TTL_SECONDS = int(
    os.environ.get("F3_DEBOUNCE_TTL_SECONDS", str(60 * 60)),
)
# Per-tenant rate limit: max notifications dispatched per hour.
F3_PER_TENANT_RATE_LIMIT = int(
    os.environ.get("F3_PER_TENANT_RATE_LIMIT", "1000"),
)
F3_RATE_LIMIT_WINDOW_SECONDS = 3600


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def handle_contract_updated(
    *,
    contract_id: str,
    tenant_id: str,
    old_lineage_hash: str,
    new_lineage_hash: str,
    version: Optional[int] = None,
    actor_user_id: str = "",
) -> Dict[str, Any]:
    """Top-level dispatcher entrypoint.

    Returns a dict with the dispatch outcome counts so callers
    (tests, the management command for replay) can assert on it.
    """
    # Counts are kept in a separate int-only dict so the per-outcome
    # ``result.get(outcome, 0) + 1`` increment stays type-uniform.
    counts: Dict[str, int] = {
        "candidates": 0,
        "dispatched": 0,
        "debounced": 0,
        "rate_limited": 0,
        "skipped_below_threshold": 0,
    }
    result: Dict[str, Any] = {
        "contract_id": contract_id,
        "severity": None,
    }

    # Capability gate — the surface ships dark by default; ops flips
    # the flag when the GA rollout starts.
    if not is_capability_enabled("lineage.change_notifications"):
        logger.debug(
            "lineage_impact_dispatch_flag_off contract_id=%s", contract_id,
        )
        result.update(counts)
        return result

    from hub.apps.contracts.models import (
        Contract,
        LineageEdge,
        LineageSubscription,
    )

    try:
        contract = Contract.objects.get(id=contract_id)
    except Contract.DoesNotExist:
        logger.warning(
            "lineage_impact_dispatch_contract_missing contract_id=%s",
            contract_id,
        )
        result.update(counts)
        return result

    # Step 1 — diff (v1: just enumerate currently-open edges; the
    # full F5 diff machinery is out of scope here).  The classifier
    # is severity-driven from the LineageEdge index, not from a
    # before/after JSON walk.
    diff, contract_diff = _compute_diff(contract)

    # Step 2 — classify.
    severity = classify(diff, contract_diff)
    result["severity"] = severity.value
    _emit_metric(
        "lineage_severity_classified_total",
        labels={"severity": severity.value},
    )

    # Step 3 — find downstream candidate contracts: walk LineageEdge
    # rows where source_contract == this contract.  The full-graph
    # transitive walk is intentionally bounded — F3 v1 routes
    # notifications based on direct subscription matches; downstream
    # transitive impact is a Phase 228.F5 concern.
    candidate_subscriptions = LineageSubscription.objects.filter(
        source_contract_id=contract_id,
    ).select_related("user", "source_contract")
    counts["candidates"] = candidate_subscriptions.count()

    # Step 4-7 — per-subscription processing.
    redis_client = _get_redis_client()
    for sub in candidate_subscriptions.iterator(chunk_size=200):
        outcome = _process_subscription(
            subscription=sub,
            severity=severity,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            redis_client=redis_client,
            contract=contract,
        )
        counts[outcome] = counts.get(outcome, 0) + 1

    result.update(counts)
    return result


# ---------------------------------------------------------------------------
# Per-subscription processing
# ---------------------------------------------------------------------------


def _process_subscription(
    *,
    subscription,
    severity: Severity,
    tenant_id: str,
    actor_user_id: str,
    redis_client,
    contract,
) -> str:
    """Process one subscription; return the outcome bucket name.

    Possible outcomes (used for the result tally):

    * ``"skipped_below_threshold"``
    * ``"debounced"``
    * ``"rate_limited"``
    * ``"dispatched"``
    """
    # Severity gate.
    threshold = Severity(subscription.severity_threshold)
    if severity.numeric() < threshold.numeric():
        return "skipped_below_threshold"

    # Debounce (per (subscriber, source)).
    debounce_key = (
        f"lineage:debounce:{subscription.user_id}:"
        f"{subscription.source_contract_id or subscription.source_asset_id}"
    )
    if _debounce_holds(redis_client, debounce_key):
        _emit_metric("lineage_subscription_debounced_total")
        return "debounced"

    # Per-tenant rate limit.
    rate_key = f"lineage:rate:{tenant_id}"
    if _rate_limit_exceeded(redis_client, rate_key):
        _audit_rate_limit_drop(
            tenant_id=tenant_id,
            subscriber_id=str(subscription.user_id),
            contract_id=str(contract.id),
            actor_user_id=actor_user_id,
        )
        _emit_metric(
            "lineage_subscription_dispatched_total",
            labels={
                "severity": severity.value, "channel": "any",
                "result": "rate_limited",
            },
        )
        return "rate_limited"

    # Cross-tenant detail-tier downgrade — the subscriber's tenant
    # may not match the source contract's tenant.  Even though F3 v1
    # restricts subscriptions to same-tenant sources at create time,
    # this guard is the dispatcher-side enforcement so that a
    # backfilled cross-tenant row can't leak detail.
    user_tenant_id = getattr(subscription.user, "tenant_id", None)
    is_cross_tenant = (
        str(user_tenant_id) != str(contract.tenant_id)
    )

    title, message = _format_notification_body(
        contract=contract,
        severity=severity,
        cross_tenant=is_cross_tenant,
    )

    # Enqueue the in-app notification + (optional) email.
    from hub.apps.notifications.utils import create_user_notification
    from hub.apps.notifications.models import (
        NotificationCategory,
        NotificationType,
    )

    notification = create_user_notification(
        user=subscription.user,
        tenant=getattr(subscription.user, "tenant", None),
        title=title,
        message=message,
        notification_type=_severity_to_notification_type(severity),
        category=NotificationCategory.LINEAGE_IMPACT,
        resource_type="contract",
        resource_id=contract.id,
    )

    # SETEX the debounce key now that we've actually dispatched.
    _debounce_set(redis_client, debounce_key, F3_DEBOUNCE_TTL_SECONDS)

    # Bump the per-tenant rate counter.
    _rate_limit_bump(redis_client, rate_key, F3_RATE_LIMIT_WINDOW_SECONDS)

    # last_dispatched_at — the subscription row tracks when it last
    # fired so the UI can render "last seen" timestamps.
    from django.utils import timezone
    subscription.last_dispatched_at = timezone.now()
    subscription.save(update_fields=["last_dispatched_at"])

    if subscription.email and notification:
        _enqueue_email(
            user=subscription.user,
            title=title,
            body=message,
            severity=severity,
            contract=contract,
        )

    _emit_metric(
        "lineage_subscription_dispatched_total",
        labels={
            "severity": severity.value, "channel": "in_app",
            "result": "success",
        },
    )
    return "dispatched"


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------


def _compute_diff(contract) -> tuple[LineageDiff, ContractDiff]:
    """V1 diff: enumerate the currently-open lineage edges and return
    them as the "added" set with no removed/modified entries.

    A richer diff (REQ-LIN-F5-002) lives in the F5 surface — for F3
    v1 we use the edges' edge_type as the dominant severity signal.
    """
    from hub.apps.contracts.models import LineageEdge

    open_edges: List[Dict[str, Any]] = []
    for row in (
        LineageEdge.objects
        .filter(
            tenant_id=contract.tenant_id,
            source_contract_id=contract.id,
            valid_to__isnull=True,
        )
        .iterator(chunk_size=200)
    ):
        open_edges.append({
            "source_contract": str(row.source_contract_id) if row.source_contract_id else None,
            "target_contract": str(row.target_contract_id) if row.target_contract_id else None,
            "source_model": row.source_model,
            "source_field": row.source_field,
            "target_model": row.target_model,
            "target_field": row.target_field,
            "edge_type": row.edge_type,
            "transformation_ref": row.transformation_ref,
            "job_ref": row.job_ref,
        })

    diff = LineageDiff(
        added=open_edges,
        removed=[],
        modified=[],
        downstream_field_dependencies={},
    )
    contract_diff = ContractDiff()
    return diff, contract_diff


# ---------------------------------------------------------------------------
# Notification body formatting
# ---------------------------------------------------------------------------


def _format_notification_body(
    *, contract, severity: Severity, cross_tenant: bool,
) -> tuple[str, str]:
    """Return ``(title, message)`` for a lineage-impact notification.

    Cross-tenant content is summary-only — no transformation_ref,
    no field names — per REQ-LIN-F3-005 scenario.
    """
    contract_name = getattr(contract, "name", None) or str(contract.id)
    if cross_tenant:
        title = f"Lineage updated: {severity.value}"
        message = (
            f"A contract you subscribe to has changed at "
            f"{severity.value} severity.  Open the lineage view to see "
            f"details (visibility limited to entitled subscribers)."
        )
    else:
        title = f"Lineage updated: {contract_name}"
        message = (
            f"Lineage for '{contract_name}' has changed.  "
            f"Severity: {severity.value}.  "
            f"Open the contract's lineage view to see what changed."
        )
    return title, message


def _severity_to_notification_type(severity: Severity) -> str:
    """Map our 4-tier severity to the UI's 4-state type enum."""
    return {
        Severity.CRITICAL: "ERROR",
        Severity.HIGH: "WARNING",
        Severity.MEDIUM: "INFO",
        Severity.LOW: "INFO",
    }[severity]


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def _enqueue_email(*, user, title: str, body: str, severity: Severity, contract) -> None:
    """Hand off to the project's email queue.

    Uses the existing ``send_email_with_template`` task pattern; the
    template ``lineage_impact.html`` lives at
    ``hub/apps/notifications/templates/email/lineage_impact.html``
    (F3.11).  Failures are logged and swallowed.
    """
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string

        context = {
            "user": user,
            "title": title,
            "body": body,
            "severity": severity.value,
            "contract_name": getattr(contract, "name", str(contract.id)),
            "contract_id": str(contract.id),
        }
        try:
            html = render_to_string(
                "notifications/emails/lineage_impact.html", context,
            )
        except Exception:
            html = body
        send_mail(
            subject=title,
            message=body,
            from_email=None,  # Use DEFAULT_FROM_EMAIL.
            recipient_list=[user.email],
            html_message=html,
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning(
            "lineage_impact_email_enqueue_failed user_id=%s error=%s",
            user.id, exc,
        )


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _audit_rate_limit_drop(
    *, tenant_id: str, subscriber_id: str,
    contract_id: str, actor_user_id: str,
) -> None:
    """Record a rate-limit drop in the audit log.

    The drop is operationally interesting (the per-tenant cap fired)
    so we surface it as ``LINEAGE_IMPACT_RATE_LIMITED`` on the audit
    surface.  Failures here are logged and swallowed — the dispatcher
    must not raise back into ``transaction.on_commit``.
    """
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="LINEAGE_SUBSCRIPTION",
            action="DISPATCH_RATE_LIMITED",
            actor_user=None,  # System actor.
            tenant=None,
            resource_id=contract_id,
            result="WARNING",
            details={
                "tenant_id": tenant_id,
                "subscriber_id": subscriber_id,
                "actor_user_id": actor_user_id,
                "limit_per_hour": F3_PER_TENANT_RATE_LIMIT,
            },
            request=None,
        )
    except Exception as exc:
        logger.warning("lineage_impact_audit_failed error=%s", exc)


# ---------------------------------------------------------------------------
# Redis helpers — debounce + rate limit
# ---------------------------------------------------------------------------


def _get_redis_client():
    """Reuse the project's Redis client pattern from contracts.signals."""
    from hub.apps.contracts.signals import _get_redis_client as _shared

    return _shared()


def _debounce_holds(client, key: str) -> bool:
    """True if the debounce key currently exists (i.e. a notification
    was sent recently)."""
    if client is None:
        return False
    try:
        return bool(client.exists(key))
    except Exception:
        return False


def _debounce_set(client, key: str, ttl_seconds: int) -> None:
    """SETEX the debounce key with the configured TTL."""
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, "1")
    except Exception as exc:
        logger.warning(
            "lineage_impact_debounce_set_failed key=%s error=%s", key, exc,
        )


def _rate_limit_exceeded(client, key: str) -> bool:
    """True if the current per-tenant counter is at or above the cap."""
    if client is None:
        return False
    try:
        current = client.get(key)
        if current is None:
            return False
        return int(current) >= F3_PER_TENANT_RATE_LIMIT
    except Exception:
        return False


def _rate_limit_bump(client, key: str, ttl_seconds: int) -> None:
    """INCR the rate counter; set TTL the first time we touch the key.

    Uses INCR + a conditional EXPIRE so the first bump in a fresh
    window starts a new TTL, and subsequent bumps within the window
    don't reset it.
    """
    if client is None:
        return
    try:
        new_value = client.incr(key)
        if int(new_value) == 1:
            client.expire(key, ttl_seconds)
    except Exception as exc:
        logger.warning(
            "lineage_impact_rate_limit_bump_failed key=%s error=%s", key, exc,
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


# Module-level Counter cache keyed by metric name. Lazy registration
# prevents Prometheus's double-registration warnings on dev autoreload.
_METRIC_REGISTRY: Dict[str, Any] = {}


def _emit_metric(name: str, labels: Optional[Dict[str, str]] = None) -> None:
    """Best-effort Prometheus emission.  No-op if the client lib is
    unavailable in the runtime."""
    try:
        from prometheus_client import Counter

        if name not in _METRIC_REGISTRY:
            _METRIC_REGISTRY[name] = Counter(
                name, name, list((labels or {}).keys()),
            )
        counter = _METRIC_REGISTRY[name]
        if labels:
            counter.labels(**labels).inc()
        else:
            counter.inc()
    except Exception:
        pass


__all__ = [
    "handle_contract_updated",
    "F3_DEBOUNCE_TTL_SECONDS",
    "F3_PER_TENANT_RATE_LIMIT",
]
