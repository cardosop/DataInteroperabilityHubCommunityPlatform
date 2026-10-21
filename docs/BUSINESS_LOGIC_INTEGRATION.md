# Business Logic Integration Documentation

This document describes how business logic is integrated across the platform's services and how
the business rules framework ensures consistent validation throughout the system.

## Business Rules Framework

The business rules framework provides a structured, chain-based approach to validation across
multiple domains. Each business rule validates a specific aspect of an operation, and rules are
composed into ordered chains via `@register_chain("chain.name")`.

### Framework Components

- **Base Classes** (`hub/apps/core/business_rules/base.py`) — abstract foundation for all rule implementations (`BusinessRules`, `RuleExecutionContext`)
- **Common Utilities** (`hub/apps/core/business_rules/utils.py`) — shared validation helpers: `get_field_path` (dotted-path nested dict access), `validate_tenant_context` (tenant-ID consistency check), `check_value_overlap` (value overlap detection), `collect_errors` (declarative error collection), `make_validation_result` (convenience constructor)
- **Chain Registry** (`hub.apps/core/business_rules/chain_registry.py`) — centralized registration of all business rule chains
- **Chain Runner** — `execute_chain("chain.name", ctx, **kwargs)` executes an ordered sequence of rules
- **Registry** (`hub/apps/core/business_rules/registry.py`) — decorator-based registration of individual rules (`@register_rule`)
- **Validation Result**: Standardized output with domain-specific variants for contracts, mesh, and virtualization

### Existing Chains

| Chain | Steps | Owner |
|---|---|---|
| `contract.publish` | TenantScoping → StructuralFloor → ContractValidation | contracts |
| `asset.activate` | TenantScoping → AssetActivation | assets |
| `marketplace.listing.publish` | TenantScoping → KYB → ComplianceThreshold → ListingValidation | marketplace |
| `governance.approval.advance` | TenantScoping → ApproverIdentity → ApprovalStage → ApprovalQuorum | governance |
| `semantic.query.execute` | TenantFlag → SPARQLSyntax → SPARQLComplexity | semantic |

### Integration Points

Business rules are invoked at service-layer boundaries:
- **Contract service**: validates publish, archive, and version operations
- **Asset service**: validates activation and deactivation
- **Marketplace service**: validates listing publish and order creation
- **Governance service**: validates access request approval advancement
- **Semantic service**: validates SPARQL query execution

### Decision Tree for New Validations

1. Single rule check → direct `XxxBusinessRules(...).validate_*()` instantiation
2. Multi-rule check with ordering → register a chain, invoke via `execute_chain()`
3. Side effects after validation → fire AFTER chain returns PASS
4. Async job validation → wrap in `transaction.atomic()`, set `ctx.metadata["is_async"]=True`

### Audit

All chain executions emit audit events with `audit_retention_category='business_rules'`.
Chain events are retained for 30 days per the Phase 234.5 retention policy.

### Anti-Patterns to Avoid

- **Bypassing chains**: Do not call `XxxBusinessRules(...).validate_*()` directly in services/views when a
  registered chain exists for the operation. Use `execute_chain()` instead. The `prefer-chain` semgrep
  rule enforces this at CI.
- **Missing tenant scoping**: Every chain must start with a `TenantScoping` step to ensure the
  operation is scoped to the correct tenant.
- **Silent degradation**: When a rule in a chain fails, the chain should fail fast with a clear error
  code. Do not catch and suppress rule failures silently.

#### VirtualizationService ✅ (Implemented - Phase 9.5.3)

The VirtualizationService integrates with the business rules framework to validate federated query
execution. Virtual dataset creation and query execution go through `semantic.query.execute` chain
which validates SPARQL syntax and complexity.

#### Virtualization Business Rules ✅ (Implemented - Phase 9.5.3)

Virtualization-specific business rules include:
- **VirtualDatasetValidation**: Ensures virtual dataset configurations reference valid external sources
- **FederatedQueryValidation**: Validates federated query structure and source availability
- **ConnectionPoolValidation**: Ensures external connection pools are within configured limits
