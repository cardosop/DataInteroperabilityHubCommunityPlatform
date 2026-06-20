# Business Rules Framework Guide

Comprehensive guide for the Data Interoperability Hub Business Rules Framework.

## Overview

The Business Rules Framework provides a structured, auditable approach to validating business constraints across the platform. It ensures all domain rules are applied consistently, with proper tenant isolation, chain-based composition, and comprehensive audit logging.

Key components:
- `BusinessRules` base class in `hub/apps/core/business_rules/base.py` — foundational abstraction for all rule implementations
- `ValidationResult` — standardized output of all rule evaluations
- `BusinessRulesRegistry` in `hub/apps/core/business_rules/registry.py` — central registry for rule classes
- `RuleExecutionContext` — contextual data passed to rules during evaluation
- Chain system via `@register_chain` decorator — ordered multi-rule composition

## Architecture

The framework follows a layered architecture:

1. **Base Layer** — `BusinessRules` base class defining the validation contract
2. **Domain Layer** — Domain-specific rule implementations (AssetsBusinessRules, ContractsBusinessRules, etc.)
3. **Chain Layer** — Composed rule sequences registered via `@register_chain`
4. **Execution Layer** — `RuleExecutionContext` carrying tenant, user, and audit context
5. **Registry Layer** — `BusinessRulesRegistry` providing runtime discovery

## Framework Features

### 1. Caching

Rule evaluation results are cached to reduce redundant validation. Cache configuration:
- Default TTL: 300 seconds (5 minutes)
- Cache key prefix: `business_rules:validation`
- Cache keys follow the format: `business_rules:validation:<tenant_id>:<rule_name>:<resource_hash>`

### 2. Metrics

The framework emits the following Prometheus metrics:
- `business_rules_executions_total` — Counter of rule evaluations by rule name and result
- `business_rules_duration_seconds` — Histogram of rule evaluation duration
- `business_rules_results_total` — Counter of validation results by status (pass/fail/warn)

### 3. Tracing

OpenTelemetry tracing is integrated into rule evaluation:
- Each chain execution creates a span named `business_rules.chain.<chain_name>`
- Each rule evaluation creates a child span named `business_rules.rule.<rule_name>`
- Span attributes include `tenant_id`, `resource_type`, `resource_id`, and `result`

### 4. Structured Logging

All rule evaluations emit structured log entries via `structlog`:
- Log level: INFO for pass, WARNING for validation warnings, ERROR for failures
- Bound context: `tenant_id`, `user_id`, `rule_name`, `resource_type`, `resource_id`
- Audit events use `audit_retention_category='business_rules'` with 30-day retention

## Business Rules Classes

The following business rules classes are registered in the framework:

#### 1. `AssetsBusinessRules`
**Location**: `hub/apps/assets/business_rules.py`
**Purpose**: Validates asset lifecycle transitions, activation requirements, and retirement constraints.
**Validation Capabilities**: Asset lifecycle validation, activation prerequisite checking, retirement constraint enforcement, version increment validation.

#### 2. `ContractsBusinessRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Purpose**: Validates contract structure, publication readiness, and status transitions.
**Validation Capabilities**: Contract structural validation, publication gate checking, status transition enforcement, ODPS schema validation.

#### 3. `DatasetsBusinessRules`
**Location**: `hub/apps/datasets/business_rules.py`
**Purpose**: Validates dataset schema changes, ingestion requirements, and quality thresholds.
**Validation Capabilities**: Schema compatibility checking, ingestion source validation, quality threshold enforcement.

#### 4. `ComplianceBusinessRules`
**Location**: `hub/apps/compliance/business_rules.py`
**Purpose**: Validates compliance regime applicability and regulatory requirements.
**Validation Capabilities**: Regime applicability checking, DPIA requirement validation, RoPA generation rules.

#### 5. `DQBusinessRules`
**Location**: `hub/apps/dq/business_rules.py`
**Purpose**: Validates data quality check configurations and result thresholds.
**Validation Capabilities**: DQ profile validation, rule configuration checking, result threshold enforcement.

#### 6. `GovernanceBusinessRules`
**Location**: `hub/apps/governance/business_rules.py`
**Purpose**: Validates access request transitions, approval chains, and policy compliance.
**Validation Capabilities**: Access request lifecycle validation, approval chain sequencing, ABAC policy evaluation.

