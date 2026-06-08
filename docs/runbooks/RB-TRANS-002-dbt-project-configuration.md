# RB-TRANS-002: dbt Project Configuration

**Owner:** Data Platform Team
**Severity:** Medium
**Runbook ID:** RB-TRANS-002

---

## 1. Overview

This runbook covers issues with dbt project configuration stored on the `TransformationPipeline` model: missing or invalid `source_config`, `warehouse_credential_ref`, `git_credential_ref`, or `git_repo_url`.

## 2. Symptoms

- Pipeline execution fails during `_task_setup_dbt_environment` before reaching dbt
- Hub API returns `DBT_PROFILE_INVALID` or `DBT_PROJECT_NOT_FOUND`
- Prefect flow fails with "Pipeline has no warehouse_credential_ref set"
- `CredentialResolverError` raised: "Access denied for secret" or "Secret not found"

## 3. Diagnosis

### 3.1 Check pipeline configuration
```bash
datahub transformation pipelines get <pipeline_id>
```
Verify these fields are set:
- `warehouse_credential_ref`: valid AWS SM ARN
- `git_credential_ref`: valid AWS SM ARN for Git PAT
- `source_config.git_repo_url`: valid HTTPS Git URL
- `source_config.target_name`: dbt target (default: "prod")
- `source_config.dbt_timeout_seconds`: positive integer

### 3.2 Verify AWS Secrets Manager secrets exist
```bash
aws secretsmanager get-secret-value \
  --secret-id <warehouse_credential_ref> \
  --region us-east-1
```

### 3.3 Verify secret format
Warehouse secret must be a JSON object:
```json
{
  "type": "snowflake",
  "account": "xy12345.us-east-1",
  "user": "dbt_user",
  "password": "...",
  "role": "transform",
  "database": "analytics",
  "warehouse": "compute_wh",
  "schema": "public"
}
```

Git secret must contain:
```json
{
  "token": "ghp_...",
  "provider": "github"
}
```

## 4. Impact

- Pipeline cannot be enqueued; `enqueue_dbt_job()` raises `ValidationError`
- User sees 400 error on the execute endpoint
- No job is created, no quota is consumed

## 5. Resolution

### 5.1 Missing credential refs
```bash
# Via API
curl -X PATCH /api/v1/transformation/pipelines/<id>/ \
  -H "Authorization: ..." -H "Content-Type: application/json" \
  -d '{
    "warehouse_credential_ref": "arn:aws:secretsmanager:...",
    "git_credential_ref": "arn:aws:secretsmanager:...",
    "source_config": {
      "git_repo_url": "https://github.com/acme/dbt-project.git",
      "target_name": "prod",
      "dbt_timeout_seconds": 3600
    }
  }'
```

### 5.2 Invalid AWS SM ARN
- Ensure the ARN format is: `arn:aws:secretsmanager:<region>:<account-id>:secret:<name>`
- Verify the Prefect worker IAM role has `secretsmanager:GetSecretValue` permission
- Check the secret exists in the correct AWS account and region

### 5.3 Rotated credentials
- Update the AWS SM secret value with the new credentials
- The credential resolver always fetches the latest version (no caching)
- Next pipeline execution will pick up the new credentials automatically

## 6. Escalation

| Level | Contact | When |
|-------|---------|------|
| L1 | Data Platform on-call | Pipeline config validation failure |
| L2 | AWS IAM admin | AccessDenied on Secrets Manager |
| L3 | Tenant admin | Incorrect pipeline configuration |

## 7. Prevention

- Validate credential refs at pipeline creation time (model `clean()` validates ARN format)
- Set up AWS CloudWatch alarms on Secrets Manager access denied events
- Document the expected secret format in the product guide
- Use the wizard UI to configure dbt projects with guided field validation
