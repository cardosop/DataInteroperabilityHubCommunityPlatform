# RB-TRANS-001: dbt Execution Failure

**Owner:** Data Platform Team
**Severity:** High
**Runbook ID:** RB-TRANS-001

---

## 1. Overview

This runbook covers failures of the `run_dbt_transformation` Prefect flow. A dbt execution failure means the dbt command (`run`, `test`, `parse`, `deps`, or `docs generate`) exited with a non-zero return code or the subprocess itself failed.

## 2. Symptoms

- Prefect flow `run_dbt_transformation` terminates with status `FAILED`
- Pipeline execution status in the hub shows `FAILED`
- `TRANSFORMATION_FAILED` audit event emitted
- Error log in `logs/dbt.log` contains `[error]` lines
- Hub API returns `DBT_EXECUTION_FAILED` error code

## 3. Diagnosis

### 3.1 Check Prefect flow logs
```bash
prefect flow-run logs <flow_run_id>
```

### 3.2 Check dbt error logs
The flow captures ERROR lines from `logs/dbt.log`. Look for:
- Database connection errors: `Database Error`, `connection refused`
- Model compilation errors: `Compilation Error`, `syntax error`
- Missing sources/refs: `Model '...' depends on a node named '...' which was not found`

### 3.3 Check warehouse connectivity
```bash
# From the worker node
python -c "
from hub.apps.transformation.credential_resolver import resolve_warehouse_credentials
profile = resolve_warehouse_credentials('<warehouse_credential_ref>')
print(profile)
"
```

### 3.4 Check profiles.yml validity
The profiles.yml is written to `/tmp/meshant_dbt_{pipeline_id}_{execution_id}/`. Verify:
- Correct warehouse type, account, credentials
- dbt can connect: `dbt debug --profiles-dir /tmp/meshant_dbt_<id>/`

## 4. Impact

- Pipeline execution fails; downstream data products that depend on the output table are stale
- Tenant's `max_transformation_runs_per_month` quota is consumed (failed runs count against the limit)
- No output Dataset or lineage edge is created on failure

## 5. Resolution

### 5.1 Model compilation error
- Fix the dbt model SQL and push to the dbt git repo
- Re-run the pipeline execution

### 5.2 Warehouse connection error
1. Verify the AWS SM secret referenced by `warehouse_credential_ref` is valid and not rotated
2. Check that the warehouse is reachable from the Prefect worker node
3. Verify the profiles.yml credentials match the warehouse connection config

### 5.3 Git clone failure
1. Verify the `git_repo_url` and `git_credential_ref` are correct
2. Check that the PAT has not expired and has `repo` scope
3. Verify the repo is accessible from the worker node

```bash
# Test git clone manually
git clone --depth 1 https://x-access-token:<PAT>@github.com/<org>/<repo>.git /tmp/test_clone
```

### 5.4 Retry the execution
```bash
# Via CLI
datahub transformation execute <pipeline_id> --asset-id <asset_id>

# Via API
curl -X POST /api/v1/transformation/pipelines/<id>/execute/ \
  -H "Authorization: ..." -H "X-Tenant-ID: ..." \
  -d '{"asset_id": "..."}'
```

## 6. Escalation

| Level | Contact | When |
|-------|---------|------|
| L1 | Data Platform on-call | Any dbt execution failure |
| L2 | dbt project owner (tenant admin) | Model compilation issues |
| L3 | Warehouse DBA | Persistent warehouse connectivity issues |
| L4 | Security team | Credential rotation / access denied |

## 7. Prevention

- Pre-validate dbt projects with `dbt parse` before committing to main branch
- Set up warehouse connection health checks (ping INFORMATION_SCHEMA)
- Monitor `TRANSFORMATION_FAILED` audit event rate
- Rotate warehouse credentials with sufficient overlap to avoid execution windows
- Run `cleanup_transformation_work_dirs --older-than=7d` weekly
