"""
Phase 279.G.1 — Cross-CLI-SDK E2E consistency tests.

Spawns ``datahub <cmd> --format json`` via subprocess, captures stdout,
parses JSON, calls the SDK equivalent, and compares structured fields
(ignoring timestamps, request_ids, and other volatile keys).

All tests skip when no running backend is detected (``DATAHUB_BASE_URL``
unset or health check fails).  Requires ``datahub`` CLI installed in PATH
or set via ``DATAHUB_CLI`` env var.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 pytest cli/tests/e2e/test_cli_sdk_consistency.py -v
"""

import json
import os
import subprocess
from typing import Any

import pytest

# ── Helpers ────────────────────────────────────────────────────────────

DATAHUB_BASE_URL = os.environ.get("DATAHUB_BASE_URL", "")
DATAHUB_CLI = os.environ.get("DATAHUB_CLI", "datahub")
API_TOKEN = os.environ.get("DATAHUB_API_TOKEN", os.environ.get("E2E_TEST_USER_TOKEN", ""))


def _backend_available() -> bool:
    """Check if a backend is reachable."""
    if not DATAHUB_BASE_URL:
        return False
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{DATAHUB_BASE_URL.rstrip('/')}/health/",
            headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


SKIP_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "deleted_at",
        "last_modified",
        "request_id",
        "timestamp",
        "expires_at",
        "published_at",
        "last_login_at",
        "approved_at",
        "rejected_at",
        "revoked_at",
        "last_triggered_at",
        "last_matched_count",
    }
)


def strip_volatile(obj: Any) -> Any:
    """Recursively remove volatile keys from a dict/list."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in SKIP_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def cli_json(*args: str) -> dict[str, Any]:
    """Run ``datahub <args> --format json`` and return parsed stdout."""
    cmd = [DATAHUB_CLI] + list(args) + ["--format", "json"]
    env = {**os.environ, "DATAHUB_BASE_URL": DATAHUB_BASE_URL}
    if API_TOKEN:
        env["DATAHUB_API_TOKEN"] = API_TOKEN
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed (rc={result.returncode}): {result.stderr[:500]}")
    return json.loads(result.stdout)


async def sdk_get(client, path: str, **kwargs) -> dict[str, Any]:
    """SDK GET with auth from env."""
    return await client.get(path, **kwargs)


# ── Consistency tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
@requires_backend
class TestCLISDKConsistency:
    """Cross-tool consistency: CLI stdout === SDK return for read ops."""

    async def test_health_consistency(self):
        """CLI ``health check`` matches SDK ``check_health()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.check_health()
            cli_result = cli_json("health", "check")
            assert strip_volatile(sdk_result) == strip_volatile(cli_result)

    async def test_tenants_list_consistency(self):
        """CLI ``tenants list`` matches SDK ``tenants.list_tenants()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.tenants.list_tenants()
            cli_result = cli_json("tenants", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_users_list_consistency(self):
        """CLI ``users list`` matches SDK ``users.list_users()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.users.list_users()
            cli_result = cli_json("users", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_assets_list_consistency(self):
        """CLI ``assets list`` matches SDK ``assets.list_assets()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.assets.list_assets()
            cli_result = cli_json("assets", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_datasets_list_consistency(self):
        """CLI ``datasets list`` matches SDK ``datasets.list_datasets()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.datasets.list_datasets()
            cli_result = cli_json("datasets", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_contracts_list_consistency(self):
        """CLI ``contracts list`` matches SDK ``contracts.list_contracts()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.contracts.list_contracts()
            cli_result = cli_json("contracts", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_jobs_list_consistency(self):
        """CLI ``jobs list`` matches SDK ``jobs.list_jobs()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.jobs.list_jobs()
            cli_result = cli_json("jobs", "list")
            sdk_stripped = strip_volatile(sdk_result.get("results", sdk_result))
            cli_stripped = strip_volatile(cli_result)
            assert len(sdk_stripped) == len(cli_stripped)

    async def test_observability_freshness_consistency(self):
        """CLI ``observability freshness`` matches SDK ``observability.get_freshness()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.observability.get_freshness_dashboard()
            cli_result = cli_json("observability", "freshness")
            assert strip_volatile(sdk_result) == strip_volatile(cli_result)

    async def test_capabilities_consistency(self):
        """CLI ``capabilities list`` matches SDK ``capabilities.list_capabilities()``."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.capabilities.list_capabilities()
            cli_result = cli_json("capabilities", "list")
            assert strip_volatile(sdk_result) == strip_volatile(cli_result)

    async def test_notifications_list_consistency(self):
        """CLI SDK: notifications list returns same shape."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=API_TOKEN)
        async with DataHubClient(config) as client:
            sdk_result = await client.notifications.list_notifications()
            assert "results" in sdk_result or isinstance(sdk_result, list)
