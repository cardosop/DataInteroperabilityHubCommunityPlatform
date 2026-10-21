"""
MVP feature gate awareness for the SDK.

W12.5 — the constants now live in the vendored canonical module
``datahub_interoperability._mvp_detection`` (a byte-for-byte copy of
``shared/mvp_detection.py``, the single source); this module re-exports
them under the SDK's consumer-facing names (``MVP_GATED_PREFIXES`` is the
SDK's historical alias for the canonical
``MVP_GATED_RELATIVE_PREFIXES`` frozenset) so existing importers are
unchanged.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from ._mvp_detection import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_FEATURE_NAMES,
    MVP_GATED_MESSAGE_TEMPLATE,
    MVP_GATED_RELATIVE_PREFIXES,
)

# The SDK's consumer-facing alias (sdk __init__ exposes it as
# MVP_GATED_PREFIXES).
MVP_GATED_PREFIXES = MVP_GATED_RELATIVE_PREFIXES

__all__ = [
    "MVP_FEATURE_GATED_CODE",
    "MVP_GATED_FEATURE_NAMES",
    "MVP_GATED_MESSAGE_TEMPLATE",
    "MVP_GATED_PREFIXES",
    "MVP_GATED_RELATIVE_PREFIXES",
]