#### 7. `MarketplaceBusinessRules`
**Location**: `hub/apps/marketplace/business_rules.py`
**Purpose**: Validates listing publication, order fulfillment, and entitlement requirements.
**Validation Capabilities**: Listing publication gate checking, KYB verification, order fulfillment validation, entitlement grant enforcement.

#### 8. `ODPSBusinessRules`
**Location**: `hub/apps/odps/business_rules.py`
**Purpose**: Validates ODPS document structure and lifecycle transitions.
**Validation Capabilities**: ODPS document validation, cross-reference integrity, lifecycle state management.

#### 9. `ODPSNormalizationRules`
**Location**: `hub/apps/odps/business_rules.py`
**Purpose**: Validates ODPS normalization procedures and output requirements.
**Validation Capabilities**: Normalization step validation, output format checking, schema compliance.

#### 10. `ODPSLinkingRules`
**Location**: `hub/apps/odps/business_rules.py`
**Purpose**: Validates ODPS cross-document linking and reference resolution.
**Validation Capabilities**: Link target validation, reference integrity, bidirectional link checking.

#### 11. `ODPSExportRules`
**Location**: `hub/apps/odps/business_rules.py`
**Purpose**: Validates ODPS export configurations and output formats.
**Validation Capabilities**: Export format validation, transformation rule checking, output compliance.

#### 12. `DataMeshBusinessRules`
**Location**: `hub/apps/data_mesh/business_rules.py`
**Purpose**: Validates data mesh topology changes and virtualization constraints.
**Validation Capabilities**: Topology change validation, virtualization constraint checking, mesh connectivity rules.

#### 13. `PolicyBusinessRules`
**Location**: `hub/apps/policies/business_rules.py`
**Purpose**: Validates policy definitions, including retention and lifecycle policies.
**Validation Capabilities**: Policy structure validation, retention rule checking, lifecycle policy enforcement.

#### 14. `TopologyBusinessRules`
**Location**: `hub/apps/data_mesh/business_rules.py`
**Purpose**: Validates data mesh topology configurations and connectivity rules.
**Validation Capabilities**: Topology configuration validation, connectivity rule enforcement, partition checking.

#### 15. `VirtualizationBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Purpose**: Validates virtual dataset definitions and query configurations.
**Validation Capabilities**: Virtual dataset validation, query configuration checking, source mapping enforcement.

#### 16. `QueryExecutionBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Purpose**: Validates query execution parameters and resource limits.
**Validation Capabilities**: Query parameter validation, resource limit checking, execution timeout enforcement.

#### 17. `ResultBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Purpose**: Validates query result formats and delivery configurations.
**Validation Capabilities**: Result format validation, delivery configuration checking, output schema enforcement.

#### 18. `OrchestrationBusinessRules`
**Location**: `hub/apps/orchestration/business_rules.py`
**Purpose**: Validates workflow definitions, step configurations, and dependency chains.
**Validation Capabilities**: Workflow definition validation, step dependency checking, execution order enforcement.

#### 19. `NotificationsBusinessRules`
**Location**: `hub/apps/notifications/business_rules.py`
**Purpose**: Validates notification configurations, templates, and delivery rules.
**Validation Capabilities**: Template validation, delivery rule checking, opt-out enforcement.

#### 20. `SearchBusinessRules`
**Location**: `hub/apps/search/business_rules.py`
**Purpose**: Validates search index configurations and query templates.
**Validation Capabilities**: Index configuration validation, query template checking, throttle rule enforcement.

#### 21. `SemanticBusinessRules`
**Location**: `hub/apps/semantic/business_rules.py`
**Purpose**: Validates semantic mapping configurations and RDF transformations.
**Validation Capabilities**: Mapping configuration validation, RDF transformation checking, vocabulary compliance.

#### 22. `WebhooksBusinessRules`
**Location**: `hub/apps/webhooks/business_rules.py`
**Purpose**: Validates webhook endpoint configurations and payload schemas.
**Validation Capabilities**: Endpoint URL validation, payload schema checking, retry configuration enforcement.

#### 23. `ScheduledIngestionBusinessRules`
**Location**: `hub/apps/scheduled_ingestion/business_rules.py`
**Purpose**: Validates scheduled ingestion configurations and source connections.
**Validation Capabilities**: Schedule validation, source connection checking, ingestion window enforcement.

