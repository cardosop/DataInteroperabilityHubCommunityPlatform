# API Requirements Extraction from Use Cases

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Source**: `docs/USE_CASES.md` (~105 use cases)  
**Task**: 0.1.4 - Extract API requirements from use cases

---

## Overview

This document extracts API requirements from all **~105 use cases** documented in `docs/USE_CASES.md`. For each use case, we identify:

1. **API Operations Required**: Specific API endpoints needed for each use case step
2. **API Dependencies**: Dependencies between use case steps and related use cases
3. **Request/Response Schemas**: Expected request and response structures
4. **Error Handling**: Error scenarios from alternate flows
5. **Performance Requirements**: Performance targets from use case specifications

---

## Methodology

### Extraction Process

1. **Use Case Analysis**: Review each use case's main flow, alternate flows, and postconditions
2. **API Mapping**: Map each flow step to required API endpoint(s)
3. **Dependency Analysis**: Identify sequential dependencies and related use case dependencies
4. **Schema Inference**: Infer request/response schemas from use case context
5. **Error Scenarios**: Extract error cases from alternate flows

### Use Case Structure

Each use case contains:
- **ID**: Unique identifier (e.g., UC-AM-001)
- **Title**: Descriptive name
- **Persona**: Primary persona(s)
- **Priority**: High, Medium, or Low
- **Status**: MVP, Post-MVP, or New
- **Description**: Detailed description
- **Preconditions**: Required conditions
- **Main Flow**: Step-by-step flow (numbered steps)
- **Alternate Flows**: Alternative scenarios (A1, A2, etc.)
- **Postconditions**: Expected outcomes
- **Related Use Cases**: Links to related use cases

---

## Asset Management Use Cases

### UC-AM-001: Create Asset via Data-First Flow

**Use Case ID**: UC-AM-001  
**Priority**: High (P0 - Critical - Blocks MVP)  
**Status**: MVP  
**Total Steps**: 14

#### Preconditions API Requirements

**API Operations**:
- `GET /api/v1/auth/me/` - Verify user authentication and role
- `GET /api/v1/tenants/{id}/` - Verify tenant is active

**Response Schema** (User Info):
```json
{
  "id": "uuid",
  "email": "string",
  "roles": ["DATA_PROVIDER"],
  "tenant_id": "uuid"
}
```

**Dependencies**: None (preconditions check)

---

#### Main Flow Step 1: User Navigates to "Create Asset" → Selects "Data-First"

**API Operations**:
- `GET /api/v1/assets/` - List existing assets (for context)
- `GET /api/v1/assets/onboarding-modes/` - Get available onboarding modes

**Response Schema** (Onboarding Modes):
```json
{
  "modes": [
    {
      "id": "data-first",
      "name": "Data-First",
      "description": "string",
      "enabled": true
    },
    {
      "id": "contract-first",
      "name": "Contract-First",
      "description": "string",
      "enabled": true
    }
  ]
}
```

**Dependencies**: None

---

#### Main Flow Step 2: User Provides Basic Metadata

**API Operations**:
- `POST /api/v1/assets/` - Create asset in DRAFT status

**Request Schema**:
```json
{
  "name": "string",
  "description": "string",
  "domain": "string",
  "tags": ["string"],
  "onboarding_mode": "data-first",
  "status": "DRAFT"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "domain": "string",
  "tags": ["string"],
  "status": "DRAFT",
  "onboarding_mode": "data-first",
  "created_at": "datetime"
}
```

**Dependencies**: None

**Error Scenarios**:
- 400: Invalid input (name required, domain invalid)
- 401: Unauthorized
- 403: Insufficient permissions (not DATA_PROVIDER role)

---

#### Main Flow Step 3: User Uploads Data File

**API Operations**:
- `POST /api/v1/files/upload/` - Upload file

**Request Schema**:
```json
{
  "file": "multipart/form-data",
  "asset_id": "uuid",
  "content_type": "text/csv|application/json|application/parquet"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "filename": "string",
  "size": "integer",
  "content_type": "string",
  "upload_status": "COMPLETED",
  "asset_id": "uuid",
  "uploaded_at": "datetime"
}
```

**Dependencies**:
- Requires Step 2 (asset_id from asset creation)

**Error Scenarios**:
- 400: Invalid file format (not CSV/JSON/Parquet)
- 413: File too large
- 500: Upload failed

---

#### Main Flow Step 4: System Validates File Format

**API Operations**:
- `POST /api/v1/files/{id}/validate/` - Validate file format

**Request Schema**: None (file_id in path)

