"""
Phase 274.7 — the provider-agnostic RuleChains.

Each chain is registered by its OWNING app at AppConfig.ready() time
(the Phase 313.1 convention): the provider-agnostic chains live here
(``contract.publish`` / ``asset.activate`` / ``governance.approval.
advance``); the paid/provider chains live with their owners
(``marketplace.listing.publish`` in marketplace/chains.py,
``semantic.query.execute`` in semantic/chains.py, the databricks chains
in databricks_admin/chains.py — the W4.6 provider-boundary move: this
module MUST NOT import provider estate code). Chain registrations are
idempotent — re-importing overwrites the previous chain with the same
name.
"""

from __future__ import annotations

from hub.apps.core.business_rules.chains import (
    register_chain,
)

# ── contract.publish ──────────────────────────────────────────────


@register_chain("contract.publish")
def _contract_publish_chain():
    from hub.apps.contracts.business_rules import ContractsBusinessRules, StructuralFloorRule

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
        return rule.validate_structural_floor(
            hub_contract,
            spec_type=getattr(contract, "original_spec_type", ""),
            spec_version=getattr(contract, "original_spec_version", ""),
            contract_id=str(getattr(contract, "id", "")),
            warnings=getattr(contract, "normalization_warnings", None) or [],
        )

    def _contract_validation(ctx, **kwargs):
        contract = kwargs.get("contract")
        if contract is None:
            from hub.apps.core.business_rules.base import ValidationResult

            return ValidationResult(is_valid=True)
        rules = ContractsBusinessRules(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
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
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
        )
        return rule.validate_activation(asset)

    return [_tenant_scoping, _activation_gate]


# ── marketplace.listing.publish ────────────────────────────────────


@register_chain("governance.approval.advance")
def _governance_approval_advance_chain():
    from hub.apps.governance.business_rules import (
        ApprovalQuorumRule,
        ApprovalStageRule,
        ApproverIdentityRule,
    )

    def _tenant_scoping(ctx, **kwargs):
        from hub.apps.core.business_rules.base import ValidationResult

        tenant = kwargs.get("tenant")
        if tenant is None:
            return ValidationResult(is_valid=False, errors=["Tenant context required"])
        return ValidationResult(is_valid=True)

    def _approver_identity(ctx, **kwargs):
        rule = ApproverIdentityRule(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
        )
        return rule.validate(
            kwargs.get("access_request"), kwargs.get("tenant"), kwargs.get("approver")
        )

    def _approval_stage(ctx, **kwargs):
        rule = ApprovalStageRule(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
        )
        return rule.validate_transition(
            kwargs.get("access_request"), kwargs.get("tenant"), kwargs.get("approver")
        )

    def _approval_quorum(ctx, **kwargs):
        rule = ApprovalQuorumRule(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
        )
        # W2.4 — pass the approver so the segregation-of-duties check
        # (no same approver on two consecutive steps) runs in the chain.
        return rule.validate(
            kwargs.get("access_request"),
            kwargs.get("tenant"),
            approver=kwargs.get("approver"),
        )

    return [_tenant_scoping, _approver_identity, _approval_stage, _approval_quorum]


# ── semantic.query.execute ────────────────────────────────────────
# (lives in hub/apps/semantic/chains.py — the Phase 313.1 owning-app
# convention: each app registers its own chains at AppConfig.ready();
# this registry module holds only the provider-agnostic chains.)

