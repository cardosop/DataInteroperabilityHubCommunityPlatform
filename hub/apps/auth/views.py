"""
Authentication Views

REST API views for authentication (login, logout, password reset, etc.).
"""

import os
import time
import uuid
from datetime import timedelta

from django.utils.translation import gettext_lazy as _
from typing import Any

import structlog
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.audit.utils import log_auth_operation
from hub.apps.core.events.publisher import publish_event
from hub.apps.users.models import User, UserStatus
from hub.apps.users.password_history import (
    is_password_reused,
    record_password_change,
)

from .jwt_utils import JWTTokenGenerator
from .utils import sha256_hex as _sha256_hex
from .models import APIKey, LoginAttempt, RefreshToken
from .email_verification import (
    issue_verification_token_plaintext,
    mark_user_email_verified,
    plaintext_valid_for_user,
)
from .serializers import (
    APIKeyCreateSerializer,
    APIKeyResponseSerializer,
    APIKeySerializer,
    CurrentUserSerializer,
    EmailVerificationSerializer,
    InvitationAcceptanceSerializer,
    LoginSerializer,
    MePatchSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshTokenResponseSerializer,
    RefreshTokenSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    ResendEmailVerificationSerializer,
    TokenResponseSerializer,
)

logger = structlog.get_logger(__name__)

# Dummy password hash computed once at module load so timing is constant (11.5).
# Used when the supplied email does not match any user in the database.
_DUMMY_HASH = make_password("dummy-password-for-timing-parity")


def _get_client_ip(request) -> str:
    """Return the best-effort client IP from the request."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _user_lookup_alias() -> str:
    """
    Choose the connection alias for *pre-auth* user lookups.

    Discriminator: does the ``admin`` alias ACTUALLY map to a
    different DB role than ``default``? That is the only condition
    under which routing pre-auth lookups through ``admin`` buys
    anything.

    * **Production:** ``DATABASES["admin"]["USER"] = "meshant_admin"``
      (BYPASSRLS), ``DATABASES["default"]["USER"] = "meshant_app"``
      (RLS-enforced). Login / password-reset / register-precheck /
      resend-verification fire BEFORE we know the tenant, so the
      RLS policy on ``users`` (which filters by
      ``current_setting('app.current_tenant_id')``) sees zero rows
      under the ``meshant_app`` role. The admin alias bypasses RLS
      and is required for these to work.

    * **Test / dev (default):** the ``admin`` alias falls back to
      the same USER as ``default`` (see [hub/settings.py:803-816]).
      It is still a SEPARATE psycopg connection — Django's
      ``ConnectionHandler`` keys on alias name, not on connection
      params — so routing through it opens a parallel session
      whose MVCC snapshot is taken BEFORE the test's atomic-wrapped
      INSERT. ``User.objects.using("admin").get(email=...)`` then
      raises ``User.DoesNotExist`` for a user the test JUST
      created, and the timing-safe path turns that into a 400
      "Invalid email or password". Same trap previously documented
      in ``hub.apps.auth.jwt_utils`` and `views.py`'s
      ``select_for_update`` paths.

      ``RLS_USERS_ENABLED`` is NOT a usable discriminator: it
      defaults to ``True`` in [hub/settings.py:1852], so testing
      ``getattr(settings, "RLS_USERS_ENABLED", False)`` would
      pick ``"admin"`` in test too — and then trip the
      cross-connection MVCC trap above.

    Tests that need to exercise the production BYPASSRLS path
    explicitly must inherit from ``TransactionTestCase`` (so the
    fixture commits and the parallel admin session can see it) AND
    arrange for the admin alias to actually use a different USER —
    the codebase's ``RLSBypassPreAuthTransactionTest`` is the
    canonical pattern.
    """
    try:
        databases = settings.DATABASES
    except Exception:  # pragma: no cover — settings always loaded
        return "default"
    admin_cfg = databases.get("admin")
    default_cfg = databases.get("default", {})
    if not admin_cfg:
        return "default"
    admin_user = admin_cfg.get("USER")
    default_user = default_cfg.get("USER")
    if not admin_user or admin_user == default_user:
        return "default"
    return "admin"


def _get_cache_redis_client() -> Any | None:
    """
    Return django-redis raw client when Redis cache backend is active.

    For test environments using LocMemCache this returns None and callers
    should use the in-cache fallback implementation.
    """
    client_wrapper = getattr(cache, "client", None)
    get_client = getattr(client_wrapper, "get_client", None)
    if not callable(get_client):
        return None
    try:
        return get_client(write=True)
    except Exception:
        return None


_SLIDING_WINDOW_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local start = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, start)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.floor(window) + 10)
return 1
"""


def _redis_sliding_window_zset_key(logical_key: str) -> str:
    """
    Physical Redis key for the sliding-window ZSET.

    Kept separate from Django cache STRING keys for the same *logical* id
    (``login_ip_rate:…``, ``password_reset_email:…``) so backend encoding
    and raw ZSET data never collide. Uses ``KEY_PREFIX`` when configured.
    """
    try:
        conf = settings.CACHES.get("default", {})
        prefix = str(conf.get("KEY_PREFIX") or "").strip()
    except Exception:
        prefix = ""
    ns = "ratelimit:ss"
    if prefix:
        return f"{prefix}:{ns}:{logical_key}"
    return f"{ns}:{logical_key}"


def _sliding_window_rate_limit_allow(
    *,
    key: str,
    limit: int,
    window_seconds: int,
    current_ts: float | None = None,
) -> bool:
    """
    Sliding-window rate limit with Redis sorted-set primary path.

    Redis path uses ZSET + Lua for atomic check-and-insert:
    ZREMRANGEBYSCORE -> ZCARD -> ZADD -> EXPIRE.

    LocMemCache fallback keeps an in-cache timestamp list with the same
    sliding-window semantics for test environments.
    """
    now = float(current_ts if current_ts is not None else time.time())
    window_start = now - float(window_seconds)
    redis_client = _get_cache_redis_client()

    if redis_client is not None:
        # Use a unique member to avoid same-second collisions overwriting
        # earlier requests in the sorted set.
        member = f"{now}:{uuid.uuid4().hex}"
        redis_key = _redis_sliding_window_zset_key(key)
        try:
            allowed_raw = redis_client.eval(
                _SLIDING_WINDOW_RATE_LIMIT_LUA,
                1,
                redis_key,
                now,
                window_seconds,
                limit,
                member,
            )
            if isinstance(allowed_raw, (bytes, bytearray)):
                allowed_raw = int(allowed_raw.decode())
            return int(allowed_raw) == 1
        except Exception:
            # Fall through to in-cache fallback if Redis errors.
            pass

    timestamps = cache.get(key, [])
    if not isinstance(timestamps, list):
        timestamps = []
    timestamps = [float(ts) for ts in timestamps if float(ts) > window_start]
    if len(timestamps) >= limit:
        cache.set(key, timestamps, window_seconds)
        return False
    timestamps.append(now)
    cache.set(key, timestamps, window_seconds)
    return True


def _check_ip_rate_limit(ip: str, current_ts: float | None = None) -> bool:
    """
    Enforce IP-level rate limit on login (11.5).

    Returns True if the request is within limits, False if it should be rejected.
    """
    max_per_minute = getattr(settings, "LOGIN_IP_RATE_PER_MINUTE", 10)
    cache_key = f"login_ip_rate:{ip}"
    return _sliding_window_rate_limit_allow(
        key=cache_key,
        limit=max_per_minute,
        window_seconds=60,
        current_ts=current_ts,
    )


def _check_refresh_rate_limit(ip: str) -> bool:
    """
    Enforce IP-level rate limit on /auth/refresh/ (F4 — glittery-herding-graham).

    Returns True if within limits, False if rate-limited.
    Higher limit than login (30/min vs 10/min) since legitimate SPAs
    refresh proactively and from multiple tabs.
    """
    max_per_minute = getattr(settings, "REFRESH_IP_RATE_PER_MINUTE", 30)
    cache_key = f"refresh_ip_rate:{ip}"
    count = cache.get(cache_key, 0)
    if count >= max_per_minute:
        return False
    if count == 0:
        cache.set(cache_key, 1, 60)
    else:
        cache.incr(cache_key)
    return True


def _check_password_reset_rate_limit(email: str, current_ts: float | None = None) -> bool:
    """
    Enforce per-email rate limit on password reset (Phase 87).

    Returns True if within limits, False if rate-limited.
    Defaults to 5 requests per hour per email address.
    """
    max_per_window = int(
        getattr(settings, "PASSWORD_RESET_RATE_LIMIT_PER_WINDOW", 5),
    )
    window_seconds = int(
        getattr(settings, "PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", 3600),
    )
    cache_key = f"password_reset_email:{email}"
    return _sliding_window_rate_limit_allow(
        key=cache_key,
        limit=max_per_window,
        window_seconds=window_seconds,
        current_ts=current_ts,
    )


