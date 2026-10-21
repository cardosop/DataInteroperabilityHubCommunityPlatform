# How to Create a dbt-Native Transformation Pipeline

**Persona:** Data Engineer
**Phase:** 285.9 (dbt-Native Transformation Engine)
**Status:** ✅ Implemented

## Overview

Create a dbt-native transformation pipeline that executes dbt Core models directly in your data warehouse.

## Prerequisites

- `transformation_enabled` feature flag enabled for your tenant
- AWS Secrets Manager secrets for warehouse credentials and git PAT
- A dbt project in a Git repository
- `transformation:write` scope on your API key

## Steps

### 1. Create the Pipeline

```bash
datahub transformation pipelines create \
  --name "Customer Analytics" \
  --pipeline-definition '{"version": "1.0.0", "steps": []}' \
  --warehouse-credential-ref "arn:aws:secretsmanager:us-east-1:123456789012:secret:wh-dbt" \
  --git-credential-ref "arn:aws:secretsmanager:us-east-1:123456789012:secret:git-pat" \
  --source-config '{"git_repo_url": "https://github.com/acme/dbt-project.git", "target_name": "prod", "dbt_timeout_seconds": 3600}'
```

### 2. Generate a Contract

```bash
datahub transformation generate-contract <pipeline_id>
```

### 3. Execute the Pipeline

```bash
datahub transformation pipelines execute <pipeline_id> --asset-id <asset_id>
```

### 4. Validate Output

```bash
datahub transformation validate-output <pipeline_id> \
  --database analytics --table-name customers --warehouse-type snowflake
```

## Via Wizard (UI)

1. Navigate to `/transformation/pipelines/<id>/wizard`
2. Choose "Code First" direction
3. Configure dbt project (git URL, credentials, warehouse type)
4. Review generated contract
5. Execute pipeline

## See Also

- [Product Guide: Transformation Pipeline](../../../PRODUCT_GUIDE.md#transformation-pipeline)
- [RB-TRANS-001: dbt Execution Failure](../../../runbooks/RB-TRANS-001-dbt-execution-failure.md)
