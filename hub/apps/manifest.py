"""App membership manifest — single source of truth for the OSS/paid split (Phase 313.1).

Consumed by:
- ``hub/settings.py`` — INSTALLED_APPS, middleware, database routers
- ``scripts/check_core_boundary.py`` (GATE-29) — paid import scanning
- ``scripts/publish_public.sh`` — mirror exclusion list generation
- CLI core-gates (later phase)

Invariants (locked by ``hub/tests/test_manifest.py``):
- CORE_APPS + PAID_APPS == ALL_HUB_APPS (every installed hub app is inside
  exactly one side of the boundary).
- ALL_HUB_APPS preserves the exact pre-split INSTALLED_APPS ordering — the
  production path (HUB_CORE_ONLY unset) must stay byte-for-byte identical.
- CORE apps MUST NOT import PAID apps (enforced by GATE-29).
- This module performs no Django imports and reads the environment lazily so
  it is importable at settings load and by standalone scripts.

Trickle-down procedure: move an entry from PAID to CORE by editing
``_PAID_MODULES`` below; everything else (settings, gates, publish) follows.
"""

from __future__ import annotations

import os
import re

# Matches only AppConfig-class entries ("hub.apps.compliance.apps.ComplianceConfig").
# Plain module paths like "hub.apps.semantic" contain ".apps." INSIDE the
# path and MUST be returned unchanged (the split-based normaliser silently
# classified every app as "hub" — caught by the 313.1 boot verification).
_APPS_CONFIG_SUFFIX_RE = re.compile(
    r"^(hub\.apps\.[A-Za-z_][A-Za-z0-9_]*)\.apps\.[A-Za-z_][A-Za-z0-9_]*$"
)

# Ordered exactly as the pre-split INSTALLED_APPS shipped them. Do NOT reorder
# without a deliberate migration plan — app order affects template lookup,
# ready() ordering, and admin discovery.
ALL_HUB_APPS: tuple[str, ...] = (
    "hub.apps.core",
    "hub.apps.tenants",
    "hub.apps.users",
    "hub.apps.auth",
    "hub.apps.audit",
    "hub.apps.billing",
    "hub.apps.platform",
    "hub.apps.gdpr",
    "hub.apps.files",
    "hub.apps.datasets",
    "hub.apps.assets",
    "hub.apps.jobs",
    "hub.apps.contracts",
    "hub.apps.dq",
    "hub.apps.compliance.apps.ComplianceConfig",
    "hub.apps.governance",
    "hub.apps.consent",
    "hub.apps.dsar.apps.DsarConfig",
    "hub.apps.ropa.apps.RopaConfig",
    "hub.apps.dpia.apps.DpiaConfig",
    "hub.apps.breach.apps.BreachConfig",
    "hub.apps.processor_agreements.apps.ProcessorAgreementsConfig",
    "hub.apps.regulation_policies.apps.RegulationPoliciesConfig",
    "hub.apps.semantic",
    "hub.apps.marketplace",
    "hub.apps.developer",
    "hub.apps.api",
    "hub.apps.graphql",
    "hub.apps.graphql_ld",
    "hub.apps.health",
    "hub.apps.observability",
    "hub.apps.notifications",
    "hub.apps.rate_limiting",
    "hub.apps.scheduled_ingestion",
    "hub.apps.scheduled_export",
    "hub.data_movement",
    "hub.apps.search",
    "hub.apps.webhooks.apps.WebhooksConfig",
    "hub.apps.api.analytics",
    "hub.apps.orchestration",
    "hub.apps.websocket",
    "hub.apps.ai",
    "hub.apps.ml",
    "hub.apps.social",
    "hub.apps.mesh",
    "hub.apps.virtualization",
    "hub.apps.integrations",
    "hub.apps.baas",
    "hub.apps.transformation",
    "hub.apps.versioning",
    "hub.apps.warehouses.apps.WarehousesConfig",
    "hub.apps.security",
)

# Paid/commercial layer — private repo, hosted SaaS. Membership drives
# settings filtering (HUB_CORE_ONLY), GATE-29, and the publish exclusions.
_PAID_MODULES: frozenset[str] = frozenset(
    {
        "hub.apps.semantic",
        "hub.apps.marketplace",
        "hub.apps.billing",
        "hub.apps.baas",
        "hub.apps.rate_limiting",
        "hub.apps.ai",
        "hub.apps.ml",
        "hub.apps.social",
        "hub.apps.graphql",
        "hub.apps.graphql_ld",
        "hub.apps.graphql_graphene",
    }
)

# Middleware entries owned by paid apps (filtered under HUB_CORE_ONLY).
PAID_MIDDLEWARE: frozenset[str] = frozenset(
    {
        "hub.apps.rate_limiting.middleware.RateLimitMiddleware",
        "hub.apps.baas.middleware.BaaSUsageRecordingMiddleware",
    }
)

_TRUE_VALUES: frozenset[str] = frozenset({"1", "true", "yes"})


def module_name(entry: str) -> str:
    """Normalise an INSTALLED_APPS entry to its importable module path.

    'hub.apps.compliance.apps.ComplianceConfig' → 'hub.apps.compliance'
    'hub.apps.semantic' → 'hub.apps.semantic' (unchanged)
    """
    m = _APPS_CONFIG_SUFFIX_RE.match(entry)
    return m.group(1) if m else entry


# Membership tuples, derived from the single ordered source.
PAID_APPS: tuple[str, ...] = tuple(e for e in ALL_HUB_APPS if module_name(e) in _PAID_MODULES)
CORE_APPS: tuple[str, ...] = tuple(e for e in ALL_HUB_APPS if module_name(e) not in _PAID_MODULES)


def is_core_only() -> bool:
    """True when the process runs without the paid layer (HUB_CORE_ONLY)."""
    return os.environ.get("HUB_CORE_ONLY", "").strip().lower() in _TRUE_VALUES


def paid_app_module_names() -> frozenset[str]:
    """Importable module path of every paid app (for GATE-29 / publish)."""
    return frozenset(module_name(e) for e in PAID_APPS) | {
        module_name(e) for e in ("hub.apps.graphql_graphene",)
    }