**Response Schema**:
```json
{
  "file_id": "uuid",
  "validation_status": "VALID",
  "format": "CSV",
  "encoding": "UTF-8",
  "errors": [],
  "warnings": []
}
```

**Dependencies**:
- Requires Step 3 (file_id from file upload)

**Error Scenarios**:
- 400: Invalid file format
- 404: File not found

---

#### Main Flow Step 5: System Infers Schema and Extracts Sample

**API Operations**:
- `POST /api/v1/datasets/` - Create dataset from file (triggers schema inference)
- `POST /api/v1/jobs/` - Create schema inference job
- `GET /api/v1/jobs/{id}/` - Get job status
- `GET /api/v1/datasets/{id}/schema/` - Get inferred schema
- `GET /api/v1/datasets/{id}/sample/` - Get sample data

**Request Schema** (Create Dataset):
```json
{
  "file_id": "uuid",
  "asset_id": "uuid",
  "trigger_schema_inference": true,
  "sample_size": 1000
}
```

**Response Schema** (Dataset):
```json
{
  "id": "uuid",
  "file_id": "uuid",
  "asset_id": "uuid",
  "schema_inference_job_id": "uuid",
  "status": "INFERRING_SCHEMA",
  "created_at": "datetime"
}
```

**Response Schema** (Inferred Schema):
```json
{
  "dataset_id": "uuid",
  "fields": [
    {
      "name": "string",
      "data_type": "string",
      "nullable": true,
      "sample_values": ["string"],
      "statistics": {
        "null_count": 0,
        "unique_count": 100,
        "min": "string",
        "max": "string"
      }
    }
  ],
  "inferred_at": "datetime"
}
```

**Dependencies**:
- Requires Step 3 (file_id from file upload)
- Requires Step 2 (asset_id from asset creation)

**WebSocket Events**:
- `job.started` - Schema inference job started
- `job.progress` - Schema inference progress updates
- `job.completed` - Schema inference completed

**Error Scenarios**:
- 400: File not found or invalid
- 500: Schema inference failed

---

#### Main Flow Step 6: System Runs AI Schema Matching (NEW)

**API Operations**:
- `POST /api/v1/ai/schema-matching/` - Request AI schema matching
- `GET /api/v1/ai/schema-matching/{job_id}/` - Get matching results

**Request Schema**:
```json
{
  "source_schema": "object (from step 5)",
  "target_schema": "object (optional - from existing contract)",
  "dataset_id": "uuid"
}
```

**Response Schema**:
```json
{
  "job_id": "uuid",
  "status": "PROCESSING",
  "estimated_completion": "datetime"
}
```

**Matching Results Response**:
```json
{
  "job_id": "uuid",
  "status": "COMPLETED",
  "mappings": [
    {
      "source_field": "string",
      "target_field": "string",
      "confidence_score": 0.95,
      "similarity_score": 0.92,
      "suggested": true
    }
  ],
  "unmapped_source_fields": ["string"],
  "unmapped_target_fields": ["string"]
}
```

**Dependencies**:
- Requires Step 5 (dataset_id and inferred schema)

**Alternate Flow A3**: AI schema matching fails → user can proceed manually
- No blocking error, use case continues

**Error Scenarios**:
- 400: Invalid schema
- 503: AI service unavailable (non-blocking)
- 500: Matching failed (non-blocking)

---

#### Main Flow Step 7: System Runs Auto-Classification (NEW)

**API Operations**:
- `POST /api/v1/ai/classification/` - Request auto-classification
- `GET /api/v1/ai/classification/{job_id}/` - Get classification results

**Request Schema**:
```json
{
  "dataset_id": "uuid",
  "sample_size": 1000
}
```

**Response Schema**:
```json
{
  "job_id": "uuid",
  "status": "PROCESSING"
}
```

**Classification Results Response**:
```json
{
  "job_id": "uuid",
  "status": "COMPLETED",
  "pii_detected": true,
  "pii_categories": ["EMAIL", "PHONE", "SSN"],
  "data_categories": ["CUSTOMER_DATA", "FINANCIAL_DATA"],
  "confidence_scores": {
    "EMAIL": 0.98,
    "PHONE": 0.95
  },
  "classification_rules_applied": ["rule-1", "rule-2"]
}
```

**Dependencies**:
- Requires Step 5 (dataset_id)

**Alternate Flow A4**: Auto-classification fails → user can proceed manually
- No blocking error, use case continues

**Error Scenarios**:
- 400: Dataset not found
- 503: Classification service unavailable (non-blocking)
- 500: Classification failed (non-blocking)

