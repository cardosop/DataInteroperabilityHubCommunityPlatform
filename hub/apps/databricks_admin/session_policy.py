"""Session-refresh policy (openspec add-databricks-control-plane task 0b.7
— JOURNEY-DB-004 contract).

Pure policy math over explicit clock inputs (no IO, no clock reads) so
every rule is deterministic and unit-pinnable:

- ``half_ttl_refresh_due`` — silent refresh at HALF the access-token TTL
  (journey step 2; the 0b.5 provider does the actual exchange).
- ``countdown_state`` / ``refresh_allowed`` — a non-blocking countdown
  (default 5 min) before the workspace's ``absolute_session_lifetime``
  ends; refresh attempts STOP inside that window (journey step 4 — the
  session is ending, a fresh re-sign-in rebinds the pair).
- ``hub_session_deadline`` — the HUB session deadline is a pure function
  of HUB inputs (issued-at + hub lifetime). Binding expiry is consulted
  ONLY by the countdown/refresh policy — "Binding expiry never logs the
  user out of the Hub session" (journey step 5).

The frontend countdown banner (0b.12) consumes ``countdown_state``; the
silent-refresh scheduler consumes ``half_ttl_refresh_due`` +
``refresh_allowed``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from django.conf import settings

# Default countdown window before absolute re-authentication (0b.7).
DEFAULT_COUNTDOWN_SECONDS = int(getattr(settings, "SESSION_REAUTH_COUNTDOWN_SECONDS", 300))
# Default absolute Hub session lifetime — the point at which the HUB
# session itself forces re-authentication (independent of Databricks).
DEFAULT_HUB_SESSION_LIFETIME_SECONDS = int(
    getattr(settings, "ABSOLUTE_SESSION_LIFETIME_SECONDS", 12 * 3600)
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def half_ttl_refresh_due(
    *,
    access_token_issued_at: datetime,
    access_token_expires_at: datetime,
    now: datetime | None = None,
) -> bool:
    """True once the access token has lived HALF its TTL (silent refresh)."""
    now = _as_utc(now or datetime.now(UTC))
    issued = _as_utc(access_token_issued_at)
    expires = _as_utc(access_token_expires_at)
    ttl = (expires - issued).total_seconds()
    if ttl <= 0:
        return True  # already past expiry — refresh (or fail closed upstream)
    half_point = issued + timedelta(seconds=ttl / 2)
    return now >= half_point


def countdown_state(
    *,
    binding_absolute_expires_at: datetime,
    now: datetime | None = None,
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS,
) -> dict:
    """The countdown window before the binding's absolute session end.

    Returns ``{"active": bool, "seconds_remaining": int | None}`` —
    ``seconds_remaining`` is only meaningful when active, and clamps at 0
    once the absolute end has passed.
    """
    now = _as_utc(now or datetime.now(UTC))
    absolute_end = _as_utc(binding_absolute_expires_at)
    remaining = (absolute_end - now).total_seconds()
    if remaining > countdown_seconds:
        return {"active": False, "seconds_remaining": None}
    return {
        "active": True,
        "seconds_remaining": max(0, int(remaining)),
    }


def refresh_allowed(
    *,
    binding_absolute_expires_at: datetime,
    now: datetime | None = None,
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS,
) -> bool:
    """Refresh attempts STOP inside the countdown window — the session is
    ending and a re-sign-in (JOURNEY-DB-003) rebinds the token pair."""
    return not countdown_state(
        binding_absolute_expires_at=binding_absolute_expires_at,
        now=now,
        countdown_seconds=countdown_seconds,
    )["active"]


def hub_session_deadline(
    *,
    session_issued_at: datetime,
    hub_lifetime: timedelta | None = None,
) -> datetime:
    """The HUB session's re-authentication deadline.

    A PURE function of hub inputs — the Databricks binding expiry is never
    consulted, so binding expiry can never shrink (or extend) the Hub
    session (JOURNEY-DB-004 step 5).
    """
    issued = _as_utc(session_issued_at)
    lifetime = hub_lifetime or timedelta(seconds=DEFAULT_HUB_SESSION_LIFETIME_SECONDS)
    return issued + lifetime
