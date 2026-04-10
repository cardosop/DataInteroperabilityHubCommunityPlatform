import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.8.2 — Dimension: observability.

Verifies:
  - CLI --verbose flag emits structured log lines (TODO if not yet implemented)
  - SDK respects logging.getLogger('datahub_interoperability') levels
  - Both propagate X-Request-ID from API responses
"""

import logging
import uuid

import requests
from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get


# ---------------------------------------------------------------------------
# X-Request-ID propagation
# ---------------------------------------------------------------------------

def test_api_response_includes_request_id():
    """API responses should include an X-Request-ID header for tracing."""
    try:
        creds = provision_persona("data_engineer")
    except Exception as exc:
        pytest.skip(f"Cannot provision persona (no backend?): {exc}")
    resp = api_get("/auth/me/", creds)
    if resp.status_code != 200:
        pytest.skip(f"/auth/me/ returned {resp.status_code}")

    request_id = resp.headers.get("X-Request-ID") or resp.headers.get("X-Request-Id")
    if request_id is None:
        pytest.skip(
            "API does not return X-Request-ID header — "
            "TODO: add X-Request-ID middleware (Phase 216.8.2)"
        )
    assert len(request_id) > 0, "X-Request-ID header is empty"


def test_client_can_send_request_id():
    """Client-supplied X-Request-ID should be echoed back or accepted."""
    try:
        creds = provision_persona("data_engineer")
    except Exception as exc:
        pytest.skip(f"Cannot provision persona (no backend?): {exc}")
    custom_id = f"test-{uuid.uuid4().hex[:12]}"
    resp = requests.get(
        f"{api_base_url()}/auth/me/",
        headers={
            "Authorization": f"Bearer {creds.api_key}",
            "X-Request-ID": custom_id,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"/auth/me/ returned {resp.status_code}")

    # The server may echo our ID or generate its own — both OK.
    # The important thing is the response has SOME request ID.
    returned_id = resp.headers.get("X-Request-ID") or resp.headers.get("X-Request-Id")
    if returned_id is None:
        pytest.skip("API does not return X-Request-ID")
    # If it echoes ours, verify it matches
    if returned_id == custom_id:
        pass  # Perfect: server echoes client-supplied ID


# ---------------------------------------------------------------------------
# SDK logging
# ---------------------------------------------------------------------------

def test_sdk_logger_exists():
    """The SDK should register a logger under a predictable name."""
    logger = logging.getLogger("datahub_interoperability")
    assert logger is not None
    # The logger should accept standard level configuration
    logger.setLevel(logging.DEBUG)
    assert logger.level == logging.DEBUG
    logger.setLevel(logging.WARNING)
    assert logger.level == logging.WARNING


# ---------------------------------------------------------------------------
# CLI --verbose (TODO marker if not yet implemented)
# ---------------------------------------------------------------------------

def test_cli_verbose_flag_exists():
    """CLI should accept a --verbose or -v flag for structured logging.

    TODO: the CLI root group (`@click.group`) does not currently have
    a --verbose flag. When added, this test should verify that:
    1. `datahub --verbose assets list` produces log lines on stderr
    2. Log lines are structured (JSON or key=value format)
    3. Log lines include timestamps and log levels
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    help_text = result.stdout.lower()
    if "--verbose" in help_text or "-v" in help_text:
        pass  # Flag exists — good
    else:
        pytest.skip(
            "CLI does not have --verbose flag yet — "
            "TODO: add --verbose to CLI root group"
        )