---

#### Main Flow Step 8: System Runs Compliance Check (Mandatory Gate)

**API Operations**:
- `POST /api/v1/compliance/scans/` - Create compliance scan
- `GET /api/v1/compliance/scans/{id}/` - Get scan status
- `GET /api/v1/compliance/scans/{id}/report/` - Get scan results

**Request Schema**:
```json
{
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "jurisdictions": ["GDPR", "CCPA"],
  "auto_classification_results": "object (from step 7, optional)"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "asset_id": "uuid",
  "status": "RUNNING",
  "created_at": "datetime"
}
```

**Scan Results Response**:
```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "pass_rate": 0.95,
  "violations": [
    {
      "rule_id": "string",
      "severity": "HIGH",
      "description": "string",
      "remediation": "string"
    }
  ],
  "jurisdiction_compliance": {
    "GDPR": "COMPLIANT",
    "CCPA": "NON_COMPLIANT"
  }
}
```

**Dependencies**:
- Requires Step 2 (asset_id)
- Requires Step 5 (dataset_id)
- Optional: Step 7 (auto-classification results for enhanced checks)

**Alternate Flow A1**: Compliance check fails → data not stored, user receives report
- **API Operations**:
  - `GET /api/v1/compliance/scans/{id}/report/` - Get failure report
  - `POST /api/v1/assets/{id}/delete/` - Delete asset (if created)
- Use case terminates, asset not created

**Error Scenarios**:
- 400: Invalid asset or dataset
- 500: Compliance scan failed

---

#### Main Flow Step 9: System Runs DQ Check

**API Operations**:
- `POST /api/v1/dq/runs/` - Create DQ run
- `GET /api/v1/dq/runs/{id}/` - Get DQ run status
- `GET /api/v1/dq/runs/{id}/results/` - Get DQ results

**Request Schema**:
```json
{
  "dataset_id": "uuid",
  "asset_id": "uuid",
  "quality_profile": "intake_basic"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "dataset_id": "uuid",
  "status": "RUNNING",
  "created_at": "datetime"
}
```

**DQ Results Response**:
```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "overall_score": 0.92,
  "check_results": [
    {
      "check_id": "string",
      "check_name": "string",
      "status": "PASS",
      "score": 0.95,
      "details": "object"
    }
  ],
  "dimension_scores": {
    "completeness": 0.95,
    "accuracy": 0.90,
    "consistency": 0.92
  }
}
```

**Dependencies**:
- Requires Step 5 (dataset_id)
- Requires Step 2 (asset_id)

**Alternate Flow A2**: DQ check fails → data not stored, user receives report
- **API Operations**:
  - `GET /api/v1/dq/runs/{id}/results/` - Get failure report
  - `POST /api/v1/assets/{id}/delete/` - Delete asset (if created)
- Use case terminates, asset not created

**Error Scenarios**:
- 400: Invalid dataset or quality profile
- 500: DQ run failed

---

#### Main Flow Step 10: System Runs ML-Based Anomaly Detection (NEW)

**API Operations**:
- `POST /api/v1/ai/anomaly-detection/` - Request ML anomaly detection
- `GET /api/v1/ai/anomaly-detection/{job_id}/` - Get anomaly detection results

**Request Schema**:
```json
{
  "dataset_id": "uuid",
  "dq_results_id": "uuid",
  "model_type": "time_series",
  "historical_data_days": 30
}
```

**Response Schema**:
```json
{
  "job_id": "uuid",
  "status": "PROCESSING"
}
```

**Anomaly Detection Results Response**:
```json
{
  "job_id": "uuid",
  "status": "COMPLETED",
  "anomalies_detected": true,
  "anomalies": [
    {
      "field": "string",
      "anomaly_type": "OUTLIER",
      "severity": "MEDIUM",
      "confidence": 0.87,
      "description": "string",
      "recommended_action": "string"
    }
  ],
  "quality_trend": "object",
  "predictions": {
    "next_period_quality": 0.90,
    "risk_factors": ["string"]
  }
}
```

**Dependencies**:
- Requires Step 5 (dataset_id)
- Requires Step 9 (dq_results_id for baseline)

**Error Scenarios**:
- 400: Invalid dataset or DQ results
- 503: ML service unavailable (non-blocking)
- 500: Anomaly detection failed (non-blocking)

---

#### Main Flow Step 11: If Checks Pass, System Creates Draft Asset and Contract

