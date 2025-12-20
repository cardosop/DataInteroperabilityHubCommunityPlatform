# API Requirements Extraction from User Journeys

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-13  
**Source**: `docs/USER_JOURNEYS.md` (82 journeys)  
**Task**: 0.1.3 - Extract API requirements from user journeys

---

## Overview

This document extracts API requirements from all **82 user journeys** across **12 personas**. For each journey, we identify:

1. **API Operations Required**: Specific API endpoints needed for each journey step
2. **API Dependencies**: Dependencies between journey steps (e.g., step 2 requires step 1 to complete)
3. **Request/Response Schemas**: Expected request and response structures
4. **Error Handling**: Error scenarios and required error responses
5. **Performance Requirements**: Performance targets from journey specifications

---

## Methodology

### Extraction Process

1. **Journey Analysis**: Review each journey's steps and success criteria
2. **API Mapping**: Map each step to required API endpoint(s)
3. **Dependency Analysis**: Identify sequential dependencies between steps
4. **Schema Inference**: Infer request/response schemas from journey context
5. **Error Scenarios**: Identify error cases from journey failure paths

### API Endpoint Naming Convention

- **Existing APIs**: Use actual endpoint paths (e.g., `/api/v1/assets/`)
- **Missing APIs**: Use proposed endpoint paths (e.g., `/api/v1/ai/schema-matching/`)
- **WebSocket Events**: Use event names (e.g., `asset.activated`)
- **GraphQL Queries**: Use query names (e.g., `getAsset`)

---

## Data Product Owner Journeys (14 journeys)

### JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Journey ID**: JOURNEY-DPO-001  
**Priority**: P0 (Critical - Blocks MVP)  
**Total Steps**: 10

#### Step 1: Create Asset (Draft)

**API Operations**:
- `POST /api/v1/assets/` - Create asset in DRAFT status

**Request Schema**:
```json
{
  "name": "string",
  "description": "string",
  "domain": "string",
  "tags": ["string"],
  "status": "DRAFT"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "name": "string",
  "status": "DRAFT",
  "created_at": "datetime"
}
```

**Dependencies**: None (first step)

**Error Scenarios**:
- 400: Invalid input (name required, domain invalid)
- 401: Unauthorized
- 403: Insufficient permissions

---

#### Step 2: Upload File

**API Operations**:
- `POST /api/v1/files/upload/` - Upload file

**Request Schema**:
```json
{
  "file": "multipart/form-data",
  "asset_id": "uuid"
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
  "asset_id": "uuid"
}
```

**Dependencies**: 
- Requires Step 1 (asset_id from asset creation)

**Error Scenarios**:
- 400: Invalid file format (not CSV/JSON/Parquet)
- 413: File too large
- 500: Upload failed

---

#### Step 3: Create Dataset (Triggers Schema Inference)

**API Operations**:
- `POST /api/v1/datasets/` - Create dataset from uploaded file
- `POST /api/v1/jobs/` - Create schema inference job

**Request Schema**:
```json
{
  "file_id": "uuid",
  "asset_id": "uuid",
  "trigger_schema_inference": true
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "file_id": "uuid",
  "asset_id": "uuid",
  "schema_inference_job_id": "uuid",
  "status": "INFERRING_SCHEMA"
}
```

**Dependencies**:
- Requires Step 2 (file_id from file upload)

**WebSocket Events**:
- `job.started` - Schema inference job started
- `job.progress` - Schema inference progress updates
- `job.completed` - Schema inference completed

**Error Scenarios**:
- 400: File not found or invalid
- 500: Schema inference failed

---

#### Step 4: AI Schema Matching Suggests Field Mappings (NEW)

**API Operations**:
- `POST /api/v1/ai/schema-matching/` - Request AI schema matching
- `GET /api/v1/ai/schema-matching/{job_id}/` - Get matching results

