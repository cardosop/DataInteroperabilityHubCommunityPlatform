"""Databricks business-rules chains (openspec add-databricks-uc-write
task 2.7 / add-databricks-sql-warehouses task 3.4) — the Phase 274
chains, REGISTERED HERE in the owning estate app (the 313.1 owning-app
convention; W4.6 moved the registrations out of the core chain
registry, which holds no estate reference — ``apps.py::ready()``
imports this module):

- ``databricks.uc.change.request`` — TenantScoping → structural payload
  build (the 2.2 ``build_ddl_payload`` bridge) → identifier regex →
  denylist (OUTERMOST safety — a flag-off destructive request fails
  with ``DATABRICKS_DDL_DENYLISTED`` before anything else).
- ``databricks.uc.change.approve`` — TenantScoping → stage validation
  (the 2.2 service's approvable set — PENDING_APPROVAL AND
  PENDING_NEXT_APPROVER) → approver authorization (the 2.2 service's
  ``_step_authorizes`` + ``_authorize_via_delegation`` pair — the 272.6
  delegation logic reused, never duplicated).
- ``databricks.uc.change.execute`` — TenantScoping → stage check
  (APPROVED) → idempotency pre-check (the payload's local half — the
  network existence check stays in the 2.3 executor).
- ``databricks.grant.apply`` — TenantScoping → ownership refusal →
  securable validation → ABAC plan (the 2.6 planner; the plan is
  stashed on the chain context for the caller's apply/verify legs).
- ``databricks.warehouse.create`` (3.4) — TenantScoping → tier gate
  (the tenant's plan tier → allowed size set, serverless included) →
  per-tenant quota (the plan limit ``max_databricks_warehouses`` via
  the repo's plan-limit stack) → structural validation — ALL before any
  network call (the chain has no network surface by construction).
- ``databricks.dlt.create`` (10.4) — TenantScoping → settings allowlist
  (the payload envelope: dict shape, workspace ownership, and the key
  allowlist — the create vocabulary ``name``/``edition``/``clusters``/
  ``libraries``/``target``/``continuous``/``development``/``photon``/
  ``notifications``/``catalog``/``channel``) → cluster policy (EVERY
  cluster carries a policy id — the D4 cost-governance discipline) →
  channel (the 10.2 model enum's vocabulary).

Guard failures carry their machine-readable codes through the chain
runner's error strings (``[CODE] message``) so callers and pins can
route on them. The framework's side-effect contract (nothing fires
until all steps PASS) is inherited — these chains add no side effects
of their own.
"""

from __future__ import annotations


def _fail(code: str, message: str):
    from hub.apps.core.business_rules.base import ValidationResult

    return ValidationResult(is_valid=False, errors=[f"[{code}] {message}"])


def _pass():
    from hub.apps.core.business_rules.base import ValidationResult

    return ValidationResult(is_valid=True)


# ── databricks.uc.change.request ─────────────────────────────────────────────


def _uc_change_request_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention): a missing
        # tenant context is a caller error, not a guard failure.
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _structural_payload(ctx, **kwargs):
        request = kwargs.get("request")
        if request is None:
            return _fail("DATABRICKS_DDL_INVALID_IDENTIFIER", "request required")
        from hub.apps.core.services.base import ValidationError
        from hub.apps.databricks_admin.uc_changes import build_ddl_payload

        try:
            payload = build_ddl_payload(request)
        except (ValidationError, ValueError) as exc:
            return _fail("DATABRICKS_DDL_INVALID_IDENTIFIER", str(exc))
        ctx.metadata["uc_ddl_payload"] = payload
        return _pass()

    def _identifier_regex(ctx, **_kwargs):
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            validate_uc_identifiers,
        )

        payload = ctx.metadata.get("uc_ddl_payload")
        try:
            validate_uc_identifiers(payload)
        except UCDdlSafetyError as exc:
            return _fail(
                getattr(exc, "code", "DATABRICKS_DDL_INVALID_IDENTIFIER"), str(exc)
            )
        return _pass()

    def _denylist(ctx, **kwargs):
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            assert_not_denylisted,
        )

        payload = ctx.metadata.get("uc_ddl_payload")
        try:
            assert_not_denylisted(payload, tenant=kwargs.get("tenant"))
        except UCDdlSafetyError as exc:
            return _fail(getattr(exc, "code", "DATABRICKS_DDL_DENYLISTED"), str(exc))
        return _pass()

    return (_tenant_scoping, _structural_payload, _identifier_regex, _denylist)