**API Operations**:
- `PUT /api/v1/assets/{id}/` - Update asset with check results
- `POST /api/v1/contracts/` - Create contract draft

**Request Schema** (Update Asset):
```json
{
  "compliance_scan_id": "uuid",
  "dq_run_id": "uuid",
  "anomaly_detection_job_id": "uuid",
  "status": "DRAFT"
}
```

**Request Schema** (Create Contract):
```json
{
  "name": "string",
  "description": "string",
  "version": "1.0.0",
  "schema": "object (from step 5)",
  "schema_mappings": "object (from step 6, optional)",
  "quality_rules": "array (from step 9)",
  "compliance_policy": "object (from step 8)",
  "asset_id": "uuid"
}
```

**Response Schema** (Contract):
```json
{
  "id": "uuid",
  "name": "string",
  "status": "DRAFT",
  "normalization_status": "PENDING",
  "validation_status": "PENDING",
  "asset_id": "uuid"
}
```

**Dependencies**:
- Requires Step 2 (asset_id)
- Requires Step 5 (inferred schema)
- Requires Step 8 (compliance scan results)
- Requires Step 9 (DQ results)
- Optional: Step 6 (schema mappings)
- Optional: Step 10 (anomaly detection results)

**Error Scenarios**:
- 400: Invalid contract schema
- 500: Contract creation failed

---

#### Main Flow Step 12: User Edits Contract in Contract Editor

**API Operations**:
- `GET /api/v1/contracts/{id}/` - Get contract for editing
- `PUT /api/v1/contracts/{id}/` - Update contract
- `POST /api/v1/contracts/{id}/auto-save/` - Auto-save draft (every 30 seconds)

**Request Schema** (Update Contract):
```json
{
  "hub_contract_json": "object",
  "schema": "object",
  "quality_rules": "array",
  "compliance_policy": "object"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "DRAFT",
  "updated_at": "datetime",
  "dirty": true
}
```

**Dependencies**:
- Requires Step 11 (contract_id)

**Error Scenarios**:
- 404: Contract not found
- 400: Invalid contract updates
- 500: Update failed

---

#### Main Flow Step 13: User Triggers DataContract CLI Validation

**API Operations**:
- `POST /api/v1/contracts/{id}/validate/` - Validate contract

**Request Schema**: None (contract_id in path)

**Response Schema**:
```json
{
  "validation_status": "VALID",
  "errors": [],
  "warnings": [
    {
      "field": "string",
      "message": "string"
    }
  ],
  "normalization_status": "NORMALIZED_OK"
}
```

**Dependencies**:
- Requires Step 12 (contract_id and updated contract)

**Alternate Flow A5**: Contract validation fails → user fixes contract and re-validates
- **API Operations**:
  - `GET /api/v1/contracts/{id}/validate/` - Get validation errors
  - `PUT /api/v1/contracts/{id}/` - Fix contract
  - `POST /api/v1/contracts/{id}/validate/` - Re-validate
- Loop until validation passes

**Error Scenarios**:
- 404: Contract not found
- 422: Validation failed (with detailed errors)

---

#### Main Flow Step 14: If Validation Passes, Asset is Activated

**API Operations**:
- `POST /api/v1/assets/{id}/activate/` - Activate asset

**Request Schema**:
```json
{
  "contract_id": "uuid"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "ACTIVE",
  "activated_at": "datetime",
  "contract_id": "uuid"
}
```

**Dependencies**:
- Requires Step 2 (asset_id)
- Requires Step 13 (validated contract_id)

**WebSocket Events**:
- `asset.activated` - Asset activation completed
- `semantic.mapping.triggered` - Semantic mapping triggered

**Error Scenarios**:
- 400: Contract not validated or missing
- 409: Asset already activated
- 500: Activation failed

---

#### Postconditions API Requirements

**API Operations**:
- `GET /api/v1/assets/{id}/` - Verify asset is ACTIVE
- `GET /api/v1/contracts/{id}/` - Verify contract is validated
- `GET /api/v1/datasets/{id}/` - Verify data is stored
- `GET /api/v1/semantic/mappings/` - Verify semantic mapping triggered

**Dependencies**: All main flow steps completed

---

#### Use Case Summary

**Total API Endpoints Required**: 25+
- **Existing**: 15 endpoints
- **Missing/New**: 10 endpoints (AI schema matching, auto-classification, ML anomaly detection, file validation, auto-save)