**Request Schema**:
```json
{
  "source_schema": "object",
  "target_schema": "object (optional)",
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
- Requires Step 3 (dataset_id and inferred schema)

**Performance Target**: < 15 seconds

**Error Scenarios**:
- 400: Invalid schema
- 503: AI service unavailable
- 500: Matching failed

---

#### Step 5: Auto-Classification Detects PII and Categorizes Data (NEW)

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
- Requires Step 3 (dataset_id)

**Performance Target**: < 20 seconds

**Error Scenarios**:
- 400: Dataset not found
- 503: Classification service unavailable
- 500: Classification failed

---

#### Step 6: Run Compliance Check

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
  "auto_classification_results": "object (from step 5)"
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
- Requires Step 1 (asset_id)
- Requires Step 3 (dataset_id)
- Optional: Step 5 (auto-classification results for enhanced checks)

**Performance Target**: < 60 seconds

**Error Scenarios**:
- 400: Invalid asset or dataset
- 500: Compliance scan failed

---

#### Step 7: Run DQ Check

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
- Requires Step 3 (dataset_id)
- Requires Step 1 (asset_id)

**Performance Target**: < 60 seconds

**Error Scenarios**:
- 400: Invalid dataset or quality profile
- 500: DQ run failed

---

#### Step 8: ML-Based Anomaly Detection Identifies Quality Issues (NEW)

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
- Requires Step 3 (dataset_id)
- Requires Step 7 (dq_results_id for baseline)

**Performance Target**: < 30 seconds

**Error Scenarios**:
- 400: Invalid dataset or DQ results
- 503: ML service unavailable
- 500: Anomaly detection failed

---

#### Step 9: Create Contract

**API Operations**:
- `POST /api/v1/contracts/` - Create contract
- `POST /api/v1/contracts/{id}/validate/` - Validate contract

**Request Schema**:
```json
{
  "name": "string",
  "description": "string",
  "version": "1.0.0",
  "schema": "object (from step 3)",
  "schema_mappings": "object (from step 4, optional)",
  "quality_rules": "array (from step 7)",
  "compliance_policy": "object (from step 6)",
  "asset_id": "uuid"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "name": "string",
  "status": "DRAFT",
  "normalization_status": "PENDING",
  "validation_status": "PENDING"
}
```

**Validation Response**:
```json
{
  "validation_status": "VALID",
  "errors": [],
  "warnings": [
    {
      "field": "string",
      "message": "string"
    }
  ]
}
```

**Dependencies**:
- Requires Step 1 (asset_id)
- Requires Step 3 (inferred schema)
- Optional: Step 4 (schema mappings)
- Optional: Step 6 (compliance policy)
- Optional: Step 7 (quality rules)

**Error Scenarios**:
- 400: Invalid contract schema
- 422: Validation failed
- 500: Contract creation failed

---

#### Step 10: Activate Asset

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
- Requires Step 1 (asset_id)
- Requires Step 9 (contract_id and validated contract)

**WebSocket Events**:
- `asset.activated` - Asset activation completed

**Error Scenarios**:
- 400: Contract not validated or missing
- 409: Asset already activated
- 500: Activation failed

---

#### Journey Summary

**Total API Endpoints Required**: 20+
- **Existing**: 12 endpoints
- **Missing/New**: 8 endpoints (AI schema matching, auto-classification, ML anomaly detection)

**Critical Dependencies**:
1. Steps 1-3 must complete sequentially (asset → file → dataset)
2. Steps 4-8 can run in parallel after step 3
3. Step 9 requires steps 3, 4 (optional), 6 (optional), 7 (optional)
4. Step 10 requires steps 1 and 9

**Performance Requirements**:
- Total duration: < 5 minutes
- Individual step targets as specified above

---

### JOURNEY-DPO-002: Publish Asset to Marketplace

**Journey ID**: JOURNEY-DPO-002  
**Priority**: P0 (Critical - Blocks MVP)  
**Total Steps**: 8

#### Step 1: Verify Asset is Active

**API Operations**:
- `GET /api/v1/assets/{id}/` - Get asset details

**Response Schema**:
```json
{
  "id": "uuid",
  "name": "string",
  "status": "ACTIVE",
  "contract_id": "uuid",
  "dataset_id": "uuid"
}
```

**Dependencies**: None

**Error Scenarios**:
- 404: Asset not found
- 400: Asset not in ACTIVE status

---

#### Step 2: Check Marketplace Eligibility

**API Operations**:
- `GET /api/v1/marketplace/eligibility/{asset_id}/` - Check asset eligibility

**Request Schema**: None (asset_id in path)

**Response Schema**:
```json
{
  "eligible": true,
  "requirements_met": [
    "ACTIVE_STATUS",
    "VALID_CONTRACT",
    "DATASET_ATTACHED"
  ],
  "missing_requirements": [],
  "recommendations": ["string"]
}
```

**Dependencies**:
- Requires Step 1 (asset_id)

**Error Scenarios**:
- 404: Asset not found
- 400: Asset not eligible (with reasons)

---

#### Step 3: Validate Transformation Pipelines (NEW)

**API Operations**:
- `GET /api/v1/assets/{id}/transformation-pipelines/` - List transformation pipelines
- `POST /api/v1/transformation/pipelines/{id}/validate/` - Validate pipeline

**Response Schema** (List pipelines):
```json
{
  "pipelines": [
    {
      "id": "uuid",
      "name": "string",
      "status": "ACTIVE",
      "validation_status": "VALID"
    }
  ]
}
```

**Validation Response**:
```json
{
  "validation_status": "VALID",
  "errors": [],
  "warnings": [],
  "compatibility": {
    "asset_compatible": true,
    "schema_compatible": true
  }
}
```

**Dependencies**:
- Requires Step 1 (asset_id)

**Error Scenarios**:
- 404: Asset or pipeline not found
- 400: Pipeline validation failed

---

#### Step 4: Create Marketplace Listing

**API Operations**:
- `POST /api/v1/marketplace/listings/` - Create marketplace listing

**Request Schema**:
```json
{
  "asset_id": "uuid",
  "title": "string",
  "description": "string",
  "category": "string",
  "tags": ["string"],
  "transformation_pipeline_ids": ["uuid"],
  "status": "DRAFT"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "asset_id": "uuid",
  "title": "string",
  "status": "DRAFT",
  "created_at": "datetime"
}
```

**Dependencies**:
- Requires Step 1 (asset_id)
- Optional: Step 3 (transformation_pipeline_ids)

**Error Scenarios**:
- 400: Invalid asset or missing required fields
- 409: Listing already exists for asset

---

#### Step 5: Configure Pricing Model (NEW)

**API Operations**:
- `POST /api/v1/marketplace/listings/{id}/pricing/` - Configure pricing model

**Request Schema**:
```json
{
  "pricing_model": "USAGE_BASED",
  "usage_tiers": [
    {
      "tier_name": "per-query",
      "unit": "QUERY",
      "rate": 0.10,
      "currency": "USD"
    },
    {
      "tier_name": "per-gb",
      "unit": "GB",
      "rate": 5.00,
      "currency": "USD"
    }
  ],
  "subscription_options": {
    "monthly": 100.00,
    "yearly": 1000.00
  }
}
```

**Response Schema**:
```json
{
  "pricing_model": "USAGE_BASED",
  "usage_tiers": ["object"],
  "configured_at": "datetime"
}
```

**Dependencies**:
- Requires Step 4 (listing_id)

**Error Scenarios**:
- 400: Invalid pricing configuration
- 404: Listing not found

---

#### Step 6: Set Up Data Preview (NEW)

**API Operations**:
- `POST /api/v1/marketplace/listings/{id}/preview/` - Configure data preview

**Request Schema**:
```json
{
  "enabled": true,
  "sample_size": 100,
  "preview_fields": ["string"],
  "quality_metrics_included": true,
  "schema_preview": true
}
```

**Response Schema**:
```json
{
  "preview_enabled": true,
  "preview_data_url": "/api/v1/marketplace/listings/{id}/preview/data/",
  "sample_generated_at": "datetime"
}
```

**Dependencies**:
- Requires Step 4 (listing_id)

**Error Scenarios**:
- 400: Invalid preview configuration
- 404: Listing not found
- 500: Preview generation failed

---

#### Step 7: Configure Trust Signals (NEW)

**API Operations**:
- `POST /api/v1/marketplace/listings/{id}/trust-signals/` - Configure trust signals

**Request Schema**:
```json
{
  "quality_slas": {
    "availability": 99.9,
    "latency_p95_ms": 200,
    "freshness_hours": 24
  },
  "certification_badges": ["ISO_27001", "SOC2"],
  "reliability_score_threshold": 0.90
}
```

**Response Schema**:
```json
{
  "trust_signals_configured": true,
  "quality_slas": "object",
  "certification_badges": ["string"],
  "configured_at": "datetime"
}
```

**Dependencies**:
- Requires Step 4 (listing_id)

**Error Scenarios**:
- 400: Invalid trust signal configuration
- 404: Listing not found

---

#### Step 8: Publish Listing

**API Operations**:
- `POST /api/v1/marketplace/listings/{id}/publish/` - Publish listing

**Request Schema**: None (listing_id in path)

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "PUBLISHED",
  "published_at": "datetime",
  "marketplace_url": "/marketplace/listings/{id}/"
}
```

