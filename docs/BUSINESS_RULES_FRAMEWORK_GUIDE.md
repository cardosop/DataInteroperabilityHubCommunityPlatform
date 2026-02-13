# Business Rules Framework Guide

**Version:** 1.0
**Last Updated:** 2025-01-XX
**Status:** ✅ Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Framework Features](#framework-features)
4. [Business Rules Classes](#business-rules-classes)
5. [REST API alignment](#rest-api-alignment)
6. [Getting Started](#getting-started)
7. [Advanced Usage](#advanced-usage)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

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

#### 27. `MarketplaceIntegrationBusinessRules`
**Location**: `hub/apps/integrations/business_rules.py`
**Rule Name**: `marketplace_integration_validation`
**Tags**: `["integrations", "marketplace", "validation"]`

**Purpose**: Validates marketplace connection, sync, and mapping operations

**Validation Capabilities**:
- Connection name and config validation
- Sync job validation
- Mapping validation
- Tenant context validation

#### 28. `SocialBusinessRules`
**Location**: `hub/apps/social/business_rules.py`
**Rule Name**: `social_rating_validation`
**Tags**: `["social", "rating", "validation"]`

**Purpose**: Validates social operations (e.g. ratings)

**Validation Capabilities**:
- Rating: asset ACTIVE and in tenant, user in tenant, rating 1–5
- Tenant context validation

---

## REST API alignment

All REST create/update/delete operations for the apps below go through a **service layer** that invokes the same business rules as workflows. Validation failures return **400** (or the appropriate HTTP error) with `error`, `code` (e.g. `BUSINESS_RULES_VALIDATION`), and `details`; no mutation occurs. This ensures a single source of truth for domain rules and consistent behaviour whether the caller uses REST or workflows.

### Per-app alignment table

| App | REST entry points | Business rule class | Rule methods / validation type | Layer |
|-----|-------------------|---------------------|--------------------------------|-------|
| **Assets** | `POST/PATCH/DELETE /api/v1/assets/` | `AssetsBusinessRules` | `validate(asset=..., validation_type=...)` | Asset views → service (create/update/delete) |
| **Contracts** | `POST/PATCH/DELETE /api/v1/contracts/` | `ContractsBusinessRules` | `validate(contract=..., validation_type=...)` | ContractViewSet → ContractService |
| **Datasets** | `POST/PATCH/DELETE /api/v1/datasets/` | `DatasetsBusinessRules` | `validate(dataset=..., validation_type=...)` | DatasetViewSet → DatasetService |
| **Marketplace** | `POST/PATCH/DELETE /api/v1/marketplace/listings/`, `orders/`, `entitlements/` | `MarketplaceBusinessRules` | Listing/order/entitlement validation | Marketplace views → MarketplaceService |
| **Files** | `POST/PATCH/DELETE /api/v1/files/` | `FilesBusinessRules` | `validate(file=..., validation_type=...)` | FileViewSet → FileService |
| **Governance** | `POST /api/v1/governance/access-requests/`, `.../{id}/approve/`, `.../{id}/reject/` | `GovernanceBusinessRules` | `validate(access_request=...)`, approval/rejection | Access_request_views → GovernanceService |
| **Compliance** | `POST /api/v1/compliance/runs/` | `ComplianceBusinessRules` | `validate(compliance_run=..., validation_type=compliance_run)` | ComplianceRunViewSet create → ComplianceService |
| **DQ** | `POST /api/v1/dq/runs/` | `DQBusinessRules` | `validate(dq_run=..., validation_type=dq_run)` | DQRunViewSet create → DQService |
| **Mesh** | `POST/PATCH/DELETE /api/v1/mesh/domains/` | `DataMeshBusinessRules` | `validate(domain=..., validation_type=structure)` | DomainViewSet → DataMeshService |
| **Virtualization** | `POST/PATCH /api/v1/virtualization/datasets/` | `VirtualizationBusinessRules` | `validate(virtual_dataset=..., validation_type=all)` | VirtualDatasetViewSet → VirtualizationService |
| **Scheduled ingestion** | `POST/PATCH/DELETE /api/v1/scheduled-ingestions/` | `ScheduledIngestionBusinessRules` | `validate(schedule=..., validation_type=schedule)` | ScheduledIngestionViewSet create → IngestionService |
| **Integrations** | `POST/PATCH/DELETE /api/v1/integrations/marketplace/connections/` | `MarketplaceIntegrationBusinessRules` | `validate(connection=..., validation_type=connection)` | MarketplaceConnectionViewSet → MarketplaceIntegrationService |
| **Social** | `POST /api/v1/ratings/` (and reviews/comments/communities as implemented) | `SocialBusinessRules` | `validate(asset=..., user=..., tenant=..., rating_value=..., validation_type=rating)` | RatingViewSet create → SocialService |

### Error response contract

When a business rule rejects a request, the API returns **400 Bad Request** with a JSON body:

- **`error`**: Human-readable message (e.g. from `ValidationError.message`).
- **`code`**: Machine-readable code (e.g. `BUSINESS_RULES_VALIDATION`, `VALIDATION_ERROR`).
- **`details`**: Optional dict with rule-specific context (e.g. `validation_type`, field-level details).

Views catch `ServiceValidationError` (or the service base `ValidationError`) and return this shape; they do not re-raise as DRF `ValidationError` without the `code` field.

### Tests

Integration tests that assert REST → business rules alignment (no mocks) live in:

- **`tests.integration.test_rest_business_rules_alignment`**

Run the Phase 18.7 alignment tests (see `openspec/changes/workflows1/tasks.md`):

```bash
./scripts/run_phase18_rest_business_rules_tests.sh --no-keepdb   # first run or fresh DB
./scripts/run_phase18_rest_business_rules_tests.sh               # reuse DB (--keepdb)
```

---

## Serializers and domain validation

**Serializers are responsible for input shape and format only.** Domain validation (e.g. “name cannot be empty”, “at least one resource required”, “asset must be ACTIVE”) stays in **business rules** invoked from the **service layer**; it must not be duplicated in serializers.

### Principle

| Responsibility | Where it lives | Examples |
|----------------|----------------|----------|
| **Input shape/format** | Serializers | Field types, `required`, `allow_blank`, max length, choice lists, JSON structure. |
| **Domain rules** | Business rules (called by services) | “Name cannot be empty”, “Asset must be ACTIVE for rating”, “At least one of asset_id/dataset_id/file_id required”, “Connection name unique per tenant”. |

### Why

- **Single source of truth**: Workflows and REST both call the same service → same business rules. No divergence between “serializer validation” and “workflow validation”.
- **Consistent errors**: Failures from business rules return 400 with `code` (e.g. `BUSINESS_RULES_VALIDATION`) and `details`; serializer-only validation typically does not set `code`.
- **Testability**: Integration tests can assert that invalid domain data is rejected by the service and returns the expected 400 body.

### Implementation note

For create/update payloads where “empty/whitespace name” or similar is a **domain** rule: serializers use `allow_blank=True` (or pass-through in `validate_*`) so that the value reaches the service; the service then calls the business rule, which rejects it and raises `ValidationError` with `code=BUSINESS_RULES_VALIDATION`. The view catches that and returns 400 with `error`, `code`, and `details`. Serializers do **not** raise `ValidationError` for those domain rules so that the response format and code remain consistent.

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

## Workflow Integration

### Overview

Business rules are seamlessly integrated with the Workflow Orchestration system to provide comprehensive validation at every workflow step. This integration ensures consistent validation, error handling, and observability across all workflow operations.

**Related Documentation**: [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md)

### Integration Points

Business rules are integrated at three key points in workflow execution:

1. **Pre-Step Validation**: Before executing a workflow step
2. **Post-Step Validation**: After executing a workflow step  
3. **Compensation Validation**: During workflow rollback

### OrchestrationBusinessRules

The `OrchestrationBusinessRules` class provides workflow-specific validation methods:

#### `validate_workflow_step_execution()`

Validates that a workflow step can execute in the current workflow state.

**Usage**:
```python
from hub.apps.orchestration.business_rules import OrchestrationBusinessRules

business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_step_execution(
    workflow=workflow_instance,
    step=workflow_step,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step cannot execute: {', '.join(result.errors)}")
```

**Validates**:
- Workflow status is RUNNING
- Step status allows execution (PENDING or RUNNING)
- Step index matches workflow current_step_index
- Workflow state is consistent
- Tenant context is valid
- User permissions are valid

#### `validate_step_input()`

Validates step input data structure and schema.

**Usage**:
```python
result = business_rules.validate_step_input(
    workflow=workflow_instance,
    step=workflow_step,
    step_input=task_input,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step input invalid: {', '.join(result.errors)}")
```

**Validates**:
- Input is a dictionary
- Input is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)
- Input size is reasonable (<10MB)

#### `validate_step_output()`

Validates step output data structure and schema.

**Usage**:
```python
result = business_rules.validate_step_output(
    workflow=workflow_instance,
    step=workflow_step,
    step_output=step_result,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Step output invalid: {', '.join(result.errors)}")
```

**Validates**:
- Output is a dictionary
- Output is JSON serializable (for state persistence)
- Required fields are present (if schema defined)
- Data types are correct (if schema defined)
- Output size is reasonable (<10MB)

#### `validate_workflow_state()`

Validates workflow state consistency.

**Usage**:
```python
result = business_rules.validate_workflow_state(
    workflow=workflow_instance,
    tenant=tenant,
    user=user
)

if not result.is_valid:
    raise WorkflowExecutionError(f"Workflow state invalid: {', '.join(result.errors)}")
```

**Validates**:
- Workflow state_data is consistent
- Step indices match workflow current_step_index
- Completed steps are in correct order
- State transitions are valid
- State data is JSON serializable

### Workflow Integration Patterns

#### Pattern 1: Using OrchestrationBusinessRules in Workflow Engine

The `WorkflowEngine` automatically uses `OrchestrationBusinessRules` for validation:

```python
# In WorkflowEngine._execute_task_step()
business_rules = OrchestrationBusinessRules(
    tenant_id=str(tenant.id) if tenant else None,
    user_id=str(user.id) if user else None
)

# Pre-step validation
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)

# Execute step
result = task_func(task_input, instance, step)

# Post-step validation
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
```

#### Pattern 2: Using Service-Specific Business Rules in Task Functions

Task functions can use service-specific business rules for domain validation:

```python
def create_contract_task(
    input_data: Dict[str, Any],
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Create contract with business rules validation"""
    
    from hub.apps.contracts.business_rules import ContractsBusinessRules
    
    # Get tenant and user context
    tenant = instance.tenant
    user = instance.created_by
    
    # Create service-specific business rules
    contract_rules = ContractsBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate contract creation
    contract_data = input_data.get("contract_data")
    validation_result = contract_rules.validate_contract_creation(
        contract_data=contract_data,
        tenant=tenant,
        user=user
    )
    
    if not validation_result.is_valid:
        raise ValueError(
            f"Contract validation failed: {', '.join(validation_result.errors)}"
        )
    
    # Log warnings if any
    if validation_result.warnings:
        logger.warning(
            f"Contract validation warnings: {', '.join(validation_result.warnings)}"
        )
    
    # Create contract
    contract = create_contract(contract_data)
    
    return {
        "contract_id": str(contract.id),
        "contract_status": contract.status
    }
```

#### Pattern 3: Compensation Validation

Compensation validates using business rules but does not block rollback:

```python
def _compensate_step(
    self,
    instance: WorkflowInstance,
    step: WorkflowStep
) -> Dict[str, Any]:
    """Compensate a workflow step with business rules validation"""
    
    business_rules = OrchestrationBusinessRules(
        tenant_id=str(tenant.id) if tenant else None,
        user_id=str(user.id) if user else None
    )
    
    # Validate compensation step (warnings don't block)
    compensation_result = business_rules.validate_workflow_step_execution(
        instance, step, tenant, user
    )
    
    if compensation_result.warnings:
        logger.warning(
            f"Compensation validation warnings: {', '.join(compensation_result.warnings)}"
        )
    
    # Execute compensation logic
    compensation_result = self._execute_compensation_task(instance, step, compensation_def)
    
    return {
        "status": "compensated",
        "result": compensation_result,
        "validation": {
            "is_valid": compensation_result.is_valid,
            "warnings": compensation_result.warnings
        }
    }
```

### Validation Patterns

#### Pattern 1: Pre-Step Validation

Always validate workflow state and step input before execution:

```python
# Validate workflow state
workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
if not workflow_state_result.is_valid:
    raise WorkflowExecutionError(
        f"Workflow state invalid: {', '.join(workflow_state_result.errors)}"
    )

# Validate step input
step_input_result = business_rules.validate_step_input(instance, step, task_input, tenant, user)
if not step_input_result.is_valid:
    raise WorkflowExecutionError(
        f"Step input invalid: {', '.join(step_input_result.errors)}"
    )
```

#### Pattern 2: Post-Step Validation

Always validate step output and workflow state after execution:

```python
# Execute step
result = task_func(task_input, instance, step)

# Validate step output
step_output_result = business_rules.validate_step_output(instance, step, result, tenant, user)
if not step_output_result.is_valid:
    raise WorkflowExecutionError(
        f"Step output invalid: {', '.join(step_output_result.errors)}"
    )

# Validate workflow state
post_workflow_state_result = business_rules.validate_workflow_state(instance, tenant, user)
if not post_workflow_state_result.is_valid:
    raise WorkflowExecutionError(
        f"Workflow state invalid: {', '.join(post_workflow_state_result.errors)}"
    )
```

#### Pattern 3: Service-Specific Validation in Task Functions

Use service-specific business rules for domain validation:

```python
def my_task_function(input_data, instance, step):
    from hub.apps.my_service.business_rules import MyServiceBusinessRules
    
    my_rules = MyServiceBusinessRules(
        tenant_id=str(instance.tenant.id),
        user_id=str(instance.created_by.id)
    )
    
    # Validate domain-specific logic
    validation_result = my_rules.validate_my_operation(
        resource=input_data.get("resource"),
        tenant=instance.tenant,
        user=instance.created_by
    )
    
    if not validation_result.is_valid:
        raise ValueError(f"Validation failed: {', '.join(validation_result.errors)}")
    
    # Perform operation
    return {"result": "success"}
```

### Best Practices

#### 1. Always Use Business Rules for Validation

**Do**:
```python
# Use business rules for validation
business_rules = OrchestrationBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = business_rules.validate_workflow_state(instance, tenant, user)
if not result.is_valid:
    raise WorkflowExecutionError(...)
```

**Don't**:
```python
# Don't skip validation or duplicate validation logic
if instance.status != WorkflowStatus.RUNNING:
    raise WorkflowExecutionError("Invalid status")
```

#### 2. Use Service-Specific Business Rules in Task Functions

**Do**:
```python
# Use service-specific business rules for domain validation
from hub.apps.contracts.business_rules import ContractsBusinessRules

contract_rules = ContractsBusinessRules(tenant_id=tenant_id, user_id=user_id)
validation_result = contract_rules.validate_contract_creation(contract_data)
if not validation_result.is_valid:
    raise ValueError(f"Contract validation failed: {', '.join(validation_result.errors)}")
```

**Don't**:
```python
# Don't duplicate validation logic in task functions
if not contract_data.get("name"):
    raise ValueError("Contract name is required")
```

#### 3. Handle Validation Warnings Appropriately

**Do**:
```python
# Log warnings but don't block execution
if validation_result.warnings:
    logger.warning(f"Validation warnings: {', '.join(validation_result.warnings)}")
```

**Don't**:
```python
# Don't treat warnings as errors
if validation_result.warnings:
    raise WorkflowExecutionError("Validation warnings found")
```

#### 4. Include Validation Context in Error Messages

**Do**:
```python
# Use _format_validation_error for consistent error messages
error_message = self._format_validation_error(
    "workflow state validation",
    validation_result,
    instance,
    step
)
raise WorkflowExecutionError(error_message)
```

**Don't**:
```python
# Don't create generic error messages
raise WorkflowExecutionError("Validation failed")
```

### Observability

Workflow validation with business rules provides comprehensive observability:

- **Metrics**: Validation success/failure rates, duration, cache hit rates
- **Events**: Validation results included in workflow events
- **Logs**: Structured logging with validation context
- **Traces**: Validation spans in distributed traces

See [Workflow Orchestration Guide](WORKFLOW_ORCHESTRATION.md#observability) for details.

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
**Last Updated**: 2026-01-29 (REST API alignment and Serializers sections added for Phase 18.8)
**Maintained By**: Data Interoperability Hub Team