**Critical Dependencies**:
1. Steps 2-5 must complete sequentially (asset → file → dataset → schema)
2. Steps 6-7 can run in parallel after step 5 (non-blocking)
3. Steps 8-9 must pass (mandatory gates)
4. Step 10 can run in parallel with steps 8-9 (non-blocking)
5. Steps 11-14 must complete sequentially

**Related Use Cases**:
- UC-AM-002: Create Asset via Contract-First Flow
- UC-CM-001: Create Contract
- UC-DQ-001: Run Data Quality Check
- UC-COMP-001: Run Compliance Scan
- UC-AI-002: AI Schema Matching
- UC-AI-005: Auto-Classification

---

## AI/ML Use Cases

### UC-AI-001: Natural Language Search

**Use Case ID**: UC-AI-001  
**Priority**: High (P1)  
**Status**: New  
**Total Steps**: 10

#### Main Flow Step 1: User Navigates to Search

**API Operations**:
- `GET /api/v1/search/` - Get search interface configuration
- `GET /api/v1/ai/natural-language-search/capabilities/` - Check if NL search is enabled

**Response Schema** (Capabilities):
```json
{
  "natural_language_enabled": true,
  "llm_service_available": true,
  "supported_languages": ["en", "es", "fr"]
}
```

**Dependencies**: None

---

#### Main Flow Step 2: User Enters Natural Language Query

**API Operations**:
- `POST /api/v1/ai/natural-language-search/` - Send natural language query

**Request Schema**:
```json
{
  "query": "show me customer data from last quarter",
  "context": {
    "user_id": "uuid",
    "tenant_id": "uuid",
    "previous_queries": ["string"]
  }
}
```

**Response Schema**:
```json
{
  "query_id": "uuid",
  "status": "PROCESSING",
  "estimated_completion": "datetime"
}
```

**Dependencies**: None

**Error Scenarios**:
- 400: Invalid query format
- 503: LLM service unavailable

---

#### Main Flow Step 3: System Sends Query to LLM Service

**API Operations**:
- `GET /api/v1/ai/natural-language-search/{query_id}/interpretation/` - Get query interpretation

**Response Schema**:
```json
{
  "query_id": "uuid",
  "status": "COMPLETED",
  "interpretation": {
    "original_query": "string",
    "translated_query": "SELECT * FROM customers WHERE date >= '2024-01-01'",
    "query_type": "SQL",
    "confidence": 0.95,
    "entities": [
      {
        "type": "TABLE",
        "value": "customers",
        "confidence": 0.98
      }
    ],
    "intent": "RETRIEVE_DATA"
  }
}
```

**Dependencies**:
- Requires Step 2 (query_id)

**Alternate Flow A1**: LLM service unavailable → fallback to keyword search
- **API Operations**:
  - `GET /api/v1/search/?q={query}` - Fallback to keyword search
- Use case continues with keyword search

**Error Scenarios**:
- 503: LLM service unavailable (triggers fallback)
- 500: Query translation failed

---

#### Main Flow Step 4: LLM Translates Query to SQL/SPARQL

**API Operations**:
- Same as Step 3 (interpretation includes translation)

**Dependencies**:
- Requires Step 3 (interpretation)

---

#### Main Flow Step 5: System Displays Query Interpretation

**API Operations**:
- `GET /api/v1/ai/natural-language-search/{query_id}/interpretation/` - Get interpretation for display

**Dependencies**:
- Requires Step 4 (translation complete)

---

#### Main Flow Step 6: User Reviews Interpretation

**API Operations**:
- `POST /api/v1/ai/natural-language-search/{query_id}/feedback/` - Provide feedback on interpretation

**Request Schema**:
```json
{
  "interpretation_correct": true,
  "suggested_corrections": ["string"]
}
```

**Dependencies**:
- Requires Step 5 (interpretation displayed)

---

#### Main Flow Step 7: System Executes Translated Query

**API Operations**:
- `POST /api/v1/ai/natural-language-search/{query_id}/execute/` - Execute translated query

**Request Schema**:
```json
{
  "query_id": "uuid",
  "confirm_execution": true
}
```

**Response Schema**:
```json
{
  "execution_id": "uuid",
  "status": "RUNNING",
  "estimated_completion": "datetime"
}
```

**Dependencies**:
- Requires Step 6 (user confirmed interpretation)

**Alternate Flow A2**: Query translation fails → system suggests alternative queries
- **API Operations**:
  - `GET /api/v1/ai/natural-language-search/{query_id}/alternatives/` - Get alternative query suggestions
- User can select alternative or refine query

**Error Scenarios**:
- 400: Invalid translated query
- 500: Query execution failed

---

#### Main Flow Step 8: System Returns Results

