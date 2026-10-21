"""Resilience test conftest - patches sleep functions to prevent real delays."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _patch_sleeps():
    """Patch all sleep/backoff functions to prevent real delays in resilience tests."""
    with (
        patch("hub.apps.core.resilience.backoff.sleep_with_jitter", return_value=None),
        patch("time.sleep", return_value=None),
    ):
        yield
