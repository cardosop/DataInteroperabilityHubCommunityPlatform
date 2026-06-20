"""
MVP feature gate awareness for the CLI.

This module owns the *CLI-side* hardcoded list of API v1 prefixes that the hub
backend disables when ``MVP_MODE=True``. Keeping a local copy (instead of
importing the Django settings module) lets the CLI surface friendly Post-MVP
errors without pulling Django into its dependency closure.

The local frozenset is kept in sync with the canonical source
(``hub/apps/api/mvp_mode.py::MVP_GATED_RELATIVE_PREFIXES``) by a drift test
that uses ``ast.parse`` — see ``cli/tests/test_mvp_gates_drift_sync.py``. The
drift test fails CI on any divergence.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from typing import Final

# Canonical relative prefixes (relative to ``/api/v1/``) that are gated when
# MVP_MODE is on. Order does not matter; the frozenset is the contract.
#
# This MUST stay byte-equivalent (as a *set*) to:
#   hub/apps/api/mvp_mode.py::MVP_GATED_RELATIVE_PREFIXES
#
# Drift is enforced by cli/tests/test_mvp_gates_drift_sync.py.
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
