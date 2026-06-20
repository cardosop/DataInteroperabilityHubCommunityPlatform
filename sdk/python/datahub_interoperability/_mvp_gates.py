"""
MVP feature gate awareness for the SDK.

Mirrors ``cli/datahub_cli/_mvp_gates.py``: keeps a local copy of the
hub backend's ``MVP_GATED_RELATIVE_PREFIXES`` so the SDK does not have to
import Django at runtime. The local copy is kept honest by an
``ast.parse``-based drift test (see ``tests/test_mvp_gates_drift_sync.py``).

Phase 215.2 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

from typing import Dict, Final, FrozenSet

# Canonical relative prefixes (relative to ``/api/v1/``) that are gated when
# MVP_MODE is on. Order does not matter; the frozenset is the contract.
#
# This MUST stay byte-equivalent (as a *set*) to:
#   hub/apps/api/mvp_mode.py::MVP_GATED_RELATIVE_PREFIXES
#
# Drift is enforced by sdk/python/tests/test_mvp_gates_drift_sync.py.
#
# ``FrozenSet`` from ``typing`` (rather than the PEP 585 ``frozenset[str]``
# generic) is used here so the literal stays parseable on Python 3.9, even
# though the SDK currently requires 3.12+ — this matches the doctrine in the
# CLI module and gives us cheap forward-portability if downstream consumers
# pin an older interpreter.
MVP_GATED_PREFIXES: Final[FrozenSet[str]] = frozenset(
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


# Human-readable feature names keyed by gated prefix.
MVP_GATED_FEATURE_NAMES: Final[Dict[str, str]] = {
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
    "developer/": "Developer Portal",
    "dpia/": "Data Protection Impact Assessments",
    "ropa/": "Record of Processing Activities",
}


# Single multi-line ``str.format``-safe template (no f-string so the template
# itself can be inspected by tests).
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