def _check_email_verification_resend_rate_limit(email: str) -> bool:
    """
    Per-email rate limit for verification resend (Phase 204).

    Allows 3 requests per hour per email address (cache-backed, same pattern as password reset).
    """
    max_per_hour = 3
    cache_key = f"email_verify_resend:{email.lower()}"
    cache.add(cache_key, 0, 3600)
    try:
        new_count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, 3600)
        return True
    return new_count <= max_per_hour


def _consume_rate_limit_counter(
    *,
    cache_key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Atomically increment a fixed-window counter and evaluate the limit."""
    cache.add(cache_key, 0, window_seconds)
    try:
        new_count = int(cache.incr(cache_key))
    except ValueError:
        cache.set(cache_key, 1, window_seconds)
        new_count = 1
    return new_count <= limit, new_count


def _retry_after_seconds(cache_key: str, fallback_seconds: int) -> int:
    """Read cache TTL when supported; otherwise return fallback window."""
    ttl_fn = getattr(cache, "ttl", None)
    if callable(ttl_fn):
        try:
            ttl_value = ttl_fn(cache_key)
        except Exception:
            ttl_value = None
        if isinstance(ttl_value, int) and ttl_value > 0:
            return ttl_value
    return fallback_seconds


def _verify_email_ip_cache_key(ip: str) -> str:
    return f"verify_email_ip:{ip}"


def _verify_email_token_cache_key(token: str) -> str:
    return f"verify_email_token:{_sha256_hex(token)}"


def _check_verify_email_ip_rate_limit(ip: str) -> tuple[bool, str, int]:
    max_per_hour = getattr(settings, "VERIFY_EMAIL_IP_RATE_PER_HOUR", 10)
    window_seconds = 3600
    cache_key = _verify_email_ip_cache_key(ip)
    allowed, _ = _consume_rate_limit_counter(
        cache_key=cache_key,
        limit=max_per_hour,
        window_seconds=window_seconds,
    )
    return allowed, cache_key, window_seconds


def _check_verify_email_token_rate_limit(token: str) -> tuple[bool, str, int]:
    max_per_hour = getattr(settings, "VERIFY_EMAIL_TOKEN_RATE_PER_HOUR", 5)
    window_seconds = 3600
    cache_key = _verify_email_token_cache_key(token)
    allowed, _ = _consume_rate_limit_counter(
        cache_key=cache_key,
        limit=max_per_hour,
        window_seconds=window_seconds,
    )
    return allowed, cache_key, window_seconds


def _get_verify_email_rate_limit_ip(request) -> str:
    """
    Resolve client IP for verify-email rate limiting.

    Security default is fail-closed against spoofing: trust REMOTE_ADDR unless
    explicit opt-in enables X-Forwarded-For parsing.
    """
    if getattr(settings, "VERIFY_EMAIL_TRUST_X_FORWARDED_FOR", False):
        return _get_client_ip(request)
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _account_lockout_cache_key(email: str) -> str:
    return f"login_lockout_failures:{email.lower().strip()}"


def _account_lockout_window_seconds() -> int:
    window_minutes = getattr(settings, "LOGIN_LOCKOUT_WINDOW_MINUTES", 15)
    return max(window_minutes * 60, 1)


def _progressive_lockout_window(lockout_level: int) -> int:
    """
    Compute progressive backoff window in seconds (277.B.066).

    Each consecutive lockout doubles the base window:
      level 1 → 15 min, level 2 → 30 min, level 3 → 60 min, ...

    Capped at LOGIN_LOCKOUT_MAX_WINDOW_MINUTES (default 24h).
    """
    base_minutes = getattr(settings, "LOGIN_LOCKOUT_WINDOW_MINUTES", 15)
    max_minutes = getattr(settings, "LOGIN_LOCKOUT_MAX_WINDOW_MINUTES", 1440)
    multiplier = 2 ** max(lockout_level - 1, 0)
    window_minutes = base_minutes * multiplier
    return min(window_minutes, max_minutes) * 60


def _check_account_lockout(email: str, user=None) -> bool:
    """
    Enforce account-level lockout (11.5 + 277.B.066 progressive backoff).

    Returns True if the account is NOT locked (request allowed),
    False if it IS locked (too many recent failures).

    Two-tier check:
      1. If user exists and has locked_until set: progressive backoff.
      2. Otherwise: flat window based on LoginAttempt count (graceful
         for unknown-email lockouts).
    """
    normalized_email = email.lower().strip()

    # ── Tier 1: Progressive lockout for known users ────────────────────────
    if user is not None and user.locked_until is not None:
        if timezone.now() < user.locked_until:
            return False
        # Lockout expired — lift it so the next attempt is allowed
        user.locked_until = None
        user.failed_login_count = 0
        user.save(update_fields=["locked_until", "failed_login_count", "updated_at"])

    # ── Tier 2: Cache/DB count-based check (flat window fallback) ──────────
    cache_key = _account_lockout_cache_key(normalized_email)
    max_attempts = getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
    cached_failures = cache.get(cache_key)

    if cached_failures is None:
        window_minutes = getattr(settings, "LOGIN_LOCKOUT_WINDOW_MINUTES", 15)
        since = timezone.now() - timedelta(minutes=window_minutes)
        failures = LoginAttempt.objects.filter(
            email=normalized_email, success=False, created_at__gte=since
        ).count()
        cache.set(cache_key, failures, _account_lockout_window_seconds())
    else:
        failures = int(cached_failures)
    return failures < max_attempts


def _record_login_attempt(email: str, ip: str, success: bool, user=None) -> None:
    # Truncate email to the field max_length to avoid DataError on oversized inputs
    normalized_email = email.lower().strip()[:254]
    LoginAttempt.objects.create(email=normalized_email, ip_address=ip, success=success)
    cache_key = _account_lockout_cache_key(normalized_email)
    if success:
        cache.delete(cache_key)
        # Clear progressive lockout state on successful login (277.B.066)
        if user is not None:
            user.failed_login_count = 0
            user.lockout_level = 0
            user.locked_until = None
            user.save(update_fields=["failed_login_count", "lockout_level", "locked_until", "updated_at"])
        return
    window_seconds = _account_lockout_window_seconds()
    cache.add(cache_key, 0, window_seconds)
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, window_seconds)

    # ── Progressive backoff tracking (277.B.066) ───────────────────────────
    if user is not None:
        user.failed_login_count += 1
        max_attempts = getattr(settings, "LOGIN_MAX_ATTEMPTS", 5)
        if user.failed_login_count >= max_attempts:
            user.lockout_level += 1
            window_seconds = _progressive_lockout_window(user.lockout_level)
            user.locked_until = timezone.now() + timedelta(seconds=window_seconds)
            # Reset counter so further failures during lockout don't re-trigger
            user.failed_login_count = 0
        user.save(update_fields=["failed_login_count", "lockout_level", "locked_until", "updated_at"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Attach the refresh token as a httpOnly, Secure, SameSite=Strict cookie (11.1)."""
    cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
    max_age = getattr(settings, "JWT_REFRESH_TOKEN_EXPIRY", 86400)
    # Phase 221.5.1: If the cookie name carries the __Secure- prefix,
    # the Secure attribute MUST be True — browsers silently drop the
    # cookie otherwise.  This covers both the environment-based default
    # and any explicit env-var override (REFRESH_COOKIE_NAME=__Secure-x).
    # For non-prefixed names, secure=True when DEBUG=False (production-like).
    secure = cookie_name.startswith("__Secure-") or not getattr(
        settings, "DEBUG", False
    )
    cookie_domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None) or None
    cookie_kwargs = {
        "max_age": max_age,
        "httponly": True,
        "secure": secure,
        "samesite": "Strict",
        "path": "/",
    }
    if cookie_domain is not None:
        cookie_kwargs["domain"] = cookie_domain
    response.set_cookie(cookie_name, token, **cookie_kwargs)


def _set_access_cookie(response: Response, token: str) -> None:
    """Attach access token cookie using the same domain policy as refresh cookie."""
    cookie_domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None) or None
    cookie_kwargs = {
        "max_age": settings.JWT_ACCESS_TOKEN_EXPIRY,
        "httponly": True,
        "secure": not getattr(settings, "DEBUG", False),
        "samesite": "Strict",
        "path": "/",
    }
    if cookie_domain is not None:
        cookie_kwargs["domain"] = cookie_domain
    response.set_cookie("access_token", token, **cookie_kwargs)


def _clear_refresh_cookie(response: Response) -> None:
    """Expire the refresh-token cookie on logout (11.1)."""
    cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
    cookie_domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None) or None
    if cookie_domain is None:
        response.delete_cookie(cookie_name, path="/")
    else:
        response.delete_cookie(cookie_name, path="/", domain=cookie_domain)


