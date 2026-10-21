"""
MVP feature gate awareness for the CLI.

W12.5 — the constants now live in the vendored canonical module
``datahub_cli._mvp_detection`` (a byte-for-byte copy of
``shared/mvp_detection.py``, the single source); this module re-exports
them under the CLI's consumer-facing names so existing importers
(``odps_errors``, the drift tests) are unchanged.

The prefix frozenset stays in lock-step with the canonical hub backend
list (``hub/apps/api/mvp_mode.py::MVP_GATED_RELATIVE_PREFIXES``) via the
ast-based drift test ``cli/tests/test_mvp_gates_drift_sync.py``.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from ._mvp_detection import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_MESSAGE_TEMPLATE,
    MVP_GATED_RELATIVE_PREFIXES,
)

__all__ = [
    "MVP_FEATURE_GATED_CODE",
    "MVP_GATED_FEATURE_NAMES",
    "MVP_GATED_MESSAGE_TEMPLATE",
    "MVP_GATED_RELATIVE_PREFIXES",
]
