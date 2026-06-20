"""
Phase 279.G.2 — SDK-side CLI-SDK consistency mirror tests.

Same cross-tool comparisons as 279.G.1 but run from the SDK test suite
perspective.  Uses ``DATAHUB_BASE_URL`` and ``DATAHUB_API_TOKEN`` env vars.
All tests skip when no backend is reachable.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 pytest sdk/python/tests/use_cases/test_cli_sdk_consistency.py -v
"""

import json
import os
import subprocess

import pytest


def _find_datahub_cli() -> str | None:
    """Locate the ``datahub`` CLI binary, trying known venv paths first.

    The test CWD is ``sdk/python/``, so relative paths are resolved from
    there.  We also walk up to the repo root and try common venv locations
    relative to it, which covers both local dev and CI setups.

    Returns the path to the CLI binary, or None if not found.
    """
    import shutil
    from pathlib import Path

    candidates: list[str] = []
    env_cli = os.environ.get("DATAHUB_CLI", "")
    if env_cli:
        candidates.append(env_cli)

    # Paths relative to CWD (sdk/python/)
    candidates.extend(
        [
            "datahub",
            ".venv/bin/datahub",
            "venv/bin/datahub",
            "cli/venv/bin/datahub",
        ]
    )

    # Walk up to find the repo root (5 levels from this file:
    # use_cases → tests → python → sdk → repo_root), then try known
    # venv locations relative to it.
    repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    candidates.extend(
        [
            str(repo_root / ".venv/bin/datahub"),
            str(repo_root / "venv/bin/datahub"),
            str(repo_root / "cli/venv/bin/datahub"),
            str(repo_root / "venv-sdk-cli-test/bin/datahub"),
        ]
    )

    for c in candidates:
        if shutil.which(c) or os.path.isfile(c):
            return c
    return None


def _get_base_url() -> str:
    return os.environ.get(
        "DATAHUB_BASE_URL",
        f"http://localhost:{os.environ.get('API_TEST_PORT', '8001')}/api/v1",
    )


def _get_api_token() -> str:
    return (
        os.environ.get("DATAHUB_API_TOKEN")
        or os.environ.get("E2E_TEST_USER_TOKEN")
        or os.environ.get("TEST_API_KEY")
        or os.environ.get("DATAHUB_API_KEY", "")
    )


DATAHUB_BASE_URL = _get_base_url()
DATAHUB_CLI = _find_datahub_cli()

requires_cli = pytest.mark.skipif(
    DATAHUB_CLI is None,
    reason="CLI binary 'datahub' not found — install with 'pip install -e cli/' or set DATAHUB_CLI env var",
)


def _api_token() -> str:
    """Lazy API token lookup — avoids module-load ordering issues."""
    return _get_api_token()


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


def _backend_available():
    from tests.conftest import is_api_available

    return is_api_available()


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


def strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in SKIP_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def cli_json(*args):
    cmd = [DATAHUB_CLI] + list(args) + ["--format", "json"]
    token = _api_token()
    env = {**os.environ, "DATAHUB_BASE_URL": DATAHUB_BASE_URL}
    if token:
        env["DATAHUB_API_TOKEN"] = token
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed (rc={result.returncode}): {result.stderr[:500]}")
    return json.loads(result.stdout)


@pytest.mark.asyncio
@requires_backend
class TestSDKCLIConsistency:
    """SDK → CLI consistency: SDK output matches CLI stdout for read ops."""

    @requires_cli
    async def test_sdk_health_matches_cli(self):
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            sdk = await client.check_health()
            cli = cli_json("health", "check")
            assert strip_volatile(sdk) == strip_volatile(cli)

    @requires_cli
    async def test_sdk_assets_count_matches_cli(self):
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            sdk = await client.assets.list_assets()
            cli = cli_json("assets", "list")
            sdk_count = len(sdk.get("results", sdk)) if isinstance(sdk, dict) else len(sdk)
            cli_count = len(cli) if isinstance(cli, list) else len(cli.get("results", cli))
            assert sdk_count == cli_count

    @requires_cli
    async def test_sdk_datasets_count_matches_cli(self):
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            sdk = await client.datasets.list_datasets()
            cli = cli_json("datasets", "list")
            sdk_count = len(sdk.get("results", sdk)) if isinstance(sdk, dict) else len(sdk)
            cli_count = len(cli) if isinstance(cli, list) else len(cli.get("results", cli))
            assert sdk_count == cli_count

    @requires_cli
    async def test_sdk_tenants_count_matches_cli(self):
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            sdk = await client.tenants.list_tenants()
            cli = cli_json("tenants", "list")
            sdk_count = len(sdk.get("results", sdk)) if isinstance(sdk, dict) else len(sdk)
            cli_count = len(cli) if isinstance(cli, list) else len(cli.get("results", cli))
            assert sdk_count == cli_count

    @requires_cli
    async def test_sdk_users_count_matches_cli(self):
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            sdk = await client.users.list_users()
            cli = cli_json("users", "list")
            sdk_count = len(sdk.get("results", sdk)) if isinstance(sdk, dict) else len(sdk)
            cli_count = len(cli) if isinstance(cli, list) else len(cli.get("results", cli))
            assert sdk_count == cli_count

    async def test_sdk_capabilities_shape(self):
        """SDK capabilities.list_capabilities() returns a dict with known keys."""
        from datahub_interoperability import DataHubClient, DataHubClientConfig

        config = DataHubClientConfig(base_url=DATAHUB_BASE_URL, api_token=_api_token())
        async with DataHubClient(config) as client:
            caps = await client.capabilities.list_capabilities()
            assert isinstance(caps, dict)
            # At minimum, we expect some capability keys to be present
            assert len(caps) > 0

    async def test_sdk_notifications_module_imports(self):
        """All Phase 5 modules import cleanly."""
        from datahub_interoperability import (
            FeatureNotEnabledError,
            NotificationAPI,
        )

        assert NotificationAPI is not None
        assert FeatureNotEnabledError is not None
