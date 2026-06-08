"""
Shared pytest fixtures for SDK integration tests.

Provides service health checks and common fixtures for ODH integration tests.

Skip helper conventions (Phase 279 post-cleanup):
-----------------------------------------------
- ``is_api_available()`` — canonical backend reachability check (port 8001).
- ``get_api_key()`` — canonical API-key retrieval with consistent messaging.
  Prefer these two helpers over ad-hoc requests/``os.environ`` checks so
  skip reasons stay consistent and CI dashboards can group them.
- ``requires_backend`` — ``pytest.mark.skipif`` marker for use-case / journey
  tests that use ``DATAHUB_BASE_URL`` + ``DATAHUB_API_TOKEN`` env vars.
"""
import warnings
import pytest
import requests
import subprocess
import time
import os

# Phase 216.X.3 — surface the cleanup_registry autouse fixture and the
# persona teardown plumbing to every test under sdk/python/tests/.
# Pytest only auto-discovers fixtures declared in conftest.py modules,
# so we re-export the fixture here. (F401 is intentional: the import
# IS the wiring.)
from tests.fixtures.cleanup_registry import (  # noqa: F401
    cleanup_registry,
    drain_persona_teardown_callbacks,
)

# ── Canonical skip-helpers (DRY — prefer these in new / updated tests) ──────

def default_api_base_url() -> str:
    """Return the default API base URL for health checks.

    Reads ``API_TEST_PORT`` and ``MESHANT_API_URL`` env vars so the
    test suite works against both the main dev stack (port 8000) and
    the test stack (port 8001).  When ``API_TEST_PORT`` is set (as in
    ``docker-compose.test.yml``) we use that port.  Defaults to 8001
    to match the ``docker-compose.test.yml`` port mapping.
    """
    url = os.environ.get("MESHANT_API_URL")
    if url:
        return url.rsplit("/api/", 1)[0] if "/api/" in url else url.rstrip("/")
    port = os.environ.get("API_TEST_PORT", "8001")
    return f"http://localhost:{port}"


def is_api_available(base_url: str = "", timeout: int = 5) -> bool:
    """Return True if the hub API is reachable at *base_url*.

    Uses the root ``/health/`` endpoint (not ``/api/v1/health/``) and
    ``status_code < 500`` so a 401/403/404 from a running server still
    counts as reachable.

    Emits a ``UserWarning`` when the check fails so the reason is
    visible in test output instead of being silently swallowed.
    """
    if not base_url:
        base_url = default_api_base_url()
    try:
        r = requests.get(f"{base_url.rstrip('/')}/health/", timeout=timeout)
        return r.status_code < 500
    except requests.exceptions.RequestException as exc:
        warnings.warn(
            f"API health check failed at {base_url.rstrip('/')}/health/: {exc!r}  "
            f"(Set API_TEST_PORT or MESHANT_API_URL if the API is on a different port.)"
        )
        return False


def get_api_key() -> str | None:
    """Return an API key from the environment, or auto-provision one.

    Checks ``TEST_API_KEY`` first, then ``DATAHUB_API_KEY``.  If neither
    is set and the API is reachable, auto-provisions a token by logging
    in with the pre-seeded E2E platform-admin credentials (available on
    all test/staging deployments).

    IMPORTANT: Tokens from env vars are validated before being returned.
    A stale/invalid token causes a fall-through to auto-provisioning so
    tests always receive a working credential.
    """
    key = os.environ.get("TEST_API_KEY") or os.environ.get("DATAHUB_API_KEY")
    if key and _token_valid(key):
        # Also mirror to DATAHUB_API_TOKEN so journey tests that read
        # the legacy var pick up the validated token.
        if not os.environ.get("DATAHUB_API_TOKEN"):
            os.environ["DATAHUB_API_TOKEN"] = key
        return key
    # Key missing, stale, or invalid — auto-provision a fresh one.
    return _auto_provision_api_key()


def _auto_provision_api_key() -> str | None:
    """Log in as the E2E platform admin and return an access token.

    Stores both the access token and refresh token in environment
    variables.  Subsequent calls validate the cached token via
    ``/auth/me/`` and refresh it transparently using the stored refresh
    token, so long-running test suites don't fail when the initial JWT
    expires (typically after 1 hour).
    """
    # Check cached token validity first
    cached = os.environ.get("_AUTO_PROVISIONED_API_KEY")
    if cached and _token_valid(cached):
        return cached
    # Token expired — try refresh if we have a refresh token
    refresh = os.environ.get("_AUTO_PROVISIONED_REFRESH_TOKEN")
    if refresh and is_api_available():
        refreshed = _try_refresh(refresh)
        if refreshed:
            return refreshed
    # Full login
    if not is_api_available():
        return None
    return _do_login()