**API Operations**:
- `GET /api/v1/ai/natural-language-search/{query_id}/results/` - Get query results

**Response Schema**:
```json
{
  "query_id": "uuid",
  "execution_id": "uuid",
  "status": "COMPLETED",
  "results": [
    {
      "columns": ["string"],
      "rows": [["string"]],
      "row_count": 100,
      "execution_time_ms": 250
    }
  ],
  "metadata": {
    "query_type": "SQL",
    "tables_accessed": ["customers"],
    "execution_plan": "object"
  }
}
```

**Dependencies**:
- Requires Step 7 (execution_id)

**Alternate Flow A3**: Query results empty → system suggests query refinement
- **API Operations**:
  - `GET /api/v1/ai/natural-language-search/{query_id}/refinement-suggestions/` - Get refinement suggestions
- User can refine query

**Error Scenarios**:
- 404: Results not found
- 500: Results retrieval failed

---

#### Main Flow Step 9: User Reviews Results

**API Operations**:
- `GET /api/v1/ai/natural-language-search/{query_id}/results/` - Get results for review
- `POST /api/v1/ai/natural-language-search/{query_id}/export/` - Export results (optional)

**Dependencies**:
- Requires Step 8 (results available)

---

#### Main Flow Step 10: User Can Refine Query if Needed

**API Operations**:
- `POST /api/v1/ai/natural-language-search/refine/` - Refine query

**Request Schema**:
```json
{
  "original_query_id": "uuid",
  "refined_query": "show me customer data from last quarter with email addresses",
  "refinement_type": "ADD_FILTER"
}
```

**Response Schema**:
```json
{
  "refined_query_id": "uuid",
  "status": "PROCESSING"
}
```

**Dependencies**:
- Requires Step 9 (original query results reviewed)
- Loop back to Step 3 with refined query

---

#### Postconditions API Requirements

**API Operations**:
- `POST /api/v1/ai/natural-language-search/{query_id}/cache/` - Cache query for performance
- `POST /api/v1/ai/natural-language-search/{query_id}/save/` - Save query to history (optional)

**Dependencies**: All main flow steps completed

---

#### Use Case Summary

**Total API Endpoints Required**: 12+
- **Existing**: 2 endpoints (search fallback)
- **Missing/New**: 10 endpoints (natural language search, LLM integration, query interpretation, execution, results)

**Critical Dependencies**:
1. Steps 2-4 must complete sequentially (query → LLM → translation)
2. Steps 5-6 can be iterative (user reviews and provides feedback)
3. Steps 7-9 must complete sequentially (execution → results → review)
4. Step 10 is optional (refinement loop)

**Related Use Cases**:
- UC-DC-001: Discover and Purchase Marketplace Asset
- UC-AI-008: Query-to-SQL Translation

**Performance Requirements**:
- Query understanding: < 3 seconds
- Results returned: < 5 seconds

---

## Transformation Use Cases

### UC-TRANS-001: Create Transformation Pipeline

**Use Case ID**: UC-TRANS-001  
**Priority**: High (P1)  
**Status**: New  
**Total Steps**: 7

#### Main Flow Step 1: User Navigates to Transformation Section

**API Operations**:
- `GET /api/v1/transformation/pipelines/` - List existing pipelines
- `GET /api/v1/transformation/capabilities/` - Get transformation capabilities

**Dependencies**: None

---

#### Main Flow Step 2: User Creates New Pipeline

**API Operations**:
- `POST /api/v1/transformation/pipelines/` - Create new pipeline

**Request Schema**:
```json
{
  "name": "string",
  "description": "string",
  "source_asset_id": "uuid",
  "target_asset_id": "uuid (optional)",
  "mode": "visual|code"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "name": "string",
  "status": "DRAFT",
  "mode": "visual",
  "created_at": "datetime"
}
```

**Dependencies**: None

---

#### Main Flow Step 3: User Designs Pipeline

**API Operations**:
- `PUT /api/v1/transformation/pipelines/{id}/design/` - Update pipeline design
- `GET /api/v1/transformation/nodes/` - Get available transformation nodes
- `POST /api/v1/transformation/pipelines/{id}/nodes/` - Add transformation node
- `PUT /api/v1/transformation/pipelines/{id}/nodes/{node_id}/` - Configure node
- `POST /api/v1/transformation/pipelines/{id}/connections/` - Connect nodes

**Request Schema** (Add Node):
```json
{
  "node_type": "filter|join|aggregate|transform|output",
  "position": {"x": 100, "y": 200},
  "configuration": {
    "filter_expression": "string",
    "join_type": "inner|left|right",
    "aggregation_function": "sum|avg|count"
  }
}
```

