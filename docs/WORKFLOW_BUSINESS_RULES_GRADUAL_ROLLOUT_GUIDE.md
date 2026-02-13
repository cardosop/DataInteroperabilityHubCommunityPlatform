# Workflow Business Rules Validation — Gradual Rollout Guide

**Version:** 1.0.0  
**Last Updated:** 2026-01-28  
**Status:** Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Workflow Tiers](#workflow-tiers)
3. [Phase 5.2.1 — Enable for Test Workflows](#phase-521--enable-for-test-workflows)
4. [Phase 5.2.2 — Enable for Production Workflows](#phase-522--enable-for-production-workflows)
5. [Phase 5.2.3 — Full Rollout](#phase-523--full-rollout)
6. [Monitoring and Verification](#monitoring-and-verification)
7. [Reporting Rollout Status](#reporting-rollout-status)

---

## Overview

This guide describes how to roll out workflow business rules validation in three phases:

- **5.2.1** Enable validation only for **test/non-critical** workflows; monitor and verify.
- **5.2.2** Enable validation for **production/critical** workflows **incrementally**; monitor and verify.
- **5.2.3** **Full rollout**: enable for all workflows; monitor and verify.

All phases use the same feature flags and settings from [Task 5.1](WORKFLOW_BUSINESS_RULES_ROLLBACK_GUIDE.md). No mocks or stubs are used; behavior is driven by environment variables and Django settings.

---

## Workflow Tiers

Workflow names are grouped into tiers for phased rollout. These are defined in Django settings and can be overridden via environment variables.

| Tier | Purpose | Default workflow names (from settings) |
|------|---------|----------------------------------------|
| **Test / non-critical** | Enable validation first (5.2.1) | `model_training`, `model_inference`, `api_key_management`, `data_quality_check`, `virtualization_query_execution` |
| **Critical / production** | Enable incrementally (5.2.2) | `product_creation`, `contract_creation`, `asset_creation`, `dataset_creation`, `marketplace_publication`, `scheduled_ingestion`, `access_request`, `compliance_reporting`, `data_mesh`, `version_creation`, `marketplace_sync` |

- **Test workflows**: Lower business impact; safe to validate first.
- **Critical workflows**: Core business flows; enable in small batches and monitor.

Override lists via:

- `WORKFLOW_BUSINESS_RULES_VALIDATION_TEST_WORKFLOWS` (comma-separated or JSON list)
- `WORKFLOW_BUSINESS_RULES_VALIDATION_CRITICAL_WORKFLOWS` (comma-separated or JSON list)

---

## Phase 5.2.1 — Enable for Test Workflows

**Goal:** Enable business rules validation only for non-critical (test) workflows. Monitor metrics and errors; verify behavior.

### Steps

1. **Enable validation only for test workflows**

   Set environment variables (or Django settings) so that **only** the test workflow list has validation enabled:

   - `ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True`
   - `WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0`  
     (so rollout % does not enable others)
   - `WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=<test workflow list>`
   - `WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=` (empty)
   - `WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS=` (empty, or use for overrides)

   Example (using test workflows from settings default):

   ```bash
   export ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True
   export WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0
   export WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS='["model_training","model_inference","api_key_management","data_quality_check","virtualization_query_execution"]'
   ```

   Or in `.env`:

   ```
   ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True
   WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0
   WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=["model_training","model_inference","api_key_management","data_quality_check","virtualization_query_execution"]
   ```

2. **Restart api-service** (and workflow-engine if used) so they pick up the new settings.

3. **Monitor metrics and errors**  
   Use existing dashboards and alerts from [5.1.2](WORKFLOW_BUSINESS_RULES_ROLLBACK_GUIDE.md):
   - Validation success/failure rates
   - Validation duration (e.g. P95)
   - Workflow execution success/failure and duration
   - Alerts for validation failures or high error rate

4. **Verify behavior**
   - Run the management command to confirm only test workflows have validation enabled:
     ```bash
     docker compose exec api-service python hub/manage.py report_workflow_validation_rollout
     ```
   - Run test workflows and confirm validation runs (logs/metrics).
   - Run a critical workflow and confirm validation is **not** applied (per config).

---

## Phase 5.2.2 — Enable for Production Workflows

**Goal:** Enable validation for critical workflows **incrementally**. Monitor metrics and errors; verify after each step.

### Steps

1. **Add critical workflows in small batches**

   Keep:
   - `ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True`
   - `WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=0` until the final step

   **Incremental option A — extend enabled list**

   Add one or a few critical workflow names to `WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS` (in addition to the test workflows). Example first batch:

   ```bash
   # Example: add product_creation and contract_creation
   export WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS='["model_training","model_inference","api_key_management","data_quality_check","virtualization_query_execution","product_creation","contract_creation"]'
   ```

   After monitoring, add the next batch (e.g. `asset_creation`, `dataset_creation`), and so on.

   **Incremental option B — per-workflow config**

   Use `WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS` to enable specific workflows by name, e.g. `{"product_creation": true, "contract_creation": true}`. Combine with `ENABLED_WORKFLOWS` if you prefer a mix.

2. **Restart api-service** (and workflow-engine) after each change.

3. **Monitor metrics and errors**  
   Same as 5.2.1: validation and workflow dashboards, alerts for failures and latency.

4. **Verify behavior**
   - Run `report_workflow_validation_rollout` and confirm the newly added workflows show as enabled.
   - Run those workflows and confirm validation runs and success/latency are acceptable.
   - If issues appear, remove the workflow from the enabled list (or set to false in WORKFLOWS) and roll back; fix root cause before re-adding.

---

## Phase 5.2.3 — Full Rollout

**Goal:** Enable validation for **all** workflows. Monitor and verify.

### Steps

1. **Enable validation globally**

   Either:

   - **Option A — 100% rollout, no disabled list**
     - `ENABLE_WORKFLOW_BUSINESS_RULES_VALIDATION=True`
     - `WORKFLOW_BUSINESS_RULES_VALIDATION_ROLLOUT_PERCENTAGE=100`
     - `WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS=` (empty)
     - `WORKFLOW_BUSINESS_RULES_VALIDATION_DISABLED_WORKFLOWS=` (empty)
     - `WORKFLOW_BUSINESS_RULES_VALIDATION_WORKFLOWS=` (empty)

   - **Option B — Keep explicit enabled list**  
     Leave `WORKFLOW_BUSINESS_RULES_VALIDATION_ENABLED_WORKFLOWS` set to the full list of all workflows (test + critical) and `ROLLOUT_PERCENTAGE=0`. This is equivalent to “all listed workflows have validation.”

2. **Restart api-service** (and workflow-engine).

3. **Monitor metrics and errors**  
   Same as 5.2.1 and 5.2.2. Ensure no degradation in workflow success rate or latency.

4. **Verify behavior**
   - Run `report_workflow_validation_rollout` and confirm all intended workflows show validation enabled.
   - Run a sample of workflows (test and critical) and confirm validation runs and behavior is correct.

---

## Monitoring and Verification

Across all phases:

- **Dashboards:** Use the workflow orchestration and validation dashboards (Grafana) from 5.1.2.
- **Alerts:** Rely on alerts for validation failures, high error rate, and high duration (5.1.2).
- **Logs:** Use structured logging and aggregation (5.1.2) to inspect validation and workflow execution.
- **Verification:** Use the management command and manual runs as above; no mocks—real feature flags and real workflows.

---

## Reporting Rollout Status

Use the management command to see current configuration and which workflows have validation enabled:

```bash
docker compose exec api-service python hub/manage.py report_workflow_validation_rollout
```

Output includes:

- Global and rollout settings
- Test and critical workflow lists (from settings)
- For each known workflow name: whether validation is currently enabled

This supports verification for 5.2.1, 5.2.2, and 5.2.3 without mocking.

---

## Related Documentation

- [Workflow Business Rules Rollback Guide](WORKFLOW_BUSINESS_RULES_ROLLBACK_GUIDE.md) — Rollback and 5.1 deployment preparation
- [Monitoring Guide](MONITORING.md) — Monitoring and observability
- [Workflow Orchestration](WORKFLOW_ORCHESTRATION.md) — Workflow engine and definitions

---

**Last Updated:** 2026-01-28  
**Maintainer:** Platform Team