#### 24. `FilesBusinessRules`
**Location**: `hub/apps/files/business_rules.py`
**Purpose**: Validates file upload configurations, size limits, and type restrictions.
**Validation Capabilities**: File size validation, content type checking, upload quota enforcement.

#### 25. `JobsBusinessRules`
**Location**: `hub/apps/jobs/business_rules.py`
**Purpose**: Validates job configurations, retry policies, and concurrency limits.
**Validation Capabilities**: Job configuration validation, retry policy checking, concurrency limit enforcement.

## Getting Started

### Single Rule Validation

For simple, single-rule checks, instantiate the appropriate business rules class directly:

```python
from hub.apps.core.business_rules.base import BusinessRules
from hub.apps.assets.business_rules import AssetsBusinessRules

rules = AssetsBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = rules.validate(asset=asset, tenant=tenant, validation_type="lifecycle")
if not result.is_valid:
    raise ValidationError(result.errors)
```

### Using the Registry

Discover and instantiate rules through the central registry:

```python
from hub.apps.core.business_rules.registry import BusinessRulesRegistry

registry = BusinessRulesRegistry()
rule_class = registry.get("AssetsBusinessRules")
rules = rule_class(tenant_id=tenant_id, user_id=user_id)
```

### Multi-Rule Chains

For operations requiring multiple rules in sequence, use the chain registry:

```python
from hub.apps.core.business_rules.chain_registry import execute_chain

result = execute_chain("asset.activate", context={"asset": asset, "tenant": tenant})
```

## Advanced Usage

### Custom Rule Implementation

```python
from hub.apps.core.business_rules.base import BusinessRules, ValidationResult

class CustomBusinessRules(BusinessRules):
    def validate_custom_constraint(self, resource, context):
        errors = []
        if not resource.meets_threshold():
            errors.append("Resource does not meet threshold")
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[]
        )
```

### Custom Chain Registration

```python
from hub.apps.core.business_rules.chain_registry import register_chain

@register_chain("custom.resource.validate")
def validate_custom_resource(context):
    # Chain steps execute in order
    pass
```

### RuleExecutionContext

The `RuleExecutionContext` provides contextual data to rules:

```python
context = RuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    resource_type="ASSET",
    resource_id=asset_id,
    metadata={"source": "api"}
)
```

## Best Practices

1. **Use chains for multi-rule operations** — Chains provide auditability, rollback on failure, and consistent error handling.
2. **Always include tenant scoping** — Every chain or rule must verify the tenant context via `TenantScoping`.
3. **Emit audit events** — Every rule evaluation should produce an audit event with the appropriate retention category.
4. **Cache judiciously** — Use the caching layer for expensive validations but invalidate on state changes.
5. **Test independently** — Each rule should be independently testable with clear inputs and outputs.
6. **Document new chains** — Update this guide when adding new chains or rules.
7. **Use ValidationResult correctly** — Always return a `ValidationResult` with clear errors and warnings.

## Troubleshooting

### Common Issues

1. **Chain execution fails with RuntimeError** — Ensure an active `transaction.atomic()` context exists. Chains require database transaction context.
2. **Cache returns stale results** — Verify cache invalidation signals are properly connected. Check `business_rules:validation` prefix keys.
3. **Metrics not appearing** — Confirm Prometheus client is initialized and the metrics registry is properly configured.
4. **Rule validation blocks unexpectedly** — Check `Tenant.business_rules_chain_<name>_enabled` flag — chains may be gated per-tenant.
5. **Import errors for rule classes** — Verify the rule class is registered in `BusinessRulesRegistry` and the module is importable.
6. **Audit events missing** — Confirm `audit_retention_category='business_rules'` is set and the audit backend is available.

### Debugging Tips

- Enable DEBUG logging for `hub.apps.core.business_rules` to see rule evaluation details.
- Use the health endpoint: `GET /api/v1/health/business-rules` to check degraded rules.
- Check the `RULE_CHAIN_COMPLETED` audit events for chain execution traces.
- Monitor `business_rules_executions_total` and `business_rules_duration_seconds` metrics for performance issues.

## See Also

- [BUSINESS_RULES_FRAMEWORK_REVIEW.md](./BUSINESS_RULES_FRAMEWORK_REVIEW.md) — Framework completeness review
- `hub/apps/core/business_rules/base.py` — BusinessRules base class
- `hub/apps/core/business_rules/registry.py` — BusinessRulesRegistry
- `hub/apps/core/business_rules/chain_registry.py` — Chain registration and execution