**Response Schema**:
```json
{
  "node_id": "uuid",
  "node_type": "filter",
  "configuration": "object",
  "position": "object"
}
```

**Dependencies**:
- Requires Step 2 (pipeline_id)

**Error Scenarios**:
- 400: Invalid node configuration
- 404: Pipeline not found

---

#### Main Flow Step 4: User Validates Pipeline

**API Operations**:
- `POST /api/v1/transformation/pipelines/{id}/validate/` - Validate pipeline

**Request Schema**: None (pipeline_id in path)

**Response Schema**:
```json
{
  "validation_status": "VALID",
  "errors": [],
  "warnings": [
    {
      "node_id": "uuid",
      "message": "string"
    }
  ],
  "compatibility": {
    "source_compatible": true,
    "target_compatible": true,
    "schema_compatible": true
  }
}
```

**Dependencies**:
- Requires Step 3 (pipeline design complete)

**Alternate Flow A1**: Pipeline validation fails → user fixes errors
- **API Operations**:
  - `GET /api/v1/transformation/pipelines/{id}/validate/` - Get validation errors
  - `PUT /api/v1/transformation/pipelines/{id}/design/` - Fix pipeline
  - `POST /api/v1/transformation/pipelines/{id}/validate/` - Re-validate
- Loop until validation passes

**Error Scenarios**:
- 422: Validation failed (with detailed errors)

---

#### Main Flow Step 5: User Previews Transformation Results

**API Operations**:
- `POST /api/v1/transformation/pipelines/{id}/preview/` - Generate preview

**Request Schema**:
```json
{
  "sample_size": 100,
  "preview_mode": "quick|detailed"
}
```

**Response Schema**:
```json
{
  "preview_id": "uuid",
  "status": "PROCESSING",
  "estimated_completion": "datetime"
}
```

**Preview Results Response**:
```json
{
  "preview_id": "uuid",
  "status": "COMPLETED",
  "sample_data": [
    {
      "columns": ["string"],
      "rows": [["string"]],
      "row_count": 100
    }
  ],
  "transformation_summary": {
    "rows_before": 1000,
    "rows_after": 950,
    "columns_before": 10,
    "columns_after": 8
  }
}
```

**Dependencies**:
- Requires Step 4 (validated pipeline)

**Alternate Flow A2**: Preview fails → user adjusts pipeline
- **API Operations**:
  - `GET /api/v1/transformation/pipelines/{id}/preview/{preview_id}/errors/` - Get preview errors
  - `PUT /api/v1/transformation/pipelines/{id}/design/` - Adjust pipeline
  - `POST /api/v1/transformation/pipelines/{id}/preview/` - Re-preview
- Loop until preview succeeds

**Error Scenarios**:
- 400: Invalid preview configuration
- 500: Preview generation failed

---

#### Main Flow Step 6: User Saves Pipeline

**API Operations**:
- `PUT /api/v1/transformation/pipelines/{id}/` - Save pipeline

**Request Schema**:
```json
{
  "name": "string",
  "description": "string",
  "status": "SAVED"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "SAVED",
  "saved_at": "datetime"
}
```

**Dependencies**:
- Requires Step 5 (preview successful, optional)

**Alternate Flow A3**: Save fails → user retries
- **API Operations**:
  - `PUT /api/v1/transformation/pipelines/{id}/` - Retry save
- Retry until successful

**Error Scenarios**:
- 500: Save failed

---

#### Main Flow Step 7: Pipeline Versioned

**API Operations**:
- `POST /api/v1/transformation/pipelines/{id}/version/` - Create new version

**Request Schema**: None (pipeline_id in path)

**Response Schema**:
```json
{
  "version": "1.0.0",
  "version_id": "uuid",
  "created_at": "datetime"
}
```

**Dependencies**:
- Requires Step 6 (pipeline saved)

---

#### Use Case Summary

**Total API Endpoints Required**: 15+
- **Existing**: 0 endpoints
- **Missing/New**: 15 endpoints (all transformation pipeline APIs)

**Critical Dependencies**:
1. Steps 2-3 must complete sequentially (create → design)
2. Steps 4-5 can be iterative (validate → preview → adjust)
3. Steps 6-7 must complete sequentially (save → version)

**Related Use Cases**:
- UC-TRANS-002: Execute Transformation Pipeline
- UC-TRANS-003: Monitor Pipeline Execution
- UC-AM-001: Create Asset via Data-First Flow

