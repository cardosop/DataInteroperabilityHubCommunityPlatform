# RB-TRANS-003: Contract Validation Failure

**Owner:** Data Platform Team
**Severity:** Medium
**Runbook ID:** RB-TRANS-003

---

## 1. Overview

This runbook covers failures of the `validate-output` endpoint (285.9.3.2) and the `DbtContractGenerator` (285.9.2.1.1). Contract validation compares the output table schema against the HubContract and returns a structured diff.

## 2. Symptoms

- `POST /transformation/pipelines/{id}/validate-output/` returns schema diff with `match: false`
- `CONTRACT_GENERATION_FAILED` error when generating contract from dbt YAML
- `SCHEMA_MISMATCH` in the validation response
- `VALIDATION_QUERY_FAILED` when the warehouse INFORMATION_SCHEMA query fails

## 3. Diagnosis

### 3.1 Check the validation diff
```bash
datahub transformation validate-output <pipeline_id> \
  --database <db> --table-name <table> --warehouse-type snowflake
```
The diff shows:
- `added`: columns in the output table but not in the contract
- `removed`: columns in the contract but not in the output table
- `changed`: columns present in both but with different types

### 3.2 Check contract generation
```bash
datahub transformation generate-contract <pipeline_id>
```
Verify the generated contract matches the expected schema.

### 3.3 Check warehouse connectivity
If `VALIDATION_QUERY_FAILED`:
- Verify the warehouse connection is active (`is_active=True` on `WarehouseConnection`)
- Check the connector subclass is installed (Snowflake/BQ/Databricks driver)
- Verify the table exists in the warehouse

### 3.4 Check dbt YAML
If `CONTRACT_GENERATION_FAILED`:
- Verify `models/*.yml` files exist in the dbt project
- Check YAML syntax: valid YAML mapping with `models` key
- Verify each model has a `name` field and each column has a `name` field

## 4. Impact

- Schema drift is detected but does not block pipeline execution (validation is non-blocking)
- The output Dataset is still registered; lineage edges are still created
- The contract preview page shows the diff

## 5. Resolution

### 5.1 Schema mismatch — columns added to output
- Update the dbt model YAML to include the new columns with descriptions and tests
- Re-generate the contract preview
- Accept the updated contract

### 5.2 Schema mismatch — columns removed from output
- Check if the dbt model SQL was changed to exclude columns
- Update the dbt model YAML to remove the dropped columns
- Or restore the missing columns in the dbt model SQL

### 5.3 Schema mismatch — type changes
- Verify the type change is intentional (e.g., `varchar(255)` → `varchar(512)`)
- Update the contract to reflect the new types
- If the change is breaking, coordinate with downstream consumers

### 5.4 Contract generation failure
- Fix the YAML syntax error in `models/*.yml`
- Ensure all models have a `name` and all columns have a `name`
- Run `dbt parse` to validate the dbt project

## 6. Escalation

| Level | Contact | When |
|-------|---------|------|
| L1 | Data Platform on-call | Contract generation failure |
| L2 | dbt project owner (tenant admin) | Schema mismatch resolution |
| L3 | Data Governance team | Breaking schema changes |

## 7. Prevention

- Run `dbt parse` in CI/CD to catch YAML/structure errors before deployment
- Include contract validation in the pipeline execution flow
- Set up monitoring for `SCHEMA_MISMATCH` rate per pipeline
- Document expected schema evolution process in PRODUCT_GUIDE.md