def _clear_auth_cookies(response: Response) -> None:
    """Expire all auth cookies on logout (Phase 220.4).

    Clears both the refresh_token cookie (Phase 11.1) and the access_token
    cookie (Phase 220.4).  Safe to call even when cookies were never set.
    """
    _clear_refresh_cookie(response)
    cookie_domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None) or None
    if cookie_domain is None:
        response.delete_cookie("access_token", path="/")
    else:
        response.delete_cookie("access_token", path="/", domain=cookie_domain)


def _get_refresh_token_str(request) -> str:
    """
    Extract the raw refresh-token string (11.1 + B2a glittery-herding-graham).

    Precedence depends on the auth mode:
    - Cookie mode (USE_HTTPONLY_AUTH_COOKIES=True): httpOnly cookie > body
    - Body mode  (USE_HTTPONLY_AUTH_COOKIES=False): body > cookie

    In body mode, a stale httpOnly cookie (from a prior cookie-mode session
    or from the always-set refresh cookie) could override a fresh body token.
    Checking body first prevents this.
    """
    cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
    use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)

    if use_cookie_auth:
        # Cookie mode: prefer cookie, fall back to body
        token = request.COOKIES.get(cookie_name, "")
        if not token and request.data:
            token = request.data.get("refresh_token", "") or ""
    else:
        # Body mode: prefer body, fall back to cookie
        token = ""
        if request.data:
            token = request.data.get("refresh_token", "") or ""
        if not token:
            token = request.COOKIES.get(cookie_name, "")
    return token.strip()



