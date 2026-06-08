"""
Phase 216.1.3 — persona provisioning helper.

Uses the pre-seeded E2E accounts on staging (created by
``manage.py ensure_e2e_user_roles``) rather than fabricating new users.
Each D145 persona role maps to a specific seeded account.

Cache key is ``(role, tenant_slug, xdist_worker_id)`` so parallel
xdist workers never collide.

This file is byte-identical in ``cli/tests/`` and ``sdk/python/tests/``.
A drift test (``cli/tests/test_persona_provisioning_sync.py``) enforces
this by ast-parsing both source files and comparing function bodies.

Cleanup is hooked into ``pytest_sessionfinish`` via
``cleanup_registry.register_persona_teardown``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import filelock
import requests

logger = logging.getLogger(__name__)


class _PersonaRateLimited(Exception):
    """Raised when persona login is rate-limited despite retries.

    ``provision_persona`` catches this and converts it to
    ``pytest.skip`` so the calling test is skipped rather than failed.
    """


class _PersonaInfrastructureError(Exception):
    """Raised when persona login fails due to transient infrastructure errors.

    This covers connection errors (DNS, network) and 5xx responses
    (Redis down, DB failover) that persist after retries.
    ``provision_persona`` catches this and converts it to
    ``pytest.skip`` so the calling test is skipped rather than failed.
    """


@dataclass(frozen=True)
class PersonaCredentials:
    """Credentials returned by ``provision_persona``."""
    api_key: str
    user_id: str
    tenant_id: str
    refresh_token: str
    role: str


# ---------------------------------------------------------------------------
# Pre-seeded E2E user mapping (must match ensure_e2e_user_roles.py)
# ---------------------------------------------------------------------------

_SEEDED_PASSWORD = "TestPass123"

# Maps D145 persona role → seeded e2e email.
# When multiple personas map to the same account, they share credentials
# (the account has sufficient permissions for all mapped roles).
_ROLE_TO_SEEDED_EMAIL: dict[str, str] = {
    "visitor":                 "",  # no login — unauthenticated
    "auditor":                 "e2e_auditor@example.com",
    "community_manager":       "e2e_test@example.com",
    "compliance_officer":      "e2e_cpo@example.com",
    "data_analyst":            "e2e_consumer@example.com",
    "data_consumer":           "e2e_consumer@example.com",
    "data_engineer":           "e2e_test@example.com",
    "data_mesh_domain_owner":  "e2e_dmo@example.com",
    "data_product_owner":      "e2e_test@example.com",
    "data_scientist":          "e2e_test@example.com",
    "external_developer":      "e2e_developer@example.com",
    "platform_admin":          "e2e_platform@example.com",
    "tenant_admin":            "e2e_admin@example.com",
}

# Maps tenant_slug → dedicated seeded e2e email for cross-tenant tests.
# These users are created by ``ensure_e2e_user_roles`` in their
# respective secondary tenants and have DATA_PROVIDER + DATA_CONSUMER roles.
_TENANT_SLUG_TO_SEEDED_EMAIL: dict[str, str] = {
    "tenant-iso": "e2e_iso@example.com",
    "tenant-b":   "e2e_tenant_b@example.com",
}


# ---------------------------------------------------------------------------
# Cache directory — ~/.cache/datahub-test-provisioning/
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(
    os.environ.get(
        "DATAHUB_TEST_CACHE_DIR",
        Path.home() / ".cache" / "datahub-test-provisioning",
    )
)


def _xdist_worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def _cache_key(role: str, tenant_slug: Optional[str]) -> str:
    """Deterministic cache key for a (role, tenant, worker) tuple."""
    worker = _xdist_worker_id()
    raw = f"{role}:{tenant_slug or 'default'}:{worker}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _lock_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.lock"


def _read_cache(key: str) -> Optional[PersonaCredentials]:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        # Expire after 1 hour
        if time.time() - data.get("_ts", 0) > 3600:
            path.unlink(missing_ok=True)
            return None
        creds = PersonaCredentials(
            api_key=data["api_key"],
            user_id=data["user_id"],
            tenant_id=data["tenant_id"],
            refresh_token=data["refresh_token"],
            role=data["role"],
        )
        # Validate cached token is still usable — a DB reset or token
        # version bump will invalidate all previously-issued tokens.
        if not _token_is_valid(creds):
            path.unlink(missing_ok=True)
            logger.info("Cached token for %s is invalid, evicting", creds.role)
            return None
        return creds
    except (json.JSONDecodeError, KeyError):
        path.unlink(missing_ok=True)
        return None


def _token_is_valid(creds: PersonaCredentials, max_validation_retries: int = 1) -> bool:
    """Return True if the cached token is still accepted by the API.

    Only validates JWT tokens (3+ dot-separated segments).  Short tokens
    (API keys, test stubs) are always considered valid — they don't
    carry expiry semantics that can change across cache epochs.

    On network errors the validation is retried once (with a 500 ms
    delay).  If both attempts fail, the token is considered *invalid*
    so the caller re-provisions — it is safer to evict a potentially
    valid cached token and re-login than to serve a stale one that
    causes downstream 401 / E2E-helper skips.
    """
    import time as _time

    if not creds.api_key:
        return False
    # Only validate JWTs — short tokens are API keys or test stubs.
    if "." not in creds.api_key or len(creds.api_key) < 50:
        return True
    base = _api_base_url()
    for attempt in range(max_validation_retries + 1):
        try:
            resp = requests.get(
                f"{base}/auth/me/",
                headers={"Authorization": f"Bearer {creds.api_key}"},
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            if attempt < max_validation_retries:
                _time.sleep(0.5)
                continue
            # Both attempts failed — evict to force fresh login.
            # A stale token causes E2E-helper skips; a fresh login
            # costs ~1 s.
            return False
    return False  # unreachable; satisfies static analysis


def _write_cache(key: str, creds: PersonaCredentials) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "api_key": creds.api_key,
        "user_id": creds.user_id,
        "tenant_id": creds.tenant_id,
        "refresh_token": creds.refresh_token,
        "role": creds.role,
        "_ts": time.time(),
    }
    _cache_path(key).write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def _api_base_url() -> str:
    port = os.environ.get("API_TEST_PORT", "8000")
    fallback = f"http://localhost:{port}/api/v1"
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", fallback),
    )


def _login_with_retry(email: str, password: str, max_retries: int = 5) -> requests.Response:
    """Login with exponential backoff on transient errors.

    Retries on three categories of transient errors:
    - 429 (rate-limit): honours ``Retry-After`` header, capped at 60 s/attempt.
    - 5xx (infrastructure): Redis, DB, or other backend failures — exponential
      backoff capped at 30 s.
    - Connection errors: DNS resolution failures, connection refused, timeouts —
      exponential backoff capped at 30 s.

    Non-transient errors (4xx auth failures other than 429) are returned
    immediately so callers can inspect and self-heal.

    Raises *PersonaInfrastructureError* when connection errors exhaust all
    retries (there is no response to return).
    """
    base = _api_base_url()
    last_resp: Optional[requests.Response] = None

    for attempt in range(max_retries + 1):
        # ---- connection-level errors: DNS, network, timeout ----
        try:
            resp = requests.post(
                f"{base}/auth/login/",
                json={"email": email, "password": password},
                timeout=15,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            wait = min(2 ** attempt, 30)
            logger.warning(
                "Login connection error for %s (attempt %d/%d): %s. "
                "Retrying in %ds...",
                email, attempt + 1, max_retries + 1, exc, wait,
            )
            if attempt < max_retries:
                time.sleep(wait)
                continue
            # Final attempt exhausted — raise so callers can skip/diagnose
            raise _PersonaInfrastructureError(
                f"Login for {email} failed after {max_retries + 1} attempts "
                f"due to connection errors (API may be down or unreachable): {exc}"
            ) from exc

        # ---- 429 rate-limit ----
        if resp.status_code == 429:
            body_text = resp.text[:300]

            # "Account temporarily locked" is a persistent lockout (Phase
            # 277.B.066 progressive backoff) — the window is at least 15
            # min and retrying within our loop is futile.  Raise immediately
            # so provision_persona converts it to pytest.skip.
            if "Account temporarily locked" in body_text:
                raise _PersonaRateLimited(
                    f"Persona login for {email} blocked: account is "
                    f"temporarily locked due to too many failed attempts. "
                    f"The lockout window should clear within 15-60 min."
                )

            retry_after = int(resp.headers.get("Retry-After", "15"))
            # Cap at 60 s per attempt to avoid hanging CI, but give the
            # rate-limit window a realistic chance to clear.
            wait = min(retry_after * (attempt + 1), 60)
            logger.info(
                "Login rate-limited (429), waiting %ds (attempt %d/%d)",
                wait, attempt + 1, max_retries + 1,
            )
            time.sleep(wait)
            last_resp = resp
            continue

        if resp.status_code == 200:
            return resp

        # ---- 5xx infrastructure errors: Redis, DB, etc. ----
        if resp.status_code >= 500:
            wait = min(2 ** attempt, 30)
            logger.warning(
                "Login infrastructure error %d for %s (attempt %d/%d): %s. "
                "Retrying in %ds...",
                resp.status_code, email, attempt + 1, max_retries + 1,
                resp.text[:200], wait,
            )
            if attempt < max_retries:
                time.sleep(wait)
                last_resp = resp
                continue
            # Final attempt exhausted — return last 5xx for callers to handle
            return resp

        # Non-transient error (4xx auth failures) — return immediately
        return resp

    # All retries exhausted — return last response for callers to handle
    if last_resp is not None:
        return last_resp
    return resp  # Should not be reached, but safe fallback


def _e2e_token() -> str:
    """Return the E2E shared secret for the X-E2E-Token header.

    Must match ``settings.E2E_TEST_SECRET`` inside the API container
    so the ``@require_e2e_token`` decorator on the ``/test/ensure-e2e-users/``
    endpoint accepts the request.

    Defaults to the local-dev value from ``.env.test``.  Override via
    the ``E2E_TEST_SECRET`` environment variable when targeting a
    staging or production deployment with a different secret.
    """
    return os.environ.get("E2E_TEST_SECRET", "e2e-test-secret-for-local-dev")


def _ensure_e2e_user(email: str, max_retries: int = 3) -> bool:
    """Call POST /test/ensure-e2e-users/ to create or reset an E2E user.

    This endpoint is gated by the ``@require_e2e_token`` decorator
    (Phase 226) — we send the ``X-E2E-Token`` header with the shared
    secret from ``_e2e_token()`` so the request is accepted.

    The endpoint is only available on test/staging environments.  It
    runs the same logic as ``manage.py ensure_e2e_user_roles`` for
    the given email.

    Retries on transient infrastructure errors (5xx, connection errors)
    with exponential backoff so self-heal survives a brief Redis/DNS blip.

    Returns True if the endpoint responded 200, False otherwise.
    """
    base = _api_base_url()
    headers = {"X-E2E-Token": _e2e_token()}

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                f"{base}/test/ensure-e2e-users/",
                json={"email": email},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                logger.info(
                    "ensure-e2e-users healed user %s: %s",
                    email, resp.text[:200],
                )
                return True

            # Retry on 5xx infrastructure errors (Redis, DB, etc.)
            if resp.status_code >= 500:
                wait = min(2 ** attempt, 15)
                logger.warning(
                    "ensure-e2e-users infrastructure error %d for %s "
                    "(attempt %d/%d): %s. Retrying in %ds...",
                    resp.status_code, email, attempt + 1, max_retries + 1,
                    resp.text[:200], wait,
                )
                if attempt < max_retries:
                    time.sleep(wait)
                    continue

            # 404 typically means the endpoint is gated: either
            # E2E_TEST_SECRET is unset in the API container or our
            # X-E2E-Token header did not match.  Log a clear diagnostic.
            if resp.status_code == 404:
                logger.warning(
                    "ensure-e2e-users for %s returned 404 (likely "
                    "E2E_TEST_SECRET mismatch or endpoint not enabled). "
                    "Set E2E_TEST_SECRET on the host to match the API "
                    "container value, or run 'manage.py ensure_e2e_user_roles' "
                    "directly inside the API container. "
                    "Response: %s",
                    email, resp.text[:200],
                )
                return False

            logger.warning(
                "ensure-e2e-users for %s returned %d: %s",
                email, resp.status_code, resp.text[:200],
            )
            return False

        except (requests.ConnectionError, requests.Timeout) as exc:
            wait = min(2 ** attempt, 15)
            logger.warning(
                "ensure-e2e-users connection error for %s (attempt %d/%d): %s. "
                "Retrying in %ds...",
                email, attempt + 1, max_retries + 1, exc, wait,
            )
            if attempt < max_retries:
                time.sleep(wait)
                continue
            logger.warning(
                "ensure-e2e-users request failed for %s after %d attempts: %s",
                email, max_retries + 1, exc,
            )
            return False

    return False


def _provision_via_login(role: str, tenant_slug: Optional[str]) -> PersonaCredentials:
    """Login as the pre-seeded E2E user for this persona role.

    Staging should already have these accounts via
    ``manage.py ensure_e2e_user_roles``.  If login fails (user
    missing or wrong password), the function self-heals by calling
    ``POST /test/ensure-e2e-users/`` to create or reset the account,
    then retries login once.

    When *tenant_slug* is provided, logs in as the dedicated user
    seeded in that secondary tenant (e.g. ``tenant-iso``,
    ``tenant-b``), so the returned ``tenant_id`` differs from the
    default-tenant credentials.

    Raises:
        _PersonaRateLimited: Rate-limit window not clearing.
        _PersonaInfrastructureError: Connection errors exhausted retries.
        RuntimeError: Auth failure (invalid credentials, email not verified)
            or persistent infrastructure error.
    """
    # Secondary tenant → use the tenant-specific seeded user
    if tenant_slug and tenant_slug in _TENANT_SLUG_TO_SEEDED_EMAIL:
        email = _TENANT_SLUG_TO_SEEDED_EMAIL[tenant_slug]
    else:
        email = _ROLE_TO_SEEDED_EMAIL.get(role)

    if not email:
        if role == "visitor":
            return PersonaCredentials(
                api_key="",
                user_id="visitor",
                tenant_id="",
                refresh_token="",
                role="visitor",
            )
        raise ValueError(
            f"Unknown persona role {role!r}. Known roles: "
            f"{sorted(_ROLE_TO_SEEDED_EMAIL.keys())}"
        )

    password = _SEEDED_PASSWORD

    login_resp = _login_with_retry(email, password)
    if login_resp.status_code == 429:
        # Rate-limited despite extended backoff — attempt to clear the
        # rate-limit state by self-healing the E2E user (resets any
        # account-level lockout / progressive-backoff counters) and
        # sleeping long enough for the IP-level rate window to clear.
        # Then retry login once with reduced retries.
        import time as _time2
        logger.warning(
            "Login rate-limited for %s (%s) after extended retries — "
            "attempting self-heal + cooldown before final retry",
            role, email,
        )
        _ensure_e2e_user(email)
        _time2.sleep(5)
        login_resp = _login_with_retry(email, password, max_retries=2)
        if login_resp.status_code == 429:
            raise _PersonaRateLimited(
                f"Persona login for {role} ({email}) rate-limited after "
                f"extended retries + self-heal + cooldown. The rate-limit "
                f"window should clear within 60 s."
            )

    # Self-heal: if login fails, try to create/reset the user via the
    # E2E helper endpoint, then retry login once.
    if login_resp.status_code != 200:
        body = login_resp.text[:300]
        is_invalid_creds = (
            "Invalid email or password" in body
            or "EMAIL_NOT_VERIFIED" in body
            or login_resp.status_code == 400
        )
        if is_invalid_creds:
            logger.info(
                "Login failed for %s (%s), attempting self-heal via "
                "ensure-e2e-users endpoint",
                role, email,
            )
            if _ensure_e2e_user(email):
                # Retry login after self-heal
                login_resp = _login_with_retry(email, password)

    if login_resp.status_code != 200:
        body = login_resp.text[:300]

        # ---- email not verified (persistent auth failure) ----
        if "EMAIL_NOT_VERIFIED" in body:
            raise RuntimeError(
                f"Persona login for {role} ({email}) blocked: "
                f"email not verified. Self-heal via "
                f"ensure-e2e-users also failed. "
                f"Fix: run 'python manage.py ensure_e2e_user_roles' "
                f"on the target environment."
            )

        # ---- infrastructure error persists after retries ----
        if login_resp.status_code >= 500:
            raise RuntimeError(
                f"Persona login for {role} ({email}) failed with "
                f"infrastructure error {login_resp.status_code}: {body}. "
                f"Self-heal via ensure-e2e-users was attempted. "
                f"The API returned a backend error — check whether "
                f"Redis (redis-cache-test), PostgreSQL, and other "
                f"infrastructure services are healthy inside the "
                f"Docker compose stack. "
                f"Run: docker compose -f docker-compose.test.yml ps"
            )

        # ---- auth failure (invalid credentials, missing user, etc.) ----
        # The self-heal endpoint was attempted but failed.  The most
        # common causes are:
        #   1. E2E users never seeded → run `manage.py ensure_e2e_user_roles`
        #   2. E2E_TEST_SECRET mismatch → the X-E2E-Token header sent by
        #      _ensure_e2e_user() didn't match the API container's secret.
        #      Set E2E_TEST_SECRET on the host to the same value as in
        #      .env.test (or whatever the API container uses).
        #   3. /test/ensure-e2e-users/ not registered → the API may not
        #      be a test/staging deployment.
        raise RuntimeError(
            f"Persona login for {role} ({email}) failed with "
            f"{login_resp.status_code}: {body}. "
            f"Self-heal via /test/ensure-e2e-users/ was attempted but "
            f"failed (check logs above for ensure-e2e-users diagnostics). "
            f"Alternatives: (1) run 'manage.py ensure_e2e_user_roles' "
            f"inside the API container, or (2) set E2E_TEST_SECRET on the "
            f"host to match the API container value and retry."
        )

    data = login_resp.json()
    return PersonaCredentials(
        api_key=data.get("access_token", ""),
        user_id=data.get("user_id", data.get("sub", "")),
        tenant_id=data.get("tenant_id", ""),
        refresh_token=data.get("refresh_token", ""),
        role=role,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def provision_persona(
    role: str,
    tenant_slug: Optional[str] = None,
) -> PersonaCredentials:
    """Provision a test persona with the given role.

    Uses the pre-seeded E2E accounts on staging. Idempotent and
    xdist-worker-aware. Uses a file-lock to prevent concurrent
    provisioning of the same (role, tenant, worker) triple.

    Args:
        role: One of the D145 persona role strings.
        tenant_slug: Optional tenant slug for cross-tenant tests.

    Returns:
        PersonaCredentials with api_key, user_id, tenant_id, refresh_token.
    """
    key = _cache_key(role, tenant_slug)

    # Fast path: read from cache
    cached = _read_cache(key)
    if cached is not None:
        return cached

    # Slow path: login with file-lock
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = filelock.FileLock(str(_lock_path(key)), timeout=60)

    with lock:
        # Re-check cache after acquiring lock
        cached = _read_cache(key)
        if cached is not None:
            return cached

        try:
            creds = _provision_via_login(role, tenant_slug)
        except (_PersonaRateLimited, _PersonaInfrastructureError, RuntimeError) as e:
            # ── Last-resort recovery ──────────────────────────────────
            # Before skipping, wait for transient conditions to clear
            # (rate-limit window, connection recovery, self-heal
            # propagation) and attempt one more direct login.  This
            # prevents intermittent skips when the test suite is under
            # heavy load.
            import time as _t
            logger.warning(
                "provision_persona(%s) failed with %s — attempting "
                "last-resort recovery after 5 s cooldown",
                role, type(e).__name__,
            )
            _t.sleep(5)
            try:
                # Purge any stale cache entries to force a clean path
                _cache_path(key).unlink(missing_ok=True)
                creds = _provision_via_login(role, tenant_slug)
                _write_cache(key, creds)
                from tests.fixtures.cleanup_registry import register_persona_teardown  # noqa: PHASE216-STATIC-ID
                register_persona_teardown(
                    f"persona:{role}:{_xdist_worker_id()}",
                    lambda: _cache_path(key).unlink(missing_ok=True),
                )
                return creds
            except Exception:
                # Last resort failed — skip gracefully
                import pytest  # noqa: PHASE216-STATIC-ID
                pytest.skip(str(e))
        _write_cache(key, creds)

        # Register teardown to clear cache at session end
        from tests.fixtures.cleanup_registry import register_persona_teardown  # noqa: PHASE216-STATIC-ID
        register_persona_teardown(
            f"persona:{role}:{_xdist_worker_id()}",
            lambda: _cache_path(key).unlink(missing_ok=True),
        )

        return creds
