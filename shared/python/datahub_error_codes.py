"""
Structured error code constants shared between CLI and SDK (Phase 279.J.2).

Both ``cli/setup.py`` and ``sdk/python/setup.py`` MUST add
``shared/python/`` to ``package_data`` so these constants are
available at runtime in installed distributions.

Usage:
    from datahub_error_codes import (
        COMPLIANCE_THRESHOLD_EXCEEDED,
        COMPLIANCE_RUN_REQUIRED,
    )
"""

# ── Compliance & Governance ────────────────────────────────────────────

COMPLIANCE_THRESHOLD_EXCEEDED = "COMPLIANCE_THRESHOLD_EXCEEDED"
COMPLIANCE_RUN_REQUIRED = "COMPLIANCE_RUN_REQUIRED"
COMPLIANCE_GATE_FAILED = "COMPLIANCE_GATE_FAILED"
COMPLIANCE_SERVICE_UNAVAILABLE = "COMPLIANCE_SERVICE_UNAVAILABLE"
COMPLIANCE_DEGRADED_BLOCKED = "COMPLIANCE_DEGRADED_BLOCKED"

# ── Governance / ABAC ──────────────────────────────────────────────────

ABAC_POLICY_DENIED = "ABAC_POLICY_DENIED"
ACCESS_REQUEST_CONFLICT = "ACCESS_REQUEST_CONFLICT"
APPROVAL_DELEGATION_EXPIRED = "APPROVAL_DELEGATION_EXPIRED"
APPROVAL_CHAIN_MISCONFIGURED = "APPROVAL_CHAIN_MISCONFIGURED"

# ── Feature gating ─────────────────────────────────────────────────────

FEATURE_NOT_ENABLED = "FEATURE_NOT_ENABLED"
OPENLINEAGE_NOT_ENABLED = "OPENLINEAGE_NOT_ENABLED"
LINEAGE_SUBSCRIPTIONS_NOT_ENABLED = "LINEAGE_SUBSCRIPTIONS_NOT_ENABLED"
SEMANTIC_FEATURE_DISABLED = "SEMANTIC_FEATURE_DISABLED"
ML_FEATURE_DISABLED = "ML_FEATURE_DISABLED"
WAREHOUSE_CONNECTIVITY_DISABLED = "WAREHOUSE_CONNECTIVITY_DISABLED"

# ── Marketplace / Billing ──────────────────────────────────────────────

PLAN_LIMIT_EXCEEDED = "PLAN_LIMIT_EXCEEDED"
ASSET_CREATION_DISABLED = "ASSET_CREATION_DISABLED"
BILLING_REQUIRED = "BILLING_REQUIRED"
PAYMENT_FAILED = "PAYMENT_FAILED"
KYC_REQUIRED = "KYC_REQUIRED"
KYC_PENDING = "KYC_PENDING"
KYC_REJECTED = "KYC_REJECTED"

# ── Validation ─────────────────────────────────────────────────────────

VALIDATION_ERROR = "VALIDATION_ERROR"
STRUCTURELESS_CONTRACT = "STRUCTURELESS_CONTRACT"
OPTIMISTIC_LOCK_VERSION_MISMATCH = "OPTIMISTIC_LOCK_VERSION_MISMATCH"

# ── Infrastructure ─────────────────────────────────────────────────────

CROSS_SERVICE_VERSION_MISMATCH = "CROSS_SERVICE_VERSION_MISMATCH"
RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
INTERNAL_ERROR = "INTERNAL_ERROR"

# ── Capability-gated remediation messages ──────────────────────────────

_FEATURE_GATE_REMEDIATION: dict[str, str] = {
    OPENLINEAGE_NOT_ENABLED: (
        "The OpenLineage feature is not enabled for this tenant. "
        "Enable it via: datahub admin feature-flags update <tenant-id> --enable-openlineage"
    ),
    LINEAGE_SUBSCRIPTIONS_NOT_ENABLED: (
        "Lineage subscriptions are not enabled for this tenant. "
        "Enable it via: datahub admin feature-flags update <tenant-id> --enable-lineage-subscriptions"
    ),
    SEMANTIC_FEATURE_DISABLED: (
        "The Semantic / SPARQL feature is not enabled for this tenant. "
        "Enable it via tenant settings or contact your Platform Admin."
    ),
    ML_FEATURE_DISABLED: (
        "ML features are not enabled for this tenant. "
        "Enable it via: datahub admin feature-flags update <tenant-id> --enable-ml"
    ),
    WAREHOUSE_CONNECTIVITY_DISABLED: (
        "Warehouse connectivity is not enabled for this tenant. "
        "Enable it via: datahub admin feature-flags update <tenant-id> --enable-warehouse"
    ),
    FEATURE_NOT_ENABLED: (
        "This feature is not enabled for your tenant. Contact your Platform Admin to enable it."
    ),
}


def get_remediation_message(error_code: str) -> str:
    """Return a human-readable remediation message for a known error code.

    Returns the empty string for unknown codes so callers can always
    call this without a guard.
    """
    return _FEATURE_GATE_REMEDIATION.get(error_code, "")
