"""
Phase 216.X.8 — local CLI duplicate of ``hub/apps/api/mvp_mode.py::_parse_bool_env``.

The CLI test suite cannot import Django at runtime (the CLI is shipped
standalone) so it duplicates the canonical environment-bool parser
byte-for-byte. A drift test (``cli/tests/test_parse_bool_env_drift.py``)
ast-parses both source files and asserts the function bodies are identical.

This is the same doctrine used by Phase 215 for ``MVP_GATED_RELATIVE_PREFIXES``
(see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md).
"""
from __future__ import annotations

import os


def _parse_bool_env(name: str) -> bool:
    """Parse a boolean environment variable using the same rules as ``env.bool``.

    Truthy values: ``true``, ``1``, ``yes``, ``on``, ``y``, ``t`` (case-insensitive).
    Everything else (including unset / empty) is False.

    This function is the **canonical** implementation. Phase 216 test helpers
    in ``cli/tests/_pytest_helpers.py`` and ``sdk/python/tests/_pytest_helpers.py``
    duplicate this function byte-for-byte (no shared module — see D129)
    and a drift test ast-parses this file to assert the bodies stay
    byte-equivalent.
    """
    value = os.environ.get(name, "")
    return value.strip().lower() in ("true", "1", "yes", "on", "y", "t")
