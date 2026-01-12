# ODPS Backend Architecture Documentation

Complete engineering-grade documentation of the ODPS (Open Data Product Standard) backend architecture in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [Component Architecture](#component-architecture)
3. [Service Layer Architecture](#service-layer-architecture)
4. [Workflow Architecture](#workflow-architecture)
5. [Event System Architecture](#event-system-architecture)
6. [Job Queue Architecture](#job-queue-architecture)
7. [Database Schema](#database-schema)
8. [Data Flows](#data-flows)
9. [Integration Points](#integration-points)
10. [Architecture Diagrams](#architecture-diagrams)

---

## Overview

The ODPS backend architecture provides comprehensive support for the Open Data Product Standard, a marketplace-focused specification that complements ODCS (Open Data Contract Standard). The architecture is designed for:

- **Scalability**: Horizontal scaling with stateless services
- **Reliability**: Transaction management, compensation logic, and retry mechanisms
- **Security**: URL validation, path traversal prevention, rate limiting, and security logging
- **Observability**: Comprehensive event publishing, metrics, and audit logging
- **Maintainability**: Clean separation of concerns, dependency injection, and testability

### Key Architectural Principles

1. **Separation of Concerns**: Clear boundaries between parsing, normalization, generation, and resolution
2. **Dependency Injection**: Services and components are injected rather than tightly coupled
3. **Transaction Management**: Atomic operations with compensation logic for rollback
4. **Event-Driven**: Asynchronous coordination through event bus
5. **Security-First**: Security controls at every layer (validation, rate limiting, audit logging)

---

## Component Architecture

The ODPS backend consists of four core components: **Parser**, **Normalizer**, **Generator**, and **Ref Resolver**.

### 1. ODPS Parser (`hub/apps/contracts/odps_parser.py`)

**Purpose**: Parse and validate ODPS documents in JSON/YAML format.

**Key Features**:
- Automatic format detection (JSON/YAML)
- Schema validation using JSON Schema (Draft 2020-12)
- Version detection (ODPS 4.1, 4.0, etc.)
- Detailed error messages with file path and line number context
- Support for multiple ODPS versions

**Key Classes**:
- `ODPSParser`: Main parser class with static methods
- `ODPSValidationError`: Exception for parsing/validation errors

**Key Methods**:
```python
ODPSParser.parse(content: str, format: str) -> Dict[str, Any]
ODPSParser.validate(odps_document: Dict, version: str) -> Tuple[bool, List[Dict]]
```

**Error Handling**:
- `ODPSValidationError` with context (file_path, line_number, validation_errors, error_code)
- Graceful degradation for missing optional fields
- Field-level error tracking

**Dependencies**:
- `jsonschema` library for schema validation
- `yaml` library for YAML parsing
- `hub/apps/contracts/odps_schema.py` for ODPS schema definitions

---

### 2. ODPS Normalizer (`hub/apps/contracts/normalization/odps_normalizer.py`)

**Purpose**: Normalize ODPS documents to HubContract format.

**Key Features**:
- Version-specific normalization (ODPS 4.1, 4.0, 3.x, 2.x, 1.x)
- Comprehensive error handling with context
- Graceful degradation for missing optional fields
- Field-level error tracking
- Type validation and conversion

**Key Classes**:
- `ODPSNormalizer`: Main normalizer class implementing `SpecNormalizer` protocol
- Version-specific normalizers: `ODPSNormalizerV4_1`, `ODPSNormalizerV4_0`, etc.

**Key Methods**:
```python
ODPSNormalizer.normalize(contract_data: Dict, spec_version: Optional[str]) -> NormalizationResult
ODPSNormalizer.supports(spec_type: str, spec_version: str, contract_data: Dict) -> bool
```

**Normalization Flow**:
1. Detect ODPS version (if not provided)
2. Select version-specific normalizer
3. Map ODPS fields to HubContract structure:
   - `product.details[lang].productID` → `hub_contract.id`
   - `product.details[lang].name` → `hub_contract.info.name`
   - `product.marketplace.pricingPlans` → `hub_contract.marketplace.x_odps.pricing_plans`
   - `product.marketplace.accessMethods` → `hub_contract.marketplace.x_odps.access_methods`
4. Extract marketplace information (pricing, access methods, payment gateways)
5. Extract contract information (from `product.contract.spec` or `product.contract.$ref`)
6. Return `NormalizationResult` with hub_contract, status, errors, warnings

**Error Handling**:
- `ODPSNormalizationError` with context (field_path, expected, actual)
- Field-level error tracking in `NormalizationResult.errors`
- Warnings for missing optional fields in `NormalizationResult.warnings`

**Dependencies**:
- `hub/apps/contracts/normalization.py` for `NormalizationResult` and `SpecNormalizer`
- `hub/apps/contracts/odps_version_detection.py` for version detection

---

### 3. ODPS Generator (`hub/apps/contracts/odps_generator.py`)

**Purpose**: Generate ODPS documents from HubContract format (reverse operation of normalization).

**Key Features**:
- ODPS 4.1 generation (latest version)
- Comprehensive error handling with `ODPSExportError`
- Field-level error context (field name, expected type, actual type)
- Support for YAML and JSON output formatting
- Optional embedding of original ODCS contract inline

**Key Functions**:
```python
generate_odps_from_hubcontract(
    hub_contract: Dict,
    target_version: str = "4.1",
    original_odcs_contract: Optional[Dict] = None,
    original_odcs_url: Optional[str] = None
) -> Dict[str, Any]
```

**Generation Flow**:
1. Validate HubContract structure (required sections: `info`)
2. Map HubContract fields to ODPS structure:
   - `hub_contract.id` → `product.details[lang].productID`
   - `hub_contract.info.name` → `product.details[lang].name`
   - `hub_contract.marketplace.x_odps.pricing_plans` → `product.marketplace.pricingPlans`
   - `hub_contract.marketplace.x_odps.access_methods` → `product.marketplace.accessMethods`
3. Embed original ODCS contract (if provided) as `product.contract.spec`
4. Reference original ODCS contract URL (if provided) as `product.contract.contractURL`
5. Return ODPS document dictionary

**Error Handling**:
- `ODPSExportError` with context (field_path, expected, actual)
- Validation errors for missing required sections
- Type conversion errors with detailed context

**Dependencies**:
- `yaml` library for YAML output (optional)
- `json` library for JSON output

---

### 4. Ref Resolver (`hub/apps/contracts/ref_resolver.py`)

**Purpose**: Securely resolve `$ref` references in ODPS documents (internal, local, external).

**Key Features**:
- **Three Reference Types**:
  - **Internal**: References within the same document (`#/definitions/...`)
  - **Local**: References to local files (`./path/to/file.json`)
  - **External**: References to external URLs (`https://example.com/schema.json`)
- **Security Features**:
  - URL validation (allowlist/denylist)
  - Path traversal prevention
  - Size limits (per-ref and total)
  - Timeout controls (per-ref and total)
  - Redis caching for external refs (TTL: 1 hour)
  - Rate limiting (global, tenant, user)
  - Security logging (all security events)
- **Progress Tracking**: Progress events for long-running resolution operations

**Key Classes**:
- `RefResolver`: Main resolver class
- `ODPSRefsConfig`: Configuration for ref resolution (allowlists, denylists, base directories)
- `ExternalRefHandling`: Enum for external ref handling modes (RESOLVE, SKIP, DISABLE)

**Key Methods**:
```python
RefResolver.resolve_all_refs(
    document: Dict,
    preserve_original: bool = True,
    external_ref_handling: ExternalRefHandling = ExternalRefHandling.RESOLVE
) -> Tuple[Dict, Dict]

RefResolver.resolve_internal(ref_path: str, document: Dict) -> Any
RefResolver.resolve_local(ref_path: str) -> Dict[str, Any]
RefResolver.resolve_external(url: str) -> Dict[str, Any]
```

**Security Controls**:
1. **URL Validation** (`_validate_external_url`):
   - Scheme validation (only `https://` allowed)
   - URL length limit (`MAX_URL_LENGTH = 2048`)
   - Allowlist/denylist checking
   - Malformed URL detection

2. **Path Traversal Prevention** (`resolve_local`):
   - Base directory validation
   - Path normalization and resolution
   - Allowed directories checking
   - Security violation logging

3. **Size Limits** (`_check_size_limit`):
   - Per-ref size limit (default: 1MB)
   - Total size limit (default: 10MB)
   - Security violation logging

4. **Timeout Controls** (`_check_timeout`):
   - Per-ref timeout (default: 30s)
   - Total timeout (default: 5 minutes)
   - Security violation logging

5. **Rate Limiting** (`hub/apps/contracts/odps_rate_limiting.py`):
   - Global rate limit (default: 1000 requests/hour)
   - Tenant rate limit (default: 100 requests/hour)
   - User rate limit (default: 50 requests/hour)
   - Redis-based rate limiting

6. **Security Logging** (`hub/apps/contracts/odps_security_logging.py`):
   - All security events logged to `SecurityAuditLog` model
   - Event types: `EXTERNAL_REF_FETCH`, `RATE_LIMIT_EXCEEDED`, `SECURITY_VIOLATION`, `CACHE_HIT`, `CACHE_MISS`
   - Severity levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

**Dependencies**:
- `redis` for caching and rate limiting
- `requests` for HTTP requests (external refs)
- `hub/apps/contracts/config/odps_refs_config.py` for configuration
- `hub/apps/contracts/models.py` for `SecurityAuditLog` model

---

## Service Layer Architecture

The service layer provides business logic for ODPS operations, encapsulating transaction management, event publishing, and error handling.

### 1. ODPSService (`hub/apps/contracts/services.py`)

**Purpose**: Service for ODPS-specific operations.

**Key Responsibilities**:
- ODPS contract creation
- ODPS normalization
- ODPS linking to ODCS
- ODPS export
- ODPS generation from HubContract

**Key Methods**:
```python
ODPSService.create_odps(
    odps_raw: str,
    odps_format: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    resolve_external_refs: bool = True,
    target_version: Optional[str] = None
) -> Contract

ODPSService.normalize_odps(
    odps_doc: Dict[str, Any],
    odps_version: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]

ODPSService.export_odps(
    contract_id: str,
    target_version: str = "4.1",
    output_format: str = "json",
    tenant_id: Optional[str] = None
) -> str

ODPSService.generate_odps_from_hubcontract(
    hub_contract: Dict[str, Any],
    target_version: str = "4.1",
    original_odcs_contract: Optional[Dict[str, Any]] = None,
    original_odcs_url: Optional[str] = None
) -> Dict[str, Any]
```

**Transaction Management**:
- All operations wrapped in `@transaction.atomic`
- Compensation logic for rollback on failure
- State tracking for compensation (`ODPSCreationState`, `ODPSLinkingState`)

**Event Publishing**:
- Extends `ODPSEventPublisher` for ODPS-specific events
- Publishes `odps.created`, `odps.normalized`, `odps.exported`, `odps.linked` events
- Event IDs tracked for compensation

**Error Handling**:
- `ValidationError` for validation failures
- `NotFoundError` for missing resources
- Compensation logic for partial failures

**Dependencies**:
- `BaseService` for metrics and common functionality
- `ODPSEventPublisher` for event publishing
- `ODPSParser`, `ODPSNormalizer`, `ODPSGenerator`, `RefResolver` for core operations
- `hub/apps/contracts/odps_compensation.py` for compensation logic

---

### 2. ContractService (`hub/apps/contracts/services.py`)

**Purpose**: Service for contract operations, including ODPS-ODCS coordination.

**Key Responsibilities**:
- Contract retrieval and validation
- ODPS-ODCS linking coordination
- Auto-generation of ODPS from ODCS
- Contract lifecycle management

**Key Methods**:
```python
ContractService.link_odps_to_odcs(
    odcs_contract_id: str,
    odps_contract_id: Optional[str] = None,
    odps_raw: Optional[str] = None,
    odps_format: Optional[str] = None,
    resolve_external_refs: bool = True,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Contract

ContractService.coordinate_odcs_odps_operations(
    odcs_contract_id: str,
    odps_operation: str,
    odps_contract_id: Optional[str] = None,
    odps_raw: Optional[str] = None,
    odps_format: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]
```

**ODPS-ODCS Coordination**:
- Validates linking compatibility
- Establishes bidirectional links (ODPS ↔ ODCS)
- Stores links in `hub_contract_json.extensions.x_odps.odcs_link` and `odps_link`
- Compensation logic for rollback

**Dependencies**:
- `ODPSService` for ODPS-specific operations
- `BaseService` for metrics and common functionality
- `ContractEventPublisher` and `ODPSEventPublisher` for event publishing
- `hub/apps/contracts/linking_validation.py` for linking validation

---

## Workflow Architecture

The workflow architecture orchestrates multi-step ODPS operations with proper error handling, retry logic, and compensation.

### ProductCreationWorkflow (`hub/apps/orchestration/workflows/product_creation.py`)

**Purpose**: Orchestrates the ODPS product creation process (Product-First flow).

**Workflow Steps**:
1. **parse_odps**: Parse ODPS document, validate schema, detect version
2. **resolve_refs**: Resolve $ref references (internal, local, external)
3. **extract_contract**: Extract ODCS from `product.contract` (required)
4. **validate_odcs**: Validate extracted ODCS contract
5. **normalize_odcs**: Normalize ODCS → HubContract (technical)
6. **normalize_odps**: Normalize ODPS → HubContract (marketplace)
7. **create_odcs_contract**: Create ODCS contract record
8. **create_odps_contract**: Create ODPS contract record
9. **link_contracts**: Establish bidirectional link (ODPS ↔ ODCS)
10. **link_data_file**: Link data file to ODPS contract (optional)
11. **index_for_search**: Index for search (ODPS product + ODCS technical)
12. **semantic_mapping**: Map ODPS to RDF (async job)

**Compensation Tasks**:
- `rollback_normalize_odcs`: Rollback ODCS normalization
- `rollback_normalize_odps`: Rollback ODPS normalization
- `rollback_odcs_contract`: Rollback ODCS contract creation
- `rollback_odps_contract`: Rollback ODPS contract creation
- `rollback_link_contracts`: Rollback contract linking
- `rollback_link_data_file`: Rollback data file linking

**Error Handling**:
- Transaction rollback on failure
- Compensation logic for partial failures
- Detailed error logging with context
- Workflow status tracking (`WorkflowStatus.PENDING`, `RUNNING`, `COMPLETED`, `FAILED`)

**Event Publishing**:
- Workflow events: `workflow.started`, `workflow.completed`, `workflow.failed`
- Step events: `workflow.step.started`, `workflow.step.completed`, `workflow.step.failed`
- ODPS events: `odps.created`, `odps.normalized`, `odps.linked`

**Dependencies**:
- `WorkflowEngine` for workflow orchestration
- `WorkflowRegistry` for workflow registration
- `ODPSParser`, `RefResolver`, `ODPSNormalizer` for core operations
- `SearchIndexer` for search indexing
- `hub/apps/semantic/utils.py` for semantic mapping

---

## Event System Architecture

The event system provides asynchronous coordination between services using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence.

### Event Bus (`hub/apps/core/events/bus.py`)

**Purpose**: Event-driven communication infrastructure.

**Components**:
1. **Redis Pub/Sub**: Real-time event delivery (fire-and-forget)
2. **PostgreSQL**: Event persistence for replay, audit, and debugging
3. **Dead Letter Queue**: Failed event storage
4. **Event Schema**: JSON Schema validation

**Key Classes**:
- `EventBus`: Main event bus class
- `EventPublisher`: Convenience class for publishing events
- `EventSubscriber`: Subscription management

**Event Publishing**:
```python
publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="odps.created",
    data={"contract_id": contract_id, "odps_version": "4.1"},
    tags=["odps", "contract"]
)
```

**Event Schema**:
```json
{
  "event_id": "uuid",
  "event_type": "odps.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "contract_service",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid",
    "odps_version": "4.1"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["odps", "contract"]
  }
}
```

**ODPS Event Types**:
- `odps.created`: ODPS contract created
- `odps.normalized`: ODPS contract normalized
- `odps.exported`: ODPS contract exported
- `odps.linked`: ODPS contract linked to ODCS
- `odps.ref.progress`: $ref resolution progress
- `odps.ref.completed`: $ref resolution completed
- `odps.ref.failed`: $ref resolution failed

**Event Subscribers**:
- `SearchService`: Index contracts for search
- `NotificationService`: Send creation notifications
- `AuditService`: Log contract operations
- `WebhookService`: Deliver webhooks
- `SemanticService`: Trigger semantic mapping

**Dependencies**:
- `redis` for Pub/Sub
- `PostgreSQL` for persistence
- `hub/apps/core/events/schema.py` for event schema validation

---

## Job Queue Architecture

The job queue system processes asynchronous ODPS operations using Redis-backed queues (django-rq).

### Priority Queues

**Three Priority Levels**:
- **HIGH** (`job_critical`): Critical long-running jobs (DQ runs, compliance runs)
- **NORMAL** (`job_default`): Standard jobs (semantic mapping, ODPS normalization, ref resolution)
- **LOW** (`job_low`): Quick validation jobs (contract validation)

**Queue Configuration** (`hub/settings.py`):
```python
RQ_QUEUES = {
    "job_critical": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 1800,  # 30 minutes
    },
    "job_default": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 360,  # 6 minutes
    },
    "job_low": {
        "URL": REDIS_QUEUE_URL,
        "DEFAULT_TIMEOUT": 60,  # 1 minute
    },
}
```

### ODPS Job Types

**Job Types** (`hub/apps/jobs/models.py`):
- `ODPS_NORMALIZATION`: Normalize ODPS contract (NORMAL priority, 10 min timeout)
- `ODPS_REF_RESOLUTION`: Resolve $ref references (NORMAL priority, 10 min timeout)
- `ODPS_EXPORT`: Export ODPS contract (NORMAL priority, 5 min timeout)
- `ODPS_SEMANTIC_MAPPING`: Map ODPS to RDF (NORMAL priority, 10 min timeout)
- `ODPS_LINKING`: Link ODPS to ODCS (NORMAL priority, 5 min timeout)

**Job Execution** (`hub/apps/jobs/tasks.py`):
```python
def _execute_odps_ref_resolution_job(job_obj: Job) -> dict:
    """
    Execute ODPS_REF_RESOLUTION job.

    Resolves all $ref references in an ODPS contract with progress tracking
    and event publishing.
    """
    # Get contract
    contract = Contract.objects.get(id=contract_id)

    # Parse ODPS document
    odps_doc = ODPSParser.parse(contract.original_raw, contract.original_format.lower())

    # Resolve refs with progress tracking
    resolver = RefResolver(tenant_id=tenant_id, user_id=user_id)
    resolved_doc, _ = resolver.resolve_all_refs(odps_doc)

    # Update contract with resolved document
    contract.original_raw_resolved = json.dumps(resolved_doc)
    contract.save()

    # Publish completion event
    odps_event_publisher.publish_odps_ref_completed(...)

    return {"refs_resolved": len(refs), "contract_id": str(contract.id)}
```

**Progress Tracking**:
- Progress events published via `odps.ref.progress` events
- Progress percentage tracked in `job.details_json.progress_percentage`
- Current phase tracked in `job.details_json.current_phase`

**Dependencies**:
- `django-rq` for job queue management
- `redis` for queue storage
- `hub/apps/jobs/models.py` for `Job` model
- `hub/apps/jobs/utils.py` for job creation utilities

---

## Database Schema

The database schema stores ODPS contracts, security audit logs, and workflow instances.

### Contract Model (`hub/apps/contracts/models.py`)

**Table**: `contracts`

**Key Fields**:
- `id`: UUID (primary key)
- `tenant`: Foreign key to `tenants.Tenant`
- `asset`: Foreign key to `assets.Asset` (nullable)
- `version`: Integer (per-asset version counter)
- `status`: CharField (DRAFT, ACTIVE, RETIRED)
- `original_spec_type`: CharField (ODCS, ODPS)
- `original_spec_version`: CharField (e.g., "4.1", "3.0.2")
- `original_format`: CharField (JSON, YAML)
- `original_raw`: TextField (original contract content)
- `original_raw_resolved`: TextField (resolved contract content, nullable)
- `hub_contract_version`: CharField (HubContract version, nullable)
- `hub_contract_json`: JSONField (normalized HubContract, GIN indexed)
- `normalization_status`: CharField (NOT_NORMALIZED, NORMALIZED_OK, NORMALIZED_WITH_WARNINGS, NORMALIZATION_FAILED)
- `normalization_errors`: JSONField (array of errors)
- `normalization_warnings`: JSONField (array of warnings)
- `validation_status`: CharField (VALID, INVALID, WARNING_ONLY, ERROR)
- `validation_errors`: JSONField (array of errors)
- `validation_warnings`: JSONField (array of warnings)
- `created_by`: Foreign key to `auth.User` (nullable)
- `created_at`: DateTimeField (auto_now_add)
- `updated_at`: DateTimeField (auto_now)

**Indexes**:
- `(tenant, asset)` - For tenant-asset queries
- `(tenant, status)` - For tenant status queries
- `(tenant, validation_status)` - For validation queries
- `hub_contract_json` - GIN index for JSONB queries (Django 6)

**Constraints**:
- Unique constraint: `(tenant, asset, version)` (when asset is not null)

**ODPS-Specific Fields**:
- `original_spec_type = "ODPS"` for ODPS contracts
- `hub_contract_json.extensions.x_odps.odcs_link` - Link to ODCS contract (bidirectional)
- `hub_contract_json.extensions.x_odps.odps_link` - Link to ODPS contract (in ODCS contracts)

---

### SecurityAuditLog Model (`hub/apps/contracts/models.py`)

**Table**: `security_audit_logs`

**Purpose**: Append-only security audit log for ODPS $ref resolution security events.

**Key Fields**:
- `id`: UUID (primary key)
- `event_type`: CharField (EXTERNAL_REF_FETCH, RATE_LIMIT_EXCEEDED, SECURITY_VIOLATION, CACHE_HIT, CACHE_MISS, CACHE_EVICTION)
- `timestamp`: DateTimeField (auto_now_add, indexed)
- `tenant`: Foreign key to `tenants.Tenant` (nullable)
- `user`: Foreign key to `auth.User` (nullable)
- `contract`: Foreign key to `contracts.Contract` (nullable)
- `severity`: CharField (LOW, MEDIUM, HIGH, CRITICAL, nullable)
- `ref_type`: CharField (internal, local, external, nullable)
- `ref_path`: CharField (max_length=2048, nullable)
- `resolved_path`: CharField (max_length=2048, nullable)
- `rate_limit_level`: CharField (global, tenant, user, nullable)
- `cache_operation`: CharField (hit, miss, eviction, nullable)
- `cache_key`: CharField (max_length=512, nullable)
- `violation_type`: CharField (max_length=100, nullable)
- `attempted_path`: CharField (max_length=2048, nullable)
- `attempted_url`: CharField (max_length=2048, nullable)
- `description`: TextField (nullable)
- `metadata_json`: JSONField (additional metadata)

**Indexes**:
- `(event_type, timestamp)` - For event type queries
- `(tenant, timestamp)` - For tenant queries
- `(user, timestamp)` - For user queries
- `(tenant, event_type, timestamp)` - For tenant-event queries
- `(tenant, user, timestamp)` - For tenant-user queries
- `(ref_type, timestamp)` - For ref type queries
- `(cache_operation, timestamp)` - For cache queries
- `(timestamp)` - For retention queries

**Constraints**:
- Append-only: Updates and deletes are prevented (override `save()` and `delete()`)

---

### WorkflowInstance Model (`hub/apps/orchestration/models.py`)

**Table**: `workflow_instances`

**Purpose**: Track workflow execution state.

**Key Fields**:
- `id`: UUID (primary key)
- `workflow_name`: CharField (e.g., "product_creation")
- `status`: CharField (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- `input_data`: JSONField (workflow input)
- `output_data`: JSONField (workflow output, nullable)
- `current_step_index`: IntegerField (current step)
- `error_message`: TextField (nullable)
- `error_details`: JSONField (nullable)
- `tenant`: Foreign key to `tenants.Tenant` (nullable)
- `created_by`: Foreign key to `auth.User` (nullable)
- `created_at`: DateTimeField (auto_now_add)
- `updated_at`: DateTimeField (auto_now)
- `completed_at`: DateTimeField (nullable)

**Indexes**:
- `(workflow_name, status)` - For workflow queries
- `(tenant, status)` - For tenant queries
- `(status, created_at)` - For status queries

---

## Data Flows

### ODPS Ingestion Flow

**Flow**: User → API → ODPSService → ProductCreationWorkflow → Database

**Steps**:
1. **API Request**: `POST /api/v1/contracts/products/` with ODPS document
2. **ODPSService.create_odps()**:
   - Parse ODPS document (`ODPSParser.parse()`)
   - Detect version (`detect_odps_version()`)
   - Validate schema (`ODPSParser.validate()`)
   - Resolve $ref references (`RefResolver.resolve_all_refs()`) [optional]
   - Normalize to HubContract (`ODPSNormalizer.normalize()`)
   - Create contract record (`Contract.objects.create()`)
   - Publish events (`odps.created`, `odps.normalized`)
3. **ProductCreationWorkflow** (if Product-First flow):
   - Extract ODCS from `product.contract`
   - Validate ODCS
   - Normalize ODCS → HubContract
   - Create ODCS contract record
   - Create ODPS contract record
   - Link contracts bidirectionally
   - Index for search
   - Trigger semantic mapping job
4. **Response**: Return created contracts and workflow instance ID

**Error Handling**:
- Validation errors return 400 Bad Request
- Compensation logic rolls back on failure
- Workflow status tracked in `WorkflowInstance`

---

### ODPS Normalization Flow

**Flow**: ODPS Document → ODPSNormalizer → HubContract

**Steps**:
1. **Version Detection**: Detect ODPS version from document
2. **Version-Specific Normalizer**: Select normalizer (V4_1, V4_0, etc.)
3. **Field Mapping**:
   - `product.details[lang].productID` → `hub_contract.id`
   - `product.details[lang].name` → `hub_contract.info.name`
   - `product.details[lang].description` → `hub_contract.info.description`
   - `product.marketplace.pricingPlans` → `hub_contract.marketplace.x_odps.pricing_plans`
   - `product.marketplace.accessMethods` → `hub_contract.marketplace.x_odps.access_methods`
   - `product.marketplace.paymentGateways` → `hub_contract.marketplace.x_odps.payment_gateways`
   - `license[lang].definition` → `hub_contract.marketplace.license_summary`
   - `license[lang].restrictions` → `hub_contract.marketplace.restricted_use`
   - `license[lang].rights` → `hub_contract.marketplace.intended_use`
4. **Contract Extraction**: Extract ODCS from `product.contract.spec` or `product.contract.$ref`
5. **Error Collection**: Collect errors and warnings
6. **Result**: Return `NormalizationResult` with hub_contract, status, errors, warnings

**Error Handling**:
- Field-level errors tracked in `NormalizationResult.errors`
- Warnings for missing optional fields in `NormalizationResult.warnings`
- `ODPSNormalizationError` raised for critical errors

---

### ODPS Export Flow

**Flow**: Contract → ODPSService → ODPSGenerator → ODPS Document

**Steps**:
1. **Contract Retrieval**: Get contract by ID
2. **HubContract Extraction**: Extract `hub_contract_json` from contract
3. **ODPS Generation**: `generate_odps_from_hubcontract()`:
   - Validate HubContract structure
   - Map HubContract fields to ODPS structure
   - Embed original ODCS contract (if linked) as `product.contract.spec`
   - Reference original ODCS contract URL (if available) as `product.contract.contractURL`
4. **Format Conversion**: Convert to JSON or YAML
5. **Response**: Return ODPS document string

**Error Handling**:
- `NotFoundError` if contract not found
- `ODPSExportError` for generation failures
- Validation errors for missing required sections

---

### ODPS Linking Flow

**Flow**: ODPS Contract + ODCS Contract → ContractService → Bidirectional Link

**Steps**:
1. **Validation**: Validate both contracts exist and are compatible
2. **Linking Validation**: Check for circular references, compatibility
3. **Bidirectional Link Creation**:
   - **ODPS → ODCS**: Store ODCS contract ID in `odps_contract.hub_contract_json.extensions.x_odps.odcs_link`
   - **ODCS → ODPS**: Store ODPS contract ID in `odcs_contract.hub_contract_json.extensions.x_odps.odps_link`
4. **Event Publishing**: Publish `odps.linked` event
5. **Response**: Return linked contracts

**Error Handling**:
- `ValidationError` for incompatible contracts
- `NotFoundError` if contracts not found
- Compensation logic for rollback on failure

---

## Integration Points

### Marketplace Service Integration

**Purpose**: Integrate ODPS marketplace information with marketplace listings.

**Integration Points**:
- **ContractMarketplacePolicyExtractor** (`hub/apps/marketplace/contract_integration.py`):
  - Reads marketplace policy from HubContract
  - Extracts pricing plans, access methods, payment gateways
  - Supports both ODCS contracts (with `marketplace.*` structure) and ODPS-linked contracts

**Event Integration**:
- `odps.created` event triggers marketplace listing creation
- `odps.normalized` event updates marketplace policy

**Dependencies**:
- `MarketplaceService` for marketplace operations
- `hub/apps/marketplace/services.py` for marketplace service

---

### Semantic Service Integration

**Purpose**: Map ODPS contracts to RDF/JSON-LD for semantic interoperability.

**Integration Points**:
- **Semantic Mapping** (`hub/apps/semantic/utils.py`):
  - `map_odps_to_semantic()`: Map ODPS contract to RDF
  - `map_odps_contract_to_semantic_via_service()`: Map via semantic service API
  - Triggered asynchronously via `ODPS_SEMANTIC_MAPPING` job

**Event Integration**:
- `odps.created` event triggers semantic mapping job
- `odps.normalized` event updates semantic mapping

**Dependencies**:
- `SemanticService` for RDF mapping
- `services/semantic-service/` for semantic service API

---

### Asset Service Integration

**Purpose**: Link ODPS contracts to assets for data product management.

**Integration Points**:
- **Asset-Contract Relationship**: ODPS contracts can be linked to assets via `contract.asset` foreign key
- **Asset Creation Workflow**: ODPS contracts can trigger asset creation workflows
- **Asset Activation**: ODPS contracts can activate assets when published

**Event Integration**:
- `odps.created` event triggers asset creation/update
- `odps.linked` event updates asset-contract relationships

**Dependencies**:
- `AssetService` for asset operations
- `hub/apps/assets/services.py` for asset service

---

### Event Bus Integration

**Purpose**: Asynchronous coordination between services.

**Integration Points**:
- **Event Publishing**: All ODPS operations publish events via `ODPSEventPublisher`
- **Event Subscribers**: Multiple services subscribe to ODPS events:
  - `SearchService`: Index contracts for search
  - `NotificationService`: Send creation notifications
  - `AuditService`: Log contract operations
  - `WebhookService`: Deliver webhooks
  - `SemanticService`: Trigger semantic mapping

**Event Types**:
- `odps.created`: ODPS contract created
- `odps.normalized`: ODPS contract normalized
- `odps.exported`: ODPS contract exported
- `odps.linked`: ODPS contract linked to ODCS
- `odps.ref.progress`: $ref resolution progress
- `odps.ref.completed`: $ref resolution completed
- `odps.ref.failed`: $ref resolution failed

**Dependencies**:
- `hub/apps/core/events/bus.py` for event bus
- `hub/apps/core/events/service_publishers.py` for `ODPSEventPublisher`

---

### Job Queue Integration

**Purpose**: Process long-running ODPS operations asynchronously.

**Integration Points**:
- **Job Creation**: ODPS operations create jobs via `hub/apps/jobs/utils.py`
- **Job Execution**: Jobs are processed by worker service (`services/worker/`)
- **Progress Tracking**: Jobs publish progress events via `odps.ref.progress`

**Job Types**:
- `ODPS_NORMALIZATION`: Normalize ODPS contract
- `ODPS_REF_RESOLUTION`: Resolve $ref references
- `ODPS_EXPORT`: Export ODPS contract
- `ODPS_SEMANTIC_MAPPING`: Map ODPS to RDF
- `ODPS_LINKING`: Link ODPS to ODCS

**Dependencies**:
- `django-rq` for job queue management
- `hub/apps/jobs/tasks.py` for job execution logic
- `services/worker/` for worker service

---

## Architecture Diagrams

### Component Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ODPS Backend Architecture                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Parser     │    │  Normalizer  │    │   Generator  │    │ Ref Resolver │
│              │    │              │    │              │    │              │
│ - Parse      │───▶│ - Normalize  │───▶│ - Generate   │───▶│ - Resolve    │
│ - Validate   │    │ - Map Fields │    │ - Export     │    │ - Security   │
│ - Detect Ver │    │ - Extract    │    │ - Format     │    │ - Cache      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │  ODPSService    │
                          │                 │
                          │ - create_odps() │
                          │ - normalize()   │
                          │ - export()      │
                          │ - link()        │
                          └─────────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ ProductCreation │
                          │    Workflow     │
                          │                 │
                          │ - Orchestrate   │
                          │ - Compensate    │
                          │ - Publish Events│
                          └─────────────────┘
```

---

### Data Flow Diagram

```
ODPS Ingestion Flow:

User Request
    │
    ▼
API Endpoint (POST /api/v1/contracts/products/)
    │
    ▼
ODPSService.create_odps()
    │
    ├─▶ ODPSParser.parse() ──────────┐
    │                                  │
    ├─▶ detect_odps_version()          │
    │                                  │
    ├─▶ ODPSParser.validate()          │
    │                                  │
    ├─▶ RefResolver.resolve_all_refs()│
    │                                  │
    └─▶ ODPSNormalizer.normalize() ────┼─▶ HubContract
                                       │
                                       ▼
                              Contract.objects.create()
                                       │
                                       ▼
                              ProductCreationWorkflow
                                       │
                                       ├─▶ Extract ODCS
                                       ├─▶ Normalize ODCS
                                       ├─▶ Create Contracts
                                       ├─▶ Link Contracts
                                       ├─▶ Index for Search
                                       └─▶ Semantic Mapping Job
```

---

### Integration Points Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ODPS Integration Points                  │
└─────────────────────────────────────────────────────────────┘

ODPSService
    │
    ├─▶ MarketplaceService ────▶ Marketplace Listings
    │
    ├─▶ SemanticService ────────▶ RDF/JSON-LD Mapping
    │
    ├─▶ AssetService ───────────▶ Asset-Contract Links
    │
    ├─▶ EventBus ────────────────▶ Event Subscribers
    │                                 │
    │                                 ├─▶ SearchService
    │                                 ├─▶ NotificationService
    │                                 ├─▶ AuditService
    │                                 ├─▶ WebhookService
    │                                 └─▶ SemanticService
    │
    └─▶ JobQueue ─────────────────▶ Worker Service
                                        │
                                        ├─▶ ODPS_NORMALIZATION
                                        ├─▶ ODPS_REF_RESOLUTION
                                        ├─▶ ODPS_EXPORT
                                        ├─▶ ODPS_SEMANTIC_MAPPING
                                        └─▶ ODPS_LINKING
```

---

## Summary

The ODPS backend architecture provides a comprehensive, engineering-grade implementation of the Open Data Product Standard with:

- **Component Architecture**: Parser, Normalizer, Generator, Ref Resolver
- **Service Layer**: ODPSService, ContractService with transaction management
- **Workflow Architecture**: ProductCreationWorkflow with compensation logic
- **Event System**: Event-driven coordination via Redis Pub/Sub and PostgreSQL
- **Job Queue**: Asynchronous processing with priority queues
- **Database Schema**: Contracts, SecurityAuditLog, WorkflowInstance models
- **Data Flows**: Ingestion, Normalization, Export, Linking flows
- **Integration Points**: Marketplace, Semantic, Asset, Event Bus, Job Queue integrations

All components follow Django and coding best practices, with comprehensive error handling, security controls, and observability.

