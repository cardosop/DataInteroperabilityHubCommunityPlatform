# Business Rules Framework Guide

**Version:** 1.0
**Last Updated:** 2025-01-XX
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Framework Features](#framework-features)
4. [Business Rules Classes](#business-rules-classes)
5. [Getting Started](#getting-started)
6. [Advanced Usage](#advanced-usage)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Business Rules Framework provides a standardized, production-grade approach to validation and business logic enforcement across all services in the Data Interoperability Hub. It ensures consistency, observability, and maintainability through:

- **Standardized Validation Results**: Consistent `ValidationResult` structure across all rules
- **Rule Execution Context**: Tenant-aware, user-aware validation with resource tracking
- **Built-in Observability**: Caching, metrics, tracing, and structured logging
- **Rule Composition**: Combine multiple rules with dependency resolution
- **Registry System**: Decorator-based registration with auto-discovery

### Key Benefits

- ✅ **Consistency**: All business rules follow the same patterns and interfaces
- ✅ **Observability**: Built-in metrics, tracing, and logging for all rule executions
- ✅ **Performance**: Automatic caching of validation results
- ✅ **Maintainability**: Centralized framework reduces code duplication
- ✅ **Testability**: Standardized structure makes testing straightforward
- ✅ **Scalability**: Registry system enables rule orchestration and dependency management

---

## Architecture

### Framework Components

```
hub/apps/core/business_rules/
├── base.py          # Base class, ValidationResult, RuleExecutionContext
├── registry.py      # Rule registry, registration decorators, dependency resolution
└── __init__.py      # Public API exports
```

### Core Classes

#### `BusinessRules` (Abstract Base Class)

The foundation for all business rules implementations. Provides:

- Standardized initialization with tenant/user context
- Built-in caching, metrics, tracing, and logging
- Rule execution orchestration via `execute()` method
- Rule composition via `compose()` method

**Location**: `hub/apps/core/business_rules/base.py`

#### `ValidationResult` (Dataclass)

Standardized result structure for all validations:

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
```

**Features**:
- Boolean evaluation (`if result:`)
- Result combination (`result.combine(other_result)`)
- String representation for debugging

#### `RuleExecutionContext` (Dataclass)

Context for rule execution:

```python
@dataclass
class RuleExecutionContext:
    tenant_id: Optional[str]
    user_id: Optional[str]
    resource: Optional[Any]
    metadata: Dict[str, Any]
```

**Features**:
- Cache key generation
- Context serialization for logging
- Resource tracking

#### `BusinessRulesRegistry`

Central registry for all business rules:

- Decorator-based registration (`@register_rule`)
- Auto-discovery of rules
- Dependency resolution and execution ordering
- Rule orchestration

**Location**: `hub/apps/core/business_rules/registry.py`

---

## Framework Features

### 1. Caching

**Purpose**: Improve performance by caching validation results

**How It Works**:
- Cache keys are generated from rule name, context, and arguments
- Only valid results are cached (errors are not cached)
- Cache TTL is configurable per rule (default: 300 seconds)
- Uses Django's cache framework (Redis in production)

**Configuration**:

```python
# In settings.py
CACHE_TTL_BUSINESS_RULES = 300  # 5 minutes default

# Per-rule override
class MyBusinessRules(BusinessRules):
    def get_cache_ttl(self) -> int:
        return 600  # 10 minutes for this rule
```

**Usage**:

```python
# Enable caching (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_caching=True)

# Disable caching
rules = MyBusinessRules(tenant_id="tenant-1", enable_caching=False)

# Override per-execution
result = rules.execute(context=ctx, use_cache=False)
```

**Cache Key Format**:
```
business_rules:validation:{rule_name}:{context_hash}:{args_hash}
```

**Cache Invalidation**:
- Automatic expiration after TTL
- Manual invalidation via cache key patterns
- Only valid results cached (invalid results bypass cache)

### 2. Metrics

**Purpose**: Monitor rule execution performance and outcomes

**Metrics Collected**:

1. **`business_rules_executions_total`** (Counter)
   - Total number of rule executions
   - Labels: `rule_name`, `result` (valid/invalid/error)

2. **`business_rules_duration_seconds`** (Histogram)
   - Execution duration in seconds
   - Labels: `rule_name`, `result`

3. **`business_rules_results_total`** (Counter)
   - Validation results with error/warning counts
   - Labels: `rule_name`, `result`, `has_errors`, `has_warnings`

**Implementation**: OpenTelemetry metrics with Prometheus exporter

**Configuration**:

```python
# Enable metrics (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_metrics=True)

# Disable metrics
rules = MyBusinessRules(tenant_id="tenant-1", enable_metrics=False)
```

**Accessing Metrics**:
- Prometheus endpoint: `/metrics`
- Grafana dashboards (if configured)
- OpenTelemetry collector

**Example Metrics Output**:
```
business_rules_executions_total{rule_name="ODPSBusinessRules",result="valid"} 1250
business_rules_executions_total{rule_name="ODPSBusinessRules",result="invalid"} 45
business_rules_duration_seconds{rule_name="ODPSBusinessRules",result="valid"} 0.023
business_rules_results_total{rule_name="ODPSBusinessRules",result="valid",has_errors="false",has_warnings="false"} 1200
```

### 3. Tracing

**Purpose**: Distributed tracing for rule execution across services

**How It Works**:
- Creates OpenTelemetry spans for each rule execution
- Spans include rule name, tenant_id, user_id, and execution details
- Spans are linked to parent traces (if available)
- Error information is recorded in spans

**Span Attributes**:
- `business_rules.rule_name`: Name of the rule
- `business_rules.tenant_id`: Tenant ID (if available)
- `business_rules.user_id`: User ID (if available)
- `business_rules.is_valid`: Validation result
- `business_rules.error_count`: Number of errors
- `business_rules.warning_count`: Number of warnings
- `business_rules.duration_seconds`: Execution duration

**Configuration**:

```python
# Enable tracing (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_tracing=True)

# Disable tracing
rules = MyBusinessRules(tenant_id="tenant-1", enable_tracing=False)
```

**Viewing Traces**:
- Jaeger UI (if configured)
- OpenTelemetry collector
- Cloud observability platforms (if configured)

**Example Trace**:
```
business_rules.ODPSBusinessRules
├── tenant_id: "tenant-1"
├── user_id: "user-123"
├── is_valid: true
├── error_count: 0
├── warning_count: 1
└── duration_seconds: 0.023
```

### 4. Structured Logging

**Purpose**: Comprehensive logging for debugging and auditing

**Log Levels**:
- **INFO**: Successful validations
- **WARNING**: Invalid validations (with errors)
- **DEBUG**: Detailed execution information

**Log Fields**:
- `rule_name`: Name of the rule
- `tenant_id`: Tenant ID
- `user_id`: User ID
- `is_valid`: Validation result
- `error_count`: Number of errors
- `warning_count`: Number of warnings
- `duration_seconds`: Execution duration
- `cached`: Whether result was from cache
- `resource_type`: Type of resource being validated
- `resource_id`: ID of resource being validated
- `errors`: List of error messages (if any)
- `warnings`: List of warning messages (if any)

**Configuration**:

```python
# Enable logging (default)
rules = MyBusinessRules(tenant_id="tenant-1", enable_logging=True)

# Disable logging
rules = MyBusinessRules(tenant_id="tenant-1", enable_logging=False)
```

**Example Log Entry**:
```json
{
  "event": "Business rule executed",
  "rule_name": "ODPSBusinessRules",
  "tenant_id": "tenant-1",
  "user_id": "user-123",
  "is_valid": true,
  "error_count": 0,
  "warning_count": 1,
  "duration_seconds": 0.023,
  "cached": false,
  "resource_type": "Contract",
  "resource_id": "contract-456",
  "warnings": ["ODPS version 1.0.0 is deprecated, consider upgrading"]
}
```

---

## Business Rules Classes

The framework includes **23 business rules classes** across all services:

### Contract Business Rules

#### 1. `ODPSBusinessRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_validation`
**Tags**: `["odps", "contracts", "validation"]`

**Purpose**: Validates ODPS (Open Data Product Standard) documents

**Validation Capabilities**:
- ODPS document structure validation
- ODPS version compatibility validation
- ODPS-ODCS linking rules validation
- Comprehensive ODPS contract validation

**Key Methods**:
- `validate_odps_structure(odps_doc, strict=False)`
- `validate_odps_version(odps_doc, required_version=None)`
- `validate_odps_contract(contract, strict=False)`

#### 2. `ODPSLinkingRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_linking_validation`
**Tags**: `["odps", "linking", "validation"]`

**Purpose**: Validates ODPS-ODCS linking rules

**Validation Capabilities**:
- Link existence validation
- Circular reference detection
- Referential integrity validation

#### 3. `ODPSExportRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_export_validation`
**Tags**: `["odps", "export", "validation"]`

**Purpose**: Validates ODPS export operations

**Validation Capabilities**:
- Export format validation
- Data completeness validation
- Fidelity validation (round-trip consistency)

#### 4. `ODPSNormalizationRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `odps_normalization_validation`
**Tags**: `["odps", "normalization", "validation"]`

**Purpose**: Validates contract normalization

**Validation Capabilities**:
- Normalization eligibility validation
- Normalization status validation
- Fidelity validation (data loss prevention)

#### 5. `ContractsBusinessRules`
**Location**: `hub/apps/contracts/business_rules.py`
**Rule Name**: `contracts_lifecycle_validation`
**Tags**: `["contracts", "lifecycle", "validation"]`

**Purpose**: Validates contract lifecycle operations

**Validation Capabilities**:
- Contract creation validation
- Contract update validation
- Contract deletion validation
- Version compatibility validation

### Data Mesh Business Rules

#### 6. `DataMeshBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `data_mesh_domain_validation`
**Tags**: `["mesh", "domain", "validation"]`

**Purpose**: Validates data mesh domain operations

**Validation Capabilities**:
- Domain structure validation
- Domain boundaries validation
- Ownership transfer validation
- Policy conflict detection
- Domain resource quota validation

**Key Methods**:
- `validate_domain_structure(domain)`
- `validate_boundaries(domain)`
- `validate_ownership_transfer(from_domain, to_domain, assets)`
- `validate_policy_conflicts(domain, policies)`

#### 7. `PolicyBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `policy_validation` (implicit)
**Tags**: `["mesh", "policy", "validation"]`

**Purpose**: Validates policy application and compliance

**Validation Capabilities**:
- Policy application validation
- Compliance checking
- Violation detection

**Key Methods**:
- `validate_policy_application(domain, policy)`
- `check_compliance(domain, policies)`
- `detect_violations(domain, asset=None)`

#### 8. `TopologyBusinessRules`
**Location**: `hub/apps/mesh/business_rules.py`
**Rule Name**: `topology_validation` (implicit)
**Tags**: `["mesh", "topology", "validation"]`

**Purpose**: Calculates topology and health metrics

**Validation Capabilities**:
- Relationship calculation between domains
- Health metrics calculation

**Key Methods**:
- `calculate_relationships(domains)`
- `calculate_health_metrics(domain)`

### Virtualization Business Rules

#### 10. `VirtualizationBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `virtualization_dataset_validation`
**Tags**: `["virtualization", "dataset", "validation"]`

**Purpose**: Validates virtual datasets

**Validation Capabilities**:
- Query syntax validation for different query types
- Schema alignment validation
- Source compatibility validation
- Cross-source compatibility validation

**Key Methods**:
- `validate_query_syntax(query, query_type)`
- `validate_schema_alignment(virtual_dataset, sources)`
- `validate_source_compatibility(virtual_dataset, source)`

#### 11. `QueryExecutionBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `query_execution_validation` (implicit)
**Tags**: `["virtualization", "query", "execution"]`

**Purpose**: Validates query execution decisions

**Validation Capabilities**:
- Query optimization strategies
- Execution mode selection (SYNC vs ASYNC)
- Timeout validation

**Key Methods**:
- `validate_execution_mode(query, context)`
- `validate_timeout(query, timeout)`

#### 12. `ResultBusinessRules`
**Location**: `hub/apps/virtualization/business_rules.py`
**Rule Name**: `result_validation` (implicit)
**Tags**: `["virtualization", "result", "validation"]`

**Purpose**: Validates query result handling

**Validation Capabilities**:
- Result caching configuration validation
- Pagination parameter validation

**Key Methods**:
- `validate_result_caching(cache_enabled, cache_ttl, result_size)`
- `validate_pagination(page, page_size)`

### Orchestration Business Rules

#### 13. `OrchestrationBusinessRules`
**Location**: `hub/apps/orchestration/business_rules.py`
**Rule Name**: `orchestration_validation`
**Tags**: `["orchestration", "validation", "workflow", "step"]`

**Purpose**: Validates workflow orchestration operations

**Validation Capabilities**:
- Workflow instance validation
- Workflow step validation
- Tenant context consistency
- User permissions and access validation
- State management validation (persistence, recovery, consistency)

**Key Methods**:
- `validate_workflow_instance(workflow, tenant, user)`
- `validate_workflow_step(step, tenant, user)`
- `validate_tenant_context(workflow, step, tenant)`

### Service Business Rules

#### 14. `NotificationsBusinessRules`
**Location**: `hub/apps/notifications/business_rules.py`
**Rule Name**: `notifications_validation`
**Tags**: `["notifications", "validation"]`

**Purpose**: Validates notification operations

**Validation Capabilities**:
- Notification creation validation
- Delivery validation
- Template validation
- Recipients validation
- Tenant context validation
- User permissions validation

#### 15. `SearchBusinessRules`
**Location**: `hub/apps/search/business_rules.py`
**Rule Name**: `search_validation`
**Tags**: `["search", "validation", "query", "index"]`

**Purpose**: Validates search operations

**Validation Capabilities**:
- Search query validation
- Index validation
- Search operation validation

#### 16. `SemanticBusinessRules`
**Location**: `hub/apps/semantic/business_rules.py`
**Rule Name**: `semantic_validation`
**Tags**: `["semantic", "validation", "mapping", "sparql", "rdf"]`

**Purpose**: Validates semantic operations

**Validation Capabilities**:
- Semantic mapping validation
- SPARQL query validation
- Semantic resource validation
- Tenant context validation

#### 17. `WebhooksBusinessRules`
**Location**: `hub/apps/webhooks/business_rules.py`
**Rule Name**: `webhooks_validation`
**Tags**: `["webhooks", "validation", "subscription", "delivery"]`

**Purpose**: Validates webhook operations

**Validation Capabilities**:
- Webhook subscription validation
- Webhook delivery validation
- Tenant context validation

#### 18. `ScheduledIngestionBusinessRules`
**Location**: `hub/apps/scheduled_ingestion/business_rules.py`
**Rule Name**: `scheduled_ingestion_validation`
**Tags**: `["scheduled_ingestion", "validation", "ingestion"]`

**Purpose**: Validates scheduled ingestion operations

**Validation Capabilities**:
- Schedule validation
- Ingestion run validation
- Source validation
- Tenant context validation

#### 19. `FilesBusinessRules`
**Location**: `hub/apps/files/business_rules.py`
**Rule Name**: `files_validation`
**Tags**: `["files", "validation", "storage"]`

**Purpose**: Validates file operations

**Validation Capabilities**:
- File validation
- Tenant context validation
- File access permissions validation

#### 20. `JobsBusinessRules`
**Location**: `hub/apps/jobs/business_rules.py`
**Rule Name**: `jobs_validation`
**Tags**: `["jobs", "validation"]`

**Purpose**: Validates job operations

**Validation Capabilities**:
- Job creation validation
- Job execution validation
- Status transition validation
- Tenant context validation
- Resource relationships validation

#### 21. `ComplianceBusinessRules`
**Location**: `hub/apps/compliance/business_rules.py`
**Rule Name**: `compliance_validation`
**Tags**: `["compliance", "validation", "risk_assessment"]`

**Purpose**: Validates compliance operations

**Validation Capabilities**:
- Compliance run validation
- Risk assessment validation
- Tenant context validation
- Resource relationships validation

#### 22. `DQBusinessRules`
**Location**: `hub/apps/dq/business_rules.py`
**Rule Name**: `dq_validation`
**Tags**: `["dq", "data_quality", "validation"]`

**Purpose**: Validates data quality operations

**Validation Capabilities**:
- Data quality run validation
- Check configuration validation
- Tenant context validation
- Dataset relationships validation

#### 23. `GovernanceBusinessRules`
**Location**: `hub/apps/governance/business_rules.py`
**Rule Name**: `governance_validation`
**Tags**: `["governance", "validation"]`

**Purpose**: Validates governance operations

**Validation Capabilities**:
- Governance policy validation
- Access request validation
- Classification validation
- Access control validation

#### 24. `MarketplaceBusinessRules`
**Location**: `hub/apps/marketplace/business_rules.py`
**Rule Name**: `marketplace_validation`
**Tags**: `["marketplace", "validation"]`

**Purpose**: Validates marketplace operations

**Validation Capabilities**:
- Marketplace listing validation
- Order validation
- Entitlement validation
- Access control validation

#### 25. `DatasetsBusinessRules`
**Location**: `hub/apps/datasets/business_rules.py`
**Rule Name**: `datasets_validation`
**Tags**: `["datasets", "validation"]`

**Purpose**: Validates dataset operations

**Validation Capabilities**:
- Dataset structure validation
- Schema validation
- Tenant context validation
- Version management validation

#### 26. `AssetsBusinessRules`
**Location**: `hub/apps/assets/business_rules.py`
**Rule Name**: `assets_validation`
**Tags**: `["assets", "validation"]`

**Purpose**: Validates asset operations

**Validation Capabilities**:
- Asset lifecycle validation
- Asset structure validation
- Tenant context validation
- Access permissions validation

---

## Getting Started

### Creating a New Business Rules Class

1. **Import the base class**:

```python
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
```

2. **Create your business rules class**:

```python
@register_rule(
    rule_name="my_service_validation",
    description="Validates my service operations",
    tags=["my_service", "validation"],
    priority=10
)
class MyServiceBusinessRules(BusinessRules):
    """Business rules validator for my service operations."""

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "MyServiceBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            ValidationResult instance
        """
        # Extract resources from context or kwargs
        resource = kwargs.get('resource') or (context.resource if context else None)

        if not resource:
            return ValidationResult(
                is_valid=False,
                errors=["Resource is required"],
            )

        # Perform validation
        errors = []
        warnings = []
        details = {}

        # Your validation logic here
        if not resource.is_valid():
            errors.append("Resource is invalid")

        # Return result
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )
```

3. **Use your business rules**:

```python
# Create instance
rules = MyServiceBusinessRules(
    tenant_id="tenant-1",
    user_id="user-123"
)

# Create context
context = rules.create_context(
    resource=my_resource,
    metadata={"operation": "create"}
)

# Execute validation
result = rules.execute(context=context)

# Check result
if result:
    print("Validation passed!")
else:
    print(f"Validation failed: {result.errors}")
```

### Using the Registry

```python
from hub.apps.core.business_rules.registry import get_registry

# Get registry
registry = get_registry()

# Get all rules
all_rules = registry.get_all_rules()

# Get rule by name
rule_metadata = registry.get_rule("my_service_validation")

# Get rules by tag
validation_rules = registry.get_rule_by_tag("validation")

# Execute multiple rules
results = registry.execute_rules(
    rule_names=["rule1", "rule2"],
    tenant_id="tenant-1",
    user_id="user-123",
    short_circuit=True  # Stop on first error
)
```

---

## Advanced Usage

### Rule Composition

Combine multiple rules into a single validation:

```python
def validate_tenant(context: RuleExecutionContext) -> ValidationResult:
    """Validate tenant."""
    # Your validation logic
    return ValidationResult(is_valid=True)

def validate_user(context: RuleExecutionContext) -> ValidationResult:
    """Validate user."""
    # Your validation logic
    return ValidationResult(is_valid=True)

# Compose rules
rules = MyServiceBusinessRules()
context = rules.create_context()

result = rules.compose(
    validate_tenant,
    validate_user,
    context=context,
    short_circuit=True  # Stop on first error
)
```

### Custom Cache TTL

```python
class MyBusinessRules(BusinessRules):
    def get_cache_ttl(self) -> int:
        return 600  # 10 minutes
```

### Dependency Resolution

Rules can declare dependencies:

```python
@register_rule(
    rule_name="dependent_rule",
    depends_on=["prerequisite_rule"],
    priority=20
)
class DependentRule(BusinessRules):
    # ...
```

The registry will automatically resolve execution order:

```python
registry = get_registry()
execution_order = registry.resolve_execution_order(
    rule_names=["dependent_rule", "prerequisite_rule"]
)
# Returns: ["prerequisite_rule", "dependent_rule"]
```

### Disabling Framework Features

```python
# Disable all features
rules = MyBusinessRules(
    tenant_id="tenant-1",
    enable_caching=False,
    enable_metrics=False,
    enable_tracing=False,
    enable_logging=False
)

# Disable specific feature per execution
result = rules.execute(context=ctx, use_cache=False)
```

---

## Best Practices

### 1. Always Use the Framework

✅ **DO**: Extend `BusinessRules` base class
❌ **DON'T**: Create custom validation classes outside the framework

### 2. Use Rule Execution Context

✅ **DO**: Use `RuleExecutionContext` for tenant/user context
❌ **DON'T**: Pass tenant_id/user_id as separate parameters

### 3. Return Comprehensive Results

✅ **DO**: Include errors, warnings, and details in `ValidationResult`
❌ **DON'T**: Return only boolean values

### 4. Register Rules

✅ **DO**: Use `@register_rule` decorator
❌ **DON'T**: Create unregistered rules

### 5. Use Descriptive Rule Names

✅ **DO**: Use descriptive, unique rule names
❌ **DON'T**: Use generic names like "validation"

### 6. Add Tags

✅ **DO**: Add relevant tags for categorization
❌ **DON'T**: Leave tags empty

### 7. Handle Errors Gracefully

✅ **DO**: Catch exceptions and return ValidationResult with error
❌ **DON'T**: Let exceptions propagate unhandled

### 8. Use Caching Appropriately

✅ **DO**: Cache expensive validations
❌ **DON'T**: Cache validations that change frequently

### 9. Provide Context in Errors

✅ **DO**: Include context in error messages
❌ **DON'T**: Return generic error messages

### 10. Test Your Rules

✅ **DO**: Write comprehensive tests for all validation paths
❌ **DON'T**: Skip testing edge cases

---

## Troubleshooting

### Common Issues

#### 1. Rule Not Found

**Problem**: `ValueError: Rule 'my_rule' not found`

**Solution**: Ensure rule is registered with `@register_rule` decorator

#### 2. Circular Dependencies

**Problem**: `ValueError: Circular dependency detected`

**Solution**: Review rule dependencies and remove circular references

#### 3. Cache Not Working

**Problem**: Results not being cached

**Solution**:
- Check `enable_caching=True` in initialization
- Verify cache backend is configured (Redis in production)
- Check cache TTL settings

#### 4. Metrics Not Appearing

**Problem**: Metrics not showing in Prometheus

**Solution**:
- Verify `enable_metrics=True` in initialization
- Check OpenTelemetry configuration
- Verify Prometheus exporter is configured

#### 5. Traces Not Showing

**Problem**: Traces not appearing in Jaeger

**Solution**:
- Verify `enable_tracing=True` in initialization
- Check OpenTelemetry configuration
- Verify trace exporter is configured

### Debugging Tips

1. **Enable Debug Logging**:
```python
import logging
logging.getLogger('hub.apps.core.business_rules').setLevel(logging.DEBUG)
```

2. **Check Registry State**:
```python
registry = get_registry()
all_rules = registry.get_all_rules()
print(all_rules)
```

3. **Inspect Validation Results**:
```python
result = rules.execute(context=ctx)
print(result)  # String representation
print(result.details)  # Detailed information
```

4. **Verify Cache Keys**:
```python
cache_key = rules._get_cache_key("MyRule", context)
print(cache_key)
```

---

## Additional Resources

- **Framework Review**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`
- **Base Class**: `hub/apps/core/business_rules/base.py`
- **Registry**: `hub/apps/core/business_rules/registry.py`
- **Tests**: `hub/apps/core/business_rules/tests/`

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-01-XX
**Maintained By**: Data Interoperability Hub Team