@extend_schema(
    request=LoginSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid credentials"),
        403: OpenApiResponse(
            description="Email not verified after 24h grace (Phase 204): "
            "error=EMAIL_NOT_VERIFIED, resend_url, code, detail"
        ),
        429: OpenApiResponse(description="Too many login attempts"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login(request):
    """
    User login endpoint.

    POST /auth/login
    Body: {"email": "user@example.com", "password": "password"}

    Returns access token; refresh token is set as httpOnly cookie (11.1).
    Enforces IP-level rate limiting (11.5) and account-level lockout (11.5).
    Timing side-channel is neutralised by always running check_password (11.5).
    """
    client_ip = _get_client_ip(request)

    # Phase 277.B.050 — increment auth_login_total on all outcomes.
    def _inc_auth_login(status_label: str, tenant: str = "", method: str = "password") -> None:
        try:
            from hub.apps.observability.otel_metrics import auth_login_total
            auth_login_total.labels(
                status=status_label, tenant_id=tenant, auth_method=method,
            ).inc()
        except Exception:
            pass

    # ── IP-level rate limit ──────────────────────────────────────────────────
    if not _check_ip_rate_limit(client_ip):
        _inc_auth_login("rate_limited")
        return Response(
            {"detail": "Too many login attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    # ── Timing-safe user lookup (11.5) ───────────────────────────────────────
    # Always run check_password regardless of whether the email exists so that
    # timing measurements do not reveal whether an account is registered.
    try:
        user = (
            User.objects
            .using(_user_lookup_alias())
            .select_related("tenant")
            .prefetch_related("user_roles__role")
            .get(email=email)
        )
        password_ok = user.check_password(password)
    except User.DoesNotExist:
        from django.contrib.auth.hashers import check_password as _chk
        _chk(password, _DUMMY_HASH)  # consume similar CPU time
        _record_login_attempt(email, client_ip, success=False)
        _inc_auth_login("failure")
        raise ValidationError({"email": str(_("Invalid email or password"))})

    # ── Account-level lockout (11.5 + 277.B.066 progressive backoff) ────────────
    if not _check_account_lockout(email, user=user):
        _record_login_attempt(email, client_ip, success=False, user=user)
        _inc_auth_login("locked_out")
        return Response(
            {"detail": "Account temporarily locked. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not password_ok:
        _record_login_attempt(email, client_ip, success=False, user=user)
        _inc_auth_login("failure")
        raise ValidationError({"email": str(_("Invalid email or password"))})

    if not user.is_active():
        _record_login_attempt(email, client_ip, success=False, user=user)
        _inc_auth_login("locked_out")
        raise ValidationError({"email": str(_("User account is not active"))})

    # Phase 204: block password login after 24h grace if email not verified
    if (
        not user.email_verified
        and not user.is_platform_admin
        and timezone.now() > user.created_at + timedelta(hours=24)
    ):
        _record_login_attempt(email, client_ip, success=False, user=user)
        return Response(
            {
                # Spec (Phase 204): machine code + resend URL at top level
                "error": "EMAIL_NOT_VERIFIED",
                "resend_url": "/api/v1/auth/resend-verification/",
                "detail": "Please verify your email address before signing in.",
                "code": "EMAIL_NOT_VERIFIED",
                "details": {"resend_url": "/api/v1/auth/resend-verification/"},
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    _record_login_attempt(email, client_ip, success=True, user=user)
    _inc_auth_login("success", tenant=str(user.tenant_id) if user.tenant_id else "")

    # ── Issue tokens ─────────────────────────────────────────────────────────
    access_token = JWTTokenGenerator.generate_access_token(user)

    refresh_token_str = RefreshToken.generate_token()
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)
    RefreshToken.objects.create(
        user=user,
        # AUTH-007 — pin the tenant on the refresh row so subsequent
        # refresh-mints stay in the same tenant context the user logged
        # into. switch-tenant later supersedes this with the switched-to
        # tenant on a freshly-issued refresh token.
        tenant_id=user.tenant_id,
        token_hash=refresh_token_hash,
        expires_at=expires_at,
    )

    # Log audit event
    log_auth_operation(action="LOGIN", user=user, details={"method": "password"}, request=request)

    # Warm cache for tenant on login (async to avoid blocking login response)
    # Skip during tests: background threads deadlock with test transaction isolation.
    if user.tenant_id and not os.environ.get("TESTING"):
        try:
            import threading

            from hub.apps.core.caching.warming import warm_tenant_cache

            def warm_cache_async():
                try:
                    warm_tenant_cache(str(user.tenant_id))
                except Exception as exc:
                    logger.warning("cache_warm_failed", error=str(exc))

            threading.Thread(target=warm_cache_async, daemon=True).start()
        except Exception as exc:
            logger.warning("cache_warm_start_failed", error=str(exc))

    # ── Build response ────────────────────────────────────────────────────────
    use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)
    body = {
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
    }
    if not use_cookie_auth:
        # Legacy: tokens in response body for CLI, SDKs, SPAs using Authorization header
        body["access_token"] = access_token
        body["refresh_token"] = refresh_token_str

    response = Response(body, status=status.HTTP_200_OK)
    _set_refresh_cookie(response, refresh_token_str)

    if use_cookie_auth:
        # Phase 220.4: deliver access_token via httpOnly cookie only
        _set_access_cookie(response, access_token)

    return response


@extend_schema(
    request=RefreshTokenSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid refresh token"),
        401: OpenApiResponse(description="Replay detected — all sessions revoked"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def refresh_token(request):
    """
    Token refresh endpoint (11.1 + 11.2).

    POST /auth/refresh
    Cookie: refresh_token=<token>   (preferred — httpOnly)
    Body:  {"refresh_token": "<token>"}  (fallback for non-browser clients)

    Issues a new access token and rotates the refresh token (family rotation).
    If a revoked token is presented (replay / theft), the entire family is
    revoked and the client must re-authenticate (11.2).

    Phase F4 (glittery-herding-graham): IP rate-limited (REFRESH_IP_RATE_PER_MINUTE).
    Phase B2 (glittery-herding-graham): grace period for concurrent-tab replay detection.
    """
    # F4: rate limit before any DB work
    client_ip = _get_client_ip(request)
    if not _check_refresh_rate_limit(client_ip):
        return Response(
            {"detail": "Too many refresh attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    refresh_token_str = _get_refresh_token_str(request)
    if not refresh_token_str:
        raise ValidationError({"refresh_token": str(_("Refresh token is required"))})

    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)

    # SELECT FOR UPDATE to prevent concurrent rotation races (11.2)
    try:
        refresh_token_obj = (
            RefreshToken.objects.select_related("user")
            .select_for_update()
            .get(token_hash=refresh_token_hash)
        )
    except RefreshToken.DoesNotExist:
        raise ValidationError({"refresh_token": "Invalid refresh token"})

    # ── Replay detection with grace period (11.2 + B2 glittery-herding-graham) ─
    if refresh_token_obj.is_revoked():
        # A revoked token was presented. Before revoking the entire family,
        # check if a valid sibling was created within the grace window —
        # this indicates a concurrent-tab refresh (Tab A rotated, Tab B is
        # late) rather than a stolen-token replay attack.
        grace = getattr(settings, "REFRESH_TOKEN_GRACE_PERIOD_SECONDS", 5)
        cutoff = timezone.now() - timedelta(seconds=grace)

        latest_sibling = (
            RefreshToken.objects.select_for_update()
            .filter(
                family_id=refresh_token_obj.family_id,
                revoked_at__isnull=True,
                created_at__gte=cutoff,
            )
            .order_by("-sequence_number")
            .first()
        ) if grace > 0 else None

        if latest_sibling and latest_sibling.user.is_active():
            # Concurrent-tab scenario: rotate from the latest valid sibling.
            logger.info(
                "refresh_token_grace_period_applied",
                family_id=str(refresh_token_obj.family_id),
                stale_seq=refresh_token_obj.sequence_number,
                sibling_seq=latest_sibling.sequence_number,
                user_id=str(refresh_token_obj.user_id),
            )
            latest_sibling.revoke()

            # AUTH-007 — same tenant-pinning rule as the non-grace path.
            grace_tenant_id = (
                latest_sibling.tenant_id
                or refresh_token_obj.tenant_id
                or latest_sibling.user.tenant_id
            )

            new_token_str = RefreshToken.generate_token()
            new_token_hash = RefreshToken.hash_token(new_token_str)
            expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)
            RefreshToken.objects.create(
                user=latest_sibling.user,
                tenant_id=grace_tenant_id,
                token_hash=new_token_hash,
                expires_at=expires_at,
                family_id=refresh_token_obj.family_id,
                sequence_number=latest_sibling.sequence_number + 1,
            )

            access_token = JWTTokenGenerator.generate_access_token(
                latest_sibling.user,
                tenant_id=str(grace_tenant_id) if grace_tenant_id else None,
            )
            log_auth_operation(action="TOKEN_REFRESHED", user=latest_sibling.user, details={"grace_period": True}, request=request)

            use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)
            body = {"token_type": "Bearer", "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY}
            if not use_cookie_auth:
                body["access_token"] = access_token
            response = Response(body, status=status.HTTP_200_OK)
            _set_refresh_cookie(response, new_token_str)
            if use_cookie_auth:
                _set_access_cookie(response, access_token)
            return response

        # No recent valid sibling — genuine replay attack.
        refresh_token_obj.revoke_family()
        logger.warning(
            "refresh_token_replay_detected",
            family_id=str(refresh_token_obj.family_id),
            user_id=str(refresh_token_obj.user_id),
        )
        response = Response(
            {"detail": "Session invalidated. Please log in again."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        _clear_refresh_cookie(response)
        return response

    if refresh_token_obj.is_expired():
        # Return 401 (not 400) so the frontend's auth interceptor
        # recognises this as an auth failure and forces re-login,
        # instead of treating it as a validation error and leaving
        # the user stuck with UNKNOWN_ERROR on every page.
        response = Response(
            {"error": "Refresh token is expired", "code": "TOKEN_EXPIRED"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        _clear_refresh_cookie(response)
        return response

    user = refresh_token_obj.user
    if not user.is_active():
        response = Response(
            {"error": "User account is not active", "code": "USER_INACTIVE"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
        _clear_refresh_cookie(response)
        return response

    # ── Rotate: revoke old, issue new sibling in same family (11.2) ──────────
    refresh_token_obj.revoke()

    # AUTH-007 — carry the tenant from the old RT to the new sibling so a
    # refresh after switch-tenant stays in the switched-to tenant. Falls
    # back to ``user.tenant_id`` for refresh tokens issued before the
    # tenant_id column existed (post-migration backfill happens lazily).
    rotation_tenant_id = refresh_token_obj.tenant_id or user.tenant_id

    new_token_str = RefreshToken.generate_token()
    new_token_hash = RefreshToken.hash_token(new_token_str)
    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)
    RefreshToken.objects.create(
        user=user,
        tenant_id=rotation_tenant_id,
        token_hash=new_token_hash,
        expires_at=expires_at,
        family_id=refresh_token_obj.family_id,
        sequence_number=refresh_token_obj.sequence_number + 1,
    )

    access_token = JWTTokenGenerator.generate_access_token(
        user, tenant_id=str(rotation_tenant_id) if rotation_tenant_id else None
    )

    log_auth_operation(action="TOKEN_REFRESHED", user=user, details={}, request=request)

    use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)
    body = {
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
    }
    if not use_cookie_auth:
        # Legacy: return access token in response body for SPA clients
        body["access_token"] = access_token
    response = Response(body, status=status.HTTP_200_OK)
    _set_refresh_cookie(response, new_token_str)
    if use_cookie_auth:
        _set_access_cookie(response, access_token)
    return response


@extend_schema(
    request=inline_serializer(
        name="TokenRefreshRequest",
        fields={"refresh_token": serializers.CharField(required=False, allow_blank=True)},
    ),
    responses={200: OpenApiResponse(description="Logged out successfully")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """
    User logout endpoint.

    POST /auth/logout
    Body: {"refresh_token": "token_string"} (optional)

    When refresh_token is provided: revokes that specific token.
    When refresh_token is omitted: revokes all refresh tokens for the authenticated user (full session cleanup).
    Invalid/unknown token returns 200 with revoked_count=0 (idempotent).
    """
    # Read token from cookie first, then body (11.1)
    refresh_token_str = _get_refresh_token_str(request)

    revoked_count = 0
    if refresh_token_str:
        refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
        # B4 (glittery-herding-graham): use select_for_update to prevent race
        # between concurrent logout + refresh on the same token.
        with transaction.atomic():
            refresh_token_obj = (
                RefreshToken.objects.select_for_update()
                .filter(token_hash=refresh_token_hash, user_id=request.user.id)
                .first()
            )
            if refresh_token_obj:
                if not refresh_token_obj.revoked_at:
                    refresh_token_obj.revoked_at = timezone.now()
                    refresh_token_obj.save(update_fields=["revoked_at", "updated_at"])
                revoked_count = 1
    else:
        # No token found: revoke all sessions for this user (full session cleanup)
        revoked = RefreshToken.objects.filter(
            user_id=request.user.id, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
        revoked_count = revoked
        # Invalidate all existing access JWTs issued before logout-all.
        request.user.increment_token_version()

    log_auth_operation(
        action="LOGOUT",
        user=request.user,
        details={"revoked_tokens": revoked_count},
        request=request,
    )

    response = Response(
        {"message": "Logged out successfully", "revoked_sessions": revoked_count},
        status=status.HTTP_200_OK,
    )
    _clear_auth_cookies(response)
    return response


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: OpenApiResponse(description="Password reset email sent")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def password_reset_request(request):
    """
    Password reset request endpoint.

    POST /auth/password-reset
    Body: {"email": "user@example.com"}

    Generates password reset token and sends email.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]

    # Phase 87: Per-email rate limiting (5 requests/hour)
    if not _check_password_reset_rate_limit(email):
        return Response(
            {"detail": "Too many password reset requests. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        user = User.objects.using(_user_lookup_alias()).get(email=email)
    except User.DoesNotExist:
        # Don't reveal if user exists
        return Response(
            {"message": "If the email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )

    # Generate password reset token — store hash, send plaintext in email (11.3)
    plaintext_token = str(uuid.uuid4())
    user.password_reset_token = _sha256_hex(plaintext_token)
    user.password_reset_token_expires_at = timezone.now() + timedelta(hours=1)
    user.password_reset_token_used_at = None
    # The UPDATE on ``users`` runs through the default (request)
    # connection which carries the limited ``meshant_app`` role in
    # production. RLS WITH CHECK on ``users`` requires the
    # ``app.current_tenant_id`` GUC to match ``user.tenant_id``;
    # the request middleware does not set this on the unauthenticated
    # password-reset path, so we set it explicitly via
    # ``tenant_context`` for the duration of the save.
    from hub.apps.tenants.request_tenant import tenant_context as _tenant_context

    if user.tenant_id:
        with _tenant_context(user.tenant_id):
            user.save(update_fields=[
                "password_reset_token",
                "password_reset_token_expires_at",
                "password_reset_token_used_at",
            ])
    else:
        user.save(update_fields=[
            "password_reset_token",
            "password_reset_token_expires_at",
            "password_reset_token_used_at",
        ])

    # Send password reset email (pass plaintext token; DB stores hash — 11.3)
    from hub.apps.notifications.tasks import send_password_reset_email

    send_password_reset_email.delay(str(user.id), plaintext_token=plaintext_token)

    # Log audit event
    log_auth_operation(action="PASSWORD_RESET_REQUESTED", user=user, details={}, request=request)

    return Response(
        {"message": "If the email exists, a password reset link has been sent."},
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={200: OpenApiResponse(description="Password reset successful")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def password_reset_confirm(request):
    """
    Password reset confirmation endpoint.

    POST /auth/password-reset/confirm
    Body: {"token": "uuid", "new_password": "password"}

    Resets password and invalidates existing tokens.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    token = serializer.validated_data["token"]
    new_password = serializer.validated_data["new_password"]

    # Clients send the plaintext UUID; we hash it for the DB lookup (11.3)
    token_hash = _sha256_hex(str(token))

    # SELECT FOR UPDATE serialises concurrent reset-confirm requests that hold
    # the same valid token, so two parallel callers cannot both pass the
    # reuse check and race each other through the write phase.
    # Use the default connection (same as the enclosing
    # ``@transaction.atomic`` block) — ``using("admin")`` would
    # route the row-lock to an autocommit connection where
    # ``SELECT ... FOR UPDATE`` is invalid.
    try:
        user = (
            User.objects.select_for_update()
            .get(
                password_reset_token=token_hash,
                password_reset_token_expires_at__gt=timezone.now(),
                password_reset_token_used_at__isnull=True,
            )
        )
    except User.DoesNotExist:
        raise ValidationError({"token": "Invalid or expired password reset token"})

    # Phase 225.1 — reject reuse of the current password or any of the last
    # PASSWORD_HISTORY_WINDOW historical passwords. Check before mutating any
    # state so a rejected attempt leaves neither the user nor PasswordHistory
    # in a changed state (and the reset token remains usable for a retry).
    if user.check_password(new_password) or is_password_reused(user, new_password):
        raise ValidationError(
            {
                "new_password": (
                    "This password has been used recently. "
                    "Please choose a password you have not used before."
                )
            }
        )

    # Snapshot the *current* password hash into history before overwriting it
    # so the old password cannot be re-selected via the history check above on
    # a future reset. Idempotent — if the same exact hash is already on file
    # the service no-ops instead of raising IntegrityError.
    record_password_change(user)

    # Update password
    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    user.password_reset_token_used_at = timezone.now()

    # Increment token version to invalidate existing tokens
    user.increment_token_version()

    # Revoke all refresh tokens
    RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )

    user.save()

    # Record the new hash so it counts toward the window on subsequent resets.
    record_password_change(user)

    # Log audit event
    log_auth_operation(action="PASSWORD_RESET_COMPLETED", user=user, details={}, request=request)

    return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)


@extend_schema(
    request=EmailVerificationSerializer,
    responses={
        200: OpenApiResponse(description="Email verified"),
        400: OpenApiResponse(description="Invalid or expired token"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def verify_email(request):
    """
    POST /auth/verify-email/
    Body: {"token": "<signed token from email>"}

    Validates HMAC and 72-hour window from ``email_verification_sent_at``, then marks verified.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    token = serializer.validated_data["token"]

    ip_allowed, ip_cache_key, ip_window = _check_verify_email_ip_rate_limit(
        _get_verify_email_rate_limit_ip(request)
    )
    if not ip_allowed:
        response = Response(
            {"detail": "Too many verification attempts. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(
            _retry_after_seconds(
                cache_key=ip_cache_key,
                fallback_seconds=ip_window,
            )
        )
        return response

    token_allowed, token_cache_key, token_window = _check_verify_email_token_rate_limit(
        token
    )
    if not token_allowed:
        response = Response(
            {"detail": "Too many verification attempts. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(
            _retry_after_seconds(
                cache_key=token_cache_key,
                fallback_seconds=token_window,
            )
        )
        return response

    token_hash = _sha256_hex(token)
    try:
        # ``select_for_update`` MUST run on the same connection that
        # the enclosing ``@transaction.atomic`` opened the transaction
        # on. The default connection holds the request transaction;
        # ``using("admin")`` would route the SELECT to a SEPARATE
        # autocommit connection where ``SELECT ... FOR UPDATE`` is
        # invalid (Postgres + Django both reject it with
        # ``TransactionManagementError("select_for_update cannot be
        # used outside of a transaction")``). The previous
        # ``using("admin")`` was a leftover from an earlier RLS
        # workaround that no longer applies on the default
        # connection (the user record is tenant-scoped but readable
        # via the email_verification_token unique index regardless).
        user = (
            User.objects
            .select_for_update()
            .get(email_verification_token=token_hash)
        )
    except User.DoesNotExist:
        raise ValidationError({"token": "Invalid or expired verification token"})

    if not plaintext_valid_for_user(user, token):
        raise ValidationError({"token": "Invalid or expired verification token"})

    if user.email_verified:
        return Response({"message": "Email already verified."}, status=status.HTTP_200_OK)
    mark_user_email_verified(user)
    log_auth_operation(action="EMAIL_VERIFIED", user=user, details={}, request=request)
    return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)


@extend_schema(
    request=ResendEmailVerificationSerializer,
    responses={
        200: OpenApiResponse(description="If the account exists, email may be sent"),
        429: OpenApiResponse(description="Too many resend requests"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def resend_verification_email(request):
    """
    POST /auth/resend-verification/
    Body: {"email": "user@example.com"}

    Rate-limited to 3/hour per email. Does not reveal whether the address is registered.
    """
    serializer = ResendEmailVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data["email"]

    if not _check_email_verification_resend_rate_limit(email):
        return Response(
            {"detail": "Too many verification emails sent. Try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    generic = Response(
        {"message": "If the account exists, a verification email has been sent."},
        status=status.HTTP_200_OK,
    )

    try:
        user = User.objects.using(_user_lookup_alias()).get(email__iexact=email)
    except User.DoesNotExist:
        return generic

    if user.email_verified or user.is_platform_admin:
        return generic

    try:
        from django_rq import get_queue

        from hub.apps.notifications.tasks import send_email_verification_email

        verify_plaintext = issue_verification_token_plaintext(user)
        vq = get_queue("job_low")
        vq.enqueue(
            send_email_verification_email,
            str(user.id),
            plaintext_token=verify_plaintext,
        )
    except Exception as e:
        structlog.get_logger(__name__).warning(
            "resend_verification_email_failed", user_id=str(user.id), error=str(e), exc_info=True
        )

    log_auth_operation(
        action="EMAIL_VERIFICATION_RESENT", user=user, details={}, request=request
    )
    return generic


@extend_schema(
    request=InvitationAcceptanceSerializer,
    responses={
        200: TokenResponseSerializer,
        400: OpenApiResponse(description="Invalid invitation token"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def accept_invitation(request):
    """
    Invitation acceptance endpoint (11.3 + 11.7).

    POST /auth/accept-invitation
    Body: {"token": "<plaintext-uuid>", "password": "password"}

    Accepts invitation and activates user account.
    Wrapped in a transaction with SELECT FOR UPDATE to prevent concurrent
    double-acceptance of the same invitation token (11.7).
    Token stored as SHA-256 hash; plaintext travels only in the email link (11.3).
    Refresh token is delivered via httpOnly cookie (11.1).
    """
    serializer = InvitationAcceptanceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    plaintext_token = str(serializer.validated_data["token"])
    password = serializer.validated_data["password"]
    token_hash = _sha256_hex(plaintext_token)

    # SELECT FOR UPDATE prevents two concurrent requests accepting the same
    # invitation simultaneously (11.7). Default connection — see
    # rationale on the verify_email site for why ``using("admin")``
    # was wrong with ``select_for_update``.
    try:
        user = (
            User.objects.select_for_update()
            .get(
                invitation_token=token_hash,
                invitation_token_expires_at__gt=timezone.now(),
                invitation_token_used_at__isnull=True,
            )
        )
    except User.DoesNotExist:
        raise ValidationError({"token": "Invalid or expired invitation token"})

    # Activate user and set password
    user.status = UserStatus.ACTIVE
    user.set_password(password)
    user.invitation_token = None
    user.invitation_token_expires_at = None
    user.invitation_token_used_at = timezone.now()
    user.email_verified = True
    user.email_verified_at = timezone.now()
    user.save()

    # Generate tokens
    access_token = JWTTokenGenerator.generate_access_token(user)

    refresh_token_str = RefreshToken.generate_token()
    refresh_token_hash = RefreshToken.hash_token(refresh_token_str)
    expires_at = timezone.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRY)
    RefreshToken.objects.create(
        user=user, token_hash=refresh_token_hash, expires_at=expires_at
    )

    use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)
    body = {
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRY,
    }
    if not use_cookie_auth:
        body["access_token"] = access_token
        # B5 fix (glittery-dreaming-micali.md): body mode must include
        # refresh_token so the SPA can store and rotate it — matching
        # the login() response shape. Without this, the session dies
        # at access_token expiry with no way to refresh, forcing users
        # who accepted an invitation to re-login after 15 min (prod).
        body["refresh_token"] = refresh_token_str

    # Notify the newly activated user about successful onboarding
    try:
        from hub.apps.notifications.utils import create_user_notification

        create_user_notification(
            user=user,
            tenant=user.tenant,
            title="Welcome to Meshant",
            message=f"Your account has been activated. Welcome aboard, {user.display_name or user.email}!",
            notification_type="SUCCESS",
            category="USERS",
            resource_type="USER",
            resource_id=str(user.id),
        )
    except Exception:
        pass  # Notifications must never block invitation acceptance

    response = Response(body, status=status.HTTP_200_OK)
    _set_refresh_cookie(response, refresh_token_str)

    if use_cookie_auth:
        _set_access_cookie(response, access_token)

    return response


@extend_schema(
    request=RegisterSerializer,
    responses={
        201: RegisterResponseSerializer,
        400: OpenApiResponse(description="Validation error or email already exists"),
        429: OpenApiResponse(description="Rate limit exceeded"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@transaction.atomic
def register(request):
    """
    User registration endpoint.

    POST /auth/register
    Body: {"email": "user@example.com", "password": "SecurePass123", "name": "John Doe", "tenant_id": "uuid (optional)"}

    Creates a new user account with email, password, and name.
    Optionally associates user with a tenant.
    Publishes user.created event and sends welcome email (async).
    """
    logger = structlog.get_logger(__name__)
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    name = serializer.validated_data["name"]
    tenant_id = serializer.validated_data.get("tenant_id")

    # Get tenant: provided tenant_id, or create personal tenant when omitted (useronboardfix 1.2)
    tenant = None
    personal_tenant_created = False
    if tenant_id:
        from hub.apps.tenants.models import Tenant

        try:
            tenant = Tenant.objects.get(id=tenant_id)
            if not tenant.is_active():
                raise ValidationError({"tenant_id": "Tenant is not active"})
        except Tenant.DoesNotExist:
            raise ValidationError({"tenant_id": "Tenant not found"})
    elif getattr(settings, "PERSONAL_TENANT_ON_REGISTRATION", True):
        from hub.apps.core.responses import api_error_response, handle_service_exception
        from hub.apps.core.services.base import NotFoundError as ServiceNotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError
        from hub.apps.tenants.services import PersonalTenantService

        try:
            with transaction.atomic():
                tenant = PersonalTenantService().create_personal_tenant_for_user(
                    email=email, display_name=name
                )
            personal_tenant_created = True
        except ServiceValidationError as e:
            # Sanitize TENANT_CREATE_COLLISION to avoid leaking collision/slug info (useronboardfix 2.2.1)
            if getattr(e, "code", None) == "TENANT_CREATE_COLLISION":
                return api_error_response(
                    message="Registration failed. Please try again.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="REGISTRATION_FAILED",
                    details={},
                )
            return handle_service_exception(e)
        except ServiceNotFoundError as e:
            # PLAN_NOT_FOUND means the database was not seeded — this is an infra/operator error.
            # Never leak the internal hint ("Run seed_default_plans") to end users.
            if getattr(e, "code", None) == "PLAN_NOT_FOUND":
                logger.error(
                    "registration_plan_not_found",
                    email=email,
                    hint="Run 'python manage.py seed_default_plans' to create default plans",
                )
                return api_error_response(
                    message="Registration is temporarily unavailable. Please try again later or contact support.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    code="SERVICE_UNAVAILABLE",
                    details={},
                )
            return handle_service_exception(e)

    if tenant:
        from django.db import transaction as django_transaction

        from hub.apps.consent.gates import enforce_signup_consent
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        try:
            enforce_signup_consent(
                tenant=tenant,
                signup_consent=bool(serializer.validated_data.get("signup_consent")),
            )
        except ServiceValidationError as e:
            django_transaction.set_rollback(True)
            return handle_service_exception(e)

    # Check for duplicate email BEFORE create_user to surface 409 reliably.
    # (The conftest idempotent-create patch can swallow IntegrityError in test
    # environments, so pre-checking is the robust approach.)
    if User.objects.using(_user_lookup_alias()).filter(email__iexact=email).exists():
        from hub.apps.core.responses import api_error_response

        return api_error_response(
            message="An account with this email address already exists.",
            status_code=status.HTTP_409_CONFLICT,
            code="EMAIL_ALREADY_EXISTS",
            details={},
        )

    # Create user — IntegrityError fallback kept as safety net for race conditions.
    from django.db import IntegrityError

    from hub.apps.tenants.request_tenant import tenant_context

    try:
        # Use the DEFAULT connection (same as the enclosing
        # ``@transaction.atomic`` decorator and the tenant created
        # by ``PersonalTenantService.create_personal_tenant_for_user``).
        # Pre-fix this called ``db_manager("admin").create_user(...)``
        # which writes via a SEPARATE psycopg connection: the just-
        # created Tenant row is still uncommitted on the default
        # connection, so admin's FK lookup ``users.tenant_id ->
        # tenants.id`` fires PG ``foreign_key_violation`` (the row is
        # invisible across the connection boundary). The except
        # handler below mis-classified this as the email-uniqueness
        # case and returned ``409 EMAIL_ALREADY_EXISTS``, breaking
        # every test that registers a brand-new user under a
        # newly-created personal tenant.
        #
        # When ``RLS_USERS_ENABLED=True`` (production / RLS-bypass
        # tests) the WITH CHECK clause on ``users`` requires
        # ``tenant_id::text = current_setting('app.current_tenant_id')``.
        # The middleware tenant resolver doesn't run for the
        # unauthenticated register path, so set the GUC explicitly
        # via ``tenant_context`` for the duration of the INSERTs.
        # The same wrapping is applied to the membership/role/consent
        # writes below since user_tenant_memberships et al carry the
        # same RLS pattern.
        if tenant is not None:
            with tenant_context(tenant.id):
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    tenant=tenant,
                    display_name=name,
                    status=UserStatus.ACTIVE,
                )
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                tenant=None,
                display_name=name,
                status=UserStatus.ACTIVE,
            )
    except IntegrityError as exc:
        # Discriminate the FK-violation case (tenant not committed
        # yet — should never happen under the default connection,
        # but guard defensively) from the email-uniqueness race
        # case. Only the latter maps to the 409 EMAIL_ALREADY_EXISTS
        # response; the former is a genuine 500.
        from hub.apps.core.responses import api_error_response

        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg or "users_email" in msg:
            return api_error_response(
                message="An account with this email address already exists.",
                status_code=status.HTTP_409_CONFLICT,
                code="EMAIL_ALREADY_EXISTS",
                details={},
            )
        # Re-raise so the global error handler returns 500 with the
        # canonical INTERNAL_ERROR shape — masking a non-uniqueness
        # IntegrityError as a 409 hides real bugs.
        raise

    # Assign DATA_PROVIDER and DATA_CONSUMER when personal tenant created (useronboardfix 1.2)
    # bulk_create reduces N per-role round-trips to a single INSERT (13.9).
    # Tenant-scoped INSERTs run inside ``tenant_context`` so the
    # ``user_roles`` / ``user_tenant_memberships`` RLS WITH CHECK
    # clauses see the matching ``app.current_tenant_id`` GUC under
    # the production ``meshant_app`` role.
    if personal_tenant_created and tenant:
        from hub.apps.users.models import Role, UserRole

        with tenant_context(tenant.id):
            _roles = Role.objects.filter(
                tenant=tenant, name__in=["DATA_PROVIDER", "DATA_CONSUMER"]
            )
            UserRole.objects.bulk_create(
                [UserRole(user=user, tenant=tenant, role=r) for r in _roles],
                ignore_conflicts=True,
            )

    # Ensure UserTenantMembership exists so X-Tenant-Id validation passes (auth middleware)
    if tenant:
        from hub.apps.users.services import UserTenantMembershipService

        with tenant_context(tenant.id):
            UserTenantMembershipService().add_membership(
                user,
                tenant,
                actor_user=user,
                reason="user_registration",
            )

    if tenant:
        from django.db import transaction as django_transaction

        from hub.apps.consent.gates import grant_signup_consent_after_registration
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        try:
            with tenant_context(tenant.id):
                grant_signup_consent_after_registration(user=user, tenant=tenant)
        except ServiceValidationError as e:
            django_transaction.set_rollback(True)
            return handle_service_exception(e)

    # Phase 204: verification email (token persisted + async send)
    try:
        from django_rq import get_queue

        from hub.apps.notifications.tasks import send_email_verification_email

        verify_plaintext = issue_verification_token_plaintext(user)
        vq = get_queue("job_low")
        vq.enqueue(
            send_email_verification_email,
            str(user.id),
            plaintext_token=verify_plaintext,
        )
    except Exception as e:
        logger.warning(
            "verification_email_queue_failed", user_id=str(user.id), error=str(e), exc_info=True
        )

    # Publish user.created event
    try:
        event_id = publish_event(
            event_type="user.created",
            data={
                "user_id": str(user.id),
                "email": user.email,
                "tenant_id": str(tenant.id) if tenant else None,
                "created_at": user.created_at.isoformat(),
            },
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id),
            request_id=getattr(request, "id", None),
        )
    except Exception as e:
        # Log error but don't fail registration
        logger.error(
            "user_created_event_publish_failed", user_id=str(user.id), error=str(e), exc_info=True
        )

    # Send welcome email asynchronously (optional, don't fail if it fails)
    try:
        from django_rq import get_queue

        from hub.apps.notifications.models import EmailType
        from hub.apps.notifications.tasks import send_email_async

        # Build welcome email context
        context = {
            "user": user,
            "tenant": tenant,
            "login_url": f"{getattr(settings, 'EMAIL_BASE_URL', 'http://localhost:8000')}/login",
        }

        # Use USER_INVITATION email type (or create USER_WELCOME if it exists)
        email_type = EmailType.USER_INVITATION  # Use existing email type

        # Queue email task (non-blocking) - send_email_async is a regular function, not a task
        # We'll call it directly in a background job
        queue = get_queue("job_low")
        queue.enqueue(
            send_email_async,
            email_type=email_type,
            to_email=user.email,
            subject=f"Welcome to {tenant.name if tenant else getattr(settings, 'APP_NAME', 'Meshant')}",
            template_name="notifications/emails/user_welcome.html",
            context=context,
            tenant_id=str(tenant.id) if tenant else None,
            user_id=str(user.id),
        )
    except Exception as e:
        # Log error but don't fail registration
        logger.warning("welcome_email_queue_failed", user_id=str(user.id), error=str(e))

    # Log audit event
    log_auth_operation(
        action="REGISTER",
        user=user,
        details={"method": "email", "tenant_id": str(tenant.id) if tenant else None},
        request=request,
    )

    # Return response
    response_serializer = RegisterResponseSerializer(
        {
            "id": user.id,
            "email": user.email,
            "name": user.display_name,
            "tenant_id": tenant.id if tenant else None,
            "created_at": user.created_at,
        }
    )

    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


def _build_me_response(user):
    """Build /auth/me/ response data. Shared by GET and PATCH."""
    roles = []
    if hasattr(user, "user_roles"):
        roles = [ur.role.name for ur in user.user_roles.all()]
    if hasattr(user, "is_platform_admin") and user.is_platform_admin:
        if "PLATFORM_ADMIN" not in roles:
            roles = list(roles) + ["PLATFORM_ADMIN"]

    from .serializers import get_user_permissions

    permissions = get_user_permissions(user)
    last_login_at = None

    tenant_id = None
    try:
        if user.tenant:
            tenant_id = user.tenant.id
    except (AttributeError, ObjectDoesNotExist):
        tenant_id = None

    avatar = getattr(user, "avatar_url", None) or None
    preferences = getattr(user, "preferences", None)
    if preferences is None:
        preferences = {}

    feature_tenant_switch_enabled = getattr(
        settings, "FEATURE_TENANT_SWITCH_ENABLED", True
    )

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.display_name,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "roles": roles,
        "permissions": permissions,
        "created_at": user.created_at,
        "last_login_at": last_login_at,
        "avatar": avatar,
        "preferences": preferences,
        "feature_tenant_switch_enabled": feature_tenant_switch_enabled,
    }


@extend_schema(
    request=MePatchSerializer,
    responses={
        200: CurrentUserSerializer,
        400: OpenApiResponse(description="Validation error - invalid display_name, avatar URL, or preferences"),
        401: OpenApiResponse(description="Unauthorized - Invalid or missing token"),
    },
    tags=["Authentication"],
)
@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    """
    Get or update current authenticated user information.

    GET /auth/me — Returns user info (id, email, name, tenant_id, roles, permissions, avatar, preferences).
    PATCH /auth/me — Partial update of display_name, avatar, preferences.

    Performance target: < 200ms p95
    Caching: GET response may be cached for up to 5 minutes; PATCH invalidates cache.
    """
    user = request.user
    cache_key = f"user:me:{user.id}"

    if request.method == "GET":
        cached_response = cache.get(cache_key)
        if cached_response:
            return Response(cached_response, status=status.HTTP_200_OK)
        response_data = _build_me_response(user)
        cache.set(cache_key, response_data, 300)
        return Response(response_data, status=status.HTTP_200_OK)

    # PATCH
    serializer = MePatchSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    update_fields = []
    if "display_name" in serializer.validated_data:
        user.display_name = serializer.validated_data["display_name"]
        update_fields.append("display_name")
    if "avatar" in serializer.validated_data:
        user.avatar_url = serializer.validated_data["avatar"] or ""
        update_fields.append("avatar_url")
    if "preferences" in serializer.validated_data:
        user.preferences = serializer.validated_data["preferences"]
        update_fields.append("preferences")

    if update_fields:
        user.save(update_fields=update_fields + ["updated_at"])
        cache.delete(cache_key)

        log_auth_operation(
            action="PROFILE_UPDATE",
            user=user,
            details={"updated_fields": update_fields},
            request=request,
        )

    response_data = _build_me_response(user)
    return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    responses={
        200: inline_serializer(
            name="MeTenantsResponse",
            fields={
                "id": serializers.UUIDField(),
                "name": serializers.CharField(),
                "slug": serializers.CharField(),
            },
        ),
        401: OpenApiResponse(description="Unauthorized"),
    },
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me_tenants(request):
    """
    List tenants the current user has membership in.

    GET /auth/me/tenants/ — Returns list of { id, name, slug } from UserTenantMembership.
    """
    if not getattr(settings, "FEATURE_TENANT_SWITCH_ENABLED", True):
        return Response(
            {"detail": "Tenant switch feature is disabled"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from hub.apps.users.services import UserTenantMembershipService

    service = UserTenantMembershipService()
    tenants = service.list_tenants_for_user(request.user)
    data = [
        {"id": str(t.id), "name": t.name, "slug": t.slug}
        for t in tenants
    ]
    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    request=inline_serializer(
        name="SwitchTenantRequest",
        fields={"tenant_id": serializers.UUIDField(required=True)},
    ),
    responses={
        200: CurrentUserSerializer,
        400: OpenApiResponse(description="Missing or invalid tenant_id"),
        403: OpenApiResponse(description="User has no membership in tenant"),
        401: OpenApiResponse(description="Unauthorized"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def switch_tenant(request):
    """
    Switch active tenant context (validates membership, returns me summary).

    POST /auth/switch-tenant/ — Body { tenant_id }. Validates UserTenantMembership.
    Returns 200 + me summary (id, email, tenant_id, roles, etc.) for the switched context.
    """
    if not getattr(settings, "FEATURE_TENANT_SWITCH_ENABLED", True):
        return Response(
            {"detail": "Tenant switch feature is disabled"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from hub.apps.tenants.models import Tenant
    from hub.apps.users.services import UserTenantMembershipService

    tenant_id = request.data.get("tenant_id")
    if not tenant_id:
        return Response(
            {"detail": "tenant_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"detail": "tenant_id must be a valid UUID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    service = UserTenantMembershipService()
    if not service.validate_membership(request.user, str(tenant_uuid)):
        return Response(
            {"detail": "You do not have access to this tenant"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        tenant = Tenant.objects.get(id=tenant_uuid)
    except Tenant.DoesNotExist:
        return Response(
            {"detail": "Tenant not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    from_tenant_id = None
    if hasattr(request.user, "tenant_id") and request.user.tenant_id:
        from_tenant_id = str(request.user.tenant_id)

    log_auth_operation(
        action="TENANT_SWITCH",
        user=request.user,
        details={
            "from_tenant_id": from_tenant_id,
            "to_tenant_id": str(tenant.id),
        },
        request=request,
    )

    request.tenant_id = str(tenant.id)
    request.tenant = tenant

    # ── AUTH-007 — re-issue JWT pair pinned to the new tenant ────────────────
    # The pre-fix implementation only set ``request.tenant_id`` on the
    # response request object and returned 200. The frontend kept reusing
    # the OLD access token, whose ``tenant_id`` claim still pointed at the
    # user's home tenant, so the tenant scoping middleware silently snapped
    # subsequent requests back to the home tenant — a cross-tenant data
    # leak (AUTH-007 isolation guarantee). We now mint a fresh access
    # token AND a fresh refresh token in a NEW family, both carrying the
    # switched-to tenant in their claims/columns. The old refresh tokens
    # are NOT revoked on purpose: other sessions (other devices, other
    # tabs) may legitimately remain on their original tenants.
    new_access_token = JWTTokenGenerator.generate_access_token(
        request.user, tenant_id=str(tenant.id)
    )
    new_refresh_token_str = RefreshToken.generate_token()
    new_refresh_token_hash = RefreshToken.hash_token(new_refresh_token_str)
    new_refresh_expires_at = timezone.now() + timedelta(
        seconds=settings.JWT_REFRESH_TOKEN_EXPIRY
    )
    RefreshToken.objects.create(
        user=request.user,
        tenant_id=tenant.id,
        token_hash=new_refresh_token_hash,
        expires_at=new_refresh_expires_at,
    )

    response_data = _build_me_response(request.user)
    response_data["tenant_id"] = str(tenant.id)
    use_cookie_auth = getattr(settings, "USE_HTTPONLY_AUTH_COOKIES", False)
    response_data["token_type"] = "Bearer"
    response_data["expires_in"] = settings.JWT_ACCESS_TOKEN_EXPIRY
    if not use_cookie_auth:
        # Legacy body-bearing flow for CLI, SDKs, and SPAs that read
        # tokens out of the response. The frontend updates its auth
        # store from these fields after a successful switch.
        response_data["access_token"] = new_access_token
        response_data["refresh_token"] = new_refresh_token_str
    response = Response(response_data, status=status.HTTP_200_OK)
    _set_refresh_cookie(response, new_refresh_token_str)
    if use_cookie_auth:
        _set_access_cookie(response, new_access_token)
    return response


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for API key management.

    Tenant-scoped: users can only manage API keys in their tenant.
    Supports pagination via query parameters: page (default: 1) and page_size (default: 50, max: 100).
    """

    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    pagination_class = StandardPageNumberPagination

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all API keys
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return APIKey.objects.all()

        # Regular users can only see API keys in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return APIKey.objects.filter(tenant=user.tenant)

        return APIKey.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new API key.

        Returns the plaintext key (shown only once).
        """
        serializer = APIKeyCreateSerializer(
            data=request.data,
            context={
                "tenant": (
                    request.user.tenant
                    if hasattr(request.user, "tenant") and request.user.tenant
                    else None
                ),
                "user": request.user,
            },
        )
        serializer.is_valid(raise_exception=True)

        # Ensure tenant is set
        tenant = serializer.context["tenant"]
        if not tenant:
            return Response(
                {"error": "User must belong to a tenant to create API keys"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for creation (Phase 24.7.2)
        from hub.apps.auth.services import APIKeyService
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        service = APIKeyService(tenant_id=str(tenant.id), user_id=str(request.user.id))
        try:
            api_key, plaintext_key = service.create_api_key(
                tenant_id=str(tenant.id),
                user_id=str(request.user.id) if request.user else None,
                name=serializer.validated_data["name"],
                scopes=serializer.validated_data.get("scopes", []),
                expires_in_days=serializer.validated_data.get("expires_in_days"),
                rate_limit_per_hour=serializer.validated_data.get("rate_limit_per_hour"),
            )
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

        # Return response with plaintext key
        response_serializer = APIKeyResponseSerializer(
            {
                "id": api_key.id,
                "name": api_key.name,
                "api_key": plaintext_key,
                "scopes": api_key.scopes,
                "expires_at": api_key.expires_at,
                "created_at": api_key.created_at,
            }
        )

        # Audit event is already created in service layer

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """List API keys (tenant-scoped)"""
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Retrieve API key by ID"""
        return super().retrieve(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Revoke an API key via service layer (soft delete by setting expires_at to past).

        For now, we'll actually delete it. In production, you might want to soft delete.
        """
        api_key = self.get_object()
        tenant_id = str(api_key.tenant.id) if api_key.tenant else None
        if not tenant_id:
            return Response(
                {"error": "API key must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use service layer for deletion (Phase 24.7.2)
        from hub.apps.auth.services import APIKeyService
        from hub.apps.core.responses import handle_service_exception
        from hub.apps.core.services.base import NotFoundError

        service = APIKeyService(tenant_id=tenant_id, user_id=str(request.user.id))
        try:
            service.delete_api_key(
                api_key_id=str(api_key.id),
                tenant_id=tenant_id,
                actor_user_id=str(request.user.id),
            )
        except NotFoundError as e:
            return handle_service_exception(e)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    operation_id="list_active_sessions",
    summary="List active sessions",
    description=(
        "Returns all refresh tokens (sessions) for the authenticated user, "
        "ordered by most-recently-created first. Includes revoked and expired "
        "tokens for audit visibility. The current session is identified by "
        "comparing the presented Bearer token's refresh-token claim."
    ),
    responses={
        200: OpenApiResponse(
            response=RefreshTokenResponseSerializer(many=True),
            description="List of sessions for the authenticated user.",
        ),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_active_sessions(request):
    """
    List active sessions (refresh tokens) for the current user.

    GET /auth/sessions/

    Returns list of refresh tokens (sessions) for the authenticated user,
    ordered by most-recently-created first.  The ``is_current`` field
    identifies which session is currently sending the request.

    Phase 277.B.068 — enhanced with proper serialisation, current-session
    detection, and session metadata.
    """
    user = request.user
    refresh_tokens = RefreshToken.objects.filter(user=user).order_by("-created_at")

    # Determine the current session: if the request carries a refresh_token
    # in the body or if we can identify it from the auth header, mark it.
    current_token_hash = None
    # Try to extract the refresh token from the Authorization header
    # (the access token embeds a refresh_token_jti claim that maps to
    # a RefreshToken row).
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt
            from django.conf import settings
            token = auth_header.split(" ", 1)[1]
            # Decode without verification to read the refresh_token_jti claim
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            refresh_jti = payload.get("refresh_token_jti") or payload.get("jti")
            if refresh_jti:
                try:
                    rt = RefreshToken.objects.get(id=refresh_jti)
                    current_token_hash = rt.token_hash
                except RefreshToken.DoesNotExist:
                    pass
        except Exception:
            # Graceful fallback — mark the most recent valid token as current
            pass

    sessions = []
    most_recent_valid = None

    for token in refresh_tokens:
        is_valid = not token.is_revoked() and not token.is_expired()
        if is_valid and most_recent_valid is None:
            most_recent_valid = token.id

        is_current = (
            (current_token_hash is not None and token.token_hash == current_token_hash)
            or (current_token_hash is None and token.id == most_recent_valid)
        ) and is_valid

        sessions.append({
            "id": str(token.id),
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "revoked_at": token.revoked_at,
            "is_current": is_current,
            "is_valid": is_valid,
        })

    serializer = RefreshTokenResponseSerializer(data=sessions, many=True)
    serializer.is_valid(raise_exception=False)

    return Response(sessions, status=status.HTTP_200_OK)


@extend_schema(
    operation_id="end_all_other_sessions",
    summary="Revoke all other sessions",
    description=(
        "Revokes all refresh tokens for the authenticated user EXCEPT the "
        "current session.  The current session is identified via the same "
        "logic as the list endpoint.  This is a bulk-revoke for security "
        "incidents (e.g. password change, suspicious activity detected)."
    ),
    request=None,
    responses={
        200: OpenApiResponse(description="Other sessions revoked. Returns count."),
        401: OpenApiResponse(description="Authentication credentials were not provided."),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@transaction.atomic
def end_all_other_sessions(request):
    """
    Revoke all other sessions for the current user.

    POST /auth/sessions/end-all-others/

    Phase 277.B.068 — bulk session revocation for security incidents.
    Revokes every refresh token EXCEPT the one that sent the request.
    """
    user = request.user

    # Identify the current session using the same logic as list
    current_token_hash = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt
            token = auth_header.split(" ", 1)[1]
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            refresh_jti = payload.get("refresh_token_jti") or payload.get("jti")
            if refresh_jti:
                current_token_hash = RefreshToken.objects.get(
                    id=refresh_jti
                ).token_hash
        except Exception:
            pass

    # Revoke all valid tokens except the current one
    to_revoke = RefreshToken.objects.filter(
        user=user,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )

    if current_token_hash is not None:
        to_revoke = to_revoke.exclude(token_hash=current_token_hash)

    revoked_count = 0
    for rt in to_revoke:
        rt.revoked_at = timezone.now()
        rt.save(update_fields=["revoked_at", "updated_at"])
        revoked_count += 1

    log_auth_operation(
        action="ALL_OTHER_SESSIONS_REVOKED",
        user=request.user,
        details={"revoked_count": revoked_count},
        request=request,
    )

    return Response(
        {
            "message": f"Successfully revoked {revoked_count} other session(s).",
            "revoked_count": revoked_count,
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    responses={200: OpenApiResponse(description="Session revoked successfully")},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def revoke_session(request, session_id):
    """
    Revoke a specific session (refresh token).

    POST /auth/sessions/{session_id}/revoke/

    Revokes the specified refresh token (session).
    """
    try:
        refresh_token = RefreshToken.objects.get(id=session_id, user=request.user)
    except RefreshToken.DoesNotExist:
        raise NotFound("Session not found")

    # Revoke the token
    if not refresh_token.revoked_at:
        refresh_token.revoked_at = timezone.now()
        refresh_token.save(update_fields=["revoked_at", "updated_at"])

        # Log audit event
        log_auth_operation(
            action="SESSION_REVOKED",
            user=request.user,
            details={"session_id": str(session_id)},
            request=request,
        )

    return Response({"message": "Session revoked successfully"}, status=status.HTTP_200_OK)
