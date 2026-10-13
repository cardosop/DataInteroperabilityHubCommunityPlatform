"""JWT/API-key scope vocabulary — the single source of truth.

W6.5 (oss-release-remediation S1): the SDK/CLI/JS clients carry a
CONTRACT-COPIED vocabulary pinned equal to this module by
``scripts/tests/test_w65_scope_set_contract.py``.  Any scope change here
must land in the same change as the client copies (the contract test
fails otherwise) — that is what makes the W7.5 enforcement flip safe
for the platform's own clients.

This module MUST stay Django-free (no ``django.conf`` import): the
contract test runs in the CI no-django lint job and imports this module
directly.  ``permissions.py`` re-exports the names for compatibility.
"""

from __future__ import annotations

# The wildcard scope: grants everything.  PLATFORM_ADMIN-only to mint
# (enforced by ``permissions.disallowed_mint_scopes``).
WILDCARD_SCOPE = "*"

# The worker-internal scope (hub/apps/scheduled_ingestion/internal_auth.py
# re-imports this constant).  R2-B2: NEVER mintable through the public
# API-key endpoints, for anyone — not even the wildcard covers it.
SCOPE_SCHEDULED_INGESTION_INTERNAL = "scheduled_ingestion:internal"

# ── Role → Scope mapping ────────────────────────────────────────────────
# Each role grants a set of scopes. PLATFORM_ADMIN gets wildcard ("*").
# Use frozensets so callers can do subset checks (e.g. dp.issubset(ta)).
ROLE_SCOPE_MAP: dict[str, frozenset[str]] = {
    "PLATFORM_ADMIN": frozenset({WILDCARD_SCOPE}),
    "TENANT_ADMIN": frozenset(
        {
            "assets:read",
            "assets:write",
            "contracts:read",
            "contracts:write",
            "datasets:read",
            "datasets:write",
            "compliance:read",
            "compliance:write",
            "governance:read",
            "governance:write",
            "users:read",
            "users:write",
            "billing:read",
            "billing:write",
            "audit:read",
            "files:read",
            "files:write",
            "jobs:read",
            "jobs:write",
            "marketplace:read",
            "marketplace:write",
            "mesh:read",
            "mesh:write",
            "integrations:read",
            "integrations:write",
            "ml:read",
            "ml:write",
            "transformation:read",
            "transformation:write",
        }
    ),
    "DATA_PROVIDER": frozenset(
        {
            "assets:read",
            "assets:write",
            "contracts:read",
            "contracts:write",
            "datasets:read",
            "datasets:write",
            "files:read",
            "files:write",
            "jobs:read",
            "jobs:write",
            "marketplace:read",
            "marketplace:write",
            "mesh:read",
            "mesh:write",
            "integrations:read",
            "integrations:write",
            "ml:read",
            "ml:write",
            "transformation:read",
            "transformation:write",
        }
    ),
    "DATA_CONSUMER": frozenset(
        {
            "assets:read",
            "contracts:read",
            "datasets:read",
            "files:read",
            "marketplace:read",
            "mesh:read",
            "ml:read",
            "transformation:read",
        }
    ),
    "DATA_VIEWER": frozenset(
        {
            "assets:read",
            "contracts:read",
            "datasets:read",
        }
    ),
    "PII_VIEWER": frozenset(
        {
            "assets:read",
            "contracts:read",
            "datasets:read",
            "datasets:view_pii",
        }
    ),
    "AUDITOR": frozenset(
        {
            "audit:read",
            "compliance:read",
            "governance:read",
        }
    ),
    "COMPLIANCE_OFFICER": frozenset(
        {
            "compliance:read",
            "compliance:write",
            "governance:read",
            "governance:write",
            "audit:read",
        }
    ),
}

# Every concrete scope in the vocabulary (the wildcard is a grant, not
# a scope).  The worker-internal scope is deliberately EXCLUDED — it is
# not part of the client-facing vocabulary.
ALL_SCOPES: frozenset[str] = frozenset(
    scope
    for role_scopes in ROLE_SCOPE_MAP.values()
    for scope in role_scopes
    if scope != WILDCARD_SCOPE
)


def effective_scopes_for_roles(role_names: list[str] | tuple[str, ...] | set[str]) -> frozenset[str]:
    """Union of the scope sets granted by *role_names*.

    ``"*"`` passes through (it means "everything" at enforcement time);
    unknown roles contribute nothing.
    """
    scopes: set[str] = set()
    for role in role_names:
        scopes |= ROLE_SCOPE_MAP.get(role, frozenset())
    return frozenset(scopes)
