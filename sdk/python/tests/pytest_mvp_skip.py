"""
Phase 216.0.2 — MVP-mode skip marker for the SDK test suite (mirror of CLI).

Exports:
    skip_if_mvp_mode  — ``pytestmark = skip_if_mvp_mode`` at module level
                         causes every test in the file to be skipped when
                         ``MVP_MODE=true``.
    mvp_only          — ``@pytest.mark.mvp`` marks tests that MUST run in
                         MVP mode (the ``pytest -m mvp`` selector).

Usage::

    from tests.pytest_mvp_skip import skip_if_mvp_mode

    pytestmark = skip_if_mvp_mode   # skip entire file when MVP_MODE=true
"""
from __future__ import annotations

import pytest

from tests._pytest_helpers import _parse_bool_env

_MVP_MODE = _parse_bool_env("MVP_MODE")

skip_if_mvp_mode = pytest.mark.skipif(
    _MVP_MODE,
    reason="Post-MVP test — skipped because MVP_MODE=true",
)

mvp_only = pytest.mark.mvp
