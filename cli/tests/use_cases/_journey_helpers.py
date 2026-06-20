"""
Phase 279.H — shared journey test helpers.

Provides the common backend-availability check, CLI runner with auth
retry, and auth-error detection used by all persona journey test files.

Usage:
    from tests.use_cases._journey_helpers import (
        _cli, _is_auth_error, requires_backend,
        DATAHUB_BASE_URL, DATAHUB_CLI, DATAHUB_CLI_CMD, API_TOKEN,
    )
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess

import pytest

_API_TEST_PORT = os.environ.get("API_TEST_PORT", "8001")
DATAHUB_BASE_URL = os.environ.get(
    "DATAHUB_BASE_URL",
    os.environ.get("MESHANT_API_URL", f"http://localhost:{_API_TEST_PORT}/api/v1"),
)
DATAHUB_CLI = os.environ.get("DATAHUB_CLI", "python3 -m datahub_cli")
DATAHUB_CLI_CMD = shlex.split(DATAHUB_CLI)
API_TOKEN = os.environ.get("DATAHUB_API_TOKEN", "")


def _backend_available() -> bool:
    """Return True if the back-end is reachable.

    Uses the API root URL (strips ``/api/v1``).  Does NOT require auth —
    any response < 500 (including 401, 404) means the backend is alive.
    """
    root_url = DATAHUB_BASE_URL.rsplit("/api/v1", 1)[0].rstrip("/")
    import urllib.request

    try:
        req = urllib.request.Request(f"{root_url}/")
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except urllib.error.URLError:
        return False


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


def _provision_fresh_token() -> str:
    """Try persona provisioning with role fallback. Return api_key or ''.

    Uses persona_provisioning's disk cache (1h TTL, /auth/me/ validation,
    automatic re-login on invalidity).  Tries platform_admin first, then
    tenant_admin, then data_engineer, so a rate-limited primary persona
    doesn't block the test.
    """
    import sys as _sys

    _path = os.path.join(os.path.dirname(__file__), "..")
    if _path not in _sys.path:
        _sys.path.insert(0, _path)
    from _persona_provisioning import provision_persona as _pp

    for _role in ("platform_admin", "tenant_admin", "data_engineer"):
        try:
            creds = _pp(_role)
            if creds and creds.api_key:
                return creds.api_key
        except pytest.skip.Exception:
            continue  # this persona is rate-limited; try next
        except Exception:
            continue
    return ""


def _get_or_provision_token() -> str:
    """Return an API token for journey tests.

    Tries persona provisioning FIRST (self-healing disk cache with
    /auth/me/ validation and automatic re-login).  Falls back to the
    env-provided API_TOKEN only when all personas are unavailable
    (e.g. rate-limited after auth-lifecycle tests).
    """
    # 1. Try persona cache first — self-healing, auto re-login on invalidity.
    token = _provision_fresh_token()
    if token:
        return token

    # 2. Fall back to env token (Makefile pre-provisioning), validating
    #    it first — auth-lifecycle tests may have invalidated it.
    if API_TOKEN:
        import requests as _requests

        try:
            root = DATAHUB_BASE_URL.rstrip("/")
            resp = _requests.get(
                f"{root}/auth/me/",
                headers={"Authorization": f"Bearer {API_TOKEN}"},
                timeout=5,
            )
            if resp.status_code == 200:
                return API_TOKEN
        except _requests.RequestException:
            return API_TOKEN  # network error — best-effort

    return ""


def _cli(*args):
    """Run a CLI command with env configured, returning parsed JSON or str.

    Sets DATAHUB_API_TOKEN in the subprocess environment and also
    removes any stale access_token from the CLI config file.  The CLI's
    ``get_auth_headers()`` checks ``config.get_access_token()`` (config
    file) BEFORE ``config.get_api_key()`` (env var), so a stale config
    file entry would shadow the env-provided token.
    """
    token = _get_or_provision_token()
    env = {**os.environ, "DATAHUB_BASE_URL": DATAHUB_BASE_URL}
    if token:
        env["DATAHUB_API_TOKEN"] = token
        # Prevent a stale config-file access_token from shadowing the
        # env-provided token (get_auth_headers checks access_token first).
        from datahub_cli.config import CONFIG_FILE

        if CONFIG_FILE.exists():
            try:
                import yaml as _yaml

                cfg = _yaml.safe_load(CONFIG_FILE.read_text()) or {}
                if "access_token" in cfg:
                    del cfg["access_token"]
                    CONFIG_FILE.write_text(_yaml.dump(cfg))
            except Exception:
                pass
    return _run_cli(list(args), env)


def _run_cli(args: list, env: dict):
    """Run a CLI command via subprocess, retrying once with a fresh token on auth failure.

    Tries ``--format json`` first, retries without it if the option is
    unrecognised.  On auth failures, provisions a fresh platform_admin
    token via persona provisioning and retries once.

    Returns parsed JSON (dict/list) or raw string on parse failure.
    Fails the calling test (``pytest.fail``) when the CLI returns non-zero.
    """
    # Try with --format json first (most commands support it).
    cmd = DATAHUB_CLI_CMD + args + ["--format", "json"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60, env=env)
    # If --format is not recognised by this subcommand, retry without it.
    if result.returncode != 0 and "No such option" in result.stderr:
        cmd = DATAHUB_CLI_CMD + args
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=60, env=env
        )

    # If the CLI command failed with an auth error, the token may have
    # been invalidated by auth-lifecycle tests.  Provision a fresh token
    # and retry once.
    if result.returncode != 0 and _is_auth_error(result.stderr or ""):
        fresh = _provision_fresh_token()
        if fresh:
            env = {**env, "DATAHUB_API_TOKEN": fresh}
            cmd = DATAHUB_CLI_CMD + args + ["--format", "json"]
            result = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=60, env=env
            )
            if result.returncode != 0 and "No such option" in result.stderr:
                cmd = DATAHUB_CLI_CMD + args
                result = subprocess.run(
                    cmd, check=False, capture_output=True, text=True, timeout=60, env=env
                )

    if result.returncode != 0:
        pytest.fail(f"CLI command failed (rc={result.returncode}): {result.stderr[:200]}")
    # Parse JSON if possible, otherwise return raw string.
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout


def _is_auth_error(stderr: str) -> bool:
    """Return True if stderr indicates an authentication failure."""
    return any(
        phrase in stderr
        for phrase in (
            "Authentication failed",
            "Invalid API key",
            "Not authenticated",
            "Token has been invalidated",
            "run 'datahub login'",
        )
    )
