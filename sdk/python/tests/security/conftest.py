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
        "http://localhost:8000/api/v1",
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
