"""
Phase 274.7 — Five registered RuleChains.

Each chain is imported by its owning app at AppConfig.ready() time.
The chain registrations are idempotent — re-importing overwrites the
previous chain with the same name.
"""
from __future__ import annotations
from hub.apps.core.business_rules.chains import register_chain, execute_chain, get_chain


# ── contract.publish ──────────────────────────────────────────────

@register_chain("contract.publish")
def _contract_publish_chain():
    from hub.apps.contracts.business_rules import StructuralFloorRule
    from hub.apps.contracts.business_rules import ContractsBusinessRules

    def _tenant_scoping(ctx, **kwargs):
        from hub.apps.core.business_rules.base import ValidationResult
        tenant = kwargs.get("tenant")
        if tenant is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _structural_floor(ctx, **kwargs):
        contract = kwargs.get("contract")
        if contract is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)  # no contract to validate
        rule = StructuralFloorRule()
        hub_contract = getattr(contract, "hub_contract_json", None)
        if hub_contract is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        return rule.validate_structural_floor(hub_contract)

    def _contract_validation(ctx, **kwargs):
        contract = kwargs.get("contract")
        if contract is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        rules = ContractsBusinessRules(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rules.validate_contract_creation(contract)

    return [_tenant_scoping, _structural_floor, _contract_validation]


# ── asset.activate ────────────────────────────────────────────────

@register_chain("asset.activate")
def _asset_activate_chain():
    from hub.apps.assets.business_rules import AssetActivationRule

    def _tenant_scoping(ctx, **kwargs):
        from hub.apps.core.business_rules.base import ValidationResult
        tenant = kwargs.get("tenant")
        if tenant is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _activation_gate(ctx, **kwargs):
        asset = kwargs.get("asset")
        if asset is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=False, errors=["Asset required"])
        rule = AssetActivationRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule.validate_activation(asset)

    return [_tenant_scoping, _activation_gate]


# ── marketplace.listing.publish ────────────────────────────────────

@register_chain("marketplace.listing.publish")
def _marketplace_listing_publish_chain():
    from hub.apps.marketplace.business_rules import (
        MarketplaceBusinessRules,
        KYBVerificationRule,
    )

    def _tenant_scoping(ctx, **kwargs):
        from hub.apps.core.business_rules.base import ValidationResult
        tenant = kwargs.get("tenant")
        if tenant is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _kyb_verification(ctx, **kwargs):
        listing = kwargs.get("listing")
        if listing is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        rule = KYBVerificationRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        # Phase 274.13 / 274.8 — call execute() instead of validate_kyb()
        # directly so the rule's per-execution observability hook fires:
        # Prometheus failure counter on rejection, canonical
        # business_rules.* OTel span attributes, and Sentry routing of
        # unexpected exceptions via track_error. The chain still receives
        # the canonical ValidationResult so its short-circuit + audit
        # semantics are unchanged.
        return rule.execute(
            context=ctx, asset=listing.asset, tenant=listing.tenant
        )

    def _compliance_threshold(ctx, **kwargs):
        listing = kwargs.get("listing")
        if listing is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        rule = MarketplaceBusinessRules(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule._check_compliance_threshold(listing)

    def _listing_validation(ctx, **kwargs):
        listing = kwargs.get("listing")
        if listing is None:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=False, errors=["Listing required"])
        rule = MarketplaceBusinessRules(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule.validate_listing_publication(listing)

    return [_tenant_scoping, _kyb_verification, _compliance_threshold, _listing_validation]


# ── governance.approval.advance ────────────────────────────────────

@register_chain("governance.approval.advance")
def _governance_approval_advance_chain():
    from hub.apps.governance.business_rules import (
        ApproverIdentityRule,
        ApprovalStageRule,
        ApprovalQuorumRule,
    )

    def _tenant_scoping(ctx, **kwargs):
        from hub.apps.core.business_rules.base import ValidationResult
        tenant = kwargs.get("tenant")
        if tenant is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _approver_identity(ctx, **kwargs):
        rule = ApproverIdentityRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule.validate(kwargs.get("access_request"), kwargs.get("tenant"), kwargs.get("approver"))

    def _approval_stage(ctx, **kwargs):
        rule = ApprovalStageRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule.validate_transition(kwargs.get("access_request"), kwargs.get("tenant"), kwargs.get("approver"))

    def _approval_quorum(ctx, **kwargs):
        rule = ApprovalQuorumRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rule.validate(kwargs.get("access_request"), kwargs.get("tenant"))

    return [_tenant_scoping, _approver_identity, _approval_stage, _approval_quorum]


# ── semantic.query.execute ────────────────────────────────────────

@register_chain("semantic.query.execute")
def _semantic_query_execute_chain():
    from hub.apps.semantic.business_rules import SemanticTenantFlagRule
    from hub.apps.search.business_rules import SearchBusinessRules

    def _tenant_flag(ctx, **kwargs):
        rule = SemanticTenantFlagRule(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        action = kwargs.get("action", "sparql")
        return rule.validate(action, kwargs.get("tenant"))

    def _sparql_syntax(ctx, **kwargs):
        query = kwargs.get("query", "")
        if not query:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        rules = SearchBusinessRules(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rules.validate_sparql_query(query)

    def _sparql_complexity(ctx, **kwargs):
        query = kwargs.get("query", "")
        if not query:
            from hub.apps.core.business_rules.base import ValidationResult
            return ValidationResult(is_valid=True)
        rules = SearchBusinessRules(
            tenant_id=ctx.tenant_id, user_id=ctx.user_id,
        )
        return rules.validate_sparql_complexity(query)

    return [_tenant_flag, _sparql_syntax, _sparql_complexity]