def _token_valid(token: str) -> bool:
    """Lightweight check: is *token* still accepted by the API?"""
    try:
        resp = requests.get(
            f"{default_api_base_url()}/api/v1/auth/me/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return True  # assume valid if network is down


def _try_refresh(refresh_token: str) -> str | None:
    """Attempt to refresh the access token.  Returns None on failure."""
    try:
        resp = requests.post(
            f"{default_api_base_url()}/api/v1/auth/refresh/",
            json={"refresh_token": refresh_token},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            access = data.get("access_token", "")
            new_refresh = data.get("refresh_token", "")
            if access:
                os.environ["_AUTO_PROVISIONED_API_KEY"] = access
                os.environ["TEST_API_KEY"] = access
                os.environ["DATAHUB_API_KEY"] = access
                os.environ["DATAHUB_API_TOKEN"] = access
                if new_refresh:
                    os.environ["_AUTO_PROVISIONED_REFRESH_TOKEN"] = new_refresh
                return access
    except requests.RequestException:
        pass
    return None


def _do_login() -> str | None:
    """Perform a fresh login and cache both tokens."""
    try:
        resp = requests.post(
            f"{default_api_base_url()}/api/v1/auth/login/",
            json={"email": "e2e_platform@example.com", "password": "TestPass123"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            access = data.get("access_token", "")
            refresh = data.get("refresh_token", "")
            if access:
                os.environ["_AUTO_PROVISIONED_API_KEY"] = access
                os.environ["TEST_API_KEY"] = access
                os.environ["DATAHUB_API_KEY"] = access
                os.environ["DATAHUB_API_TOKEN"] = access
                if refresh:
                    os.environ["_AUTO_PROVISIONED_REFRESH_TOKEN"] = refresh
                return access
    except requests.RequestException:
        pass
    return None


def require_api_key_or_skip() -> str:
    """Return a usable API key, or call ``pytest.skip`` with a canonical message."""
    key = get_api_key()
    if not key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY "
            "environment variable, or ensure Docker Compose services are running."
        )
    return key


def require_api_or_skip() -> None:
    """Skip the current test if the hub API is not reachable."""
    if not is_api_available():
        pytest.skip(
            "API service is not available. "
            "Ensure Docker Compose services are running."
        )


def pytest_sessionstart(session):  # noqa: ARG001
    """Prepare the test environment on session start.

    1. Purge stale persona cache entries (JSON + lock files).  After a
       database reset, all previously-issued JWT tokens are invalid.
    2. Purge auto-provisioned token state so every ``make`` invocation
       starts from a clean slate — stale cached JWTs whose token_version
       has been bumped by persona provisioning are discarded.
    3. Auto-provision a fresh API key if the backend is reachable, so
       tests that read ``TEST_API_KEY`` / ``DATAHUB_API_KEY`` from the
       environment pick up a valid token without manual setup.
    """
    # ── 1. Purge persona caches ──────────────────────────────────────
    import glob as _glob
    from tests._persona_provisioning import _CACHE_DIR as _cache_dir
    if _cache_dir.exists():
        for f in _glob.glob(str(_cache_dir / "*.json")):
            try:
                from pathlib import Path
                Path(f).unlink()
            except OSError:
                pass
        # Also purge stale .lock files left behind by crashed runs.
        # A stale lock blocks all subsequent persona provisioning for
        # the same role and causes ``filelock._error.Timeout`` failures.
        for f in _glob.glob(str(_cache_dir / "*.lock")):
            try:
                from pathlib import Path
                Path(f).unlink()
            except OSError:
                pass

    # ── 2. Purge auto-provisioning state ─────────────────────────────
    # Each session must perform a fresh login so the token's
    # authz_version matches the current user.token_version in the DB.
    # Reusing a cached token from a prior session (or from env vars)
    # risks TOKEN_INVALIDATED errors when persona provisioning bumps
    # token_version via ensure-e2e-users self-heal.
    for _key in (
        "_AUTO_PROVISIONED_API_KEY",
        "_AUTO_PROVISIONED_REFRESH_TOKEN",
    ):
        os.environ.pop(_key, None)

    # ── 3. Auto-provision a fresh API key ────────────────────────────
    # Must run BEFORE feature-flag enablement because the REST API
    # call in _enable_admin_tenant_feature_flags needs a valid token.
    get_api_key()

    # ── 4. Enable feature flags on the platform-admin tenant ──────────
    # Uses the auto-provisioned admin token to PATCH the admin tenant
    # via the REST API (no Docker / Django shell dependency).
    try:
        _enable_admin_tenant_feature_flags()
    except Exception:
        pass

    # Reset ODH circuit breaker at session start so integration tests
    # don't get blocked by a stale OPEN breaker from a previous run.
    try:
        _reset_odh_circuit_breaker()
    except Exception:
        pass  # docker / redis not available — tests will handle gracefully


def _enable_admin_tenant_feature_flags() -> None:
    """Enable feature flags on the auto-provisioned admin tenant.

    Uses the REST API (PATCH /api/v1/tenants/{id}/) with the
    auto-provisioned admin token.  This avoids depending on Docker /
    Django shell availability.
    """
    import requests as _requests

    # The auto-provisioned key must already be in the environment
    # (pytest_sessionstart runs get_api_key() first).
    token = os.environ.get("_AUTO_PROVISIONED_API_KEY")
    if not token:
        return

    base = default_api_base_url()
    try:
        # Resolve the admin user's tenant id via /auth/me/
        me = _requests.get(
            f"{base}/api/v1/auth/me/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if me.status_code != 200:
            return
        tenant_id = (me.json() or {}).get("tenant_id")
        if not tenant_id:
            return

        # Enable the three feature flags used by batch 9-2-f tests
        resp = _requests.patch(
            f"{base}/api/v1/tenants/{tenant_id}/",
            json={
                "baas_enabled": True,
                "marketplace_integrations_enabled": True,
                "ml_enabled": True,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code in (200, 202):
            # Invalidate the cached token so the next get_api_key() call
            # returns a fresh one that includes any authz changes.
            os.environ.pop("_AUTO_PROVISIONED_API_KEY", None)
    except Exception:
        pass  # best-effort; tests that need the flags create their own tenants


def _reset_odh_circuit_breaker() -> None:
    """Delete ODH inference scheduler circuit breaker keys from Redis."""
    import subprocess as _sp

    _sp.run(
        [
            "docker", "exec", "hub-test-redis-cache", "redis-cli",
            "DEL",
            "circuit_breaker:odh-inference-scheduler:state",
            "circuit_breaker:odh-inference-scheduler:failure_count",
            "circuit_breaker:odh-inference-scheduler:success_count",
            "circuit_breaker:odh-inference-scheduler:opened_at",
        ],
        capture_output=True,
        timeout=5,
        check=False,
    )


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Phase 216.X.3 layer 2 — drain pending persona teardown callbacks.

    See ``cli/tests/conftest.py`` for the rationale; this is the SDK
    mirror of the same hook.
    """
    failures = drain_persona_teardown_callbacks()
    if failures:
        if exitstatus == 0:
            session.exitstatus = 1
        for name, exc in failures:
            session.config.get_terminal_writer().line(
                f"[Phase 216 persona teardown] {name}: {exc!r}"
            )


def check_service_health(service_name: str, port: int, health_path: str = "/health", max_wait: int = 30) -> bool:
    """
    Check if a service is healthy.

    Args:
        service_name: Name of the service (for logging)
        port: Port number to check
        health_path: Health check endpoint path
        max_wait: Maximum time to wait in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    for attempt in range(max_wait):
        try:
            response = requests.get(f"http://localhost:{port}{health_path}", timeout=2)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            if attempt < max_wait - 1:
                time.sleep(1)
    return False


def start_service_if_needed(service_name: str, port: int, health_path: str = "/health") -> bool:
    """
    Start Docker Compose service if not running.

    Args:
        service_name: Docker Compose service name
        port: Service port number
        health_path: Health check endpoint path

    Returns:
        True if service is available, False otherwise
    """
    # Check if service is already running
    if check_service_health(service_name, port, health_path, max_wait=2):
        return True

    # Try to start the service
    try:
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        result = subprocess.run(
            ['docker', 'compose', 'up', '-d', service_name],
            capture_output=True,
            timeout=60,
            cwd=project_dir
        )
        if result.returncode == 0:
            # Wait for service to be healthy
            return check_service_health(service_name, port, health_path, max_wait=60)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return False


@pytest.fixture(scope="session")
def odh_inference_scheduler_available():
    """
    Ensure ODH Inference Scheduler service is available.

    This fixture checks if the service is running and attempts to start it if needed.
    Tests that require this service should use this fixture.
    """
    service_name = "odh-inference-scheduler"
    port = 8097

    if not start_service_if_needed(service_name, port):
        pytest.skip(
            f"ODH Inference Scheduler service not available on port {port}. "
            f"Start with: docker compose up -d {service_name}"
        )
    return True


@pytest.fixture(scope="session")
def odh_training_operator_available():
    """
    Ensure ODH Training Operator service is available.

    This fixture checks if the service is running and attempts to start it if needed.
    Tests that require this service should use this fixture.
    """
    service_name = "odh-training-operator"
    port = 8096

    if not start_service_if_needed(service_name, port):
        pytest.skip(
            f"ODH Training Operator service not available on port {port}. "
            f"Start with: docker compose up -d {service_name}"
        )
    return True