# ── databricks.uc.change.approve ─────────────────────────────────────────────


def _uc_change_approve_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention).
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _stage_validation(_ctx, **kwargs):
        # The 2.2 service's approvable set — REUSED, not re-implemented:
        # PENDING_NEXT_APPROVER is the 272.4 intermediate state, and the
        # chain must not be stricter than the service it guards.
        from hub.apps.databricks_admin.uc_changes import _APPROVABLE_STATUSES

        request = kwargs.get("request")
        if request is None or request.status not in _APPROVABLE_STATUSES:
            return _fail(
                "uc_change_not_approvable",
                "approval requires status PENDING_APPROVAL or PENDING_NEXT_APPROVER",
            )
        return _pass()

    def _approver_authorization(_ctx, **kwargs):
        # The 2.2 service's authorization pair — _step_authorizes AND the
        # 272.6 delegation fallback (_authorize_via_delegation): the chain
        # must agree with approve_change_request, which accepts a
        # delegation-mediated approver.
        from hub.apps.databricks_admin.uc_changes import (
            _authorize_via_delegation,
            _effective_step,
            _step_authorizes,
        )

        request = kwargs.get("request")
        approver = kwargs.get("approver")
        if approver is None:
            return _fail("uc_change_approver_unauthorized", "approver required")
        step = _effective_step(request)
        authorized, reason = _step_authorizes(step, approver)
        if not authorized and not _authorize_via_delegation(request, approver, step):
            return _fail(
                "uc_change_approver_unauthorized", reason or "approver unauthorized"
            )
        return _pass()

    return (_tenant_scoping, _stage_validation, _approver_authorization)


# ── databricks.uc.change.execute ─────────────────────────────────────────────


def _uc_change_execute_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention): a missing
        # tenant context is a caller error, not a guard failure.
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _stage_check(_ctx, **kwargs):
        from hub.apps.databricks_admin.models import UCChangeRequestStatus

        request = kwargs.get("request")
        if request is None or request.status != UCChangeRequestStatus.APPROVED:
            # 2.9 — the execute-refusal carries the 403 code the API
            # boundary maps to DATABRICKS_DDL_APPROVAL_REQUIRED.
            return _fail(
                "DATABRICKS_DDL_APPROVAL_REQUIRED",
                "execution requires status APPROVED",
            )
        return _pass()

    def _idempotency_pre_check(ctx, **kwargs):
        from hub.apps.core.services.base import ValidationError
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            validate_uc_identifiers,
        )
        from hub.apps.databricks_admin.uc_changes import build_ddl_payload

        request = kwargs.get("request")
        try:
            payload = build_ddl_payload(request)
            validate_uc_identifiers(payload)
        except UCDdlSafetyError as exc:
            return _fail(
                getattr(exc, "code", "DATABRICKS_DDL_INVALID_IDENTIFIER"), str(exc)
            )
        except (ValidationError, ValueError) as exc:
            return _fail("DATABRICKS_DDL_INVALID_IDENTIFIER", str(exc))
        ctx.metadata["uc_ddl_payload"] = payload
        return _pass()

    return (_tenant_scoping, _stage_check, _idempotency_pre_check)


# ── databricks.grant.apply ───────────────────────────────────────────────────


