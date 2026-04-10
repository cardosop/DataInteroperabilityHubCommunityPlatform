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
        return PersonaCredentials(
            api_key=data["api_key"],
            user_id=data["user_id"],
            tenant_id=data["tenant_id"],
            refresh_token=data["refresh_token"],
            role=data["role"],
        )
    except (json.JSONDecodeError, KeyError):
        path.unlink(missing_ok=True)
        return None


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
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", "http://localhost:8000/api/v1"),
    )


def _login_with_retry(email: str, password: str, max_retries: int = 3) -> requests.Response:
    """Login with exponential backoff on 429 rate-limit responses."""
    base = _api_base_url()
    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{base}/auth/login/",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "3"))
            wait = min(retry_after, 10) * (attempt + 1)
            logger.info(
                "Login rate-limited (429), waiting %ds (attempt %d/%d)",
                wait, attempt + 1, max_retries + 1,
            )
            time.sleep(wait)
            continue
        return resp
    return resp  # Return last 429 response if all retries exhausted


def _ensure_e2e_user(email: str) -> bool:
    """Call POST /test/ensure-e2e-users/ to create or reset an E2E user.

    This endpoint is AllowAny (no auth needed) and only available on
    test/staging environments.  It runs the same logic as
    ``manage.py ensure_e2e_user_roles`` for the given email.

    Returns True if the endpoint responded 200, False otherwise.
    """
    base = _api_base_url()
    try:
        resp = requests.post(
            f"{base}/test/ensure-e2e-users/",
            json={"email": email},
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info(
                "ensure-e2e-users healed user %s: %s",
                email, resp.text[:200],
            )
            return True
        logger.warning(
            "ensure-e2e-users for %s returned %d: %s",
            email, resp.status_code, resp.text[:200],
        )
    except requests.RequestException as exc:
        logger.warning("ensure-e2e-users request failed for %s: %s", email, exc)
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
        raise RuntimeError(
            f"Persona login for {role} ({email}) rate-limited after retries. "
            f"Wait a few minutes and retry."
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
        if "EMAIL_NOT_VERIFIED" in body:
            raise RuntimeError(
                f"Persona login for {role} ({email}) blocked: "
                f"email not verified. Self-heal via "
                f"ensure-e2e-users also failed. "
                f"Fix: run 'python manage.py ensure_e2e_user_roles' "
                f"on the target environment."
            )
        raise RuntimeError(
            f"Persona login for {role} ({email}) failed: "
            f"{login_resp.status_code} {body}. "
            f"Self-heal via ensure-e2e-users was attempted. "
            f"Was 'manage.py ensure_e2e_user_roles' run on staging?"
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

        creds = _provision_via_login(role, tenant_slug)
        _write_cache(key, creds)

        # Register teardown to clear cache at session end
        from tests.fixtures.cleanup_registry import register_persona_teardown
        register_persona_teardown(
            f"persona:{role}:{_xdist_worker_id()}",
            lambda: _cache_path(key).unlink(missing_ok=True),
        )

        return creds
