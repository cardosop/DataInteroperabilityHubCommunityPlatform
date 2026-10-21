"""Core-mode gate awareness for the CLI (Phase 313.4).

The CLI keeps a local list of paid-layer URL prefixes and command groups so
that hitting a paid endpoint against a core-only backend (HUB_CORE_ONLY=1)
surfaces a friendly "SaaS feature — not available in this deployment" error
instead of a raw 404. Same design as ``_mvp_gates.py``: no Django imports,
drift enforced by ``cli/tests/test_core_gates_drift_sync.py`` against the
canonical manifest (``hub/apps/manifest.py``).

Canonical sources:
    hub/apps/manifest.py::_PAID_MODULES      → paid CLI command groups
    hub/apps/manifest.py::PAID_URL_PREFIXES  → paid URL-path prefixes
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

# Paid URL-path prefixes — mirror of hub.apps.manifest.PAID_URL_PREFIXES.
# MUST stay byte-equivalent (as a *set*); drift is AST-enforced by
# cli/tests/test_core_gates_drift_sync.py::test_paid_url_prefixes_match_manifest.
# Paths are matched with leading slashes stripped (see detect_core_gated_feature).
PAID_URL_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "api/v1/marketplace/",
        "api/v1/integrations/marketplace/",
        "api/v1/billing/",
        "api/v1/admin/connect/review-queue/",
        "api/v1/baas/",
        "api/v1/ml/",
        "api/v1/ai/",
        "api/v1/semantic/",
        "api/v1/social/",
        "graphql/",
        "graphql-graphene/",
    }
)

# Prefix → CLI group name for the friendly message.  Nested paid paths map
# to the FUNCTIONAL group (integrations/marketplace → marketplace), which
# is the whole point of prefix-based gating.
_PAID_URL_PREFIX_TO_GROUP: Final[dict[str, str]] = {
    "api/v1/marketplace/": "marketplace",
    "api/v1/integrations/marketplace/": "marketplace",
    "api/v1/billing/": "billing",
    "api/v1/admin/connect/review-queue/": "billing",
    "api/v1/baas/": "baas",
    "api/v1/ml/": "ml",
    "api/v1/ai/": "ai",
    "api/v1/semantic/": "semantic",
    "api/v1/social/": "social",
    "graphql/": "graphql",
    "graphql-graphene/": "graphql",
}


def detect_core_gated_feature(path: str) -> tuple[str, str] | None:
    """Return ``(group, friendly_message)`` if ``path`` hits a paid prefix,
    else None.

    P.5 D3 — resolution is by PAID PATH PREFIX, not by the first URL
    segment: nested paid paths hosted under a core app's prefix
    (``api/v1/integrations/marketplace/…``) gate correctly, while core
    siblings under the same app (``api/v1/integrations/health/``) do not.
    """
    # Normalize: strip scheme/netloc and leading slashes; keep the api/v1/
    # segment so the prefixes above match exactly.
    relative = path
    if "://" in relative:
        relative = relative.split("://", 1)[1]
        relative = relative.split("/", 1)[1] if "/" in relative else ""
    relative = relative.strip("/")
    if not relative:
        return None
    for prefix, group in _PAID_URL_PREFIX_TO_GROUP.items():
        if relative == prefix.rstrip("/") or relative.startswith(prefix):
            return (
                group,
                f"'{group}' is a SaaS feature — not available in this deployment "
                "(core-only backend).",
            )
    return None