def _grant_apply_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention).
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _ownership_refusal(_ctx, **kwargs):
        from hub.apps.governance.models import AccessPolicy

        tenant = kwargs.get("tenant")
        for policy in AccessPolicy.objects.filter(tenant=tenant, effect="ALLOW"):
            grant = (policy.conditions or {}).get("uc_grant")
            if not isinstance(grant, dict):
                continue
            privileges = grant.get("privileges") or []
            if any(p in ("OWN", "OWNERSHIP") for p in privileges):
                return _fail(
                    "DATABRICKS_GRANT_UNSUPPORTED",
                    f"refusing OWNERSHIP grant in policy {policy.name} — "
                    "the DPO owns, the bridge never issues OWN",
                )
        return _pass()

    def _securable_validation(_ctx, **kwargs):
        from hub.apps.databricks_admin.uc_grants_bridge import _UC_SECURABLE_SEGMENTS
        from hub.apps.governance.models import AccessPolicy

        tenant = kwargs.get("tenant")
        for policy in AccessPolicy.objects.filter(tenant=tenant, effect="ALLOW"):
            grant = (policy.conditions or {}).get("uc_grant")
            if not isinstance(grant, dict):
                continue
            securable = str(grant.get("securable_type") or "")
            if securable not in _UC_SECURABLE_SEGMENTS:
                return _fail(
                    "DATABRICKS_GRANT_UNSUPPORTED",
                    f"unknown UC securable type '{securable}' in policy {policy.name}",
                )
        return _pass()

    def _abac_plan(ctx, **kwargs):
        from hub.apps.databricks_admin.uc_grants_bridge import (
            UCGrantBridgeError,
            plan_uc_grants,
        )

        workspace = kwargs.get("workspace")
        if workspace is None:
            return _fail("DATABRICKS_GRANT_UNSUPPORTED", "workspace required")
        try:
            intended = plan_uc_grants(workspace)
        except UCGrantBridgeError as exc:
            return _fail(getattr(exc, "code", "DATABRICKS_GRANT_UNSUPPORTED"), str(exc))
        ctx.metadata["uc_grant_plan"] = intended
        return _pass()

    return (_tenant_scoping, _ownership_refusal, _securable_validation, _abac_plan)


# ── databricks.warehouse.create (openspec add-databricks-sql-warehouses 3.4) ─


# The classic size vocabulary (the model's help_text surface). The tuple
# is ORDERED by capacity — the tier allowlists below slice it.
CLASSIC_WAREHOUSE_SIZES: tuple[str, ...] = (
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "2XL",
    "3XL",
    "4XL",
)

# Serverless is tier-gated as its own "size" (D3: "serverless and
# classic tiers"). A serverless warehouse costs the workspace's
# serverless compute pool — FREE tenants (classic-only) don't get it.
_SERVERLESS_TOKEN = "SERVERLESS"

# Plan tier → allowed size set. FREE caps at S (trial-scale), PRO at L,
# ENTERPRISE carries every classic tier + serverless. Unknown tiers
# resolve to NO entry — the tier gate fails closed on them.
TIER_ALLOWED_WAREHOUSE_SIZES: dict[str, frozenset[str]] = {
    "FREE": frozenset({"XS", "S"}),
    "PRO": frozenset({"XS", "S", "M", "L", _SERVERLESS_TOKEN}),
    "ENTERPRISE": frozenset({*CLASSIC_WAREHOUSE_SIZES, _SERVERLESS_TOKEN}),
}


def _resolve_plan_tier(tenant):
    """The check_limit plan-resolution rule (tenants/services.py): the
    tenant's own plan wins; without one the ACTIVE free plan is the
    baseline; nothing resolvable → None (the gate fails closed)."""
    from hub.apps.tenants.models import TenantPlan

    plan_id = getattr(tenant, "plan_id", None)
    if plan_id:
        plan = TenantPlan.objects.filter(id=plan_id).first()
        if plan is not None:
            return plan.tier
    free = TenantPlan.objects.filter(slug="free", is_active=True).first()
    return free.tier if free is not None else None


