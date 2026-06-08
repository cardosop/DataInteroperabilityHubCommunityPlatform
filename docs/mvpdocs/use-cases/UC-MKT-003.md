# UC-MKT-003: Import Data from External Provider

**ID:** UC-MKT-003
**Title:** Import Data from External Marketplace Provider
**Persona:** Data Product Owner (DPO)
**Priority:** Medium
**Phase:** 284.A (GA)
**Feature Flag:** `federated_import_enabled` (OFF by default, requires DPO + Legal signoff)

## Summary

A Data Product Owner discovers and imports a data product from an external
marketplace (Snowflake, AWS Data Exchange, Databricks, or Google Analytics Hub)
into the tenant's Meshant catalogue using federated import.

## Preconditions

- Tenant has `federated_import_enabled = True`
- DPO and Legal signoff obtained
- AWS Secrets Manager ARN configured with provider credentials
- Cross-region consent obtained if source and consumer regions differ

## Main Flow

1. DPO navigates to Federated Import page
2. DPO browses the list of supported providers (Snowflake Marketplace,
   AWS Data Exchange, Databricks Marketplace, Google Analytics Hub)
3. DPO selects a provider and enters the AWS Secrets Manager ARN
   (raw credentials never accepted)
4. DPO optionally specifies an external listing ID and data strategy
   (Metadata Only, Download Selective, Download All)
5. Hub creates an async `FEDERATED_IMPORT` job and returns the job ID
6. DPO polls the job status; Hub shows PENDING → RUNNING → COMPLETED/FAILED
7. On completion, the imported asset appears in the tenant catalogue
   with FEDERATED source type and linked ODPS/ODCS contracts
8. DPO can cancel a PENDING or RUNNING job

## Acceptance Criteria

- Provider list shows 4 supported marketplaces
- Import form validates AWS SM ARN format
- Credential reference masked in API responses and logs
- Job status polling functional
- Imported asset appears in catalogue with correct source type
- Cross-region consent enforced when regions differ
