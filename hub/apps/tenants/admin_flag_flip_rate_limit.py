"""
Phase 235.1.3 — per-actor-per-hour rate limit for PLATFORM_ADMIN
feature-flag flips.

Spec contract (REQ-ADMIN-FLAGS-001):

> The platform SHALL rate-limit flag flips to 60 per PLATFORM_ADMIN
> per hour (Redis counter). The 61st attempt in a rolling hour SHALL
> return ``429 Too Many Requests`` with a ``Retry-After`` header.

Design mirrors :mod:`hub.apps.webhooks.rate_limit` (Phase 233.3) but
the bucket is **per-actor + per-hour** rather than per-tenant +
per-minute. Two reasons for the wider bucket:

1.  Operator behaviour is BURSTY — an admin rolling out a kill-switch
    across 30 tenants flips 30 flags in seconds; a per-minute bucket
    would 429 mid-rollout. The per-hour bucket absorbs the burst
    while still bounding sustained abuse.
2.  The two-person rule (REQ-ADMIN-FLAGS-002) doubles every sensitive
    flip into TWO operations (request + approve); we don't want to
    penalise admins for following the second-person discipline.

Atomicity contract
==================

The Redis ``INCR`` command is atomic; concurrent calls produce
strictly-ordered counter values. The function returns ``(allowed,
observed_count, retry_after_seconds)`` so the caller can stamp the
audit row (denied flips ARE auditable) and set the response
``Retry-After`` header.

Fail-open policy
================

If Redis is unavailable, the function logs and returns ``(True, 0,
0)``. We MUST NOT fail closed: a Redis outage would otherwise lock
every PLATFORM_ADMIN out of feature-flag flips precisely when ops
visibility (which often requires flag flips to inspect / canary) is
most needed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Maximum flips per actor per hour. Spec-pinned (REQ-ADMIN-FLAGS-001).
FLAG_FLIP_LIMIT_PER_HOUR: int = 60

#: TTL for the hourly Redis bucket. Two seconds longer than the
#: bucket window so a clock-skew of < 2s between API replicas doesn't
#: leave a key orphaned in the previous hour.
_BUCKET_TTL_SECONDS: int = 60 * 60 + 2


def _hour_bucket(now: datetime | None = None) -> str:
    """Return the hour-truncated UTC ISO-8601 bucket key.

    Hour resolution (``YYYY-MM-DDTHH``) means a key naturally rolls
    over at the top of each hour. The truncated form ensures every
    API replica that calls this in the same wall-clock hour agrees
    on the bucket — no sliding window.
    """
    moment = now or timezone.now()
    return moment.strftime("%Y-%m-%dT%H")


def _counter_key(actor_id: Any, bucket: str) -> str:
    """Compose the Redis key for the per-actor hourly bucket.

    Format: ``admin:feature_flag_flip:{actor_id}:{hour_iso8601}``.
    The literal prefix matches the test-helper key-scan glob in
    :func:`hub.apps.tenants.tests.test_admin_feature_flags_phase_235_1._redis_flush_admin_buckets`.
    """
    return f"admin:feature_flag_flip:{actor_id}:{bucket}"


def check_flag_flip_rate_limit(*, actor) -> tuple[bool, int, int, str]:
    """Atomically increment the per-actor hourly bucket and decide allow/deny.

    Returns
    -------
    (allowed, observed_count, retry_after_seconds, bucket)
        * ``allowed``               — True if the flip may proceed.
        * ``observed_count``        — Post-INCR counter value (1-indexed).
                                      ``0`` on Redis unavailable (fail-open).
        * ``retry_after_seconds``   — Seconds until the bucket rolls
                                      over (used as the ``Retry-After``
                                      response header on a 429). ``0``
                                      when allowed.
        * ``bucket``                — The bucket key used (``YYYY-MM-DDTHH``)
                                      so the caller can stamp the audit
                                      row without re-deriving it.

    Contract
    --------
    * The Redis ``INCR`` is atomic — two API workers concurrently
      flipping flags at observed_count 59 see exactly one return 60
      (allowed) and the other 61 (denied).
    * The first ``INCR`` of a fresh bucket sets ``EXPIRE`` in the
      same pipeline (one round-trip) so a network blip between the
      two commands can't leave an orphan key.
    * Fail-open on Redis unavailable (logged WARNING) — see module
      docstring.
    """
    actor_id = getattr(actor, "id", None)
    if actor_id is None:
        # Defensive: an unauthenticated request shouldn't reach this
        # code path (the viewset's permission_classes block it first),
        # but if it does we deny rather than crash.
        return False, 0, 0, _hour_bucket()

    bucket = _hour_bucket()
    key = _counter_key(actor_id, bucket)

    try:
        from hub.apps.api.middleware.idempotency_utils import get_redis_client

        client = get_redis_client()
        # Pipeline INCR + EXPIRE so the two commands go in ONE Redis
        # round-trip — see hub/apps/webhooks/rate_limit.py for the
        # full reasoning on why this is the load-bearing pattern.
        with client.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, _BUCKET_TTL_SECONDS)
            results = pipe.execute()
        observed = int(results[0] or 0)
    except Exception as exc:
        logger.warning(
            "admin_feature_flag_flip_rate_limit_redis_unavailable",
            extra={"actor_id": str(actor_id), "error": str(exc)},
        )
        return True, 0, 0, bucket

    if observed > FLAG_FLIP_LIMIT_PER_HOUR:
        # Compute seconds until the bucket rolls over. The hour bucket
        # ends at the next top-of-hour; we return the residual seconds
        # so the caller can stamp ``Retry-After``.
        now = timezone.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0)
        # If we're already at :00:00, next_hour is exactly now — bump.
        from datetime import timedelta as _td

        retry_after_seconds = int(((next_hour + _td(hours=1)) - now).total_seconds())
        return False, observed, max(1, retry_after_seconds), bucket

    return True, observed, 0, bucket
