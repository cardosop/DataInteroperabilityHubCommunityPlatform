"""
Phase 233.3 — Per-tenant outbound webhook rate limiting.

Pins REQ-WH-RL-002 (Redis INCR enforcement with 90s TTL + minute-truncated
key + atomic concurrent semantics) and REQ-WH-RL-005 (Prometheus counter
``meshant_webhook_rate_limit_blocks_total`` with bounded-cardinality labels).

The module exposes ONE function — ``check_outbound_rate_limit`` — that the
delivery path calls before issuing the HTTP request. The function returns a
tuple ``(allowed, observed_count, minute_bucket)`` so the caller can:

* If ``allowed=True``: proceed with delivery as normal.
* If ``allowed=False``: persist the delivery row with ``status=RATE_LIMITED``
  AND emit the ``WEBHOOK_RATE_LIMIT_EXCEEDED`` audit AND increment the
  Prometheus counter (REQ-WH-RL-004 + REQ-WH-RL-005). All four side
  effects (limit-deny + persist + audit + metric) commit in the same DB
  transaction so an observability outage doesn't fork the contract.

Fail-open semantics: when Redis is unavailable, the function logs a
warning and returns ``(allowed=True, observed_count=0, minute_bucket=...)``.
The alternative — fail-closed — would block ALL outbound webhooks
platform-wide on any Redis blip, which is a much worse failure mode than
allowing transient over-burst during a Redis outage. Same defensive
default as the existing distributed-lock primitive in
``hub.apps.core.distributed_lock``.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Protocol

import structlog
from django.utils import timezone

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant


logger = structlog.get_logger(__name__)


# REQ-WH-RL-002: Redis counter TTL = 90 seconds. Long enough to survive
# clock-skew between the platform and Redis, short enough that memory
# does not grow unbounded.
_COUNTER_TTL_SECONDS = 90


class _RateLimitCounter(Protocol):
    """Structural type covering both prometheus_client.Counter and the
    in-process stub fallback. Mirrors the pattern used by
    ``hub.apps.observability.cross_tenant_metrics._DeniedCounter`` so
    the module type-checks under either branch of the import-fallback.
    """

    def labels(self, **kwargs: str) -> "_RateLimitCounter": ...

    def inc(self) -> None: ...


# Prometheus counter (REQ-WH-RL-005). Labels are bounded-cardinality
# (tenant_id + webhook_id + event_type) — subscriber URL is excluded
# deliberately because it would explode label cardinality.
try:
    from prometheus_client import Counter

    webhook_rate_limit_blocks_total: _RateLimitCounter = Counter(
        "meshant_webhook_rate_limit_blocks_total",
        "Outbound webhook deliveries rate-limited at the tenant per-minute budget.",
        ["tenant_id", "webhook_id", "event_type"],
    )
except Exception:  # pragma: no cover — defensive fallback
    class _CounterStub:
        def labels(self, **_: object) -> "_CounterStub":  # noqa: ARG002
            return self

        def inc(self) -> None:
            return None

    webhook_rate_limit_blocks_total = _CounterStub()


def _minute_bucket(now=None) -> str:
    """Return the minute-truncated UTC ISO-8601 bucket key.

    REQ-WH-RL-002 requires the bucket be the truncated UTC minute
    (``YYYY-MM-DDTHH:MM``) — NOT a sliding window — so all replicas
    of the API + worker pool agree on the bucket. ``timezone.now()``
    is tz-aware UTC; ``strftime`` produces the canonical form.
    """
    moment = now or timezone.now()
    return moment.strftime("%Y-%m-%dT%H:%M")


def _counter_key(tenant_id: str, bucket: str) -> str:
    """Compose the Redis key for the per-tenant minute bucket.

    Format documented in REQ-WH-RL-002: ``webhook:outbound:{tenant_id}:{minute_iso8601}``.
    """
    return f"webhook:outbound:{tenant_id}:{bucket}"


def check_outbound_rate_limit(tenant: "Tenant") -> tuple[bool, int, str]:
    """Atomically increment the per-tenant minute bucket and decide allow/deny.

    Returns
    -------
    (allowed, observed_count, minute_bucket)
        * ``allowed``         — True if the delivery may proceed,
                                False if it should be marked RATE_LIMITED.
        * ``observed_count``  — Post-INCR counter value. ``0`` when Redis
                                is unavailable (fail-open path).
        * ``minute_bucket``   — The bucket key used for this check
                                (``YYYY-MM-DDTHH:MM``); included so the
                                caller can stamp it on the audit row
                                without re-deriving the timestamp.

    Concurrency contract (REQ-WH-RL-002 Scenario 4)
    -----------------------------------------------
    The Redis ``INCR`` command is atomic — two API workers concurrently
    triggering deliveries at count 299 see exactly one return 300 and
    the other 301. The function does NOT use any application-level
    lock; the atomicity of ``INCR`` is the load-bearing primitive.
    """
    bucket = _minute_bucket()
    limit: int = int(tenant.webhook_outbound_rate_limit_per_minute or 0)

    # REQ-WH-RL-001 Scenario 3: limit=0 disables outbound webhooks
    # entirely. We DO NOT increment the counter in this branch — the
    # kill-switch is delivery-time only, and counting would just churn
    # Redis without affecting the decision.
    if limit == 0:
        return False, 0, bucket

    try:
        from hub.apps.api.middleware.idempotency_utils import get_redis_client

        redis_client = get_redis_client()
        key = _counter_key(str(tenant.id), bucket)
        # 233.3.R1 GAP-A — pipeline INCR + EXPIRE so both commands go in
        # ONE Redis round-trip. The previous two-call pattern had a
        # subtle orphan-key memory leak: if the FIRST INCR succeeded
        # but its paired EXPIRE failed (network blip between calls),
        # the key would persist with no TTL, AND if rate-limiting then
        # kicked in for that minute (no further INCRs), the key would
        # accumulate indefinitely. Pipelining makes both commands
        # atomic-ish at the connection layer — a connection break
        # produces "both fail" rather than "INCR succeeded but EXPIRE
        # didn't reach Redis". The behaviour for SUBSEQUENT INCRs in
        # the same minute is unchanged: each call re-asserts EXPIRE so
        # a key with a missing TTL gets one as soon as the next call
        # lands.
        with redis_client.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, _COUNTER_TTL_SECONDS)
            results = pipe.execute()
        # Atomic INCR: returns the post-increment value. Two concurrent
        # callers see distinct values via Redis's serialised execution
        # (REQ-WH-RL-002 Scenario 4).
        observed_count = int(results[0])
    except Exception as exc:  # pragma: no cover — env-dependent
        # Fail-open: log + allow. Blocking all outbound webhooks
        # platform-wide on a Redis blip is worse than transient
        # over-burst during the outage.
        logger.warning(
            "webhook_rate_limit_check_failed_fail_open",
            tenant_id=str(tenant.id),
            error=str(exc),
        )
        return True, 0, bucket

    allowed = observed_count <= limit
    return allowed, observed_count, bucket


def emit_rate_limit_block_metric(
    *,
    tenant_id: str,
    webhook_id: str,
    event_type: str,
) -> None:
    """Increment the Prometheus rate-limit-blocks counter (REQ-WH-RL-005).

    Pulled into a helper so the call-site stays readable AND so a future
    change to the metric (e.g. adding a label, switching to a histogram)
    has ONE place to edit. No-op when ``prometheus_client`` is missing
    (the stub from the module-level fallback handles labels + inc).
    """
    try:
        webhook_rate_limit_blocks_total.labels(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            event_type=event_type,
        ).inc()
    except Exception as exc:  # pragma: no cover — metric backend issues
        logger.warning(
            "webhook_rate_limit_metric_emit_failed",
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            error=str(exc),
        )
