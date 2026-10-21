"""
Phase 232.0 — canonical tenant-scoped role names and descriptions.

``create_default_roles`` (tenant signals) and the Phase-232 migration
backfill MUST stay aligned with ``STANDARD_TENANT_ROLE_DEFINITIONS``.
"""

from __future__ import annotations

from typing import Final

#: Roles provisioned on every NEW tenant (non-test environments). See tenants.signals.
STANDARD_TENANT_ROLE_DEFINITIONS: Final[tuple[tuple[str, str], ...]] = (
    ("TENANT_ADMIN", "Full administrative access within tenant"),
    ("DATA_PROVIDER", "Can create and manage data assets"),
    ("DATA_CONSUMER", "Can request and access data assets"),
    # Phase 260.3.E — explicit VIEW_PII / datasets:view_pii for authorised sample unmask.
    (
        "PII_VIEWER",
        "May request unredacted dataset sample previews where tenant policy allows",
    ),
    ("AUDITOR", "Read-only access to compliance/DQ reports and audit logs"),
    # D232.13 — Privacy / security programme roles (Phase 232.0).
    ("DPO", "Data Protection Officer obligations and privacy programme oversight"),
    (
        "LEGAL_ADMIN",
        "Legal bases, contracts, DPAs and regulatory attestations",
    ),
    (
        "SECURITY_ADMIN",
        "Security posture, breaches, DPIA artefacts and vendor risk",
    ),
)


STANDARD_TENANT_ROLE_NAMES: Final[frozenset[str]] = frozenset(
    n for n, _ in STANDARD_TENANT_ROLE_DEFINITIONS
)