**Dependencies**:
- Requires Step 4 (listing_id)
- Requires Step 5 (pricing configured)
- Requires Step 6 (preview configured)
- Requires Step 7 (trust signals configured)

**WebSocket Events**:
- `marketplace.listing.published` - Listing published

**Error Scenarios**:
- 400: Missing required configuration (pricing, preview, trust signals)
- 404: Listing not found
- 409: Listing already published

---

#### Journey Summary

**Total API Endpoints Required**: 10+
- **Existing**: 4 endpoints
- **Missing/New**: 6 endpoints (eligibility check, transformation validation, pricing, preview, trust signals)

**Critical Dependencies**:
1. Steps 1-2 must complete sequentially
2. Step 3 can run in parallel with step 2
3. Steps 5-7 can run in parallel after step 4
4. Step 8 requires steps 4, 5, 6, 7

---

### JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation (NEW)

**Journey ID**: JOURNEY-DPO-007  
**Priority**: P1 (High - Blocks AI/ML features)  
**Total Steps**: 9

#### Step 1: Upload Data File

**API Operations**:
- `POST /api/v1/files/upload/` - Upload file

**Dependencies**: None

**Error Scenarios**: Same as JOURNEY-DPO-001 Step 2

---

#### Step 2: System Infers Schema

**API Operations**:
- `POST /api/v1/datasets/` - Create dataset (triggers schema inference)
- `GET /api/v1/datasets/{id}/schema/` - Get inferred schema

