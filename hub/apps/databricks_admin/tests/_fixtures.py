"""Shared test constants for databricks_admin — real-host + W16 DNS guard.

Task 0.4 made workspace save() validate the host through the canonical
SSRFGuard (save-time DNS). Fixtures therefore use the REAL workspace host
from .env.test, and environments without public DNS follow the W16 policy:
local runs skip, CI raises (envpolicy.environment_guard).
"""

import json
import os
import socket
import urllib.parse

import pytest

from envpolicy import environment_guard

REAL_HOST = "dbc-6710eb95-8fe1.cloud.databricks.com"

# Host-side p313 runbook convention for the real-Redis suites (db 13 on the
# host's test Redis). In-container runs never use these — the compose stack
# exports REDIS_CACHE_URL and the resolver prefers it, exactly like the app
# settings (hub/settings.py:942).
REDIS_HOST_PORT = 63799
REDIS_HOST_DB = 13


def require_dns():
    """W16: raise in CI / skip locally when public DNS is unavailable."""
    try:
        socket.getaddrinfo(REAL_HOST, None)
    except OSError:
        environment_guard("public DNS unavailable — Databricks host resolution required")
        pytest.skip("public DNS unavailable — Databricks host resolution required")


def redis_endpoint(
    environ: dict[str, str] | None = None,
) -> tuple[str, int, int]:
    """Resolve the real-Redis endpoint the OBO/M2M-cache + budget suites
    run against.

    In-container batch runs export ``REDIS_CACHE_URL``
    (docker-compose.test.yml → ``redis://redis-cache-test:6379/0``) — the
    same env the app's settings consume. Host-side p313 runs have no
    ``REDIS_CACHE_URL`` and keep the legacy ``127.0.0.1:63799``/db-13
    probe. A reachable real Redis is a hard dependency of these suites;
    the W16 guard turns an unreachable endpoint into a loud skip (CI
    raises) instead of a silent pass.
    """
    env = os.environ if environ is None else environ
    url = env.get("REDIS_CACHE_URL") or env.get("REDIS_URL")
    if url:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        db = int((parsed.path or "/0").lstrip("/") or 0)
        return host, port, db
    return "127.0.0.1", REDIS_HOST_PORT, REDIS_HOST_DB


def redis_13_client():
    """Yield a flushed real-Redis client (fixture-ready generator).

    Every test module in the OBO/budget suites uses this ONE fixture —
    local copies that hardcode the host endpoint are the drift this
    generator eliminates (close-test-coverage-gaps 0.3).
    """
    import redis

    host, port, db = redis_endpoint()
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        environment_guard(f"real Redis unavailable at {host}:{port} — required")
        pytest.skip(f"real Redis unavailable at {host}:{port} — required")
    client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        client.close()


def load_fixture_steps(name: str) -> list[str]:
    """Resolve a named-payload fixture's ``steps`` to serialized response
    strings (the 3.10 round-trip convention): each step names a payload in
    the SAME file; a ``None`` payload serves an empty body (the compute
    API's mutation answers). The resolved list feeds
    ``RecordingHandler.json_script`` verbatim."""
    from hub.apps.databricks_admin.tests._uc_fixtures import load_fixture

    fixture = load_fixture(name)
    return [
        "" if fixture[step_name] is None else json.dumps(fixture[step_name])
        for step_name in fixture["steps"]
    ]
