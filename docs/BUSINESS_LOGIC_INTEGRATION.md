# Business Logic Integration Guide

**Last Updated**: 2025-01-15
**Version**: 2.1.0

---

## Overview

This document describes how business logic is integrated across all features of the Data Interoperability Hub. The platform uses a comprehensive integration layer that coordinates features through workflows, service layers, events, and business rules.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Service Layer Coordination](#service-layer-coordination)
3. [Workflow Integration](#workflow-integration)
4. [Event-Driven Coordination](#event-driven-coordination)
5. [Business Rules Framework](#business-rules-framework-implemented---phase-972)
6. [Service Integration Patterns](#service-integration-patterns-implemented---phase-973)
7. [Compensation Logic](#compensation-logic)
8. [Data Consistency](#data-consistency)
9. [Frontend Integration](#frontend-integration)
10. [Best Practices](#best-practices)

---

## Architecture

### Integration Layer Components

```
┌─────────────────────────────────────────────────────────┐
│              Business Logic Integration Layer            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Service    │  │   Workflow   │  │    Event     │ │
│  │    Layer     │  │   Engine     │  │     Bus      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                              │
│                   ┌────────▼────────┐                    │
│                   │ Business Rules  │                    │
│                   │    Framework    │                    │
│                   └─────────────────┘                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Features    │    │  Features    │    │  Features    │
│  (AI/ML)     │    │(Transformation)│  │  (Social)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## Service Layer Coordination

### Service Layer Pattern

All business logic is coordinated through service layer classes that extend `BaseService`:

#### BaseService

```python
from hub.apps.core.services.base import BaseService

class MyService(BaseService):
    service_name = "my_service"

    def do_something(self, tenant_id: str, data: dict):
        # Business logic here
        # Publish events
        # Return result
        pass
```

#### Service Responsibilities

1. **Business Logic Coordination**: Coordinate operations across features
2. **Event Publishing**: Publish events for asynchronous coordination
3. **Transaction Management**: Manage transaction boundaries
4. **Error Handling**: Handle errors consistently
5. **Audit Logging**: Log all operations

### Service Classes

#### TransformationService ✅ (Implemented - Phase 9.5.1)

**Location**: `hub/apps/transformation/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.1

**Responsibilities**:
- Coordinate pipeline execution with asset lifecycle
- Manage pipeline-to-asset relationships
- Handle pipeline result synchronization
- Validate pipeline compatibility with assets
- Publish transformation events (pipeline.created, pipeline.executed, etc.)

**Integration**:
- Extends `BaseService` and `TransformationEventPublisher`
- Integrates with AssetCreationWorkflow, TransformationPipelineWorkflow
- Uses Event Bus for asynchronous coordination
- Uses TransformationBusinessRules for validation

**Key Methods**:
- `create_pipeline()` - Create and validate transformation pipeline
- `execute_pipeline()` - Execute pipeline with asset coordination
- `validate_pipeline_compatibility()` - Validate pipeline against assets

**Example**:
```python
from hub.apps.transformation.services import TransformationService

service = TransformationService(tenant_id=tenant_id, user_id=user_id)
pipeline = service.create_pipeline(
    name="data_cleaning",
    asset_id=asset_id,
    nodes=[...]
)
result = service.execute_pipeline(pipeline.id, asset_id)
```

#### DataMeshService ✅ (Implemented - Phase 9.5.2)

**Location**: `hub/apps/mesh/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.2

**Responsibilities**:
- Coordinate domain operations
- Manage domain-to-asset relationships
- Handle federated governance
- Coordinate mesh topology updates
- Publish data mesh events (domain.created, domain.updated, etc.)

**Integration**:
- Extends `BaseService` and `DataMeshEventPublisher`
- Integrates with DataMeshWorkflow, AssetUpdateWorkflow
- Uses Event Bus for asynchronous coordination
- Uses DataMeshBusinessRules, PolicyBusinessRules, TopologyBusinessRules for validation

**Key Methods**:
- `create_domain()` - Create data mesh domain
- `update_domain()` - Update domain configuration
- `transfer_ownership()` - Transfer asset ownership between domains

#### VirtualizationService ✅ (Implemented - Phase 9.5.3)

**Location**: `hub/apps/virtualization/services.py`
**Status**: ✅ Implemented
**Phase**: 9.5.3

**Responsibilities**:
- Coordinate virtual dataset operations
- Manage query execution across multiple sources
- Handle schema alignment and validation
- Coordinate virtualization events
- Publish virtualization events (dataset.created, query.executed, etc.)

**Integration**:
- Extends `BaseService` and `VirtualizationEventPublisher`
- Integrates with VirtualizationWorkflow, AssetUpdateWorkflow
- Uses Event Bus for asynchronous coordination
- Uses VirtualizationBusinessRules, QueryExecutionBusinessRules, ResultBusinessRules for validation

**Key Methods**:
- `create_virtual_dataset()` - Create virtual dataset
- `execute_query()` - Execute query across sources
- `validate_schema_alignment()` - Validate schema compatibility

#### AIService ✅ (Implemented - MVP)

**Location**: `hub/apps/ai/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate ML operations with workflows
- Manage ML model lifecycle
- Handle ML result validation
- Coordinate schema matching with contract creation
- Publish AI/ML events (schema_matching_completed, classification_completed, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with AssetCreationWorkflow for schema matching
- Uses Event Bus for asynchronous coordination
- Uses AI business rules for validation (if implemented)

**Key Methods**:
- `match_schema()` - AI-powered schema matching
- `classify_asset()` - Auto-classification of assets
- `validate_ml_result()` - Validate ML model results

#### SocialService ✅ (Implemented - MVP)

**Location**: `hub/apps/social/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate ratings/reviews with asset updates
- Manage review moderation workflows
- Handle social feature events
- Coordinate activity feeds with asset operations
- Publish social events (review.created, rating.updated, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with SocialFeatureWorkflow
- Uses Event Bus for asynchronous coordination
- Uses Social business rules for validation (if implemented)

**Key Methods**:
- `create_review()` - Create asset review
- `update_rating()` - Update asset rating
- `moderate_review()` - Moderate review content

#### MarketplaceService ✅ (Implemented - MVP)

**Location**: `hub/apps/marketplace/services.py`
**Status**: ✅ Implemented
**Phase**: MVP

**Responsibilities**:
- Coordinate publishing with transformation/quality
- Manage purchase workflows
- Handle pricing model validation
- Coordinate marketplace events with asset updates
- Publish marketplace events (purchase.completed, pricing.changed, etc.)

**Integration**:
- Extends `BaseService`
- Integrates with MarketplacePublishingWorkflow
- Uses Event Bus for asynchronous coordination
- Uses MarketplaceBusinessRules for validation

**Key Methods**:
- `publish_listing()` - Publish asset to marketplace
- `create_purchase()` - Create purchase order
- `validate_pricing()` - Validate pricing model

---

## Workflow Integration

### Workflow Engine

All multi-step operations are orchestrated through the workflow engine:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
instance = engine.create_instance(
    workflow_name="asset_creation",
    input_data={"asset_id": "..."},
    tenant_id="...",
)
engine.start_instance(instance.id)
```

### Extended Workflows

#### AssetCreationWorkflow (Extended)

**New Steps**:
- AI schema matching
- Auto-classification
- ML-based quality checks

**DSL Example**:
```json
{
  "version": "1.0.0",
  "steps": [
    {"name": "create_asset", "type": "task", "task": "asset_creation.create_asset"},
    {"name": "ai_schema_matching", "type": "task", "task": "ai.schema_matching"},
    {"name": "auto_classification", "type": "task", "task": "ai.auto_classification"},
    {"name": "ml_quality_check", "type": "task", "task": "ai.ml_quality_check"}
  ]
}
```

#### TransformationPipelineWorkflow

**Steps**:
- Pipeline validation
- Pipeline execution
- Result synchronization
- Compensation on failure

#### MarketplacePublishingWorkflow

**Steps**:
- Transformation validation
- Quality check
- Pricing validation
- Listing creation

#### SocialFeatureWorkflow

**Steps**:
- Review validation
- Asset quality score update
- Notification

#### DataMeshWorkflow

**Steps**:
- Domain creation
- Asset ownership update
- Policy application

---

## Event-Driven Coordination

### Event Publishers

Services publish events for asynchronous coordination:

```python
from hub.apps.core.events.service_publishers import EventPublisher

class TransformationEventPublisher(EventPublisher):
    def publish_pipeline_completed(self, pipeline_id: str, result: dict):
        self.publish(
            event_type="transformation.pipeline_completed",
            data={"pipeline_id": pipeline_id, "result": result}
        )
```

### Event Handlers

Event handlers subscribe to events and trigger workflows:

```python
@event_handler("transformation.pipeline_completed")
def handle_pipeline_completed(event):
    # Update asset with pipeline results
    # Trigger asset update workflow
    pass
```

### Event Types

#### Transformation Events
- `transformation.pipeline_started`
- `transformation.pipeline_completed`
- `transformation.pipeline_failed`

#### AI/ML Events
- `ai.schema_matching_completed`
- `ai.classification_completed`
- `ai.recommendation_updated`

#### Social Events
- `social.review_created`
- `social.rating_updated`
- `social.comment_created`

#### Marketplace Events
- `marketplace.purchase_completed`
- `marketplace.pricing_changed`
- `marketplace.listing_updated`

#### Data Mesh Events
- `mesh.domain_created`
- `mesh.policy_applied`
- `mesh.topology_updated`

---

## Business Rules Framework ✅ (Implemented - Phase 9.7.2)

### Overview

The Business Rules Framework provides a standardized approach to validation and business logic enforcement across all services. All business rules classes follow consistent patterns for validation, error handling, and result reporting.

**Status**: ✅ Implemented (Phase 9.7.2)
**Location**: `hub/apps/core/business_rules/`
**Documentation**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`

### Framework Architecture

The framework consists of three main components:

1. **Base Classes** (`hub/apps/core/business_rules/base.py`)
   - `BusinessRules` - Abstract base class for all business rules
   - `ValidationResult` - Standardized validation result structure
   - `RuleExecutionContext` - Context for rule execution

2. **Common Utilities** (`hub/apps/core/business_rules/utils.py`)
   - Shared validation utilities
   - Tenant ID validation
   - User permission checking
   - Cross-tenant access validation
   - Schema structure validation

3. **Registry** (`hub/apps/core/business_rules/registry.py`)
   - Business rules registration
   - Rule discovery and loading
   - Rule execution coordination
   - Metrics and monitoring

### Framework Components

#### Base Class

**Location**: `hub/apps/core/business_rules/base.py`

The `BusinessRules` abstract base class provides:
- Standardized initialization with `tenant_id` and `user_id`
- Common validation patterns
- Error handling utilities
- Result creation helpers
- Tenant context validation

```python
from hub.apps.core.business_rules.base import BusinessRules, ValidationResult, RuleExecutionContext
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Standardized validation result structure."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

class BusinessRules(ABC):
    """Abstract base class for all business rules implementations."""

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @abstractmethod
    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """Main validation method (to be implemented by subclasses)."""
        pass

    def _create_result(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Helper method to create ValidationResult."""
        return ValidationResult(
            is_valid=is_valid,
            errors=errors or [],
            warnings=warnings or [],
            details=details or {}
        )

    def _validate_tenant_context(
        self,
        entity_tenant_id: Optional[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Validate tenant context consistency."""
        errors = []
        if self.tenant_id and entity_tenant_id:
            if str(entity_tenant_id) != str(self.tenant_id):
                errors.append(
                    f"Tenant mismatch: entity tenant ({entity_tenant_id}) "
                    f"does not match context tenant ({self.tenant_id})"
                )
        return errors
```

**Example Implementation**:
```python
from hub.apps.core.business_rules.base import BusinessRules, ValidationResult

class TransformationBusinessRules(BusinessRules):
    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """Main validation method"""
        pipeline = kwargs.get('pipeline')
        asset = kwargs.get('asset')

        errors = []
        warnings = []
        details = {}

        # Validate schema compatibility
        schema_result = self.validate_schema_alignment(pipeline, asset)
        if not schema_result.is_valid:
            errors.extend(schema_result.errors)
            details['schema_validation'] = schema_result.details

        # Validate data type compatibility
        type_result = self.validate_data_type_compatibility(pipeline, asset)
        if not type_result.is_valid:
            errors.extend(type_result.errors)
            details['type_validation'] = type_result.details

        result = self._create_result(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if kwargs.get('raise_on_error', False) and not result.is_valid:
            from hub.apps.core.services.base import ValidationError
            raise ValidationError(result.errors)

        return result
```

#### ValidationResult Pattern

All business rules return a standardized `ValidationResult`:

```python
@dataclass
class ValidationResult:
    """Standardized validation result structure."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]
```

**Usage**:
```python
result = rules.validate(pipeline=pipeline, asset=asset)
if result.is_valid:
    # Proceed with operation
    proceed_with_operation()
else:
    # Handle errors
    for error in result.errors:
        logger.error(f"Validation error: {error}")
    # Check warnings
    for warning in result.warnings:
        logger.warning(f"Validation warning: {warning}")
    # Access detailed validation information
    schema_details = result.details.get('schema_validation', {})
```

**ValidationResult Features**:
- **Boolean evaluation**: `if result:` checks `is_valid`
- **Error collection**: Comprehensive error messages with context
- **Warning support**: Non-critical issues reported as warnings
- **Details dictionary**: Structured validation details for debugging and metrics
- **Consistent interface**: All business rules return same structure

#### Rule Execution Context

**Location**: `hub/apps/core/business_rules/base.py`

The `RuleExecutionContext` provides context for rule execution:

```python
@dataclass
class RuleExecutionContext:
    """Context for business rule execution."""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    resource: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        return {
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'resource_id': str(self.resource.id) if self.resource and hasattr(self.resource, 'id') else None,
            'metadata': self.metadata or {}
        }
```

**Extended Contexts**:
- `TransformationRuleExecutionContext` - Adds `pipeline`, `source_asset`, `target_asset`
- `DataMeshRuleExecutionContext` - Adds `domain`, `asset`
- `VirtualizationRuleExecutionContext` - Adds `virtual_dataset`, `query`

#### Framework Registry

**Location**: `hub/apps/core/business_rules/registry.py`

The registry provides:
- Rule registration and discovery
- Rule metadata management
- Metrics collection
- Rule execution coordination

**Registration**:
```python
from hub.apps.core.business_rules.registry import register_rule

@register_rule(
    rule_name="transformation_pipeline_validation",
    description="Validates transformation pipeline structure and compatibility",
    tags=["transformation", "pipeline", "validation"],
    priority=10
)
class TransformationBusinessRules(BusinessRules):
    # Implementation
    pass
```

**Discovery**:
```python
from hub.apps.core.business_rules.registry import BusinessRulesRegistry

registry = BusinessRulesRegistry()
rule_metadata = registry.get_rule("transformation_pipeline_validation")
rules = rule_metadata.rule_class(tenant_id=tenant_id, user_id=user_id)
```

**Registry Features**:
- Automatic rule discovery via decorator
- Rule metadata storage (name, description, tags, priority)
- Rule lookup by name or tags
- Metrics collection per rule
- Rule execution tracking

### Business Rules Implementations

#### Transformation Business Rules ✅ (Implemented - Phase 9.5.1)

**Location**: `hub/apps/transformation/business_rules.py`
**Class**: `TransformationBusinessRules`
**Registry Name**: `transformation_pipeline_validation`
**Phase**: 9.5.1

**Overview**:
The TransformationBusinessRules class provides comprehensive validation for transformation pipelines, ensuring pipeline structure integrity, node compatibility, schema alignment, and asset compatibility before execution.

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all validation checks
   - Accepts `TransformationRuleExecutionContext` or standard context
   - Supports validation type filtering (`structure`, `node_compatibility`, `schema_alignment`, `asset_compatibility`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_pipeline_structure()`** - Pipeline structure validation
   - Validates pipeline definition is valid JSON object
   - Ensures required fields (`version`, `steps`) are present
   - Validates step structure and ordering
   - Checks for duplicate step names
   - Validates node types are valid (`FILTER`, `JOIN`, `AGGREGATE`, `TRANSFORM`, `OUTPUT`)
   - Enforces node execution order constraints (e.g., `AGGREGATE` must come after `FILTER`)

3. **`validate_node_compatibility()`** - Node compatibility validation
   - Validates node dependencies are satisfied
   - Ensures required fields per node type are present
   - Validates node configuration structure
   - Checks node execution order constraints

4. **`validate_schema_alignment()`** - Schema alignment validation
   - Validates pipeline input/output schemas align with asset schemas
   - Checks data type compatibility
   - Validates field mappings
   - Ensures schema transformations are valid

5. **`validate_asset_compatibility()`** - Asset compatibility validation
   - Validates source asset compatibility with pipeline
   - Validates target asset compatibility (if specified)
   - Checks asset data types match pipeline requirements
   - Validates asset status allows pipeline execution

6. **`validate_cross_tenant_operations()`** - Cross-tenant validation
   - Ensures tenant isolation
   - Validates cross-tenant operation permissions
   - Checks tenant context consistency

7. **`validate_resource_quota()`** - Resource quota validation
   - Validates pipeline resource requirements
   - Checks tenant resource quotas
   - Ensures sufficient resources available

8. **`validate_pipeline_execution_permission()`** - Permission validation
   - Validates user permissions for pipeline execution
   - Checks pipeline ownership
   - Validates execution context

**Node Type Constraints**:
- **FILTER**: Can be first node, no dependencies
- **JOIN**: Requires FILTER nodes before it
- **AGGREGATE**: Requires FILTER and/or JOIN nodes before it
- **TRANSFORM**: Can come after FILTER, JOIN, or AGGREGATE
- **OUTPUT**: Should be last node, requires all other node types before it

**Required Fields per Node Type**:
- **FILTER**: `filter_expression`
- **JOIN**: `join_keys`, `join_type`
- **AGGREGATE**: `group_by`, `aggregation_functions`
- **TRANSFORM**: `transform_expression`
- **OUTPUT**: No specific required fields

**Example Usage**:
```python
from hub.apps.transformation.business_rules import TransformationBusinessRules
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
rules = TransformationBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate pipeline structure
structure_result = rules.validate_pipeline_structure(pipeline, raise_on_error=False)
if not structure_result.is_valid:
    for error in structure_result.errors:
        logger.error(f"Pipeline structure error: {error}")

# Validate pipeline compatibility with assets
compatibility_result = rules.validate_pipeline_compatibility(
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset,
    raise_on_error=True
)

# Full validation with context
context = TransformationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset
)
result = rules.validate(context=context, validation_type='all')
```

**Integration Points**:
- Used by `TransformationService` for pipeline validation before execution
- Integrated with `TransformationPipelineWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

#### Data Mesh Business Rules ✅ (Implemented - Phase 9.5.2)

**Location**: `hub/apps/mesh/business_rules.py`
**Classes**: `DataMeshBusinessRules`, `PolicyBusinessRules`, `TopologyBusinessRules`
**Registry Names**: `data_mesh_domain_validation`, `policy_validation`, `topology_calculation`
**Phase**: 9.5.2

**Overview**:
The Data Mesh business rules provide comprehensive validation for data mesh domains, including domain structure, ownership transfer, boundaries, policy conflicts, and topology calculations.

##### DataMeshBusinessRules

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all domain validation checks
   - Accepts `DataMeshRuleExecutionContext` or standard context
   - Supports validation type filtering (`structure`, `ownership`, `boundaries`, `policy_conflicts`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_domain_structure()`** - Domain structure validation
   - Validates domain name is present and non-empty
   - Ensures domain has valid tenant assignment
   - Validates boundaries structure (if present)
   - Validates capabilities structure (if present)
   - Validates resource_quota and resource_usage structures
   - Ensures owner belongs to same tenant as domain
   - Validates domain status is valid

3. **`validate_ownership_transfer()`** - Ownership transfer validation
   - Validates new owner exists (if provided)
   - Ensures new owner belongs to same tenant as domain
   - Validates transfer permissions
   - Checks for active dependencies that prevent transfer

4. **`validate_boundaries()`** - Domain boundaries validation
   - Validates boundaries structure is valid dictionary
   - Ensures boundary definitions are complete
   - Validates boundary constraints are consistent

5. **`validate_domain_boundary_definition()`** - Boundary definition validation
   - Validates boundary structure and constraints
   - Ensures boundary definitions are complete and consistent

6. **`validate_asset_domain_boundary()`** - Asset boundary validation
   - Validates asset placement within domain boundaries
   - Ensures asset meets boundary constraints
   - Checks asset compatibility with domain

7. **`validate_cross_domain_access()`** - Cross-domain access validation
   - Validates cross-domain access permissions
   - Checks domain access policies
   - Ensures tenant isolation

8. **`validate_domain_resource_quota()`** - Resource quota validation
   - Validates domain resource quotas
   - Checks resource usage against quotas
   - Ensures sufficient resources available

9. **`validate_domain_ownership()`** - Domain ownership validation
   - Validates domain ownership structure
   - Checks owner permissions
   - Ensures ownership consistency

10. **`validate_asset_ownership_transfer()`** - Asset ownership transfer validation
    - Validates asset ownership transfer operations
    - Checks transfer permissions
    - Validates source and target domains
    - Ensures transfer constraints are met

11. **`validate_policy_conflicts()`** - Policy conflict detection
    - Detects conflicting policies within domain
    - Identifies policy incompatibilities
    - Reports conflict details

12. **`validate_policy_compatibility()`** - Policy compatibility validation
    - Validates policy compatibility with domain
    - Checks policy constraints
    - Ensures policy consistency

**Example Usage**:
```python
from hub.apps.mesh.business_rules import DataMeshBusinessRules, PolicyBusinessRules
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
mesh_rules = DataMeshBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate domain structure
structure_result = mesh_rules.validate_domain_structure(domain, raise_on_error=False)
if not structure_result.is_valid:
    for error in structure_result.errors:
        logger.error(f"Domain structure error: {error}")

# Validate ownership transfer
transfer_result = mesh_rules.validate_ownership_transfer(
    domain=domain,
    new_owner_id=new_owner_id,
    raise_on_error=True
)

# Validate boundaries
boundaries_result = mesh_rules.validate_boundaries(domain.boundaries)
if not boundaries_result.is_valid:
    raise ValidationError(boundaries_result.errors)

# Full validation with context
context = DataMeshRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    domain=domain,
    asset=asset
)
result = mesh_rules.validate(context=context, validation_type='all')
```

##### PolicyBusinessRules

**Validation Methods**:
- **`validate_policy_application()`** - Policy application validation
  - Validates policy can be applied to domain/asset
  - Checks policy constraints
  - Ensures policy compatibility
  - Validates policy permissions

**Example Usage**:
```python
from hub.apps.mesh.business_rules import PolicyBusinessRules

policy_rules = PolicyBusinessRules(tenant_id=tenant_id, user_id=user_id)
result = policy_rules.validate_policy_application(
    policy=policy,
    domain=domain,
    raise_on_error=True
)
```

##### TopologyBusinessRules

**Methods**:
- **Relationship calculation** - Calculates domain relationships
- **Health metrics calculation** - Calculates domain health metrics

**Integration Points**:
- Used by `DataMeshService` for domain validation before operations
- Integrated with `DataMeshWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

#### Virtualization Business Rules ✅ (Implemented - Phase 9.5.3)

**Location**: `hub/apps/virtualization/business_rules.py`
**Classes**: `VirtualizationBusinessRules`, `QueryExecutionBusinessRules`, `ResultBusinessRules`
**Registry Name**: `virtualization_dataset_validation`
**Phase**: 9.5.3

**Overview**:
The Virtualization business rules provide comprehensive validation for virtual datasets, including query syntax validation, schema alignment, source compatibility, and query execution validation.

##### VirtualizationBusinessRules

**Validation Methods**:

1. **`validate()`** - Main validation orchestrator
   - Coordinates all virtualization validation checks
   - Accepts `VirtualizationRuleExecutionContext` or standard context
   - Supports validation type filtering (`query_syntax`, `schema_alignment`, `source_compatibility`, `all`)
   - Returns `ValidationResult` with comprehensive details

2. **`validate_query_syntax()`** - Query syntax validation
   - Validates query is not empty
   - Validates query contains required keywords for query type
   - Ensures query does not contain forbidden keywords (write operations)
   - Validates query structure is valid for query type
   - Supports SQL, SPARQL, REST, GraphQL, and Federated query types

3. **`validate_source_configuration()`** - Source configuration validation
   - Validates source configuration structure
   - Ensures source connection parameters are valid
   - Validates source credentials (if applicable)
   - Checks source availability

4. **`validate_query_mapping()`** - Query mapping validation
   - Validates query-to-source mapping is correct
   - Ensures query fields map to source fields
   - Validates mapping consistency

5. **`validate_caching_configuration()`** - Caching configuration validation
   - Validates cache configuration structure
   - Ensures cache parameters are valid
   - Checks cache compatibility with query type

6. **`validate_virtual_dataset_schema()`** - Virtual dataset schema validation
   - Validates virtual dataset schema structure
   - Ensures schema is complete and consistent
   - Validates schema compatibility with sources

7. **`validate_schema_alignment()`** - Schema alignment validation
   - Validates schema alignment across sources
   - Checks field mappings are consistent
   - Ensures data type compatibility
   - Validates schema transformations

8. **`validate_source_compatibility()`** - Source compatibility validation
   - Validates source compatibility with query type
   - Checks source supports required query language
   - Ensures source capabilities match requirements

9. **`validate_cross_source_compatibility()`** - Cross-source compatibility validation
   - Validates multiple sources are compatible
   - Checks source schemas can be aligned
   - Ensures federated query feasibility

10. **`validate_cross_tenant_access()`** - Cross-tenant access validation
    - Validates cross-tenant access permissions
    - Ensures tenant isolation
    - Checks access policies

11. **`validate_query_language_compatibility()`** - Query language compatibility validation
    - Validates query language is compatible with sources
    - Checks language support per source
    - Ensures language consistency

12. **`validate_source_connections()`** - Source connection validation
    - Validates source connection configurations
    - Checks connection parameters
    - Ensures connection security

**Query Type Support**:
- **SQL**: PostgreSQL, MySQL, SQL Server, MSSQL sources
- **SPARQL**: SPARQL endpoints
- **REST**: REST API sources
- **GraphQL**: GraphQL API sources
- **FEDERATED**: Multiple source types combined

**Forbidden Keywords** (Write Operations):
- **SQL**: `DROP`, `DELETE`, `TRUNCATE`, `ALTER`, `CREATE TABLE`, `CREATE DATABASE`, `CREATE SCHEMA`, `DROP TABLE`, `DROP DATABASE`
- **SPARQL**: `INSERT`, `DELETE`, `DROP`, `CREATE`, `LOAD`, `CLEAR`

**Required Keywords**:
- **SQL**: At least one of `SELECT`, `WITH`, `INSERT`, `UPDATE`
- **SPARQL**: At least one of `SELECT`, `CONSTRUCT`, `ASK`, `DESCRIBE`, `PREFIX`

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import VirtualizationBusinessRules
from hub.apps.virtualization.models import QueryType
from hub.apps.core.business_rules.base import RuleExecutionContext

# Initialize rules
rules = VirtualizationBusinessRules(tenant_id=tenant_id, user_id=user_id)

# Validate query syntax
query_result = rules.validate_query_syntax(
    query=query_string,
    query_type=QueryType.SQL,
    raise_on_error=False
)
if not query_result.is_valid:
    for error in query_result.errors:
        logger.error(f"Query syntax error: {error}")

# Validate schema alignment
schema_result = rules.validate_schema_alignment(
    virtual_dataset=virtual_dataset,
    sources=sources,
    raise_on_error=True
)

# Full validation with context
context = VirtualizationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    virtual_dataset=virtual_dataset,
    query=query_string
)
result = rules.validate(context=context, validation_type='all')
```

##### QueryExecutionBusinessRules

**Methods**:
- **`validate_timeout()`** - Query timeout validation
  - Validates timeout configuration
  - Ensures timeout values are reasonable
  - Checks timeout compatibility with query type
- **Query optimization** - Optimizes query execution
- **Execution mode selection** - Selects SYNC vs ASYNC execution mode

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import QueryExecutionBusinessRules

execution_rules = QueryExecutionBusinessRules()
timeout_result = execution_rules.validate_timeout(
    timeout_seconds=300,
    query_type=QueryType.SQL,
    raise_on_error=True
)
```

##### ResultBusinessRules

**Methods**:
- **`validate_result_caching()`** - Result caching validation
  - Validates cache configuration
  - Ensures cache parameters are valid
  - Checks cache compatibility
- **`validate_pagination()`** - Pagination validation
  - Validates pagination parameters
  - Ensures pagination is consistent
  - Checks pagination limits

**Example Usage**:
```python
from hub.apps.virtualization.business_rules import ResultBusinessRules

result_rules = ResultBusinessRules()
cache_result = result_rules.validate_result_caching(
    cache_config=cache_config,
    raise_on_error=True
)
```

**Integration Points**:
- Used by `VirtualizationService` for virtual dataset validation before operations
- Integrated with `VirtualizationWorkflow` for workflow validation
- Registered in `BusinessRulesRegistry` for discovery and metrics

### Rule Validation in Service Layer

Rules are validated in service layer:

```python
from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.business_rules import TransformationBusinessRules

class TransformationService(BaseService):
    def execute_pipeline(self, pipeline_id: str, asset_id: str):
        pipeline = self.get_resource_or_raise(Pipeline, pipeline_id)
        asset = self.get_resource_or_raise(Asset, asset_id)

        # Validate using business rules
        rules = TransformationBusinessRules(
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )
        validation = rules.validate_pipeline_compatibility(pipeline, asset, raise_on_error=True)

        # Execute pipeline
        # Publish events
        pass
```

### Common Patterns

#### 1. Initialization Pattern

All business rules accept `tenant_id` and `user_id` during initialization:

```python
rules = TransformationBusinessRules(
    tenant_id=tenant_id,
    user_id=user_id
)
```

#### 2. Validation Method Pattern

All validation methods:
- Return `ValidationResult`
- Support `raise_on_error` parameter (default: `False`)
- Collect errors and warnings in lists
- Provide detailed context in `details` dictionary
- Raise exceptions when `raise_on_error=True` and validation fails

```python
result = rules.validate_pipeline_structure(
    pipeline=pipeline,
    raise_on_error=False
)
if not result.is_valid:
    # Handle errors
    pass
```

#### 3. Error Handling Pattern

Consistent use of `ValidationError` from `hub.apps.core.services.base`:

```python
from hub.apps.core.services.base import ValidationError

if raise_on_error and not result.is_valid:
    raise ValidationError(
        "; ".join(result.errors),
        code="VALIDATION_FAILED",
        details=result.details
    )
```

#### 4. Error Message Pattern

Comprehensive context in error messages and `details` dictionary:

```python
errors.append(
    f"Pipeline structure validation failed: "
    f"pipeline_id={pipeline.id}, "
    f"missing_fields={missing_fields}, "
    f"validation_type='structure'"
)
details.update({
    "pipeline_id": str(pipeline.id),
    "pipeline_name": pipeline.name,
    "validation_checks": validation_checks,
    "missing_fields": missing_fields
})
```

#### 5. Context Pattern

Use `RuleExecutionContext` for complex validations:

```python
context = TransformationRuleExecutionContext(
    tenant_id=tenant_id,
    user_id=user_id,
    pipeline=pipeline,
    source_asset=source_asset,
    target_asset=target_asset
)
result = rules.validate(context=context, validation_type='all')
```

#### 6. Registry Pattern

Register rules with metadata for discovery and metrics:

```python
@register_rule(
    rule_name="transformation_pipeline_validation",
    description="Validates transformation pipeline structure and compatibility",
    tags=["transformation", "pipeline", "validation"],
    priority=10
)
class TransformationBusinessRules(BusinessRules):
    pass
```

### Framework Benefits (Phase 9.7.2)

The framework standardization (Phase 9.7.2) provides:

1. **Consistency**: All business rules follow same patterns
2. **Maintainability**: Centralized base classes and utilities
3. **Discoverability**: Registry enables rule discovery
4. **Testability**: Standardized interfaces enable comprehensive testing
5. **Metrics**: Built-in metrics collection per rule
6. **Documentation**: Standardized patterns enable better documentation
7. **Extensibility**: Easy to add new business rules following patterns

### Framework Implementation Status

**Phase 9.7.2 Implementation**:
- ✅ Base class (`BusinessRules`) implemented
- ✅ `ValidationResult` standardized
- ✅ `RuleExecutionContext` implemented
- ✅ Common utilities created
- ✅ Registry implemented
- ✅ All existing business rules migrated to framework
- ✅ Framework documentation created
- ✅ Framework review completed

**Business Rules Using Framework**:
- ✅ TransformationBusinessRules (Phase 9.5.1)
- ✅ DataMeshBusinessRules (Phase 9.5.2)
- ✅ VirtualizationBusinessRules (Phase 9.5.3)
- ✅ ContractsBusinessRules (MVP)
- ✅ AssetsBusinessRules (MVP)
- ✅ DatasetsBusinessRules (MVP)
- ✅ MarketplaceBusinessRules (MVP)
- ✅ And 20+ other business rules classes

### Documentation

- **Framework Review**: `docs/BUSINESS_RULES_FRAMEWORK_REVIEW.md`
- **Integration Guide**: This document
- **Framework Base**: `hub/apps/core/business_rules/base.py`
- **Framework Registry**: `hub/apps/core/business_rules/registry.py`
- **Framework Utilities**: `hub/apps/core/business_rules/utils.py`

---

## Compensation Logic

### Compensation Pattern (Saga)

Workflows define compensation for rollback:

```json
{
  "version": "1.0.0",
  "compensation": {"enabled": true},
  "steps": [
    {
      "name": "create_resource",
      "type": "task",
      "task": "create_resource_task",
      "compensation": {
        "type": "task",
        "task": "delete_resource_task"
      }
    }
  ]
}
```

### Compensation Execution

Compensation is executed automatically on failure:

```python
# Workflow engine automatically executes compensation
# when a step fails and compensation is enabled
```

---

## Data Consistency

### Consistency Service

```python
from hub.apps.core.consistency.service import ConsistencyService

class ConsistencyService:
    def maintain_transformation_asset_consistency(self, pipeline_id: str, asset_id: str):
        # Sync pipeline results with asset
        # Validate consistency
        # Report inconsistencies
        pass
```

### Event-Driven Consistency

Consistency is maintained through event handlers:

```python
@event_handler("transformation.pipeline_completed")
def maintain_consistency(event):
    consistency_service = ConsistencyService()
    consistency_service.maintain_transformation_asset_consistency(
        event.data["pipeline_id"],
        event.data["asset_id"]
    )
```

### Scheduled Consistency Checks

```python
# Scheduled job runs consistency checks
@periodic_task(run_every=timedelta(hours=1))
def check_consistency():
    consistency_service = ConsistencyService()
    consistency_service.validate_all_consistency()
```

---

## Frontend Integration

### Workflow Progress Tracking

Frontend tracks workflow progress via React Query and WebSocket:

```typescript
import { useWorkflowProgress } from '@/hooks/useWorkflowProgress';

function TransformationPipelineProgress({ pipelineId }: { pipelineId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'transformation_pipeline',
    pipelineId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

### State Synchronization

Frontend state is synchronized with backend via WebSocket:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function useWorkflowUpdates(workflowName: string, instanceId: string) {
  const { data, queryClient } = useWebSocket(`workflow.${workflowName}.${instanceId}`);

  useEffect(() => {
    if (data) {
      queryClient.setQueryData(
        ['workflow', workflowName, instanceId],
        data
      );
    }
  }, [data, workflowName, instanceId, queryClient]);
}
```

---

## Service Integration Patterns ✅ (Implemented - Phase 9.7.3)

### Overview

Service integration patterns define standard approaches for service-to-service communication in the Data Interoperability Hub. These patterns ensure reliable, scalable, and maintainable inter-service coordination.

**Status**: ✅ Implemented (Phase 9.7.3)
**Documentation**: `docs/SERVICE_INTEGRATION_PATTERNS.md`

### Pattern 1: Direct Service Calls (Synchronous) ✅

**When to Use**:
- Simple operations requiring immediate response
- Real-time validation or data retrieval
- Low latency requirements (< 1 second)
- Strong consistency required
- Simple request-response interactions

**Implementation**:
- All service clients follow consistent pattern with:
  - HTTP client (httpx) with connection pooling
  - Retry logic with exponential backoff
  - Circuit breaker for fault tolerance
  - Distributed tracing support
  - Health check capabilities

**Service Clients**:
- `ComplianceServiceClient` (`hub/apps/compliance/service_client.py`)
- `DQServiceClient` (`hub/apps/dq/service_client.py`)
- `SemanticServiceClient` (`hub/apps/semantic/service_client.py`)
- `DataContractCLIClient` (`hub/apps/contracts/cli_client.py`)
- `WebhookDeliveryClient` (`hub/apps/webhooks/service_client.py`) ✅ New
- `ServiceHealthClient` (`hub/apps/core/services/health_client.py`) ✅ New

**Example**:
```python
from hub.apps.compliance.service_client import ComplianceServiceClient

client = ComplianceServiceClient()
result = client.scan_asset(asset_id=asset_id, tenant_id=tenant_id)
```

### Pattern 2: Event-Driven Coordination (Asynchronous) ✅

**When to Use**:
- Decoupled operations where immediate response not needed
- Eventual consistency acceptable
- High scalability requirements
- Multiple subscribers need to react to same event
- Long-running operations

**Implementation**:
- Redis Pub/Sub for real-time event delivery
- PostgreSQL for event persistence, replay, and audit
- Dead letter queue for failed events
- Event schema validation

**Event Publishers**:
- `TransformationEventPublisher` - Publishes `transformation.*` events
- `DataMeshEventPublisher` - Publishes `mesh.*` events
- `VirtualizationEventPublisher` - Publishes `virtualization.*` events
- `ContractEventPublisher` - Publishes `contract.*` events
- `AssetEventPublisher` - Publishes `asset.*` events

**Example**:
```python
from hub.apps.core.events import EventPublisher

publisher = EventPublisher(
    service_name="transformation_service",
    tenant_id=tenant_id,
    user_id=user_id
)
event_id = publisher.publish(
    event_type="transformation.pipeline.executed",
    data={"pipeline_id": pipeline_id, "result": result}
)
```

### Pattern 3: Workflow Orchestration (Multi-Step) ✅

**When to Use**:
- Complex multi-step operations
- Operations requiring compensation
- Long-running processes
- Operations with dependencies between steps
- Operations requiring state management

**Implementation**:
- Workflow Engine for orchestration
- Workflow DSL for definitions
- Compensation support (Saga pattern)
- State management
- Progress tracking

**Workflows**:
- `TransformationPipelineWorkflow` - Pipeline execution orchestration
- `DataMeshWorkflow` - Domain operations orchestration
- `VirtualizationWorkflow` - Virtual dataset operations orchestration
- `AssetCreationWorkflow` - Asset creation orchestration
- `ContractCreationWorkflow` - Contract creation orchestration

**Example**:
```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
instance = engine.create_instance(
    workflow_name="transformation_pipeline",
    input_data={"pipeline_id": pipeline_id, "asset_id": asset_id},
    tenant_id=tenant_id
)
engine.start_instance(instance.id)
```

### Pattern Selection Criteria

**Use Direct Service Calls when**:
- ✅ Immediate response required
- ✅ Strong consistency needed
- ✅ Simple request-response
- ✅ Low latency critical

**Use Event-Driven when**:
- ✅ Decoupled operations acceptable
- ✅ Eventual consistency acceptable
- ✅ High throughput needed
- ✅ Multiple subscribers

**Use Workflow Orchestration when**:
- ✅ Multi-step operations
- ✅ Compensation needed
- ✅ Long-running processes
- ✅ Complex dependencies

### Anti-Patterns to Avoid

1. **Direct HTTP calls outside service clients** ❌
   - Use service clients with circuit breakers and retry logic
   - Example: Use `WebhookDeliveryClient` instead of `requests.post()`

2. **Synchronous calls in event handlers** ❌
   - Event handlers should be fast and non-blocking
   - Use workflows for complex operations triggered by events

3. **Services not extending BaseService** ❌
   - All business logic services should extend `BaseService`
   - Provides consistent error handling, metrics, tenant scoping

4. **Missing circuit breakers** ❌
   - All service clients must have circuit breakers
   - Prevents cascading failures

5. **Missing retry logic** ❌
   - All service clients must have retry logic
   - Handles transient failures gracefully

### Documentation

- **Full Patterns Documentation**: `docs/SERVICE_INTEGRATION_PATTERNS.md`
- **Audit Report**: `docs/api-audit/SERVICE_INTEGRATION_AUDIT_REPORT.md`
- **Remediation Report**: `docs/api-audit/SERVICE_INTEGRATION_REMEDIATION_COMPLETE.md`

---

## Best Practices

### Service Layer

1. **Single Responsibility**: Each service has a clear responsibility
2. **Dependency Injection**: Services use dependency injection
3. **Event Publishing**: Services publish events for coordination
4. **Error Handling**: Services handle errors consistently
5. **Transaction Management**: Services manage transaction boundaries
6. **BaseService Extension**: All services extend `BaseService` ✅

### Workflow Integration

1. **Workflow DSL**: Use workflow DSL for workflow definitions
2. **Compensation**: Always define compensation for critical operations
3. **State Management**: Use workflow state for multi-step operations
4. **Error Handling**: Handle workflow failures gracefully
5. **Progress Tracking**: Track workflow progress for user experience

### Event-Driven Coordination

1. **Event Schema**: Define event schemas clearly
2. **Event Versioning**: Version events for backward compatibility
3. **Event Correlation**: Track event correlation for debugging
4. **Event Replay**: Support event replay for recovery
5. **Event Monitoring**: Monitor event processing

### Business Rules

1. **Centralized Rules**: Keep rules in centralized framework ✅
2. **Rule Testing**: Test rules independently
3. **Rule Configuration**: Make rules configurable per tenant
4. **Rule Documentation**: Document all business rules ✅
5. **Rule Validation**: Validate rules at service layer ✅
6. **ValidationResult Pattern**: Use standardized ValidationResult ✅

### Service Integration Patterns

1. **Use Service Clients**: Always use service clients for HTTP calls ✅
2. **Circuit Breakers**: All service clients must have circuit breakers ✅
3. **Retry Logic**: All service clients must have retry logic ✅
4. **Distributed Tracing**: Propagate trace headers across service calls ✅
5. **Health Checks**: All service clients must support health checks ✅

### Data Consistency

1. **Eventual Consistency**: Use eventual consistency model
2. **Consistency Validation**: Validate consistency regularly
3. **Consistency Metrics**: Track consistency metrics
4. **Consistency Monitoring**: Monitor consistency issues
5. **Consistency Recovery**: Recover from consistency issues

---

**Last Updated**: 2025-01-15
**Version**: 2.1.0