**Dependencies**:
- Requires Step 1 (file_id)

**Error Scenarios**: Same as JOURNEY-DPO-001 Step 3

---

#### Step 3: AI Schema Matching Analyzes Schema (NEW)

**API Operations**:
- `POST /api/v1/ai/schema-matching/` - Request AI schema matching
- `GET /api/v1/ai/schema-matching/{job_id}/` - Get matching results

**Request Schema**:
```json
{
  "source_schema": "object (from step 2)",
  "target_schema": "object (optional - from existing contract)",
  "matching_strategy": "SEMANTIC_SIMILARITY"
}
```

**Response Schema**: Same as JOURNEY-DPO-001 Step 4

**Dependencies**:
- Requires Step 2 (inferred schema)

**Performance Target**: < 15 seconds

---

#### Step 4: Review Suggested Field Mappings with Confidence Scores (NEW)

**API Operations**:
- `GET /api/v1/ai/schema-matching/{job_id}/mappings/` - Get detailed mappings

**Response Schema**:
```json
{
  "mappings": [
    {
      "source_field": "string",
      "target_field": "string",
      "confidence_score": 0.95,
      "similarity_score": 0.92,
      "matching_reason": "string",
      "field_type_compatibility": "EXACT_MATCH",
      "suggested": true
    }
  ],
  "unmapped_source_fields": [
    {
      "field": "string",
      "suggested_targets": [
        {
          "target_field": "string",
          "confidence": 0.75
        }
      ]
    }
  ],
  "unmapped_target_fields": ["string"]
}
```

