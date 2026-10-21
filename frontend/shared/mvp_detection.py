"""MVP feature-gate detection — the ONE canonical implementation (W12.5).

Previously shipped as two divergent copies (``shared/mvp_detection.py`` with
a required-injection API vs the CLI/SDK vendored copies with zero-arg
defaults). This module is now the single source: the functions take
OPTIONAL injection parameters (``gated_prefixes`` / ``feature_names`` —
for parametrized unit tests) and default to the module-level canonical
constants below. The CLI and SDK vendor this file byte-for-byte
(``cli/datahub_cli/_mvp_detection.py`` and
``sdk/python/datahub_interoperability/_mvp_detection.py`` — wheels stay
self-contained) and their ``_mvp_gates.py`` modules re-export the
constants from the vendored copy. Byte-identity is pinned by
``scripts/tests/test_w125_duplicate_consolidation.py``; the prefix set
stays in lock-step with the hub backend list
(``hub/apps/api/mvp_mode.py::MVP_GATED_RELATIVE_PREFIXES``) via the
existing ast-based drift tests.

Phase 215.1 / 278.AA.15 — see
openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

MVP_GATED_RELATIVE_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        "mesh/",
        "virtualization/",
        "integrations/",
        "baas/",
        "ml/",
        "ai/",
        "transformation/",
        "social/",
        "scheduled-ingestions/",
        "scheduled-exports/",
        "developer/",
        "dpia/",
        "ropa/",
        # Phase 278 apps — mounted in hub/apps/api/urls.py and present in the
        # canonical list; this copy had not been updated to match.
        "breach/",
        "consent/",
        "data-movement/",
        "databricks/",
        "dsar/",
        "gdpr/",
        "processor-agreements/",
        "warehouses/",
    }
)


# Stable, machine-readable error code. Programmatic consumers SHOULD branch on
# ``error.code == MVP_FEATURE_GATED_CODE`` rather than parsing the message.
MVP_FEATURE_GATED_CODE: Final[str] = "MVP_FEATURE_GATED"


# Human-readable feature names keyed by gated prefix. Used in the rendered
# error message and exposed via the ``feature`` attribute on the raised error.
MVP_GATED_FEATURE_NAMES: Final[dict[str, str]] = {
    "mesh/": "Data Mesh",
    "virtualization/": "Data Virtualization",
    "integrations/": "Marketplace Integrations",
    "baas/": "Backend-as-a-Service",
    "ml/": "Machine Learning Workbench",
    "ai/": "AI Assistants",
    "transformation/": "Data Transformation Pipelines",
    "social/": "Social / Collaboration",
    "scheduled-ingestions/": "Scheduled Ingestions",
    "scheduled-exports/": "Scheduled Exports",
    "developer/": "Developer APIs",
    "dpia/": "DPIA Workflows",
    "ropa/": "ROPA Records",
    # Phase 278 apps — must stay in step with MVP_GATED_RELATIVE_PREFIXES;
    # test_mvp_gated_404_handling asserts every gated prefix has a name.
    "breach/": "Breach Notification",
    "consent/": "Consent Management",
    "data-movement/": "Data Movement Records",
    "databricks/": "Databricks Control Plane",
    "dsar/": "Data Subject Access Requests",
    "gdpr/": "GDPR Compliance",
    "processor-agreements/": "Processor Agreements",
    "warehouses/": "Warehouse Connections",
}


# Message template. Single multi-line ``str.format``-safe template (we
# deliberately avoid f-strings here so the template itself can be inspected
# and asserted on by tests).
MVP_GATED_MESSAGE_TEMPLATE: Final[str] = (
    "The '{feature}' feature is not available in the current MVP release.\n"
    "\n"
    "  Endpoint:    {endpoint}\n"
    "  Environment: {environment_url}\n"
    "  Status:      Post-MVP (planned)\n"
    "\n"
    "This is a deliberate gate, not a missing resource — the route exists in\n"
    "the codebase and will be enabled after the MVP release. To track when\n"
    "'{feature}' becomes available, see the project roadmap.\n"
    "\n"
    "Error code: {code}"
)

"""
Pure functions for detecting MVP-gated paths and extracting environment info.

These are deliberately side-effect-free so they can be exhaustively
parametrized in unit tests without any HTTP, mock, or fixture machinery.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

_API_V1_PREFIX = "/api/v1/"


def _normalize_relative(path: str) -> str:
    """Strip an optional leading ``/api/v1/`` (or full URL) and return the
    relative path component used for prefix matching.

    Accepts any of:
      - ``"mesh/clusters"``                 (already relative)
      - ``"/api/v1/mesh/clusters"``         (absolute API path)
      - ``"https://host/api/v1/mesh/..."``  (full request URL)

    Leading slashes on the relative form are tolerated and stripped.
    """
    if not path:
        return ""
    if _API_V1_PREFIX in path:
        return path.split(_API_V1_PREFIX, 1)[1].lstrip("/")
    return path.lstrip("/")


def detect_mvp_gated_feature(
    path: str,
    *,
    gated_prefixes: frozenset[str] | None = None,
    feature_names: dict[str, str] | None = None,
) -> tuple[str, str] | None:
    """Return ``(prefix, feature)`` if ``path`` matches a gated prefix, else None.

    The longest matching prefix wins (so ``mesh/clusters/abc`` matches
    ``mesh/`` deterministically). The prefix list is sourced from
    ``MVP_GATED_RELATIVE_PREFIXES`` to keep this function in lock-step with
    the canonical hub backend list.
    """
    relative = _normalize_relative(path)
    if not relative:
        return None
    if gated_prefixes is None:
        gated_prefixes = MVP_GATED_RELATIVE_PREFIXES
    if feature_names is None:
        feature_names = MVP_GATED_FEATURE_NAMES
    matches = [p for p in gated_prefixes if relative.startswith(p)]
    if not matches:
        return None
    # Deterministic tiebreak: longest prefix first, then lexicographic.
    prefix = max(matches, key=lambda p: (len(p), p))
    feature = feature_names.get(prefix, prefix.rstrip("/").replace("-", " ").title())
    return (prefix, feature)


def extract_environment_url(request_url: str) -> str:
    """Return the ``scheme://netloc`` origin of ``request_url``.

    Uses :func:`urllib.parse.urlparse` directly. ``urlparse`` does not raise
    on malformed input — it returns empty fields — so this function MUST NOT
    wrap the call in a bare ``except``. If the URL has no scheme or netloc
    we fall back to the original input (trimmed) so the caller still sees
    something useful in the rendered error message.
    """
    if not request_url:
        return ""
    parsed = urlparse(request_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return request_url.strip()