def _warehouse_create_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention).
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _tier_gate(_ctx, **kwargs):
        """The requested size token against the tenant's plan allowlist.

        Malformed requests (no dict payload, no size for a classic
        create, an unknown size token) are refused with INVALID_CONFIG
        here — the gate cannot classify a token it cannot extract, and
        D3's tier→quota→structural order still holds for every
        well-formed request (a malformed one never reaches the quota).
        """
        tenant = kwargs.get("tenant")
        payload = kwargs.get("payload")
        if not isinstance(payload, dict):
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG", "payload must be an object"
            )
        if payload.get("serverless") is True:
            token = _SERVERLESS_TOKEN
        else:
            size = payload.get("size")
            if not isinstance(size, str) or not size.strip():
                return _fail(
                    "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                    "a classic warehouse requires a size tier",
                )
            if size not in CLASSIC_WAREHOUSE_SIZES:
                return _fail(
                    "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                    f"unknown classic size {size!r}",
                )
            token = size

        tier = _resolve_plan_tier(tenant)
        allowed = TIER_ALLOWED_WAREHOUSE_SIZES.get(tier) if tier else None
        if allowed is None:
            # Unknown/unresolvable tier — fail CLOSED (never a permissive
            # default, the 2.4 denylist discipline).
            return _fail(
                "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN",
                f"no size allowlist for plan tier {tier!r}",
            )
        if token not in allowed:
            return _fail(
                "DATABRICKS_WAREHOUSE_TIER_FORBIDDEN",
                f"size {token!r} is not allowed for the {tier} plan",
            )
        return _pass()

    def _quota(_ctx, **kwargs):
        """The per-tenant warehouse cap — the repo's plan-limit stack
        (PlanLimitService.check_limit: tenant row-lock serialization +
        the resource-counter count). An absent limit key means unlimited
        (the repo-wide plan-limit semantics; the 3.4 seed defaults +
        backfill migration carry the tier caps)."""
        from hub.apps.core.services.base import ValidationError as CoreValidationError
        from hub.apps.tenants.services import PlanLimitService

        tenant = kwargs.get("tenant")
        try:
            PlanLimitService(tenant_id=str(tenant.id)).check_limit(
                tenant_id=str(tenant.id),
                limit_key="max_databricks_warehouses",
                delta=1,
            )
        except CoreValidationError as exc:
            if getattr(exc, "code", None) == "plan_limit_exceeded":
                return _fail("DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED", str(exc))
            raise
        return _pass()

    def _structural_validation(_ctx, **kwargs):
        """The create-request shape (the 3.3 client's own ValueError
        contract, re-validated at the boundary): name, the serverless
        XOR size invariant, and a sane auto-stop window."""
        payload = kwargs.get("payload")  # dict — the tier gate refused
        # anything else before this step can run.
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG", "a warehouse name is required"
            )

        serverless = payload.get("serverless", False)
        if not isinstance(serverless, bool):
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG", "serverless must be a boolean"
            )
        size = payload.get("size")
        if serverless:
            if size is not None:
                return _fail(
                    "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                    "a serverless warehouse has no size tier (size must be absent)",
                )
        elif not isinstance(size, str) or size not in CLASSIC_WAREHOUSE_SIZES:
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                f"invalid classic size {size!r}",
            )

        auto_stop_mins = payload.get("auto_stop_mins", 30)
        if (
            not isinstance(auto_stop_mins, int)
            or isinstance(auto_stop_mins, bool)
            or auto_stop_mins < 0
        ):
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                "auto_stop_mins must be a non-negative integer",
            )

        workspace = kwargs.get("workspace")
        if workspace is not None and str(workspace.tenant_id) != str(
            kwargs["tenant"].id
        ):
            return _fail(
                "DATABRICKS_WAREHOUSE_INVALID_CONFIG",
                "workspace belongs to another tenant",
            )
        return _pass()

    return (_tenant_scoping, _tier_gate, _quota, _structural_validation)


# ── databricks.dlt.create (openspec add-databricks-dlt-pipelines 10.4) ──────


# The DLT create-request vocabulary (10.4's settings allowlist): the
# 10.2 model's documented settings surface (edition/clusters/libraries/
# target/continuous/development/photon/notifications/catalog) plus the
# request-level create fields (name, channel). An unknown key is a
# SETTING_FORBIDDEN refusal naming the key — the Hub never forwards a
# setting it has not vetted.
DLT_SETTINGS_ALLOWLIST: frozenset[str] = frozenset(
    {
        "name",
        "edition",
        "clusters",
        "libraries",
        "target",
        "continuous",
        "development",
        "photon",
        "notifications",
        "catalog",
        "channel",
    }
)