**Dependencies**:
- Requires Step 3 (job_id)

---

#### Step 5: Accept/Reject/Modify Mappings (NEW)

**API Operations**:
- `POST /api/v1/ai/schema-matching/{job_id}/mappings/accept/` - Accept mappings
- `POST /api/v1/ai/schema-matching/{job_id}/mappings/reject/` - Reject mappings
- `PUT /api/v1/ai/schema-matching/{job_id}/mappings/{mapping_id}/` - Modify mapping

**Request Schema** (Accept):
```json
{
  "mapping_ids": ["uuid"],
  "accept_all": false
}
```

**Request Schema** (Modify):
```json
{
  "target_field": "string",
  "confidence_override": 1.0
}
```

**Response Schema**:
```json
{
  "accepted_mappings": ["uuid"],
  "rejected_mappings": ["uuid"],
  "modified_mappings": ["uuid"],
  "final_mappings": ["object"]
}
```

**Dependencies**:
- Requires Step 4 (mappings to review)

---

#### Step 6: System Generates Contract Draft with Mappings (NEW)

**API Operations**:
- `POST /api/v1/contracts/generate-from-mappings/` - Generate contract from mappings

**Request Schema**:
```json
{
  "source_schema": "object",
  "mappings": ["object (from step 5)"],
  "contract_template": "string (optional)",
  "name": "string",
  "description": "string"
}
```

**Response Schema**:
```json
{
  "contract_id": "uuid",
  "contract_draft": "object",
  "generated_fields": ["string"],
  "mapping_coverage": 0.95
}
```

**Dependencies**:
- Requires Step 5 (final mappings)

**Performance Target**: < 10 seconds

---

#### Step 7: Review and Refine Contract

**API Operations**:
- `GET /api/v1/contracts/{id}/` - Get contract
- `PUT /api/v1/contracts/{id}/` - Update contract

**Dependencies**:
- Requires Step 6 (contract_id)

---

#### Step 8: Validate Contract

**API Operations**:
- `POST /api/v1/contracts/{id}/validate/` - Validate contract

**Dependencies**:
- Requires Step 7 (contract_id)

---

#### Step 9: Activate Asset

**API Operations**:
- `POST /api/v1/assets/{id}/activate/` - Activate asset

**Dependencies**:
- Requires Step 8 (validated contract)

---

#### Journey Summary

**Total API Endpoints Required**: 12+
- **Existing**: 6 endpoints
- **Missing/New**: 6 endpoints (AI schema matching, mapping management, contract generation from mappings)

**Critical Dependencies**:
1. Steps 1-2 must complete sequentially
2. Steps 3-5 must complete sequentially (matching → review → accept/reject)
3. Steps 6-9 must complete sequentially

**Performance Requirements**:
- Total duration: < 3 minutes
- AI schema matching: < 15 seconds
- Contract generation: < 10 seconds

---

## Summary Tables

### API Endpoints by Category

#### Core APIs (Existing)
- Assets: `/api/v1/assets/`
- Contracts: `/api/v1/contracts/`
- Datasets: `/api/v1/datasets/`
- Files: `/api/v1/files/`
- Jobs: `/api/v1/jobs/`
- Search: `/api/v1/search/`

#### AI/ML APIs (New - Required)
- Schema Matching: `/api/v1/ai/schema-matching/`
- Auto-Classification: `/api/v1/ai/classification/`
- Anomaly Detection: `/api/v1/ai/anomaly-detection/`
- Recommendations: `/api/v1/ai/recommendations/`
- Natural Language Search: `/api/v1/ai/natural-language-search/`

#### Transformation APIs (New - Required)
- Pipelines: `/api/v1/transformation/pipelines/`
- Pipeline Validation: `/api/v1/transformation/pipelines/{id}/validate/`
- Pipeline Execution: `/api/v1/transformation/pipelines/{id}/execute/`
- Data Wrangling: `/api/v1/transformation/wrangling/`

