"""
Core API-key rate-limit throttle (single identity — D2) + the R2-B1
public-registration throttle (W1.1).

The auth api-keys endpoint is the single-identity API key surface, so it
carries its own core-owned throttle. Keyed on tenant_id so tenant A's
exhaustion never affects tenant B's quota (Phase 273 throttle contract:
``throttle_{name}_{tenant_id}``). Emits ``RateLimit-*`` response headers on
every request (not only on 429) per IETF draft-ietf-httpapi-ratelimit-headers,
via the project-wide ``RateLimitHeadersMiddleware``.

The register endpoint is anonymous (no tenant yet) so its throttle is
keyed per client IP — the Phase 273 tenant-keying rule cannot apply to a
pre-tenant surface; the two buckets are per-surface by design.

The paid BaaS portal keeps its own ``BaaSAPIKeyThrottle`` for the paid views;
the two buckets are independent by design.
"""

from __future__ import annotations

import contextlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

# Shared by both throttles: check the rate AND emit the RateLimit-* META
# keys on every request, with the 429 audit in the failure branch (DRF
# 3.16 removed the throttled() override hook — a throttled() override is
# dead code on this DRF and its super() call crashes).


class _RateLimitHeaderThrottleMixin:
    """Allow_request wrapper: RateLimit-* META keys + audit-on-429."""

    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        try:
            rate_str = self.get_rate()
            num_req, period_sec = self.parse_rate(rate_str)
            history = self.history or []
            remaining = max(0, num_req - len(history))

            # Calculate reset time: when the oldest entry in the history
            # falls outside the window, the bucket refills.
            now = self.timer()
            if history:
                oldest = history[-1]
                elapsed = now - oldest
                reset_in = max(0, int(period_sec - elapsed))
            else:
                reset_in = int(period_sec)

            request.META["_ratelimit_limit"] = str(num_req)
            request.META["_ratelimit_remaining"] = str(remaining)
            request.META["_ratelimit_reset"] = str(reset_in)
        except (ValueError, TypeError, ImproperlyConfigured):
            pass
        if not allowed:
            # DRF 3.16 removed the throttled(request, wait) override hook;
            # the audit emission runs here, inside allow_request's failure
            # branch (the view raises Throttled itself afterwards).
            self._on_throttled(request, int(self.wait()))
        return allowed

    def _on_throttled(self, request, wait):
        """Refresh the reset header and emit the audit event on 429."""
        with contextlib.suppress(Exception):
            request.META["_ratelimit_reset"] = str(int(wait))
        try:
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(**self._throttled_audit_kwargs(request, wait))
        except Exception:
            pass

    def _throttled_audit_kwargs(self, request, wait):
        """The per-surface audit kwargs for the 429 emission."""
        raise NotImplementedError


class APIKeyThrottle(_RateLimitHeaderThrottleMixin, UserRateThrottle):
    """Per-tenant rate throttle for the auth API key management endpoints."""

    scope = "auth_api_key"

    def __init__(self):
        # DRF 3.16 parses num_requests INSIDE __init__ from the rate
        # present at super().__init__() time — assigning self.rate AFTER
        # super() updates the string but never recomputes num_requests
        # (the W1.1 live-found trap: RegisterThrottle enforced 10/min
        # while reporting 1000/min). Set the rate FIRST.
        self.rate = getattr(settings, "AUTH_API_KEY_RATE_LIMIT", "60/min")
        super().__init__()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            tenant_id = getattr(request.user, "tenant_id", None)
            if tenant_id:
                return f"throttle_auth_api_key_{tenant_id}"
        return self.get_ident(request)

    def _throttled_audit_kwargs(self, request, wait):
        # Phase P.9 — an API-key 429 is an API_KEY event, not a search
        # one (the previous emission mislabeled it).
        from hub.apps.audit.event_types import API_KEY_RATE_LIMIT_EXCEEDED

        return {
            "resource_type": "API_KEY",
            "action": API_KEY_RATE_LIMIT_EXCEEDED,
            "actor_user": request.user if request.user.is_authenticated else None,
            "tenant": (
                getattr(request.user, "tenant", None) if request.user.is_authenticated else None
            ),
            "resource_id": None,
            "result": "THROTTLED",
            "details": {
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
                "wait_seconds": int(wait),
            },
            "infer_tenant_from_actor": True,
        }


class RegisterThrottle(_RateLimitHeaderThrottleMixin, AnonRateThrottle):
    """R2-B1 (W1.1) — per-client-IP throttle on public registration.

    Registration is anonymous (no tenant yet), so the bucket key is the
    client IP (``throttle_auth_register_<ip>`` — the Phase 273
    tenant-keying rule cannot apply to a pre-tenant surface; there is no
    tenant whose quota could be confused). The production rate is 10/min
    per IP (``AUTH_REGISTER_RATE_LIMIT``); test environments relax the
    default so the shared E2E stack's persona seeding is not throttled —
    the 11th-register-429 contract is pinned by tests that override the
    rate explicitly.
    """

    scope = "auth_register"

    def __init__(self):
        # Same DRF-3.16 ordering trap as APIKeyThrottle: num_requests is
        # parsed inside super().__init__() — set the rate FIRST or the
        # throttle enforces the scope default ("10/minute") regardless
        # of AUTH_REGISTER_RATE_LIMIT.
        self.rate = getattr(settings, "AUTH_REGISTER_RATE_LIMIT", "10/min")
        super().__init__()

    def _throttled_audit_kwargs(self, request, wait):
        from hub.apps.audit.event_types import REGISTRATION_RATE_LIMIT_EXCEEDED

        return {
            "resource_type": "AUTH",
            "action": REGISTRATION_RATE_LIMIT_EXCEEDED,
            "actor_user": None,
            "tenant": None,
            "resource_id": None,
            "result": "THROTTLED",
            "details": {
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
                "wait_seconds": int(wait),
            },
            "infer_tenant_from_actor": False,
        }


class SSOThrottle(_RateLimitHeaderThrottleMixin, AnonRateThrottle):
    """D4/W1.5 — per-client-IP throttle on the SSO endpoints.

    The SSO surfaces are anonymous (pre-auth), so the bucket is the
    client IP (``throttle_sso_<ip>``). Production rate 10/min per IP
    (``AUTH_SSO_RATE_LIMIT``) — the login-URL initiation + callback
    share one bucket; test environments relax the default so the E2E
    stack's SSO scenarios are not throttled (the 11th-callback-429
    contract is pinned by explicit-override tests).
    """

    scope = "sso"

    def __init__(self):
        # The DRF-3.16 ordering trap (W1.1): num_requests is parsed
        # inside super().__init__() — set the rate FIRST.
        self.rate = getattr(settings, "AUTH_SSO_RATE_LIMIT", "10/min")
        super().__init__()

    def _throttled_audit_kwargs(self, request, wait):
        from hub.apps.audit.event_types import SSO_RATE_LIMIT_EXCEEDED

        return {
            "resource_type": "AUTH",
            "action": SSO_RATE_LIMIT_EXCEEDED,
            "actor_user": None,
            "tenant": None,
            "resource_id": None,
            "result": "THROTTLED",
            "details": {
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
                "wait_seconds": int(wait),
            },
            "infer_tenant_from_actor": False,
        }