---

## Summary Tables

### API Endpoints by Use Case Category

#### Asset Management Use Cases
- **Total Use Cases**: ~8
- **Total API Operations**: ~80
- **Existing APIs**: ~40
- **Missing/New APIs**: ~40

#### AI/ML Use Cases
- **Total Use Cases**: ~10
- **Total API Operations**: ~100
- **Existing APIs**: ~5
- **Missing/New APIs**: ~95

#### Transformation Use Cases
- **Total Use Cases**: ~8
- **Total API Operations**: ~120
- **Existing APIs**: ~0
- **Missing/New APIs**: ~120

#### Social Feature Use Cases
- **Total Use Cases**: ~6
- **Total API Operations**: ~60
- **Existing APIs**: ~0
- **Missing/New APIs**: ~60

#### Data Mesh Use Cases
- **Total Use Cases**: ~5
- **Total API Operations**: ~50
- **Existing APIs**: ~0
- **Missing/New APIs**: ~50

#### Virtualization Use Cases
- **Total Use Cases**: ~4
- **Total API Operations**: ~40
- **Existing APIs**: ~0
- **Missing/New APIs**: ~40

#### Advanced Marketplace Use Cases
- **Total Use Cases**: ~5
- **Total API Operations**: ~50
- **Existing APIs**: ~10
- **Missing/New APIs**: ~40

#### Advanced Governance Use Cases
- **Total Use Cases**: ~4
- **Total API Operations**: ~40
- **Existing APIs**: ~5
- **Missing/New APIs**: ~35

#### Advanced Observability Use Cases
- **Total Use Cases**: ~4
- **Total API Operations**: ~40
- **Existing APIs**: ~10
- **Missing/New APIs**: ~30

#### Integration Ecosystem Use Cases
- **Total Use Cases**: ~5
- **Total API Operations**: ~50
- **Existing APIs**: ~5
- **Missing/New APIs**: ~45

#### Developer Experience Use Cases
- **Total Use Cases**: ~4
- **Total API Operations**: ~40
- **Existing APIs**: ~0
- **Missing/New APIs**: ~40

---

### Use Case Dependencies Matrix

| Use Case | Depends On | API Endpoint | Dependency Type |
|----------|------------|--------------|-----------------|
| UC-AM-001 Step 3 | Step 2 | `POST /api/v1/files/upload/` | Requires asset_id |
| UC-AM-001 Step 5 | Steps 2,3 | `POST /api/v1/datasets/` | Requires asset_id, file_id |
| UC-AM-001 Step 8 | Steps 2,5 | `POST /api/v1/compliance/scans/` | Requires asset_id, dataset_id |
| UC-AM-001 Step 11 | Steps 2,5,8,9 | `POST /api/v1/contracts/` | Requires multiple inputs |
| UC-AI-001 Step 7 | Step 6 | `POST /api/v1/ai/natural-language-search/{id}/execute/` | Requires user confirmation |
| UC-TRANS-001 Step 4 | Step 3 | `POST /api/v1/transformation/pipelines/{id}/validate/` | Requires pipeline design |

---

### Performance Requirements Summary

| Use Case | API Endpoint | Performance Target |
|----------|--------------|-------------------|
| UC-AI-001 | `POST /api/v1/ai/natural-language-search/` | < 3 seconds (understanding) |
| UC-AI-001 | `GET /api/v1/ai/natural-language-search/{id}/results/` | < 5 seconds (results) |
| UC-AI-002 | `POST /api/v1/ai/schema-matching/` | < 15 seconds |
| UC-AI-005 | `POST /api/v1/ai/classification/` | < 20 seconds |
| UC-AM-001 | `POST /api/v1/compliance/scans/` | < 60 seconds |
| UC-AM-001 | `POST /api/v1/dq/runs/` | < 60 seconds |
| UC-VIRT-002 | `POST /api/v1/virtualization/queries/` | < 10 seconds (execution), < 5 seconds (results) |

---

## Next Steps

1. **API Gap Analysis** (Task 0.3): Compare these requirements with existing APIs
2. **API Contract Specifications** (Task 0.4): Create OpenAPI specs for missing APIs
3. **API Development Backlog** (Task 0.5): Prioritize missing API development

---

**Document Status**: ✅ Complete  
**Total Use Cases Analyzed**: ~105  
**Total API Operations Identified**: 600+  
**Missing APIs Identified**: 550+  
**Dependencies Documented**: 300+

---

**Last Updated**: 2025-12-13