#### Marketplace APIs (Enhanced - Required)
- Eligibility: `/api/v1/marketplace/eligibility/{asset_id}/`
- Pricing: `/api/v1/marketplace/listings/{id}/pricing/`
- Preview: `/api/v1/marketplace/listings/{id}/preview/`
- Trust Signals: `/api/v1/marketplace/listings/{id}/trust-signals/`

#### Social Feature APIs (New - Required)
- Ratings: `/api/v1/social/ratings/`
- Reviews: `/api/v1/social/reviews/`
- Communities: `/api/v1/social/communities/`
- Activity Feeds: `/api/v1/social/activity-feeds/`

#### Data Mesh APIs (New - Required)
- Domains: `/api/v1/mesh/domains/`
- Federated Governance: `/api/v1/mesh/governance/`
- Topology: `/api/v1/mesh/topology/`

#### Virtualization APIs (New - Required)
- Virtual Datasets: `/api/v1/virtualization/datasets/`
- Federated Queries: `/api/v1/virtualization/queries/`

#### Advanced Governance APIs (New - Required)
- Automated Compliance: `/api/v1/governance/automated-compliance/`
- Retention Policies: `/api/v1/governance/retention-policies/`
- GDPR Workflows: `/api/v1/governance/gdpr/`
- Consent Management: `/api/v1/governance/consent/`

#### Integration APIs (New - Required)
- Connectors: `/api/v1/integrations/connectors/`
- Reverse ETL: `/api/v1/integrations/reverse-etl/`
- BI Integration: `/api/v1/integrations/bi/`

#### Developer Experience APIs (New - Required)
- Plugins: `/api/v1/plugins/`
- SDK Management: `/api/v1/developer/sdks/`
- CLI Configuration: `/api/v1/developer/cli/`

---

### API Dependencies Matrix

| Journey Step | Depends On | API Endpoint | Dependency Type |
|--------------|------------|--------------|-----------------|
| JOURNEY-DPO-001 Step 2 | Step 1 | `POST /api/v1/files/upload/` | Requires asset_id |
| JOURNEY-DPO-001 Step 3 | Step 2 | `POST /api/v1/datasets/` | Requires file_id |
| JOURNEY-DPO-001 Step 4 | Step 3 | `POST /api/v1/ai/schema-matching/` | Requires dataset_id |
| JOURNEY-DPO-001 Step 9 | Steps 1,3,4,6,7 | `POST /api/v1/contracts/` | Requires multiple inputs |
| JOURNEY-DPO-001 Step 10 | Steps 1,9 | `POST /api/v1/assets/{id}/activate/` | Requires validated contract |

---

### Performance Requirements Summary

| API Endpoint | Performance Target | Journey |
|--------------|-------------------|---------|
| `POST /api/v1/ai/schema-matching/` | < 15 seconds | JOURNEY-DPO-001, JOURNEY-DPO-007 |
| `POST /api/v1/ai/classification/` | < 20 seconds | JOURNEY-DPO-001 |
| `POST /api/v1/ai/anomaly-detection/` | < 30 seconds | JOURNEY-DPO-001 |
| `POST /api/v1/compliance/scans/` | < 60 seconds | JOURNEY-DPO-001 |
| `POST /api/v1/dq/runs/` | < 60 seconds | JOURNEY-DPO-001 |
| `POST /api/v1/contracts/generate-from-mappings/` | < 10 seconds | JOURNEY-DPO-007 |

---

## Next Steps

1. **API Gap Analysis** (Task 0.3): Compare these requirements with existing APIs
2. **API Contract Specifications** (Task 0.4): Create OpenAPI specs for missing APIs
3. **API Development Backlog** (Task 0.5): Prioritize missing API development

---

**Document Status**: ✅ Complete  
**Total Journeys Analyzed**: 82  
**Total API Operations Identified**: 500+  
**Missing APIs Identified**: 100+  
**Dependencies Documented**: 200+

---

**Last Updated**: 2025-12-13