def _dlt_create_chain():
    def _tenant_scoping(_ctx, **kwargs):
        # Canonical scoping step (contract.publish convention).
        from hub.apps.core.business_rules.base import ValidationResult

        if kwargs.get("tenant") is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _settings_allowlist(_ctx, **kwargs):
        """The payload envelope: dict shape, workspace ownership (the
        3.4 discipline), then the key allowlist. An unknown key is a
        SETTING_FORBIDDEN refusal naming the key — never a silently
        dropped setting."""
        payload = kwargs.get("payload")
        if not isinstance(payload, dict):
            return _fail("DATABRICKS_DLT_INVALID_CONFIG", "payload must be an object")

        workspace = kwargs.get("workspace")
        if workspace is not None and str(workspace.tenant_id) != str(
            kwargs["tenant"].id
        ):
            return _fail(
                "DATABRICKS_DLT_INVALID_CONFIG",
                "workspace belongs to another tenant",
            )

        unknown = sorted(set(payload.keys()) - DLT_SETTINGS_ALLOWLIST)
        if unknown:
            return _fail(
                "DATABRICKS_DLT_SETTING_FORBIDDEN",
                "pipeline setting(s) outside the allowlist: "
                + ", ".join(repr(key) for key in unknown),
            )
        return _pass()

    def _cluster_policy(_ctx, **kwargs):
        """EVERY cluster in the spec carries a policy id (the D4
        cost-governance discipline — an ungoverned DLT cluster must
        never be creatable through the Hub)."""
        payload = kwargs.get("payload")  # dict — the allowlist step
        # refused anything else before this step can run.
        clusters = payload.get("clusters")
        if not isinstance(clusters, list) or not clusters:
            return _fail(
                "DATABRICKS_DLT_INVALID_CONFIG",
                "a DLT pipeline requires at least one cluster definition",
            )
        for entry in clusters:
            if not isinstance(entry, dict):
                return _fail(
                    "DATABRICKS_DLT_INVALID_CONFIG",
                    "each cluster must be an object",
                )
            policy_id = entry.get("policy_id")
            if not isinstance(policy_id, str) or not policy_id.strip():
                return _fail(
                    "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
                    "every DLT cluster requires a cluster policy id",
                )
        return _pass()

    def _channel(_ctx, **kwargs):
        """The release channel against the 10.2 model enum's vocabulary
        (the single source of truth for the wire values). Absent → the
        API's default applies (the model's NULL-able column)."""
        from hub.apps.databricks_admin.models import DatabricksDltChannel

        channel = kwargs.get("payload", {}).get("channel")
        if channel is None:
            return _pass()
        if channel not in DatabricksDltChannel.values:
            return _fail(
                "DATABRICKS_DLT_CHANNEL_INVALID",
                f"unknown DLT channel {channel!r} — expected one of "
                f"{list(DatabricksDltChannel.values)}",
            )
        return _pass()

    return (_tenant_scoping, _settings_allowlist, _cluster_policy, _channel)


# ── Registration (Phase 313.1 owning-app convention — W4.6) ────────────────
# The chains register HERE, in the estate app that owns the rules; the
# core chain registry holds only the provider-agnostic chains (the
# marketplace/semantic precedent). ``apps.py::ready()`` imports this
# module so the names resolve in every full-mode process; core-only
# processes never install this app, so the names stay absent there by
# construction (no ImportError-trap needed — the old core-side wrappers
# imported the builders lazily and could crash at chain-execution time).
from hub.apps.core.business_rules.chain_registry import register_chain


@register_chain("databricks.uc.change.request")
def _databricks_uc_change_request_chain():
    return _uc_change_request_chain()


@register_chain("databricks.uc.change.approve")
def _databricks_uc_change_approve_chain():
    return _uc_change_approve_chain()


@register_chain("databricks.uc.change.execute")
def _databricks_uc_change_execute_chain():
    return _uc_change_execute_chain()


@register_chain("databricks.grant.apply")
def _databricks_grant_apply_chain():
    return _grant_apply_chain()


@register_chain("databricks.warehouse.create")
def _databricks_warehouse_create_chain():
    return _warehouse_create_chain()


@register_chain("databricks.dlt.create")
def _databricks_dlt_create_chain():
    return _dlt_create_chain()
