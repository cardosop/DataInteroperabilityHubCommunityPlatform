"""JWT/API-key scope vocabulary carried by the CLI (W6.5, S1).

This module is a CONTRACT COPY of the backend's vocabulary
(``hub.apps.auth.scopes`` — the single source of truth).  The contract
test ``scripts/tests/test_w65_scope_set_contract.py`` pins both modules
equal, so a scope change on either side must land in the same change.
The W7.5 ``ENFORCE_JWT_SCOPES`` flip depends on the platform's own
clients carrying exactly this set.

Pure stdlib by design: the CI no-django lint job imports this module
directly.
"""

from __future__ import annotations

# The wildcard scope: grants everything.  PLATFORM_ADMIN-only to mint
# (the backend enforces the role gate — the client cannot know roles).
WILDCARD_SCOPE = "*"

# The worker-internal scope — NEVER mintable through the public API-key
# endpoints, for anyone (R2-B2).  Client validation rejects it.
SCOPE_SCHEDULED_INGESTION_INTERNAL = "scheduled_ingestion:internal"

# ── Role → Scope mapping ────────────────────────────────────────────────
# Each role grants a set of scopes. PLATFORM_ADMIN gets wildcard ("*").
# Use frozensets so callers can do subset checks.
ROLE_SCOPES: dict[str, frozenset[str]] = {
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
            # W7.5 — virtualization write views gate on HasScope
            # ("virtualization:write"); grantable roles must carry it.
            "virtualization:write",
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
            "virtualization:write",
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
# a scope; the worker-internal scope is deliberately excluded).
ALL_SCOPES: frozenset[str] = frozenset(
    scope
    for role_scopes in ROLE_SCOPES.values()
    for scope in role_scopes
    if scope != WILDCARD_SCOPE
)


def validate_scopes(requested: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    """Return the scopes from *requested* that are NOT in the client
    vocabulary, in input order, without duplicates.

    The wildcard ``"*"`` passes (mintable by PLATFORM_ADMIN — the
    backend enforces the role gate).  The worker-internal scope is
    ALWAYS flagged (unmintable via the public API — R2-B2).
    """
    invalid: list[str] = []
    seen: set[str] = set()
    for scope in requested or []:
        if scope in seen:
            continue
        seen.add(scope)
        if scope == SCOPE_SCHEDULED_INGESTION_INTERNAL or (
            scope != WILDCARD_SCOPE and scope not in ALL_SCOPES
        ):
            invalid.append(scope)
    return invalid


def scope_set_for_role(role: str) -> frozenset[str]:
    """The scope set a role grants (empty for unknown roles)."""
    return ROLE_SCOPES.get(role, frozenset())
