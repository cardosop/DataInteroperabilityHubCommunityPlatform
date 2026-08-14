"""Core-mode gate awareness for the CLI (Phase 313.4).

The CLI keeps a local list of paid-layer command groups so that hitting a
paid endpoint against a core-only backend (HUB_CORE_ONLY=1) surfaces a
friendly "SaaS feature — not available in this deployment" error instead of
a raw 404. Same design as ``_mvp_gates.py``: no Django imports, drift
enforced by ``cli/tests/test_core_gates_drift_sync.py`` against the
canonical manifest (``hub/apps/manifest.py``).

Canonical source:
    hub/apps/manifest.py::_PAID_MODULES → last path segment per module.
The CLI only lists groups that actually exist as commands in main.py.
"""

from __future__ import annotations

from typing import Final

# Paid-layer CLI command groups (last segment of each paid manifest module
# that has a registered CLI group). `developer` is NOT here: the developer
# app is CORE per the manifest boundary.
#
# MUST stay byte-equivalent (as a *set*) to:
#   {m.split('.')[-1] for m in hub.apps.manifest._PAID_MODULES}
#   ∩ {registered CLI group names in main.py}
PAID_CLI_GROUPS: Final[frozenset[str]] = frozenset(
    {
        "marketplace",
        "baas",
        "ml",
        "billing",
        "social",
        "semantic",
        "graphql",
    }
)


def detect_core_gated_feature(path: str) -> tuple[str, str] | None:
    """Return ``(group, friendly_message)`` if ``path`` hits a paid group,
    else None. Mirrors ``detect_mvp_gated_feature`` from ``_mvp_detection``."""
    # Normalize: strip scheme/netloc and the /api/v1/ prefix — the same
    # convention as _mvp_detection._normalize_relative.
    relative = path
    if "/api/v1/" in relative:
        relative = relative.split("/api/v1/", 1)[1]
    relative = relative.strip("/")
    if not relative:
        return None
    first = relative.split("/")[0]
    if first not in PAID_CLI_GROUPS:
        return None
    return (
        first,
        f"'{first}' is a SaaS feature — not available in this deployment "
        f"(core-only backend).",
    )
