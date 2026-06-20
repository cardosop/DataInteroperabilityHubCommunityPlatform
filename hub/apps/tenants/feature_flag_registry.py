"""
Phase 250.0.15 / D250.13 — feature-flag lifecycle registry.

Single source of truth for every per-tenant feature flag introduced by
Phase 250 (and forward). Flags here pair with ``Tenant`` model boolean
fields; this registry adds the metadata that the ``Tenant`` model can't
hold (owner team, retire-by date, lifecycle stage, signoff requirements).

The stale-flag detector at
[scripts/detect_stale_feature_flags.py](../../../scripts/detect_stale_feature_flags.py)
reads this registry to surface flags that have aged past their
``retire_by`` date and warrant retirement.

Adding a new flag
-----------------
1. Pick a name following ``<area>_<feature>_enabled`` convention.
2. Add the ``Tenant`` model boolean field via additive migration.
3. Append a ``FeatureFlag`` entry to ``REGISTRY`` below with full metadata.
4. Wire the flag check into the relevant view / service.
5. Emit ``TENANT_FEATURE_FLAG_FLIPPED`` audit on every change (registry
   helper provides this in future iterations).

Conventions
-----------
* ``stage = DRAFT`` — code path exists but no tenant flips it yet.
* ``stage = CANARY`` — released; friendly tenants opt in.
* ``stage = GA`` — generally-available; default flips to True (or stays
  False for explicit-opt-in features). ``retire_by`` mandatory.
* ``stage = DEPRECATED`` — marked for removal. ``retire_by`` mandatory.
* ``stage = RETIRED`` — code path AND flag deleted. Entry stays in
  registry as historical record (until annual cleanup).

Cross-references
----------------
* Lifecycle policy: [docs/runbooks/feature-flag-lifecycle.md](../../../docs/runbooks/feature-flag-lifecycle.md)
* Phase 250 design: D250.13 in `openspec/changes/preprod01/design.md`
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

FeatureFlagStage = Literal["DRAFT", "CANARY", "GA", "DEPRECATED", "RETIRED"]


@dataclass(frozen=True)
class FeatureFlag:
    """Metadata for a single per-tenant feature flag."""

    name: str
    """The Tenant model field name (e.g. ``warehouse_connectivity_enabled``)."""

    description: str
    """One-line human-readable purpose."""

    owner_team: str
    """e.g. ``asset-creation-eng`` — the team that owns retirement decisions."""

    owner_email: str
    """Team alias for ops escalation (e.g. ``asset-creation-eng@meshant.com``)."""

    created_at: datetime
    """Timezone-aware UTC datetime when the flag was added to source."""

    stage: FeatureFlagStage
    """Lifecycle stage per the policy."""

    retire_by: datetime | None
    """Mandatory if stage in {GA, DEPRECATED}; ``None`` for DRAFT / CANARY / RETIRED."""

    default_existing_tenants: bool
    """Default value applied to existing tenants on flag introduction."""

    default_new_tenants: bool
    """Default value for tenants created after flag introduction."""

    related_phase: str
    """e.g. ``Phase 250.6.A`` — the phase that introduced this flag."""

    related_design_doc: str
    """e.g. ``D250.18`` — the design decision in design.md."""

    related_audit_event: str = ""
    """Audit event emitted when this flag flips (security-relevant flags)."""

    requires_dpo_signoff: bool = False
    """True for flags affecting privacy / compliance / cross-tenant data sharing."""

    requires_legal_signoff: bool = False
    """True for flags affecting external contracts / cross-tenant relationships."""

    related_audit_report: str = ""
    """Path to audit report if this flag has one (e.g. for Phase 250 gaps)."""

    minimum_plan_order: int = 0
    """Minimum plan.order value required for this feature flag to be active.
    0 = available to all plans, 2 = Growth+, 3 = Pro+."""


# ---------------------------------------------------------------------------
# REGISTRY — every per-tenant feature flag MUST appear here.
# Sorted by Phase + flag name for stable diff churn.
# ---------------------------------------------------------------------------

_PHASE_240_INTRODUCED = datetime(2026, 3, 1, tzinfo=UTC)
_PHASE_250_INTRODUCED = datetime(2026, 5, 3, tzinfo=UTC)


REGISTRY: tuple[FeatureFlag, ...] = (
    # ─── Phase 240 — DQ feature (Phase 240.4.B per D240.18) ────────────────
    FeatureFlag(
        name="data_quality_enabled",
        description="Enables the DQ feature for the tenant. Kill-switch — opt-in feature.",
        owner_team="dq-eng",
        owner_email="dq-eng@meshant.com",
        created_at=_PHASE_240_INTRODUCED,
        stage="GA",
        retire_by=datetime(2027, 3, 1, tzinfo=UTC),  # annual review
        default_existing_tenants=True,
        default_new_tenants=False,
        related_phase="Phase 240.4.B",
        related_design_doc="D240.9 / D240.18",
    ),
    FeatureFlag(
        name="data_quality_advanced_enabled",
        description="Gates advanced DQ endpoints (trends / scorecards / anomalies / RCA). Power-user opt-in feature.",
        owner_team="dq-eng",
        owner_email="dq-eng@meshant.com",
        created_at=_PHASE_240_INTRODUCED,
        stage="GA",
        retire_by=datetime(2027, 3, 1, tzinfo=UTC),
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 240.3.B",
        related_design_doc="D240.9",
    ),
    # ─── Phase 250 — Asset Creation Hardening ──────────────────────────────
    FeatureFlag(
        name="compliance_fail_closed_enabled",
        description="When True, asset creation is rejected if compliance gate fails. "
        "When False, falls back to legacy create-then-validate (Phase 250 deprecation window).",
        owner_team="asset-creation-eng",
        owner_email="asset-creation-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="CANARY",
        retire_by=datetime(2026, 8, 1, tzinfo=UTC),  # move to GA after 30d soak
        default_existing_tenants=False,  # 30-day soak per D250.12
        default_new_tenants=True,
        related_phase="Phase 250.1.A",
        related_design_doc="D250.2 / D250.12",
        related_audit_event="TENANT_COMPLIANCE_FAIL_CLOSED_FLIPPED",
    ),
    FeatureFlag(
        name="allow_intake_on_compliance_degraded",
        description="When True AND compliance circuit is OPEN, allow asset creation in permissive mode "
        "(emergency-override only). When False (default), block with retry-after.",
        owner_team="asset-creation-eng",
        owner_email="asset-creation-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="CANARY",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 250.1.A",
        related_design_doc="D250.9",
        related_audit_event="TENANT_PERMISSIVE_MODE_FLIPPED",
    ),
    FeatureFlag(
        name="federated_import_enabled",
        description="Per-tenant flag for federated marketplace import. Default OFF; requires DPO + Legal signoff.",
        owner_team="asset-creation-eng",
        owner_email="asset-creation-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 250.5.A",
        related_design_doc="D250.3 / D250.16",
        related_audit_event="TENANT_FEDERATED_IMPORT_FLIPPED",
        requires_dpo_signoff=True,
        requires_legal_signoff=True,
    ),
    FeatureFlag(
        name="asset_creation_enabled",
        description="Per-tenant kill-switch for asset creation. Default ON for existing tenants; "
        "OFF until onboarding completion for new tenants.",
        owner_team="asset-creation-eng",
        owner_email="asset-creation-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="GA",
        retire_by=datetime(2027, 5, 1, tzinfo=UTC),
        default_existing_tenants=True,
        default_new_tenants=False,
        related_phase="Phase 250.6.A",
        related_design_doc="D250.17",
        related_audit_event="TENANT_ASSET_CREATION_FLIPPED",
    ),
    FeatureFlag(
        name="asset_auto_activate_on_gate_pass",
        description="When True, asset auto-activates when all gates PASS. When False, manual activation required.",
        owner_team="asset-creation-eng",
        owner_email="asset-creation-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=True,
        default_new_tenants=True,
        related_phase="Phase 250.2.A",
        related_design_doc="D250.2",
    ),
    FeatureFlag(
        name="compliance_intake_gate_enabled",
        description="When True, the compliance intake gate must PASS before asset creation "
        "proceeds. When False, gate failures are logged but not blocking.",
        owner_team="compliance-eng",
        owner_email="compliance-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="CANARY",
        retire_by=datetime(2026, 8, 1, tzinfo=UTC),
        default_existing_tenants=False,
        default_new_tenants=True,
        related_phase="Phase 260",
        related_design_doc="D260.1",
        related_audit_event="COMPLIANCE_INTAKE_GATE_FLIPPED",
    ),
    FeatureFlag(
        name="compliance_audit_full_sampling",
        description="When True, every GET /files/{id}/ emits FILE_METADATA_VIEWED. When False, ~10% deterministic sample.",
        owner_team="compliance-eng",
        owner_email="compliance-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="CANARY",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 260.2.F",
        related_design_doc="D260.2",
        related_audit_event="FILE_METADATA_VIEWED",
    ),
    # ─── Phase 285.13.10 — Tier-gated feature flags ──────────────────────
    FeatureFlag(
        name="data_mesh_enabled",
        description="Gates Data Mesh topology and governance endpoints.",
        owner_team="mesh-eng",
        owner_email="mesh-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=2,
    ),
    FeatureFlag(
        name="semantic_custom_ontology_enabled",
        description="Gates custom ontology upload for semantic search.",
        owner_team="semantic-eng",
        owner_email="semantic-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=2,
    ),
    FeatureFlag(
        name="pipeline_dependency_enabled",
        description="Gates pipeline dependency graph and orchestration features.",
        owner_team="orchestration-eng",
        owner_email="orchestration-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=2,
    ),
    FeatureFlag(
        name="semantic_search_enabled",
        description="Gates semantic (vector) search for the tenant.",
        owner_team="search-eng",
        owner_email="search-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=3,
    ),
    FeatureFlag(
        name="semantic_graphql_ld_enabled",
        description="Gates GraphQL-LD endpoint for linked data queries.",
        owner_team="semantic-eng",
        owner_email="semantic-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=3,
    ),
    FeatureFlag(
        name="workflows_enabled",
        description="Gates orchestration workflow engine for the tenant.",
        owner_team="orchestration-eng",
        owner_email="orchestration-eng@meshant.com",
        created_at=_PHASE_250_INTRODUCED,
        stage="DRAFT",
        retire_by=None,
        default_existing_tenants=False,
        default_new_tenants=False,
        related_phase="Phase 285.13.10",
        related_design_doc="D285.13",
        minimum_plan_order=0,
    ),
)


def get_flag(name: str) -> FeatureFlag | None:
    """Return the registry entry for ``name``, or None if absent."""
    for flag in REGISTRY:
        if flag.name == name:
            return flag
    return None


def all_flags_in_stage(stage: FeatureFlagStage) -> tuple[FeatureFlag, ...]:
    """Return all flags currently in ``stage``."""
    return tuple(f for f in REGISTRY if f.stage == stage)


def stale_flags(now: datetime | None = None) -> tuple[FeatureFlag, ...]:
    """Return flags whose ``retire_by`` is in the past (i.e. retirement
    is overdue). Caller decides severity classification.
    """
    if now is None:
        now = datetime.now(tz=UTC)
    return tuple(f for f in REGISTRY if f.retire_by is not None and f.retire_by < now)


def is_tier_at_least(tenant, minimum_order: int) -> bool:
    """Return True if ``tenant.plan.order >= minimum_order``.

    Returns False when the tenant has no plan, or the plan has no
    ``order`` attribute.

    Usage::

        if is_tier_at_least(request.tenant, 2):
            # Growth-tier (order ≥ 2) feature path
    """
    plan = getattr(tenant, "plan", None)
    if plan is None:
        return False
    order = getattr(plan, "order", 0) or 0
    return order >= minimum_order


def is_sensitive(name: str) -> bool:
    """Return True when a feature flag requires the sensitive-flip (multi-step
    approval) path in ``admin_feature_flag_views``.

    A flag is considered sensitive when it carries an
    ``related_audit_event`` or requires DPO / Legal sign-off
    — i.e. its flip has security, privacy, or contractual impact.
    """
    flag = get_flag(name)
    if flag is None:
        return False
    return bool(
        flag.related_audit_event or flag.requires_dpo_signoff or flag.requires_legal_signoff
    )


__all__ = [
    "REGISTRY",
    "FeatureFlag",
    "FeatureFlagStage",
    "all_flags_in_stage",
    "get_flag",
    "is_sensitive",
    "is_tier_at_least",
    "stale_flags",
]
