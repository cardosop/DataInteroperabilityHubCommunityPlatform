"""
Pytest fixtures for CLI e2e tests.

Mirrors ``tests/integration/conftest.py``: auto-skips e2e tests when no live
Meshant API is reachable. e2e tests run a real CLI against a real backend
and have no business failing on dev boxes that don't run docker compose.
Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass.
"""

import os

import pytest
import requests
from click.testing import CliRunner
from datahub_cli.config import Config

_api_test_port = os.environ.get("API_TEST_PORT", "8000")
_DEFAULT_API_BASE = f"http://localhost:{_api_test_port}"


def _api_is_reachable(url: str) -> bool:
    try:
        response = requests.get(url, timeout=2)
    except requests.RequestException:
        return False
    return response.status_code < 500


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    if os.environ.get("MESHANT_FORCE_INTEGRATION") == "1":
        return
    api_url = os.environ.get(
        "MESHANT_API_URL",
        f"{_DEFAULT_API_BASE}/api/v1",
    )
    api_root = api_url.rsplit("/api/v1", 1)[0] or api_url
    if _api_is_reachable(api_root):
        return
    skip_marker = pytest.mark.skip(
        reason=(
            f"Meshant API not reachable at {api_root}. CLI e2e tests "
            "require a live backend; start docker compose or set "
            "MESHANT_FORCE_INTEGRATION=1 to override."
        )
    )
    for item in items:
        fspath = str(item.fspath)
        if any(d in fspath for d in ("/tests/e2e/", "/tests/use_cases/", "/tests/security/")):
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Shared fixtures for CLI e2e tests
# ---------------------------------------------------------------------------


def unique_key(prefix: str = "test") -> str:
    """Generate a unique asset/resource key for E2E tests.

    Uses a short UUID suffix to avoid 409 Conflict on staging
    when tests are re-run against persistent data.

    Key format: lowercase alphanumeric with single hyphens only
    (no underscores, no double hyphens, no trailing hyphens).
    """
    import uuid

    # Strip trailing hyphens from prefix to avoid double-hyphen
    clean = prefix.rstrip("-").lower()
    return f"{clean}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def runner():
    """Click CLI runner."""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL — reads from env for staging, falls back to localhost."""
    return os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", f"{_DEFAULT_API_BASE}/api/v1"),
    )


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create an isolated temporary config directory for the CLI."""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file


@pytest.fixture
def temp_file(tmp_path):
    """Factory fixture: create a temporary file with given extension and content."""

    def _create_file(extension, content):
        file_path = tmp_path / f"test{extension}"
        file_path.write_text(content)
        return str(file_path), content

    return _create_file


_cached_access_token: str = ""


def _setup_cli_auth(api_base_url: str, config: Config) -> bool:
    """Set up authentication for CLI E2E tests.

    Tries, in order:
    1. ``TEST_API_KEY`` or ``DATAHUB_API_KEY`` env var
    2. Cached token from a previous successful setup
    3. Persona provisioning (``provision_persona("data_engineer")``)
       which handles rate-limit backoff, token caching, and self-heal.

    Returns True on success.
    """
    global _cached_access_token

    # --- Method 1: explicit API key from environment ---
    api_key = os.getenv("TEST_API_KEY") or os.getenv("DATAHUB_API_KEY")
    if api_key:
        config.set_api_key(api_key)
        return True

    # --- Use cached token if available ---
    if _cached_access_token:
        config.set_access_token(_cached_access_token)
        return True

    # --- Method 2: persona provisioning (handles 429, cache, self-heal) ---
    try:
        from tests._persona_provisioning import provision_persona

        creds = provision_persona("data_engineer")
        if creds and creds.api_key:
            _cached_access_token = creds.api_key
            config.set_access_token(creds.api_key)
            return True
    except Exception:
        pass

    return False


_login_failure_reason: str = ""


@pytest.fixture
def authenticated_config(temp_config_dir, api_base_url):
    """Config instance with API base URL and authentication already set up.

    CLI commands invoked via ``CliRunner`` will pick up these credentials
    because the global ``config`` singleton reads from the same patched
    config file (via ``config._load()`` called in ``api_client._request``).
    """
    cfg = Config()
    cfg.set_api_base_url(api_base_url)

    if not _setup_cli_auth(api_base_url, cfg):
        reason = _login_failure_reason or (
            "Set TEST_API_KEY or TEST_USER_EMAIL/TEST_USER_PASSWORD, "
            "or ensure pre-seeded E2E accounts exist."
        )
        pytest.skip(f"Could not set up CLI authentication for E2E test. {reason}")

    return cfg
